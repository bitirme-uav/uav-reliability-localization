"""Eslestirici karsilastirmasi -- YALNIZ gelistirme/ayar verisi (TEST'e dokunmaz).
Veri setleri: AerialVL VAL, UAV-VisLoc TUNE+RECAL (veri seti haritasi), AnyVisLoc TUNE (01, 03),
VPAIR TUNE (1-40), ALTO TUNE (ilk %20). Her birinden ~40 kare, prior 30 m hatali, arama 60 m.
Hata, her veri setinin kendi sabit duzeltmesiyle (boresight/egiklik/ofset) olculur.
Kullanim: python matcher_sweep.py superpoint,aliked,disk,sift,doghardnet,xfeat [kare_sayisi]
Cikti: outputs/matcher_sweep.json (eslestirici x veri seti)"""
import json
import random
import sys
import time

import numpy as np
import torch

from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor

METHODS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["superpoint", "aliked", "disk", "sift", "doghardnet", "xfeat"]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
OUT = "../outputs/matcher_sweep.json"


def make(method, **kw):
    if method == "xfeat":
        from xfeat_pipeline import XFeatPipeline
        return XFeatPipeline(**kw)
    if method == "roma":
        from roma_pipeline import RomaPipeline
        return RomaPipeline(**kw)
    if method == "superpoint4k":
        return LocalizationPipeline(features="superpoint", max_keypoints=4096, **kw)
    return LocalizationPipeline(features=method, **kw)


def body_correct(fe, fn, heading_deg, bias):
    h = np.radians(heading_deg); bf, br = bias
    return fe - (bf * np.sin(h) + br * np.cos(h)), fn - (bf * np.cos(h) - br * np.sin(h))


# ---- veri seti gorevleri: her biri (base_kw, [ (run(pipe) -> (lon,lat,inl) , gt_lon, gt_lat, corr) ]) ----
def tasks_aerialvl():
    import cv2
    from aerialvl_loader import AerialVLVal
    from boresight import correct_fix_enu
    from run_nav_sim import VAL_ROOT
    from splits import VAL_SEQUENCES
    val = AerialVLVal(VAL_ROOT)
    fr = [(s, i) for s in VAL_SEQUENCES for i in range(1, len(val.sequences[s]) - 1)]
    out = []
    for s, i in random.Random(1).sample(fr, N):
        seq = val.sequences[s]; f = seq[i]
        ve, vn = lonlat_to_enu_m(seq[i + 1].lon, seq[i + 1].lat, seq[i - 1].lon, seq[i - 1].lat)

        def run(pipe, f=f):
            plon, plat = enu_to_lonlat_m(21.2, 21.2, f.lon, f.lat)
            return pipe.localize(cv2.imread(str(f.path)), MapExtractor(val.map_for(f.lon, f.lat)), plon, plat, 60)

        out.append((run, f.lon, f.lat, lambda e, n, r, ve=ve, vn=vn: correct_fix_enu(e, n, ve, vn)))
    return {}, out


