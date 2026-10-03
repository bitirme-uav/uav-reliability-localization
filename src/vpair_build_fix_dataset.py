"""VPAIR acik-dongu fix-record veri seti (diger veri setleriyle ayni kosullar ve sema).
Kare kuzey-yukari icin -yaw kadar dondurulur; yer kapsami = 800 px * AGL / f.
Kullanim: python vpair_build_fix_dataset.py --group tune|test"""
import argparse
import time

import numpy as np

from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from vpair_loader import BODY_BIAS_M, F_PX, TEST_IDS, TUNE_IDS, VPAIR

R_MIN, R_MAX = 60.0, 400.0
CONDITIONS = ((0, 20), (30, 20), (80, 40), (80, 20), (200, 80), (200, 20), (300, 140))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["tune", "test"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    v = VPAIR()
    ids = TUNE_IDS if args.group == "tune" else TEST_IDS
    sample = [v.by_id[i] for i in ids if i in v.by_id and np.isfinite(v.agl(v.by_id[i]))]
    if args.limit:
        sample = sample[: args.limit]
    gm = v.geomap()
    pipe = LocalizationPipeline(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0)
    rng = np.random.default_rng(4000 + args.seed)
    out = f"../outputs/vpair_fixes_{args.group}.jsonl"
    open(out, "w").close()
    writer = FixRecordWriter(out)
    t0 = time.monotonic()
    for k, q in enumerate(sample):
        img = v.image(q)
        fpw = img.shape[1] * v.agl(q) / F_PX
        pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * s for s in (0.85, 1.0, 1.2))
        pipe.COARSE_FOOTPRINTS_M = (fpw,)
        pipe.footprint_margin_m = 0.6 * fpw
        for ci, (offset, sigma) in enumerate(CONDITIONS):
            th = rng.uniform(0, 2 * np.pi)
            px, py = offset * np.cos(th), offset * np.sin(th)
            radius = float(np.clip(3 * sigma, R_MIN, R_MAX))
            plon, plat = enu_to_lonlat_m(px, py, q.lon, q.lat)
            r = pipe.localize(img, MapExtractor(gm), plon, plat, radius, query_rot_ccw_deg=-q.yaw_deg)
            rec = FixRecord(
                run_id=f"vpair_openloop_{args.group}", policy_id="none", seed=args.seed,
                sequence_id="vpair", query_id=q.path, timestamp_s=q.utc_ts,
                magnitude_idx=offset, direction_idx=ci,
                prior_x_m=px, prior_y_m=py, prior_cov_xx=sigma ** 2, prior_cov_yy=sigma ** 2,
                true_offset_m=float(offset), search_window_m=radius, in_window=offset <= radius,
                num_matches=r.num_matches, inlier_count=r.inlier_count, inlier_ratio=r.inlier_ratio,
                reprojection_error_px=r.reprojection_error_px,
                inlier_spatial_spread=r.inlier_spatial_spread, transform_condition=r.transform_condition,
                query_ref_scale_ratio=r.query_ref_scale_ratio,
                top1_score=float(r.inlier_count), top1_top2_margin=r.top1_top2_margin,
                raw_confidence=r.raw_confidence, localization_latency_ms=r.localization_latency_ms,
            )
            if r.predicted_lon is not None:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
                if args.group == "test":      # TUNE'da olculen sabit ofset duzeltmesi
                    h = np.radians(q.yaw_deg); bf, br = BODY_BIAS_M
                    fe -= bf * np.sin(h) + br * np.cos(h); fn -= bf * np.cos(h) - br * np.sin(h)
                rec.predicted_fix_x_m, rec.predicted_fix_y_m = fe, fn
                rec.fix_error_m = float(np.hypot(fe, fn))
                rec.mahalanobis_d = float(np.hypot(fe - px, fn - py) / sigma)
                if r.top1_top2_margin is not None:
                    rec.heuristic_confidence = heuristic_confidence(r.inlier_count, r.top1_top2_margin, None)
            else:
                rec.fix_error_m = 1e6
            label_fix(rec)
            writer.write(rec)
        if (k + 1) % 20 == 0:
            print(f"  {k+1}/{len(sample)} query ({time.monotonic()-t0:.0f}s)", flush=True)
    writer.close()
    print(f"yazildi: {out}")
