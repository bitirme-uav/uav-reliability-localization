"""VPAIR = 4. gorulmemis alan. Dondurulmus AerialVL modeli ve karisik (3 veri seti) model;
egitim esigi ve etiketsiz uyum (online_adapt). Tasarim mixed_training/online_adapt ile ayni."""
import json, pickle, sys
import numpy as np
from sklearn.metrics import roc_auc_score
import mixed_training as MT
import online_adapt as OA

O = "../outputs/"
DS = sys.argv[1] if len(sys.argv) > 1 else "vpair"          # vpair | alto
t = OA.with_order(MT.load([O + f"{DS}_fixes_test.jsonl"], DS), [O + f"{DS}_fixes_test.jsonl"])
e = np.array([r["fix_error_m"] for r in t["rows"]]); m = np.isin([r["magnitude_idx"] for r in t["rows"]], (0, 30))
print(f"{DS} TEST lokalizer (prior 0/30 m): median={np.median(e[m]):.1f} m <=10m={np.mean(e[m]<=10)*100:.0f}% "
      f"<=25m={np.mean(e[m]<=25)*100:.0f}% >100/yok={np.mean(e[m]>100)*100:.0f}%  | tum kayitlarda guvenli oran {t['y10'].mean()*100:.1f}%")
raw = np.array([r["raw_confidence"] or 0 for r in t["rows"]])
print(f"ham skor AUROC={roc_auc_score(t['y10'], raw):.3f}")
b = pickle.load(open(O + "calibration_models.pkl", "rb"))
frozen = b["models"]["cal_vis+Mahal (gbm)"]; th_f = json.load(open(O + "thresholds.json"))["E7"]["high"]
pi_f = float(MT.load([O + "fixes_train.jsonl"], "aerialvl")["y10"].mean())
pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
pool = MT.cat(list(pools.values())); mixed, th_m, _ = MT.train_with_oof_threshold(pool); pi_m = float(pool["y10"].mean())
out = {}
for name, (mod, th, pi) in {"DONMUS (AerialVL)": (frozen, th_f, pi_f), "KARISIK (3 veri seti)": (mixed, th_m, pi_m)}.items():
    p = mod.predict_proba(t["rows"]); r0 = MT.evaluate(p, t, th)
    print(f"\n{name}: AUROC={r0['auroc']:.3f} AUROC25={r0['auroc25']:.3f} ECE={r0['ece']:.3f}")
    out[name] = {"metrics": r0}
    for mode in ("GLOBAL", "OTO-TOPLU", "OTO-CEVRIMICI"):
        acc = OA.decide(p, t, th, pi, mode); s = OA.summarize(acc, t); out[name][mode] = s
        print(f"   {mode:14s} kabul={s['coverage']:.3f} risk={s['risk']:.3f}")
json.dump(out, open(O + f"{DS}_eval_summary.json", "w"), indent=2, default=float)
