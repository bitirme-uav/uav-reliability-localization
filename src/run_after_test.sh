#!/bin/bash
# Bellek yetmedigi icin isler SIRAYLA: test uretimi bitsin -> recal uretimi -> wayback 09 tamamla
cd /media/davut/disk2/proje/uav_reliability_localization/src
while pgrep -f "anyvisloc_build_fix_dataset.py --group test" >/dev/null; do sleep 30; done
../venv/bin/python -u anyvisloc_build_fix_dataset.py --group recal --per-scene 40 > ../outputs/anyvisloc_build_recal.log 2>&1
echo ANYVISLOC_BUILD_BITTI >> ../outputs/anyvisloc_build_recal.log
while pgrep -f "run_wayback.sh 09 06" >/dev/null; do sleep 30; done
../venv/bin/python -u wayback_fetch.py 09 >> ../outputs/wayback_fetch.log 2>&1
for f in 09 06; do ../venv/bin/python wayback_compare.py $f 30 > ../outputs/wayback_compare_$f.txt 2>&1; done
echo HEPSI_BITTI >> ../outputs/wayback_fetch.log
