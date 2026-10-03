"""SuperPoint+LightGlue vs RoMa -- SADECE gelistirme verisi (UAV-VisLoc TUNE+RECAL ucuslari,
veri seti haritasi). Prior 30 m hatali, arama 60 m, egiklik duzeltmesi dahil. TEST'e dokunmaz.
Kullanim: python roma_dev.py KARE_SAYISI_UCUS_BASINA [superpoint,roma]"""
import random
import sys
import time

import numpy as np

from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from visloc_attitude import correct_fix_enu, load_coef
from visloc_build_fix_dataset import VISLOC_PIPE
from visloc_loader import UAVVisLoc
from visloc_splits import RECAL_FLIGHTS, TUNE_FLIGHTS

PER = int(sys.argv[1]) if len(sys.argv) > 1 else 15
METHODS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["superpoint", "roma"]
FL = [f for f in list(TUNE_FLIGHTS) + list(RECAL_FLIGHTS) if f != "10"]
v = UAVVisLoc(FL)
coef = load_coef()
samp = []
for fl in FL:
    fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
    samp += random.Random(500 + int(fl)).sample(fr, min(PER, len(fr)))
rng = np.random.default_rng(5)
offs = [(30 * np.cos(t), 30 * np.sin(t)) for t in rng.uniform(0, 2 * np.pi, len(samp))]
res = {}
for meth in METHODS:
    if meth == "roma":
        from roma_pipeline import RomaPipeline
        pipe = RomaPipeline(**VISLOC_PIPE)
    else:
        pipe = LocalizationPipeline(**VISLOC_PIPE)
    errs, inl, t0 = [], [], time.monotonic()
    for q, (de, dn) in zip(samp, offs):
        plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
        r = pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
        if r.predicted_lon is None:
            errs.append(1e6); inl.append(0); continue
        e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        e, n = correct_fix_enu(e, n, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, coef)
        errs.append(float(np.hypot(e, n))); inl.append(r.inlier_count)
    res[meth] = (np.array(errs), np.array(inl), (time.monotonic() - t0) / len(samp))
    del pipe
    import torch; torch.cuda.empty_cache()
for meth, (e, n, dt) in res.items():
    print(f"{meth:10s} n={len(e)} median={np.median(e):6.1f}m <=10m={np.mean(e<=10)*100:3.0f}% <=25m={np.mean(e<=25)*100:3.0f}% "
          f">100m/yok={np.mean(e>100)*100:3.0f}%  median_inlier={np.median(n):5.0f}  {dt:.1f} s/kare", flush=True)
    for fl in FL:
        m = np.array([q.sequence == fl for q in samp])
        print(f"   ucus {fl}: <=10m={np.mean(e[m]<=10)*100:3.0f}% <=25m={np.mean(e[m]<=25)*100:3.0f}% >100m={np.mean(e[m]>100)*100:3.0f}%")
