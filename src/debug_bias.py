"""Hata vektorlerinin yonunu ve ucusun ilerleme yonuyle iliskisini olcer --
kalan hata sistematik mi (sabit ofset / zaman gecikmesi) yoksa rastgele mi."""
import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
RADIUS = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

val = AerialVLVal(VAL_ROOT)
# her ornegin bir sonraki karesini de bil (ucus yonu icin)
pairs = []
for frames in val.sequences.values():
    for a, b in zip(frames[:-1], frames[1:]):
        if val.map_for(a.lon, a.lat) is not None:
            pairs.append((a, b))
sample = random.Random(1).sample(pairs, N)

pipe = LocalizationPipeline()
rng = np.random.default_rng(1)
rows = []
for q, nxt in sample:
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(30 * np.cos(th), 30 * np.sin(th), q.lon, q.lat)
    r = pipe.localize(cv2.imread(str(q.path)), MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, RADIUS)
    if r.predicted_lon is None:
        continue
    e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    ve, vn = lonlat_to_enu_m(nxt.lon, nxt.lat, q.lon, q.lat)
    dt = (nxt.utc_ts - q.utc_ts) / 1000.0
    v = np.array([ve, vn]) / max(dt, 1e-3)
    speed = np.linalg.norm(v)
    u = v / speed if speed > 0.1 else np.array([0.0, 0.0])
    along = e * u[0] + n * u[1]
    cross = -e * u[1] + n * u[0]
    rows.append((e, n, along, cross, speed, r.inlier_count))
    print(f"dogu={e:7.2f} kuzey={n:7.2f} |{np.hypot(e,n):6.2f}m| ucus_yonunde={along:7.2f} yanal={cross:7.2f} "
          f"hiz={speed:5.1f}m/s inlier={r.inlier_count}", flush=True)

a = np.array(rows)
print("\n--- ozet ---")
print(f"ortalama dogu={a[:,0].mean():.2f} kuzey={a[:,1].mean():.2f}  (sabit ofset varsa 0'dan uzak olur)")
print(f"ortalama ucus_yonunde={a[:,2].mean():.2f} yanal={a[:,3].mean():.2f}  (zaman gecikmesi varsa ucus_yonunde sistematik olur)")
print(f"median |hata|={np.median(np.hypot(a[:,0],a[:,1])):.2f}m  ortalama hiz={a[:,4].mean():.1f}m/s")
if a[:, 4].std() > 0.5:
    k = np.polyfit(a[:, 4], a[:, 2], 1)
    print(f"ucus_yonu hatasi ~ {k[0]:.3f}*hiz + {k[1]:.2f}  (egim = tahmini zaman gecikmesi, saniye)")
