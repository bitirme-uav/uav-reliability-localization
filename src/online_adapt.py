"""Etiketsiz bolgeye uyum (oneri 3). Tasarim SONUCLARA BAKMADAN sabitlendi (2026-10-03).

Sorun: Egitimde secilen esik yeni bolgede risk sozunu tutmuyor (taban oran kaymasi).
Yontem (gercek konum / etiket KULLANMAZ, sadece modelin o ucustaki olasiliklari):
  1) EM taban-oran duzeltmesi (Saerens vd. 2002): ucustaki tahminlerden yeni guvenli-oran
     pi' tahmin edilir, olasiliklar p' = w1 p / (w1 p + w0 (1-p)) ile duzeltilir.
  2) Oz-tahmin risk esigi: kabul edilenlerde TAHMINI risk = ort(1 - p') <= 0.20 olacak
     sekilde en genis kabul (kalibre olasiliklarin "kendi riskini soyleme" ozelligi).
Bolge = ucus / sahne (sequence_id). Iki surum:
  OTO-TOPLU     : ucusun tum fix'leri birlikte (transduktif; ucus sonrasi analiz gibi)
  OTO-CEVRIMICI : her kayitta yalniz ONCEKI kayitlar kullanilir; ilk N_MIN kayitta egitim esigi
Karsilastirma: GLOBAL (egitim esigi), OTO-EMSIZ (yalniz oz-tahmin esigi, EM yok),
               ETIKETLI-ALAN (alanin RECAL etiketleriyle esik; etiket gerektirir, referans).
Modeller: DONMUS (AerialVL) ve LODO (test alani egitimde hic yok -> gercek "yeni bolge").
Cikti: outputs/online_adapt_summary.json
"""
import json
import pickle

import numpy as np

import mixed_training as MT

RISK = 0.20
N_MIN = 30
O = "../outputs/"


def em_prior(p, pi_tr, iters=100):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    pi = pi_tr
    for _ in range(iters):
        w1, w0 = pi / pi_tr, (1 - pi) / (1 - pi_tr)
        q = w1 * p / (w1 * p + w0 * (1 - p))
        new = float(q.mean())
        if abs(new - pi) < 1e-6:
            break
        pi = new
    w1, w0 = pi / pi_tr, (1 - pi) / (1 - pi_tr)
    return w1 * p / (w1 * p + w0 * (1 - p)), pi


def self_risk_threshold(q, hf, risk=RISK):
    """Kabulde tahmini risk = ort(1-q) <= risk olan en dusuk esik (etiketsiz)."""
    s = np.sort(q[hf])[::-1]
    if len(s) == 0:
        return float("inf")
    est = np.cumsum(1 - s) / np.arange(1, len(s) + 1)
    ok = np.where(est <= risk)[0]
    return float("inf") if len(ok) == 0 else float(s[ok.max()])


def decide(p, t, th_global, pi_tr, mode):
    """Kayit basina kabul karari (bool). t: test sozlugu (grp, hf, order)."""
    acc = np.zeros(len(p), bool)
    for g in np.unique(t["grp"]):
        idx = np.where(t["grp"] == g)[0]
        idx = idx[np.argsort(t["order"][idx], kind="stable")]
        pg, hg = p[idx], t["hf"][idx]
        if mode == "GLOBAL":
            acc[idx] = (pg >= th_global) & hg
        elif mode == "OTO-EMSIZ":
            acc[idx] = (pg >= self_risk_threshold(pg, hg)) & hg
        elif mode == "OTO-TOPLU":
            q, _ = em_prior(pg, pi_tr)
            acc[idx] = (q >= self_risk_threshold(q, hg)) & hg
        elif mode == "OTO-CEVRIMICI":
            for j in range(len(idx)):
                if not hg[j]:
                    continue
                if j < N_MIN:
                    acc[idx[j]] = pg[j] >= th_global
                    continue
                q, pi = em_prior(pg[:j], pi_tr)
                th = self_risk_threshold(q, hg[:j])
                w1, w0 = pi / pi_tr, (1 - pi) / (1 - pi_tr)
                qj = w1 * pg[j] / (w1 * pg[j] + w0 * (1 - pg[j]))
                acc[idx[j]] = qj >= th
    return acc


def summarize(acc, t):
    y = t["y10"]
    per = []
    for g in np.unique(t["grp"]):
        m = (t["grp"] == g) & acc
        if m.sum() >= 5:
            per.append(1 - y[m].mean())
    return dict(coverage=float(acc.mean()), risk=float(1 - y[acc].mean()) if acc.any() else float("nan"),
                flights_over_30=int(sum(r > 0.30 for r in per)), flights_eval=len(per),
                worst_flight_risk=float(max(per)) if per else float("nan"))


def with_order(t, paths):
    from fix_record import load_records
    recs = [r for p in paths for r in load_records(p)]
    t["order"] = np.array([r.timestamp_s * 10 + (r.direction_idx or 0) for r in recs], float)
    return t


if __name__ == "__main__":
    pools = {k: MT.load(v, k) for k, v in MT.POOLS.items()}
    tests = {k: with_order(MT.load([v], MT.TEST_DOMAIN[k]), [v]) for k, v in MT.TESTS.items()}
    out = {}

    # DONMUS AerialVL modeli
    bundle = pickle.load(open(O + "calibration_models.pkl", "rb"))
    frozen = bundle["models"]["cal_vis+Mahal (gbm)"]
    th_frozen = json.load(open(O + "thresholds.json"))["E7"]["high"]
    pi_frozen = float(MT.load([O + "fixes_train.jsonl"], "aerialvl")["y10"].mean())
    models = {"DONMUS": {k: (frozen, th_frozen, pi_frozen) for k in tests}}

    # LODO: test alani egitimde yok
    lodo = {}
    for held in pools:
        pool = MT.cat([pools[k] for k in pools if k != held])
        m, th, _ = MT.train_with_oof_threshold(pool)
        lodo[held] = (m, th, float(pool["y10"].mean()))
    models["LODO"] = {k: lodo[MT.TEST_DOMAIN[k]] for k in tests}

    # Referans: etiketli alan esigi (alanin kendi RECAL/egitim etiketleri), LODO modeliyle
    print(f"{'model':7s} {'test':10s} {'yontem':14s} {'kabul':>6s} {'risk':>6s} {'>%30 ucus':>10s} {'en kotu ucus':>12s}")
    for mname, per_test in models.items():
        out[mname] = {}
        for k, t in tests.items():
            model, th, pi_tr = per_test[k]
            p = model.predict_proba(t["rows"])
            out[mname][k] = {}
            modes = ["GLOBAL", "OTO-EMSIZ", "OTO-TOPLU", "OTO-CEVRIMICI"]
            for mode in modes:
                acc = decide(p, t, th, pi_tr, mode)
                out[mname][k][mode] = summarize(acc, t)
            dom = MT.TEST_DOMAIN[k]
            pr = pools[dom]
            th_lab = MT.pick(model.predict_proba(pr["rows"]), pr["y10"], pr["hf"], RISK)
            out[mname][k]["ETIKETLI-ALAN"] = summarize((p >= th_lab) & t["hf"], t)
            for mode, r in out[mname][k].items():
                print(f"{mname:7s} {k:10s} {mode:14s} {r['coverage']:6.3f} {r['risk']:6.3f} "
                      f"{r['flights_over_30']:>4d}/{r['flights_eval']:<5d} {r['worst_flight_risk']:12.3f}", flush=True)
    json.dump(out, open(O + "online_adapt_summary.json", "w"), indent=2, default=float)
    print("yazildi: outputs/online_adapt_summary.json")
