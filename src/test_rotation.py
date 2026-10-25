"""Hipotez: AerialVL README'sine gore kareler 'heading east', VAL haritalari
'heading north' -> aralarinda sabit bir donukluk olabilir. SuperPoint
donmeye dayanikli degil. Her donme acisi icin ayni query'lerde hata/inlier
olc."""
import random
import sys

import cv2
import numpy as np

from aerialvl_loader import AerialVLVal
from geo_utils import enu_to_lonlat_m
from localization_pipeline import LocalizationPipeline, MapExtractor, fix_error_m

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
RADIUS = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

ROT = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

val = AerialVLVal(VAL_ROOT)
cands = [f for f in val.all_frames() if val.map_for(f.lon, f.lat) is not None]
sample = random.Random(1).sample(cands, N)
pipe = LocalizationPipeline(query_rotation=None)  # donmeyi burada elle uyguluyoruz
rng = np.random.default_rng(1)
offsets = [(30 * np.cos(t), 30 * np.sin(t)) for t in rng.uniform(0, 2 * np.pi, N)]

for angle, code in ROT.items():
    errs, inl = [], []
    for q, (de, dn) in zip(sample, offsets):
        img = cv2.imread(str(q.path))
        if code is not None:
            img = cv2.rotate(img, code)
        plon, plat = enu_to_lonlat_m(de, dn, q.lon, q.lat)
        r = pipe.localize(img, MapExtractor(val.map_for(q.lon, q.lat)), plon, plat, RADIUS)
        e = fix_error_m(r.predicted_lon, r.predicted_lat, q.lon, q.lat)
        errs.append(e if e is not None else 9999.0)
        inl.append(r.inlier_count)
    errs = np.array(errs)
    print(f"rot={angle:3d}  median_err={np.median(errs):7.1f}m  <=10m={np.sum(errs<=10):2d}/{N}  "
          f"<=25m={np.sum(errs<=25):2d}/{N}  ort_inlier={np.mean(inl):5.1f}", flush=True)
