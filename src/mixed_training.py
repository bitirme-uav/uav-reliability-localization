"""Karisik-alan egitimi ve bir-veri-setini-disarida-birak (LODO) deneyi.
Tasarim SONUCLARA BAKMADAN sabitlendi (2026-10-03):

  Havuzlar (egitim icin kullanilabilir; hicbiri TEST degil):
    aerialvl : fixes_train + fixes_val
    anyvisloc: anyvisloc_fixes_recal
    visloc   : visloc_fixes_recal (veri seti haritasi)
  TEST kumeleri (yalniz olcum):
    aerialvl : fixes_test
    anyvisloc: anyvisloc_fixes_test
    visloc   : visloc_fixes_test ve visloc_fixes_test_k1 (K1 harita kurali)

  Model: ayni ozellikler (gorsel + Mahalanobis), GBM + isotonic (dondurulmus modelle ayni tarif).
  Esik: egitim havuzunda sekans/sahne gruplu 5-kat capraz dogrulama (OOF) tahminlerinde,
        kabul edilenlerde risk <= 0.20 (yuksek) kurali -- AerialVL'deki kuralla ayni.
  Deneyler:
    DONMUS : mevcut AerialVL modeli + AerialVL VAL esigi (karsilastirma)
    KARISIK: uc havuzun birlesimi
    LODO-x : x disindaki iki havuz; x'in TEST'inde olc (gorulmemis alan)
Etiket: <= 10 m (birincil); <= 25 m (ikincil) AUROC'u da raporlanir.
Cikti: outputs/mixed_training_summary.json
"""
import json
import pickle

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from fix_record import load_records
from reliability_model import VISUAL_PLUS_MAHALANOBIS, ReliabilityModel, expected_calibration_error

RISK = 0.20
O = "../outputs/"
POOLS = {
    "aerialvl": [O + "fixes_train.jsonl", O + "fixes_val.jsonl"],
    "anyvisloc": [O + "anyvisloc_fixes_recal.jsonl"],
    "visloc": [O + "visloc_fixes_recal.jsonl"],
}
TESTS = {
    "aerialvl": O + "fixes_test.jsonl",
    "anyvisloc": O + "anyvisloc_fixes_test.jsonl",
    "visloc": O + "visloc_fixes_test.jsonl",
    "visloc_k1": O + "visloc_fixes_test_k1.jsonl",
}
TEST_DOMAIN = {"aerialvl": "aerialvl", "anyvisloc": "anyvisloc", "visloc": "visloc", "visloc_k1": "visloc"}


def load(paths, tag):
    recs = [r for p in paths for r in load_records(p)]
    rows = [r.to_dict() for r in recs]
    y10 = np.array([1 if r.safe_primary else 0 for r in recs])
    y25 = np.array([1 if r.safe_secondary else 0 for r in recs])
    hf = np.array([r.predicted_fix_x_m is not None for r in recs])
    grp = np.array([f"{tag}:{r.sequence_id}" for r in recs])
    return dict(rows=rows, y10=y10, y25=y25, hf=hf, grp=grp)


def cat(parts):
    return {k: (sum((p[k] for p in parts), []) if k == "rows" else np.concatenate([p[k] for p in parts])) for k in parts[0]}


def pick(s, y, hf, risk):
    s, y = s[hf], y[hf]
    o = np.argsort(-s)
    rk = 1 - np.cumsum(y[o]) / np.arange(1, len(o) + 1)
    ok = np.where(rk <= risk)[0]
    return float("inf") if len(ok) == 0 else float(s[o][ok.max()])


def new_model():
    return ReliabilityModel(features=VISUAL_PLUS_MAHALANOBIS, calibration="isotonic", base="gbm")


