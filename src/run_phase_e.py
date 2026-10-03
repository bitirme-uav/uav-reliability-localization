"""Faz E: M6 (drift) + M2 (gerçek localization) + M8 (chi-square/raw gate)
BİRLEŞTİRİLMİŞ, tek bir AerialVL sekansı üzerinde çalışan navigasyon
simülatörü.

Akış (dokümanın Faz E girdi/çıktı tanımına uygun):
    ground-truth trajectory (AerialVL sekansı, ts sıralı kareler)
      -> DriftSimulator.step() HER karede (prior sürekli güncellenir)
      -> call_interval_s'te bir: GERÇEK LocalizationPipeline.localize()
         (o anki kareyi query, prior'u arama merkezi olarak kullanarak)
      -> birden fazla POLİTİKA aynı fix'i değerlendirir (E1/E2/E3/E5 --
         drift-only, accept-all, raw-score gate, chi-square gate):
         her politika kendi prior'unu AYRI tutar (aynı sürüklenme,
         aynı fix'ler, farklı kabul/red kararları)
      -> kabul edilirse DriftSimulator.apply_correction()

Çıktı: her politika için trajectory RMSE + zararlı-düzeltme sayısı.
Bu, dokümanın M10/E1-E9 karşılaştırmasının KÜÇÜK ÖLÇEKLİ, tek-sekanslık,
henüz KALİBRE EDİLMEMİŞ (ham/chi-square gate'e sınırlı) bir ön-versiyonu.
"""
from __future__ import annotations

import argparse
import sys
import time

import pickle

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal, Frame
from drift_simulator import DriftSimulator, FilterNoiseConfig, REGIME_PRESETS
from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import Decision, ReliabilityPolicy, chi_square_gate
from geo_utils import lonlat_to_enu_m, enu_to_lonlat_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m


