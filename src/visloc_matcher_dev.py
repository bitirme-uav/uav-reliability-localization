"""SuperPoint vs ALIKED -- SADECE gelistirme ucuslari (TUNE+RECAL), prior 30 m hatali,
egiklik duzeltmesi dahil. TEST ucuslarina dokunmaz."""
import random
import sys

import numpy as np

from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from visloc_attitude import correct_fix_enu, load_coef
from visloc_build_fix_dataset import VISLOC_PIPE
from visloc_loader import UAVVisLoc
from visloc_splits import RECAL_FLIGHTS, TUNE_FLIGHTS

PER = int(sys.argv[1]) if len(sys.argv) > 1 else 25
FL = [f for f in list(TUNE_FLIGHTS) + list(RECAL_FLIGHTS) if f != "10"]
v = UAVVisLoc(FL)
coef = load_coef()
samp = []
for fl in FL:
    fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
    samp += random.Random(100 + int(fl)).sample(fr, min(PER, len(fr)))
rng = np.random.default_rng(1)
offs = [(30 * np.cos(t), 30 * np.sin(t)) for t in rng.uniform(0, 2 * np.pi, len(samp))]
imgs = None
res = {}
for feat in ("superpoint", "aliked"):
    pipe = LocalizationPipeline(**VISLOC_PIPE, features=feat)
    errs, inl = [], []
    for q, (de, dn) in zip(samp, offs):
        plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
        r = pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
        if r.predicted_lon is None:
            errs.append(1e6); inl.append(0); continue
        e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        e, n = correct_fix_enu(e, n, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, coef)
        errs.append(np.hypot(e, n)); inl.append(r.inlier_count)
    res[feat] = (np.array(errs), np.array(inl))
    del pipe
for feat, (e, n) in res.items():
    print(f"{feat:10s} n={len(e)} median={np.median(e):6.1f}m <=10m={np.mean(e<=10)*100:3.0f}% <=25m={np.mean(e<=25)*100:3.0f}% "
          f">100m/yok={np.mean(e>100)*100:3.0f}% median_inlier={np.median(n):4.0f}")
    for fl in FL:
        m = np.array([q.sequence == fl for q in samp])
        print(f"   ucus {fl}: <=10m={np.mean(e[m]<=10)*100:3.0f}% <=25m={np.mean(e[m]<=25)*100:3.0f}%")
