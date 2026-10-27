# Reproducibility study — priority-reading papers (proposal v6 §19)

Goal: for each paper in the proposal's priority-reading list, re-run (or re-implement when no
code is released) the experiment(s) whose numbers we can check with data we have, and report
paper value vs. our value. Data and disk constraints decide what is feasible: the D: drive has
~9 GB free, so large datasets are not downloaded.

Environment (Windows): `D:\proje\venv_win` (Python 3.12, torch 2.6.0+cu124, RTX 4060 Laptop 8 GB).
Set `TORCH_HOME=D:\proje\torch_cache` so model weights do not land on the full C: drive.
Results (JSON/JSONL) are written to `reproducibility/results/`.

## Status per paper

| # | Paper | Code released? | Data here? | What we reproduce | Script | Status |
|---|---|---|---|---|---|---|
| 1 | AerialVL (He et al., RA-L 2024) | data only (no baseline code) | yes (5 of 11 sequences on disk; TRAIN images deleted) | Table VII protocol (sequential alignment from known start, Succ. Rate / MLE / CTL) on ST.5, LT.5, LT.6 with our localizer | `aerialvl_table7.py` | queued |
| 2 | GeoVINS (Li et al., T-RO 2025) | no | no (rosbags, Baidu, large) | not feasible | — | infeasible |
| 3 | SatLoc / SatLoc-Fusion (Zhou et al., Remote Sens. 2025) | empty repo | no (529 GB, Quark) | Eq. (2) confidence C1 re-implemented and scored on our fix records (dataset not downloadable) | `satloc_c1.py` | done (sign error found) |
| 4 | Zhang et al. (UST 2026), Map-Aided UAV Visual Localization via VO and Orthophoto Map Alignment | no | no (two private Tianjin flights) | method re-implemented (homography VO, gated map correction, local relocalization, pure-VO baseline) and run on AerialVL ST.5 / LT.5 / LT.6 | `aerialvl_zhang.py` | queued |
| 5 | AnyVisLoc (Ye et al., CVPR-F 2026) | yes (UAV-AVL/Benchmark) | yes (24 scenes, 60 GB zips) | Table 6 aerial baseline (CAMP + RoMa + top-5, A@5/10/20 m), Table 4 SP+LG rows | `anyvisloc_run.py` | 9-scene run done (not comparable); full 24-scene run on Kaggle in progress |
| 6 | UAV-VisLoc (Xu et al., arXiv 2024) | data only | yes | dataset statistics, Table II | `uav_visloc_stats.py` | done |
| 7 | Bar-Shalom et al. (2001) | textbook | simulated | §5.3–5.4 DWNA Kalman example, NEES/NIS consistency tests, χ² regions | `barshalom_consistency.py` | reproduced |
| 8 | Sequence Matching (Wang et al., TGRS 2024) | no (site down) | yes (ALTO Val = paper's test split) | Table I "Ours", Table IV, Table V, k sweep | `seqmatch_alto.py` | sorting reproduced; matching partly |
| 9 | UAVD4L (Wu et al., 3DV 2024) | yes | no (large) | not feasible | — | infeasible |
| 10 | OrthoLoC (Dhaouadi et al., NeurIPS 2025) | yes | no (287 GB) | not feasible | — | infeasible |
| 11 | OrthoTrack (Dhaouadi et al., ECCV 2026) | announced | no (MovingDrone, large) | not feasible | — | infeasible |
| 12 | Ahmedelbadawi et al. (SPIE 2025) | no | no | not feasible | — | infeasible |
| 13 | Bi et al. (ISPRS J. 2026), UAV coarse visual localization (XIAN-Visloc) | yes (VERYBC/UCVL, eval only) | Kaggle (HF, 26 GB + 4.5 GB) | Tables 4/7/9 retrieval on XIAN-Visloc; Table 13 real-world | `bi_xian_visloc/` | Table 13 reproduced exactly; XIAN-Visloc tables partly (released weights are the real-world model) |
| 14 | Wang et al. (ISPRS Archives 2026), UAV Visual Localization in GNSS-Denied Environments | no | no (own NCSIST-funded flights, 3,770 images, not released) | not feasible | — | infeasible |

Results are filled in below as each experiment finishes.

## 7. Bar-Shalom et al. — §5.3–5.4 DWNA example (`barshalom_consistency.py`) — reproduced

Simulated exactly as in the book (T = 1, r = 1, x0 = [0, 10], 100 steps, two-point init, N = 50 MC runs).

| Quantity | Book | Ours |
|---|---|---|
| Steady-state gain, q = 1 | [0.75, 0.50] | [0.750, 0.500] |
| Steady-state gain, q = 9 | [0.90, 0.94] | [0.901, 0.942] |
| χ² values 5.99 / 7.38 / 0.05, 100-dof [74.2, 129.6], 50-dof [32.3, 71.4] | | 5.99 / 7.38 / 0.05, [74.2, 129.6], [32.4, 71.4] |
| MC NEES region, NIS region, autocorr. region | [1.5, 2.6], [0.65, 1.43], ±0.277 | [1.48, 2.59], [0.65, 1.43], ±0.277 |
| Matched (q = 1): single-run NEES points > 5.99 | 3–6 / 100 | 2 (q = 1), 6 (q = 9) |
| Matched: MC NEES / NIS / autocorr. points outside | 6 / 4 / 8 | 4 / 6 / 4 (q = 1); 2 / 9 / 9 (q = 9) |
| Matched: real-time time-avg NIS (region [0.74, 1.3]) | 0.936 | 0.878 / 0.864 |
| Mismatched (q_true = 9, q_filter = 1): single-run NEES > 5.99 | 41 / 100 | 43 / 100 |
| Mismatched: MC averages | all outside (upper) | NEES 98/98, NIS 97/98 above upper bound |
| Mismatched: real-time ρ(1) | 0.509 | 0.638 |

All deterministic quantities match to the printed precision; the random counts are within the
run-to-run spread expected for 50-run MC (the book's numbers come from one realisation).
Added for the project's gate: false-reject rate of a 2-dof χ² gate when the innovation covariance
is understated by ×2 / ×4 / ×9 → 22 % / 47 % / 72 % at α = 0.05 (5 % when correct), which is the
mechanism behind FINAL_RAPOR's "chi-square gate collapses under covariance misspecification".

## 8. Sequence Matching (Wang et al., TGRS 2024) on ALTO (`seqmatch_alto.py`) — re-implemented

No code is available (project site down), so Algorithm 1 (ISOMAP 1-D sorting of shuffled
satellite patches) and the LoFTR sequence matcher were re-implemented. ALTO Val here =
the paper's test split (1684 / 459 here vs 1683 / 458 in the paper).

**Sorting (Table IV, Table V, k sweep, sort-error histogram)**

| | Paper | Ours |
|---|---|---|
| S-ACC, ISOMAP (AlexNet, k = 3) | 0.990 | **1.000** |
| S-ACC, PCA / t-SNE | 0.004 / 0.004 | 0.007 / 0.037 |
| k sweep | stable for k ∈ [3, 8] | 1.00 for k = 3–8 (≥ 0.99), 0.83 at k = 9, ~0.11 for k ≥ 10, 0.03 at k = 2 |
| Sort-error histogram | 455 at 0, 2 at ±1 | 459 at 0 |
| VGG16 / ResNet18 / ResNet50 / DenseNet121 / ConvNeXt / ViT | 0.67 / 0.71 / 0.57 / 0.67 / 0.36 / 0.07 | 1.00 / 0.01 / 0.00 / 0.01 / 0.02 / 0.03 |

Important detail: the "AlexNet feature" must be the **convolutional (pool5, 9216-d) output**.
With the usual fc7 (4096-d) embedding ISOMAP reaches only 0.67–0.73 for k = 4–7 and 0.00 at
k = 3. With pooled-global features (ResNet/DenseNet/ConvNeXt/ViT) sorting fails in our runs
(≤ 0.03), lower than the paper's 0.36–0.71 for those backbones — the paper does not say which
layer is used for them, so the Table V ranking (AlexNet best, ViT worst) is reproduced but not
the intermediate values.

**Sequence matching (Table I "Ours", R@1 / R@5 / mAP, M = 10, LoFTR outdoor, 256 px)**

| | R@1 | R@5 | mAP |
|---|---|---|---|
| Paper | 41.63 | 99.11 | 69.42 |
| Ours, all 1684 queries | 35.21 | 75.30 | 54.21 |
| Ours, first 1300 queries | 41.1 | 91.9 | 65.2 |

The re-implementation matches the paper while the tracker stays locked (first 1300 frames),
then the forward-only candidate window ({I_s^j … I_s^(j+m)}, as written in the paper) overshoots
by one patch, the true patch falls behind the window, and the track is never recovered
(last 384 frames: R@1 15 %). The paper does not describe a recovery mechanism; sensitivity runs
with native 500 px matching and a window starting one patch behind j are listed below when done.

## 5. AnyVisLoc (Ye et al., CVPR-F 2026) — Table 6 aerial baseline (`anyvisloc_run.py`)

Setting as in the paper: CAMP retrieval + RoMa matching, top-5 re-ranking, `Topn_opt`, P3P,
yaw/pitch prior without noise, aerial reference map, 10 % subset (every 10th image).
Code: UAV-AVL/Benchmark @ `6c8f798` with `anyvisloc_lowmem.patch` (lazy map rotation, no change
to the method).

Paper (Table 6, aerial): R@1 61.6, A@5 74.1, A@10 87.7, A@20 94.2 (10 % subset: A@5 74.6,
A@10 87.6, A@20 94.2).

**First run (laptop, RTX 4060): 9 scenes, not comparable.** 378 images, A@5 96.8 / A@10 98.7 /
A@20 99.7, R@1 65.6 (scene mean A@5 94.6). Scenes 02–05 crashed (out of memory) and the others
were not run, so only 9 of 24 scenes are in it: 01, 15, 16, 18, 19, 20, 22, 23, 24. Scene_01 alone
is 185 of the 378 images (A@5 100 %). This number is far above the paper because the large and
hard scenes are missing; it must not be quoted as a reproduction.

**Full run (Kaggle, 2× T4): all 24 scenes, 2,018 images, in progress.** The 24 zips (62 GB)
were downloaded from the authors' OneDrive and the scenes split over the two GPUs (~1,000
images each, ~26 s/image, ~7.5 h). Finished scenes so far (2026-10-27 17:50 UTC):

| Scene | Images | A@5 (%) |
|---|---|---|
| Scene_01 | 185 | 100.0 |
| Scene_02 | 184 | 93.5 |
| Scene_04 | 299 | 89.6 |

Scenes 02 and 04 crashed on the laptop and now run without problems (5 GB of 31 GB RAM used).
The final image-weighted and scene-mean metrics replace this table when the run ends.

## 3. SatLoc (Zhou et al., Remote Sens. 2025) — Eq. (2) C1 on our fix records (`satloc_c1.py`)

The SatLoc dataset (529 GB) cannot be downloaded, so the confidence formula was evaluated on
the project's open-loop fix records (AUROC for "fix error ≤ 10 m"):

| Data | C_score as printed | C_score sign-corrected | C_res (GSD) | C1 corrected, w = 0.5 |
|---|---|---|---|---|
| AerialVL TEST | 0.243 | 0.757 | 0.712 | 0.773 |
| AnyVisLoc TEST | 0.218 | 0.782 | 0.634 | 0.753 |
| ALTO TEST | 0.349 | 0.651 | 0.551 | 0.633 |
| VPAIR TEST | 0.329 | 0.671 | 0.577 | 0.655 |
| UAV-VisLoc TEST | 0.486 | 0.514 | 0.501 | 0.494 |

As printed, `C_score = 1 − sigmoid((S_best − S_subopt) − Thrs_diff)` *falls* as the best match
stands out, contradicting the text ("a more concentrated distribution indicates higher
confidence"); its AUROC is exactly 1 − AUROC of the corrected form, i.e. it ranks fixes
backwards. The sign-corrected C_score equals the project's SatLoc-style heuristic (0.757 on
AerialVL TEST, as in FINAL_RAPOR §2). The GSD term adds a little on AerialVL (0.773) and
hurts elsewhere. Approximation: our records keep only the runner-up score (M = 1 sub-optimal).

## 6. UAV-VisLoc (Xu et al., 2024) — Table II (`uav_visloc_stats.py`)

- 6,774 drone images and CSV rows (paper: 6,742); 11 flights; 14 map files (flight 09 is split
  into 4 tiles that tile to exactly 44800 × 33280, as in the paper).
- Image sizes, capture months, flight heights match Table II for all flights (heights within
  1 m; flights 05 and 11 are listed as "/" in the paper — the CSV has ~2313 m and ~2573 m,
  i.e. MSL). Map sizes match for 10 / 11 flights; flight 06 map is 8082 × 9780 vs 4119 × 8592 in
  the paper (the released map is larger).
- Heading Φ: the paper's value matches the **first frame's** Phi1 for 6 of 10 flights
  (01: 163.9 vs 165, 03: −39.3 vs −40, 05: 91 vs 100, 08: 98 vs 100, 09: −53.7 vs −50,
  11: 96 vs 90); 02, 04, 06, 10 differ (by ~160–180°, i.e. likely the return leg / opposite
  convention). Flight 07 has no attitude columns and a malformed date (`2018071…`).

## 1. AerialVL (He et al., RA-L 2024) — Table VII protocol (`aerialvl_table7.py`)

The paper's tables are images; values were read from the PDF. Table VII (framework,
"Comb.1" = GeM-R50 + raw LK + SIFT tracking, "Comb.2" = MixVPR + DLK + SuperPoint tracking):

