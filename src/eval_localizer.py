"""Lokalizer dogrulugunu bir sekans grubunda olcer, boresight duzeltmesi
ONCESI ve SONRASI. Varsayilan: VAL sekanslari (ayarlamada kullanilmayan).

Ucus yonu icin +-W kare uzerinden hiz kullanilir -- calisma anindaki
navigasyon tahmininin hizina vekil (drift yavas oldugundan yon cok yakin).
"""
import argparse
import random

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from boresight import correct_fix_enu
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from splits import TRAIN_SEQUENCES, VAL_SEQUENCES

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
ap = argparse.ArgumentParser()
ap.add_argument("--split", default="val", choices=["train", "val"])
ap.add_argument("--n", type=int, default=120)
ap.add_argument("--radius", type=float, default=60.0)
ap.add_argument("--prior-offset", type=float, default=30.0)
args = ap.parse_args()
seqs = VAL_SEQUENCES if args.split == "val" else TRAIN_SEQUENCES
W = 4

val = AerialVLVal(VAL_ROOT)
items = []
for name in seqs:
    fr = val.sequences[name]
    for i in range(W, len(fr) - W):
        if val.map_for(fr[i].lon, fr[i].lat) is not None:
            items.append((fr, i))
sample = random.Random(21).sample(items, min(args.n, len(items)))

pipe = LocalizationPipeline()
rng = np.random.default_rng(21)
raw, cor = [], []
for fr, i in sample:
    q, a, b = fr[i], fr[i - W], fr[i + W]
    ve, vn = lonlat_to_enu_m(b.lon, b.lat, a.lon, a.lat)
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(args.prior_offset * np.cos(th), args.prior_offset * np.sin(th), q.lon, q.lat)
    r = pipe.localize(cv2.imread(str(q.path)), MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, args.radius)
    if r.predicted_lon is None:
        raw.append(9999.0); cor.append(9999.0)
        continue
    de, dn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    ce, cn = correct_fix_enu(de, dn, ve, vn)
    raw.append(float(np.hypot(de, dn)))
    cor.append(float(np.hypot(ce, cn)))

for label, e in (("ham", np.array(raw)), ("boresight-duzeltilmis", np.array(cor))):
    print(f"[{args.split}] {label:22s} n={len(e)} median={np.median(e):6.2f}m  <=10m={np.mean(e<=10)*100:4.0f}%  "
          f"<=25m={np.mean(e<=25)*100:4.0f}%  >100m={np.mean(e>100)*100:4.0f}%")
