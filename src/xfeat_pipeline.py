"""XFeat (Potje vd. CVPR 2024; hafif, gomulu cihaz icin tasarlanmis) ile lokalizer.
Olcek aramasi / RANSAC / konum hesabi LocalizationPipeline ile ayni; eslesmeler XFeat'ten."""
import cv2
import numpy as np
import torch

from roma_pipeline import RomaPipeline
from localization_pipeline import LocalizationPipeline


class XFeatPipeline(RomaPipeline):
    TOP_K = 4096

    def __init__(self, *a, **kw):
        kw.setdefault("map_max_keypoints", None)
        LocalizationPipeline.__init__(self, *a, **kw)
        self.extractor = self.map_extractor_net = self.matcher = None
        torch.cuda.empty_cache()
        self.xfeat = torch.hub.load("verlab/accelerated_features", "XFeat", pretrained=True, top_k=self.TOP_K,
                                    trust_repo=True)

    def _correspondences(self, feats_q, feats_m):
        qa, mb = feats_q["img"], feats_m["img"]
        if min(qa.shape[:2]) < 16 or min(mb.shape[:2]) < 16:
            return np.zeros((0, 2)), np.zeros((0, 2))
        try:
            with torch.no_grad():
                ka, kb = self.xfeat.match_xfeat(cv2.cvtColor(qa, cv2.COLOR_BGR2RGB), cv2.cvtColor(mb, cv2.COLOR_BGR2RGB),
                                                top_k=self.TOP_K)
        except (IndexError, RuntimeError):   # hic anahtar nokta yok (bos/tekduze bolge) -> eslesme yok
            return np.zeros((0, 2)), np.zeros((0, 2))
        ka, kb = np.asarray(ka, float), np.asarray(kb, float)
        if len(ka) and feats_q.get("mask") is not None:
            m = feats_q["mask"]
            xi = np.clip(ka[:, 0].astype(int), 0, m.shape[1] - 1); yi = np.clip(ka[:, 1].astype(int), 0, m.shape[0] - 1)
            ok = m[yi, xi]; ka, kb = ka[ok], kb[ok]
        return ka, kb
