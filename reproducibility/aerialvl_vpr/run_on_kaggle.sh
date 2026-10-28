#!/bin/bash
# AerialVL Table III on Kaggle (2x T4), as run on 2026-10-27/28.
# 1) data: images/VPR/VPR.zip.001..036 (76.5 GB) from huggingface.co/datasets/hmf21/AerialVL
#    -> /tmp/aerialvl (not extracted; avl_vpr.py reads the split zip directly)
# 2) code: gmberton/deep-visual-geo-localization-benchmark @ 4af5194, plus avl_vpr.py
# 3) weights: the benchmark README's MSLS-trained models (Google Drive ids below)
set -e
mkdir -p /tmp/aerialvl && cd /tmp/aerialvl
python -c "
with open('urls.txt','w') as f:
  for i in range(1,37): f.write(f'https://huggingface.co/datasets/hmf21/AerialVL/resolve/main/images/VPR/VPR.zip.{i:03d}\n  out=VPR.zip.{i:03d}\n')"
aria2c -i urls.txt -j 6 -x 8 -s 8 --file-allocation=none --max-tries=10 --retry-wait=10

cd /kaggle/working
git clone -q https://github.com/gmberton/deep-visual-geo-localization-benchmark.git dvgl
(cd dvgl && git checkout -q 4af5194)
cp avl_vpr.py dvgl/
pip install -q gdown faiss-cpu pyproj torchscan
# the benchmark imports google_drive_downloader (old name); only needed for off-the-shelf nets
mkdir -p pylib/google_drive_downloader && echo "class GoogleDriveDownloader: pass" > pylib/google_drive_downloader/__init__.py
mkdir -p w && cd w
for p in vgg16_gem:1GqgO-qG-WNJXWty43KgvDtW0OpG0Wrq- resnet50_gem:1uuIYJN4N7lQqqsN32pbZwjhz5Xvv3zr- \
         resnet101_gem:1Iondvd8P3vb3piHFTA-RUgTFpqh0I31M vgg16_netvlad:1dwai3uNudjvns58JIyaf5CBRg4ojcWIW \
         resnet50_netvlad:1krf0A6CeW8GqLqHWZ7dlSNJ9aTJ4dotF resnet101_netvlad:1rtPfsgfJ2Zoxs5uu7Ph1_qc7q-hIxJek; do
  gdown -q ${p#*:} -O ${p%%:*}.pth
done

cd /kaggle/working/dvgl
export PYTHONPATH=/kaggle/working/pylib DATASETS_FOLDER=/kaggle/working TORCH_HOME=/kaggle/working/torch
run () {  # gpu backbone aggregation weights
  CUDA_VISIBLE_DEVICES=$1 python -u avl_vpr.py --backbone $2 --aggregation $3 \
    --resume /kaggle/working/w/$4.pth --infer_batch_size 32 > /kaggle/working/avl_vpr_$4.log 2>&1
}
( run 0 resnet50conv4 gem resnet50_gem; run 0 resnet101conv4 gem resnet101_gem
  run 0 vgg16 gem vgg16_gem; run 0 resnet50conv4 netvlad resnet50_netvlad ) &
( run 1 vgg16 netvlad vgg16_netvlad; run 1 resnet101conv4 netvlad resnet101_netvlad ) &
wait
