"""Veri seti kok dizini.

Varsayilan: proje klasorunun yanindaki ../uav_vloc_datasets/
Farkli bir yerdeyse UAV_DATA_ROOT ortam degiskeniyle ver:
    export UAV_DATA_ROOT=/yol/uav_vloc_datasets        (Linux)
    $env:UAV_DATA_ROOT = "D:/yol/uav_vloc_datasets"    (PowerShell)
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("UAV_DATA_ROOT", PROJECT_ROOT.parent / "uav_vloc_datasets"))
