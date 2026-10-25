#!/bin/bash
# TEST asamasi (SS9.1): config freeze SONRASI, bir kez. Hicbir ayar degismez.
set -e
cd "$(dirname "$0")"
PY=../venv/bin/python
OUT=../outputs
filt() { grep -v "Warning\|warn" || true; }
mkdir -p $OUT/sweep_test/fix $OUT/sweep_test/sum $OUT/sweep_test/log $OUT/sweep_test/reacq

$PY freeze_config.py verify

echo "=== $(date +%T) TEST acik-dongu fix verisi ==="
$PY build_fix_dataset.py --split test --n 150 --allow-test 2>&1 | filt | tail -n 1
echo "=== $(date +%T) TEST kalibrasyon (dondurulmus) ==="
$PY eval_calibration_frozen.py test 2>&1 | filt

echo "=== $(date +%T) TEST nav taramasi ==="
$PY sweep.py --split test --kind nav > $OUT/sweep_test/cmds_nav.txt
xargs -P 3 -I{} sh -c '{}' < $OUT/sweep_test/cmds_nav.txt
$PY aggregate_sweep.py --split test 2>&1 | filt

echo "=== $(date +%T) TEST reacquire ==="
$PY sweep.py --split test --kind reacq --seeds 0,1 > $OUT/sweep_test/cmds_reacq.txt
xargs -P 2 -I{} sh -c '{}' < $OUT/sweep_test/cmds_reacq.txt
cat $OUT/sweep_test/reacq/*.jsonl > $OUT/sweep_test/reacquire_all.jsonl

$PY freeze_config.py verify
echo "=== $(date +%T) TEST_PIPELINE_BITTI ==="
