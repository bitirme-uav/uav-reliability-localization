"""Faz E / M10: kapali-dongu GPS-denied navigasyon simulatoru, tum
politikalar ayni drift tohumu ve ayni cagri zamanlariyla.

Politikalar (M10):
  E1  drift-only               E6  calibrated (visual-only)
  E2  accept-all               E7  calibrated (visual + Mahalanobis)
  E3  raw-score gate           E8  calibrated + chi-square (ikisi de gecmeli)
  E4  heuristic (SatLoc) gate  E9  randomized-decision reference (sadece degerlendirme)
  E5  chi-square gate          E10 label-oracle reference (sadece degerlendirme, GT kullanir)

Duzeltme: 2D Kalman guncellemesi; down-weight = R_nominal * 4.
Ucus yonu (boresight duzeltmesi) politikanin KENDI dead-reckoning
artimlarindan alinir -- ground truth'tan degil.
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from collections import deque

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from boresight import correct_fix_enu
from drift_simulator import MATCHED_FILTER_NOISE, REGIME_PRESETS, DriftConfig, DriftSimulator, FilterNoiseConfig
from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import CHI2_THRESHOLD_ALPHA_005, heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from splits import TEST_SEQUENCES

VAL_ROOT = "/media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted"
R_MIN, R_MAX = 60.0, 400.0
DOWNWEIGHT_R_SCALE = 4.0
VEL_WINDOW = 6  # dead-reckoning hizi icin son N adim
ALL_POLICIES = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10")
V2_POLICIES = ("M10", "M25", "A25", "M10T", "M10A")
# M10T: M10 karari + ardisik-fix tutarliligi (REACQUIRE teyit fikrinin normal moda tasinmasi).
# Onceki fix (kabul edilsin edilmesin) olu-hesap hiziyla bugune tasinir; yeni fix TAU icindeyse ikisi
# birbirini dogrular (down-weight -> accept), degilse bir kademe dusurulur (accept -> dw -> reject).
CONS_TAU_M = 25.0
CONS_MAX_GAP_CALLS = 2.5   # reliability_v2_bundle.pkl: karisik/AerialVL modelleri, 10/25 m etiketi


class Policy:
    def __init__(self, pid: str, drift_cfg: DriftConfig, filter_cfg: FilterNoiseConfig):
        self.pid = pid
        self.sim = DriftSimulator(drift_cfg, filter_cfg)
        self.errors: list[float] = []
        self.counts = {"accept": 0, "down-weight": 0, "reject": 0, "no-fix": 0}
        self.harmful = 0
        self.incs: deque = deque(maxlen=VEL_WINDOW)
        self.last_post: np.ndarray | None = None
        self.last_t: float | None = None
        self.last_fix: tuple | None = None   # (xy, t) son uretilen fix (M10T)

    def step(self, t, gx, gy):
        s = self.sim.step(t, gx, gy)
        p = np.array([s.prior_x_m, s.prior_y_m])
        if self.last_post is not None:
            self.incs.append((p - self.last_post, t - self.last_t))
        self.last_post, self.last_t = p, t
        self.errors.append(s.true_offset_m)
        return s

    def dr_velocity(self) -> np.ndarray:
        if not self.incs:
            return np.zeros(2)
        d = sum(i[0] for i in self.incs)
        dt = sum(i[1] for i in self.incs)
        return d / max(dt, 1e-6)

    def correct(self, fix_xy, r_scalar, gx, gy):
        before = float(np.hypot(*(self.sim.current_prior()[0] - (gx, gy))))
        self.sim.apply_correction(fix_xy[0], fix_xy[1], r_scalar)
        p, _ = self.sim.current_prior()
        after = float(np.hypot(p[0] - gx, p[1] - gy))
        self.last_post = p
        self.errors[-1] = after
        if after > before:
            self.harmful += 1


def three_level(score, th):
    if score is None:
        return "reject"
    if score >= th["high"]:
        return "accept"
    if score >= th["low"]:
        return "down-weight"
    return "reject"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--drift", default="moderate", choices=list(REGIME_PRESETS))
    ap.add_argument("--filter", default="matched", choices=["matched", "misspecified"])
    ap.add_argument("--call-interval", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0, help="0 = tum sekans")
    ap.add_argument("--policies", default=",".join(ALL_POLICIES))
    ap.add_argument("--thresholds", default="../outputs/thresholds.json")
    ap.add_argument("--models", default="../outputs/calibration_models.pkl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--summary-out", default="../outputs/nav_sim_summary.jsonl")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--dataset", default="aerialvl", choices=["aerialvl", "visloc"])
    args = ap.parse_args()
    if args.dataset == "visloc":
        from visloc_splits import TEST_FLIGHTS as _VT
        test_seqs = _VT
    else:
        test_seqs = TEST_SEQUENCES
    if args.sequence in test_seqs and not args.allow_test:
        raise SystemExit("TEST sekansi: config freeze'den once calistirilmaz (SS9.1).")

    with open(args.thresholds) as f:
        TH = json.load(f)
    with open(args.models, "rb") as f:
        bundle = pickle.load(f)
    models, R_nominal = bundle["models"], bundle["R_nominal"]
    r_nom = float(np.mean(np.diag(R_nominal)))
    m_vis = models["cal_visual (logreg)"]
    m_vm = models["cal_vis+Mahal (gbm)"]
    V2 = {}
    if any(pp in V2_POLICIES for pp in args.policies.split(",")):
        with open("../outputs/reliability_v2_bundle.pkl", "rb") as f:
            V2 = pickle.load(f)

    if args.dataset == "visloc":
        from visloc_attitude import correct_fix_enu as att_correct, load_coef
        from visloc_build_fix_dataset import make_pipeline
        from visloc_loader import UAVVisLoc
        val = UAVVisLoc([args.sequence])
        att_coef = load_coef()
    else:
        val = AerialVLVal(VAL_ROOT)
    frames = val.sequences[args.sequence]
    if args.max_frames:
        frames = frames[: args.max_frames]
    o = frames[0]
    gt = [lonlat_to_enu_m(f.lon, f.lat, o.lon, o.lat) for f in frames]
    ts = [(f.utc_ts - o.utc_ts) / 1000.0 for f in frames]

    drift_cfg = DriftConfig(**{**REGIME_PRESETS[args.drift].__dict__, "seed": args.seed})
    q = MATCHED_FILTER_NOISE[args.drift] if args.filter == "matched" else MATCHED_FILTER_NOISE["mild"]
    filter_cfg = FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=q)
    pids = args.policies.split(",")
    pols = {p: Policy(p, drift_cfg, filter_cfg) for p in pids}
    rand_rng = np.random.default_rng(10_000 + args.seed)

    pipe = make_pipeline() if args.dataset == "visloc" else LocalizationPipeline()
    tag = f"{args.sequence}_{args.drift}_{args.filter}_ci{args.call_interval:g}_s{args.seed}"
    out = args.out or f"../outputs/navsim/{tag}.jsonl"
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").close()
    writer = FixRecordWriter(out)

    cache: dict = {}
    n_calls = n_loc = 0
    last_call = -1e9
    t0 = time.monotonic()
    for i, (f, (gx, gy), t) in enumerate(zip(frames, gt, ts)):
        samples = {p: pol.step(t, gx, gy) for p, pol in pols.items()}
        if t - last_call < args.call_interval:
            continue
        last_call = t
        n_calls += 1
        geo_map = val.map_for(f.lon, f.lat)
        if geo_map is None:
            continue
        img = None
        for p, pol in pols.items():
            if p == "E1":
                continue
            s = samples[p]
            prior = np.array([s.prior_x_m, s.prior_y_m])
            sigma = float(np.sqrt(s.prior_cov_xx))
            radius = float(np.clip(3 * sigma, R_MIN, R_MAX))
            key = (i, round(prior[0], 2), round(prior[1], 2), round(radius, 1))
            if key not in cache:
                if img is None:
                    img = val.image(f) if args.dataset == "visloc" else cv2.imread(str(f.path))
                plon, plat = enu_to_lonlat_m(prior[0], prior[1], o.lon, o.lat)
                rot = -f.yaw_deg if args.dataset == "visloc" else None
                cache[key] = pipe.localize(img, MapExtractor(geo_map), plon, plat, radius, query_rot_ccw_deg=rot)
                n_loc += 1
            r = cache[key]

            rec = FixRecord(run_id=tag, policy_id=p, seed=args.seed, drift_regime=args.drift,
                            filter_noise_setting=args.filter, call_interval_s=args.call_interval,
                            sequence_id=args.sequence, query_id=str(f.path) if args.dataset == "visloc" else f.path.stem, timestamp_s=t,
                            ground_truth_x_m=gx, ground_truth_y_m=gy, prior_x_m=prior[0], prior_y_m=prior[1],
                            prior_cov_xx=s.prior_cov_xx, prior_cov_yy=s.prior_cov_yy,
                            true_offset_m=s.true_offset_m, search_window_m=radius,
                            in_window=s.true_offset_m <= radius,
                            num_matches=r.num_matches, inlier_count=r.inlier_count, inlier_ratio=r.inlier_ratio,
                            reprojection_error_px=r.reprojection_error_px,
                            inlier_spatial_spread=r.inlier_spatial_spread,
                            transform_condition=r.transform_condition,
                            query_ref_scale_ratio=r.query_ref_scale_ratio,
                            top1_score=float(r.inlier_count), top1_top2_margin=r.top1_top2_margin,
                            raw_confidence=r.raw_confidence, localization_latency_ms=r.localization_latency_ms)
            fix = None
            if r.predicted_lon is not None:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, o.lon, o.lat)
                v = pol.dr_velocity()
                if args.dataset == "visloc":
                    fe, fn = att_correct(fe, fn, f.yaw_deg, f.omega, f.kappa, r.ground_footprint_m, att_coef)
                else:
                    fe, fn = correct_fix_enu(fe, fn, v[0], v[1])
                fix = np.array([fe, fn])
                rec.predicted_fix_x_m, rec.predicted_fix_y_m = fe, fn
                rec.fix_error_m = float(np.hypot(fe - gx, fn - gy))
                rec.mahalanobis_d = float(np.hypot(*(fix - prior)) / max(sigma, 1e-6))
                if r.top1_top2_margin is not None:
                    rec.heuristic_confidence = heuristic_confidence(r.inlier_count, r.top1_top2_margin, None)
                nu = fix - prior
                S = np.diag([s.prior_cov_xx, s.prior_cov_yy]) + R_nominal
                rec.chi2_d2 = float(nu @ np.linalg.inv(S) @ nu)
            label_fix(rec)

            if fix is None:
                decision = "reject"
                pol.counts["no-fix"] += 1
            else:
                row = rec.to_dict()
                if p == "E2":
                    decision = "accept"
                elif p == "E3":
                    decision = three_level(rec.raw_confidence, TH["E3"])
                elif p == "E4":
                    decision = three_level(rec.heuristic_confidence, TH["E4"])
                elif p == "E5":
                    decision = "reject" if rec.chi2_d2 > CHI2_THRESHOLD_ALPHA_005 else "accept"
                elif p == "E6":
                    rec.calibrated_reliability = float(m_vis.predict_proba([row])[0])
                    decision = three_level(rec.calibrated_reliability, TH["E6"])
                elif p in ("E7", "E8"):
                    rec.calibrated_reliability = float(m_vm.predict_proba([row])[0])
                    decision = three_level(rec.calibrated_reliability, TH["E7"])
                    if p == "E8" and rec.chi2_d2 > CHI2_THRESHOLD_ALPHA_005:
                        decision = "reject"
                elif p == "E9":
                    probs = TH["E9_decision_probs"]
                    decision = rand_rng.choice(["accept", "down-weight", "reject"],
                                               p=[probs["accept"], probs["down-weight"], probs["reject"]])
                elif p == "E10":
                    decision = "accept" if rec.safe_primary else "reject"
                elif p in V2_POLICIES:
                    b = V2["M10" if p == "M10T" else p]
                    rec.calibrated_reliability = float(b["model"].predict_proba([row])[0])
                    decision = three_level(rec.calibrated_reliability, b["th"])
                    if p == "M10T":
                        lf = pol.last_fix
                        if lf is not None and t - lf[1] <= CONS_MAX_GAP_CALLS * args.call_interval:
                            pred = lf[0] + pol.dr_velocity() * (t - lf[1])
                            if float(np.hypot(*(fix - pred))) <= CONS_TAU_M:
                                decision = "accept" if decision in ("accept", "down-weight") else decision
                            else:
                                decision = {"accept": "down-weight", "down-weight": "reject"}.get(decision, decision)
                        pol.last_fix = (fix.copy(), t)
                else:
                    decision = "reject"
            rec.decision = decision
            writer.write(rec)
            if fix is not None:
                pol.counts[decision] += 1
                r_use = float(np.mean(np.diag(V2["M10" if p == "M10T" else p]["R"]))) if p in V2_POLICIES else r_nom
                if decision == "accept":
                    pol.correct(fix, r_use, gx, gy)
                elif decision == "down-weight":
                    pol.correct(fix, r_use * DOWNWEIGHT_R_SCALE, gx, gy)
    writer.close()

    wall = time.monotonic() - t0
    print(f"{tag}: {len(frames)} kare, {n_calls} cagri, {n_loc} localize ({wall:.0f}s)")
    print(f"{'pol':4s} {'RMSE':>8s} {'final':>8s} {'max':>8s} {'acc':>4s} {'dw':>4s} {'rej':>4s} {'nofix':>5s} {'zararli':>7s}")
    os.makedirs(os.path.dirname(args.summary_out), exist_ok=True)
    with open(args.summary_out, "a") as fs:
        for p, pol in pols.items():
            e = np.array(pol.errors)
            row = dict(tag=tag, sequence=args.sequence, drift=args.drift, filter=args.filter,
                       call_interval=args.call_interval, seed=args.seed, policy=p,
                       rmse=float(np.sqrt(np.mean(e ** 2))), final=float(e[-1]), max=float(e.max()),
                       harmful=pol.harmful, n_calls=n_calls, **pol.counts)
            fs.write(json.dumps(row) + "\n")
            print(f"{p:4s} {row['rmse']:8.2f} {row['final']:8.2f} {row['max']:8.2f} {pol.counts['accept']:4d} "
                  f"{pol.counts['down-weight']:4d} {pol.counts['reject']:4d} {pol.counts['no-fix']:5d} {pol.harmful:7d}")


if __name__ == "__main__":
    main()
