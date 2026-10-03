"""RQ1/RQ2 TEST degerlendirmesi: DONDURULMUS modeller ve esiklerle
(outputs/calibration_models.pkl, outputs/thresholds.json) yeniden egitim
YAPMADAN fixes_test.jsonl uzerinde metrikler. Config freeze sonrasi bir kez.
"""
import json
import pickle
import sys

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from fix_record import load_records
from reliability_model import expected_calibration_error, risk_coverage_curve

split = sys.argv[1] if len(sys.argv) > 1 else "test"
recs = load_records(f"../outputs/fixes_{split}.jsonl")
bundle = pickle.load(open("../outputs/calibration_models.pkl", "rb"))
TH = json.load(open("../outputs/thresholds.json"))
models, R_nominal = bundle["models"], bundle["R_nominal"]
y = np.array([1 if r.safe_primary else 0 for r in recs])
has_fix = np.array([r.predicted_fix_x_m is not None for r in recs])
print(f"{split.upper()} n={len(recs)} (fix'li {has_fix.sum()}) safe={y.mean()*100:.1f}%")


def chi2_d2(r):
    if r.predicted_fix_x_m is None:
        return 1e9
    nu = np.array([r.predicted_fix_x_m - r.prior_x_m, r.predicted_fix_y_m - r.prior_y_m])
    S = np.array([[r.prior_cov_xx, r.prior_cov_xy], [r.prior_cov_xy, r.prior_cov_yy]]) + R_nominal
    return float(nu @ np.linalg.inv(S) @ nu)


rows = [r.to_dict() for r in recs]
scores = {
    "raw (inlier_ratio)": ("E3", np.array([r.raw_confidence or 0.0 for r in recs])),
    "heuristic (SatLoc-tarzi)": ("E4", np.array([r.heuristic_confidence or 0.0 for r in recs])),
    "chi2 (p-degeri)": (None, np.array([np.exp(-chi2_d2(r) / 2) for r in recs])),
}
for name, m in models.items():
    gate = {"cal_visual (logreg)": "E6", "cal_vis+Mahal (gbm)": "E7"}.get(name)
    scores[name] = (gate, m.predict_proba(rows))

print(f"\n{'yontem':26s} {'AUROC':>6s} {'AUPRC':>6s} {'Brier':>6s} {'ECE':>6s} {'risk@25%':>9s}"
      f" {'esik:kabul':>10s} {'esik:risk':>9s}")
summary = {}
for name, (gate, s) in scores.items():
    _, risk = risk_coverage_curve(y, s)
    row = dict(auroc=roc_auc_score(y, s), auprc=average_precision_score(y, s),
               brier=brier_score_loss(y, np.clip(s, 0, 1)), ece=expected_calibration_error(y, np.clip(s, 0, 1)),
               risk25=float(risk[int(0.25 * len(s)) - 1]))
    # dondurulmus HIGH esiginin test'teki gercek kapsami ve riski
    acc_cov = acc_risk = float("nan")
    if gate is not None and np.isfinite(TH[gate]["high"]):
        acc = (s >= TH[gate]["high"]) & has_fix
        acc_cov = float(acc.mean())
        acc_risk = float(1 - y[acc].mean()) if acc.any() else float("nan")
    row.update(frozen_high_coverage=acc_cov, frozen_high_risk=acc_risk)
    summary[name] = row
    print(f"{name:26s} {row['auroc']:6.3f} {row['auprc']:6.3f} {row['brier']:6.3f} {row['ece']:6.3f} "
          f"{row['risk25']:9.3f} {acc_cov:10.3f} {acc_risk:9.3f}")
print(f"(taban oran: unsafe = {1-y.mean():.3f}; VAL'de secilen hedef risk = {TH['_meta']['risk_high']})")
json.dump(summary, open(f"../outputs/calibration_summary_{split}.json", "w"), indent=2)
