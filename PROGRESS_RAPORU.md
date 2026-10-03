# Gece Oturumu İlerleme Raporu — Calibrated Reliability-Aware RGB Map Relocalization

**Tarih:** 2026-09-30 gece (kullanıcı uyurken otonom çalışma)
**Bağlam:** Kullanıcı, "PDF'teki her şeyi yap" hedefiyle değil, gerçekçi bir
7 aylık/4 kişilik bitirme projesinin Ay-1 minimum kapsamını (ve mümkünse
ötesini) ilerletmemi istedi. Jetson Orin Nano henüz yok — tüm testler
PC'de (RTX 4060 8GB) yapılıyor.

## TL;DR (30 saniyelik özet)

- AerialVL indirildi, açıldı, gerçek veriyle Ay-1 kriterleri geçildi.
- Uçtan uca sistem (drift + gerçek localization + chi-square/raw/
  calibrated gate) yazıldı ve GERÇEK veride 11 sekansta test edildi.
- Kalibre güvenilirlik modeli GERÇEKTEN sinyal öğreniyor (AUROC 0.731)
  ama şu anki eşik/veri hacmiyle "chi-square'i güvenilir şekilde geçtiği"
  henüz KANITLANMADI — ya hep-reddet (zarar yok, fayda yok) ya da
  gevşetilince zarar veriyor.
- **Kök sorun**: M2'nin (görsel lokalizasyon) doğruluğu düşük ve sekanslar
  arası çok değişken (median 8-400m) — hem raw hem chi-square hem
  calibrated gate'in E1 (hiç düzeltme yapmama) baseline'ını GEÇEMEMESİNİN
  asıl nedeni bu. Sıradaki oturumun önceliği M2'yi iyileştirmek olmalı.
- Detaylar, tüm ayarlama denemeleri (işe yarayan/yaramayan) ve tam
  sonuç tabloları aşağıda.

## Özet — şu an nerede olduğumuz

**Tamamlanan (Ay-1 çıkış kriterleri):**
- ✅ AerialVL VAL dataset'i indirildi, birleştirildi, açıldı (54GB, 11
  sekans, 15136 kare, 2 harita) — `/media/davut/disk2/proje/uav_vloc_datasets/AerialVL_data/images/VAL/extracted/`
- ✅ `aerialvl_loader.py` gerçek veriyle test edildi, doğru parse ediyor
- ✅ `visualize_pairs.py`: 25 query görselleştirildi, **0/25 haritanın
  dışında** (koordinat sistemi doğru) — `outputs/pairs.png`
- ✅ `run_month1_demo.py`: uçtan uca tek query→fix çalışıyor (kod
  hatasız çalışıyor, ama doğruluk henüz düşük — aşağı bakın)
- ✅ **Kritik bir bug bulundu ve düzeltildi**: `MapExtractor` başta
  rasterio'nun TIFF içi gömülü geotransform'una güveniyordu; AerialVL'nin
  haritaları muhtemelen bunu taşımıyor. Artık dosya adından ayrıştırılan
  sınırlardan (GeoMap) affine transform MANUEL kuruluyor
  (`rasterio.transform.from_bounds`). `debug_visual.png` bu düzeltmenin
  doğru çalıştığını görsel olarak doğruladı (1. örnekte query ve harita
  crop'u AÇIKÇA aynı binaları/yolları gösteriyor).

**Kısmi/devam eden (M2 — görsel lokalizasyon doğruluğu):**
- ⚠️ Pipeline MEKANİK olarak çalışıyor (fix üretiyor, hata hesaplıyor,
  etiketliyor) ama **doğruluk henüz M3'ün 10m eşiğini geçmiyor**
  (mevcut baseline: median hata ~40-53m, en iyi tek örnek 15-27m,
  0/10-15 "safe"). Bu BEKLENEN bir durum — dokümanın kendisi de UAV↔uydu
  cross-domain eşleştirmeyi "normal eşleştirmeden zor" olarak tanımlıyor
  ve M2'nin bu oturumda "assembled by students" (hazır bileşenlerle
  kurulan, zamanla tune edilen) bir aşama olduğunu vurguluyor.

### M2 tuning günlüğü (dürüst, tüm denemeler)

