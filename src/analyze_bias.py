"""Ucus-yonu sapmasinin kaynagi: zaman gecikmesi (hiza orantili) mi, sabit
kamera ofseti mi? along = a*hiz + b regresyonu. Sadece TRAIN sekanslari."""
import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from splits import TRAIN_SEQUENCES

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
W = 4  # yon/hiz icin +-W kare pencere (0.5s araliklar -> +-2s)

val = AerialVLVal(VAL_ROOT)
items = []
for name in TRAIN_SEQUENCES:
    fr = val.sequences[name]
    for i in range(W, len(fr) - W):
        if val.map_for(fr[i].lon, fr[i].lat) is not None:
            items.append((name, fr, i))
sample = random.Random(11).sample(items, N)

pipe = LocalizationPipeline()
rng = np.random.default_rng(11)
rows = []
for name, fr, i in sample:
    q = fr[i]
    a, b = fr[i - W], fr[i + W]
    ve, vn = lonlat_to_enu_m(b.lon, b.lat, a.lon, a.lat)
    dt = (b.utc_ts - a.utc_ts) / 1000.0
    speed = np.hypot(ve, vn) / dt
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(30 * np.cos(th), 30 * np.sin(th), q.lon, q.lat)
    r = pipe.localize(cv2.imread(str(q.path)), MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, 60.0)
    if r.predicted_lon is None or r.inlier_count < 50:
        continue
    de, dn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    if np.hypot(de, dn) > 60:
        continue
    if speed > 1.0:
        u = np.array([ve, vn]) / np.hypot(ve, vn)
        along, cross = de * u[0] + dn * u[1], -de * u[1] + dn * u[0]
    else:
        along = cross = np.nan
    rows.append((name, speed, along, cross, de, dn))

a = np.array([r[1:] for r in rows], dtype=float)
moving = a[~np.isnan(a[:, 1])]
print(f"guvenilir fix: {len(a)}  (hareketli: {len(moving)})")
k, c = np.polyfit(moving[:, 0], moving[:, 1], 1)
resid = moving[:, 1] - (k * moving[:, 0] + c)
print(f"along = {k:.3f} * hiz + {c:.2f}   (egim=zaman gecikmesi [s], sabit=kamera ofseti [m])")
print(f"  along ort={moving[:,1].mean():.2f}  std={moving[:,1].std():.2f}  regresyon sonrasi std={resid.std():.2f}")
print(f"  cross ort={moving[:,2].mean():.2f}  std={moving[:,2].std():.2f}")
for lo, hi in ((1, 4), (4, 7), (7, 9), (9, 15)):
    m = (moving[:, 0] >= lo) & (moving[:, 0] < hi)
    if m.sum():
        print(f"  hiz {lo:2d}-{hi:2d} m/s: n={m.sum():3d}  along_ort={moving[m,1].mean():7.2f}m")
hover = a[np.isnan(a[:, 1])]
if len(hover):
    print(f"  hover (<1 m/s): n={len(hover)}  dogu_ort={hover[:,3].mean():.2f} kuzey_ort={hover[:,4].mean():.2f}")
print("\nsekans bazinda along ortalamasi:")
for name in TRAIN_SEQUENCES:
    m = [r[2] for r in rows if r[0] == name and not np.isnan(r[2])]
    if m:
        print(f"  {name}: n={len(m):3d} along_ort={np.mean(m):7.2f}")
