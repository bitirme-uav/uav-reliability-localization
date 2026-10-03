"""AnyVisLoc sahne ayrimi -- SONUCLARA BAKMADAN sabitlendi (2026-10-03).
TUNE: platform/konvansiyon ayari icin bakilan sahneler (01, 03).
Kalan 22 sahne sabit tohumla karistirilip ikiye bolundu: RECAL (gelistirme /
yeniden kalibrasyon) ve TEST (yalnizca bir kez, en sonda)."""
import random

TUNE_SCENES = ("01", "03")
_rest = [f"{i:02d}" for i in range(1, 25) if f"{i:02d}" not in TUNE_SCENES]
random.Random(20261003).shuffle(_rest)
RECAL_SCENES = tuple(sorted(_rest[:11]))
TEST_SCENES = tuple(sorted(_rest[11:]))

if __name__ == "__main__":
    print("TUNE ", TUNE_SCENES); print("RECAL", RECAL_SCENES); print("TEST ", TEST_SCENES)
