"""Ay-1 çıkış kriteri: 'bir query -> metrik fix çalışıyor'.

Rastgele bir query karesi seçer, GERÇEK ground-truth konumunun etrafına
(sentetik, bilinen bir offset ile) bir 'prior' yerleştirir, prior-merkezli
arama bölgesinde LocalizationPipeline ile fix üretir, fix_error_m'i
ground truth ile karşılaştırır ve tam bir FixRecord basar.

Bu adımda GERÇEK bir navigasyon/drift senaryosu simüle edilmiyor
(o M6/Faz E) -- yalnızca "tek query -> tek metrik fix" uçtan uca
çalışıyor mu diye TEK BİR örnek üzerinde doğrulama yapılıyor.
"""
from __future__ import annotations

import argparse
import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from fix_record import FixRecord, label_fix
from geo_utils import lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("val_root")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prior-offset-m", type=float, default=30.0,
                     help="sentetik prior hatasi (metre) -- gercek drift simulatoru degil, tek-ornek testi")
    ap.add_argument("--search-radius-m", type=float, default=150.0)
    args = ap.parse_args()

    val = AerialVLVal(args.val_root)
    print(val.summary())

    rng = random.Random(args.seed)
    candidates = [f for f in val.all_frames() if val.map_for(f.lon, f.lat) is not None]
    if not candidates:
        print("HATA: haritasi bulunan hic query yok", file=sys.stderr)
        sys.exit(1)
    query = rng.choice(candidates)
    geo_map = val.map_for(query.lon, query.lat)
    print(f"\nSeçilen query: {query.path.name} (sekans {query.sequence})")
    print(f"Ground truth: lon={query.lon:.6f} lat={query.lat:.6f}")
    print(f"Kullanılacak harita: {geo_map.name}")

    # sentetik prior: ground truth'a rastgele yonde sabit bir offset ekle
    np_rng = np.random.default_rng(args.seed)
    theta = np_rng.uniform(0, 2 * np.pi)
    d_east = args.prior_offset_m * np.cos(theta)
    d_north = args.prior_offset_m * np.sin(theta)
    from geo_utils import enu_to_lonlat_m
    prior_lon, prior_lat = enu_to_lonlat_m(d_east, d_north, query.lon, query.lat)
    print(f"Sentetik prior (gerçek+{args.prior_offset_m}m offset): lon={prior_lon:.6f} lat={prior_lat:.6f}")

    query_img = cv2.imread(str(query.path))
    if query_img is None:
        print(f"HATA: query görüntüsü okunamadı: {query.path}", file=sys.stderr)
        sys.exit(1)

    map_extractor = MapExtractor(geo_map)
    pipeline = LocalizationPipeline()

    print(f"\nLokalizasyon çalıştırılıyor (arama yarıçapı={args.search_radius_m}m)...")
    result = pipeline.localize(query_img, map_extractor, prior_lon, prior_lat, args.search_radius_m)

    err = fix_error_m(result.predicted_lon, result.predicted_lat, query.lon, query.lat)

    rec = FixRecord(
        run_id="month1_demo", policy_id="none", seed=args.seed,
        sequence_id=query.sequence, query_id=query.path.stem,
        prior_x_m=0.0, prior_y_m=0.0,  # origin=query gt burada, basitlik icin
        true_offset_m=args.prior_offset_m,
        search_window_m=args.search_radius_m,
        predicted_fix_x_m=None, predicted_fix_y_m=None,
        raw_confidence=result.raw_confidence,
        fix_error_m=err,
        num_matches=result.num_matches, inlier_count=result.inlier_count,
        inlier_ratio=result.inlier_ratio, reprojection_error_px=result.reprojection_error_px,
        inlier_spatial_spread=result.inlier_spatial_spread,
        transform_condition=result.transform_condition,
        localization_latency_ms=result.localization_latency_ms,
    )
    label_fix(rec)

    print("\n=== SONUÇ (FixRecord) ===")
    for k, v in rec.to_dict().items():
        if v is not None:
            print(f"  {k}: {v}")

    if err is None:
        print("\n>>> FIX ÜRETİLEMEDİ (yetersiz eşleşme/RANSAC başarısız) <<<")
    else:
        verdict = "SAFE (<=10m)" if rec.safe_primary else ("secondary-safe (<=25m)" if rec.safe_secondary else "UNSAFE")
        print(f"\n>>> fix_error={err:.2f}m -> {verdict} <<<")


if __name__ == "__main__":
    main()
