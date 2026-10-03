"""RoMa (yogun, gorunum farkina dayanikli eslestirici; Edstedt vd. CVPR 2024) ile lokalizer.
LocalizationPipeline'in olcek aramasi, RANSAC ve konum hesabi AYNEN kullanilir; yalniz
nokta eslesmeleri RoMa'dan gelir (romatch paketi, 'outdoor' agirliklari).
'feats' burada goruntunun kendisi (+ gecerli-piksel maskesi)."""
import cv2
import numpy as np
import torch
from PIL import Image

from localization_pipeline import LocalizationPipeline


class RomaPipeline(LocalizationPipeline):
    NUM_SAMPLES = 3000
    MIN_CERT = 0.05

    def __init__(self, *a, coarse_res=560, upsample_res=864, **kw):
        kw.setdefault("map_max_keypoints", None)
        super().__init__(*a, **kw)
        # SuperPoint/LightGlue agirliklari yuklendi ama kullanilmayacak; GPU'dan bosalt
        self.extractor = self.map_extractor_net = self.matcher = None
        torch.cuda.empty_cache()
        from romatch import roma_outdoor
        self.roma = roma_outdoor(device=self.device, coarse_res=coarse_res, upsample_res=upsample_res,
                                 use_custom_corr=False)   # local_corr CUDA eklentisi kurulu degil
        self.roma.eval()

    def _extract(self, img_bgr, net=None):
        return {"img": img_bgr, "mask": None}

    def _query_feats(self, query_bgr, qcache, scale):
        key = round(scale, 4)
        if key not in qcache:
            h0, w0 = query_bgr.shape[:2]
            nw, nh = max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))
            q = cv2.resize(query_bgr, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            m = None
            if qcache.get("_mask") is not None:
                m = cv2.resize(qcache["_mask"], (nw, nh), interpolation=cv2.INTER_NEAREST) > 0
            qcache[key] = ({"img": q, "mask": m}, (nh, nw))
        return qcache[key]

    def _correspondences(self, feats_q, feats_m):
        qa, mb = feats_q["img"], feats_m["img"]
        if min(qa.shape[:2]) < 16 or min(mb.shape[:2]) < 16:
            return np.zeros((0, 2)), np.zeros((0, 2))
        A = Image.fromarray(cv2.cvtColor(qa, cv2.COLOR_BGR2RGB))
        B = Image.fromarray(cv2.cvtColor(mb, cv2.COLOR_BGR2RGB))
        with torch.no_grad():
            warp, cert = self.roma.match(A, B, device=self.device)
            matches, c = self.roma.sample(warp, cert, num=self.NUM_SAMPLES)
        keep = c > self.MIN_CERT
        matches = matches[keep]
        if len(matches) < 4:
            return np.zeros((0, 2)), np.zeros((0, 2))
        ka, kb = self.roma.to_pixel_coordinates(matches, qa.shape[0], qa.shape[1], mb.shape[0], mb.shape[1])
        ka, kb = ka.cpu().numpy(), kb.cpu().numpy()
        if feats_q.get("mask") is not None:
            m = feats_q["mask"]
            xi = np.clip(ka[:, 0].astype(int), 0, m.shape[1] - 1); yi = np.clip(ka[:, 1].astype(int), 0, m.shape[0] - 1)
            ok = m[yi, xi]
            ka, kb = ka[ok], kb[ok]
        return ka, kb
