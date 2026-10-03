import io, sys, random
import numpy as np, cv2, torch
from lightglue.utils import rbd
S = sys.argv[1] if len(sys.argv) > 1 else "03"
COMBO = sys.argv[2] if len(sys.argv) > 2 else "B"
sys.argv = [sys.argv[0], S, "1", "aerial"]
import anyvisloc_axis_test as T

def rodrigues(axis, deg):
    return cv2.Rodrigues(np.asarray(axis, float) / np.linalg.norm(axis) * np.radians(deg))[0]

def nadir_R(d, R, half_max=400):
    img = cv2.cvtColor(d["image"], cv2.COLOR_RGB2BGR); K = d["K"].astype(np.float64)
    Rv = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]], dtype=np.float64).T
    x, y, zc = d["xyz"]; agl = max(zc - T.ground_z(x, y, True), 20.0); fv = agl / T.res
    half = int(min(fv * np.tan(np.radians(60)), half_max))
    H = np.array([[fv, 0, half], [0, fv, half], [0, 0, 1]]) @ Rv.T @ R @ np.linalg.inv(K)
    return cv2.warpPerspective(img, H, (2 * half, 2 * half)), half

def base_R(d):
    R0 = d["pose_c2w"][:3, :3].astype(np.float64)
    return R0 @ np.diag((1, 1, -1)) if COMBO == "B" else R0.T @ np.diag((1, -1, -1))

def match(q, half, f1, PAD):
    f0 = T.feats(q)
    with torch.no_grad():
        mt = rbd(T.lg({"image0": f0, "image1": f1}))
    idx = mt["matches"].cpu().numpy()
    if len(idx) < 4: return 0, None
    k0, k1 = rbd(f0)["keypoints"].cpu().numpy(), rbd(f1)["keypoints"].cpu().numpy()
    A, msk = cv2.estimateAffinePartial2D(k0[idx[:, 0]], k1[idx[:, 1]], method=cv2.RANSAC, ransacReprojThreshold=4.0)
    if A is None: return 0, None
    return int(msk.sum()), (A @ np.array([half, half, 1.0]) - (400 + PAD)) * T.res

names = sorted(n for n in T.z.namelist() if n.endswith(".npz"))
PAD = 400
for n in random.Random(23).sample(names, 10):
    d = np.load(io.BytesIO(T.z.read(n)))
    if d["euler_deg"][1] < 15: continue
    R = base_R(d)
    oa = R[:, 2]                         # optik eksen (dunya)
    h_ax = np.cross(oa, [0, 0, 1.0])     # yatay, optik eksene dik -> egiklik ekseni
    f1 = T.feats(T.crop(d["xyz"][0], d["xyz"][1], True, 400 + PAD))
    best = []
    for dt in range(-60, 61, 5):
        q, half = nadir_R(d, rodrigues(h_ax, dt) @ R)
        ni, off = match(q, half, f1, PAD)
        best.append((ni, dt, off))
    ni, dt, off = max(best, key=lambda b: b[0])
    nad = np.degrees(np.arccos(-oa[2]))
    print(f"{n[-12:]} pitch={d['euler_deg'][1]:5.1f} optik-eksen-nadir-acisi={nad:5.1f}  en iyi dtilt={dt:+4d} inl={ni:3d} "
          f"kayma={'-' if off is None else f'{np.hypot(*off):6.1f}'}", flush=True)
