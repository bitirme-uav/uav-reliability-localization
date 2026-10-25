"""ALTO Train (10.436 kare, ~28.5 km) -> karisik egitim havuzu icin acik-dongu fix kayitlari.
Goruntuler zip'ten dogrudan okunur (disk tasarrufu). Rota ~3 km'lik ORTUSEN parcalara bolunur; her parca
kendi haritasi (EPSG:4326, 0.8 m/px). Kare, en yakin referans kesitinin 'cekirdek' parcasina atanir.
Platform ayarlari (donus ofseti, yer kapsami, govde ofseti) ALTO Val TUNE'dan (alto_loader) -- ayni helikopter.
Kullanim: python alto_train.py maps     (parca haritalarini uret)
          python alto_train.py build    (her 20. kare x 7 kosul -> outputs/alto_fixes_trainpool.jsonl)"""
import csv
import io
import sys
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np

from aerialvl_loader import GeoMap
from alto_loader import BODY_BIAS_M, MAP_GSD, QUERY_FOOTPRINT_M, REF_GSD, ROT_OFFSET_DEG, utm_to_lonlat

from paths import DATA_ROOT
ZIP = DATA_ROOT / "Train.zip"
MAPDIR = DATA_ROOT / "ALTO/train_maps"
CORE, OVL = 300, 60          # parca basina referans (rota boyu ~10 m aralik) ve ortusme
STEP = 20


def zread(z, name):
    return cv2.imdecode(np.frombuffer(z.read(name), np.uint8), cv2.IMREAD_COLOR)


def refs_route(z):
    R = list(csv.DictReader(io.TextIOWrapper(z.open("Train/reference.csv"))))
    lo, la = utm_to_lonlat([float(r["easting"]) for r in R], [float(r["northing"]) for r in R])
    base = [i for i, r in enumerate(R) if r["name"].startswith("offset_0_None")]
    return R, lo, la, base


def build_maps():
    import rasterio
    from rasterio.transform import from_bounds
    MAPDIR.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(ZIP); R, lo, la, base = refs_route(z)
    stem = lambda n: n.split("/")[1]
    by_stem = {}
    for i, r in enumerate(R):
        by_stem.setdefault(stem(r["name"]), []).append(i)      # ayni rota noktasinin 5 kaydirmasi
    stems = [stem(R[i]["name"]) for i in base]
    nchunk = int(np.ceil(len(stems) / CORE))
    for c in range(nchunk):
        out = MAPDIR / f"chunk_{c:02d}.tif"
        if out.exists():
            continue
        sel = [i for s in stems[max(0, c * CORE - OVL): (c + 1) * CORE + OVL] for i in by_stem[s]]
        x, y = lo[sel], la[sel]; lat_c = float(np.mean(y))
        dlat = MAP_GSD / 111320.0; dlon = MAP_GSD / (111320.0 * np.cos(np.radians(lat_c)))
        half = 250 * REF_GSD
        lon0 = x.min() - half / 111320.0 / np.cos(np.radians(lat_c)); lon1 = x.max() + half / 111320.0 / np.cos(np.radians(lat_c))
        lat0 = y.min() - half / 111320.0; lat1 = y.max() + half / 111320.0
        W = int((lon1 - lon0) / dlon); H = int((lat1 - lat0) / dlat)
        acc = np.zeros((H, W, 3), np.float32); cnt = np.zeros((H, W), np.float32)
        sz = int(round(500 * REF_GSD / MAP_GSD)); wy, wx = np.mgrid[0:sz, 0:sz]
        wgt = np.exp(-(((wx - sz / 2) / sz) ** 2 + ((wy - sz / 2) / sz) ** 2) * 4).astype(np.float32)
        for i in sel:
            img = cv2.resize(zread(z, "Train/reference_images/" + R[i]["name"]), (sz, sz), interpolation=cv2.INTER_AREA)
            c0 = int(round((lo[i] - lon0) / dlon - sz / 2)); r0 = int(round((lat1 - la[i]) / dlat - sz / 2))
            if c0 < 0 or r0 < 0 or c0 + sz > W or r0 + sz > H:
                continue
            acc[r0:r0 + sz, c0:c0 + sz] += img.astype(np.float32) * wgt[..., None]; cnt[r0:r0 + sz, c0:c0 + sz] += wgt
        o = np.zeros((H, W, 3), np.uint8); m = cnt > 0
        o[m] = np.clip(acc[m] / cnt[m][:, None], 0, 255).astype(np.uint8); del acc, cnt
        with rasterio.open(out, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs="EPSG:4326",
                           transform=from_bounds(lon0, lat0, lon1, lat1, W, H), compress="jpeg", tiled=True) as ds:
            ds.write(o[:, :, ::-1].transpose(2, 0, 1))
        print(f"parca {c}: {W}x{H} px, {len(sel)} kesit", flush=True)


