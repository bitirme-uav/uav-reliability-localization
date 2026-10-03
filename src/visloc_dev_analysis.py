"""Gelistirme ucuslari (TUNE + RECAL) uzerinde ucus-basina analiz: prior=GT,
eslesme basarisi, govde-ekseni hata, Omega/Kappa, yer kapsami. TEST'e dokunmaz.
Cikti: outputs/visloc_dev_rows.npy"""
import random
import sys

import numpy as np

from geo_utils import lonlat_to_enu_m
from localization_pipeline import MapExtractor
from visloc_build_fix_dataset import make_pipeline
from visloc_loader import UAVVisLoc
from visloc_splits import RECAL_FLIGHTS, TUNE_FLIGHTS

PER = int(sys.argv[1]) if len(sys.argv) > 1 else 30
FL = sys.argv[2].split(",") if len(sys.argv) > 2 else list(TUNE_FLIGHTS) + list(RECAL_FLIGHTS)
v = UAVVisLoc(FL)
pipe = make_pipeline()
rows = []
for fl in FL:
    fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
    samp = random.Random(int(fl)).sample(fr, min(PER, len(fr)))
    ok = 0
    for q in samp:
        r = pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), q.lon, q.lat, 20,
                          query_rot_ccw_deg=-q.yaw_deg)
        if r.predicted_lon is None:
            rows.append([int(fl), 0, np.nan, np.nan, np.nan, np.nan, q.omega, q.kappa, q.yaw_deg, q.height])
            continue
        e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        h = np.radians(q.yaw_deg)
        rows.append([int(fl), r.inlier_count, e * np.sin(h) + n * np.cos(h), e * np.cos(h) - n * np.sin(h),
                     r.ground_footprint_m or np.nan, np.hypot(e, n), q.omega, q.kappa, q.yaw_deg, q.height])
        ok += r.inlier_count >= 40
    a = np.array([x for x in rows if x[0] == int(fl)], dtype=float)
    good = a[(a[:, 1] >= 40) & (a[:, 5] < 150)]
    print(f"ucus {fl}: n={len(a)} basarili(inlier>=40)={ok}  "
          + (f"ileri ort={good[:,2].mean():6.1f} sag ort={good[:,3].mean():6.1f} fp med={np.nanmedian(good[:,4]):4.0f} "
             f"omega ort={good[:,6].mean():5.2f} kappa ort={good[:,7].mean():5.2f} h={good[:,9].mean():5.0f}" if len(good) else ""),
          flush=True)
np.save(f"../outputs/visloc_dev_rows_{'_'.join(FL)}.npy", np.array(rows, dtype=float))
