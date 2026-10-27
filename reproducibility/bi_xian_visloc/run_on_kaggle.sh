#!/bin/bash
# Reproduction of Bi et al. (ISPRS J. 2026), XIAN-Visloc test results, as run on Kaggle (2x T4, 31 GB RAM).
# Upstream code: https://github.com/VERYBC/UCVL @ 020c3e658bd5820ce866065910f4da0b49d4d972
# No training: released checkpoints BEMN-Tiny.pth / BEMN-Base.pth are evaluated as-is.
set -e
cd /kaggle/working
git clone https://github.com/VERYBC/UCVL.git
cd UCVL
pip install -q gdown
gdown --folder "https://drive.google.com/drive/folders/1E2IXkT4bqmuNL_bT2Fo20K0c39E1pOCI" -O checkpoints

# 1) Data: download the full zip (26 GB, ~2 min with aria2c) and extract only the test flights + maps.
cd /tmp
aria2c -x 16 -s 16 -k 64M --file-allocation=none -o XIAN_Visloc.zip \
  "https://huggingface.co/datasets/VERYBC/XIAN_Visloc/resolve/main/XIAN_Visloc.zip"
unzip -q XIAN_Visloc.zip 'XIAN_Visloc/Xian/satellite/*' 'XIAN_Visloc/Xian/drone/16/*' \
  'XIAN_Visloc/Xian/drone/17/*' 'XIAN_Visloc/Xian/drone/18/*' 'XIAN_Visloc/Xian/drone/19/*' \
  'XIAN_Visloc/Weinan/*' -d /tmp/xian

# 2) Build the AMS test tile libraries and 392x392 queries with the authors' scripts (only paths changed).
cd /kaggle/working/UCVL
X=/tmp/xian/XIAN_Visloc/Xian
W=/tmp/xian/XIAN_Visloc/Weinan
sed "s#data_root = \"G:/Data set/Github/Xian_visloc/Xian_Visloc/Xian\"#data_root = \"$X\"#" \
  scripts/XIAN_Visloc_same_AMS_test.py > build_xian_same_test.py
sed -e "s#root_dir = '../data/Real-world filght data'#root_dir = '$X/drone'#" \
  -e "s#DATA_LIST = \[3\]#DATA_LIST = [16, 17, 18, 19]#" "scripts/UAV image rescaling.py" > rescale_xian.py
# The upstream cross-area script has target_size = (3,3); the README says 392x392, which is used here.
sed -e "s#data_root = \"G:/Data set/Github/Xian_visloc/Xian_Visloc/Weinan\"#data_root = \"$W\"#" \
  -e "s#target_size = (3,3)#target_size = (392,392)#" scripts/XIAN_Visloc_cross_AMS_test.py > build_xian_cross_test.py
sed -e "s#root_dir = '../data/Real-world filght data'#root_dir = '$W/drone'#" \
  -e "s#DATA_LIST = \[3\]#DATA_LIST = [1, 2]#" "scripts/UAV image rescaling.py" > rescale_weinan.py
python rescale_xian.py && python build_xian_same_test.py
python rescale_weinan.py && python build_xian_cross_test.py

# 3) The dataset class selects coordinate columns only if 'Xian_visloc' is in the path, so use symlinks.
mkdir -p /tmp/data /tmp/data3
ln -sfn $X /tmp/data/Xian_visloc     # same-area: flights 16-19
ln -sfn $W /tmp/data3/Xian_visloc    # cross-area: Weinan flights 01-02

# 4) eval_xian_same.py = eval_real_world.py with: dataset_name='drone', data_folder=/tmp/data/Xian_visloc,
#    TEST_LIST=[16,17,18,19] (cross: data_folder=/tmp/data3/Xian_visloc, TEST_LIST=[1,2]), and the model
#    and retrieval switches read from UCVL_MODEL / UCVL_SCGA / UCVL_CM.
#    Runs share ./tmp_data, so they must run one after another (clear tmp_data in between).
#    Center-region matching (UCVL_CM=1) runs out of 31 GB RAM for BEMN-Base and for the Weinan gallery.
for cfg in "BEMN-Tiny 0 0" "BEMN-Tiny 1 0" "BEMN-Tiny 1 1" "BEMN-Base 0 0" "BEMN-Base 1 0"; do
  set -- $cfg
  rm -f tmp_data/*.json tmp_data/*.pkl tmp_data/*.mat tmp_data/*.csv
  UCVL_MODEL=$1 UCVL_SCGA=$2 UCVL_CM=$3 python eval_xian_same.py 2>&1 | grep -a -v TIFF_Warning
done