class PolicyState:
    """Bir politikanin (accept-all/raw-gate/chi-square) kendi bagimsiz
    prior/drift durumu -- ayni gercek fix'leri degerlendirir ama farkli
    kabul/red kararlari verip farkli sonuc trajektorileri uretir."""

    def __init__(self, name: str, drift_cfg, filter_cfg: FilterNoiseConfig, r_nominal: np.ndarray):
        self.name = name
        self.sim = DriftSimulator(drift_cfg, filter_cfg)
        self.r_nominal = r_nominal
        self.errors: list[float] = []      # |prior - ground_truth| her ADIMDA (M10 trajectory error)
        self.harmful_corrections = 0       # kabul sonrasi hata ARTTIYSA sayilir
        self.n_accepted = 0
        self.n_rejected = 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("val_root")
    ap.add_argument("--sequence", default=None, help="varsayilan: en kisa sekans")
    ap.add_argument("--call-interval-s", type=float, default=5.0)
    ap.add_argument("--max-frames", type=int, default=200, help="hiz icin sekansi kirp")
    ap.add_argument("--r-min-m", type=float, default=60.0, help="M7 dinamik arama yaricapi alt siniri")
    ap.add_argument("--r-max-m", type=float, default=400.0, help="M7 dinamik arama yaricapi ust siniri")
    ap.add_argument("--drift-regime", default="moderate", choices=list(REGIME_PRESETS.keys()))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="../outputs/phase_e_fixrecords.jsonl")
    ap.add_argument("--r-nominal-sigma-m", type=float, default=None,
                     help="chi-square gate icin R_nominal std (m); varsayilan=search_radius/2 (yer tutucu, gercek validation-split hatasindan tahmin edilmeli, M8 kurali)")
    ap.add_argument("--reliability-model", default=None,
                     help="train_and_save_model.py ile kaydedilmis pickle -- verilirse E7_calibrated politikasi eklenir")
    args = ap.parse_args()

    calibrated_model = None
    if args.reliability_model:
        with open(args.reliability_model, "rb") as f:
            calibrated_model = pickle.load(f)
        print(f"Kalibre model yuklendi: {args.reliability_model}")

    val = AerialVLVal(args.val_root)
    if args.sequence is None:
        args.sequence = min(val.sequences, key=lambda k: len(val.sequences[k]))
    frames: list[Frame] = val.sequences[args.sequence][: args.max_frames]
    print(f"Sekans: {args.sequence} ({len(frames)} kare, call_interval={args.call_interval_s}s, "
          f"drift={args.drift_regime}, arama_yaricapi=[{args.r_min_m},{args.r_max_m}]m (dinamik, M7))")

    # ground truth -> ENU metre (sekansin ilk karesi origin)
    origin_lon, origin_lat = frames[0].lon, frames[0].lat
    t0_ms = frames[0].utc_ts
    gt_xy = [lonlat_to_enu_m(f.lon, f.lat, origin_lon, origin_lat) for f in frames]
    gt_t = [(f.utc_ts - t0_ms) / 1000.0 for f in frames]

    drift_cfg = REGIME_PRESETS[args.drift_regime]
    drift_cfg = type(drift_cfg)(**{**drift_cfg.__dict__, "seed": args.seed})
    filter_cfg = FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=drift_cfg.random_walk_sigma_m_per_sqrt_s)
    # R_nominal: bu erken asamada validation-split hata istatistigi henuz
    # yok (M2 tuning devam ediyor) -- yer tutucu olarak arama yaricapinin
    # bir fonksiyonu kullaniliyor (TODO: gercek validation-split hatasindan
    # tahmin et, M8 kurali).
    r_nominal_sigma_m = args.r_nominal_sigma_m if args.r_nominal_sigma_m is not None else args.r_min_m / 2
    r_nominal = np.array([[r_nominal_sigma_m ** 2, 0.0], [0.0, r_nominal_sigma_m ** 2]])

    policies = {
        "E1_drift_only": PolicyState("E1_drift_only", drift_cfg, filter_cfg, r_nominal),
        "E2_accept_all": PolicyState("E2_accept_all", drift_cfg, filter_cfg, r_nominal),
        "E3_raw_score_gate": PolicyState("E3_raw_score_gate", drift_cfg, filter_cfg, r_nominal),
        "E5_chi_square_gate": PolicyState("E5_chi_square_gate", drift_cfg, filter_cfg, r_nominal),
    }
    if calibrated_model is not None:
        policies["E7_calibrated"] = PolicyState("E7_calibrated", drift_cfg, filter_cfg, r_nominal)
    raw_policy = ReliabilityPolicy(high_threshold=0.50, low_threshold=0.35)  # inlier_ratio dogrudan "reliability" gibi kullanilir (gecici)
    # ESIK NOTU: model isotonic kalibrasyonlu, yani P(safe) GERCEKTEN dusuk
    # taban oranini (%4.9 pozitif) yansitiyor -- en iyi fix'ler bile ~0.05-0.10
    # civarinda cikiyor (bkz. PROGRESS_RAPORU.md canli inceleme). Esikler
    # 0.5/0.3 GIBI "olagan" degerler yerine bu gercekci araliga gore
    # ayarlandi. TODO: production'da validation-split ROC/risk-coverage
    # egrisinden sistematik sec, elle ayarlama degil.
    # NOT (onemli metodolojik bulgu, PROGRESS_RAPORU.md'de ayrintili):
    # esik degisimi KAPALI DONGU davranisini degistiriyor (bir esikle
    # kabul edilen fix bir sonraki prior'u degistirir, bu da SONRAKI
    # cagrilarin arama merkezini/sonuclarini degistirir) -- yani "sabit
    # 25 ornek uzerinde grid-search" YANILTICI, her esik farkli bir
    # yorungeye yol aciyor. Dogru yontem: esigi SADECE acik-dongu
    # (dondurulmus prior'larla, M7 tile-cache) validation verisinde sec,
    # sonra kapali-dongu test et (M9.1 configuration freeze kurali tam
    # da bunun icin var). Simdilik EN GUVENLI/MUHAFAZAKAR secim
    # (yuksek esik -> supheli durumda reddet) kullaniliyor.
    calibrated_policy = ReliabilityPolicy(high_threshold=0.5, low_threshold=0.3)

    pipeline = LocalizationPipeline()
    writer = FixRecordWriter(args.out)

    last_call_t = -1e9
    n_calls = 0
    t_start = time.monotonic()
    for i, (frame, (gx, gy), gt) in enumerate(zip(frames, gt_xy, gt_t)):
        do_call = (gt - last_call_t) >= args.call_interval_s

        last_sample = {}
        for pname, pol in policies.items():
            last_sample[pname] = pol.sim.step(gt, gx, gy)
            pol.errors.append(last_sample[pname].true_offset_m)

        if not do_call:
            continue
        last_call_t = gt
        n_calls += 1

        query_img = cv2.imread(str(frame.path))
        if query_img is None:
            continue
        geo_map = val.map_for(frame.lon, frame.lat)
        if geo_map is None:
            continue

        # ONEMLI DUZELTME: her politika KENDI suruklenmis prior'undan arama
        # yapar (TEK ORTAK prior kullanmak -- ozellikle en kotu politikanin
        # priorunu digerlerine de dayatmak -- canli testte E3/E5'i haksiz
        # yere kotulestirdigi tespit edildi, bkz. PROGRESS_RAPORU.md).
        # Bu N-kat (politika sayisi kadar) daha yavas ama dogru.
        map_extractor = MapExtractor(geo_map)

        for pname, pol in policies.items():
            if pname == "E1_drift_only":
                continue  # hic localize/duzeltme yapilmaz, sadece drift birikir

            s = last_sample[pname]
            prior_lon, prior_lat = enu_to_lonlat_m(s.prior_x_m, s.prior_y_m, origin_lon, origin_lat)
            # M7 kurali: arama yaricapi sabit DEGIL, prior'un o anki
            # belirsizligine (sigma_pos) gore buyur -- r = clip(3*sigma_pos, r_min, r_max).
            sigma_pos = np.sqrt(s.prior_cov_xx)
            dynamic_radius = float(np.clip(3.0 * sigma_pos, args.r_min_m, args.r_max_m))

            try:
                result = pipeline.localize(query_img, map_extractor, prior_lon, prior_lat, dynamic_radius)
            except Exception as e:
                print(f"  [{i}] {pname} localize hatasi: {e}", file=sys.stderr)
                pol.n_rejected += 1
                continue

            err = fix_error_m(result.predicted_lon, result.predicted_lat, frame.lon, frame.lat)
            fix_xy = None
            mahalanobis_d = None
            if result.predicted_lon is not None:
                fix_xy = np.array(lonlat_to_enu_m(result.predicted_lon, result.predicted_lat, origin_lon, origin_lat))
                prior_xy_m4 = np.array([s.prior_x_m, s.prior_y_m])
                prior_cov_m4 = np.array([[s.prior_cov_xx, s.prior_cov_xy], [s.prior_cov_xy, s.prior_cov_yy]])
                try:
                    nu = fix_xy - prior_xy_m4
                    mahalanobis_d = float(np.sqrt(max(nu.T @ np.linalg.inv(prior_cov_m4) @ nu, 0.0)))
                except np.linalg.LinAlgError:
                    mahalanobis_d = None

            rec = FixRecord(
                run_id="phase_e", policy_id=pname, seed=args.seed, drift_regime=args.drift_regime,
                sequence_id=args.sequence, query_id=frame.path.stem, timestamp_s=gt,
                search_window_m=dynamic_radius, fix_error_m=err,
                num_matches=result.num_matches, inlier_count=result.inlier_count,
                inlier_ratio=result.inlier_ratio, reprojection_error_px=result.reprojection_error_px,
                inlier_spatial_spread=result.inlier_spatial_spread,
                transform_condition=result.transform_condition,
                query_ref_scale_ratio=None if result.query_ref_scale_ratio is None else float(result.query_ref_scale_ratio),
                mahalanobis_d=mahalanobis_d,
                raw_confidence=result.raw_confidence,
            )
            label_fix(rec)
            writer.write(rec)

            if pname == "E2_accept_all":
                print(f"  [{i:4d}] t={gt:7.1f}s call#{n_calls} matches={result.num_matches:3d} "
                      f"inliers={result.inlier_count:3d} fix_err={err if err is not None else float('nan'):7.1f}m "
                      f"safe={rec.safe_primary}")

            if fix_xy is None:
                pol.n_rejected += 1
                continue
            if pname == "E2_accept_all":
                decision = Decision.ACCEPT
            elif pname == "E3_raw_score_gate":
                decision = raw_policy.decide(result.raw_confidence)
            elif pname == "E5_chi_square_gate":
                prior_xy = np.array([s.prior_x_m, s.prior_y_m])
                prior_cov = np.array([[s.prior_cov_xx, s.prior_cov_xy], [s.prior_cov_xy, s.prior_cov_yy]])
                chi = chi_square_gate(prior_xy, prior_cov, fix_xy, r_nominal)
                decision = Decision.REJECT if chi.reject else Decision.ACCEPT
            elif pname == "E7_calibrated":
                reliability = float(calibrated_model.predict_proba([rec.to_dict()])[0])
                decision = calibrated_policy.decide(reliability)
            else:
                decision = Decision.REJECT

            if decision in (Decision.ACCEPT, Decision.DOWNWEIGHT):
                err_before = pol.errors[-1]
                pol.sim.apply_correction(fix_xy[0], fix_xy[1], float(np.trace(r_nominal) / 2))
                err_after = float(np.linalg.norm(np.array([gx, gy]) - fix_xy))
                if err_after > err_before:
                    pol.harmful_corrections += 1
                pol.n_accepted += 1
            else:
                pol.n_rejected += 1

    writer.close()
    dt_wall = time.monotonic() - t_start
    print(f"\n=== {n_calls} localization cagrisi, {dt_wall:.1f}s surdu ({dt_wall/max(n_calls,1):.2f}s/cagri) ===")
    print(f"{'Politika':22s} {'RMSE(m)':>10s} {'final(m)':>10s} {'max(m)':>10s} {'kabul':>6s} {'red':>6s} {'zararli':>8s}")
    for pname, pol in policies.items():
        errs = np.array(pol.errors)
        rmse = float(np.sqrt(np.mean(errs ** 2)))
        print(f"{pname:22s} {rmse:10.2f} {errs[-1]:10.2f} {errs.max():10.2f} "
              f"{pol.n_accepted:6d} {pol.n_rejected:6d} {pol.harmful_corrections:8d}")


if __name__ == "__main__":
    main()
