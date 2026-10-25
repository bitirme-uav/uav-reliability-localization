"""ALTO (ICRA 2022 yarisma alt kumesi, Val bolumu) okuyucu + referans kesitlerinden rota haritasi.

Veri (Val): query_images/NNNNNN.png (500x500, helikopter, asagi bakan), query.csv
(UTM easting/northing, altitude, orient quaternion x,y,z,w); reference_images/offset_*/...
(500x500 uydu kesiti, kuzey-yukari) + reference.csv (kesit merkezleri). Rota boyunca ~10 m
aralikla kesitler, ayrica 20 ve 40 m kuzey/guney kaydirilmis kesitler.

Veriden olculenler (YALNIZ TUNE = ilk %20 kare; sonuca bakmadan sabitlendi):
  - referans GSD 0.613 m/px (ardisik kesitlerin kaymasi)
  - query GSD ~0.506 m/px -> yer kapsami ~253 m
  - kuzey-yukari icin CCW donus = quaternion ZYX-Z acisi - 3.3 derece
  - UTM bolgesi 17N (Ohio/Pennsylvania; ALTO makalesi)
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aerialvl_loader import GeoMap

from paths import DATA_ROOT
ROOT = DATA_ROOT / "ALTO/Val"
MAP_TIF = ROOT.parent / "alto_val_map.tif"
REF_GSD = 0.613
QUERY_FOOTPRINT_M = 253.0
ROT_OFFSET_DEG = -3.3
MAP_GSD = 0.8
UTM = "EPSG:32617"
N_TUNE_FRAC = 0.2
# Govde ekseninde sabit ofset (ileri, sag) [m] -- TUNE olcumunden sonra doldurulur
BODY_BIAS_M = (1.0, 6.2)   # duzeltilmis harita, TUNE: ileri 1.0 (std 4.9), sag 6.2 (std 7.8)


def utm_to_lonlat(e, n):
    from rasterio.warp import transform
    lo, la = transform(UTM, "EPSG:4326", np.atleast_1d(e).tolist(), np.atleast_1d(n).tolist())
    return np.array(lo), np.array(la)


@dataclass(frozen=True)
class AFrame:
    path: str
    idx: int
    lon: float
    lat: float
    rot_ccw_deg: float
    utc_ts: float
    sequence: str = "alto_val"


class ALTO:
    def __init__(self):
        from scipy.spatial.transform import Rotation as R
        rows = list(csv.DictReader(open(ROOT / "query.csv")))
        lo, la = utm_to_lonlat([float(r["easting"]) for r in rows], [float(r["northing"]) for r in rows])
        self.frames = []
        for i, (r, a, b) in enumerate(zip(rows, lo, la)):
            z = R.from_quat([float(r[k]) for k in ("orient_x", "orient_y", "orient_z", "orient_w")]).as_euler("ZYX", degrees=True)[0]
            self.frames.append(AFrame(str(ROOT / "query_images" / r["name"]), i, float(a), float(b),
                                      float(z + ROT_OFFSET_DEG), float(i)))
        n_tune = int(len(self.frames) * N_TUNE_FRAC)
        self.tune, self.test = self.frames[:n_tune], self.frames[n_tune:]

    def image(self, f: AFrame):
        img = cv2.imread(f.path, cv2.IMREAD_UNCHANGED)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) if img.ndim == 3 and img.shape[2] == 4 else img

    def geomap(self) -> GeoMap:
        import rasterio
        b = rasterio.open(MAP_TIF).bounds
        return GeoMap(path=MAP_TIF, name="alto_val_map", lt_lon=b.left, lt_lat=b.top, rb_lon=b.right, rb_lat=b.bottom)


def build_map():
    """Tum referans kesitlerini (5 kaydirma) her birinin GERCEK enlem/boylamina yerlestirip
    EPSG:4326 GeoTIFF yazar. (Ilk surum UTM->enlem/boylam'i dogrusal kabul ediyordu; UTM
    izgara yakinsamasi ~0.3 derece oldugu icin rota boyunca ~10 m kayma yaratti -- duzeltildi.)
    Tek kesit icindeki ~0.3 derecelik donus ihmal edildi (kenarda < 1 m)."""
    import rasterio
    from rasterio.transform import from_bounds
    refs = list(csv.DictReader(open(ROOT / "reference.csv")))
    lo, la = utm_to_lonlat([float(r["easting"]) for r in refs], [float(r["northing"]) for r in refs])
    lat_c = float(np.mean(la))
    dlat = MAP_GSD / 111320.0; dlon = MAP_GSD / (111320.0 * np.cos(np.radians(lat_c)))
    half = 250 * REF_GSD
    lon0 = lo.min() - half / 111320.0 / np.cos(np.radians(lat_c)); lon1 = lo.max() + half / 111320.0 / np.cos(np.radians(lat_c))
    lat0 = la.min() - half / 111320.0; lat1 = la.max() + half / 111320.0
    W = int((lon1 - lon0) / dlon); H = int((lat1 - lat0) / dlat)
    acc = np.zeros((H, W, 3), np.float32); cnt = np.zeros((H, W), np.float32)
    s = REF_GSD / MAP_GSD; sz = int(round(500 * s))
    wy, wx = np.mgrid[0:sz, 0:sz]
    wgt = np.exp(-(((wx - sz / 2) / sz) ** 2 + ((wy - sz / 2) / sz) ** 2) * 4).astype(np.float32)
    for r, x, y in zip(refs, lo, la):
        img = cv2.resize(cv2.imread(str(ROOT / "reference_images" / r["name"])), (sz, sz), interpolation=cv2.INTER_AREA)
        c0 = int(round((x - lon0) / dlon - sz / 2)); r0 = int(round((lat1 - y) / dlat - sz / 2))
        if c0 < 0 or r0 < 0 or c0 + sz > W or r0 + sz > H:
            continue
        acc[r0:r0 + sz, c0:c0 + sz] += img.astype(np.float32) * wgt[..., None]
        cnt[r0:r0 + sz, c0:c0 + sz] += wgt
    out = np.zeros((H, W, 3), np.uint8); m = cnt > 0
    out[m] = np.clip(acc[m] / cnt[m][:, None], 0, 255).astype(np.uint8)
    with rasterio.open(MAP_TIF, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs="EPSG:4326",
                       transform=from_bounds(lon0, lat0, lon1, lat1, W, H), compress="jpeg", tiled=True) as ds:
        ds.write(out[:, :, ::-1].transpose(2, 0, 1))
    print(f"harita: {W}x{H} px @ {MAP_GSD} m -> {MAP_TIF}")


if __name__ == "__main__":
    build_map()
