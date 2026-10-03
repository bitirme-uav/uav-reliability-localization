"""UAV-VisLoc platform kalibrasyonu (SADECE kalibrasyon ucusu 10; degerlendirmede
kullanilmaz). AerialVL'deki 90° donme ve 15.7 m ofset gibi:
  1) yaw konvansiyonu: query'yi CCW (sign*yaw + offset) derece dondur; sign in
     {+1,-1}, offset in {0,90,180,270} -> en cok inlier veren
  2) secilen konvansiyonla ucus-yonu / yanal sistematik ofset
"""
import random
import sys

import numpy as np

from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m
from visloc_loader import UAVVisLoc

CALIB_FLIGHT = "10"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 24

v = UAVVisLoc([CALIB_FLIGHT])
fr = [f for f in v.sequences[CALIB_FLIGHT] if v.map_for(f.lon, f.lat) is not None]
idx = sorted(random.Random(3).sample(range(1, len(fr) - 1), min(N, len(fr) - 2)))
pipe = LocalizationPipeline(query_rotation=None)
rng = np.random.default_rng(3)
offs = [(30 * np.cos(t), 30 * np.sin(t)) for t in rng.uniform(0, 2 * np.pi, len(idx))]
imgs = {i: v.image(fr[i]) for i in idx}

best = None
for sign in (1, -1):
    for off in (0, 90, 180, 270):
        inl, err = [], []
        for i, (de, dn) in zip(idx, offs):
            q = fr[i]
            plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
            r = pipe.localize(imgs[i], MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, 60.0,
                              query_rot_ccw_deg=sign * q.yaw_deg + off)
            e = fix_error_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
            inl.append(r.inlier_count); err.append(9999 if e is None else e)
        print(f"sign={sign:+d} off={off:3d}: median inlier={np.median(inl):6.0f}  median hata={np.median(err):7.1f} m", flush=True)
        if best is None or np.median(inl) > best[0]:
            best = (np.median(inl), sign, off)
print(f"SECILEN: sign={best[1]:+d} off={best[2]}")

sign, off = best[1], best[2]
along, cross = [], []
for i, (de, dn) in zip(idx, offs):
    q, a, b = fr[i], fr[i - 1], fr[i + 1]
    plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
    r = pipe.localize(imgs[i], MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, 60.0,
                      query_rot_ccw_deg=sign * q.yaw_deg + off)
    if r.predicted_lon is None or r.inlier_count < 50:
        continue
    e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    ve, vn = lonlat_to_enu_m(b.lon, b.lat, a.lon, a.lat)
    sp = np.hypot(ve, vn)
    if sp < 1 or np.hypot(e, n) > 60:
        continue
    along.append((e * ve + n * vn) / sp); cross.append((-e * vn + n * ve) / sp)
print(f"guvenilir n={len(along)}  ucus-yonu ofset ort={np.mean(along):.2f} m (std {np.std(along):.2f}), "
      f"yanal ort={np.mean(cross):.2f} m (std {np.std(cross):.2f})")
