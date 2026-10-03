"""Tum kamera-ekseni isaret kombinasyonlari x R / R^T x sanal-kamera y isareti, ek donus YOK.
Hava haritasina karsi inlier sayisi ve merkez kaymasi."""
import io, sys, random, itertools
import numpy as np, cv2, torch
from lightglue.utils import rbd
S = sys.argv[1] if len(sys.argv) > 1 else "03"
sys.argv = [sys.argv[0], S, "1", "aerial"]
import anyvisloc_axis_test as T

def nadir(d, ax, transpose, vy):
    img = cv2.cvtColor(d["image"], cv2.COLOR_RGB2BGR); K = d["K"].astype(np.float64)
    R0 = d["pose_c2w"][:3, :3].astype(np.float64)
    R = (R0.T if transpose else R0) @ np.diag(ax)
    if R[2] @ np.array([0, 0, 1.0]) > 0:   # optik eksen (+z kamera) yukari bakiyorsa gecersiz
        return None, 0
    Rv = np.array([[1, 0, 0], [0, vy, 0], [0, 0, -1]], dtype=np.float64).T
    x, y, zc = d["xyz"]; agl = max(zc - T.ground_z(x, y, True), 20.0); fv = agl / T.res
    half = int(min(fv * np.tan(np.radians(60)), 400))
    H = np.array([[fv, 0, half], [0, fv, half], [0, 0, 1]]) @ Rv.T @ R @ np.linalg.inv(K)
    out = cv2.warpPerspective(img, H, (2 * half, 2 * half))
    return out, half

names = sorted(n for n in T.z.namelist() if n.endswith(".npz"))
samp = [np.load(io.BytesIO(T.z.read(n))) for n in random.Random(11).sample(names, 6)]
PAD = 300
crops = [(T.feats(T.crop(d["xyz"][0], d["xyz"][1], True, 400 + PAD))) for d in samp]
res = []
for ax in itertools.product((1, -1), repeat=3):
    for tr in (False, True):
        for vy in (1, -1):
            inl, off = [], []
            for d, f1 in zip(samp, crops):
                q, half = nadir(d, ax, tr, vy)
                if q is None:
                    inl.append(-1); continue
                f0 = T.feats(q)
                with torch.no_grad():
                    mt = rbd(T.lg({"image0": f0, "image1": f1}))
                idx = mt["matches"].cpu().numpy()
                if len(idx) < 4:
                    inl.append(0); continue
                k0, k1 = rbd(f0)["keypoints"].cpu().numpy(), rbd(f1)["keypoints"].cpu().numpy()
                A, msk = cv2.estimateAffinePartial2D(k0[idx[:, 0]], k1[idx[:, 1]], method=cv2.RANSAC, ransacReprojThreshold=4.0)
                ni = int(msk.sum()) if msk is not None else 0; inl.append(ni)
                if ni >= 15:
                    # crop merkezi = 400+PAD; harita kesiti ile ayni 'half' degil -> merkez farki
                    cc = A @ np.array([half, half, 1.0]); off.append(np.hypot(*(cc - (400 + PAD))) * T.res)
            res.append((np.median([max(i, 0) for i in inl]), ax, tr, vy, inl, np.median(off) if off else np.nan))
for r in sorted(res, key=lambda r: -r[0])[:8]:
    print(f"eksen={r[1]} R^T={r[2]} vy={r[3]}: inlier={r[4]} median kayma={r[5]:.1f} m")
