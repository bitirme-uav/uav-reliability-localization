"""UAV-VisLoc acik-dongu lokalizer degerlendirmesi (prior = GT + ofset).
Kullanim: python visloc_eval.py --flights 10 --n 24 [--fp 250,350,500,700 --margin 350 --gsd 0.8 ...]"""
import argparse
import random
import time

import numpy as np

from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m
from visloc_loader import UAVVisLoc

ap = argparse.ArgumentParser()
ap.add_argument("--flights", default="10")
ap.add_argument("--n", type=int, default=24)
ap.add_argument("--radius", type=float, default=60.0)
ap.add_argument("--offset", type=float, default=30.0)
ap.add_argument("--fp", default="250,350,500,700")
ap.add_argument("--margin", type=float, default=350.0)
ap.add_argument("--gsd", type=float, default=0.8)
ap.add_argument("--mapkp", type=int, default=4096)
ap.add_argument("--kp", type=int, default=2048)
ap.add_argument("--yaw-sign", type=float, default=-1.0)
ap.add_argument("--yaw-off", type=float, default=0.0)
ap.add_argument("--seed", type=int, default=3)
args = ap.parse_args()

flights = args.flights.split(",")
v = UAVVisLoc(flights)
items = [f for fl in flights for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
sample = random.Random(args.seed).sample(items, min(args.n, len(items)))
pipe = LocalizationPipeline(query_rotation=None, max_keypoints=args.kp,
                            footprint_candidates_m=[float(x) for x in args.fp.split(",")],
                            footprint_margin_m=args.margin, map_work_gsd_m=args.gsd,
                            map_max_keypoints=args.mapkp)
rng = np.random.default_rng(args.seed)
err, inl, sc, lat, de_all = [], [], [], [], []
for q in sample:
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(args.offset * np.cos(th), args.offset * np.sin(th), q.lon, q.lat)
    t = time.monotonic()
    r = pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, args.radius,
                      query_rot_ccw_deg=args.yaw_sign * q.yaw_deg + args.yaw_off)
    lat.append(time.monotonic() - t)
    e = fix_error_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    err.append(9999.0 if e is None else e)
    inl.append(r.inlier_count)
    sc.append(r.query_ref_scale_ratio)
    if e is not None and e < 60:
        de_all.append(lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat))
err = np.array(err)
print(f"ucuslar={args.flights} n={len(err)} fp={args.fp} margin={args.margin} gsd={args.gsd} yaw={args.yaw_sign:+.0f}*yaw{args.yaw_off:+.0f}")
print(f"  median={np.median(err):7.2f}m  <=10m={np.mean(err<=10)*100:4.0f}%  <=25m={np.mean(err<=25)*100:4.0f}%  "
      f">100m={np.mean(err>100)*100:4.0f}%  median_inlier={np.median(inl):5.0f}  sure={np.mean(lat):.2f}s")
if de_all:
    d = np.array(de_all)
    print(f"  basarili fix'lerde ort ofset: dogu={d[:,0].mean():.2f} kuzey={d[:,1].mean():.2f} m")
vals = [round(s, 3) for s in sc if s]
print(f"  secilen olcekler: {sorted(set(vals))[:8]}")