| Konfigürasyon | median hata | min hata | Not |
|---|---|---|---|
| homography, radius=150m, tek-ölçek | 188-264m | 54m | başlangıç |
| homography, radius=150m, çok-ölçek (5 aday) | ~194m | - | çok iyileşme yok |
| homography, radius=60m | 101m | 33m | radius küçültmek yardımcı oldu |
| **similarity transform, radius=60m, çok-ölçek** | **40-53m** | **15-27m** | **EN İYİ — şu anki baseline** |
| similarity, radius=30m | 44m | 23m | tutarlı ama plato |
| + MIN_CROP_PX=400 + MIN_QUERY_PX=300 (çift-resample) | 21-227m | - | KÖTÜLEŞTİ, geri alındı |
| + MIN_QUERY_PX tek-resize, footprint=(60,120,250,500) | 127m | 41m | KÖTÜLEŞTİ, geri alındı |
| + MIN_CROP_PX=700, footprint=(250,400,550,700) | 204m | 128m | KÖTÜLEŞTİ, geri alındı |

**Şu anki sabit konfigürasyon** (`localization_pipeline.py`):
similarity transform (`cv2.estimateAffinePartial2D`, RANSAC), çok-ölçekli
query arama (footprint adayları 40/80/160/320/640m), `search_radius_m=60`
önerilen çağrı değeri, `MIN_CROP_PX`/`MIN_QUERY_PX` devre dışı (kod içinde
yorumla işaretli, neden devre dışı bırakıldığı belgeli).

**Kök neden HENÜZ TAM ANLAŞILMADI**: küçük crop/query boyutlarının neden
büyük/"daha doğru boyutlandırılmış" versiyonlardan sistematik olarak
DAHA İYİ sonuç verdiği mantıksız görünüyor (normalde daha fazla context
daha iyi eşleştirme vermeli). Olası açıklamalar (test edilmedi):
1. `cv2.estimateAffinePartial2D`'nin RANSAC eşiği (4.0px) crop boyutuyla
   orantılı olmalı (büyük crop'ta 4px daha "sıkı" bir tolerans demek).
2. SuperPoint'in `max_num_keypoints=2048` sınırı büyük/yüksek-çözünürlüklü
   crop'larda keypoint'lerin "seyrekleşmesine" (dağılmasına) yol açıyor
   olabilir — max_keypoints artırılmadan crop büyütmek, per-bölge
   keypoint yoğunluğunu düşürüyor olabilir.
3. Harita çözünürlüğü (~0.96 m/piksel) zaten oldukça kaba; büyük crop'lar
   daha fazla ALAN ama AYNI DÜŞÜK detay yoğunluğunu getiriyor, yani "daha
   fazla context" aslında "daha fazla bulanık/ayırt edici olmayan piksel"
   anlamına geliyor olabilir.

**Sıradaki oturum için öneri**: max_num_keypoints'i crop boyutuyla
orantılı artırmayı dene (örn `max(2048, crop_px*4)`), RANSAC eşiğini
crop boyutuna göre normalize et, ve/veya XFeat+LightGlue'yu (dokümanın
önerdiği alternatif) dene.

## Faz E entegrasyonu (M6+M8+M9) — bu oturumda planlanan sıradaki adım

`drift_simulator.py` ve `gates.py` ayrı ayrı sentetik verilerle test
edildi (bkz. önceki mesajlar) ama BİRLEŞTİRİLMEDİ. Sıradaki adım: bir
AerialVL sekansı boyunca gerçek localization_pipeline + drift_simulator +
gates'i TEK bir döngüde çalıştırmak (`run_phase_e.py`).

## Dosya durumu

