"""Kapali-dongu icin v2 model paketi: her (havuz, etiket) icin model + esikler (OOF, risk 0.20 / 0.35)
+ olcum gurultusu R (havuzda o etikete gore 'guvenli' fix'lerin hata kovaryansi). TEST kullanilmaz."""
import pickle
import numpy as np
from sklearn.model_selection import GroupKFold
import mixed_training as MT

pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
from fix_record import load_records
recs = {k: [r for p in v for r in load_records(p)] for k, v in MT.POOLS.items()}
out = {}
for name, use, ykey in (("M10", ["aerialvl", "anyvisloc", "visloc"], "y10"), ("M25", ["aerialvl", "anyvisloc", "visloc"], "y25"),
                        ("A25", ["aerialvl"], "y25")):
    pool = MT.cat([pools[k] for k in use])
    oof = np.zeros(len(pool[ykey]))
    for tr, va in GroupKFold(n_splits=5).split(pool["rows"], pool[ykey], pool["grp"]):
        m = MT.new_model().fit([pool["rows"][i] for i in tr], pool[ykey][tr])
        oof[va] = m.predict_proba([pool["rows"][i] for i in va])
    th = {"high": MT.pick(oof, pool[ykey], pool["hf"], 0.20), "low": MT.pick(oof, pool[ykey], pool["hf"], 0.35)}
    model = MT.new_model().fit(pool["rows"], pool[ykey])
    lim = 10.0 if ykey == "y10" else 25.0
    xy = np.array([[r.predicted_fix_x_m, r.predicted_fix_y_m] for k in use for r in recs[k]
                   if r.predicted_fix_x_m is not None and r.fix_error_m <= lim])
    R = np.cov(xy.T)
    out[name] = dict(model=model, th=th, R=R, label=ykey, pools=use)
    print(name, "esik", {k: round(v, 3) for k, v in th.items()}, "R diag", np.diag(R).round(1))
pickle.dump(out, open("../outputs/reliability_v2_bundle.pkl", "wb"))
