#!/usr/bin/env bash
# Refresh indexes and install together: apt update can succeed with missing
# indexes, so a successful install is also required before proceeding.
set -euo pipefail
(( $# > 0 )) || { echo "apt-install: expected package names" >&2; exit 2; }
options=(-o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30
         -o Acquire::Retries=3 -o DPkg::Lock::Timeout=60)
for attempt in 1 2 3; do
  if apt-get "${options[@]}" update && apt-get "${options[@]}" install -y "$@"; then
    exit 0
  fi
  echo "apt-install: update/install attempt $attempt failed" >&2
done
echo "apt-install: dependencies unavailable after three attempts" >&2
exit 1
