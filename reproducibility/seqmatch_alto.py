"""Re-implementation of Wang et al. (2024), "Sequence Matching for Image-Based
UAV-to-Satellite Geolocalization", IEEE TGRS 62, on the ALTO set the paper evaluates.

The authors' code site (seqmatch.geovisuallocalization.com) is not reachable, so the
method is re-implemented from Sec. III and IV-B of the paper:
  1. ImageNet AlexNet features of the satellite patches (images resized to 256x256).
  2. ISOMAP (k = 3 neighbours, Floyd shortest paths, classical MDS) to 1-D; sorting the
     1-D value recovers the order of the patches (Algorithm 1). Metric: S-ACC (Eq. 9-10).
  3. Sequence matching: the UAV frame at t is matched with LoFTR (pretrained outdoor
     weights, no fine-tuning) against the M = 10 satellite patches that follow the patch
     matched at t-1; a RANSAC homography maps the UAV image centre P into each patch and
     the patch with the smallest g(m) = ||P - H_m P|| is the result (Eq. 8).
     Candidates are ranked by g(m) for R@K; mAP uses the rank of the single ground-truth patch.

Experiments (subcommands):
  sort      Table IV (ISOMAP / PCA / t-SNE) and Fig. 13 (k sweep) with AlexNet features
  extractors  Table V (S-ACC per ImageNet backbone)
  match     Table I "Ours" row (R@1, R@5, mAP)

ALTO data: the local "Val" folder (1684 UAV / 459 satellite images) corresponds to the
split the paper calls "test" (1683 UAV / 458 satellite images).
"""
import argparse
import csv
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(os.environ.get("ALTO_ROOT", r"D:/proje/uav_vloc_datasets/ALTO/Val"))
OUT = Path(__file__).resolve().parent / "results"
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def load_refs():
    with open(ROOT / "reference.csv") as fh:
        rows = [r for r in csv.DictReader(fh) if r["name"].startswith("offset_0_None/")]
    return rows  # file order == route order


def load_queries():
    with open(ROOT / "gt_matches.csv") as fh:
        gt = list(csv.DictReader(fh))
    return gt


# ---------------------------------------------------------------- features
def backbone(name):
    import torchvision.models as tvm
    # AlexNet/VGG: the convolutional trunk (pool5, flattened). With fc7 (classifier minus its
    # last layer) ISOMAP only reaches S-ACC ~0.7 on ALTO; with pool5 it reaches the paper's 0.99,
    # so the paper's "AlexNet feature" is taken to be the convolutional one.
    if name in ("alexnet", "alexnet_fc7"):
        m = tvm.alexnet(weights="IMAGENET1K_V1")
        m.classifier = m.classifier[:-1] if name == "alexnet_fc7" else torch.nn.Identity()
    elif name == "vgg16":
        m = tvm.vgg16(weights="IMAGENET1K_V1")
        m.classifier = torch.nn.Identity()
    elif name in ("resnet18", "resnet50", "resnet101"):
        m = getattr(tvm, name)(weights="IMAGENET1K_V1")
        m.fc = torch.nn.Identity()
    elif name == "densenet121":
        m = tvm.densenet121(weights="IMAGENET1K_V1")
        m.classifier = torch.nn.Identity()
    elif name == "convnext_tiny":
        m = tvm.convnext_tiny(weights="IMAGENET1K_V1")
        m.classifier[-1] = torch.nn.Identity()
    elif name == "vit_b_16":
        m = tvm.vit_b_16(weights="IMAGENET1K_V1")
        m.heads = torch.nn.Identity()
    else:
        raise ValueError(name)
    return m.eval().to(DEV)


