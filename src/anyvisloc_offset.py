import io, sys, random
import numpy as np, cv2, torch
from lightglue.utils import rbd
S = sys.argv[1] if len(sys.argv) > 1 else "03"
sys.argv = [sys.argv[0], S, "1", "aerial"]
import anyvisloc_axis_test as T
from anyvisloc_conv_search import nadir
names = sorted(n for n in T.z.namelist() if n.endswith(".npz"))
PAD = 400
for name, ax, tr, vy in (("A", (1, -1, -1), True, -1), ("B", (1, 1, -1), False, 1)):
    print("kombinasyon", name)
    for n in random.Random(23).sample(names, 8):
        d = np.load(io.BytesIO(T.z.read(n)))
        q, half = nadir(d, ax, tr, vy)
        f0 = T.feats(q); f1 = T.feats(T.crop(d["xyz"][0], d["xyz"][1], True, 400 + PAD))
        with torch.no_grad():
            mt = rbd(T.lg({"image0": f0, "image1": f1}))
        idx = mt["matches"].cpu().numpy()
        k0, k1 = rbd(f0)["keypoints"].cpu().numpy(), rbd(f1)["keypoints"].cpu().numpy()
        A, msk = cv2.estimateAffinePartial2D(k0[idx[:, 0]], k1[idx[:, 1]], method=cv2.RANSAC, ransacReprojThreshold=4.0)
        ni = int(msk.sum())
        cc = (A @ np.array([half, half, 1.0]) - (400 + PAD)) * T.res      # harita: +x sutun, +y satir
        sc = np.hypot(A[0, 0], A[0, 1]); rot = np.degrees(np.arctan2(A[1, 0], A[0, 0]))
        R0 = d["pose_c2w"][:3, :3]; fwd = -R0[:, 2] if name == "A" else R0[:, 2]
        h = np.degrees(np.arctan2(fwd[1], fwd[0]))
        e = d["euler_deg"]
        print(f"  {n[-12:]} inl={ni:3d} kayma=({cc[0]:7.1f},{cc[1]:7.1f}) |{np.hypot(*cc):6.1f}| aci={np.degrees(np.arctan2(cc[1],cc[0])):7.1f}"
              f"  bakis_yonu(yerel)={h:7.1f} yaw={e[2]:6.1f} pitch={e[1]:5.1f} z={d['xyz'][2]:5.0f} olcek={sc:.2f} don={rot:6.1f}", flush=True)
