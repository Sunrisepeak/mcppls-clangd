"""Apply the server's actual LSP edits and compile the resulting unsaved TU.

Unknown snippet constructs fail closed. Placeholder bindings are supplied by
the legal fixture, rather than guessing expressions from parameter names.
"""
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


def offset(text, position):
    lines = text.splitlines(keepends=True)
    line, character = position['line'], position['character']
    if line == len(lines) and character == 0:
        return len(text)
    if not 0 <= line < len(lines):
        raise ValueError('edit line outside document')
    current = lines[line]
    encoded = current.encode('utf-16-le')
    if character * 2 > len(encoded):
        raise ValueError('edit character outside line')
    prefix = encoded[:character * 2].decode('utf-16-le')
    return sum(map(len, lines[:line])) + len(prefix)


def snippet(text, bindings):
    output, cursor = [], 0
    while cursor < len(text):
        char = text[cursor]
        if char == '\\':
            cursor += 1
            if cursor == len(text) or text[cursor] not in '\\$}':
                raise ValueError('unsupported snippet escape')
            output.append(text[cursor])
            cursor += 1
        elif char != '$':
            output.append(char)
            cursor += 1
        else:
            match = re.match(r'\$(\d+)|\$\{(\d+)(?::([^{}]*))?\}', text[cursor:])
            if not match:
                raise ValueError('unsupported snippet variable, choice, nesting or transform')
            number = match.group(1) or match.group(2)
            default = match.group(3) or ''
            output.append(bindings.get(number, default))
            cursor += len(match.group(0))
    return ''.join(output)


def apply(text, position, item, bindings):
    edit = item.get('textEdit')
    if edit:
        primary = {'range': edit.get('range', edit.get('replace')), 'newText': edit['newText']}
    else:
        end = offset(text, position)
        begin = end
        while begin and (text[begin - 1].isalnum() or text[begin - 1] == '_'):
            begin -= 1
        primary = {'range': None, 'newText': item.get('insertText', item['label'])}
    replacement = primary['newText']
    if item.get('insertTextFormat', 1) == 2:
        replacement = snippet(replacement, bindings)
    if primary['range'] is not None:
        begin = offset(text, primary['range']['start'])
        end = offset(text, primary['range']['end'])
    edits = [(begin, end, replacement)]
    for extra in item.get('additionalTextEdits', []):
        edits.append((offset(text, extra['range']['start']),
                      offset(text, extra['range']['end']), extra['newText']))
    ordered = sorted(edits)
    for first, second in zip(ordered, ordered[1:]):
        if first[1] > second[0] or first[0] == second[0]:
            raise ValueError('overlapping completion edits')
    for begin, end, replacement in reversed(ordered):
        if begin > end:
            raise ValueError('reversed completion edit')
        text = text[:begin] + replacement + text[end:]
    return text


def compiler_entry(project, source):
    cdb = project / 'compile_commands.json'
    entries = json.loads(cdb.read_text())
    matches = [entry for entry in entries if
               (Path(entry['directory']) / entry['file']).resolve() == source]
    if len(matches) != 1:
        raise ValueError('source requires exactly one actual CDB entry')
    entry = matches[0]
    arguments = entry.get('arguments') or shlex.split(entry['command'])
    return entry['directory'], arguments, hashlib.sha256(cdb.read_bytes()).hexdigest()


def compile_insertion(project, source, text, timeout=45):
    directory, arguments, cdb_digest = compiler_entry(project, source)
    with tempfile.NamedTemporaryFile(mode='w', suffix=source.suffix,
                                     prefix='.mcppls-insertion-', dir=source.parent,
                                     delete=False) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    try:
        command, skip, replaced = [], False, 0
        for argument in arguments:
            if skip:
                skip = False
                continue
            if argument == '-o':
                skip = True
            elif argument == '-c':
                continue
            elif (Path(directory) / argument).resolve() == source:
                command.append(str(temporary))
                replaced += 1
            else:
                command.append(argument)
        if replaced != 1:
            raise ValueError('CDB must name the actual source exactly once')
        command.append('-fsyntax-only')
        import time
        began = time.monotonic()
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True,
                                    text=True, timeout=timeout)
            return {'exit_code': result.returncode, 'stdout': result.stdout,
                    'stderr': result.stderr, 'elapsed_ms': (time.monotonic() - began) * 1000,
                    'command': command, 'directory': directory, 'cdb_sha256': cdb_digest,
                    'applied_tu_sha256': hashlib.sha256(text.encode()).hexdigest()}
        except subprocess.TimeoutExpired as error:
            return {'exit_code': None, 'error': str(error), 'command': command,
                    'directory': directory, 'cdb_sha256': cdb_digest,
                    'applied_tu_sha256': hashlib.sha256(text.encode()).hexdigest()}
    finally:
        temporary.unlink()
