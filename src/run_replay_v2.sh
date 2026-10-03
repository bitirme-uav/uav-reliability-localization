#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
L=../outputs/replay_v2.log
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files visloc_fixes_test.jsonl,alto_fixes_test.jsonl,vpair_fixes_test.jsonl,fixes_test.jsonl,anyvisloc_fixes_test.jsonl >> $L 2>&1
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher superpoint --files anyvisloc_fixes_test.jsonl >> $L 2>&1
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files fixes_train.jsonl,fixes_val.jsonl,visloc_fixes_recal.jsonl,anyvisloc_fixes_recal.jsonl >> $L 2>&1
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher superpoint --files anyvisloc_fixes_recal.jsonl >> $L 2>&1
echo REPLAY_BITTI >> $L
