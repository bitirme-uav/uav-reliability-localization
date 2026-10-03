"""Esri World Imagery Wayback arsivinden, verilen bolge icin farkli tarihli uydu
goruntusu indirir ve EPSG:4326 GeoTIFF'e (lat'ta dogrusal) yeniden orneklenmis
olarak yazar. Amac: harita tarihi/mevsimi eslesmeyi ne kadar etkiliyor?

Kullanim: python wayback_fetch.py UCUS [--zoom 18]
Cikti: ext_wayback/<ucus>/wb_<cekim-tarihi>.tif + index.json
"""
import argparse
import concurrent.futures as cf
import datetime
import io
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import rasterio
from rasterio.transform import from_bounds

from visloc_loader import ROOT, UAVVisLoc

CONFIG_URL = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
OUT = ROOT / "ext_wayback"
META_LAYER = 5          # "60cm Resolution Metadata"
UA = {"User-Agent": "research-uav-localization/0.1"}


def get(url, timeout=30, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except Exception:
            if i == tries - 1:
                raise


def releases_by_capture_date(cfg, lat, lon):
    """Her farkli cekim tarihi icin onu gosteren ilk Wayback surumu."""
    def q(k):
        url = f"{cfg[k]['metadataLayerUrl']}/{META_LAYER}/query?" + urllib.parse.urlencode(dict(
            geometry=f"{lon},{lat}", geometryType="esriGeometryPoint", inSR=4326,
            outFields="SRC_DATE2,SRC_RES,NICE_DESC", returnGeometry="false", f="json"))
        try:
            f = json.loads(get(url)).get("features")
            return f[0]["attributes"] if f else None
        except Exception:
            return None
    ks = sorted(cfg, key=int)
    with cf.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(q, ks))
    out = {}
    for k, a in zip(ks, res):
        if a and a["SRC_DATE2"] and a["SRC_DATE2"] not in out:
            out[a["SRC_DATE2"]] = dict(release=k, res_m=a["SRC_RES"], source=a["NICE_DESC"],
                                       date=str(datetime.datetime.utcfromtimestamp(a["SRC_DATE2"] / 1000).date()))
    return sorted(out.values(), key=lambda r: r["date"])


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def fetch_mosaic(item_url, release, bbox, z, need=None):
    lon0, lat0, lon1, lat1 = bbox            # bati, guney, dogu, kuzey
    x0, y0 = lonlat_to_tile(lon0, lat1, z)
    x1, y1 = lonlat_to_tile(lon1, lat0, z)
    tx, ty = range(int(x0), int(x1) + 1), range(int(y0), int(y1) + 1)
    mos = np.zeros((len(ty) * 256, len(tx) * 256, 3), np.uint8)

    def one(c):
        col, row = c
        url = item_url.replace("{level}", str(z)).replace("{row}", str(row)).replace("{col}", str(col))
        try:
            im = cv2.imdecode(np.frombuffer(get(url), np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            im = None
        return c, im
    todo = [(c, r) for r in ty for c in tx if need is None or (c, r) in need]
    with cf.ThreadPoolExecutor(32) as ex:
        for (col, row), im in ex.map(one, todo):
            if im is not None:
                i, j = row - ty[0], col - tx[0]
                mos[i * 256:(i + 1) * 256, j * 256:(j + 1) * 256] = im
    # Mercator -> esdikdortgen (lat'ta dogrusal) yeniden ornekleme
    H = int(round((y1 - y0) * 256)); W = int(round((x1 - x0) * 256))
    lats = lat1 + (lat0 - lat1) * (np.arange(H) + 0.5) / H
    mys = np.array([lonlat_to_tile(lon0, la, z)[1] for la in lats]) - ty[0]
    mxs = (x0 - tx[0]) + (np.arange(W) + 0.5) / W * (x1 - x0)
    # en yakin piksel (0.5 m'lik piksel icin yeterli; tam izgara remap'i GB'larca bellek ister)
    ri = np.clip(np.round(mys * 256 - 0.5).astype(int), 0, mos.shape[0] - 1)
    ci = np.clip(np.round(mxs * 256 - 0.5).astype(int), 0, mos.shape[1] - 1)
    return mos[ri][:, ci]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flight")
    ap.add_argument("--zoom", type=int, default=18)
    ap.add_argument("--pad-m", type=float, default=800)
    a = ap.parse_args()
    v = UAVVisLoc([a.flight])
    fr = [f for f in v.sequences[a.flight] if v.map_for(f.lon, f.lat) is not None]
    lons, lats = np.array([f.lon for f in fr]), np.array([f.lat for f in fr])
    dlat = a.pad_m / 111320; dlon = a.pad_m / (111320 * math.cos(math.radians(lats.mean())))
    bbox = (lons.min() - dlon, lats.min() - dlat, lons.max() + dlon, lats.max() + dlat)
    cfg = json.loads(get(CONFIG_URL))
    rels = releases_by_capture_date(cfg, float(np.median(lats)), float(np.median(lons)))
    # yalnizca rota koridoru: her kareden pad-m icindeki karolar
    need = set()
    tile_m = 40075016.7 * math.cos(math.radians(lats.mean())) / 2 ** a.zoom
    k = int(math.ceil(a.pad_m / tile_m))
    for lo, la in zip(lons, lats):
        cx, cy = (int(t) for t in lonlat_to_tile(lo, la, a.zoom))
        need.update((cx + i, cy + j) for i in range(-k, k + 1) for j in range(-k, k + 1))
    print(f"ucus {a.flight}: koridor karo sayisi={len(need)}", flush=True)
    print(f"ucus {a.flight}: bbox={np.round(bbox, 4)} cekimler={[r['date'] for r in rels]}", flush=True)
    od = OUT / a.flight; od.mkdir(parents=True, exist_ok=True)
    for r in rels:
        p = od / f"wb_{r['date']}.tif"
        if not p.exists():
            img = fetch_mosaic(cfg[r["release"]]["itemURL"], r["release"], bbox, a.zoom, need)
            with rasterio.open(p, "w", driver="GTiff", width=img.shape[1], height=img.shape[0], count=3,
                               dtype="uint8", crs="EPSG:4326", transform=from_bounds(*bbox, img.shape[1], img.shape[0]),
                               compress="jpeg", tiled=True) as ds:
                ds.write(img[:, :, ::-1].transpose(2, 0, 1))
        r.update(path=str(p), bbox=bbox)
        print(f"  {r['date']} ({r['source']}, {r['res_m']} m) -> {p.name}", flush=True)
    json.dump(rels, open(od / "index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
