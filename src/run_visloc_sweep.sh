#!/bin/bash
cd "$(dirname "$0")"
xargs -P 3 -I{} sh -c '{}' < ../outputs/sweep_visloc/cmds_nav.txt
echo VISLOC_SWEEP_BITTI > ../outputs/sweep_visloc/done.txt