def chunk_maps():
    import rasterio
    out = {}
    for p in sorted(MAPDIR.glob("chunk_*.tif")):
        b = rasterio.open(p).bounds
        out[int(p.stem.split("_")[1])] = GeoMap(path=p, name=p.stem, lt_lon=b.left, lt_lat=b.top, rb_lon=b.right, rb_lat=b.bottom)
    return out


def build_fixes():
    from scipy.spatial.transform import Rotation as Rot
    from fix_record import FixRecord, FixRecordWriter, label_fix
    from gates import heuristic_confidence
    from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
    from localization_pipeline import LocalizationPipeline, MapExtractor
    from replay_fixes import body_correct
    R_MIN, R_MAX = 60.0, 400.0
    COND = ((0, 20), (30, 20), (80, 40), (80, 20), (200, 80), (200, 20), (300, 140))
    z = zipfile.ZipFile(ZIP); R, rlo, rla, base = refs_route(z)
    maps = chunk_maps()
    Q = list(csv.DictReader(io.TextIOWrapper(z.open("Train/query.csv"))))
    qlo, qla = utm_to_lonlat([float(q["easting"]) for q in Q], [float(q["northing"]) for q in Q])
    bl, ba = rlo[base], rla[base]
    pipe = LocalizationPipeline(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0)
    pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(QUERY_FOOTPRINT_M * s for s in (0.85, 1.0, 1.2))
    pipe.COARSE_FOOTPRINTS_M = (QUERY_FOOTPRINT_M,); pipe.footprint_margin_m = 0.6 * QUERY_FOOTPRINT_M
    rng = np.random.default_rng(7000)
    out = "../outputs/alto_fixes_trainpool.jsonl"; open(out, "w").close(); w = FixRecordWriter(out)
    idx = list(range(0, len(Q), STEP)); t0 = time.monotonic()
    for k, i in enumerate(idx):
        q = Q[i]; lon, lat = float(qlo[i]), float(qla[i])
        j = int(np.argmin((bl - lon) ** 2 + (ba - lat) ** 2)); ch = min(j // CORE, max(maps))
        zq = Rot.from_quat([float(q[c]) for c in ("orient_x", "orient_y", "orient_z", "orient_w")]).as_euler("ZYX", degrees=True)[0]
        rot = float(zq + ROT_OFFSET_DEG); hd = 90.0 - (rot + 3.3)
        img = cv2.imdecode(np.frombuffer(z.read("Train/query_images/" + q["name"]), np.uint8), cv2.IMREAD_COLOR)
        for ci, (off, sig) in enumerate(COND):
            th = rng.uniform(0, 2 * np.pi); px, py = off * np.cos(th), off * np.sin(th)
            radius = float(np.clip(3 * sig, R_MIN, R_MAX)); plon, plat = enu_to_lonlat_m(px, py, lon, lat)
            try:
                r = pipe.localize(img, MapExtractor(maps[ch]), plon, plat, radius, query_rot_ccw_deg=rot)
            except Exception:
                r = None
            rec = FixRecord(run_id="alto_openloop_trainpool", policy_id="none", seed=0, sequence_id=f"alto_train_{ch:02d}",
                            query_id="Train/query_images/" + q["name"], timestamp_s=float(i), magnitude_idx=off, direction_idx=ci,
                            prior_x_m=px, prior_y_m=py, prior_cov_xx=sig ** 2, prior_cov_yy=sig ** 2, true_offset_m=float(off),
                            search_window_m=radius, in_window=off <= radius)
            if r is not None:
                rec.num_matches, rec.inlier_count, rec.inlier_ratio = r.num_matches, r.inlier_count, r.inlier_ratio
                rec.reprojection_error_px, rec.inlier_spatial_spread = r.reprojection_error_px, r.inlier_spatial_spread
                rec.transform_condition, rec.query_ref_scale_ratio = r.transform_condition, r.query_ref_scale_ratio
                rec.top1_score, rec.top1_top2_margin = float(r.inlier_count), r.top1_top2_margin
                rec.raw_confidence, rec.localization_latency_ms = r.raw_confidence, r.localization_latency_ms
            if r is not None and r.predicted_lon is not None:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, lon, lat)
                fe, fn = body_correct(fe, fn, hd, BODY_BIAS_M); fe, fn = float(fe), float(fn)
                rec.predicted_fix_x_m, rec.predicted_fix_y_m = fe, fn; rec.fix_error_m = float(np.hypot(fe, fn))
                rec.mahalanobis_d = float(np.hypot(fe - px, fn - py) / sig)
                if r.top1_top2_margin is not None:
                    rec.heuristic_confidence = heuristic_confidence(r.inlier_count, r.top1_top2_margin, None)
            else:
                rec.fix_error_m = 1e6
            label_fix(rec); w.write(rec)
        if (k + 1) % 50 == 0:
            print(f"  {k+1}/{len(idx)} ({time.monotonic()-t0:.0f}s)", flush=True)
    w.close(); print("yazildi:", out)


if __name__ == "__main__":
    {"maps": build_maps, "build": build_fixes}[sys.argv[1]]()
