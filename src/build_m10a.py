"""M10A: M10 tarifi, havuza ALTO Train eklenmis (4 veri seti). reliability_v2_bundle.pkl'e eklenir."""
import pickle
import numpy as np
from sklearn.model_selection import GroupKFold
import mixed_training as MT
from fix_record import load_records
P = dict(MT.POOLS); P["alto"] = ["../outputs/alto_fixes_trainpool.jsonl"]
pool = MT.cat([MT.load(v, k) for k, v in P.items()])
oof = np.zeros(len(pool["y10"]))
for tr, va in GroupKFold(n_splits=5).split(pool["rows"], pool["y10"], pool["grp"]):
    m = MT.new_model().fit([pool["rows"][i] for i in tr], pool["y10"][tr]); oof[va] = m.predict_proba([pool["rows"][i] for i in va])
th = {"high": MT.pick(oof, pool["y10"], pool["hf"], 0.20), "low": MT.pick(oof, pool["y10"], pool["hf"], 0.35)}
model = MT.new_model().fit(pool["rows"], pool["y10"])
xy = np.array([[r.predicted_fix_x_m, r.predicted_fix_y_m] for v in P.values() for p in v for r in load_records(p)
               if r.predicted_fix_x_m is not None and r.fix_error_m <= 10])
b = pickle.load(open("../outputs/reliability_v2_bundle.pkl", "rb"))
b["M10A"] = dict(model=model, th=th, R=np.cov(xy.T), label="y10", pools=list(P))
pickle.dump(b, open("../outputs/reliability_v2_bundle.pkl", "wb"))
print("M10A esik", {k: round(v, 3) for k, v in th.items()}, "R", np.diag(np.cov(xy.T)).round(1))
