#!/bin/bash
# UAV-VisLoc yeni harita kurallari. Bellek nedeniyle TEK surec, sirayla.
cd "$(dirname "$0")"
LOG=../outputs/visloc_maps.log
while kill -0 76037 2>/dev/null; do sleep 20; done      # calisan test k1
echo "test k1 bitti $(date +%T)" >> $LOG
for job in "recal k1" "test k2" "recal k2"; do
  set -- $job
  echo "$1 $2 basladi $(date +%T)" >> $LOG
  ../venv/bin/python -u visloc_build_fix_dataset.py --group $1 --per-flight 50 --maps $2 > ../outputs/visloc_build_$1_$2.log 2>&1
done
echo VISLOC_MAPS_BITTI >> $LOG
