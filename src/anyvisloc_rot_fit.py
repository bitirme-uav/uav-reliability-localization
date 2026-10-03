"""Her kare icin en iyi (ayna + donus) aramasi; gereken donus ile euler yaw iliskisi ve
eslesmeden bulunan konum kaymasi (yerel x, y). Hava haritasina karsi."""
import io, sys, random
import numpy as np, cv2, torch
from lightglue.utils import rbd
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "03", "1", "aerial"]
import anyvisloc_axis_test as T
S = sys.argv[1]
names = sorted(n for n in T.z.namelist() if n.endswith(".npz"))
samp = random.Random(11).sample(names, 14)
print("kare        yaw   pitch  best_rot inl   dx_m   dy_m (harita px yonunde)")
for n in samp:
    d = np.load(io.BytesIO(T.z.read(n)))
    q0, half = T.nadir(d, (1, -1, -1), True, False)
    q0 = cv2.flip(q0, 1)
    m = T.crop(d["xyz"][0], d["xyz"][1], True, half + 250)
    f1 = T.feats(m); k1 = rbd(f1)["keypoints"].cpu().numpy()
    best = (0, None, None)
    for rot in range(0, 360, 15):
        q = cv2.warpAffine(q0, cv2.getRotationMatrix2D((half, half), rot, 1.0), (2 * half, 2 * half))
        f0 = T.feats(q)
        with torch.no_grad():
            mt = rbd(T.lg({"image0": f0, "image1": f1}))
        idx = mt["matches"].cpu().numpy()
        if len(idx) < 4:
            continue
        k0 = rbd(f0)["keypoints"].cpu().numpy()
        A, msk = cv2.estimateAffinePartial2D(k0[idx[:, 0]], k1[idx[:, 1]], method=cv2.RANSAC, ransacReprojThreshold=4.0)
        ni = int(msk.sum()) if msk is not None else 0
        if ni > best[0]:
            cc = A @ np.array([half, half, 1.0])
            best = (ni, rot, (cc - (half + 250)) * T.res)
    e = d["euler_deg"]
    if best[1] is None:
        print(f"{n[-12:]} {e[2]:6.1f} {e[1]:6.1f}   yok"); continue
    print(f"{n[-12:]} {e[2]:6.1f} {e[1]:6.1f}  {best[1]:6d} {best[0]:4d} {best[2][0]:7.1f} {best[2][1]:7.1f}", flush=True)
