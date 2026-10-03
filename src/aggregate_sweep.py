"""Sweep ozetlerini toplar: her (drift, filtre, cagri araligi) icin
politika basina RMSE / final / zararli duzeltme, sekanslar uzerinden
ortalama. Ayrica E7 vs E5 ve E7 vs E3 ikili kazanma sayilari."""
import argparse
import glob
import json
from collections import defaultdict

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--split", choices=["val", "test"], required=True)
args = ap.parse_args()

rows = []
for p in glob.glob(f"../outputs/sweep_{args.split}/sum/*.jsonl"):
    with open(p) as f:
        rows += [json.loads(l) for l in f if l.strip()]
print(f"{len(rows)} satir, {len({r['tag'] for r in rows})} kosu")

POL = ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
grp = defaultdict(lambda: defaultdict(list))
for r in rows:
    grp[(r["drift"], r["filter"], r["call_interval"])][r["policy"]].append(r)

out = {}
for key in sorted(grp):
    d = grp[key]
    print(f"\n=== drift={key[0]} filtre={key[1]} cagri_araligi={key[2]}s  (n_sekans={len(d['E1'])}) ===")
    print(f"{'':4s} {'RMSE':>8s} {'final':>8s} {'max':>8s} {'kabul':>6s} {'dw':>5s} {'red':>5s} {'zararli':>8s}")
    out[str(key)] = {}
    for p in POL:
        if p not in d:
            continue
        rr = d[p]
        m = {k: float(np.mean([x[k] for x in rr])) for k in ("rmse", "final", "max", "accept", "down-weight", "reject", "harmful")}
        out[str(key)][p] = m
        print(f"{p:4s} {m['rmse']:8.2f} {m['final']:8.2f} {m['max']:8.2f} {m['accept']:6.1f} {m['down-weight']:5.1f} "
              f"{m['reject']:5.1f} {m['harmful']:8.1f}")

# ikili karsilastirma: ayni kosuda E7 RMSE < X RMSE mi?
by_tag = defaultdict(dict)
for r in rows:
    by_tag[r["tag"]][r["policy"]] = r["rmse"]
print("\n=== ikili: E7'nin daha dusuk RMSE verdigi kosu sayisi ===")
for other in ("E1", "E2", "E3", "E4", "E5", "E6", "E8", "E9"):
    pairs = [(t["E7"], t[other]) for t in by_tag.values() if "E7" in t and other in t]
    if pairs:
        wins = sum(1 for a, b in pairs if a < b)
        ratio = np.median([a / b for a, b in pairs if b > 0])
        print(f"  E7 vs {other}: {wins}/{len(pairs)} kosuda daha iyi, median RMSE orani E7/{other}={ratio:.3f}")
with open(f"../outputs/sweep_{args.split}_aggregate.json", "w") as f:
    json.dump(out, f, indent=2)
