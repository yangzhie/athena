#!/usr/bin/env python3
"""Back up or restore a STOPPED Athena data volume, including immutable material."""
import argparse
import shutil
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['backup', 'restore'])
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
if args.destination.exists():
    parser.error('Destination must not exist (never overwrite active data)')
if not args.source.is_dir():
    parser.error('Source must be a data directory')
shutil.copytree(args.source, args.destination, ignore=shutil.ignore_patterns('*-wal', '*-shm'))
for source in args.source.rglob('*.db'):
    target = args.destination / source.relative_to(args.source)
    with sqlite3.connect(source) as original, sqlite3.connect(target) as copied:
        original.backup(copied)
        if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
print(f'{args.action} complete; destination integrity verified')
