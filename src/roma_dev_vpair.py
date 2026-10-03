"""SuperPoint vs RoMa -- VPAIR TUNE kareleri (1-40), prior 30 m hatali, arama 60 m. TEST'e dokunmaz."""
import numpy as np, time, torch
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import LocalizationPipeline, MapExtractor
from vpair_loader import F_PX, TUNE_IDS, VPAIR
v = VPAIR(); gm = v.geomap(); samp = [v.by_id[i] for i in TUNE_IDS if np.isfinite(v.agl(v.by_id[i]))]
rng = np.random.default_rng(9); offs = [(30*np.cos(t), 30*np.sin(t)) for t in rng.uniform(0, 2*np.pi, len(samp))]
for meth in ("superpoint", "roma"):
    kw = dict(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0)
    if meth == "roma":
        from roma_pipeline import RomaPipeline; pipe = RomaPipeline(**kw)
    else:
        pipe = LocalizationPipeline(**kw)
    err, inl, t0 = [], [], time.monotonic()
    for q, (de, dn) in zip(samp, offs):
        img = v.image(q); fpw = img.shape[1] * v.agl(q) / F_PX
        pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw*s for s in (0.85, 1.0, 1.2)); pipe.footprint_margin_m = 0.6*fpw
        plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
        r = pipe.localize(img, MapExtractor(gm), plon, plat, 60, query_rot_ccw_deg=-q.yaw_deg)
        e = 1e6 if r.predicted_lon is None else float(np.hypot(*lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)))
        err.append(e); inl.append(r.inlier_count)
    e = np.array(err)
    print(f"{meth:10s} n={len(e)} median={np.median(e):5.1f}m <=5m={np.mean(e<=5)*100:3.0f}% <=10m={np.mean(e<=10)*100:3.0f}% <=25m={np.mean(e<=25)*100:3.0f}% median_inlier={np.median(inl):.0f} {(time.monotonic()-t0)/len(e):.1f} s/kare", flush=True)
    del pipe; torch.cuda.empty_cache()