def tasks_visloc():
    from visloc_attitude import correct_fix_enu, load_coef
    from visloc_build_fix_dataset import VISLOC_PIPE
    from visloc_loader import UAVVisLoc
    from visloc_splits import RECAL_FLIGHTS, TUNE_FLIGHTS
    FL = [f for f in list(TUNE_FLIGHTS) + list(RECAL_FLIGHTS) if f != "10"]
    v = UAVVisLoc(FL); coef = load_coef(); out = []
    per = max(1, N // len(FL))
    for fl in FL:
        frs = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
        for q in random.Random(700 + int(fl)).sample(frs, per):
            def run(pipe, q=q):
                plon, plat = enu_to_lonlat_m(21.2, -21.2, q.lon, q.lat)
                return pipe.localize(v.image(q), MapExtractor(v.map_for(q.lon, q.lat)), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
            out.append((run, q.lon, q.lat, None, q))
    def corr(e, n, r, q): return correct_fix_enu(e, n, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, coef)
    return dict(VISLOC_PIPE), [(t[0], t[1], t[2], lambda e, n, r, q=t[4]: corr(e, n, r, q)) for t in out]


def tasks_anyvisloc():
    from anyvisloc_build_fix_dataset import ANY_PIPE, configure_for
    from anyvisloc_loader import AnyVisLoc
    a = AnyVisLoc(("01", "03")); out = []
    for s in ("01", "03"):
        for f in random.Random(900 + int(s)).sample(a.sequences[s], N // 2):
            def run(pipe, f=f):
                view = a.nadir_view(f)
                if view is None:
                    return None
                img, mask, ctr, fpw, _ = view
                configure_for(pipe, fpw)
                lon, lat = a.lonlat(f); plon, plat = enu_to_lonlat_m(21.2, 21.2, lon, lat)
                return pipe.localize(img, MapExtractor(a.map_for(f)), plon, plat, 60, query_mask=mask, query_center_px=ctr)
            lon, lat = a.lonlat(f)
            out.append((run, lon, lat, None))
    return dict(ANY_PIPE), out


def tasks_vpair():
    from vpair_loader import F_PX, TUNE_IDS, VPAIR
    v = VPAIR(); gm = v.geomap(); out = []
    for i in TUNE_IDS:
        q = v.by_id[i]
        if not np.isfinite(v.agl(q)):
            continue
        def run(pipe, q=q):
            img = v.image(q); fpw = img.shape[1] * v.agl(q) / F_PX
            pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * s for s in (0.85, 1.0, 1.2)); pipe.footprint_margin_m = 0.6 * fpw
            plon, plat = enu_to_lonlat_m(-21.2, 21.2, q.lon, q.lat)
            return pipe.localize(img, MapExtractor(gm), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
        out.append((run, q.lon, q.lat, None))
    return dict(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0), out[:N]


def tasks_alto():
    from alto_loader import ALTO, BODY_BIAS_M, QUERY_FOOTPRINT_M
    v = ALTO(); gm = v.geomap(); out = []
    for q in v.tune[:: max(1, len(v.tune) // N)][:N]:
        def run(pipe, q=q):
            pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(QUERY_FOOTPRINT_M * s for s in (0.85, 1.0, 1.2))
            pipe.footprint_margin_m = 0.6 * QUERY_FOOTPRINT_M
            plon, plat = enu_to_lonlat_m(21.2, 21.2, q.lon, q.lat)
            return pipe.localize(v.image(q), MapExtractor(gm), plon, plat, 60, query_rot_ccw_deg=q.rot_ccw_deg)
        hd = 90.0 - (q.rot_ccw_deg + 3.3)
        out.append((run, q.lon, q.lat, lambda e, n, r, hd=hd: body_correct(e, n, hd, BODY_BIAS_M)))
    return dict(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0), out


DATASETS = {"aerialvl": tasks_aerialvl, "visloc": tasks_visloc, "anyvisloc": tasks_anyvisloc,
            "vpair": tasks_vpair, "alto": tasks_alto}

if __name__ == "__main__":
    try:
        res = json.load(open(OUT))
    except FileNotFoundError:
        res = {}
    for ds, fn in DATASETS.items():
        base_kw, tasks = fn()
        for m in METHODS:
            if res.get(m, {}).get(ds):
                continue
            pipe = make(m, **base_kw)
            errs, t0 = [], time.monotonic()
            for t in tasks:
                run, glon, glat, corr = t[0], t[1], t[2], t[3]
                try:
                    r = run(pipe)
                except Exception as ex:
                    r = None
                if r is None or r.predicted_lon is None:
                    errs.append(1e6); continue
                e, n = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, glon, glat)
                if corr is not None:
                    e, n = corr(e, n, r)
                errs.append(float(np.hypot(e, n)))
            e = np.array(errs); dt = (time.monotonic() - t0) / max(1, len(e))
            res.setdefault(m, {})[ds] = dict(n=len(e), median=float(np.median(e)), le10=float(np.mean(e <= 10)),
                                             le25=float(np.mean(e <= 25)), gt100=float(np.mean(e > 100)), sec=dt)
            print(f"{ds:10s} {m:12s} n={len(e)} median={np.median(e):7.1f} <=10m={np.mean(e<=10)*100:3.0f}% "
                  f"<=25m={np.mean(e<=25)*100:3.0f}% >100={np.mean(e>100)*100:3.0f}% {dt:.2f}s/kare", flush=True)
            json.dump(res, open(OUT, "w"), indent=1)
            del pipe; torch.cuda.empty_cache()
