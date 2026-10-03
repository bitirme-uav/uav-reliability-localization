"""AnyVisLoc acik-dongu fix-record veri seti (AerialVL / UAV-VisLoc ile ayni kosullar
ve sema). Kare once IMU tutumu (euler) ile sanal nadir kameraya cevrilir; yer
kapsami irtifa + DEM'den (uydu DSM) tahmin edilir ve olcek adaylari / harita payi
kare basina ondan turetilir. Etiket = kameranin altindaki yer noktasi.
Cikti: outputs/anyvisloc_fixes_<grup>.jsonl
Kullanim: python anyvisloc_build_fix_dataset.py --group recal|test|tune --per-scene 40"""
import argparse
import random
import time

import numpy as np

from anyvisloc_loader import AnyVisLoc
from anyvisloc_splits import RECAL_SCENES, TEST_SCENES, TUNE_SCENES
from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor

R_MIN, R_MAX = 60.0, 400.0
CONDITIONS = ((0, 20), (30, 20), (80, 40), (80, 20), (200, 80), (200, 20), (300, 140))

# AnyVisLoc platform ayarlari (SADECE TUNE sahnelerinde belirlendi). Kare basina
# olcekler yer kapsamindan (fpw) turetilir -> configure_for().
ANY_PIPE = dict(query_rotation=None, map_work_gsd_m=0.6, map_max_keypoints=4096, tile_radius_m=150.0)
FP_FACTORS = (0.85, 1.0, 1.2, 1.45)
COARSE_FACTORS = (1.0, 1.2)
MARGIN_FACTOR = 0.6


def make_pipeline():
    return LocalizationPipeline(**ANY_PIPE)


def configure_for(pipe, fpw):
    pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * k for k in FP_FACTORS)
    pipe.COARSE_FOOTPRINTS_M = tuple(fpw * k for k in COARSE_FACTORS)
    pipe.footprint_margin_m = MARGIN_FACTOR * fpw


def localize_frame(pipe, a, f, view, plon, plat, radius):
    img, mask, ctr, fpw, _ = view
    configure_for(pipe, fpw)
    return pipe.localize(img, MapExtractor(a.map_for(f)), plon, plat, radius, query_mask=mask, query_center_px=ctr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["recal", "test", "tune"])
    ap.add_argument("--per-scene", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scene", default=None, help="tek sahne (bellek sizintisina karsi sahne basina ayri surec)")
    args = ap.parse_args()
    scenes = {"recal": RECAL_SCENES, "test": TEST_SCENES, "tune": TUNE_SCENES}[args.group]
    if args.scene:
        assert args.scene in scenes
        scenes = (args.scene,)

    a = AnyVisLoc(scenes)
    base = 3000 + args.seed + (100 * int(args.scene) if args.scene else 0)   # sahne basina sabit tohum
    rng_py = random.Random(base)
    rng = np.random.default_rng(base)
    sample = []
    for s in scenes:
        fr = a.sequences[s]
        sample += rng_py.sample(fr, min(args.per_scene, len(fr)))

    pipe = make_pipeline()
    out = f"../outputs/anyvisloc_fixes_{args.group}.jsonl"
    if not args.scene:
        open(out, "w").close()
    writer = FixRecordWriter(out)       # sahne modunda ekleme (append)
    t0 = time.monotonic()
    for k, q in enumerate(sample):
        view = a.nadir_view(q)
        qlon, qlat = a.lonlat(q)
        for ci, (offset, sigma) in enumerate(CONDITIONS):
            th = rng.uniform(0, 2 * np.pi)
            px, py = offset * np.cos(th), offset * np.sin(th)
            radius = float(np.clip(3 * sigma, R_MIN, R_MAX))
            plon, plat = enu_to_lonlat_m(px, py, qlon, qlat)
            rec = FixRecord(
                run_id=f"anyvisloc_openloop_{args.group}", policy_id="none", seed=args.seed,
                sequence_id=q.scene, query_id=q.path, timestamp_s=float(k),
                magnitude_idx=offset, direction_idx=ci,
                prior_x_m=px, prior_y_m=py, prior_cov_xx=sigma ** 2, prior_cov_yy=sigma ** 2,
                true_offset_m=float(offset), search_window_m=radius, in_window=offset <= radius,
            )
            r = None if view is None else localize_frame(pipe, a, q, view, plon, plat, radius)
            if r is not None:
                rec.num_matches, rec.inlier_count, rec.inlier_ratio = r.num_matches, r.inlier_count, r.inlier_ratio
                rec.reprojection_error_px = r.reprojection_error_px
                rec.inlier_spatial_spread, rec.transform_condition = r.inlier_spatial_spread, r.transform_condition
                rec.query_ref_scale_ratio = r.query_ref_scale_ratio
                rec.top1_score, rec.top1_top2_margin = float(r.inlier_count), r.top1_top2_margin
                rec.raw_confidence, rec.localization_latency_ms = r.raw_confidence, r.localization_latency_ms
            if r is not None and r.predicted_lon is not None:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, qlon, qlat)
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
