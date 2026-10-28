"""AerialVL (He et al., RA-L 2024) Table III: one-stage VPR with MSLS-trained models of the
deep-visual-geo-localization-benchmark (Berton et al., CVPR 2022, ref. [33] of the paper).

Queries: query_images_1..4 (18,361), names @lon@lat@.png.
Database: map_database/level_1..3 (14,096 tiles), names @map@LBlon@LBlat@RTlon@RTlat@.png;
the tile position is the centre of its corners. Positions are converted to UTM 51N.
A retrieval is correct if a top-N tile lies within 50 m / 100 m of the query (Recall@N).
Features are extracted once per model; both thresholds are computed from the same ranking.
Images are read directly from the split VPR.zip.0xx parts, without joining or extracting them.

Place this file in a clone of gmberton/deep-visual-geo-localization-benchmark (@ 4af5194).
usage: python avl_vpr.py --backbone resnet50conv4 --aggregation gem --resume w/resnet50_gem.pth
"""
import io, json, os, time, zipfile
from os.path import join, basename
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from sklearn.neighbors import NearestNeighbors
import faiss
from pyproj import Transformer

import parser as vg_parser
import util
from model import network

PARTS = sorted(__import__("glob").glob(os.environ.get("AVL_VPR_PARTS", "/tmp/aerialvl/VPR.zip.0??")))
OUT = os.environ.get("AVL_VPR_OUT", "/kaggle/working/avl_vpr_results")


class SplitFile(io.RawIOBase):
    """Read-only view of a raw-split zip (VPR.zip.001 ... .036) as one seekable file."""

    def __init__(self, parts):
        self.f = [open(p, "rb") for p in parts]
        self.off = np.concatenate([[0], np.cumsum([os.path.getsize(p) for p in parts])])
        self.pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, o, whence=0):
        self.pos = o if whence == 0 else (self.pos + o if whence == 1 else int(self.off[-1]) + o)
        return self.pos

    def readinto(self, b):
        n, done = len(b), 0
        while done < n and self.pos < self.off[-1]:
            k = int(np.searchsorted(self.off, self.pos, side="right") - 1)
            self.f[k].seek(self.pos - int(self.off[k]))
            chunk = self.f[k].read(min(n - done, int(self.off[k + 1]) - self.pos))
            b[done:done + len(chunk)] = chunk
            done += len(chunk)
            self.pos += len(chunk)
        return done


def open_zip():
    return zipfile.ZipFile(io.BufferedReader(SplitFile(PARTS), 1 << 20))


def positions():
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)
    names = open_zip().namelist()
    db = sorted(n for n in names if n.startswith("map_database/level_") and n.endswith(".png"))
    q = sorted(n for n in names if n.startswith("query_images/query_images_") and n.endswith(".png"))
    dll = np.array([[float(v) for v in basename(p).split("@")[2:6]] for p in db])
    dlon, dlat = (dll[:, 0] + dll[:, 2]) / 2, (dll[:, 1] + dll[:, 3]) / 2
    qll = np.array([[float(v) for v in basename(p).split("@")[1:3]] for p in q])
    dxy = np.stack(tr.transform(dlon, dlat), 1)
    qxy = np.stack(tr.transform(qll[:, 0], qll[:, 1]), 1)
    return db, q, dxy, qxy


class DS(torch.utils.data.Dataset):
    def __init__(self, names, resize):
        self.n = names
        self.z = None  # one ZipFile handle per worker
        self.t = T.Compose([T.Resize(resize, antialias=True), T.ToTensor(),
                            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])

    def __len__(self):
        return len(self.n)

    def __getitem__(self, i):
        if self.z is None:
            self.z = open_zip()
        im = Image.open(io.BytesIO(self.z.read(self.n[i]))).convert("RGB")
        return self.t(im), i


def extract(model, names, args):
    dl = torch.utils.data.DataLoader(DS(names, args.resize), batch_size=args.infer_batch_size,
                                     num_workers=4, pin_memory=True)
    out = np.empty((len(names), args.features_dim), dtype=np.float32)
    with torch.no_grad():
        for x, i in dl:
            out[i.numpy()] = model(x.to(args.device)).cpu().numpy()
    return out


def main():
    args = vg_parser.parse_arguments()
    tag = basename(args.resume).replace(".pth", "")
    model = network.GeoLocalizationNet(args).to(args.device)
    if args.aggregation in ["netvlad", "crn"]:
        args.features_dim *= args.netvlad_clusters
    model = util.resume_model(args, model).eval()
    db, q, dxy, qxy = positions()
    print(tag, "db", len(db), "queries", len(q), flush=True)
    t0 = time.time()
    fd = extract(model, db, args)
    fq = extract(model, q, args)
    t2 = time.time()
    index = faiss.IndexFlatL2(args.features_dim)
    index.add(fd)
    _, pred = index.search(fq, 20)
    res = {"model": tag, "backbone": args.backbone, "aggregation": args.aggregation,
           "resize": args.resize, "n_db": len(db), "n_q": len(q),
           "ms_per_image": round(1000 * (t2 - t0) / (len(db) + len(q)), 2)}
    knn = NearestNeighbors(n_jobs=-1).fit(dxy)
    for thr in (50, 100):
        pos = knn.radius_neighbors(qxy, radius=thr, return_distance=False)
        has = np.array([len(p) > 0 for p in pos])
        for n in (1, 5, 10, 20):
            hit = [np.any(np.isin(pred[i, :n], pos[i])) for i in range(len(q))]
            res[f"R@{n}_{thr}m"] = round(100 * float(np.mean(hit)), 1)
        res[f"queries_without_positive_{thr}m"] = int((~has).sum())
    print(json.dumps(res), flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(join(OUT, f"{tag}_{args.resize[0]}x{args.resize[1]}.json"), "w"), indent=1)
    np.save(join(OUT, f"{tag}_pred.npy"), pred.astype(np.int32))


if __name__ == "__main__":
    main()
