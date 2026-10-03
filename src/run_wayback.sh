#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
for f in "$@"; do ../venv/bin/python -u wayback_fetch.py $f; done > ../outputs/wayback_fetch.log 2>&1
echo WAYBACK_BITTI >> ../outputs/wayback_fetch.log
