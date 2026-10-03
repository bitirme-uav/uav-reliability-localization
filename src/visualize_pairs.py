"""Ay-1 çıkış kriteri: '≥20 query/map pair'i harita üzerinde görselleştir'.

Kullanım:
    python visualize_pairs.py <VAL_kok_dizini> [--n 25] [--out outputs/pairs.png]

Her query karesinin (dosya adından çıkarılan ground-truth lon/lat)
ilgili haritanın (geo_referenced_map) sınırları içinde doğru yere
düştüğünü GÖRSEL olarak doğrular -- doküman notu (gpt.md): "Dataset
düzgün okunuyor mu, koordinat sistemi doğru mu, görüntü gerçekten
haritadaki doğru yere düşüyor mu?" Bu, projenin temelinin sağlam
olup olmadığının ilk ve en önemli kontrolü.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import rasterio

from aerialvl_loader import AerialVLVal, Frame


def plot_pairs(val: AerialVLVal, frames: list[Frame], out_path: Path) -> None:
    n_maps = len(val.maps)
    fig, axes = plt.subplots(1, max(n_maps, 1), figsize=(8 * max(n_maps, 1), 8))
    if n_maps <= 1:
        axes = [axes]

    seq_names = sorted({f.sequence for f in frames})
    cmap = plt.cm.get_cmap("tab20", max(len(seq_names), 1))
    seq_color = {s: cmap(i) for i, s in enumerate(seq_names)}

    for ax, geo_map in zip(axes, val.maps):
        try:
            with rasterio.open(geo_map.path) as ds:
                # buyuk raster'i thumbnail'a indirerek goster (bellek icin)
                thumb = ds.read(
                    out_shape=(ds.count, min(ds.height, 1500), min(ds.width, 1500)),
                )
                img = np.transpose(thumb[:3], (1, 2, 0))
                extent = [geo_map.lon_min, geo_map.lon_max, geo_map.lat_min, geo_map.lat_max]
                ax.imshow(img, extent=extent, origin="upper" if geo_map.lt_lat > geo_map.rb_lat else "lower")
        except Exception as e:
            ax.set_facecolor("#eeeeee")
            ax.text(0.5, 0.5, f"harita okunamadi:\n{e}", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlim(geo_map.lon_min, geo_map.lon_max)
            ax.set_ylim(geo_map.lat_min, geo_map.lat_max)

        in_this_map = [f for f in frames if geo_map.contains(f.lon, f.lat)]
        for f in in_this_map:
            ax.scatter(f.lon, f.lat, s=14, color=seq_color[f.sequence], edgecolors="k", linewidths=0.3)
        ax.set_title(f"{geo_map.name} -- {len(in_this_map)}/{len(frames)} query burada")
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")

    handles = [mpatches.Patch(color=seq_color[s], label=s) for s in seq_names]
    fig.legend(handles=handles, loc="lower center", ncol=min(len(seq_names), 6), fontsize=7)
    fig.suptitle(f"AerialVL VAL -- {len(frames)} query/map çifti görselleştirmesi")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    print(f"kaydedildi: {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("val_root")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--out", default="outputs/query_map_pairs.png")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    val = AerialVLVal(args.val_root)
    print(val.summary())

    all_frames = val.all_frames()
    if not all_frames:
        print("HATA: hic kare bulunamadi -- VAL_kok_dizini dogru mu?", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(args.seed)
    n = min(args.n, len(all_frames))
    sample = rng.sample(all_frames, n)

    n_outside = sum(1 for f in sample if val.map_for(f.lon, f.lat) is None)
    print(f"\n{n} query seçildi, {n_outside}/{n} tanesi HİÇBİR haritanın sınırları içinde DEĞİL "
          f"(0 olmalı -- aksi halde koordinat sistemi/harita eşleşmesi sorunu var demektir).")

    plot_pairs(val, sample, Path(args.out))


if __name__ == "__main__":
    main()