| | ST.5 (5.09 km) | LT.5 (7.83 km) | LT.6 (11.05 km) |
|---|---|---|---|
| Comb.1 Succ. Rate / MLE | 71.41 % / 20.01 m | 40.87 % / 26.92 m | 70.05 % / 17.89 m |
| Comb.2 Succ. Rate / MLE | 79.57 % / 22.27 m | 83.27 % / 14.22 m | 88.04 % / 17.50 m |

Sequence identification: the paper does not name its sequences. Paper lengths are a constant
~1.13 × the GNSS polyline length of our frames for exactly one assignment:
ST.5 = 2023-03-18-16-43-16 (4.54 km, project VAL), LT.5 = 2023-03-18-15-01-14 (6.88 km, VAL),
LT.6 = 2023-03-18-15-40-18 (9.87 km, TEST). The SatLoc paper's "AerialVL Comb. Method 1/2"
numbers (Table 4) are these values: "short" = ST.5 and "long" = mean of LT.5 and LT.6
(e.g. (40.87 + 70.05) / 2 = 55.5 %).

Not comparable 1:1: we have no VO, so the prediction is constant velocity from accepted fixes;
the acceptance gate is the project's frozen raw-score gate (E3, chosen on open-loop VAL fixes);
every second frame is used (~1 s).

