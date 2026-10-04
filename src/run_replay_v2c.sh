#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
L=../outputs/replay_v2b.log
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files alto_fixes_test.jsonl,vpair_fixes_test.jsonl,fixes_test.jsonl,anyvisloc_fixes_test.jsonl,anyvisloc_fixes_recal.jsonl >> $L 2>&1
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher superpoint --files anyvisloc_fixes_recal.jsonl >> $L 2>&1
echo REPLAY_B_BITTI >> $L
