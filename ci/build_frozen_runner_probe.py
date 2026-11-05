#!/usr/bin/env python3
"""Build diagnostic runner variants from one completed, pinned source build.

The original object files remain untouched.  Recompilation of the original
translation units and relinking must reproduce the baseline binary exactly.
This tool never compiles clangd or changes its payload.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def command(argv, cwd, log):
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=120)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (argv[0], result.returncode, str(log))


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after)


def cpu_moments(text):
    text = replace_once(
        text, 'struct moment { const char* name; kal_u64 ns, faults; };',
        'struct moment { const char* name; kal_u64 ns, faults, cpu_ns; kal_u32 present; };')
    first = text.index('kal_u64 faults_now() {')
    last = text.index('\n// --- the touches', first)
    text = text[:first] + '''moment process_moment(const char* name) {
    moment result{ name, kal_time_monotonic() - g_started, 0, 0, 0 };
    kal_process self{};
    if (kal_process_self(&self) != kal_ok) return result;
    kal_program_info info{};
    info.self_size = sizeof info;
    const int e = kal_process_info(self, KAL_PINFO_FAULTS | KAL_PINFO_CPU, &info);
    kal_process_close(self);
    if (e == kal_ok) {
        result.present = info.present;
        result.faults = info.faults_minor + info.faults_major;
        result.cpu_ns = info.cpu_ns;
    }
    return result;
}
''' + text[last:]
    text = replace_once(text,
        'moment{ name, kal_time_monotonic() - g_started, faults_now() }',
        'process_moment(name)')
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if 'b.number(g_moments[i].faults);' in line)
    lines[index + 1:index + 1] = [
        '        b.put(", \\"cpu_ns\\": "); b.number(g_moments[i].cpu_ns);',
        '        b.put(", \\"present\\": "); b.number(g_moments[i].present);']
    return '\n'.join(lines) + '\n'


def compilation_database(source):
    matches = []
    for path in source.glob('target/*/*/compile_commands.json'):
        entries = json.loads(path.read_text())
        binding = [entry for entry in entries if Path(entry['file']) == source/'run/src/bindings.cpp']
        if binding:
            matches.append((path.parent, entries))
    assert len(matches) == 1, 'expected one actual runner compilation database'
    return matches[0]


def include_directories(arguments):
    result = []
    for index, value in enumerate(arguments):
        if value == '-I':
            result.append(Path(arguments[index + 1]))
        elif value.startswith('-I'):
            result.append(Path(value[2:]))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    target, database = compilation_database(source)
    commands = {name: next(entry for entry in database if Path(entry['file']) == source/('run/src/' + name + '.cpp'))
                for name in ['bindings', 'prof']}
    lines = (target/'build.ninja').read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith('build bin/openkal-tools/okrun : cxx_link ')]
    assert len(starts) == 1
    start = starts[0]
    objects = shlex.split(lines[start].split(' : cxx_link ', 1)[1])
    assert objects and all(name.endswith('.o') for name in objects)
    variables = {}
    for line in lines[start + 1:]:
        if not line.startswith('  '):
            break
        key, value = line.strip().split(' = ', 1)
        variables[key] = value
    assert all('$' not in variables[key] for key in ['ldflags', 'unit_ldflags'])
    baseline = target/'bin/openkal-tools/okrun'
    object_hashes = {str(target/name): sha(target/name) for name in objects}
    surfaces = [directory/'surface.inc' for directory in include_directories(commands['bindings']['arguments'])
                if (directory/'surface.inc').is_file()]
    assert len(surfaces) == 1
    surface = surfaces[0]
    plan = dict(source=str(source), target=str(target), original_runner_sha256=sha(baseline),
        compiler=commands['bindings']['arguments'][0], compiler_sha256=sha(commands['bindings']['arguments'][0]),
        objects=object_hashes, source_hashes={name: sha(entry['file']) for name, entry in commands.items()},
        surface_sha256=sha(surface), qualification=False,
        scope='Matched runner variants only. Original object/binary bytes must reproduce; clangd is never rebuilt.')
    save(output/'plan.json', plan)
    candidate = output/'candidate'
    candidate.mkdir()
    original_binding = Path(commands['bindings']['file']).read_text()
    marker = '#define OKRUN_BIND(n, i)'
    assert original_binding.count(marker) == 2
    (candidate/'bindings.cpp').write_text(original_binding.replace(
        marker, (HERE/'diagnostic_child_prefetch.inc').read_text() + '\n' + marker, 1))
    table, changed = re.subn(r'^OKRUN_BIND\(kal_process_spawn, (\d+)\)$',
                            r'OKRUN_OWN(kal_process_spawn, \1)', surface.read_text(), flags=re.M)
    assert changed == 1
    (candidate/'surface.inc').write_text(table)
    (candidate/'prof.cpp').write_text(cpu_moments(Path(commands['prof']['file']).read_text()))
    compiled = {}
    compile_records = []
    for kind, entry in commands.items():
        for label in ['original', 'candidate']:
            source_file = Path(entry['file']) if label == 'original' else candidate/(kind + '.cpp')
            obj = output/(kind + '-' + label + '.o')
            argv = [str(source_file) if item == entry['file'] else str(obj) if item == entry['output'] else item
                    for item in entry['arguments']]
            argv.insert(1, '-I' + str(Path(entry['file']).parent))
            command(argv, entry['directory'], output/(kind + '-' + label + '-compile.log'))
            if label == 'original':
                assert sha(obj) == sha(entry['output']), 'original object must reproduce exactly'
            compiled[(kind, label)] = obj
            compile_records.append(dict(kind=kind, label=label, argv=argv, sha256=sha(obj)))
    results = []
    for label, child, phases in [('baseline', False, False), ('candidate', True, False),
                                  ('baseline-phases', False, True), ('candidate-phases', True, True)]:
        replacements = {commands['bindings']['output']: compiled[('bindings', 'candidate' if child else 'original')],
                        commands['prof']['output']: compiled[('prof', 'candidate' if phases else 'original')]}
        link_objects = [str(replacements.get(str(target/name), target/name)) for name in objects]
        runner = output/(label + '-okrun')
        argv = [plan['compiler'], *link_objects, '-o', str(runner),
                *shlex.split(variables['ldflags']), *shlex.split(variables['unit_ldflags'])]
        command(argv, target, output/(label + '-link.log'))
        if label == 'baseline':
            assert sha(runner) == plan['original_runner_sha256'], 'baseline binary must reproduce exactly'
        results.append(dict(label=label, path=str(runner), sha256=sha(runner), bytes=runner.stat().st_size,
                            child_prefetch=child, cpu_phases=phases, link_command=argv))
    meter = output/'native-main-meter.so'
    cc = shutil.which('cc')
    assert cc
    common = [cc, '-O2', '-Wall', '-Wextra', '-Werror']
    command([*common, '-fPIC', '-shared', '-o', str(meter), str(HERE/'diagnostic_native_main_meter.c'), '-ldl'],
            output, output/'native-meter-compile.log')
    control = output/'native-meter-control'
    command([*common, '-o', str(control), str(HERE/'diagnostic_native_meter_control.c')],
            output, output/'native-control-compile.log')
    assert all(sha(path) == digest for path, digest in object_hashes.items())
    assert sha(baseline) == plan['original_runner_sha256']
    save(output/'verified.json', dict(results=results, compile_records=compile_records,
        meter=dict(path=str(meter), sha256=sha(meter), source_sha256=sha(HERE/'diagnostic_native_main_meter.c')),
        meter_control=dict(path=str(control), sha256=sha(control)),
        baseline_reproduced_exactly=True, originals_unchanged=True, valid=True, qualification=False))
    print(json.dumps(dict(runners={row['label']: row['sha256'] for row in results},
                          baseline_reproduced_exactly=True, valid=True)))


if __name__ == '__main__':
    main()