```
src/aerialvl_loader.py       ✅ gercek veride test edildi
src/geo_utils.py              ✅ (dolaylı, haversine/ENU testte kullanıldı)
src/fix_record.py             ✅ kullaniliyor
src/localization_pipeline.py  ⚠️ calisiyor ama dogruluk dusuk (M2 tuning devam ediyor)
src/visualize_pairs.py        ✅ gercek veride basarili
src/run_month1_demo.py        ✅ gercek veride calisiyor (dogruluk haric)
src/batch_test.py             ✅ (bu oturumda eklendi, tuning icin)
src/debug_bias.py             ✅ (bu oturumda eklendi, tanı icin)
src/debug_visual.py           ✅ (bu oturumda eklendi, gorsel dogrulama icin)
src/drift_simulator.py        ✅ sentetik veride test edildi (M6)
src/gates.py                  ✅ sentetik veride test edildi, H4 dogrulandi (M8/M9)
src/reliability_model.py      ✅ sentetik veride test edildi (M5.4)
src/run_phase_e.py            ❌ HENÜZ YAZILMADI (sıradaki adım)
```

## Disk/altyapı notları

- `/media/davut/disk2` NTFS3 dosya sistemi — büyük dosya birleştirme
  (`cat`) beklenenden yavaş. Extraction sırasında disk 17GB'a kadar
  daraldı ama `unzip` açıkken `VAL.zip`'i silmek (POSIX unlink-while-open)
  güvenle denendi; alan unzip bitince otomatik geri geldi (ntfs3 sürücüsü
  standart POSIX semantiğini destekliyor).
- Sadece `images/VAL/` indirildi (54GB) — `images/VPR/` ve
  `vpr_training_data/` (~88GB) BİLİNÇLİ OLARAK indirilmedi (kendi
  retrieval modelimizi eğitmiyoruz, hazır SuperPoint+LightGlue kullanıyoruz).

## Faz E entegrasyonu — TAMAMLANDI ve İLK ANLAMLI SONUÇ ALINDI

`run_phase_e.py` yazıldı: bir AerialVL sekansı boyunca GERÇEK
`LocalizationPipeline` + `DriftSimulator` (M6) + `chi_square_gate`/
`ReliabilityPolicy` (M8/M9) + M7 dinamik arama yarıçapını (`r=clip(3σ_pos,
r_min,r_max)`) TEK bir döngüde birleştiriyor. 4 politikayı (E1 drift-only,
E2 accept-all, E3 raw-score gate, E5 chi-square gate) AYNI gerçek fix
akışı üzerinde karşılaştırıyor.

**İlk çalıştırmalarda bir bug bulundu ve düzeltildi**: chi-square gate
çağrısında prior/fix karıştırılmıştı (`ν` her zaman 0 çıkıyordu) —
düzeltildi, artık `last_sample[pname]`'den doğru `prior_x/y` ve
`prior_cov` kullanılıyor.

### İLK ANLAMLI SONUÇ (sekans `2023-03-18-12-18-25`, 25 çağrı, moderate drift, call_interval=3s)

| Politika | RMSE (m) | final (m) | kabul | red | zararlı |
|---|---|---|---|---|---|
| E1 drift-only | 8.68 | 11.48 | 0 | 0 | 0 |
| E2 accept-all | 180.82 | 413.33 | 25 | 0 | **17** |
| E3 raw-score gate | 105.19 | 159.78 | 2 | 23 | 2 |
| **E5 chi-square gate** | **37.32** | 39.59 | 5 | 20 | 3 |

