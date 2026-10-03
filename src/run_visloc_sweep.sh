#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
xargs -P 3 -I{} sh -c '{}' < ../outputs/sweep_visloc/cmds_nav.txt
echo VISLOC_SWEEP_BITTI > ../outputs/sweep_visloc/done.txt
