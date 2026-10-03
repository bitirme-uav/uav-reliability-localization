"""UAV-VisLoc kamera egiklik (attitude) duzeltmesi.

Gozlem (TUNE ucusu 05): goruntu-merkezi fix'i ile etiket arasindaki hata
govde ekseninde ileri ~ +Kappa, sag ~ -Omega ile 0.97 korelasyonlu. Yani
kamera egik oldugunda goruntu merkezi drone'un altindaki noktadan kayiyor
(README Omega=pitch / Kappa=roll diyor, olcum tersini gosteriyor).

Model: ileri = CF * irtifa_vekili * tan(Kappa), sag = CR * irtifa_vekili * tan(Omega)
irtifa_vekili = eslesmeden cikan yer kapsami (ground_footprint_m) -- calisma
aninda bilinir; egiklik IMU'dan bilinir. Katsayilar SADECE TUNE ucuslarinda
uydurulur (fit modunda), sonra sabitlenir.
"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np

COEF_PATH = os.path.join(os.path.dirname(__file__), "..", "outputs", "visloc_attitude_coef.json")


def load_coef():
    with open(COEF_PATH) as f:
        return json.load(f)


def correct_fix_enu(fix_e, fix_n, yaw_deg, omega_deg, kappa_deg, footprint_m, coef):
    """Goruntu-merkezi fix'ini drone konumuna cevirir (ENU, metre)."""
    if footprint_m is None or not np.isfinite(footprint_m):
        return fix_e, fix_n
    fwd = coef["cf"] * footprint_m * np.tan(np.radians(kappa_deg)) + coef.get("bf", 0.0)
    right = coef["cr"] * footprint_m * np.tan(np.radians(omega_deg)) + coef.get("br", 0.0)
    h = np.radians(yaw_deg)
    de = fwd * np.sin(h) + right * np.cos(h)
    dn = fwd * np.cos(h) - right * np.sin(h)
    return fix_e - de, fix_n - dn


if __name__ == "__main__":
    from geo_utils import lonlat_to_enu_m
    from localization_pipeline import LocalizationPipeline, MapExtractor
    from visloc_loader import UAVVisLoc
    from visloc_splits import TUNE_FLIGHTS

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    v = UAVVisLoc(list(TUNE_FLIGHTS))
    items = [f for fl in TUNE_FLIGHTS for f in v.sequences[fl]]
    sample = random.Random(11).sample(items, min(N, len(items)))
    pipe = LocalizationPipeline(query_rotation=None, footprint_candidates_m=[250, 400, 600, 850],
                                footprint_margin_m=450, map_work_gsd_m=0.8, map_max_keypoints=4096)
    rows = []
    for q in sample:
        r = pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), q.lon, q.lat, 20,
                          query_rot_ccw_deg=-q.yaw_deg)
        if r.predicted_lon is None or r.inlier_count < 40:
            continue
        e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        if np.hypot(e, n) > 80:
            continue
        h = np.radians(q.yaw_deg)
        rows.append(dict(e=e, n=n, fwd=e * np.sin(h) + n * np.cos(h), right=e * np.cos(h) - n * np.sin(h),
                         fp=r.ground_footprint_m, om=q.omega, ka=q.kappa, yaw=q.yaw_deg, fl=q.sequence))
    np.save("../outputs/visloc_att_rows.npy", np.array([[r["e"],r["n"],r["fwd"],r["right"],r["fp"],r["om"],r["ka"],r["yaw"],float(r["fl"])] for r in rows]))
    print(f"guvenilir TUNE fix: {len(rows)}  (ucus: {sorted({r['fl'] for r in rows})})")
    def fit_coef(rr):
        Xf = np.array([[r["fp"] * np.tan(np.radians(r["ka"])), 1.0] for r in rr]); yf = np.array([r["fwd"] for r in rr])
        Xr = np.array([[r["fp"] * np.tan(np.radians(r["om"])), 1.0] for r in rr]); yr = np.array([r["right"] for r in rr])
        (cf, bf), (cr, br) = np.linalg.lstsq(Xf, yf, rcond=None)[0], np.linalg.lstsq(Xr, yr, rcond=None)[0]
        return {"cf": float(cf), "bf": float(bf), "cr": float(cr), "br": float(br)}

    def report(name, rr, coef):
        before = [np.hypot(r["e"], r["n"]) for r in rr]
        after = [np.hypot(*correct_fix_enu(r["e"], r["n"], r["yaw"], r["om"], r["ka"], r["fp"], coef)) for r in rr]
        print(f"  {name:22s} n={len(rr)} median hata: once={np.median(before):5.1f}m sonra={np.median(after):5.1f}m  "
              f"<=10m once={np.mean(np.array(before)<=10)*100:3.0f}% sonra={np.mean(np.array(after)<=10)*100:3.0f}%")

    random.Random(0).shuffle(rows)
    fit, hold = rows[: len(rows) // 2], rows[len(rows) // 2:]
    report("yari-dogrulama (ayrilan)", hold, fit_coef(fit))
    coef = fit_coef(rows)
    coef.update(n_fit=len(rows), source="TUNE ucuslari " + ",".join(TUNE_FLIGHTS) + " (pratikte ucus 05)")
    print(f"nihai katsayilar (tum TUNE): {coef}")
    report("tum TUNE (uyum)", rows, coef)
    with open(COEF_PATH, "w") as f:
        json.dump(coef, f, indent=2)
    print("kaydedildi:", COEF_PATH)
