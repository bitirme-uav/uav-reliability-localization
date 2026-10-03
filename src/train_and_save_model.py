"""Bir sekansi TAMAMEN disarida birakarak (sequence-disjoint, dokuman
kurali SS9.1) modeli egitir ve pickle olarak kaydeder -- run_phase_e.py
E7 politikasi bunu yukleyip GERCEK navigasyon dongusunde test edebilsin
diye."""
import pickle
import sys

import numpy as np

sys.path.insert(0, ".")
from fix_record import load_records
from reliability_model import ReliabilityModel

HELD_OUT_SEQUENCE = sys.argv[1] if len(sys.argv) > 1 else "2023-03-18-12-18-25"
LABEL_ATTR = "safe_secondary"

recs = load_records("../outputs/phase_e_fixrecords.jsonl")
train_recs = [r for r in recs if r.sequence_id != HELD_OUT_SEQUENCE]
print(f"egitim: {len(train_recs)} kayit ({HELD_OUT_SEQUENCE} HARIC tutuldu)")

y = np.array([1 if getattr(r, LABEL_ATTR) else 0 for r in train_recs])
rows = [r.to_dict() for r in train_recs]
print(f"pozitif oran: {y.mean()*100:.1f}%")

model = ReliabilityModel(calibration="isotonic")
model.fit(rows, y)

with open("../outputs/reliability_model.pkl", "wb") as f:
    pickle.dump(model, f)
print("kaydedildi: outputs/reliability_model.pkl")
