"""Ayni kareleri farkli haritalarla lokalize et: veri setinin haritasi vs Wayback
arsivindeki farkli tarihli cekimler. Prior 30 m hatali, egiklik duzeltmesi dahil.
Kullanim: python wayback_compare.py UCUS [kare_sayisi]"""
import json
import random
import sys

import numpy as np

from aerialvl_loader import GeoMap
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import MapExtractor
from visloc_attitude import correct_fix_enu, load_coef
from visloc_build_fix_dataset import make_pipeline
from visloc_loader import ROOT, UAVVisLoc

fl = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
v = UAVVisLoc([fl])
coef = load_coef()
SRC = sys.argv[3].split(",") if len(sys.argv) > 3 else ["wayback"]       # wayback | google
maps = {"veri seti": None}
for src in SRC:
  idx = json.load(open(ROOT / f"ext_{src}" / fl / "index.json"))
  for r in idx:
    w, s, e, n = r["bbox"]
    maps[f"{src} {r['date']}"] = GeoMap(path=r["path"], name=f"wb_{fl}_{r['date']}", lt_lon=w, lt_lat=n, rb_lon=e, rb_lat=s)
fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
samp = random.Random(7 + int(fl)).sample(fr, min(N, len(fr)))
rng = np.random.default_rng(int(fl))
offs = [(30 * np.cos(t), 30 * np.sin(t)) for t in rng.uniform(0, 2 * np.pi, len(samp))]
pipe = make_pipeline()
print(f"ucus {fl}, ucus tarihi {getattr(samp[0], 'date', '?')}, {len(samp)} kare")
ALL = {}


def report(name, e, raw, inl):
    print(f"  {name:20s} median={np.median(e):7.1f}m <=10m={np.mean(e<=10)*100:3.0f}% <=25m={np.mean(e<=25)*100:3.0f}% "
          f">100m/yok={np.mean(e>100)*100:3.0f}%  (duzeltmesiz <=25m={np.mean(raw<=25)*100:3.0f}%)  median inlier={np.median(inl):.0f}",
          flush=True)


for name, gm in maps.items():
    errs, raw, inl = [], [], []
    for q, (de, dn) in zip(samp, offs):
        m = gm if gm is not None else v.map_for(q.lon, q.lat)
        plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
        try:
            r = pipe.localize(v.image(q), MapExtractor(m), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
        except Exception:
            r = None
        if r is None or r.predicted_lon is None:
            errs.append(1e6); raw.append(1e6); inl.append(0); continue
        e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        raw.append(np.hypot(e, n))
        e, n = correct_fix_enu(e, n, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, coef)
        errs.append(np.hypot(e, n)); inl.append(r.inlier_count)
    e, raw, inl = np.array(errs), np.array(raw), np.array(inl)
    ALL[name] = (e, raw, inl)
    report(name, e, raw, inl)
# Sahada uygulanabilir secim (GT kullanmaz): her karede en cok inlier veren harita
E, RAW, INL = (np.stack([ALL[k][i] for k in ALL]) for i in range(3))
best = INL.argmax(0); c = np.arange(E.shape[1])
report("EN IYI (inlier'e gore)", E[best, c], RAW[best, c], INL[best, c])
wb = [i for i, k in enumerate(ALL) if k != "veri seti"]
bw = np.array(wb)[INL[wb].argmax(0)]
report("sadece yeni, en iyi", E[bw, c], RAW[bw, c], INL[bw, c])
