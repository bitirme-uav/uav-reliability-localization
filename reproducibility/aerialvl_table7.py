"""AerialVL (He et al., RA-L 2024) Table VII protocol with this project's localizer.

Table VII runs a sequential visual-alignment localization from a known start pose on three
trajectories (ST.5 5.09 km, LT.5 7.83 km, LT.6 11.05 km) and reports
  Succ. Rate : share of the non-drift trajectory with error < 25 m (drift = error > 50 m)
  MLE        : mean localization error over the trajectory except the drift part.
Table V's CTL (length localized within 50 m) is reported as well.

Sequence mapping (paper lengths are ~1.13x the GNSS polyline length of our frames, for all
three; see README): ST.5 = 2023-03-18-16-43-16, LT.5 = 2023-03-18-15-01-14,
LT.6 = 2023-03-18-15-40-18.

Tracking loop (no ground truth after the first frame):
  prediction  = last estimate + constant velocity (estimated from accepted fixes; the paper
                uses SIFT/SuperPoint frame-to-frame tracking here, we have no VO)
  alignment   = SuperPoint + LightGlue against the map within --radius of the prediction,
                boresight-corrected (project M2, frozen)
  acceptance  = frozen project raw-score gate E3 (inlier ratio >= outputs/thresholds.json
                E3.low, chosen on open-loop VAL fixes) and >= --min-inliers inliers
  recovery    = after --miss consecutive rejections the search widens to --recover-radius
                (tiled search; stands in for the paper's global retrieval stage)

Usage: python aerialvl_table7.py [--seqs ST.5 LT.5 LT.6] [--stride 2]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aerialvl_loader import AerialVLVal  # noqa: E402
from boresight import correct_fix_enu  # noqa: E402
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m  # noqa: E402
from localization_pipeline import LocalizationPipeline, MapExtractor  # noqa: E402

VAL_ROOT = r"D:/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted"
OUT = Path(__file__).resolve().parent / "results" / "aerialvl_table7"
SEQS = {"ST.5": "2023-03-18-16-43-16", "LT.5": "2023-03-18-15-01-14", "LT.6": "2023-03-18-15-40-18"}
PAPER = {  # Table VII: Succ. Rate (%), MLE (m)
    "ST.5": {"km": 5.09, "Comb.1": (71.41, 20.01), "Comb.2": (79.57, 22.27)},
    "LT.5": {"km": 7.83, "Comb.1": (40.87, 26.92), "Comb.2": (83.27, 14.22)},
    "LT.6": {"km": 11.05, "Comb.1": (70.05, 17.89), "Comb.2": (88.04, 17.50)},
}


def track(val, pipe, frames, a, thr):
    o_lon, o_lat = frames[0].lon, frames[0].lat
    gt = np.array([lonlat_to_enu_m(f.lon, f.lat, o_lon, o_lat) for f in frames])
    est = gt[0].copy()  # known start position, as in the paper
    vel = np.zeros(2)
    last_fix, last_fix_t = est.copy(), frames[0].utc_ts / 1000.0
    t_prev, misses, extractors, recs = last_fix_t, 0, {}, []
    for k, f in enumerate(frames):
        t = f.utc_ts / 1000.0
        pred = est + vel * (t - t_prev) if k else est
        radius = a.recover_radius if misses >= a.miss else a.radius
        plon, plat = enu_to_lonlat_m(pred[0], pred[1], o_lon, o_lat)
        gmap = val.map_for(plon, plat) or val.map_for(f.lon, f.lat)
        accepted, r = False, None
        if gmap is not None:
            me = extractors.setdefault(gmap.name, MapExtractor(gmap))
            r = pipe.localize(cv2.imread(str(f.path)), me, plon, plat, radius)
            if (r.predicted_lon is not None and r.raw_confidence >= thr
                    and r.inlier_count >= a.min_inliers):
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, o_lon, o_lat)
                fe, fn = correct_fix_enu(fe, fn, vel[0], vel[1])
                fix = np.array([fe, fn])
                if t > last_fix_t:
                    v_new = (fix - last_fix) / (t - last_fix_t)
                    vel = v_new if not np.any(vel) else 0.5 * vel + 0.5 * v_new
                est, last_fix, last_fix_t, accepted, misses = fix, fix, t, True, 0
        if not accepted:
            est, misses = pred, misses + 1
        t_prev = t
        recs.append({"k": k, "t": t, "gt_e": gt[k][0], "gt_n": gt[k][1], "est_e": float(est[0]),
                     "est_n": float(est[1]), "err": float(np.hypot(*(est - gt[k]))), "accepted": accepted,
                     "radius": radius, "inliers": None if r is None else int(r.inlier_count),
                     "inlier_ratio": None if r is None else float(r.raw_confidence)})
        if k % 100 == 0:
            print(f"  {k}/{len(frames)} err={recs[-1]['err']:.1f} acc={np.mean([x['accepted'] for x in recs]):.2f}",
                  flush=True)
    return recs


def metrics(recs):
    gt = np.array([[r["gt_e"], r["gt_n"]] for r in recs])
    err = np.array([r["err"] for r in recs])
    seg = np.r_[0.0, np.hypot(*np.diff(gt, axis=0).T)]  # path length attributed to each frame
    ok, nd = err < 25, err <= 50
    return {
        "frames": len(recs), "path_km": round(seg.sum() / 1000, 2),
        "succ_rate_nondrift_pct": round(100 * seg[ok].sum() / max(seg[nd].sum(), 1e-9), 2),
        "succ_rate_total_pct": round(100 * seg[ok].sum() / seg.sum(), 2),
        "MLE_nondrift_m": round(float(err[nd].mean()), 2) if nd.any() else None,
        "RMSE_nondrift_m": round(float(np.sqrt((err[nd] ** 2).mean())), 2) if nd.any() else None,
        "CTL_m": round(float(seg[nd].sum()), 0), "drift_pct": round(100 * seg[~nd].sum() / seg.sum(), 2),
        "median_err_m": round(float(np.median(err)), 2), "accept_rate": round(float(np.mean([r["accepted"] for r in recs])), 3),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seqs", nargs="*", default=list(SEQS))
    p.add_argument("--stride", type=int, default=2, help="use every n-th frame (frames are ~0.5 s apart)")
    p.add_argument("--radius", type=float, default=60.0)
    p.add_argument("--recover-radius", type=float, default=300.0)
    p.add_argument("--miss", type=int, default=5)
    p.add_argument("--min-inliers", type=int, default=15)
    a = p.parse_args()
    thr = json.loads((ROOT / "outputs" / "thresholds.json").read_text())["E3"]["low"]
    OUT.mkdir(parents=True, exist_ok=True)
    val = AerialVLVal(VAL_ROOT)
    pipe = LocalizationPipeline()
    summary_path = OUT / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in a.seqs:
        frames = val.sequences[SEQS[name]][::a.stride]
        print(name, SEQS[name], len(frames), "frames", flush=True)
        t0 = time.time()
        recs = track(val, pipe, frames, a, thr)
        with open(OUT / f"{name}.jsonl", "w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        summary[name] = {"sequence": SEQS[name], "ours": metrics(recs), "paper": PAPER[name],
                         "settings": {**vars(a), "E3_low": thr}, "seconds": round(time.time() - t0)}
        summary_path.write_text(json.dumps(summary, indent=1))
        print(name, summary[name]["ours"], flush=True)


if __name__ == "__main__":
    main()
