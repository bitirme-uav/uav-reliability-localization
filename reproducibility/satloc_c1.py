"""SatLoc (Zhou et al., Remote Sens. 2025, 17, 3048) Eq. (2) confidence C1, evaluated on our
open-loop fix records (the SatLoc dataset itself is 529 GB and not downloadable here).

  Cscore     = 1 - sigmoid((S_best - S_subopt) - Thrs_diff)        (as printed)
  Cres_lower = sigmoid(Ratio_GSD - Thrs_ratio),  Thrs_ratio = 0.8
  C1         = w_s * Cscore + w_r * Cres_lower,  w_s + w_r = 1
  R          = sigma_base^2 / (C1 + eps)

As printed, Cscore *decreases* when the best score stands out from the rest, the opposite of
the text ("a more concentrated distribution indicates higher confidence"). Both the printed
form and the sign-corrected form (sigmoid instead of 1 - sigmoid) are scored. Thrs_diff and the
weights are not given in the paper; Thrs_diff only shifts a monotone map, so it does not change
AUROC for Cscore alone; weights are swept.

Our records carry top1/top2 inlier counts as `top1_top2_margin` = (s1 - s2) / s1, i.e. the
normalised gap to the single runner-up (M = 1 sub-optimal score), and `query_ref_scale_ratio`
as the GSD ratio proxy.

Usage: python satloc_c1.py
"""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"
OUT = Path(__file__).resolve().parent / "results" / "satloc_c1.json"
SETS = {"AerialVL TEST": "fixes_test.jsonl", "UAV-VisLoc TEST": "visloc_fixes_test.jsonl",
        "AnyVisLoc TEST": "anyvisloc_fixes_test.jsonl", "ALTO TEST": "alto_fixes_test.jsonl",
        "VPAIR TEST": "vpair_fixes_test.jsonl"}


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def load(path):
    rows = [json.loads(l) for l in open(path)]
    rows = [r for r in rows if r.get("fix_error_m") is not None and r.get("top1_top2_margin") is not None]
    err = np.array([r["fix_error_m"] for r in rows], float)
    gap = np.array([r["top1_top2_margin"] for r in rows], float)
    ratio = np.array([r.get("query_ref_scale_ratio") or np.nan for r in rows], float)
    heur = np.array([r.get("heuristic_confidence") if r.get("heuristic_confidence") is not None else np.nan
                     for r in rows], float)
    return err, gap, ratio, heur


def auroc(y, s):
    ok = np.isfinite(s)
    if ok.sum() < 10 or len(set(y[ok])) < 2:
        return None
    return round(float(roc_auc_score(y[ok], s[ok])), 3)


def main():
    res = {}
    for name, fn in SETS.items():
        p = OUTPUTS / fn
        if not p.exists():
            continue
        err, gap, ratio, heur = load(p)
        cres = sig(ratio - 0.8)
        out = {"n": int(len(err))}
        for thr in (10, 25):
            y = (err <= thr).astype(int)
            d = {"base_rate": round(float(y.mean()), 3),
                 "Cscore_as_printed": auroc(y, 1 - sig(gap - 0.5)),
                 "Cscore_sign_corrected": auroc(y, sig(gap - 0.5)),
                 "Cres_lower": auroc(y, cres),
                 "project_satloc_style_heuristic": auroc(y, heur)}
            for ws in (0.25, 0.5, 0.75):
                d[f"C1_corrected_ws{ws}"] = auroc(y, ws * sig(gap - 0.5) + (1 - ws) * cres)
            out[f"label_le_{thr}m"] = d
        res[name] = out
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
