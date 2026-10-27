"""Sensitivity checks on the released SUE (tudelft-iv/SUE @ 24bdae5), St Lucia pickle.
1) clipping as released: min(500, d) caps only positive offsets; symmetric clip(d, -500, 500)
2) slope and number of neighbours

Run next to st_luciatest_cvprcameraready.pickle (from the SUE repo via Git LFS).
The pickle is third-party data; it was opened only on the Kaggle VM, not on a team machine.
"""
import pickle, json
import numpy as np
from sklearn.metrics import precision_recall_curve, auc

with open('st_luciatest_cvprcameraready.pickle', 'rb') as h:
    L = [pickle.load(h) for _ in range(7)]
    q_mu, db_mu, q_sig, db_sig, preds, dists, gt = L
    for _ in range(3): pickle.load(h)
    ref_poses = pickle.load(h)

y = np.array([1.0 if np.any(np.in1d(p[:1], gt[i])) else 0.0 for i, p in enumerate(preds)])
def aucpr(s):
    p, r, _ = precision_recall_curve(y, s); return round(float(auc(r, p)), 4)

def sue(num_nn=10, slope=350, clip="released", cap=500.0):
    out = np.zeros(len(preds))
    for i in range(len(preds)):
        nn = ref_poses[preds[i][:num_nn]]
        w = np.exp(-np.abs(np.asarray(dists[i][:num_nn], float)) * slope); w = w / w.sum()
        m = np.average(nn[:, :2], axis=0, weights=w)
        d = nn[:, :2] - m
        if clip == "released": d = np.minimum(cap, d)
        elif clip == "symmetric": d = np.clip(d, -cap, cap)
        out[i] = np.sum(w[:, None] * d ** 2) / 2
    return -out

res = {"n_queries": int(len(y)), "top1_correct_%": round(100 * y.mean(), 2),
       "L2": aucpr(-np.array([d[0] for d in dists]))}
res["SUE_released"] = aucpr(sue())
res["SUE_symmetric_clip"] = aucpr(sue(clip="symmetric"))
res["SUE_no_clip"] = aucpr(sue(clip="none"))
res["slope"] = {s: aucpr(sue(slope=s)) for s in (0, 50, 100, 200, 350, 500, 1000)}
res["num_nn"] = {k: aucpr(sue(num_nn=k)) for k in (2, 3, 5, 10)}
# offsets beyond +-500 m around the mean pose (the released clip touches only the positive side)
neg = pos = 0
for i in range(len(preds)):
    nn = ref_poses[preds[i][:10]][:, :2]; d = nn - nn.mean(0)
    pos += int((d > 500).sum()); neg += int((d < -500).sum())
res["offsets_gt_500m"] = pos; res["offsets_lt_minus500m"] = neg
print(json.dumps(res, indent=1))
json.dump(res, open('sue_check.json', 'w'), indent=1)
