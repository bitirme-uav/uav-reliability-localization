"""VPAIR (ornek alt kume, 200 kare, Almanya) okuyucu + referans goruntulerinden rota haritasi.

Veri: queries/NNNNN.png (800x600, ~300-400 m AGL, asagi bakan), reference_views/NNNNN.png
(ayni konumdan dik-asagi, kuzey-yukari PERSPEKTIF render) + depth_NNNNN.npy (metrik derinlik).
Pozlar ECEF (m); roll/pitch/yaw radyan.

Harita: Her referans gorunumunun her pikseli derinlikle yere izdusurulur (dik kamera:
dogu = (u-cx)*z/f, kuzey = -(v-cy)*z/f) ve EPSG:4326 dogrusal bir tuvale ortalanarak
yazilir -> ortofoto rota haritasi (vpair_map.tif). f = 747 px, ardisik referans
goruntulerinin kaymasindan olculdu (TUNE kareleri 1-40).

Ayrim (sonuclara bakmadan): TUNE = kare 1-40 (konvansiyon ayari), TEST = 41-200.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aerialvl_loader import GeoMap
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m

from paths import DATA_ROOT
ROOT = DATA_ROOT / "VPAIR/vpair_sample"
MAP_TIF = ROOT.parent / "vpair_map.tif"
F_PX = 747.0
MAP_GSD = 0.8   # lokalizer zaten 0.8 m/px'de calisiyor; bellek icin
TUNE_IDS = range(1, 41)
# Govde ekseninde sabit kamera ofseti (ileri, sag) [m] -- YALNIZ TUNE karelerinden olculdu
BODY_BIAS_M = (1.1, 5.6)
TEST_IDS = range(41, 201)


def ecef2lla(x, y, z):
    a = 6378137.0; e2 = 6.69437999014e-3; b = a * np.sqrt(1 - e2); ep2 = (a * a - b * b) / (b * b)
    p = np.hypot(x, y); th = np.arctan2(z * a, p * b); lon = np.arctan2(y, x)
    lat = np.arctan2(z + ep2 * b * np.sin(th) ** 3, p - e2 * a * np.cos(th) ** 3)
    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.degrees(lon), np.degrees(lat), p / np.cos(lat) - N


@dataclass(frozen=True)
class PFrame:
    path: str
    idx: int
    lon: float
    lat: float
    h: float
    yaw_deg: float
    utc_ts: float
    sequence: str = "vpair"


class VPAIR:
    def __init__(self):
        rows = list(csv.DictReader(open(ROOT / "poses_query.txt")))
        self.frames = []
        for r in rows:
            i = int(Path(r["filepath"]).stem)
            lon, lat, h = ecef2lla(float(r["x"]), float(r["y"]), float(r["z"]))
            self.frames.append(PFrame(str(ROOT / r["filepath"]), i, float(lon), float(lat), float(h),
                                      float(np.degrees(float(r["yaw"]))), float(i)))
        self.by_id = {f.idx: f for f in self.frames}

    def image(self, f: PFrame):
        return cv2.imread(f.path)

    def agl(self, f: PFrame) -> float:
        d = ROOT / "reference_views" / f"depth_{f.idx:05d}.npy"
        if not d.exists():
            return float("nan")
        z = np.load(d)
        return float(np.median(z[z.shape[0] // 2 - 50: z.shape[0] // 2 + 50, z.shape[1] // 2 - 50: z.shape[1] // 2 + 50]))

    def geomap(self) -> GeoMap:
        import rasterio
        b = rasterio.open(MAP_TIF).bounds
        return GeoMap(path=MAP_TIF, name="vpair_map", lt_lon=b.left, lt_lat=b.top, rb_lon=b.right, rb_lat=b.bottom)


def build_map():
    import rasterio
    from rasterio.transform import from_bounds
    rows = list(csv.DictReader(open(ROOT / "poses_reference_view.txt")))
    refs = []
    for r in rows:
        lon, lat, _ = ecef2lla(float(r["x"]), float(r["y"]), float(r["z"]))
        refs.append((ROOT / r["filepath"], float(lon), float(lat)))
    lon0, lat0 = refs[0][1], refs[0][2]
    pad = 300.0
    en = np.array([lonlat_to_enu_m(lo, la, lon0, lat0) for _, lo, la in refs])
    e_min, n_min = en.min(0) - pad; e_max, n_max = en.max(0) + pad
    W = int((e_max - e_min) / MAP_GSD); H = int((n_max - n_min) / MAP_GSD)
    acc = np.zeros((H, W, 3), np.float32); cnt = np.zeros((H, W), np.float32)   # ~1 GB
    for (p, lo, la), (ce, cn) in zip(refs, en):
        img = cv2.imread(str(p)); dep = np.load(p.parent / f"depth_{p.stem}.npy").astype(np.float64)
        h, w = img.shape[:2]; cx, cy = w / 2.0, h / 2.0
        v, u = np.mgrid[0:h, 0:w]
        ok = np.isfinite(dep) & (dep > 0)
        E = ce + (u - cx) * dep / F_PX; N = cn - (v - cy) * dep / F_PX
        col = ((E - e_min) / MAP_GSD).astype(int); row = ((n_max - N) / MAP_GSD).astype(int)
        ok &= (col >= 0) & (col < W) & (row >= 0) & (row < H)
        # merkeze yakin piksellere daha cok agirlik (kenar bozulmalari az)
        wgt = np.exp(-(((u - cx) / w) ** 2 + ((v - cy) / h) ** 2) * 4)[ok]
        r, c_ = row[ok], col[ok]
        r0, r1, c0, c1 = r.min(), r.max() + 1, c_.min(), c_.max() + 1
        lin = (r - r0) * (c1 - c0) + (c_ - c0)                     # yalniz bu goruntunun yerel penceresi
        n = (r1 - r0) * (c1 - c0)
        for ch in range(3):
            acc[r0:r1, c0:c1, ch] += np.bincount(lin, weights=img[..., ch][ok] * wgt, minlength=n).reshape(r1 - r0, c1 - c0)
        cnt[r0:r1, c0:c1] += np.bincount(lin, weights=wgt, minlength=n).reshape(r1 - r0, c1 - c0)
    out = np.zeros((H, W, 3), np.uint8); m = cnt > 0
    out[m] = np.clip(acc[m] / cnt[m][:, None], 0, 255).astype(np.uint8)
    del acc, cnt
    W_, N_ = enu_to_lonlat_m(e_min, n_max, lon0, lat0); E_, S_ = enu_to_lonlat_m(e_max, n_min, lon0, lat0)
    with rasterio.open(MAP_TIF, "w", driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs="EPSG:4326",
                       transform=from_bounds(W_, S_, E_, N_, W, H), compress="jpeg", tiled=True) as ds:
        ds.write(out[:, :, ::-1].transpose(2, 0, 1))
    print(f"harita: {W}x{H} px @ {MAP_GSD} m -> {MAP_TIF}")


if __name__ == "__main__":
    build_map()
