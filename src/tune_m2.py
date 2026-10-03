"""M2 parametre taramasi: ayni sabit query ornegi uzerinde farkli
ayarlarin hatasini karsilastirir. Sadece TRAIN sekanslari kullanir
(TEST_SEQUENCES haric) -- test seti ayarlamada hic gorulmez (SS9.1)."""
import argparse
import random
import time
from collections import Counter

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m
from splits import TEST_SEQUENCES

VAL_ROOT = "/media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted"

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
ap.add_argument("--radius", type=float, default=60.0)
ap.add_argument("--prior-offset", type=float, default=30.0)
ap.add_argument("--model", default="similarity")
ap.add_argument("--ransac", type=float, default=4.0)
ap.add_argument("--footprints", default="40,80,160,320,640")
ap.add_argument("--min-crop", type=int, default=1)
ap.add_argument("--max-kp", type=int, default=2048)
args = ap.parse_args()

val = AerialVLVal(VAL_ROOT)
pairs = []
for name, frames in val.sequences.items():
    if name in TEST_SEQUENCES:
        continue
    for a, b in zip(frames[:-1], frames[1:]):
        if val.map_for(a.lon, a.lat) is not None:
            pairs.append((a, b))
sample = random.Random(7).sample(pairs, args.n)

MapExtractor.MIN_CROP_PX = args.min_crop
pipe = LocalizationPipeline(max_keypoints=args.max_kp, transform_model=args.model,
                            ransac_thresh_px=args.ransac,
                            footprint_candidates_m=[float(x) for x in args.footprints.split(",")])
rng = np.random.default_rng(7)
errs, along, inl, scales, lat = [], [], [], [], []
for q, nxt in sample:
    th = rng.uniform(0, 2 * np.pi)
    plon, plat = enu_to_lonlat_m(args.prior_offset * np.cos(th), args.prior_offset * np.sin(th), q.lon, q.lat)
    t = time.monotonic()
    r = pipe.localize(cv2.imread(str(q.path)), MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, args.radius)
    lat.append(time.monotonic() - t)
    e = fix_error_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
    errs.append(e if e is not None else 9999.0)
    inl.append(r.inlier_count)
    scales.append(None if r.query_ref_scale_ratio is None else round(r.query_ref_scale_ratio, 3))
    if r.predicted_lon is not None:
        de, dn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        ve, vn = lonlat_to_enu_m(nxt.lon, nxt.lat, q.lon, q.lat)
        sp = np.hypot(ve, vn)
        if sp > 1.0 and e is not None and e < 60:
            along.append((de * ve + dn * vn) / sp)

errs = np.array(errs)
print(f"model={args.model} r={args.radius} ransac={args.ransac} fp={args.footprints} min_crop={args.min_crop} kp={args.max_kp}")
print(f"  median={np.median(errs):6.2f}m  p75={np.percentile(errs,75):6.2f}m  <=10m={np.mean(errs<=10)*100:4.0f}%  "
      f"<=25m={np.mean(errs<=25)*100:4.0f}%  >100m={np.mean(errs>100)*100:4.0f}%  "
      f"ort_inlier={np.mean(inl):5.0f}  ucus_yonu_bias={np.mean(along) if along else float('nan'):6.2f}m  "
      f"sure={np.mean(lat):.2f}s")
print(f"  secilen olcekler: {Counter(scales).most_common(6)}")
