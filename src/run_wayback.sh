#!/bin/bash
cd "$(dirname "$0")"
for f in "$@"; do ../venv/bin/python -u wayback_fetch.py $f; done > ../outputs/wayback_fetch.log 2>&1
echo WAYBACK_BITTI >> ../outputs/wayback_fetch.log
