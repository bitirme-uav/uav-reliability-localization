"""Acik-dongu esik secimi: E2_accept_all kayitlari (esikten ETKILENMEYEN,
cunku E2 hicbir zaman reddetmiyor -- prior yorungesi esik secimine
bagli degil) uzerinde risk-coverage egrisinden kalibre modelin
ACCEPT esigini prensipli sekilde sec."""
import pickle
import sys

import numpy as np

sys.path.insert(0, ".")
from fix_record import load_records
from reliability_model import risk_coverage_curve

HELD_OUT_SEQUENCE = "2023-03-18-12-18-25"

recs = load_records("../outputs/phase_e_fixrecords.jsonl")
# SADECE E2_accept_all (esikten bagimsiz, "acik-dongu" localization denemeleri)
# VE held-out sekans HARIC (model bu sekansi hic gormedi, esik secimi de
# gormemeli -- ayni ayrimi koru).
e2_recs = [r for r in recs if r.policy_id == "E2_accept_all" and r.sequence_id != HELD_OUT_SEQUENCE]
print(f"acik-dongu (E2) kayit sayisi (held-out haric): {len(e2_recs)}")

with open("../outputs/reliability_model.pkl", "rb") as f:
    model = pickle.load(f)

rows = [r.to_dict() for r in e2_recs]
y = np.array([1 if r.safe_secondary else 0 for r in e2_recs])
probs = model.predict_proba(rows)

coverage, risk = risk_coverage_curve(y, probs)
order = np.argsort(-probs)
probs_sorted = probs[order]

print(f"\n{'coverage':>10s} {'risk':>8s} {'esik(prob)':>12s}")
for frac in (0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30):
    idx = int(frac * len(y)) - 1
    idx = max(0, min(idx, len(y) - 1))
    print(f"{coverage[idx]:10.3f} {risk[idx]:8.3f} {probs_sorted[idx]:12.5f}")

# Basit kural: risk <= 0.5 olan (yani kabul edilenlerin yarisindan azi
# unsafe) EN YUKSEK coverage'i veren esigi sec (M9/M10 ruhuna uygun,
# "az ama guvenilir kabul" tercih edilir).
target_risk = 0.5
best_idx = None
for i in range(len(risk)):
    if risk[i] <= target_risk:
        best_idx = i
if best_idx is not None:
    print(f"\nOnerilen esik (risk<={target_risk}): prob>={probs_sorted[best_idx]:.5f} "
          f"(coverage={coverage[best_idx]:.3f}, risk={risk[best_idx]:.3f})")
else:
    print("\nHicbir esikte risk<=%.2f saglanamadi -- model bu veri setinde yetersiz ayrim gucune sahip." % target_risk)
