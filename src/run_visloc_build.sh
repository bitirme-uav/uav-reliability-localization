#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
../venv/bin/python visloc_build_fix_dataset.py --group recal --per-flight 50 > ../outputs/visloc_build_recal.log 2>&1 &
../venv/bin/python visloc_build_fix_dataset.py --group test --per-flight 50 > ../outputs/visloc_build_test.log 2>&1 &
wait
echo VISLOC_BUILD_BITTI >> ../outputs/visloc_build_recal.log
