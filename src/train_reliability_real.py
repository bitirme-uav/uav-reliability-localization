"""Gercek Faz E FixRecord verisiyle kalibre guvenilirlik modelini egit
ve raw confidence + chi-square ile karsilastir.

NOT (dogruluk icin belirtilmeli): Bu ilk deneme icin sequence-bazli
train/val/test ayrimi (dokuman kurali, SS9.1) HENUZ uygulanmadi --
rastgele split kullanildi. Bu, ayni sekanstan gelen benzer orneklerin
hem train hem test'te bulunmasina izin verdigi icin performansi
OLDUGUNDAN IYI gosterebilir (optimistic bias). Gercek/nihai
degerlendirme icin sequence-disjoint split ZORUNLU.
"""
import sys

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, ".")
from fix_record import load_records
from reliability_model import ReliabilityModel, expected_calibration_error
from sklearn.metrics import brier_score_loss

recs = load_records("../outputs/phase_e_fixrecords.jsonl")
label_attr = "safe_secondary"  # primary (%0.6) cok seyrek, secondary (%4.9) ile basliyoruz
y = np.array([1 if getattr(r, label_attr) else 0 for r in recs])
rows = [r.to_dict() for r in recs]

print(f"toplam={len(recs)} pozitif={y.sum()} ({100*y.mean():.1f}%)")

idx = np.arange(len(recs))
idx_train, idx_test = train_test_split(idx, test_size=0.3, random_state=0, stratify=y)
rows_train = [rows[i] for i in idx_train]
rows_test = [rows[i] for i in idx_test]
y_train, y_test = y[idx_train], y[idx_test]

model = ReliabilityModel(calibration="isotonic")
model.fit(rows_train, y_train)
metrics = model.evaluate(rows_test, y_test)
print(f"\nKalibre model (rastgele split, n_test={metrics.n}):")
print(f"  AUROC={metrics.auroc:.3f} AUPRC={metrics.auprc:.3f} Brier={metrics.brier:.3f} ECE={metrics.ece:.3f}")

# ham inlier_ratio ile karsilastirma
raw = np.array([r["inlier_ratio"] if r["inlier_ratio"] is not None else 0.0 for r in rows_test])
print(f"\nHam inlier_ratio (kalibrasyonsuz):")
print(f"  Brier={brier_score_loss(y_test, raw):.3f} ECE={expected_calibration_error(y_test, raw):.3f}")

# chi-square gate'in ayni test setinde ne kadar isabetli oldugunu da olcelim
# (basit: chi2_d2 varsa onu kullan, yoksa atla -- bu run'da chi2_d2 loglanmadi,
# TODO: sonraki toplama turunda chi2_d2'yi de FixRecord'a yaz)
