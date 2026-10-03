"""Rapor grafikleri. Kullanim: python make_figures.py test   (veya val)
Ciktilar: outputs/figures/<split>_*.png"""
import glob
import json
import os
import pickle
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

from fix_record import load_records

split = sys.argv[1] if len(sys.argv) > 1 else "test"
OUT = "../outputs/figures"
os.makedirs(OUT, exist_ok=True)

# referans palet (dataviz skill, light mod) -- sabit sira, metin notr murekkep
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "lines.linewidth": 2, "legend.frameon": False,
})

FIX = {"visloc": "../outputs/visloc_fixes_test.jsonl", "anyvisloc": "../outputs/anyvisloc_fixes_test.jsonl"}.get(split, f"../outputs/fixes_{split}.jsonl")
SWEEP = {"visloc": "../outputs/sweep_visloc"}.get(split, f"../outputs/sweep_{split}")
LABEL = {"visloc": "UAV-VisLoc TEST", "anyvisloc": "AnyVisLoc TEST"}.get(split, split.upper())
recs = load_records(FIX)
bundle = pickle.load(open("../outputs/calibration_models.pkl", "rb"))
TH = json.load(open("../outputs/thresholds.json"))
R_nominal = bundle["R_nominal"]
y = np.array([1 if r.safe_primary else 0 for r in recs])
rows = [r.to_dict() for r in recs]


def chi2_p(r):
    if r.predicted_fix_x_m is None:
        return 0.0
    nu = np.array([r.predicted_fix_x_m - r.prior_x_m, r.predicted_fix_y_m - r.prior_y_m])
    S = np.array([[r.prior_cov_xx, 0], [0, r.prior_cov_yy]]) + R_nominal
    return float(np.exp(-(nu @ np.linalg.inv(S) @ nu) / 2))


scores = [
    ("Ham skor (inlier orani)", np.array([r.raw_confidence or 0 for r in recs]), C[1]),
    ("SatLoc-tarzi heuristic", np.array([r.heuristic_confidence or 0 for r in recs]), C[3]),
    ("Chi-square p-degeri", np.array([chi2_p(r) for r in recs]), C[4]),
    ("Kalibre: goruntu-only", bundle["models"]["cal_visual (logreg)"].predict_proba(rows), C[2]),
    ("Kalibre: goruntu+Mahalanobis", bundle["models"]["cal_vis+Mahal (gbm)"].predict_proba(rows), C[0]),
]

# --- 1) risk-coverage ---
fig, ax = plt.subplots(figsize=(7, 4.2))
for name, s, col in scores:
    o = np.argsort(-s)
    cov = np.arange(1, len(s) + 1) / len(s)
    risk = 1 - np.cumsum(y[o]) / np.arange(1, len(s) + 1)
    ax.plot(cov, risk, color=col, label=name)
ax.axhline(1 - y.mean(), color=INK2, lw=1, ls=":")
ax.text(1.0, 1 - y.mean() + 0.01, "taban oran (her seyi kabul)", ha="right", va="bottom", color=INK2, fontsize=8)
ax.axhline(TH["_meta"]["risk_high"], color=INK2, lw=1, ls="--")
ax.text(0.01, TH["_meta"]["risk_high"] + 0.01, "hedef risk (VAL'de secildi)", color=INK2, fontsize=8)
ax.set_xlabel("Kapsam: kabul edilen fix orani")
ax.set_ylabel("Risk: kabul edilenlerde >10 m hata orani")
ax.set_xlim(0, 1); ax.set_ylim(0, max(0.65, 1 - y.mean() + 0.08))
ax.set_title(f"Risk-kapsam egrisi ({LABEL}) -- dusuk egri daha iyi", loc="left", color=INK)
ax.legend(loc="lower right", fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}/{split}_risk_coverage.png", dpi=150); plt.close(fig)

# --- 2) guvenilirlik diyagrami ---
fig, ax = plt.subplots(figsize=(5, 4.2))
ax.plot([0, 1], [0, 1], color=INK2, lw=1, ls=":")
for name, s, col in (scores[0], scores[4]):
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(s, bins) - 1, 0, 9)
    xs, ys, ns = [], [], []
    for b in range(10):
        m = idx == b
        if m.sum() >= 10:
            xs.append(s[m].mean()); ys.append(y[m].mean()); ns.append(m.sum())
    ax.plot(xs, ys, color=col, marker="o", markersize=6, label=name)
ax.set_xlabel("Tahmin edilen guvenilirlik")
ax.set_ylabel("Gercekte <=10 m olan oran")
ax.set_title(f"Guvenilirlik diyagrami ({LABEL})", loc="left", color=INK)
ax.legend(loc="upper left", fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}/{split}_reliability_diagram.png", dpi=150); plt.close(fig)

# --- 3) navigasyon: RMSE vs cagri araligi ---
nav = []
for p in glob.glob(f"{SWEEP}/sum/*.jsonl"):
    nav += [json.loads(l) for l in open(p) if l.strip()]
POL = [("E1", "E1 drift-only", INK2, ":"), ("E3", "E3 ham skor", C[1], "-"), ("E5", "E5 chi-square", C[4], "-"),
       ("E6", "E6 kalibre goruntu-only", C[2], "-"), ("E7", "E7 kalibre goruntu+Mahal.", C[0], "-"),
       ("E10", "E10 etiket-kahini (referans)", INK, "--")]
if nav:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for ax, (drift, filt) in zip(axes.flat, [("moderate", "matched"), ("moderate", "misspecified"),
                                             ("severe", "matched"), ("severe", "misspecified")]):
        g = defaultdict(list)
        for r in nav:
            if r["drift"] == drift and r["filter"] == filt:
                g[(r["policy"], r["call_interval"])].append(r["rmse"])
        cis = sorted({k[1] for k in g})
        for pid, lab, col, ls in POL:
            ax.plot(cis, [np.median(g[(pid, c)]) for c in cis], color=col, ls=ls, marker="o", markersize=5, label=lab)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}" if str(int(v))[0] in "2358" else ""))
        ax.set_title(f"drift={drift}, filtre={'dogru' if filt == 'matched' else 'yanlis-belirtilmis'}",
                     loc="left", fontsize=9, color=INK)
        ax.set_xticks(cis)
    for ax in axes[1]:
        ax.set_xlabel("Lokalizasyon cagri araligi (s)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Konum RMSE (m, log)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=8)
    fig.suptitle(f"Kapali-dongu navigasyon ({LABEL}, sekanslar uzerinden median)", x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(f"{OUT}/{split}_nav_rmse.png", dpi=150); plt.close(fig)

print("grafikler:", sorted(glob.glob(f"{OUT}/{split}_*.png")))
