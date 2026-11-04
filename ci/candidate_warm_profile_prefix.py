"""Profile warm launches only; let the cold launch build its ordinary cache."""
import os
from pathlib import Path
import sys

counter = Path(os.environ.pop('MCPPLS_DIAGNOSTIC_COUNTER'))
profiles = os.environ.pop('MCPPLS_DIAGNOSTIC_PROFILES')
launch = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(launch + 1))
os.environ.pop('OKRUN_PROF', None)
if launch:
    os.environ['OKRUN_PROF'] = 'phases,counters,calls,samples=200:' + profiles
os.execv(sys.argv[1], sys.argv[1:])
