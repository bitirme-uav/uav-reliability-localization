#!/bin/bash
cd "$(dirname "$0")"
until grep -q REPLAY_BITTI ../outputs/replay_v2.log; do sleep 30; done
systemd-run --user --scope -q -p MemoryMax=5G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files alto_fixes_test.jsonl,vpair_fixes_test.jsonl,fixes_test.jsonl,anyvisloc_fixes_test.jsonl,anyvisloc_fixes_recal.jsonl >> ../outputs/replay_v2b.log 2>&1
echo REPLAY_B_BITTI >> ../outputs/replay_v2b.log
