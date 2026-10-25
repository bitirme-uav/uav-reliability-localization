"""Query goruntusu + (ground-truth merkezli) harita crop'unu yan yana
kaydeder -- gozle kontrol icin. Bu, otomatik metriklerin yeterince
acikliga kavusturamadigi bir noktada (eslesme neden zayif?) dogrudan
gorsel dogrulama saglar."""
import random
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aerialvl_loader import AerialVLVal
from localization_pipeline import MapExtractor

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")

val = AerialVLVal(VAL_ROOT)
candidates = [f for f in val.all_frames() if val.map_for(f.lon, f.lat) is not None]
rng = random.Random(1)
sample = rng.sample(candidates, 4)

fig, axes = plt.subplots(4, 2, figsize=(12, 20))
for i, query in enumerate(sample):
    geo_map = val.map_for(query.lon, query.lat)
    query_img = cv2.imread(str(query.path))
    query_rgb = cv2.cvtColor(query_img, cv2.COLOR_BGR2RGB)

    map_extractor = MapExtractor(geo_map)
    # GERCEK ground-truth merkezli crop (prior hatasi YOK) -- eger bu bile
    # gorsel olarak eslesmiyor gozukuyorsa sorun crop/koordinat tarafinda,
    # eslestirme algoritmasi tarafinda degil.
    map_crop, window = map_extractor.crop_around(query.lon, query.lat, 60.0)
    map_rgb = cv2.cvtColor(map_crop, cv2.COLOR_BGR2RGB)

    axes[i, 0].imshow(query_rgb)
    axes[i, 0].set_title(f"QUERY {query.path.name}\n{query_img.shape}")
    axes[i, 1].imshow(map_rgb)
    axes[i, 1].set_title(f"HARITA CROP (GT-merkezli, r=60m)\n{map_crop.shape} @ {geo_map.name}")

fig.tight_layout()
fig.savefig("../outputs/debug_visual.png", dpi=100)
print("kaydedildi: outputs/debug_visual.png")
