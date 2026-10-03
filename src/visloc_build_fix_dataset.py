"""UAV-VisLoc acik-dongu fix-record veri seti (AerialVL build_fix_dataset ile
ayni kosullar ve sema). Farklar: kare basina yaw ile kuzey-yukari dondurme,
buyuk yer kapsami icin harita payi, kamera-egiklik duzeltmesi (boresight
yerine). Cikti: outputs/visloc_fixes_<grup>.jsonl
Kullanim: python visloc_build_fix_dataset.py --group recal|test|tune --per-flight 50"""
import argparse
import random
import time

import numpy as np

from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from visloc_attitude import correct_fix_enu, load_coef
from visloc_loader import UAVVisLoc
from visloc_splits import RECAL_FLIGHTS, TEST_FLIGHTS, TUNE_FLIGHTS

R_MIN, R_MAX = 60.0, 400.0
CONDITIONS = ((0, 20), (30, 20), (80, 40), (80, 20), (200, 80), (200, 20), (300, 140))

# UAV-VisLoc platform ayarlari (SADECE TUNE ucuslarinda belirlendi)
VISLOC_PIPE = dict(query_rotation=None, footprint_candidates_m=(250, 400, 600, 850),
                   footprint_margin_m=450.0, map_work_gsd_m=0.8, map_max_keypoints=4096,
                   tile_radius_m=300.0, coarse_footprints_m=(400, 600))


def make_pipeline():
    return LocalizationPipeline(**VISLOC_PIPE)


# Harita secim kurallari (gelistirme ucuslarina gore, TEST'ten ONCE sabitlendi, 2026-10-03).
# Her kosulda tum aday haritalarda lokalize et, en cok inlier vereni sec (GT kullanmaz).
#   dataset : yalniz veri setinin haritasi (onceki sonuclar)
#   k1      : veri seti + Google 'ucustan once en yakin' (gercekci)
#   k2      : veri seti + Google once/yakin + tum Wayback cekimleri (geriye donuk; ucus-sonrasi dahil)
def candidate_maps(rule, flight):
    import json as _json
    from aerialvl_loader import GeoMap
    from visloc_loader import ROOT
    out = []
    srcs = {"dataset": [], "k1": [("google", {"once"})], "k2": [("google", None), ("wayback", None)]}[rule]
    for src, keep in srcs:
        p = ROOT / f"ext_{src}" / flight / "index.json"
        if not p.exists():
            continue
        for r in _json.load(open(p)):
            if keep is None or r["date"] in keep:
                w, s_, e, n = r["bbox"]
                out.append(GeoMap(path=r["path"], name=f"{src}_{flight}_{r['date']}", lt_lon=w, lt_lat=n, rb_lon=e, rb_lat=s_))
    return out


def localize_best(pipe, img, maps, plon, plat, radius, rot):
    best = None
    for m in maps:
        try:
            r = pipe.localize(img, MapExtractor(m), plon, plat, radius, query_rot_ccw_deg=rot)
        except Exception:
            continue
        if best is None or (r.predicted_lon is not None and (best.predicted_lon is None or r.inlier_count > best.inlier_count)):
            best = r
    return best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["recal", "test", "tune"])
    ap.add_argument("--per-flight", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--maps", default="dataset", choices=["dataset", "k1", "k2"])
    args = ap.parse_args()
    flights = {"recal": RECAL_FLIGHTS, "test": TEST_FLIGHTS, "tune": TUNE_FLIGHTS}[args.group]

    v = UAVVisLoc(list(flights))
    coef = load_coef()
    rng_py = random.Random(2000 + args.seed)
    rng = np.random.default_rng(2000 + args.seed)
    sample = []
    for fl in flights:
        fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
        sample += rng_py.sample(fr, min(args.per_flight, len(fr)))

    pipe = make_pipeline()
    out = f"../outputs/visloc_fixes_{args.group}.jsonl" if args.maps == "dataset" else \
        f"../outputs/visloc_fixes_{args.group}_{args.maps}.jsonl"
    open(out, "w").close()
    writer = FixRecordWriter(out)
    t0 = time.monotonic()
    for k, q in enumerate(sample):
        img = v.image(q)
        geo_map = v.map_for(q.lon, q.lat)
        maps = [geo_map] + candidate_maps(args.maps, q.sequence)
        for ci, (offset, sigma) in enumerate(CONDITIONS):
            th = rng.uniform(0, 2 * np.pi)
            px, py = offset * np.cos(th), offset * np.sin(th)
            radius = float(np.clip(3 * sigma, R_MIN, R_MAX))
            plon, plat = enu_to_lonlat_m(px, py, q.lon, q.lat)
            r = localize_best(pipe, img, maps, plon, plat, radius, -q.yaw_deg)
            rec = FixRecord(
                run_id=f"visloc_openloop_{args.group}", policy_id="none", seed=args.seed,
                sequence_id=q.sequence, query_id=q.path, timestamp_s=q.utc_ts / 1000.0,
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
                fe, fn = correct_fix_enu(fe, fn, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, coef)
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
