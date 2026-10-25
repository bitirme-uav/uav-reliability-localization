#!/bin/bash
cd "$(dirname "$0")"
while read -r c; do systemd-run --user --scope -q -p MemoryMax=4G sh -c "$c"; done < ../outputs/sweep_v2s1/cmds.txt
echo SWEEP_V2_BITTI > ../outputs/sweep_v2s1/done.txt
