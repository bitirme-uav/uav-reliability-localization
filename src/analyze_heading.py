"""Kareler haritaya gore SABIT bir acida mi (dunya-hizali), yoksa ucus
yonune gore mi donuk (govde-hizali)? Her ucus yonu icin basari ve
tahmin edilen donme acisini olcer. Sadece TRAIN sekanslari."""
import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m
from splits import TRAIN_SEQUENCES

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 160
W = 4

val = AerialVLVal(VAL_ROOT)
items = []
for name in TRAIN_SEQUENCES:
    fr = val.sequences[name]
    for i in range(W, len(fr) - W):
        if val.map_for(fr[i].lon, fr[i].lat) is not None:
            items.append((fr, i))
sample = random.Random(13).sample(items, N)

pipe = LocalizationPipeline()
rng = np.random.default_rng(13)
rows = []
for fr, i in sample:
    q, a, b = fr[i], fr[i - W], fr[i + W]
    ve, vn = lonlat_to_enu_m(b.lon, b.lat, a.lon, a.lat)
    if np.hypot(ve, vn) < 4:  # neredeyse duran -> yon belirsiz
        continue
    heading = (np.degrees(np.arctan2(ve, vn)) + 360) % 360  # 0=kuzey, 90=dogu
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(30 * np.cos(th), 30 * np.sin(th), q.lon, q.lat)
    r = pipe.localize(cv2.imread(str(q.path)), MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, 60.0)
    e = fix_error_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    ok = e is not None and e < 40 and r.inlier_count >= 50
    rows.append((heading, ok, r.rotation_deg if ok else np.nan, r.inlier_count))

a = np.array(rows, dtype=float)
print(f"n={len(a)}  basari={a[:,1].mean()*100:.0f}%")
print(f"{'ucus yonu':>12s} {'n':>4s} {'basari':>7s} {'ort_inlier':>10s} {'donme_ort':>10s} {'donme_std':>10s}")
for lo in range(0, 360, 45):
    m = (a[:, 0] >= lo) & (a[:, 0] < lo + 45)
    if m.sum() == 0:
        continue
    rot = a[m & (a[:, 1] == 1), 2]
    print(f"{lo:5d}-{lo+45:3d} deg {m.sum():4d} {a[m,1].mean()*100:6.0f}% {a[m,3].mean():10.0f} "
          f"{np.nanmean(rot) if len(rot) else float('nan'):10.1f} {np.nanstd(rot) if len(rot) else float('nan'):10.1f}")
