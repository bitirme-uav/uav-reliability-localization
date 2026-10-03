"""AerialVL 'VAL' bolumu icin veri yukleyici.

Klasor yapisi (AerialVL README.md):
    VAL/
      geo_referenced_map/
        @large_map@LTLon@LTLat@RBLon@RBLat@.tif
        @small_map@LTLon@LTLat@RBLon@RBLat@.tif
      long_trajtr/
        2023-03-16-18-04-01/
          @UTCTimeStamp@Longitude@Latitude@.png
          ...
        ... (6 sekans)
      short_trajtr/
        ... (5 sekans)

Ground truth dogrudan dosya adinda kodlanmis -- ayri bir CSV/label
dosyasi yok. Bu modul sadece dosya adlarini parse eder, hicbir goruntu
islemi yapmaz.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_MAP_RE = re.compile(
    r"^@(?P<name>[^@]+)@(?P<lt_lon>-?\d+\.?\d*)@(?P<lt_lat>-?\d+\.?\d*)@"
    r"(?P<rb_lon>-?\d+\.?\d*)@(?P<rb_lat>-?\d+\.?\d*)@\.tif$"
)
_FRAME_RE = re.compile(
    r"^@(?P<ts>-?\d+\.?\d*)@(?P<lon>-?\d+\.?\d*)@(?P<lat>-?\d+\.?\d*)@\.png$"
)


@dataclass(frozen=True)
class GeoMap:
    """Bir @map@.tif dosyasinin ayristirilmis hali.

    Harita 'north-heading' -- ust-sol (left-top) ve alt-sag (right-bottom)
    koseleri lon/lat cinsinden dosya adinda veriliyor.
    """
    path: Path
    name: str
    lt_lon: float
    lt_lat: float
    rb_lon: float
    rb_lat: float

    @property
    def lon_min(self) -> float:
        return min(self.lt_lon, self.rb_lon)

    @property
    def lon_max(self) -> float:
        return max(self.lt_lon, self.rb_lon)

    @property
    def lat_min(self) -> float:
        return min(self.lt_lat, self.rb_lat)

    @property
    def lat_max(self) -> float:
        return max(self.lt_lat, self.rb_lat)

    def contains(self, lon: float, lat: float) -> bool:
        return self.lon_min <= lon <= self.lon_max and self.lat_min <= lat <= self.lat_max


@dataclass(frozen=True)
class Frame:
    """Bir @ts@lon@lat@.png karesinin ayristirilmis hali (ground truth dahil)."""
    path: Path
    utc_ts: float
    lon: float
    lat: float
    sequence: str
    sequence_kind: str  # 'long' veya 'short'


def parse_map_filename(path: Path) -> GeoMap:
    m = _MAP_RE.match(path.name)
    if not m:
        raise ValueError(f"harita dosya adi beklenen formata uymuyor: {path.name}")
    g = m.groupdict()
    return GeoMap(
        path=path, name=g["name"],
        lt_lon=float(g["lt_lon"]), lt_lat=float(g["lt_lat"]),
        rb_lon=float(g["rb_lon"]), rb_lat=float(g["rb_lat"]),
    )


def parse_frame_filename(path: Path, sequence: str, sequence_kind: str) -> Frame:
    m = _FRAME_RE.match(path.name)
    if not m:
        raise ValueError(f"kare dosya adi beklenen formata uymuyor: {path.name}")
    g = m.groupdict()
    return Frame(
        path=path, utc_ts=float(g["ts"]), lon=float(g["lon"]), lat=float(g["lat"]),
        sequence=sequence, sequence_kind=sequence_kind,
    )


class AerialVLVal:
    """VAL/ kok dizinini tarayip haritalari ve sekanslari indeksler."""

    def __init__(self, val_root: str | Path):
        self.root = Path(val_root)
        self.maps: list[GeoMap] = []
        self.sequences: dict[str, list[Frame]] = {}
        self._scan()

    def _scan(self) -> None:
        map_dir = self.root / "geo_referenced_map"
        if map_dir.is_dir():
            for p in sorted(map_dir.glob("*.tif")):
                try:
                    self.maps.append(parse_map_filename(p))
                except ValueError:
                    continue

        for kind, subdir in (("long", "long_trajtr"), ("short", "short_trajtr")):
            root = self.root / subdir
            if not root.is_dir():
                continue
            for seq_dir in sorted(p for p in root.iterdir() if p.is_dir()):
                frames = []
                for p in sorted(seq_dir.glob("*.png")):
                    try:
                        frames.append(parse_frame_filename(p, seq_dir.name, kind))
                    except ValueError:
                        continue
                if frames:
                    frames.sort(key=lambda f: f.utc_ts)
                    self.sequences[seq_dir.name] = frames

    def map_for(self, lon: float, lat: float) -> GeoMap | None:
        """Verilen koordinati iceren haritayi dondurur (yoksa None).

        Birden fazla eslesirse en kucuk alanli (en yuksek cozunurluklu
        olma ihtimali yuksek) haritayi tercih eder.
        """
        candidates = [m for m in self.maps if m.contains(lon, lat)]
        if not candidates:
            return None
        def area(m: GeoMap) -> float:
            return (m.lon_max - m.lon_min) * (m.lat_max - m.lat_min)
        return min(candidates, key=area)

    def all_frames(self) -> list[Frame]:
        out: list[Frame] = []
        for frames in self.sequences.values():
            out.extend(frames)
        return out

    def summary(self) -> str:
        lines = [f"Haritalar: {len(self.maps)}"]
        for m in self.maps:
            lines.append(f"  - {m.name}: lon[{m.lon_min:.5f},{m.lon_max:.5f}] "
                         f"lat[{m.lat_min:.5f},{m.lat_max:.5f}]")
        lines.append(f"Sekanslar: {len(self.sequences)} "
                     f"(toplam {sum(len(v) for v in self.sequences.values())} kare)")
        for name, frames in sorted(self.sequences.items()):
            lines.append(f"  - {name} ({frames[0].sequence_kind}): {len(frames)} kare")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    val = AerialVLVal(sys.argv[1] if len(sys.argv) > 1 else "AerialVL_data/images/VAL")
    print(val.summary())
