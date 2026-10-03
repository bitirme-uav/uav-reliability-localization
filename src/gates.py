"""M5 (confidence baselines) + M8 (chi-square gate + reliability policy)
+ M9 (reacquisition logic) -- hepsi saf matematik, veri/görüntü gerekmez.

Bu modüldeki hiçbir fonksiyon ground-truth hatasını (fix_error_m) veya
ondan türetilen hiçbir niceliği GİRDİ olarak KULLANMAZ (M4 label-leakage
yasağı) -- yalnızca çalışma-zamanında gerçekten mevcut olan sinyalleri
(retrieval/matching istatistikleri, prior, kovaryans) kullanır.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np


# ---------------------------------------------------------------- M5 ----

def raw_confidence(inlier_ratio: float) -> float:
    """M5.1: 'one direct score, e.g. inlier ratio or top-1 similarity'."""
    return float(inlier_ratio)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def heuristic_confidence(top1_score: float, top1_top2_margin: float, gsd_ratio: float | None,
                          w_s: float = 1.0, w_r: float = 1.0,
                          score_margin_threshold: float = 0.1,
                          margin_scale: float = 10.0, gsd_scale: float = 5.0) -> float:
    """M5.2: SatLoc-tarzı sezgisel güven, yayınlanan denklemlerden yeniden
    üretildi.

        C1 = w_s * C_score + w_r * C_res
        C_score = sigmoid(top1 vs mean-suboptimal retrieval-score margin - threshold)
        C_res   = sigmoid(UAV/satellite GSD ratio - 0.8)

    Doküman notu (M5.2): "published equations are internally inconsistent...
    implement the evidently intended monotonic form ... parameters not
    stated in the paper are tuned on validation data only." Burada
    varsayılan ağırlıklar/ölçekler yer tutucudur -- Ay-3'te (M3/M5
    kalibrasyon fazı) validation split'inde ayarlanmalı, TEST split'ine
    hiç dokunulmadan (proje kuralı, §9.1).

    gsd_ratio None ise (irtifa türetilemiyorsa) C_res terimi düşürülür ve
    yalnızca C_score kullanılır -- dokümanın "GSD teriminin düşürülüp
    belgelenmesi" talimatına uygun.
    """
    c_score = _sigmoid(margin_scale * (top1_top2_margin - score_margin_threshold))
    if gsd_ratio is None:
        return float(c_score)
    c_res = _sigmoid(gsd_scale * (gsd_ratio - 0.8))
    total_w = w_s + w_r
    return float((w_s * c_score + w_r * c_res) / total_w)


# ---------------------------------------------------------------- M8 ----

@dataclass
class ChiSquareResult:
    d2: float
    threshold: float
    reject: bool


# m=dim(z)=2 (2D pozisyon) icin ki-kare kritik degerleri (M8'de verilen)
CHI2_THRESHOLD_ALPHA_001 = 9.21
CHI2_THRESHOLD_ALPHA_005 = 5.99


def chi_square_gate(prior_xy: np.ndarray, prior_cov: np.ndarray, fix_xy: np.ndarray,
                     r_nominal: np.ndarray, alpha: float = 0.05) -> ChiSquareResult:
    """M8 zorunlu ki-kare innovation gate.

        ν = z_fix - H·x̂_prior ;  S = H·P_prior·H^T + R_nominal ;  d² = ν^T S⁻¹ ν
        reject if d² > χ²_m(1-α),  m=dim(z)=2

    Simülatörün durumu SADECE 2D pozisyon olduğu için H=I (doküman notu:
    "In the mandatory simulator the state is 2-D position only, so H = I
    and S = P_prior + R_nominal").
    """
    threshold = CHI2_THRESHOLD_ALPHA_001 if abs(alpha - 0.01) < 1e-9 else CHI2_THRESHOLD_ALPHA_005
    nu = fix_xy - prior_xy
    S = prior_cov + r_nominal
    d2 = float(nu.T @ np.linalg.inv(S) @ nu)
    return ChiSquareResult(d2=d2, threshold=threshold, reject=d2 > threshold)


def r_nominal_from_validation_errors(fix_errors_m: np.ndarray) -> np.ndarray:
    """R_nominal = validation-split'te M3 primary label'ı GEÇEN (safe) fix'lerin
    hata varyansından tahmin edilir (M8 notu: 'estimated from validation-split
    localization errors of fixes that satisfy the primary ground-truth label,
    NOT from fixes accepted by any policy under evaluation'). İzotropik 2x2
    kovaryans döner.
    """
    var = float(np.var(fix_errors_m)) if len(fix_errors_m) > 1 else 1.0
    return np.array([[var, 0.0], [0.0, var]])


# --------------------------------------------------------- M8 policy ----

class Decision(str, Enum):
    ACCEPT = "accept"
    DOWNWEIGHT = "down-weight"
    REJECT = "reject"
    PENDING_CONFIRMATION = "pending-confirmation"


@dataclass
class ReliabilityPolicy:
    """M8 'Proposed policy':
        RELIABLE   -> accept (nominal R)
        UNCERTAIN  -> down-weight (R scaled by fixed, documented function)
        UNRELIABLE -> reject
    """
    high_threshold: float = 0.90   # >= -> RELIABLE
    low_threshold: float = 0.60    # >= -> UNCERTAIN, altı -> UNRELIABLE
    downweight_r_scale: float = 4.0  # UNCERTAIN kabulde R_nominal * bu katsayı

    def decide(self, reliability: float) -> Decision:
        if reliability >= self.high_threshold:
            return Decision.ACCEPT
        if reliability >= self.low_threshold:
            return Decision.DOWNWEIGHT
        return Decision.REJECT

    def effective_r(self, r_nominal: np.ndarray, decision: Decision) -> np.ndarray:
        if decision == Decision.DOWNWEIGHT:
            return r_nominal * self.downweight_r_scale
        return r_nominal


# ------------------------------------------------------ M9 REACQUIRE ----

class NavMode(str, Enum):
    NORMAL = "NORMAL"
    REACQUIRE = "REACQUIRE"


@dataclass
class ReacquisitionManager:
    """M9: N ardışık red/eksik fix VEYA sigma_pos > bound -> REACQUIRE.
    REACQUIRE modunda: arama r_max'a genişler, ki-kare/tutarlılık cezası
    askıya alınır, kabul için k ardışık fix (relative displacement,
    dead-reckoned hareketle tau toleransıyla uyumlu) gerekir.
    """
    n_consecutive_for_reacquire: int = 3
    sigma_pos_bound_m: float = 150.0
    k_confirmation: int = 2
    tau_m: float | None = None  # None ise __post_init__'te primary_threshold*2 ile doldurulur
    primary_threshold_m: float = 10.0

    mode: NavMode = NavMode.NORMAL
    _reject_streak: int = 0
    _pending_fixes: list[tuple[float, float]] | None = None

    def __post_init__(self):
        if self.tau_m is None:
            self.tau_m = 2 * self.primary_threshold_m
        self._pending_fixes = []

    def on_fix(self, decision: Decision, sigma_pos_m: float,
               fix_xy: np.ndarray | None, dead_reckoned_delta: np.ndarray | None) -> Decision:
        """Bir fix işlendikten sonra çağrılır; mode geçişlerini uygular ve
        REACQUIRE modundaysa nihai kararı (confirmation mantığıyla) döner.
        """
        if self.mode == NavMode.NORMAL:
            if decision in (Decision.REJECT,) or fix_xy is None:
                self._reject_streak += 1
            else:
                self._reject_streak = 0
            if self._reject_streak >= self.n_consecutive_for_reacquire or sigma_pos_m > self.sigma_pos_bound_m:
                self.mode = NavMode.REACQUIRE
                self._pending_fixes = []
            return decision

        # REACQUIRE modu: sadece RELIABLE (ACCEPT) sinyalli fix'ler aday,
        # ama tek başına yeterli değil -- k ardışık, birbirleriyle
        # dead-reckoned harekete gore tutarlı fix gerekir (M9.3).
        if decision != Decision.ACCEPT or fix_xy is None:
            self._pending_fixes = []
            return Decision.REJECT

        if self._pending_fixes:
            last_fix = np.array(self._pending_fixes[-1])
            predicted = last_fix + (dead_reckoned_delta if dead_reckoned_delta is not None else np.zeros(2))
            agree = float(np.linalg.norm(fix_xy - predicted)) <= self.tau_m
            if not agree:
                self._pending_fixes = [tuple(fix_xy)]
                return Decision.PENDING_CONFIRMATION
        self._pending_fixes.append(tuple(fix_xy))

        if len(self._pending_fixes) >= self.k_confirmation:
            self.mode = NavMode.NORMAL
            self._reject_streak = 0
            self._pending_fixes = []
            return Decision.ACCEPT
        return Decision.PENDING_CONFIRMATION


if __name__ == "__main__":
    # Self-test (sentetik, veri gerekmez)
    pol = ReliabilityPolicy()
    for r in (0.97, 0.75, 0.2):
        print(f"reliability={r:.2f} -> {pol.decide(r).value}")

    r_nom = np.array([[25.0, 0.0], [0.0, 25.0]])
    prior = np.array([100.0, 200.0])
    fix_ok = np.array([103.0, 197.0])
    fix_bad = np.array([500.0, 900.0])
    prior_cov = np.array([[100.0, 0.0], [0.0, 100.0]])
    res_ok = chi_square_gate(prior, prior_cov, fix_ok, r_nom)
    res_bad = chi_square_gate(prior, prior_cov, fix_bad, r_nom)
    print(f"chi2 (uyumlu fix): d2={res_ok.d2:.2f} reject={res_ok.reject}")
    print(f"chi2 (uyumsuz fix): d2={res_bad.d2:.2f} reject={res_bad.reject}")

    print("\nH4 senaryosu: buyuk-drift sonrasi DOGRU ama UZAK fix, chi-square'i gecemez:")
    prior_far = np.array([100.0, 200.0])
    prior_cov_small = np.array([[25.0, 0.0], [0.0, 25.0]])  # filtre kendine COK guveniyor
    correct_far_fix = np.array([350.0, 420.0])  # buyuk driftten sonra GERCEKTEN dogru olan uzak fix
    res_h4 = chi_square_gate(prior_far, prior_cov_small, correct_far_fix, r_nom)
    print(f"  d2={res_h4.d2:.2f} (esik={res_h4.threshold}) reject={res_h4.reject} "
          f"-> {'BEKLENEN: dogru fix reddedildi (H4 dogrulandi)' if res_h4.reject else 'kabul edildi'}")
