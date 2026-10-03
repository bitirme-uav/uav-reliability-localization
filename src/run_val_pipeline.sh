#!/bin/bash
# VAL asamasi: kalibrasyon -> esikler -> M10 nav taramasi -> M9/E11 reacquire.
# TRAIN uretimi bittikten sonra calistirilir. TEST'e dokunmaz.
set -e
cd /media/davut/disk2/proje/uav_reliability_localization/src
PY=../venv/bin/python
OUT=../outputs
filt() { grep -v "Warning\|warn" || true; }

echo "=== $(date +%T) kalibrasyon ==="
$PY eval_calibration.py 2>&1 | filt
echo "=== $(date +%T) esikler ==="
$PY select_thresholds.py 2>&1 | filt

echo "=== $(date +%T) nav taramasi (32 kosu, 3 paralel) ==="
xargs -P 3 -I{} sh -c '{}' < $OUT/sweep_val/cmds_nav.txt
echo "=== $(date +%T) nav taramasi bitti: $(ls $OUT/sweep_val/sum | wc -l) ozet ==="
$PY aggregate_sweep.py --split val 2>&1 | filt

echo "=== $(date +%T) reacquire (8 kosu, 2 paralel) ==="
xargs -P 2 -I{} sh -c '{}' < $OUT/sweep_val/cmds_reacq.txt
cat $OUT/sweep_val/reacq/*.jsonl > $OUT/sweep_val/reacquire_all.jsonl
echo "=== $(date +%T) VAL_PIPELINE_BITTI ==="
