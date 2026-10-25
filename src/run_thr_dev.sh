#!/bin/bash
cd "$(dirname "$0")"
D=../outputs/thr_dev
for w in w1 w2; do ( while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < $D/$w.txt; echo $w >> $D/workers.txt ) & done
wait; echo THR_DEV_BITTI > $D/done.txt
