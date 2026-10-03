"""Birden fazla query uzerinde run_month1_demo mantigini tekrarlayip
istatistik cikartir -- tek ornekle yanlis sonuca varmamak icin."""
from __future__ import annotations

import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from fix_record import FixRecord, label_fix
from geo_utils import enu_to_lonlat_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m

VAL_ROOT = sys.argv[1] if len(sys.argv) > 1 else "/media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 15
PRIOR_OFFSET_M = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
SEARCH_RADIUS_M = float(sys.argv[4]) if len(sys.argv) > 4 else 150.0

val = AerialVLVal(VAL_ROOT)
candidates = [f for f in val.all_frames() if val.map_for(f.lon, f.lat) is not None]
rng = random.Random(1)
sample = rng.sample(candidates, N)

pipeline = LocalizationPipeline()
np_rng = np.random.default_rng(1)

results = []
for i, query in enumerate(sample):
    geo_map = val.map_for(query.lon, query.lat)
    theta = np_rng.uniform(0, 2 * np.pi)
    d_east = PRIOR_OFFSET_M * np.cos(theta)
    d_north = PRIOR_OFFSET_M * np.sin(theta)
    prior_lon, prior_lat = enu_to_lonlat_m(d_east, d_north, query.lon, query.lat)

    query_img = cv2.imread(str(query.path))
    if query_img is None:
        print(f"[{i}] okunamadi: {query.path}")
        continue

    map_extractor = MapExtractor(geo_map)
    result = pipeline.localize(query_img, map_extractor, prior_lon, prior_lat, SEARCH_RADIUS_M)
    err = fix_error_m(result.predicted_lon, result.predicted_lat, query.lon, query.lat)

    rec = FixRecord(fix_error_m=err, num_matches=result.num_matches,
                     inlier_count=result.inlier_count, inlier_ratio=result.inlier_ratio,
                     reprojection_error_px=result.reprojection_error_px)
    label_fix(rec)
    results.append((query.path.name, result.num_matches, result.inlier_count, result.inlier_ratio, err, rec.safe_primary))
    print(f"[{i:2d}] {query.sequence:22s} matches={result.num_matches:4d} inliers={result.inlier_count:4d} "
          f"inlier_ratio={result.inlier_ratio:.2f} err={err if err is not None else float('nan'):8.2f}m "
          f"safe={rec.safe_primary}")

n_ok = sum(1 for r in results if r[5])
errs = [r[4] for r in results if r[4] is not None]
print(f"\n=== {n_ok}/{len(results)} SAFE (<=10m) ===")
if errs:
    print(f"median err={np.median(errs):.2f}m  mean={np.mean(errs):.2f}m  min={np.min(errs):.2f}m  max={np.max(errs):.2f}m")
print(f"ortalama inlier_ratio={np.mean([r[3] for r in results]):.3f}")
print(f"ortalama num_matches={np.mean([r[1] for r in results]):.1f}")
