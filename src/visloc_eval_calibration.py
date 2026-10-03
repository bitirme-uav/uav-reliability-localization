"""E12 / RQ6 benzeri: kalibrasyon transferi AerialVL -> UAV-VisLoc (farkli
sehirler, farkli kamera/irtifa, farkli yil/mevsim haritalari).

  A) DONDURULMUS: AerialVL'de egitilen model + VAL'de secilen esikler, hic
     degistirilmeden UAV-VisLoc TEST ucuslarina
  B) YENIDEN KALIBRASYON: ayni dondurulmus skor; sadece monoton kalibrasyon
     katmani (isotonic) ve esikler RECAL ucuslarinda yeniden uydurulur
  C) YENIDEN EGITIM (referans): ayni ozellik seti, model RECAL'de bastan egitilir
Etiket: fix_error <= 10 m. Esik kurali AerialVL ile ayni (risk <= 0.20).
"""
import json
import pickle
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from fix_record import load_records
from reliability_model import VISUAL_PLUS_MAHALANOBIS, ReliabilityModel, expected_calibration_error

RISK = 0.20
DS = sys.argv[1] if len(sys.argv) > 1 else "visloc"          # visloc | anyvisloc
recal = load_records(f"../outputs/{DS}_fixes_recal.jsonl")
test = load_records(f"../outputs/{DS}_fixes_test.jsonl")
aer = load_records("../outputs/fixes_test.jsonl")
bundle = pickle.load(open("../outputs/calibration_models.pkl", "rb"))
TH = json.load(open("../outputs/thresholds.json"))
M = bundle["models"]
R_aer = bundle["R_nominal"]


def lab(rs):
    return np.array([1 if r.safe_primary else 0 for r in rs])


def has(rs):
    return np.array([r.predicted_fix_x_m is not None for r in rs])


def chi2p(rs, R):
    out = []
    for r in rs:
        if r.predicted_fix_x_m is None:
            out.append(0.0); continue
        nu = np.array([r.predicted_fix_x_m - r.prior_x_m, r.predicted_fix_y_m - r.prior_y_m])
        S = np.diag([r.prior_cov_xx, r.prior_cov_yy]) + R
        out.append(float(np.exp(-(nu @ np.linalg.inv(S) @ nu) / 2)))
    return np.array(out)


def pick(s, y, hf, risk):
    s, y = s[hf], y[hf]
    o = np.argsort(-s)
    rk = 1 - np.cumsum(y[o]) / np.arange(1, len(o) + 1)
    ok = np.where(rk <= risk)[0]
    return float("inf") if len(ok) == 0 else float(s[o][ok.max()])


def at_threshold(s, y, hf, th):
    acc = (s >= th) & hf
    return float(acc.mean()), (float(1 - y[acc].mean()) if acc.any() else float("nan"))


y_r, y_t, hf_r, hf_t = lab(recal), lab(test), has(recal), has(test)
rows_r, rows_t = [r.to_dict() for r in recal], [r.to_dict() for r in test]
print(f"AerialVL TEST : n={len(aer)} safe={lab(aer).mean()*100:.1f}%")
print(f"{DS} RECAL  : n={len(recal)} safe={y_r.mean()*100:.1f}%  fix'li={hf_r.mean()*100:.0f}%")
print(f"{DS} TEST   : n={len(test)} safe={y_t.mean()*100:.1f}%  fix'li={hf_t.mean()*100:.0f}%")
for nm, rs in (("RECAL", recal), ("TEST", test)):
    e = np.array([r.fix_error_m for r in rs if r.magnitude_idx in (0, 30)])
    print(f"  lokalizer ({nm}, prior 0/30 m): median={np.median(e):.1f}m <=10m={np.mean(e<=10)*100:.0f}% <=25m={np.mean(e<=25)*100:.0f}% fix-yok/>100m={np.mean(e>100)*100:.0f}%")

safe_r = np.array([[r.predicted_fix_x_m, r.predicted_fix_y_m] for r in recal if r.safe_primary and r.predicted_fix_x_m is not None])
R_vis = np.cov(safe_r.T) if len(safe_r) > 5 else R_aer

