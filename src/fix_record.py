"""Ortak fix-record semasi (proje onerisi SS7, 'Common Fix-Record Interface').

Alanlar aynen dokumandaki listeyle eslesecek sekilde tanimlandi.
[eval] ile isaretli alanlar SADECE degerlendirme/loglama icin -- hicbir
gate/policy fonksiyonu bu alanlari GIRDI olarak KULLANMAMALI (label
leakage yasagi, M4 notu: "Never use ground-truth error or any quantity
derived from the label. ... never part of the label").
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional


@dataclass
class FixRecord:
    # --- run identity / reproducibility ---
    run_id: str = ""
    policy_id: str = ""
    seed: int = 0
    drift_regime: str = ""
    filter_noise_setting: str = ""
    call_interval_s: float = 0.0
    sequence_id: str = ""
    query_id: str = ""
    timestamp_s: float = 0.0
    magnitude_idx: Optional[int] = None
    direction_idx: Optional[int] = None
    mode: str = "NORMAL"  # NORMAL / REACQUIRE / LOST

    # --- state ---
    ground_truth_x_m: float = 0.0        # [eval]
    ground_truth_y_m: float = 0.0        # [eval]
    prior_x_m: float = 0.0
    prior_y_m: float = 0.0
    prior_cov_xx: float = 0.0
    prior_cov_xy: float = 0.0
    prior_cov_yy: float = 0.0

    # --- localization geometry ---
    true_offset_m: float = 0.0           # [eval]
    offset_bin: Optional[str] = None
    search_window_m: float = 0.0
    in_window: Optional[bool] = None     # [eval]

    # --- fix ---
    predicted_fix_x_m: Optional[float] = None
    predicted_fix_y_m: Optional[float] = None
    raw_confidence: Optional[float] = None
    heuristic_confidence: Optional[float] = None
    calibrated_reliability: Optional[float] = None
    chi2_d2: Optional[float] = None
    confirmation_count: Optional[int] = None
    fix_error_m: Optional[float] = None          # [eval]
    safe_primary: Optional[bool] = None           # [eval] (<=10m, M3)
    safe_secondary: Optional[bool] = None         # [eval] (<=25m, M3)
    decision: str = ""  # accept / down-weight / reject / pending-confirmation

    # --- raw runtime features (M4, girdi olarak kullanilabilir) ---
    top1_score: Optional[float] = None
    top1_top2_margin: Optional[float] = None
    retrieval_entropy: Optional[float] = None
    num_matches: Optional[int] = None
    inlier_count: Optional[int] = None
    inlier_ratio: Optional[float] = None
    reprojection_error_px: Optional[float] = None
    inlier_spatial_spread: Optional[float] = None
    transform_condition: Optional[float] = None
    query_ref_scale_ratio: Optional[float] = None
    mahalanobis_d: Optional[float] = None

    # --- cost ---
    localization_latency_ms: Optional[float] = None
    confidence_latency_ms: Optional[float] = None
    power_w: Optional[float] = None
    energy_per_fix_j: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


# M3: Ground-truth-only good/unsafe label -- sabit, sonuclar goruldukten
# SONRA degistirilmemeli (proje kurali).
SAFE_PRIMARY_THRESHOLD_M = 10.0
SAFE_SECONDARY_THRESHOLD_M = 25.0


def label_fix(rec: FixRecord) -> None:
    """fix_error_m doluysa safe_primary/safe_secondary'yi hesaplar (yerinde günceller)."""
    if rec.fix_error_m is None:
        return
    rec.safe_primary = rec.fix_error_m <= SAFE_PRIMARY_THRESHOLD_M
    rec.safe_secondary = rec.fix_error_m <= SAFE_SECONDARY_THRESHOLD_M


class FixRecordWriter:
    """JSONL'e satır satır fix-record yazar (append-only, çökme-güvenli)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, rec: FixRecord) -> None:
        self._fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "FixRecordWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def load_records(path: str | Path) -> list[FixRecord]:
    out = []
    field_names = {f.name for f in fields(FixRecord)}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(FixRecord(**{k: v for k, v in d.items() if k in field_names}))
    return out
