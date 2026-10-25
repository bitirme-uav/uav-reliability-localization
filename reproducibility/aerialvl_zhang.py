"""Zhang et al. (UST 2026), "Map-Aided UAV Visual Localization via Visual Odometry and
Orthophoto Map Alignment", re-implemented and run on AerialVL.

The paper's two Tianjin flights are not released and no code is available, so its Table II
numbers cannot be re-run. What is reproduced is the method, on the public dataset closest to
its setting (gimbal-stabilised nadir camera, ~1 Hz frames, north-up orthophoto/satellite map):

  VO propagation   T_k^ = T_{k-1} H_{k-1,k}^-1                                   (Eq. 5)
                   x_k^ = pi(T_k^ c)                                             (Eq. 6)
                   H from SuperPoint + LightGlue + RANSAC between adjacent frames
                   (the paper uses XFeat + LightGlue and states the framework is not tied
                   to the feature module; SuperPoint + LightGlue is the project's matcher)
  map correction   every --keyframe frames: align with a patch around x_k^ (project localizer),
                   T_k^map, x_k^map = pi(T_k^map c)                              (Eq. 7-8)
  quality gate     matches, RANSAC inliers, inlier ratio, mean reprojection error and the
                   correction displacement d_k = ||x_k^map - x_k^||               (Eq. 9)
  relocalization   when VO fails or --reloc-after consecutive corrections are rejected:
                   a grid of candidate centres around x_k^, best candidate by inliers that
                   passes the relocalization gate                                 (Eq. 10)
  pure-VO baseline initial map alignment, then VO only; stops when VO fails.

The paper gives the gate criteria but no threshold values; ours are fixed a priori (below),
except the inlier-ratio bound, which is the project's frozen E3 value (chosen on open-loop
VAL fixes). T maps north-up query pixels to local ENU metres; it is a similarity here because
the project localizer estimates a 4-DOF transform to the map (the inter-frame H is a full
homography). Metrics: the paper's Table II/III and AerialVL Table VII (see aerialvl_table7.py).

Usage: python aerialvl_zhang.py [--seqs ST.5 LT.5 LT.6] [--mode zhang|pure_vo]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aerialvl_loader import AerialVLVal  # noqa: E402
from aerialvl_table7 import PAPER as PAPER_AVL, SEQS, VAL_ROOT, metrics as avl_metrics  # noqa: E402
from boresight import ALONG_TRACK_OFFSET_M  # noqa: E402
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m  # noqa: E402
from lightglue.utils import numpy_image_to_torch, rbd  # noqa: E402
from localization_pipeline import LocalizationPipeline, MapExtractor  # noqa: E402

OUT = Path(__file__).resolve().parent / "results" / "aerialvl_zhang"
PAPER_ZHANG = {  # Table II, proposed method: localized, mean, median, RMSE, max, final, <=10 m, <=20 m
    "Dataset 1": {"localized": "371/371", "mean": 8.1, "median": 7.2, "rmse": 8.9, "max": 19.2,
                  "final": 13.8, "le10": 80.3, "le20": 100.0, "pure_vo": {"localized": "326/371", "mean": 55.2}},
    "Dataset 2": {"localized": "302/302", "mean": 8.4, "median": 6.0, "rmse": 12.7, "max": 57.9,
                  "final": 23.1, "le10": 86.8, "le20": 92.4, "pure_vo": {"localized": "173/302", "mean": 133.2}},
}
F = np.diag([1.0, -1.0])  # image axes (x right, y down) -> (east, north) for a north-up image


class VO:
    """Inter-frame homography on north-up (rotated) frames at reduced resolution."""

    def __init__(self, pipe, width=640):
        self.pipe, self.width, self.prev = pipe, width, None

    def feats(self, img):
        f = self.width / img.shape[1]
        small = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        t = numpy_image_to_torch(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)).to(self.pipe.device)
        with torch.no_grad():
            return self.pipe.extractor.extract(t), f

    def step(self, img):
        """Homography prev -> current in full-resolution pixels (None if tracking fails)."""
        cur = self.feats(img)
        prev, self.prev = self.prev, cur
        if prev is None:
            return None, 0
        (f0, s), (f1, _) = prev, cur
        with torch.no_grad():
            m = self.pipe.matcher({"image0": f0, "image1": f1})
        f0_, f1_, m = (rbd(x) for x in (f0, f1, m))
        idx = m["matches"]
        if len(idx) < 15:
            return None, len(idx)
        p0 = f0_["keypoints"][idx[:, 0]].cpu().numpy() / s
        p1 = f1_["keypoints"][idx[:, 1]].cpu().numpy() / s
        H, inl = cv2.findHomography(p0, p1, cv2.RANSAC, 4.0)
        if H is None or inl.sum() < 15:
            return None, int(0 if inl is None else inl.sum())
        return H, int(inl.sum())


def pi(T, c):
    v = T @ np.array([c[0], c[1], 1.0])
    return v[:2] / v[2]


def T_from_fix(r, fix_en, c):
    """Similarity T (north-up query px -> ENU m) whose centre maps to fix_en."""
    s = r.ground_footprint_m / r._w0  # metres per original query pixel
    th = np.radians(r.rotation_deg or 0.0)
    A = s * F @ np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    T = np.eye(3)
    T[:2, :2] = A
    T[:2, 2] = fix_en - A @ np.asarray(c)
    return T


class Aligner:
    def __init__(self, val, pipe, origin, a, thr_ratio):
        self.val, self.pipe, self.o, self.a, self.thr_ratio = val, pipe, origin, a, thr_ratio
        self.extractors, self.calls, self.seconds = {}, 0, 0.0

    def align(self, raw, w_rot, center_en):
        """raw: original frame (the localizer rotates it north-up itself); w_rot: north-up width."""
        lon, lat = enu_to_lonlat_m(center_en[0], center_en[1], *self.o)
        gmap = self.val.map_for(lon, lat)
        if gmap is None:
            return None
        me = self.extractors.setdefault(gmap.name, MapExtractor(gmap))
        t0 = time.time()
        r = self.pipe.localize(raw, me, lon, lat, self.a.radius)
        self.calls += 1
        self.seconds += time.time() - t0
        if r.predicted_lon is None or r.ground_footprint_m is None:
            return None
        r._w0 = w_rot  # ground_footprint_m spans the north-up query width
        r.en = np.array(lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, *self.o))
        return r

    def passes(self, r, pred_en, max_disp):
        if r is None:
            return False, None
        d = float(np.hypot(*(r.en - pred_en)))
        ok = (r.num_matches >= self.a.min_matches and r.inlier_count >= self.a.min_inliers
              and r.inlier_ratio >= self.thr_ratio and (r.reprojection_error_px or 1e9) <= self.a.max_reproj
              and d <= max_disp)
        return ok, d


def boresight(fix_en, vel):
    sp = float(np.hypot(*vel))
    return fix_en if sp < 1.0 else fix_en + ALONG_TRACK_OFFSET_M * vel / sp


def run(val, pipe, frames, a, thr_ratio, mode):
    o = (frames[0].lon, frames[0].lat)
    gt = np.array([lonlat_to_enu_m(f.lon, f.lat, *o) for f in frames])
    al, vo = Aligner(val, pipe, o, a, thr_ratio), VO(pipe)
    T, vel, recs, rejects, n_acc, n_reloc, vo_s = None, np.zeros(2), [], 0, 0, 0, 0.0
    alive = True
    for k, f in enumerate(frames):
        raw = cv2.imread(str(f.path))
        img = cv2.rotate(raw, pipe.query_rotation)  # north-up, for VO and for T's pixel frame
        c, w = (img.shape[1] / 2.0, img.shape[0] / 2.0), img.shape[1]
        t0 = time.time()
        H, vo_inl = vo.step(img)
        vo_s += time.time() - t0
        event = ""
        if T is None:  # initial strictly successful map alignment around the known start
            r = al.align(raw, w, gt[0])
            if al.passes(r, gt[0], a.reloc_max_disp)[0]:
                T, n_acc, event = T_from_fix(r, r.en, c), n_acc + 1, "init"
            x = pi(T, c) if T is not None else None
        else:
            prev_x = pi(T, c)
            vo_ok = H is not None
            if vo_ok:
                T = T @ np.linalg.inv(H)  # Eq. (5)
            elif mode == "pure_vo":
                alive = False
            pred = pi(T, c)  # Eq. (6)
            if k and frames[k].utc_ts > frames[k - 1].utc_ts:
                vel = (pred - prev_x) / ((frames[k].utc_ts - frames[k - 1].utc_ts) / 1000.0)
            if mode == "zhang":
                if not vo_ok or rejects >= a.reloc_after:  # local relocalization
                    n_reloc += 1
                    best = None
                    for dx in (-a.reloc_step, 0, a.reloc_step):
                        for dy in (-a.reloc_step, 0, a.reloc_step):
                            r = al.align(raw, w, pred + np.array([dx, dy]))
                            if r is not None:
                                r.en = boresight(r.en, vel)
                            ok, _ = al.passes(r, pred, a.reloc_max_disp)
                            if ok and (best is None or r.inlier_count > best.inlier_count):
                                best = r
                    if best is not None:
                        T, rejects, n_acc, event = T_from_fix(best, best.en, c), 0, n_acc + 1, "reloc"
                    else:
                        event = "reloc_fail"
                elif k % a.keyframe == 0:  # periodic map correction
                    r = al.align(raw, w, pred)
                    if r is not None:
                        r.en = boresight(r.en, vel)
                    ok, d = al.passes(r, pred, a.max_disp)
                    if ok:
                        T, rejects, n_acc, event = T_from_fix(r, r.en, c), 0, n_acc + 1, "correct"
                    else:
                        rejects, event = rejects + 1, "reject"
            x = pi(T, c)
        localized = alive and x is not None
        recs.append({"k": k, "t": f.utc_ts / 1000.0, "gt_e": float(gt[k][0]), "gt_n": float(gt[k][1]),
                     "est_e": float(x[0]) if x is not None else None, "est_n": float(x[1]) if x is not None else None,
                     "err": float(np.hypot(*(x - gt[k]))) if x is not None else None,
                     "localized": localized, "accepted": event in ("init", "correct", "reloc"),
                     "event": event, "vo_inliers": vo_inl})
        if k % 100 == 0:
            e = [r["err"] for r in recs if r["localized"]]
            print(f"  {mode} {k}/{len(frames)} err={recs[-1]['err']} med={np.median(e) if e else None} "
                  f"acc={n_acc} reloc={n_reloc}", flush=True)
    stats = {"map_candidates": al.calls, "accepted_map": n_acc, "relocalizations": n_reloc,
             "vo_time_s": round(vo_s / len(frames), 3), "map_align_time_s": round(al.seconds / max(al.calls, 1), 3)}
    return recs, stats


def zhang_metrics(recs):
    loc = [r for r in recs if r["localized"]]
    e = np.array([r["err"] for r in loc])
    if not len(e):
        return {"localized": f"0/{len(recs)}"}
    return {"localized": f"{len(loc)}/{len(recs)}", "mean": round(float(e.mean()), 1),
            "median": round(float(np.median(e)), 1), "rmse": round(float(np.sqrt((e ** 2).mean())), 1),
            "max": round(float(e.max()), 1), "final": round(float(e[-1]), 1),
            "le10": round(100 * float((e <= 10).mean()), 1), "le20": round(100 * float((e <= 20).mean()), 1)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seqs", nargs="*", default=list(SEQS))
    p.add_argument("--modes", nargs="*", default=["zhang", "pure_vo"])
    p.add_argument("--stride", type=int, default=2, help="AerialVL frames are ~0.5 s apart; 2 -> ~1 Hz as in the paper")
    p.add_argument("--keyframe", type=int, default=2, help="map correction every n processed frames")
    p.add_argument("--radius", type=float, default=60.0)
    p.add_argument("--min-matches", type=int, default=30)
    p.add_argument("--min-inliers", type=int, default=20)
    p.add_argument("--max-reproj", type=float, default=3.0)
    p.add_argument("--max-disp", type=float, default=30.0, help="correction displacement gate (m)")
    p.add_argument("--reloc-after", type=int, default=3)
    p.add_argument("--reloc-step", type=float, default=60.0)
    p.add_argument("--reloc-max-disp", type=float, default=150.0)
    p.add_argument("--limit", type=int, default=0, help="smoke test: first n processed frames, results not saved")
    a = p.parse_args()
    thr = json.loads((ROOT / "outputs" / "thresholds.json").read_text())["E3"]["low"]
    OUT.mkdir(parents=True, exist_ok=True)
    val = AerialVLVal(VAL_ROOT)
    pipe = LocalizationPipeline()
    sp = OUT / "summary.json"
    summary = json.loads(sp.read_text()) if sp.exists() else {}
    for name in a.seqs:
        frames = val.sequences[SEQS[name]][::a.stride]
        if a.limit:
            for mode in a.modes:
                recs, stats = run(val, pipe, frames[:a.limit], a, thr, mode)
                print("SMOKE", name, mode, zhang_metrics(recs), stats, flush=True)
            continue
        for mode in a.modes:
            print(name, mode, len(frames), "frames", flush=True)
            t0 = time.time()
            recs, stats = run(val, pipe, frames, a, thr, mode)
            with open(OUT / f"{name}_{mode}.jsonl", "w") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
            loc = [r for r in recs if r["localized"]]
            summary[f"{name}/{mode}"] = {
                "sequence": SEQS[name], "zhang_table2": zhang_metrics(recs), "zhang_table3": stats,
                "aerialvl_table7": avl_metrics(loc) if loc else None, "paper_aerialvl": PAPER_AVL[name],
                "settings": {**vars(a), "E3_low": thr}, "seconds": round(time.time() - t0)}
            summary["paper_zhang"] = PAPER_ZHANG
            sp.write_text(json.dumps(summary, indent=1))
            print(name, mode, summary[f"{name}/{mode}"]["zhang_table2"], flush=True)


if __name__ == "__main__":
    main()
