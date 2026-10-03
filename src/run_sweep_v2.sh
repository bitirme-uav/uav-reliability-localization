#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < ../outputs/sweep_v2/cmds.txt
echo SWEEP_V2_BITTI > ../outputs/sweep_v2/done.txt
