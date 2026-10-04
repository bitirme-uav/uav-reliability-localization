#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
D=../outputs/sweep_v2s1
# replay zinciri A
( systemd-run --user --scope -q -p MemoryMax=4G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files alto_fixes_test.jsonl,vpair_fixes_test.jsonl,fixes_test.jsonl >> ../outputs/replay_A.log 2>&1
  systemd-run --user --scope -q -p MemoryMax=4G ../venv/bin/python -u replay_fixes.py --matcher superpoint --files anyvisloc_fixes_recal.jsonl >> ../outputs/replay_A.log 2>&1
  echo A_BITTI >> ../outputs/replay_A.log ) &
# replay zinciri B
( systemd-run --user --scope -q -p MemoryMax=4G ../venv/bin/python -u replay_fixes.py --matcher xfeat --files anyvisloc_fixes_test.jsonl,anyvisloc_fixes_recal.jsonl >> ../outputs/replay_B.log 2>&1
  echo B_BITTI >> ../outputs/replay_B.log ) &
# tarama isci 1: calisan kosuyu bekle, sonra kendi listesi
( while kill -0 454945 2>/dev/null; do sleep 20; done
  while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < $D/cmds_w1.txt; echo W1 >> $D/workers.txt ) &
# tarama isci 2
( while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < $D/cmds_w2.txt; echo W2 >> $D/workers.txt ) &
wait