methods = {
    "ham skor":          (np.array([r.raw_confidence or 0 for r in recal]), np.array([r.raw_confidence or 0 for r in test]), "E3"),
    "SatLoc-tarzi":      (np.array([r.heuristic_confidence or 0 for r in recal]), np.array([r.heuristic_confidence or 0 for r in test]), "E4"),
    "chi-square":        (chi2p(recal, R_vis), chi2p(test, R_vis), None),
    "kal. goruntu-only": (M["cal_visual (logreg)"].predict_proba(rows_r), M["cal_visual (logreg)"].predict_proba(rows_t), "E6"),
    "kal. gor.+Mahal.":  (M["cal_vis+Mahal (gbm)"].predict_proba(rows_r), M["cal_vis+Mahal (gbm)"].predict_proba(rows_t), "E7"),
}
summary = {}
print(f"\n{'yontem':18s} {'AUROC':>6s} {'AUPRC':>6s} | {'DONDURULMUS: ECE':>16s} {'kabul':>6s} {'risk':>6s} | "
      f"{'YENIDEN KAL.: ECE':>17s} {'kabul':>6s} {'risk':>6s}")
for nm, (sr, st, gate) in methods.items():
    auroc, auprc = roc_auc_score(y_t, st), average_precision_score(y_t, st)
    # A) dondurulmus
    ece_a = expected_calibration_error(y_t, np.clip(st, 0, 1))
    th_a = TH[gate]["high"] if gate and np.isfinite(TH[gate]["high"]) else float("inf")
    cov_a, risk_a = at_threshold(st, y_t, hf_t, th_a)
    # B) yeniden kalibrasyon (isotonic RECAL'de) + esik RECAL'de
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(sr, y_r)
    cr, ct = iso.predict(sr), iso.predict(st)
    ece_b = expected_calibration_error(y_t, ct)
    cov_b, risk_b = at_threshold(ct, y_t, hf_t, pick(cr, y_r, hf_r, RISK))
    summary[nm] = dict(auroc=auroc, auprc=auprc, frozen=dict(ece=ece_a, coverage=cov_a, risk=risk_a),
                       recal=dict(ece=ece_b, brier=brier_score_loss(y_t, ct), coverage=cov_b, risk=risk_b))
    print(f"{nm:18s} {auroc:6.3f} {auprc:6.3f} | {ece_a:16.3f} {cov_a:6.3f} {risk_a:6.3f} | {ece_b:17.3f} {cov_b:6.3f} {risk_b:6.3f}")

# C) referans: RECAL'de bastan egitim
m_c = ReliabilityModel(features=VISUAL_PLUS_MAHALANOBIS, calibration="isotonic", base="gbm").fit(rows_r, y_r)
pr, pt = m_c.predict_proba(rows_r), m_c.predict_proba(rows_t)
cov_c, risk_c = at_threshold(pt, y_t, hf_t, pick(pr, y_r, hf_r, RISK))
summary["yeniden egitim (gbm, RECAL)"] = dict(auroc=roc_auc_score(y_t, pt), auprc=average_precision_score(y_t, pt),
                                              recal=dict(ece=expected_calibration_error(y_t, pt), coverage=cov_c, risk=risk_c))
print(f"{'yeniden egitim':18s} {roc_auc_score(y_t, pt):6.3f} {average_precision_score(y_t, pt):6.3f} | {'':16s} {'':6s} {'':6s} | "
      f"{expected_calibration_error(y_t, pt):17.3f} {cov_c:6.3f} {risk_c:6.3f}")
print(f"(kabul = TEST kayitlarinda kabul orani; risk = kabul edilenlerde >10 m orani; hedef {RISK})")
json.dump(summary, open(f"../outputs/{DS}_calibration_summary.json", "w"), indent=2, default=float)
pickle.dump({"R_vis": R_vis}, open(f"../outputs/{DS}_recal_bundle.pkl", "wb"))
