#!/bin/bash
# Bellek yetmedigi icin: sahne basina ayri surec, sirayla. Sonra wayback 09 tamamla + karsilastirmalar.
cd "$(dirname "$0")"
LOG=../outputs/anyvisloc_chain.log
for s in 19 22 24; do
  echo "test $s basladi $(date +%T)" >> $LOG
  ../venv/bin/python -u anyvisloc_build_fix_dataset.py --group test --scene $s --per-scene 40 >> $LOG 2>&1
done
for s in 05 06 08 10 14 15 16 17 20 21 23; do
  echo "recal $s basladi $(date +%T)" >> $LOG
  ../venv/bin/python -u anyvisloc_build_fix_dataset.py --group recal --scene $s --per-scene 40 >> $LOG 2>&1
done
echo ANYVISLOC_BUILD_BITTI >> $LOG
# wayback indirmesi (run_wayback.sh) bitene kadar bekle, sonra 09'un eksik tarihi
while [ -n "$(ps -eo cmd | grep '^/bin/bash ./run_wayback.sh')" ]; do sleep 30; done
../venv/bin/python -u wayback_fetch.py 09 >> ../outputs/wayback_fetch.log 2>&1
for f in 09 06; do ../venv/bin/python wayback_compare.py $f 30 > ../outputs/wayback_compare_$f.txt 2>&1; done
echo HEPSI_BITTI >> $LOG