def train_with_oof_threshold(pool):
    oof = np.zeros(len(pool["y10"]))
    gkf = GroupKFold(n_splits=min(5, len(set(pool["grp"]))))
    for tr, va in gkf.split(pool["rows"], pool["y10"], pool["grp"]):
        m = new_model().fit([pool["rows"][i] for i in tr], pool["y10"][tr])
        oof[va] = m.predict_proba([pool["rows"][i] for i in va])
    th = pick(oof, pool["y10"], pool["hf"], RISK)
    model = new_model().fit(pool["rows"], pool["y10"])
    return model, th, oof


def evaluate(p, t, th):
    acc = (p >= th) & t["hf"]
    return dict(auroc=roc_auc_score(t["y10"], p), auprc=average_precision_score(t["y10"], p),
                auroc25=roc_auc_score(t["y25"], p), ece=expected_calibration_error(t["y10"], p),
                coverage=float(acc.mean()), risk=float(1 - t["y10"][acc].mean()) if acc.any() else float("nan"),
                base_safe=float(t["y10"].mean()))


if __name__ == "__main__":
    pools = {k: load(v, k) for k, v in POOLS.items()}
    tests = {k: load([v], TEST_DOMAIN[k]) for k, v in TESTS.items()}
    summary = {}

    bundle = pickle.load(open(O + "calibration_models.pkl", "rb"))
    frozen = bundle["models"]["cal_vis+Mahal (gbm)"]
    th_frozen = json.load(open(O + "thresholds.json"))["E7"]["high"]
    summary["DONMUS (AerialVL)"] = {k: evaluate(frozen.predict_proba(t["rows"]), t, th_frozen) for k, t in tests.items()}

    configs = {"KARISIK (3 veri seti)": list(pools)}
    for held in pools:
        configs[f"LODO: {held} disarida"] = [k for k in pools if k != held]
    for name, use in configs.items():
        model, th, _ = train_with_oof_threshold(cat([pools[k] for k in use]))
        summary[name] = {k: evaluate(model.predict_proba(t["rows"]), t, th) for k, t in tests.items()}
        summary[name]["_threshold"] = th
        summary[name]["_train_pools"] = use
        print(f"{name}: esik={th:.3f}", flush=True)

    print(f"\n{'deney':28s} {'test':10s} {'AUROC':>6s} {'AUROC25':>7s} {'ECE':>6s} {'kabul':>6s} {'risk':>6s}  (guvenli oran)")
    for name, res in summary.items():
        for k, r in res.items():
            if k.startswith("_"):
                continue
            seen = "" if name.startswith("DONMUS") or name.startswith("KARISIK") else \
                   (" <- GORULMEMIS ALAN" if TEST_DOMAIN[k] not in res["_train_pools"] else "")
            print(f"{name:28s} {k:10s} {r['auroc']:6.3f} {r['auroc25']:7.3f} {r['ece']:6.3f} {r['coverage']:6.3f} "
                  f"{r['risk']:6.3f}  ({r['base_safe']:.3f}){seen}")
    # SONRADAN ANALIZ (onceden planlanmadi, raporda ayrica belirtildi): karisik model + alan-bazli esik.
    # Esik, karisik havuzun OOF tahminlerinden YALNIZ ilgili alanin satirlariyla secilir.
    pool = cat([pools[k] for k in pools])
    model, _, oof = train_with_oof_threshold(pool)
    dom = np.array([g.split(":")[0] for g in pool["grp"]])
    post = {}
    print("\nSONRADAN ANALIZ: karisik model + alan-bazli esik")
    for k, t in tests.items():
        m = dom == TEST_DOMAIN[k]
        thd = pick(oof[m], pool["y10"][m], pool["hf"][m], RISK)
        post[k] = evaluate(model.predict_proba(t["rows"]), t, thd); post[k]["_threshold"] = thd
        print(f"  {k:10s} esik={thd:.3f} kabul={post[k]['coverage']:.3f} risk={post[k]['risk']:.3f}")
    summary["SONRADAN: KARISIK + alan-bazli esik"] = post
    json.dump(summary, open(O + "mixed_training_summary.json", "w"), indent=2, default=float)
    print("yazildi: outputs/mixed_training_summary.json")