def extract(name, paths, size=256):
    from torchvision import transforms as T
    size = 224 if name == "vit_b_16" else size  # ViT-B/16 needs a 224 input
    tf = T.Compose([T.Resize((size, size)), T.ToTensor(),
                    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    m = backbone(name)
    feats = []
    with torch.no_grad():
        for i in range(0, len(paths), 32):
            x = torch.stack([tf(Image.open(p).convert("RGB")) for p in paths[i:i + 32]]).to(DEV)
            feats.append(m(x).flatten(1).float().cpu())
    return torch.cat(feats).numpy()


def cached_features(name, paths):
    f = OUT / "cache" / f"alto_ref_{name}.npy"
    if f.exists():
        return np.load(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    x = extract(name, paths)
    np.save(f, x)
    return x


# ---------------------------------------------------------------- sorting
def isomap_1d(F, k=3):
    """Algorithm 1: kNN graph -> Floyd-Warshall -> double centring -> top eigenvector."""
    from scipy.sparse.csgraph import shortest_path
    from scipy.spatial.distance import cdist
    D = cdist(F, F)
    N = len(F)
    A = np.full((N, N), np.inf)
    nn = np.argsort(D, 1)[:, 1:k + 1]
    for i in range(N):
        A[i, nn[i]] = D[i, nn[i]]
        A[nn[i], i] = D[i, nn[i]]
    np.fill_diagonal(A, 0)
    DG = shortest_path(A, method="FW", directed=False)
    if np.isinf(DG).any():  # disconnected graph: classical ISOMAP would fail, keep it finite
        DG[np.isinf(DG)] = DG[np.isfinite(DG)].max() * 2
    H = np.eye(N) - np.ones((N, N)) / N
    K = -0.5 * H @ (DG ** 2) @ H
    w, V = np.linalg.eigh(K)
    return V[:, -1] * np.sqrt(max(w[-1], 0))


def pca_1d(F):
    from sklearn.decomposition import PCA
    return PCA(1).fit_transform(F)[:, 0]


def tsne_1d(F, seed=0):
    from sklearn.manifold import TSNE
    return TSNE(1, random_state=seed, init="pca").fit_transform(F)[:, 0]


def sort_order(v, ids):
    """Sorted sequence of true ids (ids[i] = true id of item i). The 1-D embedding has an
    arbitrary sign, so the direction that agrees better with the route is kept."""
    pred = ids[np.argsort(v)]
    ref = np.arange(len(ids))
    return pred if (pred == ref).mean() >= (pred[::-1] == ref).mean() else pred[::-1]


def s_acc(v, ids):
    """Eq. (9)-(10): fraction of sequence positions i whose predicted id equals i."""
    return float((sort_order(v, ids) == np.arange(len(ids))).mean())


def shuffled(F, seed=0):
    perm = np.random.default_rng(seed).permutation(len(F))
    return F[perm], perm  # perm[i] = true id of shuffled item i


def cmd_sort(a):
    refs = load_refs()
    paths = [ROOT / "reference_images" / r["name"] for r in refs]
    F = cached_features("alexnet", paths)
    Fs, perm = shuffled(F, a.seed)
    res = {"n": len(F), "isomap_k3": s_acc(isomap_1d(Fs, 3), perm),
           "pca": s_acc(pca_1d(Fs), perm), "tsne": s_acc(tsne_1d(Fs, a.seed), perm)}
    res["k_sweep"] = {k: s_acc(isomap_1d(Fs, k), perm) for k in range(2, 13)}
    errs = sort_order(isomap_1d(Fs, 3), perm) - np.arange(len(F))
    res["sort_error_hist"] = {int(e): int((errs == e).sum()) for e in np.unique(errs)}
    res["paper"] = {"isomap": 0.990, "pca": 0.004, "tsne": 0.004,
                    "k_sweep": "flat for k in [3,8] per text; drops for k > 6 per text/Fig. 13",
                    "sort_error_hist": {"-1": 2, "0": 455, "1": 2}}
    save("seqmatch_sort.json", res)


def cmd_extractors(a):
    refs = load_refs()
    paths = [ROOT / "reference_images" / r["name"] for r in refs]
    paper = {"alexnet": 0.99, "vgg16": 0.67, "resnet18": 0.71, "resnet50": 0.57, "resnet101": None,
             "densenet121": 0.67, "convnext_tiny": 0.36, "vit_b_16": 0.07}
    res = {}
    for name in a.models.split(","):
        F = cached_features(name, paths)
        Fs, perm = shuffled(F, a.seed)
        res[name] = {"s_acc": s_acc(isomap_1d(Fs, 3), perm), "paper": paper.get(name), "dim": int(F.shape[1])}
        print(name, res[name], flush=True)
    save("seqmatch_extractors.json", res)


# ---------------------------------------------------------------- matching
class Matcher:
    def __init__(self, size=256):
        import kornia.feature as KF
        self.m = KF.LoFTR(pretrained="outdoor").eval().to(DEV)
        self.size = size
        self.cache = {}

    def gray(self, path):
        if path not in self.cache:
            im = Image.open(path).convert("L").resize((self.size, self.size))
            self.cache[path] = torch.from_numpy(np.asarray(im, np.float32) / 255.0)[None, None]
            if len(self.cache) > 4000:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[path]

    def g(self, q, r):
        import cv2
        with torch.no_grad():
            out = self.m({"image0": self.gray(q).to(DEV), "image1": self.gray(r).to(DEV)})
        k0, k1 = out["keypoints0"].cpu().numpy(), out["keypoints1"].cpu().numpy()
        if len(k0) < 4:
            return np.inf, len(k0), 0
        Hm, inl = cv2.findHomography(k0, k1, cv2.RANSAC, 5.0)
        if Hm is None:
            return np.inf, len(k0), 0
        P = np.array([self.size / 2, self.size / 2, 1.0])
        Pm = Hm @ P
        if abs(Pm[2]) < 1e-9:
            return np.inf, len(k0), int(inl.sum())
        return float(np.linalg.norm(P[:2] - Pm[:2] / Pm[2])), len(k0), int(inl.sum())


def cmd_match(a):
    refs = load_refs()
    gt = load_queries()
    ref_paths = [ROOT / "reference_images" / r["name"] for r in refs]
    n_ref = len(refs)
    if a.order == "isomap":  # satellite sequence recovered by Algorithm 1 from shuffled patches
        F = cached_features("alexnet", ref_paths)
        Fs, perm = shuffled(F, a.seed)
        order = sort_order(isomap_1d(Fs, 3), perm)
    else:
        order = np.arange(n_ref)
    pos = {int(r): i for i, r in enumerate(order)}  # ref id -> position in the sequence
    mt = Matcher(a.size)
    j = pos[int(gt[0]["ref_ind"])]  # known start: the patch of the first UAV frame
    recs, t0 = [], time.time()
    qs = gt[: a.limit] if a.limit else gt
    for t, row in enumerate(qs):
        # paper: {I_s^j, ..., I_s^(j+m)} (forward only, back = 0); back > 0 is our sensitivity variant
        lo = max(0, j - a.back)
        cand = [order[p] for p in range(lo, min(lo + a.M, n_ref))]
        scores = []
        for r in cand:
            g, nm, ni = mt.g(ROOT / "query_images" / row["query_name"], ref_paths[r])
            scores.append((g, int(r), nm, ni))
        ranked = sorted(scores, key=lambda s: s[0])
        best = ranked[0][1]
        if np.isfinite(ranked[0][0]):
            j = pos[best]
        true = int(row["ref_ind"])
        ids = [s[1] for s in ranked]
        rank = ids.index(true) + 1 if true in ids else None
        recs.append({"t": t, "gt": true, "pred": best, "rank": rank, "g": ranked[0][0],
                     "n_matches": ranked[0][2], "inliers": ranked[0][3]})
        if t % 100 == 0:
            print(t, len(qs), f"{time.time() - t0:.0f}s", summary(recs), flush=True)
    res = {"order": a.order, "M": a.M, "size": a.size, "back": a.back, **summary(recs),
           "paper_ours": {"R@1": 41.63, "R@5": 99.11, "mAP": 69.42}, "seconds": time.time() - t0}
    tag = a.order + ("" if (a.size, a.back) == (256, 0) else f"_s{a.size}_b{a.back}")
    save(f"seqmatch_match_{tag}.json", res)
    with open(OUT / f"seqmatch_match_{tag}.jsonl", "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def summary(recs):
    ranks = [r["rank"] for r in recs]
    n = len(ranks)
    return {"n": n,
            "R@1": round(100 * sum(1 for r in ranks if r and r <= 1) / n, 2),
            "R@5": round(100 * sum(1 for r in ranks if r and r <= 5) / n, 2),
            "mAP": round(100 * sum(1 / r for r in ranks if r) / n, 2),
            "pred_within_1_patch": round(100 * sum(abs(r["pred"] - r["gt"]) <= 1 for r in recs) / n, 2)}


def save(name, res):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["sort", "extractors", "match"])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--models", default="alexnet,alexnet_fc7,vgg16,resnet18,resnet50,resnet101,densenet121,convnext_tiny,vit_b_16")
    p.add_argument("--order", choices=["isomap", "true"], default="isomap")
    p.add_argument("--M", type=int, default=10)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--size", type=int, default=256, help="LoFTR input size (ALTO patches are 500x500)")
    p.add_argument("--back", type=int, default=0, help="candidate window starts this many patches behind j")
    a = p.parse_args()
    {"sort": cmd_sort, "extractors": cmd_extractors, "match": cmd_match}[a.cmd](a)
