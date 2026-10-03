#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
until grep -q VISLOC_MAPS_BITTI ../outputs/visloc_maps.log; do sleep 30; done
../venv/bin/python visloc_eval_calibration.py visloc k2 > ../outputs/visloc_k2_eval.txt 2>&1
../venv/bin/python -u mixed_training.py > ../outputs/mixed_training.txt 2>&1
echo KARISIK_BITTI >> ../outputs/mixed_training.txt
