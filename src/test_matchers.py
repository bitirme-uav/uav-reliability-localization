"""Eslestirici karsilastirmasi (SADECE TUNE ucuslari 05,10). Prior = GT,
kucuk arama; her eslestirici icin ayni kesit/olcekler. Amac: gorunum
farkina dayanikli eslestirici secmek."""
import random
import sys
import time

import cv2
import kornia.feature as KF
import numpy as np
import torch
from lightglue import ALIKED, DISK, LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd

from localization_pipeline import MapExtractor, _rotate_expand, _filter_feats_by_mask, _apply_transform
from geo_utils import haversine_m
from visloc_loader import UAVVisLoc
from visloc_splits import TUNE_FLIGHTS

N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
GSD = 0.8
FOOTPRINTS = (250, 400, 600)
dev = "cuda"

v = UAVVisLoc(list(TUNE_FLIGHTS))
items = [f for fl in TUNE_FLIGHTS for f in v.sequences[fl]]
sample = random.Random(5).sample(items, N)

lg = {}
for name, ext_cls, kp in (("superpoint", SuperPoint, 2048), ("aliked", ALIKED, 2048), ("disk", DISK, 2048)):
    lg[name] = (ext_cls(max_num_keypoints=kp).eval().to(dev), ext_cls(max_num_keypoints=4096).eval().to(dev),
                LightGlue(features=name).eval().to(dev))
loftr = KF.LoFTR(pretrained="outdoor").eval().to(dev)


def ransac(p0, p1):
    if len(p0) < 4:
        return None, 0
    M, m = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=4.0, confidence=0.999)
    return M, (0 if m is None else int(m.sum()))


def match_lg(name, q, qmask, m):
    eq, em, mt = lg[name]
    with torch.no_grad():
        fq = eq.extract(numpy_image_to_torch(cv2.cvtColor(q, cv2.COLOR_BGR2RGB)).to(dev))
        fq = _filter_feats_by_mask(fq, qmask)
        fm = em.extract(numpy_image_to_torch(cv2.cvtColor(m, cv2.COLOR_BGR2RGB)).to(dev))
        out = mt({"image0": fq, "image1": fm})
    fq, fm, out = rbd(fq), rbd(fm), rbd(out)
    mm = out["matches"]
    return fq["keypoints"][mm[:, 0]].cpu().numpy(), fm["keypoints"][mm[:, 1]].cpu().numpy()


def match_loftr(q, qmask, m):
    def prep(img, maxside):
        s = min(1.0, maxside / max(img.shape[:2]))
        g = cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        h, w = (g.shape[0] // 8) * 8, (g.shape[1] // 8) * 8
        return torch.from_numpy(g[:h, :w]).float()[None, None].to(dev) / 255.0, s
    tq, sq = prep(q, 640)
    tm, sm = prep(m, 1024)
    with torch.no_grad():
        out = loftr({"image0": tq, "image1": tm})
    k0, k1, c = out["keypoints0"].cpu().numpy(), out["keypoints1"].cpu().numpy(), out["confidence"].cpu().numpy()
    k0, k1 = k0 / sq, k1 / sm
    keep = c > 0.3
    xy = k0[keep].round().astype(int)
    xy[:, 0] = xy[:, 0].clip(0, qmask.shape[1] - 1); xy[:, 1] = xy[:, 1].clip(0, qmask.shape[0] - 1)
    ok = qmask[xy[:, 1], xy[:, 0]] > 0
    return k0[keep][ok], k1[keep][ok]


res = {k: [] for k in ("superpoint", "aliked", "disk", "loftr")}
tim = {k: 0.0 for k in res}
for q in sample:
    img = v.image(q)
    me = MapExtractor(v.map_for(q.lon, q.lat))
    crop, win = me.crop_around(q.lon, q.lat, 20, extra_m=max(FOOTPRINTS) / 2 + 60)
    map_gsd = abs(me.transform.a) * 111320 * np.cos(np.radians(q.lat))
    cs = map_gsd / GSD
    crop = cv2.resize(crop, None, fx=cs, fy=cs, interpolation=cv2.INTER_AREA)
    rot, mask = _rotate_expand(img, -q.yaw_deg)
    for meth in res:
        t = time.monotonic()
        best = (0, None)
        for fp in FOOTPRINTS:
            s = (fp / img.shape[1]) / GSD
            qs = cv2.resize(rot, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            qm = cv2.resize(mask, (qs.shape[1], qs.shape[0]), interpolation=cv2.INTER_NEAREST)
            p0, p1 = match_loftr(qs, qm, crop) if meth == "loftr" else match_lg(meth, qs, qm, crop)
            M, n = ransac(p0, p1)
            if M is not None and n > best[0]:
                c = _apply_transform(M, np.array([[qs.shape[1] / 2, qs.shape[0] / 2]]))[0] / cs
                lon, lat = me.pixel_to_lonlat(win.col_off + c[0], win.row_off + c[1])
                best = (n, haversine_m(lon, lat, q.lon, q.lat))
        tim[meth] += time.monotonic() - t
        res[meth].append(best)
    print(q.path, " ".join(f"{k}:{r[-1][0]}/{(r[-1][1] or 9999):.0f}m" for k, r in res.items()), flush=True)

print("\n=== ozet (TUNE ucuslari, prior=GT) ===")
for k, r in res.items():
    e = np.array([x[1] if x[1] is not None else 9999 for x in r]); n = np.array([x[0] for x in r])
    print(f"{k:11s} median_inlier={np.median(n):5.0f}  <=10m={np.mean(e<=10)*100:4.0f}%  <=25m={np.mean(e<=25)*100:4.0f}%  "
          f"median_hata={np.median(e):7.1f}m  sure/kare={tim[k]/len(r):.2f}s")
