"""Her drift rejimi icin 'dogru belirtilmis' filtre surec gurultusu:
10 s pencerelerdeki hata artisindan sigma_q^2 = E|d_err|^2 / (2*dt).
Gercek bir TRAIN ucusunun rotasi uzerinde, 5 tohumla."""
import numpy as np

from aerialvl_loader import AerialVLVal
from drift_simulator import REGIME_PRESETS, DriftConfig, DriftSimulator, FilterNoiseConfig
from geo_utils import lonlat_to_enu_m

from paths import DATA_ROOT
VAL_ROOT = str(DATA_ROOT / "AerialVL_data/images/VAL/extracted")
SEQ = "2023-03-18-12-47-05"  # TRAIN, long
WIN = 10.0

frames = AerialVLVal(VAL_ROOT).sequences[SEQ]
o = frames[0]
t = np.array([(f.utc_ts - o.utc_ts) / 1000.0 for f in frames])
xy = np.array([lonlat_to_enu_m(f.lon, f.lat, o.lon, o.lat) for f in frames])
dist = np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1))
print(f"{SEQ}: {t[-1]:.0f}s, {dist:.0f}m")

for name, base in REGIME_PRESETS.items():
    qs, finals = [], []
    for seed in range(5):
        cfg = DriftConfig(**{**base.__dict__, "seed": seed})
        sim = DriftSimulator(cfg, FilterNoiseConfig(process_noise_sigma_m_per_sqrt_s=1.0))
        err = []
        for ti, (x, y) in zip(t, xy):
            s = sim.step(float(ti), float(x), float(y))
            err.append((s.prior_x_m - x, s.prior_y_m - y))
        err = np.array(err)
        idx = np.searchsorted(t, t + WIN)
        ok = idx < len(t)
        d = err[idx[ok]] - err[ok]
        qs.append(np.mean(np.sum(d ** 2, axis=1)) / (2 * WIN))
        finals.append(np.linalg.norm(err[-1]))
    sq = np.sqrt(np.mean(qs))
    print(f"{name:9s} sigma_q={sq:.3f} m/sqrt(s)  son hata={np.mean(finals):6.1f}m "
          f"(%{np.mean(finals)/dist*100:.2f} mesafe)")
