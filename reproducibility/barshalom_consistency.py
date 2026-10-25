"""Reproduce Bar-Shalom, Li & Kirubarajan (2001), Estimation with Applications to
Tracking and Navigation, Sections 5.3-5.4: the DWNA Kalman filter example and the
NEES / NIS / innovation-autocorrelation consistency tests (matched and mismatched filter),
plus the chi-square acceptance regions the book quotes.

This is the statistical basis of the project's chi-square innovation gate (M8).

Usage: python barshalom_consistency.py
"""
import json
from pathlib import Path

import numpy as np
from scipy.stats import chi2

OUT = Path(__file__).resolve().parent / "results" / "barshalom_consistency.json"
T = 1.0
F = np.array([[1, T], [0, 1]])
G = np.array([[T * T / 2], [T]])
H = np.array([[1.0, 0.0]])
R = 1.0
K_STEPS = 100  # k = 1..100 measurements, filter starts at k = 3
N_MC = 50


def simulate(q, rng):
    x = np.array([0.0, 10.0])
    xs, zs = [], []
    for _ in range(K_STEPS):
        x = F @ x + (G[:, 0] * rng.normal(0, np.sqrt(q)))
        xs.append(x.copy())
        zs.append(x[0] + rng.normal(0, np.sqrt(R)))
    return np.array(xs), np.array(zs)


def run_filter(zs, q_f):
    """Two-point differencing initialisation (5.5.3-3..5), filter runs from k = 3."""
    x = np.array([zs[1], (zs[1] - zs[0]) / T])
    P = np.array([[R, R / T], [R / T, 2 * R / T ** 2]])
    Q = q_f * (G @ G.T)
    out = []
    for k in range(2, K_STEPS):
        xp = F @ x
        Pp = F @ P @ F.T + Q
        S = (H @ Pp @ H.T).item() + R
        nu = zs[k] - xp[0]
        K = (Pp @ H.T / S)[:, 0]
        x = xp + K * nu
        P = (np.eye(2) - np.outer(K, H)) @ Pp
        out.append((k, x.copy(), P.copy(), nu, S, K.copy()))
    return out


def nees_nis(q_true, q_f, seed):
    rng = np.random.default_rng(seed)
    nees = np.zeros((N_MC, K_STEPS - 2))
    nis = np.zeros_like(nees)
    nu_n = np.zeros_like(nees)
    gains = None
    for n in range(N_MC):
        xs, zs = simulate(q_true, rng)
        res = run_filter(zs, q_f)
        for i, (k, x, P, nu, S, K) in enumerate(res):
            e = xs[k] - x
            nees[n, i] = e @ np.linalg.solve(P, e)
            nis[n, i] = nu * nu / S
            nu_n[n, i] = nu / np.sqrt(S)
        gains = res[-1][5]
    return nees, nis, nu_n, gains


def summarise(q_true, q_f, seed=0):
    nees, nis, nu_n, gains = nees_nis(q_true, q_f, seed)
    m = nees.shape[1]
    single_out = int((nees[0] > chi2.ppf(0.95, 2)).sum())
    lo, hi = chi2.ppf([0.025, 0.975], 2 * N_MC) / N_MC
    nlo, nhi = chi2.ppf([0.025, 0.975], N_MC) / N_MC
    avg_nees, avg_nis = nees.mean(0), nis.mean(0)
    # N-run sample autocorrelation one step apart (5.4.2-13)
    rho = (nu_n[:, :-1] * nu_n[:, 1:]).sum(0) / np.sqrt((nu_n[:, :-1] ** 2).sum(0) * (nu_n[:, 1:] ** 2).sum(0))
    rho_bound = 1.96 / np.sqrt(N_MC)
    # single-run real-time tests (5.4.2-15/16), run 0
    v = nu_n[0]
    rho1_rt = float((v[:-1] * v[1:]).sum() / np.sqrt((v[:-1] ** 2).sum() * (v[1:] ** 2).sum()))
    tavg_nis = float(nis[0].mean())
    tlo, thi = chi2.ppf([0.025, 0.975], m) / m
    return {
        "q_true": q_true, "q_filter": q_f, "steps_evaluated": m,
        "steady_state_gain": [round(float(g), 3) for g in gains],
        "single_run_nees_points_outside_5.99": single_out,
        "mc_avg_nees_region": [round(lo, 2), round(hi, 2)],
        "mc_avg_nees_points_outside": int(((avg_nees < lo) | (avg_nees > hi)).sum()),
        "mc_avg_nis_region": [round(nlo, 2), round(nhi, 2)],
        "mc_avg_nis_points_outside": int(((avg_nis < nlo) | (avg_nis > nhi)).sum()),
        "mc_avg_nis_points_above_upper": int((avg_nis > nhi).sum()),
        "mc_autocorr_region": [-round(rho_bound, 3), round(rho_bound, 3)],
        "mc_autocorr_points_outside": int((np.abs(rho) > rho_bound).sum()),
        "realtime_rho1": round(rho1_rt, 3), "realtime_rho1_region": [-0.196, 0.196],
        "realtime_time_avg_nis": round(tavg_nis, 3), "realtime_nis_region": [round(tlo, 2), round(thi, 2)],
    }


def gate_false_reject(n=200_000, seed=0):
    """2-D gate used in the project: d2 = nu' S^-1 nu with S = P + R, nu ~ N(0, S_true)."""
    rng = np.random.default_rng(seed)
    out = {}
    for scale in (1.0, 2.0, 4.0, 9.0):  # true innovation covariance = scale * assumed S
        nu = rng.normal(size=(n, 2)) * np.sqrt(scale)
        d2 = (nu ** 2).sum(1)
        out[f"true_cov_x{scale:g}"] = {a: round(float((d2 > chi2.ppf(1 - a, 2)).mean()), 4) for a in (0.05, 0.01)}
    return out


def main():
    table = {
        "chi2_2dof_0.95": round(chi2.ppf(0.95, 2), 2),        # book 5.99
        "chi2_2dof_0.975": round(chi2.ppf(0.975, 2), 2),      # book 7.38
        "chi2_2dof_0.025": round(chi2.ppf(0.025, 2), 2),      # book 0.05
        "chi2_2dof_0.99": round(chi2.ppf(0.99, 2), 2),        # project 9.21
        "chi2_100dof_2.5_97.5": [round(v, 1) for v in chi2.ppf([0.025, 0.975], 100)],  # book [74.2, 129.6]
        "chi2_50dof_2.5_97.5": [round(v, 1) for v in chi2.ppf([0.025, 0.975], 50)],    # book [32.3, 71.4]
    }
    res = {
        "chi2_table": table,
        "q1_matched": summarise(1, 1, seed=1),
        "q9_matched": summarise(9, 9, seed=2),
        "q9_true_q1_filter_mismatched": summarise(9, 1, seed=3),
        "gate_false_reject_rate": gate_false_reject(),
        "book": {
            "gain_q1": [0.75, 0.50], "gain_q9": [0.90, 0.94],
            "matched_single_run_outside": "3-6 of 100", "mc_nees_region": [1.5, 2.6], "mc_nees_outside": 6,
            "mc_nis_region": [0.65, 1.43], "mc_nis_outside": 4, "mc_autocorr_region": [-0.277, 0.277],
            "mc_autocorr_outside": 8, "realtime_rho1_matched": 0.152, "realtime_rho1_mismatched": 0.509,
            "realtime_nis_matched": 0.936, "realtime_nis_region": [0.74, 1.3],
            "mismatched_single_run_outside": 41, "mismatched_mc": "all points outside (upper tail)",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
