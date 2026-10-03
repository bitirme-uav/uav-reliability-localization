"""M9 / E11: buyuk-drift kurtarma (REACQUIRE + teyit).

t_inject anında prior'a buyuk bir sicrama (varsayilan 300 m) enjekte
edilir; filtrenin kovaryansi buyutulmez (filtre hatanin farkinda degil).

Senaryo A: sonrasinda gercek lokalizer ciktilari (dogru-ama-uzak fix'ler).
Senaryo B: REACQUIRE'a girdikten sonraki ILK cagrida lokalizer ciktisi,
  ayni ozellik/guven degerleriyle ama 150 m kaydirilmis "inandirici yanlis
  fix" ile degistirilir (kendine-benzer bolgeden gelen guvenli-ama-yanlis fix).

Varyantlar:
  chi2_only      : sadece chi-square, REACQUIRE yok
  cal_normal     : kalibre (vis+Mahal) + chi2, REACQUIRE yok
  reacq_k1       : REACQUIRE var ama teyit yok (k=1)
  reacq_k2       : onerilen: REACQUIRE + k=2 teyit (dead-reckoned tutarlilik)

REACQUIRE modunda (M9): arama r_max'a genisler, chi-square/Mahalanobis
cezasi askiya alinir (kalibre GORUNTU-ONLY model kullanilir), kabul icin
k ardisik guvenilir fix'in birbirine gore yer degistirmesi dead-reckoned
yer degistirmeyle tau icinde uyusmali.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from boresight import correct_fix_enu
from drift_simulator import MATCHED_FILTER_NOISE, REGIME_PRESETS, DriftConfig, FilterNoiseConfig
from gates import CHI2_THRESHOLD_ALPHA_005
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from run_nav_sim import R_MAX, R_MIN, Policy
from splits import TEST_SEQUENCES

VAL_ROOT = "/media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted"
VARIANTS = ("chi2_only", "cal_normal", "reacq_k1", "reacq_k2")
N_REJECT_FOR_REACQ = 3
TAU_M = 2 * 10.0 + 5.0  # M9: 2 x primary esik + beklenen goreli drift
RECOVERED_M = 25.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--scenario", choices=["A", "B"], required=True)
    ap.add_argument("--inject-m", type=float, default=300.0)
    ap.add_argument("--t-inject", type=float, default=60.0)
    ap.add_argument("--drift", default="moderate")
    ap.add_argument("--call-interval", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--thresholds", default="../outputs/thresholds.json")
    ap.add_argument("--models", default="../outputs/calibration_models.pkl")
    ap.add_argument("--summary-out", default="../outputs/reacquire_summary.jsonl")
    ap.add_argument("--allow-test", action="store_true")
    args = ap.parse_args()
    if args.sequence in TEST_SEQUENCES and not args.allow_test:
        raise SystemExit("TEST sekansi: config freeze'den once calistirilmaz.")

    TH = json.load(open(args.thresholds))
    bundle = pickle.load(open(args.models, "rb"))
    R_nominal = bundle["R_nominal"]
    r_nom = float(np.mean(np.diag(R_nominal)))
    m_vis = bundle["models"]["cal_visual (logreg)"]
    m_vm = bundle["models"]["cal_vis+Mahal (gbm)"]

    val = AerialVLVal(VAL_ROOT)
    frames = val.sequences[args.sequence]
    if args.max_frames:
        frames = frames[: args.max_frames]
    o = frames[0]
    gt = [lonlat_to_enu_m(f.lon, f.lat, o.lon, o.lat) for f in frames]
    ts = [(f.utc_ts - o.utc_ts) / 1000.0 for f in frames]

    drift_cfg = DriftConfig(**{**REGIME_PRESETS[args.drift].__dict__, "seed": args.seed})
    filter_cfg = FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=MATCHED_FILTER_NOISE[args.drift])
    pols = {v: Policy(v, drift_cfg, filter_cfg) for v in VARIANTS}
    rng = np.random.default_rng(20_000 + args.seed)
    th_inj = rng.uniform(0, 2 * np.pi)
    inj = args.inject_m * np.array([np.cos(th_inj), np.sin(th_inj)])
    th_false = rng.uniform(0, 2 * np.pi)
    false_shift = 150.0 * np.array([np.cos(th_false), np.sin(th_false)])

    st = {v: dict(mode="NORMAL", streak=0, pending=[], recovered_t=None, false_accepts=0,
                  reacq_time=0.0, b_injected=False, last_dr_pos=None) for v in VARIANTS}
    pipe = LocalizationPipeline()
    cache = {}
    injected = False
    last_call = -1e9
    prev_t = ts[0]

    for i, (f, (gx, gy), t) in enumerate(zip(frames, gt, ts)):
        for v, pol in pols.items():
            pol.step(t, gx, gy)
        if not injected and t >= args.t_inject:
            for pol in pols.values():
                pol.sim.inject_offset(*inj)
                pol.last_post = pol.sim.current_prior()[0]
                pol.errors[-1] = float(np.hypot(*(pol.sim.current_prior()[0] - (gx, gy))))
            injected = True
        for v in VARIANTS:
            if st[v]["mode"] == "REACQUIRE":
                st[v]["reacq_time"] += t - prev_t
        prev_t = t
        # kurtarma zamani: enjeksiyondan sonra ilk kez hata < RECOVERED_M
        if injected:
            for v, pol in pols.items():
                if st[v]["recovered_t"] is None and pol.errors[-1] < RECOVERED_M:
                    st[v]["recovered_t"] = t - args.t_inject

        if t - last_call < args.call_interval:
            continue
        last_call = t
        geo_map = val.map_for(f.lon, f.lat)
        if geo_map is None:
            continue
        img = None
        for v, pol in pols.items():
            S = st[v]
            prior, P = pol.sim.current_prior()
            sigma = float(np.sqrt(P))
            reacq = S["mode"] == "REACQUIRE"
            radius = R_MAX if reacq else float(np.clip(3 * sigma, R_MIN, R_MAX))
            key = (i, round(prior[0], 2), round(prior[1], 2), round(radius, 1))
            if key not in cache:
                if img is None:
                    img = cv2.imread(str(f.path))
                plon, plat = enu_to_lonlat_m(prior[0], prior[1], o.lon, o.lat)
                cache[key] = pipe.localize(img, MapExtractor(geo_map), plon, plat, radius)
            r = cache[key]
            if r.predicted_lon is None:
                fix = None
            else:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, o.lon, o.lat)
                vel = pol.dr_velocity()
                fix = np.array(correct_fix_enu(fe, fn, vel[0], vel[1]))
            if fix is None:
                feats = None
            else:
                feats = dict(num_matches=r.num_matches, inlier_count=r.inlier_count, inlier_ratio=r.inlier_ratio,
                             reprojection_error_px=r.reprojection_error_px,
                             inlier_spatial_spread=r.inlier_spatial_spread,
                             transform_condition=r.transform_condition, top1_top2_margin=r.top1_top2_margin,
                             query_ref_scale_ratio=r.query_ref_scale_ratio,
                             mahalanobis_d=float(np.hypot(*(fix - prior)) / max(sigma, 1e-6)))
                nu = fix - prior
                d2 = float(nu @ np.linalg.inv(np.eye(2) * P + R_nominal) @ nu)
            fix_err = None if fix is None else float(np.hypot(fix[0] - gx, fix[1] - gy))

            # --- karar ---
            decision = "reject"
            if fix is not None:
                if v == "chi2_only":
                    decision = "accept" if d2 <= CHI2_THRESHOLD_ALPHA_005 else "reject"
                elif not reacq:
                    p = float(m_vm.predict_proba([feats])[0])
                    decision = "accept" if p >= TH["E7"]["high"] else ("down-weight" if p >= TH["E7"]["low"] else "reject")
                    if d2 > CHI2_THRESHOLD_ALPHA_005:
                        decision = "reject"
                else:
                    # REACQUIRE: tutarlilik cezasi askida -> goruntu-only kalibre model
                    p = float(m_vis.predict_proba([feats])[0])
                    # aday kapisi kasitli olarak gevsek (E6 'low', VAL risk<=0.35);
                    # guvenlik k-fix teyidinden gelir (M9). E6 'high' VAL'de
                    # fix'lerin %0.1'ini gecirdigi icin adayi neredeyse hic
                    # olusturmuyordu (VAL Senaryo A: k=2 hic kurtaramadi).
                    decision = "candidate" if p >= TH["E6"]["low"] else "reject"
                    # Senaryo B: gate'i GECEN ilk adayin konumu, ayni (guvenli)
                    # ozelliklerle 150 m kaydirilmis yanlis bir konumla degistirilir
                    # -> kendine-benzer bolgeden gelen guvenli-ama-yanlis fix.
                    if args.scenario == "B" and decision == "candidate" and not S["b_injected"]:
                        fix = np.array([gx, gy]) + false_shift
                        fix_err = float(np.hypot(*false_shift))
                        S["b_injected"] = True

            if not reacq:
                if decision in ("accept", "down-weight"):
                    S["streak"] = 0
                    pol.correct(fix, r_nom if decision == "accept" else r_nom * 4, gx, gy)
                else:
                    S["streak"] += 1
                    if v.startswith("reacq") and S["streak"] >= N_REJECT_FOR_REACQ:
                        S["mode"] = "REACQUIRE"
                        S["pending"] = []
                        S["last_dr_pos"] = None
                continue

            # REACQUIRE modu
            k_needed = 1 if v == "reacq_k1" else 2
            dr_pos = pol.sim.current_prior()[0]  # dead-reckoned (duzeltilmemis) konum
            if decision != "candidate":
                S["pending"] = []
                continue
            if S["pending"]:
                last_fix, last_dr = S["pending"][-1]
                expected = last_fix + (dr_pos - last_dr)
                if np.hypot(*(fix - expected)) > TAU_M:
                    S["pending"] = [(fix, dr_pos)]
                    continue
            S["pending"].append((fix, dr_pos))
            if len(S["pending"]) >= k_needed:
                # kabul: kovaryansi sisirip son fix'e tam guvenerek guncelle
                if fix_err is not None and fix_err > RECOVERED_M:
                    S["false_accepts"] += 1
                pol.sim.set_cov((R_MAX / 3) ** 2)
                pol.correct(fix, r_nom, gx, gy)
                S["mode"] = "NORMAL"
                S["streak"] = 0
                S["pending"] = []

    tag = f"{args.sequence}_{args.scenario}_{args.drift}_inj{args.inject_m:g}_s{args.seed}"
    print(f"{tag}")
    print(f"{'varyant':11s} {'kurtarma_s':>10s} {'yanlis_kabul':>12s} {'reacq_sure_s':>12s} {'RMSE_sonra':>10s} {'final':>8s}")
    os.makedirs(os.path.dirname(args.summary_out), exist_ok=True)
    i_inj = int(np.searchsorted(ts, args.t_inject))
    with open(args.summary_out, "a") as fs:
        for v, pol in pols.items():
            e = np.array(pol.errors[i_inj:])
            row = dict(tag=tag, sequence=args.sequence, scenario=args.scenario, seed=args.seed, variant=v,
                       recovery_s=st[v]["recovered_t"], false_accepts=st[v]["false_accepts"],
                       reacquire_time_s=st[v]["reacq_time"], rmse_after=float(np.sqrt(np.mean(e ** 2))),
                       final=float(e[-1]))
            fs.write(json.dumps(row) + "\n")
            rec = "yok" if row["recovery_s"] is None else f"{row['recovery_s']:.0f}"
            print(f"{v:11s} {rec:>10s} {row['false_accepts']:12d} {row['reacquire_time_s']:12.0f} "
                  f"{row['rmse_after']:10.1f} {row['final']:8.1f}")


if __name__ == "__main__":
    main()
