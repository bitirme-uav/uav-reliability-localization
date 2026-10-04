#!/bin/bash
cd /media/davut/disk2/proje/uav_reliability_localization/src
D=../outputs/sweep_t
for w in w1 w2; do ( while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < $D/$w.txt; echo $w >> $D/workers.txt ) & done
wait; echo SWEEP_T_BITTI > $D/done.txt
