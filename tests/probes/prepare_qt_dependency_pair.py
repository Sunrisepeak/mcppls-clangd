#!/usr/bin/env python3
"""Prepare include/import Qt probes without changing the original project.

The header arm uses the actual GCC std provider's global module fragment.
Both arms retain the original compiler flags and provider entries, isolating
source dependency spelling first. This is a selected-completion comparison,
not proof that textual headers expose exactly the module's exported API.
Use the prepared main.cpp as project_completion.py --draft-source, keeping
--source/--project/--compile-commands-dir on the original project. The copied
CDBs are transformation records; moved source URIs can change PCH eligibility.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--cdb', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source, cdb = args.source.resolve(), args.cdb.resolve()
    entries = json.loads(cdb.read_text())
    matches = [e for e in entries if
               (Path(e['directory']) / e['file']).resolve() == source]
    providers = [e for e in entries if e['file'].endswith('/bits/std.cc')]
    if len(matches) != 1 or len(providers) != 1:
        parser.error('requires one source entry and one actual GCC std provider')
    if not all('arguments' in e for e in matches):
        parser.error('source CDB must contain structured arguments')
    provider = (Path(providers[0]['directory']) / providers[0]['file']).resolve()
    provider_text = provider.read_text()
    if provider_text.count('export module std;') != 1:
        parser.error('unrecognized GCC std provider')
    fragment = provider_text.split('export module std;', 1)[0]
    if fragment.count('module;') != 1:
        parser.error('requires a single global module fragment')
    fragment = fragment.split('module;', 1)[1]
    original = source.read_text()
    if original.count('import std;') != 1 or original.count('import nlohmann.json;') != 1:
        parser.error('requires the Qt fixture with both named imports')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('output must be empty; existing evidence is never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    arms = {}
    for mode in ('modules', 'headers'):
        directory = output / mode
        directory.mkdir()
        target = directory / source.name
        # Qt defines emit/slots: placing syncstream or JSON after Qt changes
        # their declarations and makes the textual TU ill-formed. Load the
        # dependency headers before Qt, as a valid textual project would.
        text = original if mode == 'modules' else (
            fragment + '\n#include <nlohmann/json.hpp>\n' +
            original.replace('import std;', '').replace('import nlohmann.json;', ''))
        target.write_text(text)
        arm = copy.deepcopy(entries)
        entry = arm[entries.index(matches[0])]
        count = sum((Path(entry['directory']) / a).resolve() == source
                    for a in entry['arguments'])
        if count != 1:
            raise ValueError('actual source must occur exactly once in arguments')
        entry['arguments'] = [str(target) if
            (Path(entry['directory']) / a).resolve() == source else a
            for a in entry['arguments']]
        entry['arguments'].insert(1, '-I' + str(source.parent))
        entry['file'] = str(target)
        arm_cdb = directory / 'compile_commands.json'
        arm_cdb.write_text(json.dumps(arm, indent=2) + '\n')
        arms[mode] = {'source': str(target), 'source_sha256': sha(target),
                      'cdb_sha256': sha(arm_cdb)}
    (output / 'identity.json').write_text(json.dumps({
        'original_source': str(source), 'original_sha256': sha(source),
        'original_cdb_sha256': sha(cdb), 'std_provider': str(provider),
        'std_provider_sha256': sha(provider), 'arms': arms,
        'limits': ['Module flags and provider entries retained in both arms.',
                   'Original build cwd retained; original source include path added to both.',
                   'Textual macro/declaration exposure differs from module exports.',
                   'Dependency headers precede Qt to avoid emit/slots macro collisions.',
                   'Use typed Sema and actual insertion checks for each selected context.']
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
