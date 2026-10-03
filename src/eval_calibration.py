"""RQ1/RQ2: Guven sinyalleri fix dogrulugunu ne kadar iyi tahmin ediyor,
kalibrasyon ham skorlara ve heuristic'e gore fayda sagliyor mu?

TRAIN fix kayitlarinda egit, VAL'de degerlendir (TEST'e dokunulmaz).
Etiket: safe_primary (fix_error <= 10m, M3). Yontemler (M5):
  1. raw:        inlier_ratio
  2. heuristic:  SatLoc-tarzi C_score (GSD terimi yok -- irtifa turetilemiyor)
  3. chi2:       chi-square tutarlilik skoru exp(-d2/2) = 2-DOF p-degeri
  4. cal_visual: kalibre model, sadece goruntu ozellikleri
  5. cal_vis+M:  kalibre model, goruntu + Mahalanobis
Cikti: AUROC, AUPRC, Brier, ECE, risk@coverage, ve kalibre modeller pickle.
"""
import json
import pickle

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from fix_record import load_records
from reliability_model import (VISUAL_FEATURES, VISUAL_PLUS_MAHALANOBIS, ReliabilityModel,
                               expected_calibration_error, risk_coverage_curve)

train = load_records("../outputs/fixes_train.jsonl")
val = load_records("../outputs/fixes_val.jsonl")
y_tr = np.array([1 if r.safe_primary else 0 for r in train])
y_va = np.array([1 if r.safe_primary else 0 for r in val])
print(f"TRAIN n={len(train)} safe={y_tr.mean()*100:.1f}%   VAL n={len(val)} safe={y_va.mean()*100:.1f}%")

# R_nominal (M8): TRAIN'de primary-safe fix'lerin hata kovaryansi
safe_err = np.array([[r.predicted_fix_x_m, r.predicted_fix_y_m] for r in train
                     if r.safe_primary and r.predicted_fix_x_m is not None])
R_nominal = np.cov(safe_err.T)
print(f"R_nominal (TRAIN safe fix'lerden): sigma_e={np.sqrt(R_nominal[0,0]):.2f}m sigma_n={np.sqrt(R_nominal[1,1]):.2f}m")


def chi2_d2(r) -> float:
    if r.predicted_fix_x_m is None:
        return 1e9
    nu = np.array([r.predicted_fix_x_m - r.prior_x_m, r.predicted_fix_y_m - r.prior_y_m])
    S = np.array([[r.prior_cov_xx, r.prior_cov_xy], [r.prior_cov_xy, r.prior_cov_yy]]) + R_nominal
    return float(nu @ np.linalg.inv(S) @ nu)


def nz(v):
    return 0.0 if v is None else float(v)


scores = {
    "raw (inlier_ratio)": np.array([nz(r.raw_confidence) for r in val]),
    "heuristic (SatLoc-tarzi)": np.array([nz(r.heuristic_confidence) for r in val]),
    "chi2 (p-degeri)": np.array([np.exp(-chi2_d2(r) / 2) for r in val]),
}
rows_tr = [r.to_dict() for r in train]
rows_va = [r.to_dict() for r in val]
models = {}
for name, feats, base in (("cal_visual (logreg)", VISUAL_FEATURES, "logreg"),
                          ("cal_vis+Mahal (logreg)", VISUAL_PLUS_MAHALANOBIS, "logreg"),
                          ("cal_visual (gbm)", VISUAL_FEATURES, "gbm"),
                          ("cal_vis+Mahal (gbm)", VISUAL_PLUS_MAHALANOBIS, "gbm")):
    m = ReliabilityModel(features=feats, calibration="isotonic", base=base).fit(rows_tr, y_tr)
    models[name] = m
    scores[name] = m.predict_proba(rows_va)

print(f"\n{'yontem':26s} {'AUROC':>6s} {'AUPRC':>6s} {'Brier':>6s} {'ECE':>6s} {'risk@25%':>9s} {'risk@50%':>9s}")
summary = {}
for name, s in scores.items():
    cov, risk = risk_coverage_curve(y_va, s)
    r25 = risk[int(0.25 * len(s)) - 1]
    r50 = risk[int(0.50 * len(s)) - 1]
    row = dict(auroc=roc_auc_score(y_va, s), auprc=average_precision_score(y_va, s),
               brier=brier_score_loss(y_va, np.clip(s, 0, 1)), ece=expected_calibration_error(y_va, np.clip(s, 0, 1)),
               risk25=r25, risk50=r50)
    summary[name] = row
    print(f"{name:26s} {row['auroc']:6.3f} {row['auprc']:6.3f} {row['brier']:6.3f} {row['ece']:6.3f} "
          f"{row['risk25']:9.3f} {row['risk50']:9.3f}")
print(f"(taban oran: VAL'de unsafe orani = {1-y_va.mean():.3f}; risk = kabul edilenler icinde unsafe orani)")

with open("../outputs/calibration_models.pkl", "wb") as f:
    pickle.dump({"models": models, "R_nominal": R_nominal}, f)
with open("../outputs/calibration_summary_val.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nkaydedildi: outputs/calibration_models.pkl, outputs/calibration_summary_val.json")
