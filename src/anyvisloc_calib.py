"""AnyVisLoc platform kalibrasyonu (SADECE Scene_01): y ekseni yonu ve
sanal-nadir hizalamanin dogrulugu. prior = GT, kucuk arama."""
import random
import sys

import cv2
import numpy as np

from anyvisloc_loader import AnyVisLoc
from geo_utils import haversine_m
from localization_pipeline import LocalizationPipeline, MapExtractor

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
GROUND_Z = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

pipe = LocalizationPipeline(query_rotation=None, footprint_margin_m=500.0, map_work_gsd_m=0.6,
                            map_max_keypoints=4096)
for flip in (-1,):
    a = AnyVisLoc(("01",), y_flip=flip)
    fr = a.sequences["01"]
    samp = random.Random(4).sample(fr, N)
    inl, err = [], []
    for k, f in enumerate(samp):
        img, mask, ctr, fpw, agl = a.nadir_view(f)
        pipe.QUERY_FOOTPRINT_CANDIDATES_M = tuple(fpw * k for k in (0.85, 1.0, 1.2, 1.45))
        pipe.footprint_margin_m = 0.6 * fpw
        lon, lat = a.lonlat(f)
        r = pipe.localize(img, MapExtractor(a.maps["01"]), lon, lat, 20, query_mask=mask, query_center_px=ctr)
        e = 9999 if r.predicted_lon is None else haversine_m(r.predicted_lon, r.predicted_lat, lon, lat)
        inl.append(r.inlier_count); err.append(e)
        if k == 0:
            crop, _ = MapExtractor(a.maps["01"]).crop_around(lon, lat, 300, margin_ratio=1.0)
            vis = np.hstack([cv2.resize(img, (800, 800)), cv2.resize(crop, (800, 800))])
            cv2.imwrite(f"../outputs/anyvisloc_flip{flip}.jpg", vis)
    print(f"y_flip={flip:+d}: median inlier={np.median(inl):5.0f}  median hata={np.median(err):7.1f} m  "
          f"<=10m={np.mean(np.array(err)<=10)*100:3.0f}%  <=25m={np.mean(np.array(err)<=25)*100:3.0f}%", flush=True)
