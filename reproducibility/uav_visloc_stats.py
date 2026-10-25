"""Reproduce UAV-VisLoc (Xu et al., arXiv:2405.11936) Table II and dataset counts
from the released files.

The paper has no localization experiments; its reproducible claims are the dataset
statistics: 6,742 drone images, 11 satellite maps, and per-site attributes in Table II
(image size, capture date, heading Phi, height, map size, map date, coordinate range).

Usage: python uav_visloc_stats.py [dataset_root]
"""
import csv
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:/proje/uav_vloc_datasets/UAV-VisLoc")
OUT = Path(__file__).resolve().parent / "results" / "uav_visloc_stats.json"

# Table II of the paper, row order = flight 01..11
PAPER = [
    ("Changjiang-20", "3976x2652", "2018-09", 165, 405, "9774x26762", "2023-11"),
    ("Changjiang-23", "3976x2652", "2018-09", 5, 405, "11482x34291", "2022-09"),
    ("Taizhou-1", "3976x2652", "2018-10", -40, 466, "35092x24308", "2021-04"),
    ("Taizhou-6", "3976x2652", "2018-10", 170, 542, "18093x38408", "2023-03"),
    ("Yunnan", "3000x2000", "2016-06", 100, None, "9394x6144", "2022-03"),
    ("Zhuxi", "3976x2652", "2022-10", -15, 840, "4119x8592", "2022-09"),
    ("Donghuayuan", "3000x2000", "2018-07", -1.5, 688, "3000x170", "2023-06"),
    ("Huzhou-3", "3976x2652", "2019-06", 100, 551, "43421x16294", "2023-07"),
    ("Huzhou-6", "3976x2652", "2019-06", -50, 546, "44800x33280", "2024-01"),
    ("Huailai", "3000x2000", "2018-09", 170, 772, "6593x5077", "2023-06"),
    ("Shandan", "3976x2652", "2023-10", 90, None, "29592x16582", "2021-03"),
]


def tif_size(path_or_bytes):
    im = Image.open(path_or_bytes)
    return f"{im.size[0]}x{im.size[1]}"


def fmt(v, spec):
    return format(v, spec) if v is not None else "-"


def main():
    zf = zipfile.ZipFile(ROOT / "UAV_VisLoc_dataset.zip")
    names = zf.namelist()
    drone = [n for n in names if "/drone/" in n and n.lower().endswith(".jpg")]
    sats = [n for n in names if n.lower().endswith(".tif")]
    rows = []
    for i, paper in enumerate(PAPER, start=1):
        fid = f"{i:02d}"
        with zf.open(f"{fid}/{fid}.csv") as fh:
            recs = list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")))
        imgs = [n for n in drone if n.startswith(f"{fid}/")]
        with zf.open(imgs[0]) as fh:
            im = Image.open(io.BytesIO(fh.read()))
            img_size = f"{im.size[0]}x{im.size[1]}"
        map_sizes = []
        for s in sorted(n for n in sats if n.startswith(f"{fid}/")):
            ext = ROOT / "ext" / s
            if ext.exists():
                map_sizes.append(tif_size(ext))
            else:  # read from the zip (stored, so this only touches the header region)
                with zf.open(s) as fh:
                    map_sizes.append(tif_size(io.BytesIO(fh.read())))
        heights = [float(r["height"]) for r in recs if r.get("height") not in (None, "", "nan")]
        phis = [float(r["Phi1"]) for r in recs if r.get("Phi1") not in (None, "")]
        phi2 = [float(r["Phi2"]) for r in recs if r.get("Phi2") not in (None, "")]
        dates = sorted({r["date"][:7] for r in recs if r.get("date")})
        rows.append({
            "flight": fid, "site_paper": paper[0],
            "n_csv": len(recs), "n_images": len(imgs),
            "image_size": img_size, "image_size_paper": paper[1],
            "date_months": dates, "date_paper": paper[2],
            "phi_first": phis[0] if phis else None, "phi_median": sorted(phis)[len(phis) // 2] if phis else None,
            "phi2_median": sorted(phi2)[len(phi2) // 2] if phi2 else None, "csv_columns": list(recs[0].keys()),
            "phi_paper": paper[3],
            "height_median": sorted(heights)[len(heights) // 2] if heights else None,
            "height_min": min(heights) if heights else None, "height_max": max(heights) if heights else None,
            "height_paper": paper[4],
            "map_sizes": map_sizes, "map_size_paper": paper[5], "map_date_paper": paper[6],
        })
    summary = {
        "n_drone_images": len(drone), "n_drone_images_paper": 6742,
        "n_csv_rows": sum(r["n_csv"] for r in rows),
        "n_flights": len(rows), "n_map_files": len(sats), "n_maps_paper": 11,
        "flights": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=1))
    print(f"drone images: {summary['n_drone_images']} (paper 6742); csv rows {summary['n_csv_rows']}; "
          f"map files {summary['n_map_files']} (paper 11 maps)")
    hdr = f"{'id':3} {'site':14} {'n':>5} {'img':>10}/{'paper':10} {'date':>16}/{'paper':7} {'phi1med':>7}/{'paper':>5} "\
          f"{'h_med':>6}/{'paper':>5} {'map':>24}/{'paper':12}"
    print(hdr)
    for r in rows:
        print(f"{r['flight']:3} {r['site_paper']:14} {r['n_images']:5} {r['image_size']:>10}/{r['image_size_paper']:10} "
              f"{','.join(r['date_months']):>16}/{r['date_paper']:7} {fmt(r['phi_median'], '7.1f'):>7}/{r['phi_paper']:>5} "
              f"{r['height_median'] if r['height_median'] is not None else '-':>6}/{str(r['height_paper']):>5} "
              f"{';'.join(r['map_sizes']):>24}/{r['map_size_paper']:12}")


if __name__ == "__main__":
    main()
