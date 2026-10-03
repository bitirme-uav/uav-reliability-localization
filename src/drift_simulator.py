"""M6: Kontrollü GPS/GNSS-kayıp drift simülatörü.

Ground-truth (ENU metre) rotasına deterministik-tohumlu drift enjekte
eder. Beş bozulma bileşeni (dokumanla birebir):
  - constant bias
  - velocity/scale bias
  - Gaussian random walk
  - slowly varying heading bias
  - occasional burst error

Kritik kural (M6): "the filter's assumed process noise must be
configurable SEPARATELY from the true drift, to test covariance
mis-specification (filter assumes 'mild', truth is 'severe')."
Bu yuzden DriftConfig (GERCEK drift) ile FilterNoiseConfig (prior_cov'un
BUYUME hizini belirleyen, filtrenin KENDI VARSAYIMI) birbirinden
tamamen bagimsiz iki yapi.

Bu modul saf Python/NumPy'dir, hicbir goruntu/harita verisine ihtiyac
duymaz -- gercek AerialVL indirmesi bitmeden de tam olarak test
edilebilir (asagidaki __main__ self-test bunu yapiyor).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DriftConfig:
    """GERÇEK drift üretecinin parametreleri (regime: mild/moderate/severe)."""
    seed: int
    regime: str  # 'mild' | 'moderate' | 'severe'
    constant_bias_m: tuple[float, float] = (0.0, 0.0)
    velocity_scale_bias: float = 0.0             # örn 0.05 = hız %5 fazla tahmin
    random_walk_sigma_m_per_sqrt_s: float = 0.0  # true Gaussian random-walk süreç gürültüsü
    heading_bias_deg_per_s: float = 0.0          # yavaş değişen yön (heading) sapması
    heading_bias_max_deg: float = 0.0            # |heading bias| üst sınırı
    burst_prob_per_s: float = 0.0                # ani sıçrama olasılığı (Poisson oranı)
    burst_sigma_m: float = 0.0


@dataclass
class FilterNoiseConfig:
    """Filtrenin KENDİ VARSAYIMI (prior_cov büyüme hızı) -- DriftConfig'ten
    BAĞIMSIZ. Bunları eşit tutarsanız 'doğru kalibre' filtre, farklı
    tutarsanız (örn filter='mild', truth=DriftConfig(regime='severe'))
    kasıtlı yanlış-kalibrasyon (mis-specification) testi yapmış olursunuz
    -- H4 hipotezinin (chi-square gate kalibrasyon hatasına duyarlı)
    doğrudan test aracı budur.
    """
    process_noise_sigma_m_per_sqrt_s: float
    initial_cov_m2: float = 25.0  # t=0 anında prior_cov_xx=prior_cov_yy başlangıcı


# Dokümanda sabit bir sayısal tanım verilmiyor (rejim isimleri "mild/moderate/
# severe" olarak tanımlanmış, kesin sayılar projeye bırakılmış) -- burada
# MAKUL, belgelenmiş varsayılan değerler seçildi. Kalibrasyon/tuning
# sırasında validation verisiyle ayarlanabilir (M9.1 kuralına uygun:
# yalnızca train/validation sequence'lerinde).
# Hedef kaba buyukluk: kat edilen mesafenin ~%0.5 (mild), ~%1.5 (moderate),
# ~%4 (severe) kadar hata -- tipik VIO/odometri drift araliklari.
# (2026-10-01: heading-bias bug'i duzeltilince eski degerler 15 dk'lik ucusta
# yuzlerce derece sapma uretiyordu; sinirlandirildi ve yeniden ayarlandi.)
REGIME_PRESETS: dict[str, DriftConfig] = {
    "mild": DriftConfig(
        seed=0, regime="mild",
        constant_bias_m=(2.0, -1.0), velocity_scale_bias=0.01,
        random_walk_sigma_m_per_sqrt_s=0.3, heading_bias_deg_per_s=0.005, heading_bias_max_deg=0.5,
        burst_prob_per_s=0.0, burst_sigma_m=0.0,
    ),
    "moderate": DriftConfig(
        seed=0, regime="moderate",
        constant_bias_m=(5.0, -3.0), velocity_scale_bias=0.03,
        random_walk_sigma_m_per_sqrt_s=1.0, heading_bias_deg_per_s=0.02, heading_bias_max_deg=2.0,
        burst_prob_per_s=0.002, burst_sigma_m=15.0,
    ),
    "severe": DriftConfig(
        seed=0, regime="severe",
        constant_bias_m=(10.0, -8.0), velocity_scale_bias=0.06,
        random_walk_sigma_m_per_sqrt_s=2.5, heading_bias_deg_per_s=0.05, heading_bias_max_deg=5.0,
        burst_prob_per_s=0.005, burst_sigma_m=40.0,
    ),
}


# "Dogru belirtilmis" filtre surec gurultusu (calibrate_filter_noise.py,
# TRAIN ucusu 2023-03-18-12-47-05, 5 tohum, 10 s pencere). Yanlis-belirtilmis
# senaryo: gercek rejim 'severe', filtre 'mild' degerini varsayar.
MATCHED_FILTER_NOISE: dict[str, float] = {"mild": 0.37, "moderate": 1.32, "severe": 3.58}


@dataclass
class PriorSample:
    t_s: float
    prior_x_m: float
    prior_y_m: float
    prior_cov_xx: float
    prior_cov_xy: float
    prior_cov_yy: float
    true_offset_m: float  # |prior - ground_truth| -- [eval], sadece kayıt için


class DriftSimulator:
    """Ground-truth (t,x,y) dizisi üzerinden drift'li prior üretir.

    Kullanım:
        sim = DriftSimulator(DriftConfig(seed=42, **REGIME_PRESETS['moderate'].__dict__ ...),
                              FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=0.5))
        for t, x, y in ground_truth_traj:
            sample = sim.step(t, x, y)
    """

    def __init__(self, drift_cfg: DriftConfig, filter_cfg: FilterNoiseConfig):
        self.drift_cfg = drift_cfg
        self.filter_cfg = filter_cfg
        self._rng = np.random.default_rng(drift_cfg.seed)

        self._t_prev: float | None = None
        self._rw_offset = np.zeros(2)          # random-walk kümülatif
        self._heading_bias_deg = 0.0
        self._scale_bias_offset = np.zeros(2)  # velocity/scale bias'ın kümüle ettirdiği kayma
        self._prev_true_xy: np.ndarray | None = None
        self._burst_offset = np.zeros(2)
        self._cov_scalar = filter_cfg.initial_cov_m2  # basit izotropik büyüme (xx=yy, xy=0)
        self._last_prior = np.zeros(2)

    def reset(self) -> None:
        self.__init__(self.drift_cfg, self.filter_cfg)

    def step(self, t_s: float, true_x_m: float, true_y_m: float) -> PriorSample:
        dt = 0.0 if self._t_prev is None else max(0.0, t_s - self._t_prev)
        true_xy = np.array([true_x_m, true_y_m])
        # bu adimdaki gercek yer degistirme (2. ve 4. bilesenler kullanir).
        # NOT: onceki surumde _prev_true_xy 2. adimda guncellendigi icin
        # 4. adimdaki heading-bias yer degistirmesi her zaman 0'di (bug).
        delta = np.zeros(2) if self._prev_true_xy is None else true_xy - self._prev_true_xy
        self._prev_true_xy = true_xy

        # 1) constant bias
        bias = np.array(self.drift_cfg.constant_bias_m)

        # 2) velocity/scale bias: dead-reckoned yer degistirme olcek hatali
        self._scale_bias_offset = self._scale_bias_offset + self.drift_cfg.velocity_scale_bias * delta

        # 3) Gaussian random walk (true surec gurultusu)
        if dt > 0.0 and self.drift_cfg.random_walk_sigma_m_per_sqrt_s > 0.0:
            sigma = self.drift_cfg.random_walk_sigma_m_per_sqrt_s * np.sqrt(dt)
            self._rw_offset = self._rw_offset + self._rng.normal(0.0, sigma, size=2)

        # 4) yavas degisen heading bias: dead-reckoned yer degistirme
        #    theta kadar donuk entegre edilir -> hata artisi (R(theta)-I)*delta
        if dt > 0.0:
            self._heading_bias_deg += self.drift_cfg.heading_bias_deg_per_s * dt * self._rng.normal(1.0, 0.3)
            lim = self.drift_cfg.heading_bias_max_deg
            self._heading_bias_deg = float(np.clip(self._heading_bias_deg, -lim, lim))
            theta = np.radians(self._heading_bias_deg)
            rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
            self._rw_offset = self._rw_offset + (rot - np.eye(2)) @ delta

        # 5) ani sicrama (burst), Poisson-yaklasimi
        if dt > 0.0 and self.drift_cfg.burst_prob_per_s > 0.0:
            if self._rng.random() < self.drift_cfg.burst_prob_per_s * dt:
                self._burst_offset = self._rng.normal(0.0, self.drift_cfg.burst_sigma_m, size=2)
            else:
                # burst kalici degil, yumusakca sonebilir (basit sizinti modeli)
                self._burst_offset *= 0.9

        prior_xy = true_xy + bias + self._scale_bias_offset + self._rw_offset + self._burst_offset

        # prior_cov: filtrenin KENDI varsayimina gore buyur (DriftConfig'ten
        # BAGIMSIZ -- mis-specification testinin kalbi burasi)
        if dt > 0.0:
            self._cov_scalar += (self.filter_cfg.process_noise_sigma_m_per_sqrt_s ** 2) * dt

        self._t_prev = t_s
        self._last_prior = prior_xy
        true_offset = float(np.linalg.norm(prior_xy - true_xy))

        return PriorSample(
            t_s=t_s, prior_x_m=float(prior_xy[0]), prior_y_m=float(prior_xy[1]),
            prior_cov_xx=float(self._cov_scalar), prior_cov_xy=0.0, prior_cov_yy=float(self._cov_scalar),
            true_offset_m=true_offset,
        )

    def apply_correction(self, fixed_x_m: float, fixed_y_m: float, r_m2: float) -> None:
        """2D pozisyon Kalman guncellemesi (H=I, izotropik): K = P/(P+R),
        x <- x + K(z - x), P <- (1-K)P. Buyuk R (down-weight) daha kucuk
        duzeltme demektir. Duzeltmeden sonra drift yeni konumdan birikmeye
        devam eder.
        """
        P = self._cov_scalar
        k = P / (P + r_m2)
        z = np.array([fixed_x_m, fixed_y_m])
        new_prior = self._last_prior + k * (z - self._last_prior)
        self._rw_offset = self._rw_offset + (new_prior - self._last_prior)
        self._last_prior = new_prior
        self._cov_scalar = (1.0 - k) * P

    def inject_offset(self, dx_m: float, dy_m: float) -> None:
        """M9 Senaryo A/B: prior'a ani buyuk bir hata ekler; kovaryans
        BUYUTULMEZ (filtre hatanin farkinda degil -- yanlis-belirtim)."""
        self._rw_offset = self._rw_offset + np.array([dx_m, dy_m])
        self._last_prior = self._last_prior + np.array([dx_m, dy_m])

    def set_cov(self, cov_m2: float) -> None:
        self._cov_scalar = cov_m2

    def current_prior(self) -> tuple[np.ndarray, float]:
        return self._last_prior.copy(), self._cov_scalar


if __name__ == "__main__":
    # Basit self-test: gercek veri gerekmez, sentetik duz-cizgi rota.
    import sys
    t = np.arange(0.0, 120.0, 0.5)
    true_x = 5.0 * t  # 5 m/s doguya sabit hiz
    true_y = np.zeros_like(t)

    for regime_name in ("mild", "moderate", "severe"):
        cfg = REGIME_PRESETS[regime_name]
        filt = FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=cfg.random_walk_sigma_m_per_sqrt_s)
        sim = DriftSimulator(cfg, filt)
        offsets = []
        for ti, xi, yi in zip(t, true_x, true_y):
            s = sim.step(float(ti), float(xi), float(yi))
            offsets.append(s.true_offset_m)
        offsets = np.array(offsets)
        print(f"{regime_name:8s}: t=120s sonunda offset={offsets[-1]:6.2f}m  "
              f"ortalama={offsets.mean():6.2f}m  max={offsets.max():6.2f}m")

    print("\nMis-specification testi (truth=severe, filter assumed=mild):")
    cfg = REGIME_PRESETS["severe"]
    filt_mild = FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=REGIME_PRESETS["mild"].random_walk_sigma_m_per_sqrt_s)
    sim = DriftSimulator(cfg, filt_mild)
    last = None
    for ti, xi, yi in zip(t, true_x, true_y):
        last = sim.step(float(ti), float(xi), float(yi))
    print(f"  gercek offset={last.true_offset_m:.2f}m  ama filtrenin prior_cov std'si="
          f"{last.prior_cov_xx**0.5:.2f}m  -> filtre kendine oldugundan FAZLA guveniyor "
          f"(chi-square gate'in yanlis-kabul riski, H4)")
    sys.exit(0)
