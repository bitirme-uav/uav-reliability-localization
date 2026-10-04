"""§19: SuperPoint vs XFeat, eslestirilmis (ayni kare / prior / yaricap) karsilastirma.
  1) Lokalizer: 5 TEST + havuzlar, <=10/<=25/>100 m ve sure.
  2) Guvenilirlik: reliability_v2 tarifi (AerialVL-yalniz / KARISIK; y10 / y25) HER eslestiricinin
     kendi kayitlariyla yeniden egitilir; 5 TEST'te AUROC / kabul / risk.
AnyVisLoc tabani: v2_superpoint (guncel kodla yeniden oynatilmis; XFeat ile ayni kod)."""
import json
import os

import numpy as np

import mixed_training as MT
import reliability_v2 as RV
from fix_record import load_records

O = "../outputs/"
FILES_POOL = {"aerialvl": ["fixes_train.jsonl", "fixes_val.jsonl"], "anyvisloc": ["anyvisloc_fixes_recal.jsonl"],
              "visloc": ["visloc_fixes_recal.jsonl"]}
FILES_TEST = {"aerialvl": "fixes_test.jsonl", "anyvisloc": "anyvisloc_fixes_test.jsonl", "visloc": "visloc_fixes_test.jsonl",
              "vpair": "vpair_fixes_test.jsonl", "alto": "alto_fixes_test.jsonl"}


def path(matcher, fname):
    if matcher == "xfeat":
        return O + "v2_xfeat/" + fname
    if fname.startswith("anyvisloc_") and os.path.exists(O + "v2_superpoint/" + fname + ".done"):
        return O + "v2_superpoint/" + fname
    return O + fname


if __name__ == "__main__":
    out = {"lokalizer": {}, "guvenilirlik": {}}
    print("== 1) Lokalizer (tum kosullar | prior 0/30 m) ==")
    for ds, f in list(FILES_TEST.items()) + [(k + "-havuz", v) for k, vs in FILES_POOL.items() for v in vs]:
        for m in ("superpoint", "xfeat"):
            R = load_records(path(m, f))
            e = np.array([r.fix_error_m for r in R]); e0 = np.array([r.fix_error_m for r in R if r.magnitude_idx in (0, 30)])
            lat = float(np.median([r.localization_latency_ms for r in R if r.localization_latency_ms]))
            d = dict(le10=float(np.mean(e <= 10)), le25=float(np.mean(e <= 25)), gt100=float(np.mean(e > 100)),
                     le10_p030=float(np.mean(e0 <= 10)), le25_p030=float(np.mean(e0 <= 25)), ms=lat)
            out["lokalizer"].setdefault(ds + ":" + f, {})[m] = d
            print(f"{ds:16s} {f:28s} {m:10s} <=10 {d['le10']*100:3.0f}% <=25 {d['le25']*100:3.0f}% >100 {d['gt100']*100:3.0f}% | "
                  f"p0/30 <=10 {d['le10_p030']*100:3.0f}% <=25 {d['le25_p030']*100:3.0f}% | {lat:.0f} ms", flush=True)
    print("\n== 2) Guvenilirlik (her eslestirici kendi kayitlariyla) ==")
    print(f"{'esl.':10s} {'havuz':16s} {'etiket':5s} {'test':10s} {'AUROC':>6s} {'kabul':>6s} {'risk':>6s} {'en kotu':>8s}")
    for m in ("superpoint", "xfeat"):
        pools = {k: MT.load([path(m, f) for f in fs], k) for k, fs in FILES_POOL.items()}
        tests = {k: MT.load([path(m, f)], k) for k, f in FILES_TEST.items()}
        for pname, use in RV.POOLSETS.items():
            pool = MT.cat([pools[k] for k in use])
            for ykey in ("y10", "y25"):
                model, th = RV.oof_fit(pool, ykey)
                for k, t in tests.items():
                    r = RV.evaluate(model.predict_proba(t["rows"]), t, th, ykey)
                    out["guvenilirlik"].setdefault(m, {}).setdefault(pname, {}).setdefault(ykey, {})[k] = r
                    print(f"{m:10s} {pname:16s} {ykey:5s} {k:10s} {r['auroc']:6.3f} {r['coverage']:6.3f} {r['risk']:6.3f} {r['worst']:8.3f}", flush=True)
    json.dump(out, open(O + "xfeat_v2_summary.json", "w"), indent=2, default=float)
