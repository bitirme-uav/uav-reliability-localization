#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
OUT=../outputs
echo "=== $(date +%T) reacquire (8 kosu, 2 paralel) ==="
xargs -P 2 -I{} sh -c '{}' < $OUT/sweep_val/cmds_reacq.txt
cat $OUT/sweep_val/reacq/*.jsonl > $OUT/sweep_val/reacquire_all.jsonl
echo "=== $(date +%T) VAL_REACQ_BITTI ==="
