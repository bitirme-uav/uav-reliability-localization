"""Her sahne icin: zip'ten satellite_map.png + referans json + DSM -> satellite_{s}.tif
(sahte lon/lat sinirli, en az 0.3 m/px'e kucultulmus, JPEG sikistirmali) + satellite_{s}.json
(duz format) + dsm_{s}.npy. PNG gecici olarak RAM'de acilir, diske yazilmaz."""
import io, json, sys, zipfile
import cv2, numpy as np, rasterio
from rasterio.transform import from_bounds
from anyvisloc_loader import ROOT, local_to_lonlat

MIN_RES = 0.3
for s in sys.argv[1:] or [f"{i:02d}" for i in range(1, 25)]:
    tif, js = ROOT / f"satellite_{s}.tif", ROOT / f"satellite_{s}.json"
    z = zipfile.ZipFile(ROOT / f"Scene_{s}.zip")
    ref = [n for n in z.namelist() if n.endswith("_reference.json")]
    if ref:
        j = json.load(z.open(ref[0]))["modes"]["satellite"]
        json.dump(j, open(js, "w"), indent=1)
    j = json.load(open(js))
    dsm = ROOT / f"dsm_{s}.npy"
    if not dsm.exists():
        np.save(dsm, np.load(io.BytesIO(z.read(f"Scene_{s}/satellite_dsm.npy"))))
    if tif.exists():
        print(s, "var"); continue
    buf = np.frombuffer(z.read(f"Scene_{s}/satellite_map.png"), np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR); del buf
    res = j["map_resolution"][0]; ox, oy = j["map_origin_local"]
    h, w = img.shape[:2]
    assert [h, w] == list(j["map_size"]), (s, img.shape, j["map_size"])
    W, N = local_to_lonlat(ox, oy)                    # sol-ust (satir 0 = en kucuk y = en kuzey)
    E, S_ = local_to_lonlat(ox + w * res, oy + h * res)
    if res < MIN_RES:
        f = res / MIN_RES; img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    with rasterio.open(tif, "w", driver="GTiff", width=img.shape[1], height=img.shape[0], count=3, dtype="uint8",
                       crs="EPSG:4326", transform=from_bounds(W, S_, E, N, img.shape[1], img.shape[0]),
                       compress="jpeg", tiled=True) as ds:
        ds.write(img[:, :, ::-1].transpose(2, 0, 1))
    print(s, f"{w}x{h} @{res:.3f} -> {img.shape[1]}x{img.shape[0]}  {tif.stat().st_size/1e6:.0f} MB", flush=True)
