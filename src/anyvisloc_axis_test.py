"""AnyVisLoc koordinat/kamera konvansiyonu testi -- HAVA haritasina karsi (alan farki yok).
Her kombinasyon icin: egik kare -> sanal nadir (dogrudan yerel harita cercevesinde),
harita kesitiyle SuperPoint+LightGlue, RANSAC inlier sayisi ve merkez kaymasi.
Kullanim: python anyvisloc_axis_test.py SAHNE [kare_sayisi] [aerial|satellite]"""
import io
import json
import random
import sys
import zipfile

import cv2
import numpy as np
import torch
from lightglue import LightGlue, SuperPoint
from lightglue.utils import rbd

D = "/media/davut/disk2/proje/uav_vloc_datasets/AnyVisLoc/"
S = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
MODE = sys.argv[3] if len(sys.argv) > 3 else "aerial"
j = json.load(open(f"{D}ext/{S}/Scene_{S}/L{S}_reference.json"))["modes"][MODE]
RED = max(1, min(8, 2 ** int(np.floor(np.log2(0.6 / j["map_resolution"][0])))))   # ~0.6 m/px calisma
res = j["map_resolution"][0] * RED
ox, oy = j["map_origin_local"]
flag = {8: cv2.IMREAD_REDUCED_COLOR_8, 4: cv2.IMREAD_REDUCED_COLOR_4, 2: cv2.IMREAD_REDUCED_COLOR_2, 1: cv2.IMREAD_COLOR}[RED]
A = cv2.imread(f"{D}ext/{S}/Scene_{S}/{MODE}_map.png", flag)
dsm = np.load(f"{D}ext/{S}/Scene_{S}/{MODE}_dsm.npy"); dres = j["dsm_resolution"][0]
dox, doy = ox + j["dsm_origin_local"][0], oy + j["dsm_origin_local"][1]
valid = dsm[(dsm > -1000) & (dsm < 9000)]; zmed = float(np.median(valid))
dev = "cuda" if torch.cuda.is_available() else "cpu"
ext = SuperPoint(max_num_keypoints=2048).eval().to(dev)
lg = LightGlue(features="superpoint").eval().to(dev)


def feats(img):
    t = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)).float()[None, None].to(dev) / 255
    with torch.no_grad():
        return ext.extract(t)


def ground_z(x, y, rows_down):
    c = int((x - dox) / dres); r = int((y - doy) / dres)
    if not rows_down:
        r = dsm.shape[0] - 1 - int((y - doy) / dres)
    if 0 <= r < dsm.shape[0] and 0 <= c < dsm.shape[1] and -1000 < dsm[r, c] < 9000:
        return float(dsm[r, c])
    return zmed


def nadir(d, cam_axes, rows_down, undist):
    img = cv2.cvtColor(d["image"], cv2.COLOR_RGB2BGR)
    K = d["K"].astype(np.float64)
    if undist:
        img = cv2.undistort(img, K, d["dist"].astype(np.float64))
    R = d["pose_c2w"][:3, :3].astype(np.float64) @ np.diag(cam_axes)
    # sanal kamera eksenleri (dunya cercevesinde): goruntu x = +x yerel; goruntu satiri = +y (rows_down) ya da -y
    Rv = np.array([[1, 0, 0], [0, 1 if rows_down else -1, 0], [0, 0, -1]], dtype=np.float64).T
    x, y, zc = d["xyz"]
    agl = max(zc - ground_z(x, y, rows_down), 20.0)
    # cikti olcegi = harita cozunurlugu: fv = agl / res  -> 1 px = res m
    fv = agl / res
    half = int(min(fv * np.tan(np.radians(60)), 400))
    Kv = np.array([[fv, 0, half], [0, fv, half], [0, 0, 1]])
    H = Kv @ Rv.T @ R @ np.linalg.inv(K)
    out = cv2.warpPerspective(img, H, (2 * half, 2 * half))
    m = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), H, (2 * half, 2 * half))
    out[m == 0] = 0
    return out, half


def crop(x, y, rows_down, R):
    c = int((x - ox) / res)
    r = int((y - oy) / res) if rows_down else A.shape[0] - 1 - int((y - oy) / res)
    out = np.zeros((2 * R, 2 * R, 3), np.uint8)
    r0, c0 = r - R, c - R
    a = A[max(r0, 0):r + R, max(c0, 0):c + R]
    out[max(0, -r0):max(0, -r0) + a.shape[0], max(0, -c0):max(0, -c0) + a.shape[1]] = a
    return out


z = zipfile.ZipFile(f"{D}Scene_{S}.zip")
names = sorted(n for n in z.namelist() if n.endswith(".npz"))
samp = random.Random(5).sample(names, N)
ROT = [int(v) for v in sys.argv[4].split(",")] if len(sys.argv) > 4 else [0]
MIR = [False, True] if len(ROT) > 1 else [False]
combos = [(ax, rd, ud, rot, mir) for ax in ((1, -1, -1),) for rd in (True,) for ud in (False,) for rot in ROT for mir in MIR] \
    if len(ROT) > 1 else [(ax, rd, ud, 0, False) for ax in ((1, -1, -1), (1, 1, 1)) for rd in (True, False) for ud in (False,)]
for ax, rd, ud, rot, mir in combos:
    inl, off = [], []
    for n in samp:
        d = np.load(io.BytesIO(z.read(n)))
        q, half = nadir(d, ax, rd, ud)
        if mir:
            q = cv2.flip(q, 1)
        if rot:
            q = cv2.warpAffine(q, cv2.getRotationMatrix2D((half, half), rot, 1.0), (2 * half, 2 * half))
        m = crop(d["xyz"][0], d["xyz"][1], rd, half + 150)
        f0, f1 = feats(q), feats(m)
        with torch.no_grad():
            mt = rbd(lg({"image0": f0, "image1": f1}))
        k0, k1 = rbd(f0)["keypoints"].cpu().numpy(), rbd(f1)["keypoints"].cpu().numpy()
        idx = mt["matches"].cpu().numpy()
        if len(idx) < 4:
            inl.append(0); off.append(np.nan); continue
        p0, p1 = k0[idx[:, 0]], k1[idx[:, 1]]
        T, msk = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=4.0)
        ni = int(msk.sum()) if msk is not None else 0
        inl.append(ni)
        if T is not None and ni >= 15:
            cc = T @ np.array([half, half, 1.0])
            off.append(np.hypot(cc[0] - (half + 150), cc[1] - (half + 150)) * res)
        else:
            off.append(np.nan)
    print(f"{MODE} eksen={ax} satir_asagi={rd} don={rot} ayna={mir}: inlier={inl}  median kayma={np.nanmedian(off) if np.isfinite(off).any() else float('nan'):.1f} m",
          flush=True)
