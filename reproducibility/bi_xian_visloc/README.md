# Reproduction: Bi et al. (ISPRS J. 2026), XIAN-Visloc retrieval results

C. Bi et al., "UAV coarse visual localization in large-scale continuous scenes," ISPRS J. Photogramm.
Remote Sens., vol. 238, pp. 243–260, 2026, doi: 10.1016/j.isprsjprs.2026.04.054.

- Code: https://github.com/VERYBC/UCVL @ `020c3e6` (released code, evaluation only, no training)
- Weights: released `BEMN-Tiny.pth` (148 MB) and `BEMN-Base.pth` (458 MB) from the authors' Google Drive
- Data: XIAN-Visloc from Hugging Face (`VERYBC/XIAN_Visloc`), test flights 16–19 (Xi'an, same-area)
  and Weinan 01–02 (cross-area)
- Hardware: Kaggle notebook, 2× Tesla T4 (15 GB), 31 GB RAM, run on 2026-10-26
- Exact commands: `run_on_kaggle.sh` (XIAN-Visloc), `run_realworld_on_kaggle.sh` (real-world flights); per-flight numbers: `results/per_flight_summary.txt`

## Result

| Setting | Source | R@1 | AP | Dis@1 (m) |
|---|---|---|---|---|
| **Same-area, BEMN-T, no retrieval method** | Paper, Tables 7 & 9 | 72.21 | 71.13 | 216.14 |
| | Ours | **75.63** | **74.31** | **452.86** |
| **Same-area, BEMN-T, SC+GA** | Paper, Table 9 | 72.21 | 70.97 | 216.14 |
| | Ours | 75.14 | 73.34 | 478.50 |
| **Same-area, BEMN-T, SC+GA+CM (full method)** | Paper, Tables 4 & 9 | 74.14 | 71.90 | 216.49 |
| | Ours | **76.18** | **73.88** | **477.56** |
| **Same-area, BEMN-B, no retrieval method** | Paper, Table 7 | 75.53 | 73.94 | 164.41 |
| | Ours | 79.40 | 78.50 | 366.83 |
| Same-area, BEMN-B, SC+GA | Ours (SC+GA+CM ran out of RAM) | 79.40 | 77.27 | 366.83 |
| **Cross-area (Weinan), BEMN-T, no retrieval method** | Paper, Table 7 | 53.76 | 43.58 | 645.20 |
| | Ours | **80.28** | **64.44** | **240.50** |
| Cross-area, BEMN-T, full method | Paper, Table 4 | 55.89 | 45.08 | 632.05 |
| Cross-area, BEMN-T, SC+GA | Ours (SC+GA+CM ran out of RAM) | 80.28 | 65.49 | 240.50 |

SC = semantic-space clustering, GA = geospatial aggregation, CM = center-region matching.
Dis@1 = mean distance between the true UAV position and the centre of the top-1 tile.

## Conclusion

**Partially reproduced.**

1. **Same-area R@1 and AP are reproduced within 2–4 points, in our favour.** The effect of the
   retrieval methods also matches the paper qualitatively. SC+GA leaves R@1 practically unchanged
   (paper: unchanged; ours: −0.5). CM adds about one point (paper: +1.9; ours: +1.0).
2. **Dis@1 is not reproduced: ours is about 2× the paper's value.** Dis@1 is a mean, and it is
   dominated by a few gross errors. On flight 16 the top-1 error has a median of 68 m, but 16 % of
   queries are more than 500 m off (the maximum is 16 km, i.e. a tile on another map). The mean
   is 675 m; without errors above 1 km it is 84 m. A small difference in the number of gross
   errors therefore doubles Dis@1, while R@1 hardly moves.
3. **The released BEMN-T checkpoint is the paper's real-world model (§5.9), not the XIAN-Visloc
   model of Tables 4, 7 and 9.** On real-world trajectory 1 it gives R@1 56.00 / AP 40.06 /
   Dis@1 1027.41 m, identical to Table 13 ("BEMN-T w/SC") to two decimals (see below). On XIAN-Visloc:
   - Cross-area (Weinan, an area the paper's model never saw) is far *better* than in the paper:
     R@1 80.3 vs 53.8, Dis@1 241 m vs 645 m.
   - BEMN-B is almost perfect on flights 18 and 19 (R@1 96.6 / 96.9, Dis@1 ≈ 50 m), but only
     44.1 % on flight 16.

   This fits a real-world model trained on more data than flights 1–15. The paper does not say
   what it was trained on; this question should go to the corresponding author
   (liuganchao@nwpu.edu.cn). The XIAN-Visloc models are not released, so Tables 4, 7 and 9 cannot be
   reproduced exactly. These weights must not be used to claim unseen-area (cross-area)
   performance on XIAN-Visloc.

### Evidence on the released checkpoints (checked 2026-10-27)

- The weights link appears only in README section 3, "Real-world flight data test". The released
  `eval_real_world.py` defaults to `dataset_name='Real-world filght data'`, `TEST_LIST=[1,2,3]`.
- The README of March 2026 said for XIAN-Visloc/UAV-Visloc tests: "We will soon supplement the
  code!" (commit `2cc0b9f`). That section was replaced by the real-world test and never added back.
- Paper §5.9: the real-world area is "entirely independent of XIAN-Visloc". A model for it can be
  trained on all of XIAN-Visloc, including test flights 16–21. The paper does not say which model
  was used there.
- Paper Table 10 shows several training variants (CMS, AMS+CMS, UAV-Visloc, UAV-Visloc fine-tuned
  on XIAN-Visloc). Its best cross-area XIAN-Visloc result is R@1 73.81; the released BEMN-T gives
  80.28, above every model in the paper.
- Training code is not released (issue #1: "may not be released in the short term").
- **Real-world flight test (decisive check).** The released BEMN-T was run on the real-world
  flight data (`Real-world flight data.zip` on the HF dataset) with the unmodified
  `eval_real_world.py` (SC+GA+CM) and the authors' library script. Results:

  | Trajectory | Gallery | R@1 | R@5 | AP | Dis@1 (m) |
  |---|---|---|---|---|---|
  | 1 (ours) | 6417 | **56.00** | 70.67 | **40.06** | **1027.41** |
  | 1, paper Table 13, BEMN-T w/SC | | 56.00 | | 40.06 | 1027.41 |
  | 2 (ours) | 6580 | 52.62 | 76.56 | 44.16 | 916.07 |

  Trajectory 1 matches the paper exactly. Two changes were needed to run it: the data path must
  contain `Xian_visloc` (same dataset-class issue as above, even for the authors' own real-world
  script), and center-region features were stored as fp16 instead of fp32 on CPU, because fp32 ran
  out of 31 GB RAM. The exact match shows the fp16 change has no effect on the metrics.
  Trajectory 3 and BEMN-B were not finished: the Kaggle session was closed once, and BEMN-B with
  center-region matching crashed the notebook (out of RAM). Raw numbers:
  `results/realworld_partial.txt`.

## Checks done

- **Tile library.** It was rebuilt with the authors' script (`XIAN_Visloc_same_AMS_test.py`, only
  the path changed). Gallery sizes match the paper (Table 5): 3928 tiles for flights 16/17 and
  3432 for flight 18. The zip also contains the authors' own prebuilt library for flight 16
  (`satellite_test_392`). It has the same number of tiles, but tile centres and sizes differ.
  With it, flight 16 gives R@1 69.2 / AP 52.0 instead of 57.6 / 63.0. So R@1 and AP depend on
  how the library is built, because the positive tiles change. Dis@1 does not (675 m vs 673 m).
- **Checkpoint loading.** Both checkpoints load completely (Tiny 335/335 keys, Base 375/375 keys,
  no missing or unexpected keys). The authors' `strict=False` therefore hides nothing.
- **Georeferencing of XIAN-Visloc** (an open item in our proposal). The Xi'an maps are GeoTIFFs in
  EPSG:3857 with 0.2986 m pixels. That is ≈ 0.247 m on the ground at 34° N, the value stated in
  the paper, and it agrees with `satellite_coordinates_range.csv`.

## Problems found in the released code and data

1. `scripts/XIAN_Visloc_cross_AMS_test.py` has `target_size = (3,3)`, which would shrink every
   tile to 3×3 pixels. The README's 392×392 was used instead.
2. `sample4geo/dataset/visloc.py` chooses the coordinate columns only if the path contains the
   exact string `Xian_visloc`; otherwise the run fails with `AttributeError ... coordinates`.
   We worked around it with a symlink named `Xian_visloc`.
3. The authors' prebuilt library for flight 16 contains a stray duplicate tile,
   `01_00199 - 副本.tif` ("副本" = "copy").
4. Center-region matching keeps region features of the whole gallery in RAM. It does not fit in
   31 GB for BEMN-Base (same-area) or for the Weinan gallery with BEMN-Tiny (both processes were
   killed, exit code 137). For those cases SC+GA is reported instead; CM changed R@1 by only
   +1.0 for BEMN-Tiny.
5. `sample4geo/model.py` sets `HF_ENDPOINT=https://hf-mirror.com`. It worked on Kaggle, but the
   backbones are then downloaded from a third-party mirror.
6. Dataset notes: Xi'an CSVs have `id,file_name,latitude,longitude` (no altitude). Weinan CSVs
   also have an altitude column (≈ 350 m). Flights 16/17 are 490×490 images, flights 18/19 are
   3840×2160. There are no timestamps or camera attitude.

## Relevance for our project

- XIAN-Visloc is usable as a second dataset for retrieval experiments: the georeferencing is
  correct, and frame order and positions are available. The missing timestamps and attitude still
  limit sequential replay.
- The heavy tail of the top-1 error is direct evidence for our motivation. With R@1 around 75 %,
  about one query in six still gets a confident top-1 tile that is hundreds of metres to
  kilometres away. A geographic fix built on such a tile is exactly the "convincing but wrong"
  fix that the reliability gate has to reject.
- The released BEMN-T weights can serve as a retrieval front end or baseline, with the caveat
  in point 3 of the conclusion.
