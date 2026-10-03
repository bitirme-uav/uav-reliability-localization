"""M5.4 (calibrated reliability) + M10/§10 değerlendirme metrikleri.

Doküman notu (M5.4): "logistic regression, isotonic/Platt calibration,
or a shallow gradient-boosted model. A tiny MLP only if simpler models
fail." Burada varsayılan: LogisticRegression + isotonic kalibrasyon
(sklearn CalibratedClassifierCV). Büyük bir ağ YOK.

M4 label-leakage kuralı burada da geçerli: `fit()`'e verilen X, SADECE
runtime'da gerçekten mevcut olan ham sinyalleri (inlier_ratio,
num_matches, reprojection_error, margin, mahalanobis_d, ...) içermeli;
y ise SADECE M3'ün ground-truth-only etiketi (safe_primary).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# M4'te tanımlı, sızıntısız (ground-truth İÇERMEYEN) aday özellik seti.
# Gercek veriyle calisirken mevcut olmayan alanlar (None) satir bazinda
# atilir / imputed edilir -- bu dosyada basit "mevcut olanları kullan"
# yaklaşımı var.
DEFAULT_FEATURES = [
    "num_matches", "inlier_count", "inlier_ratio", "reprojection_error_px",
    "inlier_spatial_spread", "transform_condition", "top1_top2_margin",
    "mahalanobis_d",
]


@dataclass
class CalibrationMetrics:
    auroc: float
    auprc: float
    brier: float
    ece: float
    n: int


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Standart ECE: olasılık [0,1]'i n_bins eşit aralığa böl, her binde
    |ortalama tahmin - gerçek pozitif oranı| ağırlıklı ortalaması."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        if not np.any(mask):
            continue
        bin_acc = float(np.mean(y_true[mask]))
        bin_conf = float(np.mean(y_prob[mask]))
        ece += (np.sum(mask) / n) * abs(bin_acc - bin_conf)
    return float(ece)


def risk_coverage_curve(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Güveni azalan sırayla kapsam artırıp, kapsanan altkümedeki hata
    (risk = 1 - accept edilenler arasindaki safe orani) oranını döner.
    (coverage[i], risk[i]) -- en güvenilirden başlayarak kümülatif.
    """
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]
    n = len(y_true)
    coverage = np.arange(1, n + 1) / n
    cum_safe = np.cumsum(y_sorted)
    risk = 1.0 - cum_safe / np.arange(1, n + 1)
    return coverage, risk


# Sayim/olcek turu, cok genis aralikli ozellikler log1p ile sikistirilir.
LOG_FEATURES = {"num_matches", "inlier_count", "top1_score", "transform_condition",
                "reprojection_error_px", "inlier_spatial_spread", "mahalanobis_d"}

VISUAL_FEATURES = [
    "num_matches", "inlier_count", "inlier_ratio", "reprojection_error_px",
    "inlier_spatial_spread", "transform_condition", "top1_top2_margin", "query_ref_scale_ratio",
]
VISUAL_PLUS_MAHALANOBIS = VISUAL_FEATURES + ["mahalanobis_d"]


class ReliabilityModel:
    def __init__(self, features: list[str] | None = None, calibration: str = "isotonic",
                 base: str = "logreg"):
        self.features = features or DEFAULT_FEATURES
        self.calibration = calibration
        if base == "gbm":
            from sklearn.ensemble import HistGradientBoostingClassifier
            clf = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05)
        else:
            clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        self._base = make_pipeline(StandardScaler(), clf)
        self._model = None

    def _to_matrix(self, rows: list[dict]) -> np.ndarray:
        X = np.zeros((len(rows), len(self.features)))
        for i, r in enumerate(rows):
            for j, f in enumerate(self.features):
                v = r.get(f)
                v = 0.0 if v is None or not np.isfinite(v) else float(v)
                X[i, j] = np.log1p(max(v, 0.0)) if f in LOG_FEATURES else v
        return X

    def fit(self, rows: list[dict], y_safe: np.ndarray) -> "ReliabilityModel":
        X = self._to_matrix(rows)
        if self.calibration in ("isotonic", "sigmoid"):
            self._model = CalibratedClassifierCV(self._base, method=self.calibration, cv=5)
        else:
            self._model = self._base
        self._model.fit(X, y_safe)
        return self

    def predict_proba(self, rows: list[dict]) -> np.ndarray:
        X = self._to_matrix(rows)
        return self._model.predict_proba(X)[:, 1]

    def evaluate(self, rows: list[dict], y_safe: np.ndarray) -> CalibrationMetrics:
        p = self.predict_proba(rows)
        return CalibrationMetrics(
            auroc=float(roc_auc_score(y_safe, p)),
            auprc=float(average_precision_score(y_safe, p)),
            brier=float(brier_score_loss(y_safe, p)),
            ece=expected_calibration_error(y_safe, p),
            n=len(y_safe),
        )


if __name__ == "__main__":
    # Self-test: SENTETİK fix-record'lar (gerçek dataset gerekmez).
    # inlier_ratio ve reprojection_error ile "safe" arasına GERÇEKÇİ,
    # gürültülü bir ilişki kuruyoruz, model bunu öğrenip kalibre edebilmeli.
    rng = np.random.default_rng(42)
    n = 2000
    inlier_ratio = rng.beta(2, 2, n)
    num_matches = rng.integers(10, 300, n).astype(float)
    reproj_err = rng.exponential(3.0, n) * (1.5 - inlier_ratio)
    margin = rng.normal(0.15, 0.1, n) + 0.3 * (inlier_ratio - 0.5)

    logit = 4.0 * inlier_ratio - 0.4 * reproj_err + 2.0 * margin - 1.0 + rng.normal(0, 0.5, n)
    p_safe_true = 1.0 / (1.0 + np.exp(-logit))
    y_safe = (rng.random(n) < p_safe_true).astype(int)

    rows = [
        {"num_matches": num_matches[i], "inlier_count": inlier_ratio[i] * num_matches[i],
         "inlier_ratio": inlier_ratio[i], "reprojection_error_px": reproj_err[i],
         "inlier_spatial_spread": None, "transform_condition": None,
         "top1_top2_margin": margin[i], "mahalanobis_d": None}
        for i in range(n)
    ]

    n_train = 1500
    model = ReliabilityModel()
    model.fit(rows[:n_train], y_safe[:n_train])
    metrics = model.evaluate(rows[n_train:], y_safe[n_train:])
    print(f"Kalibre model (test split, n={metrics.n}):")
    print(f"  AUROC={metrics.auroc:.3f}  AUPRC={metrics.auprc:.3f}  "
          f"Brier={metrics.brier:.3f}  ECE={metrics.ece:.3f}")

    # Karsilastirma: ham inlier_ratio'nun kendisini "confidence" olarak
    # kullansak (kalibrasyonsuz) ECE/Brier nasil olurdu?
    raw = inlier_ratio[n_train:]
    ece_raw = expected_calibration_error(y_safe[n_train:], raw)
    brier_raw = brier_score_loss(y_safe[n_train:], raw)
    print(f"\nHam inlier_ratio (kalibrasyonsuz, karsilastirma):")
    print(f"  Brier={brier_raw:.3f}  ECE={ece_raw:.3f}")
    print(f"  -> Kalibre model {'DAHA IYI' if metrics.ece < ece_raw else 'DAHA KOTU'} kalibre "
          f"(ECE {metrics.ece:.3f} vs {ece_raw:.3f})")
