"""Tum gate'ler icin AYNI kuralla esik secimi, SADECE VAL acik-dongu
verisinden (SS9.1: esikler validation'da ayarlanir; acik-dongu, cunku
kapali-dongu esik denemesi yaniltici -- 2026-09-30 gecesi bulgusu).

Kural (skor ne olursa olsun ayni):
  high = esik ustundeki fix'lerde unsafe orani <= RISK_HIGH olan EN DUSUK esik
  low  = ayni, RISK_LOW icin
Uncalibrated skorlar (raw, heuristic) ve kalibre olasiliklar ayni risk
hedefleriyle esiklenir -> fark esik seciminden degil skorun ayirt
ediciliginden gelir.

E9 (randomized reference): E7'nin VAL'deki karar dagilimi.
"""
import json
import pickle

import numpy as np

from fix_record import load_records

RISK_HIGH = 0.20
RISK_LOW = 0.35
LABEL = "safe_primary"

val = load_records("../outputs/fixes_val.jsonl")
with open("../outputs/calibration_models.pkl", "rb") as f:
    bundle = pickle.load(f)
models = bundle["models"]
rows = [r.to_dict() for r in val]
has_fix = np.array([r.predicted_fix_x_m is not None for r in val])
y = np.array([1 if getattr(r, LABEL) else 0 for r in val])

scores = {
    "E3": np.array([r.raw_confidence or 0.0 for r in val]),
    "E4": np.array([r.heuristic_confidence or 0.0 for r in val]),
    "E6": models["cal_visual (logreg)"].predict_proba(rows),
    "E7": models["cal_vis+Mahal (gbm)"].predict_proba(rows),
}


def pick(score, risk_target):
    s, yy = score[has_fix], y[has_fix]
    order = np.argsort(-s)
    s_sorted, y_sorted = s[order], yy[order]
    risk = 1.0 - np.cumsum(y_sorted) / np.arange(1, len(y_sorted) + 1)
    ok = np.where(risk <= risk_target)[0]
    if len(ok) == 0:
        return float("inf"), 0.0
    k = ok.max()
    return float(s_sorted[k]), float((k + 1) / len(s))


TH = {}
print(f"VAL n={len(val)} (fix'li {has_fix.sum()}), {LABEL} orani={y[has_fix].mean():.3f}")
print(f"{'gate':5s} {'high':>9s} {'kapsam@high':>12s} {'low':>9s} {'kapsam@low':>11s}")
for g, s in scores.items():
    hi, cov_hi = pick(s, RISK_HIGH)
    lo, cov_lo = pick(s, RISK_LOW)
    lo = min(lo, hi)
    TH[g] = {"high": hi, "low": lo}
    print(f"{g:5s} {hi:9.4f} {cov_hi:12.3f} {lo:9.4f} {cov_lo:11.3f}")

s7 = scores["E7"][has_fix]
dec = np.where(s7 >= TH["E7"]["high"], "accept", np.where(s7 >= TH["E7"]["low"], "down-weight", "reject"))
TH["E9_decision_probs"] = {k: float(np.mean(dec == k)) for k in ("accept", "down-weight", "reject")}
TH["_meta"] = {"risk_high": RISK_HIGH, "risk_low": RISK_LOW, "label": LABEL, "source": "fixes_val.jsonl (acik-dongu)"}
print("E9 karar dagilimi:", TH["E9_decision_probs"])
with open("../outputs/thresholds.json", "w") as f:
    json.dump(TH, f, indent=2)
print("kaydedildi: outputs/thresholds.json")
