#!/bin/bash
# Real-world flight test of the released UCVL checkpoints (Bi et al. 2026, Table 13), as run on Kaggle (2x T4, 31 GB RAM).
# Upstream code: https://github.com/VERYBC/UCVL @ 020c3e6. No training.
R=/kaggle/working/results; mkdir -p $R
pip install -q aria2 gdown
cd /tmp
aria2c -x 16 -s 16 -k 64M --file-allocation=none -o rw.zip \
  "https://huggingface.co/datasets/VERYBC/XIAN_Visloc/resolve/main/Real-world%20flight%20data.zip"
mkdir -p /tmp/rw && cd /tmp/rw && unzip -q -o ../rw.zip
cd /kaggle/working
git clone -q https://github.com/VERYBC/UCVL.git && cd UCVL
gdown --folder "https://drive.google.com/drive/folders/1E2IXkT4bqmuNL_bT2Fo20K0c39E1pOCI" -O checkpoints
# The authors' scripts expect ./data/Real-world filght data; the dataset class also needs 'Xian_visloc' in the path.
mkdir -p data/Xian_visloc
ln -sfn /tmp/rw "data/Real-world filght data"
ln -sfn /tmp/rw "data/Xian_visloc/Real-world filght data"
sed -i 's/DATA_LIST = \[3\]/DATA_LIST = [1, 2, 3]/' "scripts/UAV image rescaling.py"
# Memory: store center-region features as fp16 on CPU (fp32 does not fit in 31 GB with ~6500-tile galleries).
sed -i 's/center_features_list.append(center_feature.to(torch.float32).cpu())/center_features_list.append(center_feature.to(torch.float16).cpu())/' sample4geo/trainer.py
sed -i 's/            c_qf = center_features_query\[i\] $/            c_qf = center_features_query[i].float()/; s/                topk_c_gf = c_gf\[topk_index, :\] $/                topk_c_gf = c_gf[topk_index, :].float()/' sample4geo/evaluate/visloc.py
sed -i 's#    data_folder: str = "./data"\r\?$#    data_folder: str = "./data/Xian_visloc"#' eval_real_world.py
cd scripts && python "UAV image rescaling.py" && python Real_world_flight_test.py && cd ..
# BEMN-Tiny, full method (SC+GA+CM). BEMN-Base with CM crashed the notebook (out of RAM).
python -u eval_real_world.py 2>&1 | tee $R/rw_tiny_full.log
python "Coarse localization_result.py" | tee $R/rw_tiny_full_coarse.log
