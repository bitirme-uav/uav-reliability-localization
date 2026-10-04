"""Karisik havuza ALTO Train eklemenin etkisi (y10 / y25). Tarif reliability_v2 ile ayni.
Havuzlar: KARISIK-3 (AerialVL+AnyVisLoc+UAV-VisLoc) vs KARISIK-4 (+ALTO Train, 522 kare).
TEST: 5 kume; ALTO Val TEST artik 'ayni platform, farkli ucus', VPAIR hala gorulmemis."""
import json
import mixed_training as MT
import reliability_v2 as RV
pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
pools["alto"] = MT.load(["../outputs/alto_fixes_trainpool.jsonl"], "alto")
tests = {k: MT.load([v], k) for k, v in RV.TESTS.items()}
out = {}
for name, use in (("KARISIK-3", ["aerialvl", "anyvisloc", "visloc"]), ("KARISIK-4", ["aerialvl", "anyvisloc", "visloc", "alto"])):
    pool = MT.cat([pools[k] for k in use])
    for ykey in ("y10", "y25"):
        model, th = RV.oof_fit(pool, ykey)
        for k, t in tests.items():
            r = RV.evaluate(model.predict_proba(t["rows"]), t, th, ykey)
            out.setdefault(name, {}).setdefault(ykey, {})[k] = r
            print(f"{name:10s} {ykey} {k:10s} AUROC {r['auroc']:.3f} kabul {r['coverage']:.3f} risk {r['risk']:.3f} enkotu {r['worst']:.3f}", flush=True)
json.dump(out, open("../outputs/mixed4_summary.json", "w"), indent=2, default=float)
