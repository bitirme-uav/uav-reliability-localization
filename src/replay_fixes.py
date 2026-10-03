"""Mevcut acik-dongu fix kayitlarini AYNI kare / AYNI prior / AYNI arama yaricapi ile baska bir
eslestiriciyle yeniden uretir (eslestirilmis karsilastirma). Lokalizasyon disindaki alanlar korunur.
Kullanim: python replay_fixes.py --matcher xfeat --files fixes_test.jsonl,alto_fixes_test.jsonl,...
Cikti: outputs/v2_<matcher>/<ayni dosya adi>"""
import argparse
import json
import os
import time

import cv2
import numpy as np

from fix_record import FixRecord, FixRecordWriter, label_fix, load_records
from gates import heuristic_confidence
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m
from localization_pipeline import MapExtractor

O = "../outputs/"


def make(matcher, **kw):
    if matcher == "xfeat":
        from xfeat_pipeline import XFeatPipeline
        return XFeatPipeline(**kw)
    from localization_pipeline import LocalizationPipeline
    return LocalizationPipeline(features=matcher, **kw)


def body_correct(fe, fn, heading_deg, bias):
    h = np.radians(heading_deg); bf, br = bias
    return fe - (bf * np.sin(h) + br * np.cos(h)), fn - (bf * np.cos(h) - br * np.sin(h))


class AerialAdapter:
    kw = {}

    def __init__(self):
        from aerialvl_loader import AerialVLVal
        from run_nav_sim import VAL_ROOT
        self.val = AerialVLVal(VAL_ROOT)
        man = json.load(open(O + "aerialvl_train_manifest.json"))
        self.coords = {}   # sekans -> [(stem, lon, lat)] (silinmis TRAIN kareleri dahil, dosya adindan)
        for s, names in man.items():
            self.coords[s] = [(n[:-4], float(n.split("@")[2]), float(n.split("@")[3])) for n in names]
        for s, fr in self.val.sequences.items():
            if s not in self.coords:
                self.coords[s] = [(f.path.stem, f.lon, f.lat) for f in fr]
        self.byid = {f.path.stem: f for fr in self.val.sequences.values() for f in fr}

    def run(self, pipe, rec):
        from boresight import correct_fix_enu
        f = self.byid[rec.query_id]
        c = self.coords[rec.sequence_id]; i = [x[0] for x in c].index(rec.query_id)
        a, b = c[max(0, i - 4)], c[min(len(c) - 1, i + 4)]
        ve, vn = lonlat_to_enu_m(b[1], b[2], a[1], a[2])
        plon, plat = enu_to_lonlat_m(rec.prior_x_m, rec.prior_y_m, f.lon, f.lat)
        r = pipe.localize(cv2.imread(str(f.path)), MapExtractor(self.val.map_for(f.lon, f.lat)), plon, plat, rec.search_window_m)
        return r, f.lon, f.lat, (lambda e, n: correct_fix_enu(e, n, ve, vn))


class VislocAdapter:
    def __init__(self):
        from visloc_attitude import load_coef
        from visloc_build_fix_dataset import VISLOC_PIPE
        from visloc_loader import UAVVisLoc
        self.kw = dict(VISLOC_PIPE)
        self.v = UAVVisLoc(["01", "02", "03", "04", "06", "08", "09", "11"])
        self.byid = {f.path: f for fr in self.v.sequences.values() for f in fr}
        self.coef = load_coef()

    def run(self, pipe, rec):
        from visloc_attitude import correct_fix_enu
        q = self.byid[rec.query_id]
        plon, plat = enu_to_lonlat_m(rec.prior_x_m, rec.prior_y_m, q.lon, q.lat)
        r = pipe.localize(self.v.image(q), MapExtractor(self.v.map_for(q.lon, q.lat)), plon, plat, rec.search_window_m,
                          query_rot_ccw_deg=-q.yaw_deg)
        return r, q.lon, q.lat, (lambda e, n: correct_fix_enu(e, n, q.yaw_deg, q.omega, q.kappa, r.ground_footprint_m, self.coef))


class AnyAdapter:
    def __init__(self):
        from anyvisloc_build_fix_dataset import ANY_PIPE
        from anyvisloc_loader import AnyVisLoc
        self.kw = dict(ANY_PIPE)
        self.a = AnyVisLoc(tuple(f"{i:02d}" for i in range(1, 25)))
        self.byid = {f.path: f for fr in self.a.sequences.values() for f in fr}
        self._view = (None, None)

    def run(self, pipe, rec):
        from anyvisloc_build_fix_dataset import configure_for
        f = self.byid[rec.query_id]
        if self._view[0] != rec.query_id:
            self._view = (rec.query_id, self.a.nadir_view(f))
        view = self._view[1]
        lon, lat = self.a.lonlat(f)
        if view is None:
            return None, lon, lat, None
        img, mask, ctr, fpw, _ = view
        configure_for(pipe, fpw)
        plon, plat = enu_to_lonlat_m(rec.prior_x_m, rec.prior_y_m, lon, lat)
        r = pipe.localize(img, MapExtractor(self.a.map_for(f)), plon, plat, rec.search_window_m, query_mask=mask, query_center_px=ctr)
        return r, lon, lat, None


