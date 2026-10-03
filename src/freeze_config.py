"""Configuration freeze (SS9.1): tum kod, model ve esik dosyalarinin
SHA-256 ozetlerini kaydeder. TEST kosulari bundan sonra yapilir; TEST
sonuclarina gore hicbir dosya degistirilmez. verify modu, TEST
kosularindan sonra hicbir seyin degismedigini kontrol eder."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src").glob("*.py")) + [
    "src/run_val_pipeline.sh",
    "outputs/calibration_models.pkl",
    "outputs/thresholds.json",
]
MANIFEST = ROOT / "outputs" / "config_freeze.json"


def digest(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


if len(sys.argv) > 1 and sys.argv[1] == "verify":
    m = json.loads(MANIFEST.read_text())
    bad = [f for f, h in m["files"].items() if digest(f) != h]
    print("DEGISMEMIS" if not bad else f"DEGISEN DOSYALAR: {bad}")
    sys.exit(1 if bad else 0)

m = {"frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"), "files": {f: digest(f) for f in FILES}}
MANIFEST.write_text(json.dumps(m, indent=2))
print(f"{len(FILES)} dosya donduruldu -> {MANIFEST}")
