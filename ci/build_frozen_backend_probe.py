#!/usr/bin/env python3
"""Relink one verified Linux backend translation unit into frozen runners."""
from pathlib import Path
import argparse
import hashlib
import json
from build_frozen_runner_probe import command, save, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variants', type=Path, required=True)
    parser.add_argument('--backend-source', type=Path, required=True)
    parser.add_argument('--source-git-blob', required=True)
    parser.add_argument('--header-git-blob', action='append', default=[], help='published changed header as name=git-blob')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build = json.loads((args.variants/'verified.json').read_text())
    plan = json.loads((args.variants/'plan.json').read_text())
    assert build['baseline_reproduced_exactly'] and build['originals_unchanged']
    target = Path(plan['target'])
    database = json.loads((target/'compile_commands.json').read_text())
    entries = [entry for entry in database if entry['file'].endswith('/src/process.cpp')]
    assert len(entries) == 1
    entry = entries[0]
    source = args.backend_source.resolve()
    data = source.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert blob == args.source_git_blob, 'backend source differs from the requested published blob'
    original_source = Path(entry['file'])
    expected_headers = dict(item.split('=', 1) for item in args.header_git_blob)
    changed_headers = {}
    for header in source.parent.glob('*.h'):
        other = original_source.parent/header.name
        assert other.is_file(), 'backend header was added'
        if sha(header) == sha(other):
            continue
        contents = header.read_bytes()
        header_blob = hashlib.sha1(b'blob '+str(len(contents)).encode()+b'\0'+contents).hexdigest()
        assert expected_headers.get(header.name) == header_blob, 'unverified changed backend header: '+header.name
        changed_headers[header.name] = header_blob
    assert changed_headers == expected_headers
    original_object = Path(entry['output'])
    before = {path:sha(path) for path in plan['objects']}
    objects = {}
    for label, translation_unit in [('original', original_source), ('filtered', source)]:
        obj = output/(label+'-process.o')
        argv = [str(translation_unit) if item == entry['file'] else str(obj) if item == entry['output'] else item
                for item in entry['arguments']]
        argv.insert(1, '-I'+str(original_source.parent))
        command(argv, entry['directory'], output/(label+'-compile.log'))
        if label == 'original':
            assert sha(obj) == sha(original_object), 'original backend object failed reproduction'
        objects[label] = obj
    results = []
    for old_label, label in [('baseline', 'filtered'), ('baseline-phases', 'filtered-phases')]:
        original = next(row for row in build['results'] if row['label'] == old_label)
        assert sha(original['path']) == original['sha256']
        assert original['link_command'].count(str(original_object)) == 1
        runner = output/(label+'-okrun')
        argv = [str(objects['filtered']) if item == str(original_object) else str(runner) if item == original['path'] else item
                for item in original['link_command']]
        command(argv, target, output/(label+'-link.log'))
        results.append(dict(label=label, path=str(runner), sha256=sha(runner), link_command=argv))
    assert all(sha(path) == value for path,value in before.items())
    save(output/'verified.json', dict(results=results, original_backend_object_reproduced=True,
        original_objects_unchanged=True, backend_git_blob=blob, backend_source_sha256=sha(source),
        changed_header_git_blobs=changed_headers,
        source_original_sha256=sha(original_source), variants_sha256=sha(args.variants/'verified.json'),
        scope='One published Linux process translation unit differs. Both phase variants use the same meter. No clangd recompilation or release qualification.',
        valid=True, qualification=False))
    print(json.dumps(dict(valid=True, runners={row['label']:row['sha256'] for row in results})))


if __name__ == '__main__':
    main()
