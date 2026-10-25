#!/bin/bash
cd "$(dirname "$0")"
( systemd-run --user --scope -q -p MemoryMax=4G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files anyvisloc_fixes_test.jsonl >> ../outputs/replay_B1.log 2>&1; echo B1_BITTI >> ../outputs/replay_B1.log ) &
( systemd-run --user --scope -q -p MemoryMax=4G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files anyvisloc_fixes_recal.jsonl >> ../outputs/replay_B2.log 2>&1; echo B2_BITTI >> ../outputs/replay_B2.log ) &
wait
