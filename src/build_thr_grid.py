"""Esik izgarasi (kapali-dongu esik secimi icin). M10 (3 havuz) ve M10A (4 havuz) modelleri ayni;
'high' esik OOF'ta kabulde risk <= RH olacak sekilde, 'low' = risk <= RH+0.15. Paket: reliability_v2_bundle.pkl'e
'M10_r15'...'M10A_r40' adlariyla eklenir. TEST kullanilmaz."""
import pickle
import numpy as np
from sklearn.model_selection import GroupKFold
import mixed_training as MT
b = pickle.load(open("../outputs/reliability_v2_bundle.pkl", "rb"))
P3 = dict(MT.POOLS); P4 = dict(MT.POOLS); P4["alto"] = ["../outputs/alto_fixes_trainpool.jsonl"]
for base, P in (("M10", P3), ("M10A", P4)):
    pool = MT.cat([MT.load(v, k) for k, v in P.items()])
    oof = np.zeros(len(pool["y10"]))
    for tr, va in GroupKFold(n_splits=5).split(pool["rows"], pool["y10"], pool["grp"]):
        m = MT.new_model().fit([pool["rows"][i] for i in tr], pool["y10"][tr]); oof[va] = m.predict_proba([pool["rows"][i] for i in va])
    for rh in (0.15, 0.20, 0.25, 0.30, 0.40):
        th = {"high": MT.pick(oof, pool["y10"], pool["hf"], rh), "low": MT.pick(oof, pool["y10"], pool["hf"], min(rh + 0.15, 0.60))}
        name = f"{base}_r{int(rh*100)}"
        b[name] = dict(model=b[base]["model"], th=th, R=b[base]["R"], label="y10", pools=list(P))
        print(name, {k: round(v, 3) for k, v in th.items()})
pickle.dump(b, open("../outputs/reliability_v2_bundle.pkl", "wb"))
