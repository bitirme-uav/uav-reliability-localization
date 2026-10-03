"""Coğrafi/metrik koordinat yardımcıları.

AerialVL koordinatları WGS84 lon/lat. Metrik hata (M3: fix_error_m) ve
metrik ENU (M6/M7: drift simulator, search radius) icin lokal bir
duzlem projeksiyonu kullaniyoruz -- HIL bridge'de de ayni yaklasim
var (bkz. flight_controller/f450_ws_hil hil_bridge_node.py _gps_to_enu),
tutarlilik icin ayni formul.
"""
from __future__ import annotations

import math

EARTH_R_M = 6371000.0


def lonlat_to_enu_m(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    """(lon,lat) -> (east_m, north_m), origin'e gore lokal duzlem projeksiyonu.

    Kucuk alanlar (bir kac 10 km) icin yeterli dogrulukta equirectangular
    yaklasim. Buyuk UTM zone gecisleri gerekmiyor cunku her AerialVL
    sekansi tek bir bolgede (<= ~11 km) kaliyor.
    """
    origin_lat_rad = math.radians(origin_lat)
    east = (lon - origin_lon) * EARTH_R_M * math.cos(origin_lat_rad) * math.pi / 180.0
    north = (lat - origin_lat) * EARTH_R_M * math.pi / 180.0
    return east, north


def enu_to_lonlat_m(east: float, north: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    """lonlat_to_enu_m'nin tersi."""
    origin_lat_rad = math.radians(origin_lat)
    lon = origin_lon + east / (EARTH_R_M * math.cos(origin_lat_rad) * math.pi / 180.0)
    lat = origin_lat + north / (EARTH_R_M * math.pi / 180.0)
    return lon, lat


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """İki lon/lat noktası arası büyük-daire mesafesi (metre).

    M3'teki fix_error_i = ||predicted - ground_truth|| (metre, 2D) için
    kullanılır. AerialVL mesafeleri (<11km) için equirectangular ile
    haversine arasındaki fark ihmal edilebilir, ama etiket tanımı
    (M3) "metres" dediği için burada doğru büyük-daire formülünü
    kullanıyoruz.
    """
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat = r2 - r1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))