class VpairAdapter:
    kw = dict(query_rotation=None, map_work_gsd_m=0.8, map_max_keypoints=4096, tile_radius_m=150.0)

    def __init__(self):
        from vpair_loader import VPAIR
        self.v = VPAIR(); self.gm = self.v.geomap(); self.byid = {f.path: f for f in self.v.frames}

    def run(self, pipe, rec):
        from vpair_loader import BODY_BIAS_M, F_PX
        q = self.byid[rec.query_id]; img = self.v.image(q); fpw = img.shape[1] * self.v.agl(q) / F_PX
        pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * s for s in (0.85, 1.0, 1.2))
        pipe.COARSE_FOOTPRINTS_M = (fpw,); pipe.footprint_margin_m = 0.6 * fpw
        plon, plat = enu_to_lonlat_m(rec.prior_x_m, rec.prior_y_m, q.lon, q.lat)
        r = pipe.localize(img, MapExtractor(self.gm), plon, plat, rec.search_window_m, query_rot_ccw_deg=-q.yaw_deg)
        corr = (lambda e, n: body_correct(e, n, q.yaw_deg, BODY_BIAS_M)) if "test" in rec.run_id else None
        return r, q.lon, q.lat, corr


class AltoAdapter(VpairAdapter):
    def __init__(self):
        from alto_loader import ALTO
        self.v = ALTO(); self.gm = self.v.geomap(); self.byid = {f.path: f for f in self.v.frames}

    def run(self, pipe, rec):
        from alto_loader import BODY_BIAS_M, QUERY_FOOTPRINT_M
        q = self.byid[rec.query_id]; fpw = QUERY_FOOTPRINT_M
        pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * s for s in (0.85, 1.0, 1.2))
        pipe.COARSE_FOOTPRINTS_M = (fpw,); pipe.footprint_margin_m = 0.6 * fpw
        plon, plat = enu_to_lonlat_m(rec.prior_x_m, rec.prior_y_m, q.lon, q.lat)
        r = pipe.localize(self.v.image(q), MapExtractor(self.gm), plon, plat, rec.search_window_m, query_rot_ccw_deg=q.rot_ccw_deg)
        hd = 90.0 - (q.rot_ccw_deg + 3.3)
        corr = (lambda e, n: body_correct(e, n, hd, BODY_BIAS_M)) if "test" in rec.run_id else None
        return r, q.lon, q.lat, corr


def adapter_for(fname):
    if fname.startswith("visloc_"):
        return VislocAdapter
    if fname.startswith("anyvisloc_"):
        return AnyAdapter
    if fname.startswith("vpair_"):
        return VpairAdapter
    if fname.startswith("alto_"):
        return AltoAdapter
    return AerialAdapter


LOC_FIELDS = ("num_matches", "inlier_count", "inlier_ratio", "reprojection_error_px", "inlier_spatial_spread",
              "transform_condition", "query_ref_scale_ratio", "top1_score", "top1_top2_margin", "raw_confidence",
              "localization_latency_ms", "predicted_fix_x_m", "predicted_fix_y_m", "fix_error_m", "mahalanobis_d",
              "heuristic_confidence", "safe_primary", "safe_secondary")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--matcher", default="xfeat")
    ap.add_argument("--files", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()
    od = args.outdir or O + f"v2_{args.matcher}/"; os.makedirs(od, exist_ok=True)
    for fname in args.files.split(","):
        out = od + fname
        if os.path.exists(out) and os.path.exists(out + ".done"):
            print("var:", out); continue
        recs = load_records(O + fname)
        if args.limit:
            recs = recs[: args.limit]
        A = adapter_for(fname)(); pipe = make(args.matcher, **A.kw)
        open(out, "w").close(); w = FixRecordWriter(out); t0 = time.monotonic()
        for k, rec in enumerate(recs):
            d = rec.to_dict()
            for f in LOC_FIELDS:
                d.pop(f, None)
            new = FixRecord(**{kk: vv for kk, vv in d.items() if kk in FixRecord.__dataclass_fields__})
            r, glon, glat, corr = A.run(pipe, rec)
            if r is not None:
                new.num_matches, new.inlier_count, new.inlier_ratio = r.num_matches, r.inlier_count, r.inlier_ratio
                new.reprojection_error_px, new.inlier_spatial_spread = r.reprojection_error_px, r.inlier_spatial_spread
                new.transform_condition, new.query_ref_scale_ratio = r.transform_condition, r.query_ref_scale_ratio
                new.top1_score, new.top1_top2_margin = float(r.inlier_count), r.top1_top2_margin
                new.raw_confidence, new.localization_latency_ms = r.raw_confidence, r.localization_latency_ms
            if r is not None and r.predicted_lon is not None:
                fe, fn = lonlat_to_enu_m(r.predicted_lon, r.predicted_lat, glon, glat)
                if corr is not None:
                    fe, fn = corr(fe, fn)
                fe, fn = float(fe), float(fn)
                new.predicted_fix_x_m, new.predicted_fix_y_m = fe, fn
                new.fix_error_m = float(np.hypot(fe, fn))
                sig = float(np.sqrt(rec.prior_cov_xx))
                new.mahalanobis_d = float(np.hypot(fe - rec.prior_x_m, fn - rec.prior_y_m) / sig)
                if r.top1_top2_margin is not None:
                    new.heuristic_confidence = heuristic_confidence(r.inlier_count, r.top1_top2_margin, None)
            else:
                new.fix_error_m = 1e6
            label_fix(new); w.write(new)
            if (k + 1) % 140 == 0:
                print(f"  {fname}: {k+1}/{len(recs)} ({time.monotonic()-t0:.0f}s)", flush=True)
        w.close(); open(out + ".done", "w").close()
        print(f"yazildi: {out} ({time.monotonic()-t0:.0f}s)", flush=True)
        del pipe
        import torch; torch.cuda.empty_cache()
