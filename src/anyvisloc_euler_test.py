"""Euler (resmi kodun konvansiyonu) ile sanal nadir: yaw kuzeyden saat yonu, pitch nadirden.
Harita: sutun=+x (dogu), satir=+y (guney). Hava ya da uydu haritasina karsi test."""
import io, sys, random
import numpy as np, cv2, torch
from lightglue.utils import rbd
S = sys.argv[1] if len(sys.argv) > 1 else "03"; MODE = sys.argv[2] if len(sys.argv) > 2 else "aerial"
PS = int(sys.argv[3]) if len(sys.argv) > 3 else 1      # pitch isareti denemesi
sys.argv = [sys.argv[0], S, "1", MODE]
import anyvisloc_axis_test as T

def R_from_euler(roll, pitch, yaw):
    h, p = np.radians(yaw), np.radians(pitch) * PS
    f = np.array([np.sin(h), np.cos(h), 0.0]); r = np.array([np.cos(h), -np.sin(h), 0.0]); dn = np.array([0, 0, -1.0])
    x = r; y = -np.cos(p) * f + np.sin(p) * dn; z = np.cos(p) * dn + np.sin(p) * f
    R = np.stack([x, y, z], 1)                                   # kamera -> dunya (D=dogu, K=kuzey, Y=yukari)
    if roll:
        R = R @ cv2.Rodrigues(np.array([0, 0, np.radians(roll)]))[0]
    return R

def nadir_e(d, use_undist=False):
    img = cv2.cvtColor(d["image"], cv2.COLOR_RGB2BGR); K = d["K"].astype(np.float64)
    if use_undist: img = cv2.undistort(img, K, d["dist"].astype(np.float64))
    ro, pi, ya = (float(v) for v in d["euler_deg"])
    R = R_from_euler(ro, pi, ya)
    Rv = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64).T   # goruntu x=dogu, satir=guney
    x, y, zc = d["xyz"]; agl = max(zc - T.ground_z(x, y, True), 20.0); fv = agl / T.res
    half = int(min(fv * np.tan(np.radians(70)), 450))
    H = np.array([[fv, 0, half], [0, fv, half], [0, 0, 1]]) @ Rv.T @ R @ np.linalg.inv(K)
    return cv2.warpPerspective(img, H, (2 * half, 2 * half)), half

if __name__ == "__main__":
    names = sorted(n for n in T.z.namelist() if n.endswith(".npz"))
    PAD = 300
    for n in random.Random(23).sample(names, 10):
        d = np.load(io.BytesIO(T.z.read(n)))
        q, half = nadir_e(d)
        f0 = T.feats(q); f1 = T.feats(T.crop(d["xyz"][0], d["xyz"][1], True, half + PAD))
        with torch.no_grad():
            mt = rbd(T.lg({"image0": f0, "image1": f1}))
        idx = mt["matches"].cpu().numpy(); ni = 0; off = None
        if len(idx) >= 4:
            k0, k1 = rbd(f0)["keypoints"].cpu().numpy(), rbd(f1)["keypoints"].cpu().numpy()
            A, msk = cv2.estimateAffinePartial2D(k0[idx[:, 0]], k1[idx[:, 1]], method=cv2.RANSAC, ransacReprojThreshold=4.0)
            if A is not None:
                ni = int(msk.sum()); off = (A @ np.array([half, half, 1.0]) - (half + PAD)) * T.res
                sc = np.hypot(A[0, 0], A[0, 1]); rot = np.degrees(np.arctan2(A[1, 0], A[0, 0]))
        e = d["euler_deg"]
        print(f"{n[-12:]} pitch={e[1]:5.1f} yaw={e[2]:6.1f} inl={ni:3d} " +
              (f"kayma={np.hypot(*off):6.1f} m olcek={sc:.2f} don={rot:6.1f}" if off is not None and ni >= 12 else ""), flush=True)
