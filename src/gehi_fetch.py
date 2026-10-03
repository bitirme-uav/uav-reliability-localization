"""Google Earth gecmis goruntuleri (GEHistoricalImagery araci) ile UAV-VisLoc ucuslari icin
tarihli harita. Secim kurali SONUCLARA BAKMADAN sabitlendi, kare (tile) basina:
  once  : ucus tarihinden ONCEKI en yakin cekim  (gercekci: harita ucustan once vardir)
  yakin : ucus tarihine en yakin cekim (once/sonra) (geriye donuk)
Cikti: ext_google/<ucus>/ge_<kural>.tif + index.json (wayback_compare.py ile ayni bicim).
Ucus 11 haric (yakin tarihli goruntu yok)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from visloc_loader import ROOT, UAVVisLoc

TOOL = "/media/davut/disk2/proje/tools/gehi/GEHistoricalImagery"
OUT = ROOT / "ext_google"
ZOOM = 18          # ~0.5 m/px; lokalizer 0.8 m/px'de calisiyor
PAD_DEG = 0.008    # ~800 m
RULES = {"once": "ClosestBefore", "yakin": "Closest"}


def flight_date(fl):
    import csv, glob
    f = glob.glob(str(ROOT / "ext" / "**" / f"{fl}.csv"), recursive=True)[0]
    return next(csv.DictReader(open(f)))["date"][:10]


def main(flights):
    v = UAVVisLoc(flights)
    for fl in flights:
        fr = [f for f in v.sequences[fl] if v.map_for(f.lon, f.lat) is not None]
        lon, lat = np.array([f.lon for f in fr]), np.array([f.lat for f in fr])
        bbox = (lon.min() - PAD_DEG, lat.min() - PAD_DEG, lon.max() + PAD_DEG, lat.max() + PAD_DEG)
        fd = flight_date(fl)
        od = OUT / fl; od.mkdir(parents=True, exist_ok=True)
        idx = []
        for name, match in RULES.items():
            p = od / f"ge_{name}.tif"
            if not p.exists():
                cmd = [TOOL, "download", "-q", "-z", str(ZOOM),
                       f"--lower-left={bbox[1]:.6f},{bbox[0]:.6f}", f"--upper-right={bbox[3]:.6f},{bbox[2]:.6f}",
                       "-d", fd.replace("-", "/"), f"--date-match={match}",
                       "--co=COMPRESS=JPEG", "--co=TILED=YES", "-o", str(p)]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
                if r.returncode != 0 or not p.exists():
                    print(f"ucus {fl} {name}: HATA {r.stderr[-400:]}", flush=True)
                    continue
            import rasterio
            b = rasterio.open(p).bounds
            idx.append(dict(date=name, path=str(p), bbox=[b.left, b.bottom, b.right, b.top], flight_date=fd))
            print(f"ucus {fl} {name} ({match}, ucus {fd}) -> {p.name} {p.stat().st_size/1e6:.0f} MB", flush=True)
        json.dump(idx, open(od / "index.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or ["03", "09", "01", "06", "02", "04", "08", "05", "10"])
