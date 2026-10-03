# Calibrated Reliability-Aware RGB Map Relocalization — çalışma alanı

Bu klasör, `Calibrated Reliability-Aware RGB Map Relocalization for
GPS/GNSS-Denied UAV Navigation.pdf` proje önerisinin **Ay-1 minimum
kapsamının** koduna ayrılmıştır. **Bu proje Gazebo/ROS2/SWIL/HIL
firmware projesiyle TEKNİK OLARAK İLİŞKİSİZDİR** — doküman açıkça
"mandatory ROS 2/Gazebo" ve "Gazebo... not recommended as core
dependencies" diyor (§5, §13). Burada yapılan iş saf computer-vision +
istatistiksel kalibrasyon araştırması; "simülatör" sadece saf Python'da
ground-truth rotaya drift ekleyen bir döngü.

## Dizin yapısı

```
uav_reliability_localization/
  venv/                    Python venv (torch+cu124, LightGlue, rasterio, sklearn, ...)
  src/
    aerialvl_loader.py     AerialVL VAL/ klasör parser'ı (dosya adından ground truth)
    geo_utils.py           lon/lat <-> ENU metre dönüşümleri, haversine
    fix_record.py          §7 fix-record şeması (JSONL logger)
    localization_pipeline.py  SuperPoint+LightGlue+RANSAC -> harita fix'i (M2)
    drift_simulator.py     M6: mild/moderate/severe drift enjeksiyonu -- TEST EDİLDİ
    gates.py                M8/M9: chi-square gate, reliability policy, REACQUIRE -- TEST EDİLDİ
    reliability_model.py    M5.4: kalibre edilmiş güvenilirlik modeli -- TEST EDİLDİ
    visualize_pairs.py      Ay-1 çıkış kriteri: ≥20 query/map çifti görselleştirme
    run_month1_demo.py      Ay-1 çıkış kriteri: tek query -> metrik fix
  requirements.txt
  outputs/                 üretilen görseller/loglar

/media/davut/disk2/proje/uav_vloc_datasets/
  AerialVL/                 github.com/hmf21/AerialVL (kod/README, veri değil)
  AerialVL_data/images/VAL/ asıl veri: geo_referenced_map/ + long_trajtr/ + short_trajtr/
    (VAL.zip.001-027 Tsinghua Cloud + HuggingFace CDN'den indirildi, ardından
     birleştirilip açıldı -- bkz. merge_and_extract_val.sh)
```

## Neden bu dataset (AerialVL)

Doküman §8.1: "primary" ve zorunlu dataset. 11 gerçek UAV uçuş sekansı
(~70km toplam), 2 georeferenced uydu haritası, ground truth DOĞRUDAN
dosya adında kodlu (`@UTCTimeStamp@Longitude@Latitude@.png`). MIT/CC-BY
lisanslı, indirilebilir. VPR/vpr_training_data (retrieval MODELİ
EĞİTİMİ için, ~88GB) İNDİRİLMEDİ -- bu proje kendi retrieval modelini
eğitmiyor, hazır/pretrained SuperPoint+LightGlue kullanıyor (M2).

## Çalıştırma

```bash
VENV=/media/davut/disk2/proje/uav_reliability_localization/venv
cd /media/davut/disk2/proje/uav_reliability_localization/src

# 1) Veri okunuyor mu, koordinatlar doğru mu?
$VENV/bin/python aerialvl_loader.py /media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted/VAL

# 2) Ay-1 kriteri: >=20 query/map çifti görselleştir
$VENV/bin/python visualize_pairs.py <VAL_kok> --n 25 --out ../outputs/pairs.png

# 3) Ay-1 kriteri: tek query -> metrik fix
$VENV/bin/python run_month1_demo.py <VAL_kok> --seed 0

# 4) Veri gerektirmeyen modüllerin kendi self-testleri:
$VENV/bin/python drift_simulator.py
$VENV/bin/python gates.py
$VENV/bin/python reliability_model.py

# 5) Faz E: GERÇEK localization + drift + gate'ler TEK sekansta (M6-M9 entegre)
$VENV/bin/python run_phase_e.py <VAL_kok> --sequence <sekans_adi> \
  --max-frames 150 --call-interval-s 3 --drift-regime moderate --seed 0 \
  --r-nominal-sigma-m 15

# 6) Kalibre model eğitimi (sequence-disjoint) + held-out testte kullanımı
$VENV/bin/python train_and_save_model.py <held_out_sekans_adi>
$VENV/bin/python run_phase_e.py <VAL_kok> --sequence <held_out_sekans_adi> \
  --reliability-model ../outputs/reliability_model.pkl ...

# 7) Açık-döngü eşik seçimi (E2_accept_all verisiyle risk-coverage)
$VENV/bin/python select_threshold.py
```

## Ay-1 sonrası — DURUM (gece oturumu sonrası, PROGRESS_RAPORU.md'de ayrıntılı)

**Tamamlanan:**
- ✅ **Faz E** (M6+M7+M8+M9 entegre navigasyon döngüsü) `run_phase_e.py`
  ile YAZILDI ve GERÇEK AerialVL verisiyle test edildi. 4-5 politika
  (E1/E2/E3/E5/E7) aynı gerçek fix akışında karşılaştırılıyor.
- ✅ **M4 tam özellik seti**: `mahalanobis_d`, `inlier_spatial_spread`,
  `transform_condition`, `query_ref_scale_ratio` artık FixRecord'a
  yazılıyor (ilk denemede eksikti, AUROC 0.479→0.731'e sıçramasının
  nedeni buydu).
- ✅ **M5.4 kalibre model GERÇEK veriyle eğitildi**: AUROC=0.731,
  held-out sekansta chi-square gate'i (RMSE 38m→8.68m) geçti — ama
  genel veri setinde (select_threshold.py) sağlam bir eşik BULUNAMADI,
  bkz. PROGRESS_RAPORU.md "dürüst negatif/karışık sonuç" bölümü.
- ✅ **M7 dinamik arama yarıçapı** (`r=clip(3σ_pos,r_min,r_max)`) eklendi.

**Hâlâ eksik/devam ediyor:**
- **M2 gerçek çoklu-aday retrieval**: hâlâ tek-crop + çok-ölçekli
  basitleştirme (`top1_score`/`top1_top2_margin` dolmuyor). Doğruluk
  düşük ve sekanslar arası çok değişken (median 8m-400m).
- **Sequence-bazlı TAM train/val/test ayrımı + configuration freeze**
  (§9.1) — şu an ad-hoc tek-sekans held-out kullanıldı, resmi değil.
- **M10 tam call-rate sweep** (birden fazla call_interval karşılaştırması).
- **M11 Jetson Orin Nano deployment** (donanım henüz yok).
- **E11/E12**: büyük-drift kurtarma senaryoları (Scenario A/B), AnyVisLoc
  cross-dataset transfer.
- **M5.2 heuristic (SatLoc-style) parametre tuning**.

## Önemli kurallar (dokümandan, asla ihlal edilmemeli)

- Hiçbir gate/policy/reliability-model fonksiyonu `fix_error_m` veya
  ondan türetilmiş hiçbir niceliği GİRDİ olarak kullanamaz (label leakage).
- M3 etiket eşikleri (10m primary, 25m secondary) SONUÇLAR GÖRÜLDÜKTEN
  SONRA değiştirilemez.
- Kalibrasyon/tuning SADECE train/validation sequence'lerinde; test
  sequence'leri configuration-freeze'e kadar hiç işlenmez (§9.1).
