"""Tanidik-olmayan-bolge (OOD) tespiti + temkinli mod. Tasarim SONUCLARA BAKMADAN sabitlendi (2026-10-04).
Etiket KULLANMAZ (yalniz guvenilirlik modelinin girdi ozellikleri):
  - Ucus skoru = ucustaki fix'lerin ozellik vektorlerinin egitim havuzu dagilimina ortalama
    Mahalanobis uzakligi (Ledoit-Wolf kovaryans, standart olceklenmis ozellikler).
  - 'Tanidik' siniri: havuzdaki her ucus/sahne, havuzun geri kalanina gore skorlanir (birini-disarida-birak);
    sinir = bu skorlarin en buyugu (havuzda hic OOD alarmi olmasin).
  - Temkinli mod: OOD ucusta esik, havuzun OOF tahminlerinde risk <= 0.05 olacak sekilde secilen esik.
Modeller ve etiketler reliability_v2 ile ayni (AerialVL-yalniz / KARISIK; y10 / y25).
Cikti: outputs/ood_gate_summary.json"""
import json

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.model_selection import GroupKFold

import mixed_training as MT
from reliability_v2 import POOLSETS, TESTS
from reliability_model import ReliabilityModel, VISUAL_PLUS_MAHALANOBIS

O = "../outputs/"
FE = ReliabilityModel(features=VISUAL_PLUS_MAHALANOBIS)


def X(rows, hf):
    x = FE._to_matrix(rows)[hf]
    return np.sign(x) * np.log1p(np.abs(x))


class Familiarity:
    def __init__(self, Xp):
        self.mu, self.sd = Xp.mean(0), Xp.std(0) + 1e-6
        self.lw = LedoitWolf().fit((Xp - self.mu) / self.sd)

    def score(self, Xq):
        z = (Xq - self.mu) / self.sd
        return float(np.sqrt(np.maximum(self.lw.mahalanobis(z), 0)).mean())


def oof(pool, ykey):
    p = np.zeros(len(pool[ykey]))
    for tr, va in GroupKFold(n_splits=5).split(pool["rows"], pool[ykey], pool["grp"]):
        m = MT.new_model().fit([pool["rows"][i] for i in tr], pool[ykey][tr])
        p[va] = m.predict_proba([pool["rows"][i] for i in va])
    return p


if __name__ == "__main__":
    pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
    tests = {k: MT.load([v], k) for k, v in TESTS.items()}
    out = {}
    print(f"{'havuz':16s} {'etiket':5s} {'test':10s} {'OOD ucus':>9s} | {'NORMAL kabul/risk/enkotu':>26s} | {'OOD-KAPILI kabul/risk/enkotu':>30s}")
    for pname, use in POOLSETS.items():
        pool = MT.cat([pools[k] for k in use])
        Xp_all = X(pool["rows"], np.ones(len(pool["rows"]), bool)); hfp = pool["hf"]
        # tanidik siniri: birini-disarida-birak, havuz ucuslari
        lim = 0.0
        for g in np.unique(pool["grp"]):
            m = pool["grp"] == g
            if (m & hfp).sum() < 10:
                continue
            lim = max(lim, Familiarity(Xp_all[~m & hfp]).score(Xp_all[m & hfp]))
        fam = Familiarity(Xp_all[hfp])
        for ykey in ("y10", "y25"):
            p_oof = oof(pool, ykey)
            th_n = MT.pick(p_oof, pool[ykey], hfp, 0.20); th_c = MT.pick(p_oof, pool[ykey], hfp, 0.05)
            model = MT.new_model().fit(pool["rows"], pool[ykey])
            for k, t in tests.items():
                p = model.predict_proba(t["rows"]); y = t[ykey]
                accN = (p >= th_n) & t["hf"]; accG = accN.copy(); n_ood = 0; groups = np.unique(t["grp"])
                Xt = X(t["rows"], np.ones(len(t["rows"]), bool))
                for g in groups:
                    m = (t["grp"] == g) & t["hf"]
                    if m.sum() >= 10 and fam.score(Xt[m]) > lim:
                        n_ood += 1
                        gm = t["grp"] == g
                        accG[gm] = (p[gm] >= th_c) & t["hf"][gm]

                def summ(acc):
                    per = [1 - y[(t["grp"] == g) & acc].mean() for g in groups if ((t["grp"] == g) & acc).sum() >= 5]
                    return (float(acc.mean()), float(1 - y[acc].mean()) if acc.any() else float("nan"),
                            float(max(per)) if per else float("nan"))
                n, gk = summ(accN), summ(accG)
                out.setdefault(pname, {}).setdefault(ykey, {})[k] = dict(ood_flights=n_ood, n_flights=len(groups),
                                                                        normal=n, gated=gk, limit=lim)
                print(f"{pname:16s} {ykey:5s} {k:10s} {n_ood:>4d}/{len(groups):<4d} | {n[0]:7.3f} {n[1]:7.3f} {n[2]:7.3f}    | "
                      f"{gk[0]:7.3f} {gk[1]:7.3f} {gk[2]:7.3f}", flush=True)
    json.dump(out, open(O + "ood_gate_summary.json", "w"), indent=2, default=float)
