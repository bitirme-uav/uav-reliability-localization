#!/bin/bash
cd "$(dirname "$0")"
../venv/bin/python -u anyvisloc_build_fix_dataset.py --group recal --per-scene 40 > ../outputs/anyvisloc_build_recal.log 2>&1 &
../venv/bin/python -u anyvisloc_build_fix_dataset.py --group test --per-scene 40 > ../outputs/anyvisloc_build_test.log 2>&1 &
wait
echo ANYVISLOC_BUILD_BITTI >> ../outputs/anyvisloc_build_recal.log
