#!/usr/bin/env python3
"""Collect a matching linked PDB/executable pair; optionally prove CDB lookup."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid


def run(command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, text=True, timeout=120)


def identity(executable, pdb, readobj, pdbutil):
    pe = run([str(readobj), '--coff-debug-directory', str(executable)])
    info = run([str(pdbutil), 'dump', '-summary', str(pdb)])
    def field(text, name):
        match = re.search(r'^\s*' + name + r':\s*(.+?)\s*$', text, re.M)
        if not match:
            raise ValueError(f'missing {name}')
        return match.group(1).strip()
    def guid_value(value):
        # Older llvm-readobj prints CodeView GUID bytes in their PE layout.
        # Its first three fields are little endian, unlike the final bytes.
        if re.fullmatch(r'\((?:[0-9a-fA-F]{2}\s+){15}[0-9a-fA-F]{2}\)', value):
            value = uuid.UUID(bytes_le=bytes.fromhex(value[1:-1]))
        else:
            value = uuid.UUID(value)
        return '{' + str(value).upper() + '}'
    guid = guid_value(field(pe, 'PDBGUID'))
    age = int(field(pe, 'PDBAge'))
    if guid != guid_value(field(info, 'GUID')) or age != int(field(info, 'Age')):
        raise ValueError('executable CodeView GUID/age does not match linked PDB')
    if field(info, 'Has Debug Info').lower() != 'true' or field(info, 'Has Publics').lower() != 'true':
        raise ValueError('PDB lacks debug or public symbol streams')
    return {'guid': guid, 'age': age, 'codeview': pe, 'pdb_summary': info}


def collect(args):
    result = identity(args.engine, args.pdb, args.readobj, args.pdbutil)
    # Refuse an empty/wrong PDB before producing any artifact. Compiler PDBs
    # are deliberately excluded: only the executable's linked PDB qualifies.
    args.output.mkdir(parents=True, exist_ok=True)
    for source in (args.engine, args.pdb):
        shutil.copy2(source, args.output / source.name)
    result['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (args.engine, args.pdb)}
    result['symbol_lookup'] = 'not-run'
    if args.cdb:
        symbols = run([str(args.cdb), '-y', str(args.pdb.resolve().parent),
                       '-c', '.reload /f clangd.exe; x clangd!*clangdMain*; q',
                       str(args.engine), '--version'])
        (args.output / 'cdb-symbols.log').write_text(symbols)
        if not re.search(r'^[0-9a-fA-F`]+\s+clangd!.*clangdMain', symbols, re.M):
            raise ValueError('CDB could not resolve clangdMain from the matching PDB')
        result['symbol_lookup'] = 'clangdMain'
    (args.output / 'symbols.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'pdb', 'readobj', 'pdbutil', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cdb', type=Path)
    collect(parser.parse_args())
