"""Kamera montaj/egiklik ofseti (boresight) duzeltmesi.

analyze_bias.py (SADECE TRAIN sekanslari, 83 hareketli guvenilir fix):
  along = -0.026 * hiz - 15.70  -> egim ~0 (zaman gecikmesi DEGIL),
  sabit ~ -15.7m: goruntu merkezinin isaret ettigi zemin noktasi GPS
  konumunun ucus yonunde ~15.7m GERISINDE (kamera hafif geriye egik veya
  kamera/anten ofseti). Sekanslar arasi tutarli (-11..-20m).

Calisma aninda ucus yonu, navigasyon tahmininin (prior) hizindan alinir --
ground truth'tan DEGIL. Hiz cok dusukse (yon belirsiz) duzeltme uygulanmaz.

Bu bir LOKALIZER KALIBRASYON parametresidir (kamera dis parametresi gibi),
guvenilirlik ozelligi degil; TRAIN uzerinde tahmin edilip config freeze'de
sabitlenir (SS9.1).
"""
from __future__ import annotations

import numpy as np

ALONG_TRACK_OFFSET_M = 15.7   # TRAIN'den tahmin edildi, 2026-10-01
MIN_SPEED_FOR_CORRECTION = 1.0  # m/s


def correct_fix_enu(fix_e: float, fix_n: float, vel_e: float, vel_n: float,
                    offset_m: float = ALONG_TRACK_OFFSET_M) -> tuple[float, float]:
    """ENU fix'i, ucus yonunde offset_m kadar ileri kaydirir."""
    speed = float(np.hypot(vel_e, vel_n))
    if speed < MIN_SPEED_FOR_CORRECTION:
        return fix_e, fix_n
    return fix_e + offset_m * vel_e / speed, fix_n + offset_m * vel_n / speed
