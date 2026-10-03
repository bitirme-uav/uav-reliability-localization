"""Guvenilirlik v2: ikincil etiket (<= 25 m, PDF M3'te onceden tanimli) ile egitim ve 5 alanda olcum.
Tasarim SONUCLARA BAKMADAN sabitlendi (2026-10-04):
  Etiketler: y10 (birincil) ve y25 (ikincil). Her etiket icin ayri model + ayri esik.
  Modeller : DONMUS-tarif (yalniz AerialVL havuzu) ve KARISIK (AerialVL + AnyVisLoc RECAL + UAV-VisLoc RECAL).
             Ayni ozellikler / GBM + isotonic. Esik: havuzda gruplu 5-kat OOF, kabulde risk <= 0.20.
  TEST     : AerialVL, AnyVisLoc, UAV-VisLoc (veri seti haritasi), VPAIR, ALTO.
             VPAIR ve ALTO hicbir havuzda yok (gorulmemis alan).
  Raporlanan: AUROC, kabul orani, kabulde risk (o etikete gore), ucus/sahne basina en kotu risk.
Cikti: outputs/reliability_v2_summary.json
"""
import json

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

import mixed_training as MT

O = "../outputs/"
RISK = 0.20
TESTS = {"aerialvl": O + "fixes_test.jsonl", "anyvisloc": O + "anyvisloc_fixes_test.jsonl",
         "visloc": O + "visloc_fixes_test.jsonl", "vpair": O + "vpair_fixes_test.jsonl",
         "alto": O + "alto_fixes_test.jsonl"}
POOLSETS = {"AerialVL-yalniz": ["aerialvl"], "KARISIK": ["aerialvl", "anyvisloc", "visloc"]}


def oof_fit(pool, ykey):
    oof = np.zeros(len(pool[ykey]))
    for tr, va in GroupKFold(n_splits=5).split(pool["rows"], pool[ykey], pool["grp"]):
        m = MT.new_model().fit([pool["rows"][i] for i in tr], pool[ykey][tr])
        oof[va] = m.predict_proba([pool["rows"][i] for i in va])
    th = MT.pick(oof, pool[ykey], pool["hf"], RISK)
    return MT.new_model().fit(pool["rows"], pool[ykey]), th


def evaluate(p, t, th, ykey):
    y = t[ykey]; acc = (p >= th) & t["hf"]
    per = [1 - y[(t["grp"] == g) & acc].mean() for g in np.unique(t["grp"]) if ((t["grp"] == g) & acc).sum() >= 5]
    return dict(auroc=float(roc_auc_score(y, p)), coverage=float(acc.mean()),
                risk=float(1 - y[acc].mean()) if acc.any() else float("nan"), base=float(y.mean()),
                worst=float(max(per)) if per else float("nan"))


if __name__ == "__main__":
    pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
    tests = {k: MT.load([v], k) for k, v in TESTS.items()}
    out = {}
    print(f"{'havuz':16s} {'etiket':6s} {'test':10s} {'AUROC':>6s} {'kabul':>6s} {'risk':>6s} {'en kotu':>8s} (taban)")
    for pname, use in POOLSETS.items():
        pool = MT.cat([pools[k] for k in use])
        for ykey in ("y10", "y25"):
            model, th = oof_fit(pool, ykey)
            for k, t in tests.items():
                r = evaluate(model.predict_proba(t["rows"]), t, th, ykey)
                out.setdefault(pname, {}).setdefault(ykey, {})[k] = r
                unseen = "" if k in use else "  <- gorulmemis"
                print(f"{pname:16s} {ykey:6s} {k:10s} {r['auroc']:6.3f} {r['coverage']:6.3f} {r['risk']:6.3f} {r['worst']:8.3f} ({r['base']:.2f}){unseen}", flush=True)
    json.dump(out, open(O + "reliability_v2_summary.json", "w"), indent=2, default=float)