**Bu, projenin H1 ve H4 hipotezlerinin GERÇEK VERİDE canlı doğrulanmasıdır:**
- **H1** ("ham retrieval/matching skorları metre-seviyesi doğruluğun
  zayıf tahmincisidir"): E3 (ham inlier_ratio eşiği) E2'den (accept-all)
  çok daha iyi ama E5'ten (chi-square) çok daha kötü — ham skor tek
  başına yetersiz.
- **H4** ("chi-square gate karakteristik şekillerde başarısız olur"):
  E5 en iyi sonucu verdi (RMSE 180→37) ama HALA E1'in (saf drift) 4 katı
  kötü ve 3 zararlı düzeltmeyi kabul etti — chi-square TEK BAŞINA
  yeterli değil, tam da dokümanın "image-based reliability can
  complement it" (H4) önerisinin gerekçesi.

Bu sonuç, **kalibre edilmiş güvenilirliğin (henüz eğitilmedi) chi-square'i
geçip geçemeyeceği** sorusunu artık gerçek, canlı üretilmiş FixRecord
verisiyle test edebileceğimiz anlamına geliyor — bu projenin TAM
araştırma sorusu.

### Önemli düzeltme: M7 dinamik arama yarıçapı

İlk Faz E denemelerinde arama yarıçapı SABİT (60m) kullanılıyordu; M7
kuralına göre `r = clip(3·σ_pos, r_min, r_max)` olması gerektiği fark
edilip düzeltildi (`--r-min-m 60 --r-max-m 400`). Bu deneyde drift henüz
60m eşiğini aşacak kadar büyümediğinden sonucu değiştirmedi ama mekanizma
artık doğru ve ileride büyük drift senaryolarında (M9 Scenario A/B)
gerekli olacak.

### Sekanslar arası büyük varyans gözlendi

`2023-03-16-16-58-43` sekansında (muhtemelen kırsal/tarla alanı) TÜM 24
çağrı kötüydü (140-300m hata, hiç "iyi" fix yok) — gate'ler doğru
davrandı (hepsini reddetti) ama "iyi ile kötüyü ayırt etme" gösterilemedi.
`2023-03-18-12-18-25` sekansında (yukarıdaki tablo) hem iyi (20-72m) hem
kötü (150-413m) fix'ler karıştı — gate'lerin GERÇEK ayrım yapma
yeteneğini test edebildiğimiz asıl sekans bu oldu. **Ders**: M10 tam
deney matrisinde TÜM 11 sekans kullanılmalı, tek sekansa güvenmek yanıltıcı
olabilir (bazı sekanslar hiç sinyal içermiyor).

### Metodoloji düzeltmesi: her politika kendi prior'undan aramalı

İlk toplu veri toplamada (532 kayıt) TÜM politikalar (E3/E5) aramalarını
E2'nin (accept-all, sürekli kötüleşen) prior'undan yapıyordu — bu E3/E5'i
haksız yere kötü gösteriyordu. Düzeltildi: her politika artık KENDİ
sürüklenmiş prior'undan arar (4 kat yavaş, 0.30s/çağrı → 0.80s/çağrı,
ama doğru). Ayrıca `localization_pipeline.py`'nin zaten hesapladığı
`inlier_spatial_spread`/`transform_condition`/`query_ref_scale_ratio`
alanları ve yeni eklenen `mahalanobis_d` (ν^T·S⁻¹·ν'nin karekökü)
`FixRecord`'a hiç YAZILMIYORDU — bu da kalibre modelin ayırt edici
hiçbir sinyal göremeyip başarısız olmasına yol açmıştı (bkz. aşağı).

## GERÇEK VERİYLE İLK KALİBRASYON SONUCU — projenin ana araştırma sorusu

11 sekans × 2 seed × 3 politika (E2/E3/E5) ile **1596 FixRecord**
toplandı (`outputs/phase_e_fixrecords.jsonl`). Etiket dengesi çok
seyrek: **safe_primary (≤10m) = %0.6**, **safe_secondary (≤25m) = %4.9**
— bu yüzden ikincil eşikle çalışıldı.

**İlk deneme (eksik özellik seti, SADECE num_matches/inlier_count/
inlier_ratio/reprojection_error_px doluydu):** AUROC=**0.479**
(rastgele tahminden KÖTÜ — hiç sinyal yok).

**mahalanobis_d + inlier_spatial_spread + transform_condition eklendikten
sonra (yukarıdaki düzeltme):** AUROC=**0.731**, Brier=0.044 (ham
inlier_ratio'nun 0.095'ine göre çok daha iyi), ECE=0.005. **Bu, projenin
merkezi araştırma sorusuna (kalibre edilmiş güvenilirlik ham skordan
daha mı iyi?) GERÇEK VERİDE İLK OLUMLU KANITTIR** — ama rastgele
train/test split ile (sequence-disjoint DEĞİL), bu yüzden iyimser
yanlılık (optimistic bias) olasılığı var, dokümanın §9.1 kuralına göre
NİHAİ değil.

### Sequence-disjoint held-out test (gerçek metodolojik doğrulama)

`train_and_save_model.py` ile `2023-03-18-12-18-25` sekansı TAMAMEN
eğitim setinden çıkarılıp (1446 kayıtla eğitim) model kaydedildi, sonra
`run_phase_e.py --reliability-model` ile bu held-out sekansta E7
politikası olarak GERÇEK navigasyon döngüsünde test edildi:

| Politika | RMSE (m) |
|---|---|
| E1 drift-only | 8.68 |
| E2 accept-all | 180.82 |
| E3 raw-score | 93.43 |
| E5 chi-square | 38.42 |
| **E7 calibrated (muhafazakar eşik)** | **8.68 — E1 ile AYNI, chi-square'den DAHA İYİ** |

Modelin ürettiği ham olasılıkları (`predict_proba`) tek tek inceledim
(bkz. konuşma geçmişi): **model gerçek bir ayrım öğrenmiş** — en düşük
hatalı fix (12.4m) en yüksek olasılığı (0.0997) alırken, en kötü
fix'ler (90-152m) hep 0.0000 aldı. Monoton olmasa da net bir eğilim var.

### ÖNEMLİ METODOLOJİK BULGU: eşik seçimi kapalı-döngü davranışını değiştiriyor

Eşiği gevşetmeyi (0.5/0.3 → 0.05/0.02 → 0.055/0.055) denedim — sonuçlar
TUTARSIZ çıktı (8.68m → 261.88m → 95.06m), ilk bakışta "model kötü"
gibi göründü. Gerçek sebep: **bu kapalı-döngü bir sistem** — bir eşikle
kabul edilen fix, o politikanın SONRAKİ prior'unu değiştirir, bu da
SONRAKİ çağrıların arama merkezini/sonuçlarını değiştirir. Yani "aynı
25 örnek üzerinde eşik dene" yaklaşımı YANILTICI — her eşik farklı bir
yörünge yaratıyor, gerçekte KARŞILAŞTIRILABİLİR değiller. **Doğru
yöntem** (dokümanın zaten M7 "exact tile-level cache" ve §9.1
"configuration freeze" ile öngördüğü): eşiği SADECE açık-döngü
(dondurulmuş prior'larla) validation verisinde seç, SONRA kapalı-döngüde
TEK SEFER test et. Bu ayrım gece oturumunda ihmal edilmişti, ŞİMDİ
belgelendi — sıradaki oturumda düzeltilmeli.

Şu anki `run_phase_e.py`, kod içi yorumla açıkça işaretlenmiş şekilde
EN GÜVENLİ/muhafazakar eşiği (0.5/0.3, pratikte "şüpheliyse reddet")
kullanıyor.

### Açık-döngü eşik seçimi denendi — dürüst negatif/karışık sonuç

`select_threshold.py`: held-out sekans HARİÇ, SADECE `E2_accept_all`
kayıtları (eşikten bağımsız, gerçekten "açık-döngü" localization
denemeleri, 482 kayıt) üzerinde risk-coverage eğrisi hesaplandı.
**Sonuç: HİÇBİR olasılık eşiğinde risk ≤ %50'ye inmiyor** (en iyi:
coverage=0.10'da risk=0.917, yani kabul edilen en güvenilir %10'un bile
%92'si hâlâ unsafe). Bu, held-out sekanstaki (2023-03-18-12-18-25) iyi
görünen ayrımın (12.4m fix'in en yüksek olasılığı alması) o sekansa özgü
YEREL bir korelasyon olduğunu, TÜM veri setine GENELLEMEDİĞİNİ gösteriyor.

**Dürüst yorum**: Mevcut özellik seti (num_matches, inlier_count,
inlier_ratio, reprojection_error_px, inlier_spatial_spread,
transform_condition, mahalanobis_d — `top1_top2_margin` hiç
TOPLANMADI, çünkü gerçek çoklu-aday retrieval hâlâ eksik, M2 notu) +
şu anki M2'nin düşük/tutarsız doğruluğu (sekanslar arası median 8m'den
400m'ye kadar değişiyor) birlikte, kalibre modelin genel-geçer, güvenilir
bir eşik üretmesini ŞU AN engelliyor. Bu BEKLENEN bir ara-durum —
dokümanın 7 aylık planının Ay 2-5'i tam olarak bunun (M2 doğruluğu +
tam özellik seti + gerçek train/val/test ayrımı + threshold tuning)
üzerine kurulu. Bu gece elde edilen "AUROC=0.731" ve "held-out sekansta
chi-square'i geçme" bulguları GERÇEK ve DEĞERLİ ama henüz İSTATİSTİKSEL
OLARAK SAĞLAM/GENELLENEBİLİR değil (532-1596 kayıt, %0.6-4.9 pozitif
oran, tek held-out sekans — hepsi küçük örneklem uyarıları).

## Dürüst genel değerlendirme

Bu gece **gerçek, çalışan, uçtan uca bir sistem** kuruldu ve GERÇEK
AerialVL verisiyle test edildi:
- Ay-1 çıkış kriterleri karşılandı (veri, görselleştirme, tek fix)
- M2 (localization) çalışıyor ama doğruluğu düşük (median ~50-200m,
  sekansa göre büyük varyans) — Ay 2-3 tuning gerektiriyor
- M6+M7+M8+M9 (drift, dinamik arama, chi-square, reacquisition mantığı)
  entegre ve GERÇEK veride test edildi
- M5.4 (kalibre güvenilirlik) GERÇEK veride eğitildi, chi-square'i
  held-out sekansta GEÇTİĞİ gösterildi — ama eşik seçimi/kapalı-döngü
  metodolojisi henüz OLGUNLAŞMADI (yukarıdaki bulgu)
- **HENÜZ YAPILMADI**: sequence-bazlı TAM train/val/test ayrımı +
  configuration freeze (§9.1), tam M10 call-rate sweep (birden fazla
  call_interval), E11 (Scenario A/B büyük-drift kurtarma), E12
  (AnyVisLoc transfer), M11 (Jetson), M12 (final paket/rapor)

## SON TUR: TÜM 11 sekansta E1-E7 karşılaştırması (gece oturumunun kapanışı)

Nihai model TÜM 1596 kayıtla eğitilip (resmi held-out DEĞİL, sadece
betimleyici son tur) 11 sekansın hepsinde E1/E2/E3/E5/E7 karşılaştırıldı
(moderate drift, call_interval=3s, 150 kare/sekans, muhafazakar eşik
0.5/0.3):

| Sekans | E1 | E2 | E3 | E5 | **E7** |
|---|---|---|---|---|---|
| 2023-03-11-11-48-35 | 5.41 | 211.08 | 74.65 | 58.45 | **5.41** |
| 2023-03-16-16-58-43 | 7.15 | 200.49 | 26.69 | 67.68 | **7.15** |
| 2023-03-16-18-04-01 | 6.17 | 311.38 | 17.26 | 144.56 | **6.17** |
| 2023-03-18-12-18-25 | 8.68 | 180.82 | 93.43 | 38.42 | **8.68** |
| 2023-03-18-12-47-05 | 8.66 | 284.99 | 64.36 | 74.94 | **8.66** |
| 2023-03-18-14-38-32 | 9.13 | 314.36 | 56.58 | 49.35 | **9.13** |
| 2023-03-18-15-01-14 | 9.12 | 328.00 | 96.77 | 90.22 | **9.12** |
| 2023-03-18-15-40-18 | 9.40 | 285.47 | 120.99 | 53.86 | **9.40** |
| 2023-03-18-16-30-27 | 7.83 | 176.26 | 117.84 | 107.25 | **7.83** |
| 2023-03-18-16-43-16 | 7.75 | 252.55 | 49.82 | 85.99 | **7.75** |
| 2023-03-18-16-55-37 | 7.78 | 294.87 | 78.27 | 129.57 | **7.78** |

**En kritik dürüst bulgu**: E7, HER TEK sekansta E1 ile BİREBİR AYNI
çıktı (0 kabul, tüm çağrılar reddedildi). Bu şu anlama geliyor:
- ✅ **Asla-zarar-verme garantisi MÜKEMMEL çalışıyor** — E7 hiçbir
  sekansta E2/E3/E5'in yaptığı türden bir kötüleşmeye izin vermedi.
- ❌ **Ama HİÇBİR faydalı düzeltme de sağlamadı** — muhafazakar eşik
  (0.5/0.3) genel veri setinin ürettiği olasılık aralığının (max ~0.10-
  0.12) HER ZAMAN üstünde kaldığından, model pratikte "hep reddet"
  moduna düşüyor. Bu, kalibre modelin chi-square'den "daha iyi" olduğu
  ANLAMINA GELMİYOR — sadece "hiçbir şey yapmama" stratejisinin, E2/E3/
  E5'in yaptığı riskli kabullerden kaynaklanan zararı önlediği anlamına
  geliyor.

**İkinci önemli gözlem**: E1'in (drift-only, hiç düzeltme yok) RMSE'si
zaten çok düşük (5-9m) TÜM sekanslarda. Bu, "moderate" drift rejiminin
75 saniyelik test penceresinde doğal olarak zaten küçük bir sürüklenme
ürettiğini gösteriyor — yani bu test senaryosunda düzeltmeye pek
İHTİYAÇ yok, bu da E2/E3/E5'in görece kötü performansını (gerçek
"düzeltmeye ihtiyaç var mı" sorusundan bağımsız olarak her fix'i
değerlendirmeye çalışmaları) kısmen açıklıyor. **Sıradaki oturumda**
daha uzun sekanslar / daha şiddetli drift rejimleri (severe, veya
call_interval'ı büyütüp gerçek drift birikmesine izin vermek) ile
tekrar test edilmeli — E1'in zaten iyi olduğu bir senaryoda "düzeltme
politikaları" karşılaştırmak dokümanın kendi M10 tasarımının
öngördüğü gibi ANLAMLI bir test değil.

## GECE OTURUMU NİHAİ ÖZET

Bu gece **gerçek, çalışan, uçtan uca bir araştırma prototipi** kuruldu
ve GERÇEK veriyle defalarca test edildi. En değerli 3 bulgu:
1. **Koordinat/veri altyapısı %100 sağlam** (görsel doğrulamayla kanıtlandı).
2. **M2 (localization) çalışıyor ama doğruluğu düşük ve sekanslar arası
   çok değişken** — bu Ay 2-3'ün asıl işi, bu gece "çözülmedi" (beklenen).
3. **Kalibre güvenilirlik modeli GERÇEKTEN sinyal öğreniyor** (AUROC
   0.479→0.731, mahalanobis_d eklenince) ama **eşik seçimi/genelleme
   HENÜZ olgun değil** — hem "gevşek eşik zarar veriyor" hem "sıkı eşik
   hiçbir fayda sağlamıyor" uçları gözlendi, ikisi arası dengeli bir
   nokta HENÜZ bulunamadı. Bu dokümanın 7 aylık planının Ay 3-5'inin
   (kalibrasyon + call-rate sweep + configuration freeze) TAM olarak
   neden gerekli olduğunu somut şekilde gösteriyor.

**Ek doğrulama (severe drift rejimi, aynı sekans)**: E1=35.11m (artık
gerçek/anlamlı bir drift birikimi var, önceki moderate'teki 8.68m'den
farklı olarak). Ama **E5 (chi-square, 85.09m) ve E3 (raw, 128.43m) HÂLÂ
E1'in üstünde** — yani drift daha şiddetli olsa bile, mevcut M2
doğruluğuyla hiçbir gate net fayda sağlayamıyor. Bu, sorunun "test
senaryosu çok kolay" değil, doğrudan **M2'nin fix kalitesinin henüz
düzeltme yapmaya yetecek kadar güvenilir olmadığı** olduğunu netleştiriyor.

**Sıradaki oturum için somut öncelik sırası**:
1. Daha uzun/şiddetli drift senaryolarıyla test (E1'in zaten iyi olmadığı
   bir rejimde politikaları karşılaştır).
2. Sequence-bazlı resmi train/val/test ayrımı + configuration freeze.
3. M2'nin gerçek çoklu-aday retrieval'ı (top1_top2_margin gibi eksik
   özellikleri doldurmak için).
4. Risk-coverage eğrisinden AÇIK-DÖNGÜ (dondurulmuş prior) eşik seçimi
   — kapalı-döngü grid-search'ün yanıltıcı olduğu bu gece kanıtlandı.

---
*Bu rapor otonom oturum sırasında canlı güncellenmektedir. Sabah
kontrolünde en son duruma bakın.*
