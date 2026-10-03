"""M2: Görsel lokalizasyon temel pipeline'ı.

    query image
      -> prior-merkezli arama bölgesi içinde harita crop'u al
      -> SuperPoint + LightGlue ile eşleştir
      -> RANSAC (homografi) ile geometrik doğrulama
      -> harita pikseli -> lon/lat -> metrik (ENU) fix
      -> ham güven sinyalleri (M4)

NOT (Ay-1 basitleştirmesi, ileride genişletilecek): M2/M7'nin tam
"coarse-to-fine tile retrieval" adımı (arama bölgesi içindeki BİRDEN
FAZLA aday karo arasından top-K seçme) henüz burada YOK. Şu an, prior
+ arama yarıçapından TEK bir crop üretiliyor (retrieval adımının
"top-1 = tek aday" dejenere hali). top1_score/top1_top2_margin bu
yüzden şimdilik None dönüyor -- gerçek çoklu-aday retrieval eklenince
doldurulacak. Bu basitleştirme raporlarda AÇIKÇA belirtilmeli.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import rasterio
import rasterio.transform
import torch
from rasterio.windows import Window
from lightglue import LightGlue, SuperPoint
from lightglue.utils import numpy_image_to_torch, rbd

from geo_utils import enu_to_lonlat_m, haversine_m


@dataclass
class RawLocalizationResult:
    predicted_lon: float | None
    predicted_lat: float | None
    num_matches: int
    inlier_count: int
    inlier_ratio: float
    reprojection_error_px: float | None
    inlier_spatial_spread: float | None
    transform_condition: float | None
    localization_latency_ms: float
    # ham confidence: basitce inlier_ratio kullanılıyor (M5.1 "raw confidence
    # -- one direct score, e.g. inlier ratio or top-1 similarity")
    raw_confidence: float
    # M4: query/reference GSD orani -- cok-olcekli aramada en iyi sonucu
    # veren aday (query_gsd_m / map_gsd_m). Tek-olcekli cagrilarda None.
    query_ref_scale_ratio: float | None = None
    # tahmin edilen donusumun icindeki donme acisi (derece, query->harita)
    rotation_deg: float | None = None
    # ikinci-en-iyi RANSAC hipotezinin inlier sayisi (top1-top2 margin icin)
    second_inlier_count: int = 0
    # arama bolgesi yuklu haritanin tamamen disinda kaldiysa True
    out_of_map: bool = False
    # karolu aramada (M2 coarse retrieval): en iyi / farkli-yerdeki ikinci en iyi karo skoru
    retrieval_top1: int | None = None
    retrieval_top2: int | None = None
    n_tiles: int = 0

    @property
    def top1_top2_margin(self) -> float | None:
        if self.inlier_count <= 0:
            return None
        return (self.inlier_count - self.second_inlier_count) / self.inlier_count


class MapExtractor:
    """Bir GeoTIFF haritanın pixel<->lonlat dönüşümünü ve crop'larını yönetir.

    ÖNEMLİ: AerialVL'nin @map@LTLon@LTLat@RBLon@RBLat@.tif dosyaları
    GENELDE gömülü GeoTIFF etiketi TAŞIMAZ (düz RGB TIFF, coğrafi bilgi
    SADECE dosya adında). Bu yüzden rasterio'nun kendi `ds.transform`'una
    GÜVENMİYORUZ -- affine dönüşümü, README'de tanımlanan 'maps are
    heading north' (north-up, sol-üst köşe=LT) kuralına göre dosya
    adından ayrıştırılan sınırlardan (GeoMap) MANUEL kuruyoruz. Bu, TIFF
    içinde yanlış/eksik/hiç geotransform olmasından tamamen bağımsız,
    garanti doğru bir sonuç verir.
    """

    def __init__(self, geo_map, tif_path: str | Path | None = None):
        """geo_map: aerialvl_loader.GeoMap (dosya adından ayrıştırılmış sınırlar).
        tif_path verilmezse geo_map.path kullanılır (genelde aynı şey)."""
        self.geo_map = geo_map
        self.path = Path(tif_path) if tif_path is not None else Path(geo_map.path)
        self._ds = rasterio.open(self.path)
        self.width = self._ds.width
        self.height = self._ds.height
        # north-up: satir 0 = en kuzey (lt_lat=lat_max), sutun 0 = en bati (lt_lon=lon_min)
        self.transform = rasterio.transform.from_bounds(
            geo_map.lon_min, geo_map.lat_min, geo_map.lon_max, geo_map.lat_max,
            self.width, self.height,
        )

    def lonlat_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        col, row = ~self.transform * (lon, lat)
        return col, row

    def pixel_to_lonlat(self, col: float, row: float) -> tuple[float, float]:
        lon, lat = self.transform * (col, row)
        return lon, lat

    MIN_CROP_PX = 1  # NOT: MIN_CROP_PX>1 (400/700 px) ve MIN_QUERY_PX ile yapilan
    # canli denemeler (bkz. PROGRESS_RAPORU.md) TUTARLI SEKILDE daha kotu
    # sonuc verdi (median hata 40m -> 127-204m). Gecici olarak devre disi
    # birakildi (deger=1, pratikte etkisiz) -- kok neden (kucuk crop'larin
    # neden daha iyi calistigini) HENUZ ANLAŞILMADI, ileride arastirilmali.

    def crop_around(self, lon: float, lat: float, radius_m: float, margin_ratio: float = 1.5) -> tuple[np.ndarray, Window]:
        """prior (lon,lat) etrafında, en az 'radius_m' yarıçapı kapsayan bir
        crop döndürür (BGR uint8, cv2 uyumlu) + kullanılan rasterio Window.

        Piksel boyutu MIN_CROP_PX'in altına düşmez (küçük search_radius'ta
        bile) -- çok küçük crop'lar SuperPoint için dejenere/anlamsız
        keypoint sayılarına yol açıyordu (canlı testte tespit edildi,
        bkz. debug_bias.py bulguları).
        """
        # yaklaşık derece/metre oranı (küçük bölge, equirectangular yeterli)
        lat_rad = np.radians(lat)
        deg_per_m_lat = 1.0 / 111320.0
        deg_per_m_lon = 1.0 / (111320.0 * max(np.cos(lat_rad), 1e-6))
        half_w_deg = radius_m * margin_ratio * deg_per_m_lon
        half_h_deg = radius_m * margin_ratio * deg_per_m_lat

        col_c, row_c = self.lonlat_to_pixel(lon, lat)
        col_half = max(half_w_deg / abs(self.transform.a), self.MIN_CROP_PX / 2.0)
        row_half = max(half_h_deg / abs(self.transform.e), self.MIN_CROP_PX / 2.0)

        col0 = max(0, int(col_c - col_half))
        row0 = max(0, int(row_c - row_half))
        col1 = min(self.width, int(col_c + col_half))
        row1 = min(self.height, int(row_c + row_half))
        # harita kenarinda kirpilip seride donusen pencereler de gecersiz
        # (SuperPoint en az birkac pooling katmani kadar boyut ister)
        if col1 - col0 < 64 or row1 - row0 < 64:
            raise ValueError("crop penceresi harita disinda kaldi")

        window = Window(col0, row0, col1 - col0, row1 - row0)
        arr = self._ds.read([1, 2, 3], window=window)  # (3,H,W) RGB varsayimi
        img = np.transpose(arr, (1, 2, 0))
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img_bgr, window

    def crop_pixel_to_map_pixel(self, window: Window, col_in_crop: float, row_in_crop: float) -> tuple[float, float]:
        return window.col_off + col_in_crop, window.row_off + row_in_crop


class LocalizationPipeline:
    # AerialVL README: kareler 'heading east', VAL haritalari 'heading north'.
    # SuperPoint donmeye dayanikli olmadigi icin query'yi haritanin
    # yonelimine getirmek sart -- test_rotation.py: 90° CW ile ortalama
    # inlier 7 -> 282, median hata 53m -> 12.6m.
    DEFAULT_QUERY_ROTATION = cv2.ROTATE_90_CLOCKWISE

    def __init__(self, device: str | None = None, max_keypoints: int = 2048,
                 query_rotation: int | None = DEFAULT_QUERY_ROTATION,
                 transform_model: str = "similarity", ransac_thresh_px: float = 4.0,
                 footprint_candidates_m: tuple[float, ...] | None = None):
        self.query_rotation = query_rotation
        self.transform_model = transform_model
        self.ransac_thresh_px = ransac_thresh_px
        if footprint_candidates_m is not None:
            self.QUERY_FOOTPRINT_CANDIDATES_M = tuple(footprint_candidates_m)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.extractor = SuperPoint(max_num_keypoints=max_keypoints).eval().to(self.device)
        self.matcher = LightGlue(features="superpoint").eval().to(self.device)

    def _extract(self, img_bgr: np.ndarray) -> dict:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        tensor = numpy_image_to_torch(img_rgb).to(self.device)
        with torch.no_grad():
            feats = self.extractor.extract(tensor)
        return feats

    # AerialVL'de irtifa/EXIF/GSD bilgisi YOK, query'nin gercek footprint'i
    # bilinmiyor -> cok-olcekli arama: query birkac aday footprint
    # varsayimiyla olceklenip her birinde eslestirilir, en cok inlier veren
    # olcek secilir (query_ref_scale_ratio, M4 ozelligi).
    # (Bu aralik donme duzeltmesinden SONRA tune_m2.py ile yeniden
    # karsilastirildi; daha dar araliklar belirgin fark yaratmadi.)
    QUERY_FOOTPRINT_CANDIDATES_M = (40.0, 80.0, 160.0, 320.0, 640.0)
    MIN_QUERY_PX = 1

    # M2 'coarse retrieval over tiles': arama yaricapi bu esigi asarsa bolge
    # karolara bolunur. Tek parca buyuk crop'ta (r=400m) eslestirme cokuyordu
    # (VAL: median 322m), r<=150m'de iyi calisiyor (median ~9m).
    TILE_THRESHOLD_M = 150.0
    TILE_RADIUS_M = 120.0
    COARSE_FOOTPRINTS_M = (80.0, 160.0)   # tune_m2'de en sik secilen olcekler
    DISTINCT_HYPOTHESIS_M = 50.0          # top1/top2 karsilastirmasinda "farkli yer" esigi

    def localize(self, query_bgr: np.ndarray, map_extractor: MapExtractor,
                 prior_lon: float, prior_lat: float, search_radius_m: float) -> RawLocalizationResult:
        t0 = time.monotonic()
        if self.query_rotation is not None:
            query_bgr = cv2.rotate(query_bgr, self.query_rotation)
        qcache: dict = {}
        if search_radius_m > self.TILE_THRESHOLD_M:
            res = self._localize_tiled(query_bgr, qcache, map_extractor, prior_lon, prior_lat, search_radius_m)
        else:
            res = self._localize_single(query_bgr, qcache, map_extractor, prior_lon, prior_lat,
                                        search_radius_m, self.QUERY_FOOTPRINT_CANDIDATES_M)
        res.localization_latency_ms = (time.monotonic() - t0) * 1000.0
        return res

    def _query_feats(self, query_bgr, qcache, scale):
        key = round(scale, 4)
        if key not in qcache:
            h0, w0 = query_bgr.shape[:2]
            nw, nh = max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))
            q = cv2.resize(query_bgr, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            qcache[key] = (self._extract(q), (nh, nw))
        return qcache[key]

    def _localize_single(self, query_bgr, qcache, map_extractor, prior_lon, prior_lat,
                         search_radius_m, footprints) -> RawLocalizationResult:
        try:
            map_crop, window = map_extractor.crop_around(prior_lon, prior_lat, search_radius_m)
        except ValueError:
            # OUT_OF_MAP: arama bolgesi yuklu haritanin tamamen disinda
            # (dokuman: tespit et, drift-only devam et, ayri raporla)
            res = RawLocalizationResult(None, None, 0, 0, 0.0, None, None, None, 0.0, 0.0)
            res.out_of_map = True
            return res
        map_gsd_m = abs(map_extractor.transform.a) * 111320.0 * np.cos(np.radians(prior_lat))
        h_q0, w_q0 = query_bgr.shape[:2]
        feats_m = self._extract(map_crop)

        best, best_inl, best_scale = None, -1, None
        for footprint_m in footprints:
            scale = (footprint_m / w_q0) / map_gsd_m
            scale = float(np.clip(max(scale, self.MIN_QUERY_PX / min(w_q0, h_q0)), 0.02, 3.0))
            feats_q, qshape = self._query_feats(query_bgr, qcache, scale)
            r = self._match_and_verify(feats_q, qshape, feats_m, map_extractor, window)
            if r.inlier_count > best_inl:
                best, best_inl, best_scale = r, r.inlier_count, scale
        best.query_ref_scale_ratio = best_scale
        return best

    def _localize_tiled(self, query_bgr, qcache, map_extractor, prior_lon, prior_lat,
                        search_radius_m) -> RawLocalizationResult:
        tr = self.TILE_RADIUS_M
        step = 1.5 * tr
        n = int(np.ceil(search_radius_m / step))
        coarse = []
        for ix in range(-n, n + 1):
            for iy in range(-n, n + 1):
                de, dn = ix * step, iy * step
                if np.hypot(de, dn) > search_radius_m + 0.5 * tr:
                    continue
                lon, lat = enu_to_lonlat_m(de, dn, prior_lon, prior_lat)
                r = self._localize_single(query_bgr, qcache, map_extractor, lon, lat, tr,
                                          self.COARSE_FOOTPRINTS_M)
                if r.predicted_lon is not None:
                    coarse.append((r.inlier_count, r, lon, lat))
        if not coarse:
            res = RawLocalizationResult(None, None, 0, 0, 0.0, None, None, None, 0.0, 0.0)
            res.out_of_map = True
            return res
        coarse.sort(key=lambda c: -c[0])
        top_inl, top_r, _, _ = coarse[0]
        # retrieval margin: en iyi karo ile FARKLI bir yeri gosteren en iyi karo
        second = 0
        for inl, r, _, _ in coarse[1:]:
            d = haversine_m(r.predicted_lon, r.predicted_lat, top_r.predicted_lon, top_r.predicted_lat)
            if d > self.DISTINCT_HYPOTHESIS_M:
                second = inl
                break
        # ince asama: en iyi karonun tahmini etrafinda tam cok-olcekli eslestirme
        final = self._localize_single(query_bgr, qcache, map_extractor, top_r.predicted_lon, top_r.predicted_lat,
                                      tr, self.QUERY_FOOTPRINT_CANDIDATES_M)
        if final.predicted_lon is None:
            final = top_r
        final.retrieval_top1 = top_inl
        final.retrieval_top2 = second
        final.n_tiles = len(coarse)
        return final

    def _match_and_verify(self, feats_q: dict, qshape: tuple[int, int], feats_m: dict,
                          map_extractor: MapExtractor, window: Window) -> RawLocalizationResult:
        with torch.no_grad():
            matches01 = self.matcher({"image0": feats_q, "image1": feats_m})
        feats_q_, feats_m_, matches01 = (rbd(x) for x in (feats_q, feats_m, matches01))
        matches = matches01["matches"]  # (N,2) idx into kpts0/kpts1
        kpts_q = feats_q_["keypoints"]
        kpts_m = feats_m_["keypoints"]

        num_matches = int(matches.shape[0])
        if num_matches < 4:
            return RawLocalizationResult(None, None, num_matches, 0, 0.0, None, None, None, 0.0, 0.0)

        pts_q = kpts_q[matches[:, 0]].cpu().numpy()
        pts_m = kpts_m[matches[:, 1]].cpu().numpy()

        # transform_model: "similarity" (4 DOF, az inlier'da stabil) veya
        # "homography" (8 DOF, perspektifi de modeller; bol inlier gerekir).
        M, inlier_mask = self._ransac(pts_q, pts_m)
        if M is None:
            return RawLocalizationResult(None, None, num_matches, 0, 0.0, None, None, None, 0.0, 0.0)

        inlier_mask = inlier_mask.ravel().astype(bool)
        inlier_count = int(inlier_mask.sum())
        inlier_ratio = inlier_count / max(num_matches, 1)

        # Ikinci-en-iyi geometrik hipotez: birinci hipotezin inlier'lari
        # cikarilip kalan eslesmelerde tekrar RANSAC. Belirsizlik sinyali
        # (top1-top2 margin, M4) -- tek-crop'ta coklu-karo retrieval'in
        # yerine gecen, ayni anlami tasiyan olcu.
        rest = ~inlier_mask
        second_inliers = 0
        if rest.sum() >= 4:
            _, m2 = self._ransac(pts_q[rest], pts_m[rest])
            if m2 is not None:
                second_inliers = int(m2.ravel().astype(bool).sum())

        proj = _apply_transform(M, pts_q[inlier_mask])
        errs = np.linalg.norm(proj - pts_m[inlier_mask], axis=1)
        reproj_err = float(np.mean(errs)) if len(errs) else None

        inlier_spread = float(np.std(pts_m[inlier_mask], axis=0).mean()) if inlier_count > 1 else None
        # transform_condition: lineer kismin (donme+olcek[+kayma]) kosul sayisi
        # -- buyuk deger dejenere/gurultulu tahmine isaret eder.
        try:
            transform_cond = float(np.linalg.cond(M[:2, :2]))
        except np.linalg.LinAlgError:
            transform_cond = None

        # query goruntusunun merkezi (nadir varsayimi) -> harita crop pikseli
        h_q, w_q = qshape
        center_m = _apply_transform(M, np.array([[w_q / 2.0, h_q / 2.0]]))
        col_crop, row_crop = float(center_m[0, 0]), float(center_m[0, 1])

        col_map, row_map = map_extractor.crop_pixel_to_map_pixel(window, col_crop, row_crop)
        pred_lon, pred_lat = map_extractor.pixel_to_lonlat(col_map, row_map)

        return RawLocalizationResult(
            predicted_lon=pred_lon, predicted_lat=pred_lat,
            num_matches=num_matches, inlier_count=inlier_count, inlier_ratio=inlier_ratio,
            reprojection_error_px=reproj_err, inlier_spatial_spread=inlier_spread,
            transform_condition=transform_cond, localization_latency_ms=0.0,
            raw_confidence=inlier_ratio,
            rotation_deg=float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))),
            second_inlier_count=second_inliers,
        )

    def _ransac(self, pts_q: np.ndarray, pts_m: np.ndarray):
        # "similarity" (4 DOF, az inlier'da stabil) veya "homography" (8 DOF)
        if self.transform_model == "homography":
            return cv2.findHomography(pts_q, pts_m, cv2.RANSAC,
                                      ransacReprojThreshold=self.ransac_thresh_px, confidence=0.999)
        return cv2.estimateAffinePartial2D(pts_q, pts_m, method=cv2.RANSAC,
                                           ransacReprojThreshold=self.ransac_thresh_px, confidence=0.999)


def _apply_transform(M: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """2x3 (affine/similarity) veya 3x3 (homografi) donusumu Nx2 noktalara uygular."""
    pts_h = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
    out = (M @ pts_h.T).T
    if M.shape[0] == 3:
        out = out[:, :2] / out[:, 2:3]
    return out


def fix_error_m(pred_lon: float | None, pred_lat: float | None, gt_lon: float, gt_lat: float) -> float | None:
    if pred_lon is None or pred_lat is None:
        return None
    return haversine_m(pred_lon, pred_lat, gt_lon, gt_lat)