## 4. Zhang et al. (UST 2026) — method re-implemented on AerialVL (`aerialvl_zhang.py`)

Paper results (Table II, proposed / pure VO), private data, no code:

| | Localized | Mean | Median | RMSE | Max | Final | ≤ 10 m | ≤ 20 m |
|---|---|---|---|---|---|---|---|---|
| Dataset 1 (371 frames, 0.6 km, 83 m AGL) | 371/371 | 8.1 | 7.2 | 8.9 | 19.2 | 13.8 | 80.3 % | 100 % |
| Dataset 1, pure VO | 326/371 | 55.2 | 45.4 | 66.3 | 130.1 | 44.0 | 9.2 % | 19.9 % |
| Dataset 2 (302 frames, 1.8 km, 100 m AGL) | 302/302 | 8.4 | 6.0 | 12.7 | 57.9 | 23.1 | 86.8 % | 92.4 % |
| Dataset 2, pure VO | 173/302 | 133.2 | 107.5 | 164.9 | 408.5 | 408.5 | 6.4 % | 6.9 % |

Their numbers cannot be re-run (data not released). The method is implemented as described
(Eqs. 5–10) and run on AerialVL, whose setting matches (gimbal nadir camera, ~1 Hz, north-up
map), with both papers' metrics. Deviations: SuperPoint + LightGlue instead of XFeat +
LightGlue (the paper states the framework is feature-agnostic); the map-alignment transform is
a similarity (project localizer); the gate thresholds are not given in the paper and were
fixed a priori (matches ≥ 30, inliers ≥ 20, inlier ratio ≥ frozen E3 0.367, mean reprojection
≤ 3 px, correction displacement ≤ 30 m; relocalization: 3×3 grid, 60 m spacing, ≤ 150 m);
AerialVL trajectories are 3–5× longer and flown higher (120–200 m) than Zhang's.

Note on the project's earlier wording: `src/gates.py` contains no Zhang-specific gate; the
comparison to Zhang in the proposal is conceptual (heuristic quality gating + relocalization
vs. calibrated reliability + chi-square gating).

## 14. Wang et al. (ISPRS Archives 2026) — not feasible

T.-C. Wang, L.-H. Tsou, J.-P. Jhan, R.-S. Tang, "UAV Visual Localization in GNSS-Denied
Environments," ISPRS Archives XLIX-B1-2026 (XXV ISPRS Congress). SuperPoint + LightGlue
matching to a true orthophoto and DSM, pose by IRLS, plus a reliability check of the estimated
pose. No code is released. The data are the authors' own flights (3,770 images at 100–250 m
over three terrain types; project NCSIST-ACOM-114-172C001), which are not public. Neither the
code nor the data can be obtained, so nothing can be re-run. The method is close to the project's
own pipeline (SuperPoint + LightGlue to an orthophoto), so it is used only as a conceptual
comparison.
