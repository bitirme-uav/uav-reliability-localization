"""AnyVisLoc okuyucu (indirilen kismi set: Scene_01, Scene_02).

Format: her kare bir npz (goruntu 1368x912, K, pose_c2w 4x4, xyz yerel metrik).
Kareler EGIK (pitch 20-50°). Calisma aninda IMU tutumu bilindigi icin kare,
ayni kamera merkezinde SANAL BIR NADIR (asagi bakan, kuzey-yukari) kameraya
homografiyle donusturulur: H = K_v Rv^T T R_c2w K^-1. Boylece sanal goruntu
merkezi = drone'un dogrudan altindaki yer noktasi -> etiket = (x, y).

Yerel (x, y) koordinatlari sabit sahte bir (lon, lat) referansina eslenir
(esdikdortgen yaklasim, birkac km'de ihmal edilebilir hata) -- mevcut
lon/lat tabanli lokalizer degismeden kullanilir.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aerialvl_loader import GeoMap
from geo_utils import enu_to_lonlat_m, lonlat_to_enu_m

from paths import DATA_ROOT
ROOT = DATA_ROOT / "AnyVisLoc"
LON0, LAT0 = 120.0, 30.0
# Yerel y ekseni harita satirlarinin artis yonune ters mi (-1) ayni mi (+1)?
# anyvisloc_calib.py ile Scene_01'de belirlendi.
Y_FLIP = -1
MAX_NADIR_ANGLE_DEG = 60.0
MAX_HALF_PX = 1600


@dataclass(frozen=True)
class AFrame:
    path: str
    scene: str
    x: float
    y: float
    z: float
    utc_ts: float = 0.0

    @property
    def sequence(self):
        return self.scene


def local_to_lonlat(x, y, y_flip=None):
    yf = Y_FLIP if y_flip is None else y_flip
    return enu_to_lonlat_m(x, yf * y, LON0, LAT0)


def lonlat_to_local(lon, lat, y_flip=None):
    yf = Y_FLIP if y_flip is None else y_flip
    e, n = lonlat_to_enu_m(lon, lat, LON0, LAT0)
    return e, yf * n


class AnyVisLoc:
    def __init__(self, scenes=("01", "02"), y_flip=None):
        self.y_flip = Y_FLIP if y_flip is None else y_flip
        self._z = {s: zipfile.ZipFile(ROOT / f"Scene_{s}.zip") for s in scenes}
        self.maps: dict[str, GeoMap] = {}
        self._dsm: dict = {}
        self.sequences: dict[str, list[AFrame]] = {}
        for s in scenes:
            j = json.load(open(ROOT / f"satellite_{s}.json"))
            res = j["map_resolution"][0]
            ox, oy = j["map_origin_local"]
            h, w = j["map_size"]                        # [satir, sutun]
            x0, x1 = ox, ox + w * res
            y_top, y_bot = (oy, oy + h * res) if self.y_flip == -1 else (oy + h * res, oy)
            lt_lon, lt_lat = local_to_lonlat(x0, y_top, self.y_flip)
            rb_lon, rb_lat = local_to_lonlat(x1, y_bot, self.y_flip)
            self.maps[s] = GeoMap(path=ROOT / f"satellite_{s}.tif", name=f"anyvisloc_{s}",
                                  lt_lon=lt_lon, lt_lat=lt_lat, rb_lon=rb_lon, rb_lat=rb_lat)
            names = sorted(n for n in self._z[s].namelist() if n.endswith(".npz"))
            meta = self._meta(s, names)
            self.sequences[s] = [AFrame(path=n, scene=s, x=m[0], y=m[1], z=m[2]) for n, m in zip(names, meta)]

    def _meta(self, s, names):
        cache = ROOT / f"meta_{s}.npy"
        if cache.exists():
            return np.load(cache)
        out = []
        for n in names:
            d = np.load(io.BytesIO(self._z[s].read(n)))
            out.append(d["xyz"])
        out = np.array(out)
        np.save(cache, out)
        return out

    def load(self, f: AFrame) -> dict:
        d = np.load(io.BytesIO(self._z[f.scene].read(f.path)))
        return {k: d[k] for k in ("image", "K", "pose_c2w", "euler_deg")}

    def map_for(self, f_or_lon, lat=None):
        if isinstance(f_or_lon, AFrame):
            return self.maps[f_or_lon.scene]
        for m in self.maps.values():
            if m.contains(f_or_lon, lat):
                return m
        return None

    def lonlat(self, f: AFrame):
        return local_to_lonlat(f.x, f.y, self.y_flip)

    def ground_z(self, f: AFrame) -> float:
        """Uydu DSM'inden (30 m) kamera alti zemin yuksekligi; gecersizse sahne medyani."""
        if f.scene not in self._dsm:
            j = json.load(open(ROOT / f"satellite_{f.scene}.json"))
            cache = ROOT / f"dsm_{f.scene}.npy"
            if not cache.exists():
                np.save(cache, np.load(io.BytesIO(self._z[f.scene].read(f"Scene_{f.scene}/satellite_dsm.npy"))))
            d = np.load(cache)
            # resmi kod (avl_utils.py): dsm_origin_local HARITA orijinine goreli
            dox = j["map_origin_local"][0] + j["dsm_origin_local"][0]
            doy = j["map_origin_local"][1] + j["dsm_origin_local"][1]
            self._dsm[f.scene] = (d, j["dsm_resolution"][0], (dox, doy), float(np.nanmedian(d[d > -1000])))
        d, res, (ox, oy), med = self._dsm[f.scene]
        c, r = int((f.x - ox) / res), int((f.y - oy) / res)
        if 0 <= r < d.shape[0] and 0 <= c < d.shape[1] and -1000 < d[r, c] < 9000:
            return float(d[r, c])
        return med

    @staticmethod
    def camera_R(roll_deg, pitch_deg, yaw_deg):
        """Kamera->dunya (dogu, kuzey, yukari), OpenCV kamera ekseni. Resmi kodun konvansiyonu
        (UAV-AVL/Benchmark, view_center_anyvisloc): yaw kuzeyden saat yonunde, pitch NADIRDEN
        egiklik. Not: pose_c2w farkli bir eksen konvansiyonunda; kullanilmiyor."""
        h, p = np.radians(yaw_deg), np.radians(pitch_deg)
        f = np.array([np.sin(h), np.cos(h), 0.0]); r = np.array([np.cos(h), -np.sin(h), 0.0])
        dn = np.array([0.0, 0.0, -1.0])
        R = np.stack([r, -np.cos(p) * f + np.sin(p) * dn, np.cos(p) * dn + np.sin(p) * f], 1)
        if roll_deg:
            R = R @ cv2.Rodrigues(np.array([0.0, 0.0, np.radians(roll_deg)]))[0]
        return R

    def nadir_view(self, f: AFrame):
        """Egik kareyi sanal nadir, kuzey-yukari kameraya cevirip gecerli bolgeye kirpar.
        Donus: (goruntu BGR, maske, nadir pikseli (x, y), kirpik genisliginin yer karsiligi [m], AGL [m])."""
        d = self.load(f)
        img = cv2.cvtColor(d["image"], cv2.COLOR_RGB2BGR)
        K = d["K"].astype(np.float64)
        ro, pi, ya = (float(v) for v in d["euler_deg"])
        R = self.camera_R(ro, pi, ya)
        Rv = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64).T  # x=dogu, satir=guney
        # sanal odak uzakligi: gercek fx, ama sanal goruntu en fazla 2*MAX_HALF_PX (bellek)
        fv = min(K[0, 0], MAX_HALF_PX / np.tan(np.radians(MAX_NADIR_ANGLE_DEG)))
        half = int(fv * np.tan(np.radians(MAX_NADIR_ANGLE_DEG)))
        Kv = np.array([[fv, 0, half], [0, fv, half], [0, 0, 1]], dtype=np.float64)
        H = Kv @ Rv.T @ R @ np.linalg.inv(K)
        size = (2 * half, 2 * half)
        valid = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), H, size, flags=cv2.INTER_NEAREST)
        circ = np.zeros_like(valid); cv2.circle(circ, (half, half), half, 255, -1)
        valid &= circ
        out = cv2.warpPerspective(img, H, size, flags=cv2.INTER_LINEAR)
        rows, cols = np.where(valid > 0)
        if len(rows) == 0:
            return None
        y0, y1, x0, x1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        out, valid = out[y0:y1, x0:x1], cv2.erode(valid[y0:y1, x0:x1], np.ones((15, 15), np.uint8))
        agl = max(f.z - self.ground_z(f), 20.0)
        return out, valid, (half - x0, half - y0), (x1 - x0) / fv * agl, agl
