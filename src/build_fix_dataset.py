"""M7 'fixed offset grid' tarzinda ACIK-DONGU fix-record veri seti.

Her query icin birkac (gercek prior ofseti, filtrenin varsaydigi sigma_pos)
kosulu denenir; arama yaricapi M7 kuraliyla r = clip(3*sigma_pos, 60, 400).
Bazi kosullarda gercek ofset yaricapi asar (in_window=False) -- filtre
kovaryansinin yanlis-belirtildigi, sahte fix uretmeye en yatkin durumlar.

Acik-dongu: kabul/red kararlari sonraki aramalari ETKILEMEZ, bu yuzden
esik/kalibrasyon secimi icin dogru veri (dun gece kapali-dongude yapilan
esik denemelerinin yaniltici oldugu goruldu).

Ucus yonu (boresight duzeltmesi) icin +-W kare hizi kullanilir --
calisma anindaki navigasyon hizi tahminine vekil.

TEST sekanslari bu scriptle URETILMEZ (config freeze sonrasi ayri).
"""
import argparse
import random
import time

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from boresight import correct_fix_enu
from fix_record import FixRecord, FixRecordWriter, label_fix
from gates import heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from splits import TEST_SEQUENCES, TRAIN_SEQUENCES, VAL_SEQUENCES

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
W = 4
R_MIN, R_MAX = 60.0, 400.0
# (gercek prior ofseti m, filtrenin varsaydigi sigma_pos m)
CONDITIONS = ((0, 20), (30, 20), (80, 40), (80, 20), (200, 80), (200, 20), (300, 140))

ap = argparse.ArgumentParser()
ap.add_argument("--split", required=True, choices=["train", "val", "test"])
ap.add_argument("--n", type=int, default=200)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--allow-test", action="store_true", help="SADECE config freeze sonrasi")
args = ap.parse_args()
if args.split == "test" and not args.allow_test:
    raise SystemExit("TEST sekanslari config freeze'den once islenmez (SS9.1). --allow-test ile acikca onayla.")
seqs = {"train": TRAIN_SEQUENCES, "val": VAL_SEQUENCES, "test": TEST_SEQUENCES}[args.split]

val = AerialVLVal(VAL_ROOT)
items = []
for name in seqs:
    fr = val.sequences[name]
    for i in range(W, len(fr) - W):
        if val.map_for(fr[i].lon, fr[i].lat) is not None:
            items.append((name, fr, i))
rng_py = random.Random(1000 + args.seed)
sample = rng_py.sample(items, min(args.n, len(items)))
rng = np.random.default_rng(1000 + args.seed)

pipe = LocalizationPipeline()
out = f"../outputs/fixes_{args.split}.jsonl"
open(out, "w").close()
writer = FixRecordWriter(out)
t_start = time.monotonic()
for k, (name, fr, i) in enumerate(sample):
    q, a, b = fr[i], fr[i - W], fr[i + W]
    ve, vn = lonlat_to_enu_m(b.lon, b.lat, a.lon, a.lat)
    img = cv2.imread(str(q.path))
    geo_map = val.map_for(q.lon, q.lat)
    for ci, (offset, sigma) in enumerate(CONDITIONS):
        th = rng.uniform(0, 2 * np.pi)
        px, py = offset * np.cos(th), offset * np.sin(th)
        radius = float(np.clip(3 * sigma, R_MIN, R_MAX))
        plon, plat = enu_to_lonlat_m(px, py, q.lon, q.lat)
        r = pipe.localize(img, MapExtractor(geo_map), plon, plat, radius)

        rec = FixRecord(
            run_id=f"openloop_{args.split}", policy_id="none", seed=args.seed,
            sequence_id=name, query_id=q.path.stem, timestamp_s=q.utc_ts / 1000.0,
            magnitude_idx=offset, direction_idx=ci,
            ground_truth_x_m=0.0, ground_truth_y_m=0.0,
            prior_x_m=px, prior_y_m=py, prior_cov_xx=sigma ** 2, prior_cov_yy=sigma ** 2,
            true_offset_m=float(offset), search_window_m=radius, in_window=offset <= radius,
            num_matches=r.num_matches, inlier_count=r.inlier_count, inlier_ratio=r.inlier_ratio,
            reprojection_error_px=r.reprojection_error_px,
            inlier_spatial_spread=r.inlier_spatial_spread, transform_condition=r.transform_condition,
            query_ref_scale_ratio=r.query_ref_scale_ratio,
            top1_score=float(r.inlier_count), top1_top2_margin=r.top1_top2_margin,
            raw_confidence=r.raw_confidence,
            localization_latency_ms=r.localization_latency_ms,
        )
        if r.predicted_lon is not None:
            fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
            fe, fn = correct_fix_enu(fe, fn, ve, vn)
            rec.predicted_fix_x_m, rec.predicted_fix_y_m = fe, fn
            rec.fix_error_m = float(np.hypot(fe, fn))
            rec.mahalanobis_d = float(np.hypot(fe - px, fn - py) / sigma)
            if r.top1_top2_margin is not None:
                rec.heuristic_confidence = heuristic_confidence(r.inlier_count, r.top1_top2_margin, None)
        else:
            rec.fix_error_m = 1e6  # fix yok -> kesinlikle unsafe
        label_fix(rec)
        writer.write(rec)
    if (k + 1) % 25 == 0:
        print(f"  {k+1}/{len(sample)} query  ({time.monotonic()-t_start:.0f}s)", flush=True)
writer.close()
print(f"yazildi: {out}")
