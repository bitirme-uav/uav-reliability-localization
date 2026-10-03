"""UAV-VisLoc okuyucu -- AerialVLVal ile ayni arayuz (maps, sequences, map_for).

Farklar (README_dataset.txt):
  - lat/lon, drone goruntusunun MERKEZINE ait -> AerialVL kamera ofseti
    (boresight) burada UYGULANMAZ.
  - Her karenin yaw'i var (Phi1, kuzeyden saat yonunde derece). Calisma aninda
    IMU/pusuladan bilinen bu aci ile query kuzey-yukari dondurulur.
  - Drone JPG'leri dogrudan zip'ten okunur (disk tasarrufu); uydu haritalari
    ext/ altina cikarildi.
  - satellite09 dort parcaya bolunmus; parcalarin kendi gomulu
    georeferansi kullanilir (yoksa 2x2 izgara varsayilir).
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import rasterio

from aerialvl_loader import GeoMap

ROOT = Path("/media/davut/disk2/proje/uav_vloc_datasets/UAV-VisLoc")
ZIP = ROOT / "UAV_VisLoc_dataset.zip"
EXT = ROOT / "ext"


@dataclass(frozen=True)
class VFrame:
    path: str          # zip icindeki yol
    utc_ts: float      # ms (AerialVL ile ayni birim)
    lon: float
    lat: float
    height: float
    yaw_deg: float     # Phi1
    sequence: str
    omega: float = 0.0  # pitch (README)
    kappa: float = 0.0  # roll (README)
    sequence_kind: str = "visloc"


class UAVVisLoc:
    def __init__(self, flights: list[str] | None = None):
        self._zip = zipfile.ZipFile(ZIP)
        self.maps: list[GeoMap] = []
        self.sequences: dict[str, list[VFrame]] = {}
        rng = {}
        with open(EXT / "satellite_ coordinates_range.csv") as f:
            for r in csv.DictReader(f):
                rng[r["mapname"]] = r
        flights = flights or sorted(p.name for p in EXT.iterdir() if p.is_dir())
        for fl in flights:
            d = EXT / fl
            tifs = sorted(d.glob("satellite*.tif"))
            if not tifs:
                continue
            for t in tifs:
                self.maps.append(self._geomap(t, rng))
            frames = []
            with open(d / f"{fl}.csv") as f:
                for r in csv.DictReader(f):
                    yaw = r.get("Phi1") or r.get("Phi") or "nan"
                    frames.append(VFrame(
                        path=f"{fl}/drone/{r['filename']}",
                        utc_ts=datetime.fromisoformat(r["date"]).timestamp() * 1000.0,
                        lon=float(r["lon"]), lat=float(r["lat"]), height=float(r["height"]),
                        yaw_deg=float(yaw), sequence=fl,
                        omega=float(r.get('Omega') or 0), kappa=float(r.get('Kappa') or 0)))
            frames.sort(key=lambda x: x.utc_ts)
            self.sequences[fl] = frames

    @staticmethod
    def _geomap(tif: Path, rng: dict) -> GeoMap:
        with rasterio.open(tif) as ds:
            b, crs = ds.bounds, ds.crs
        if crs is not None and crs.is_geographic:
            return GeoMap(path=tif, name=tif.stem, lt_lon=b.left, lt_lat=b.top, rb_lon=b.right, rb_lat=b.bottom)
        r = rng.get(tif.name)
        if r is None:  # parcali harita, gomulu georef yok -> ana haritanin 2x2 izgarasi
            base = rng[tif.name.split("_")[0] + ".tif"]
            row, col = (int(x) for x in tif.stem.split("_")[1].split("-"))
            lt_lat, lt_lon = float(base["LT_lat_map"]), float(base["LT_lon_map"])
            rb_lat, rb_lon = float(base["RB_lat_map"]), float(base["RB_lon_map"])
            dlat, dlon = (lt_lat - rb_lat) / 2, (rb_lon - lt_lon) / 2
            return GeoMap(path=tif, name=tif.stem, lt_lon=lt_lon + (col - 1) * dlon, lt_lat=lt_lat - (row - 1) * dlat,
                          rb_lon=lt_lon + col * dlon, rb_lat=lt_lat - row * dlat)
        return GeoMap(path=tif, name=tif.stem, lt_lon=float(r["LT_lon_map"]), lt_lat=float(r["LT_lat_map"]),
                      rb_lon=float(r["RB_lon_map"]), rb_lat=float(r["RB_lat_map"]))

    def image(self, f: VFrame) -> np.ndarray:
        buf = np.frombuffer(self._zip.read(f.path), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def map_for(self, lon: float, lat: float) -> GeoMap | None:
        c = [m for m in self.maps if m.contains(lon, lat) and m.name.startswith("satellite")]
        if not c:
            return None
        # kenara en uzak olani sec (parcali haritada sinira yakin noktalar icin)
        def margin(m):
            return min(lon - m.lon_min, m.lon_max - lon, lat - m.lat_min, m.lat_max - lat)
        return max(c, key=margin)

    def all_frames(self):
        return [f for v in self.sequences.values() for f in v]


if __name__ == "__main__":
    v = UAVVisLoc()
    for m in v.maps:
        with rasterio.open(m.path) as ds:
            gsd = (m.lon_max - m.lon_min) * 111320 * np.cos(np.radians(m.lat_min)) / ds.width
            print(f"{m.name:22s} {ds.width}x{ds.height} crs={ds.crs} ~{gsd:.2f} m/px")
    for k, fr in v.sequences.items():
        inside = sum(v.map_for(f.lon, f.lat) is not None for f in fr)
        print(f"ucus {k}: {len(fr)} kare, haritada {inside}")
