# UAV-VisLoc için tarihi uyan harita — araştırma bulguları (2026-10-03)

Görev: `UAV_VISLOC_HARITA_ARASTIRMA.md`.

**Kısa sonuç:** En iyi kaynak **Google Earth "geçmiş görüntüler" (Time Machine)**. Her uçuş bölgesi için uçuş tarihine haftalar ile birkaç ay arasında yakın, 0.3–0.5 m sınıfı çekimler var. Bunu **gerçekten sorgulayarak doğruladım**: açık kaynaklı `GEHistoricalImagery` aracıyla tarih listesi, uçuş rotası kapsama oranı ve örnek indirme. Tek ciddi engel **lisans**: resmi API yok, erişim tersine mühendislikle yapılan bir protokol üzerinden.

## 1. Veri setinin kendi haritaları (bağlam)

UAV-VisLoc makalesi (arXiv 2405.11936, Tablo II) haritaların **Google Earth'ten, 0.3 m** çözünürlükte alındığını ve şu tarihleri veriyor:

| Harita / bölge | Drone | Harita (makaleye göre) |
|---|---|---|
| Changjiang-20 (uçuş 01) | 2018-09 | 2023-11 |
| Changjiang-23 (02) | 2018-09 | 2022-09 |
| Taizhou-1 (03) | 2018-10 | 2021-04 |
| Taizhou-6 (04) | 2018-10 | 2023-03 |
| Yunnan (05) | 2016-06 | 2022-03 |
| Zhuxi (06) | 2022-10 | 2022-09 |
| Huzhou-3 (08) | 2019-06 | 2023-07 |
| Huzhou-6 (09) | 2019-06 | 2024-01 |
| Huailai (10) | 2018-09 | 2023-06 |
| Shandan (11) | 2023-10 | 2021-03 |

Yani haritalar uçuştan 1–5 yıl sonra çekilmiş; Shandan'da 2.5 yıl önce. Aynı kaynağın (Google Earth) eski sürümleri arşivde duruyor.

**Doğrulanmış gözlem (çelişki):** Uçuş 04'te test ettiğim noktada, veri setinin haritası Google Earth'ün **2018-11-14 Maxar** çekimiyle görsel olarak birebir aynı (aynı gölgeler, aynı ağaçlar). Makaledeki "2023-03" tarihi en azından haritanın tamamı için geçerli değil olabilir; Google Earth mozaikleri karışık tarihli. Uçuş 04'te bazı bölgelerde harita zaten uçuş tarihine yakın olabilir. Bu yalnızca tek bir 450 m'lik noktada kontrol edildi.

## 2. Kaynak: Google Earth geçmiş görüntüler — DOĞRULANDI

- **Erişim:** Resmi API yok. `khmdb.google.com` (db=tm) üzerinden şifreli quadtree protokolü; topluluk tersine mühendislikle çözmüş.
- **Araç:** `GEHistoricalImagery` v0.7.1 (GPL-3.0), Linux x64 ikili dosyası hazır, kurulum gerektirmiyor.
  - Projede denendi: `scratchpad/gehi/` (geçici; projeye kopyalanmadı).
  - Komutlar: `info` (bir noktadaki tarihler), `availability` (bölgedeki tarihler, GeoJSON çıktı), `download` (tarih seçerek GeoTIFF).
  - Kaynak: https://github.com/Mbucari/GEHistoricalImagery
- **Koordinat sistemi:** Çıktı EPSG:4326 GeoTIFF (+ .tfw); karolar plate-carrée. Bizim `GeoMap`/`MapExtractor` ile doğrudan uyumlu. Google Earth WGS84 kullanıyor, **GCJ-02 kayması yok**. Örnek indirmede veri seti haritasıyla aynı noktaya oturdu.
- **Çözünürlük:** Zoom 19 ≈ 0.25–0.3 m/px. Örnek indirmeler 0.25 m/px çıktı. Kaynaklar Maxar (0.3–0.5 m) ve CNES/Airbus (Pléiades 0.5 m; bazıları SPOT 1.5 m olabilir, yakından bakılmalı).
- **Hız:** 450 m × 450 m'lik bir alan (1864×1491 px) birkaç saniyede iniyor. Kullanıcının bağlantısıyla bir uçuşun tamamı dakikalar içinde iner.
- **Lisans ve risk:** Google Earth hizmet koşulları otomatik/toplu indirmeyi ve çevrimdışı kullanımı yasaklıyor. Bu yöntem desteklenmeyen ve her an değişebilecek bir uç nokta kullanıyor. Akademik yayınlarda Google Earth görüntüsü atıfla gösterilebiliyor ve UAV-VisLoc'un kendisi de Google Earth görüntüsü kullanıyor. Ama toplu indirme hukuken gri alan. **Kullanıcı bu riski kabul edip etmeyeceğine karar vermeli.** Makalede "Google Earth historical imagery, © Maxar / CNES-Airbus" atfı gerekir.

### 2.1 Her uçuş için bulunan çekimler (doğrulandı)

Zoom 19'da, uçuş tarihinin ±2 yıl çevresi tarandı. "Kapsama" = uçuş karelerinin konumlarından o tarihli görüntünün düştüğü oran (`availability` GeoJSON'u ile hesaplandı). Bir tarih %100'ün altında kalırsa, eksik kısım başka bir tarihle tamamlanabilir (aracın "closest date" eşleştirmesi bunu otomatik yapıyor).

| Uçuş | Uçuş tarihi | En iyi adaylar (tarih, kapsama, uçuşa göre gün) | Değerlendirme |
|---|---|---|---|
| **02 TEST** | 2018-09-18 | 2018-10-29 %56 (+41); 2019-09-21 %100 (+368, aynı mevsim); 2019-10-04 %100 (+381); 2017-11-01 %100 (−321) | Çok iyi: +41 günlük çekim + 1 yıl sonraki aynı mevsim. Rotanın bir kısmı nehir üstünde (bilgi yok). |
| **04 TEST** | 2018-10-24 | 2018-11-14 %81 (+21); 2019-01-01 %92 (+69); 2018-01-01 %100 (−296) | Çok iyi. Veri seti haritasının bir kısmı zaten 2018-11-14 olabilir (bkz. §1). |
| **08 TEST** | 2019-06-14 | 2019-08-26 %67 (+73); 2018-07-15 %100 (−334, yaz); 2019-10-10 %44 (+118); 2018-04-28 %100 | İyi. **Görsel doğrulama:** 2018-07 ve 2019-08 çekimleri yeşil (drone gibi); veri seti haritası kahverengi, sürülmüş tarla. |
| **11 TEST** | 2023-10-19 | ±2 yılda yalnız 2025-03-24 %100 (+522). Daha eski: 2021-03-04 (Airbus; veri seti haritası muhtemelen bu) | **Düzelme beklenmiyor.** Esri Wayback'teki 2022-04 ve 2024-11 çekimleri daha yakın (bkz. önceki dosya). |
| 01 RECAL | 2018-09-17 | 2018-10-04 %100 (+17); 2018-10-29 %100 (+42); 2019-09-21 %100 | Çok iyi tarih; ama uçuş büyük ölçüde nehir üstünde. |
| 03 RECAL | 2018-10-23 | 2018-11-14 %84 (+22); 2017-12-20 %100 (−307); 2019-05-11 %56 | Çok iyi. |
| 06 RECAL | 2022-10-09 | 2022-09-26 %100 (−13); 2022-08-13 %100 (−57) | Çok iyi; veri seti haritası zaten 2022-09 (makale). |
| 09 RECAL | 2019-06-15 | 2019-08-30 %61 (+76); 2019-10-10 %64 (+117); 2020-09-08 %100; 2018-04-18 %100 | İyi. |
| 05 TUNE | 2016-06-27 | 2016-11-21 %100 (+147); 2015-01-13 %100 | Orta (aynı mevsim yok). |
| 10 TUNE | 2018-09-05 | 2019-08-24 %75 (+353, aynı mevsim); 2019-10-02 %100; 2018-04-18 %100 (−140) | İyi. Mevsim farkı en belirgin uçuş buydu. |

**İndirme örneği (doğrulandı):**
```bash
./GEHistoricalImagery download -q -z 19 \
  --lower-left=32.200,119.928 --upper-right=32.204,119.933 \
  -d 2018/11/14 --exact-date -o t04_20181114.tif
# birden çok tarih + eksikte en yakın tarih: -d 2018/11/14 -d 2019/01/01 --date-match=Closest
# tüm rota icin: --region-file=rota_koridoru.kml (poligon)
```
Çıktı EPSG:4326 GeoTIFF; `GeoMap(path, lt_lon=sol, lt_lat=üst, rb_lon=sağ, rb_lat=alt)` ile doğrudan kullanılabilir (`wayback_compare.py` kalıbı).

## 3. Diğer kaynaklar (doğrulanmadı / uygun değil)

| Kaynak | Durum | Neden ikincil |
|---|---|---|
| **Esri Wayback** | Daha önce denendi | 2018–2019 için çekim yok (en eski 2020–2021). Yalnız uçuş 11 için Google'dan daha yakın tarih var (2022-04-06, 2024-11-13). GEHistoricalImagery `--provider=Wayback` ile de indirilebilir. |
| **Maxar Discovery API** (STAC, `api.maxar.com/discovery/v1`) | Doğrulanmadı (hesap/API anahtarı gerekir) | Arşiv araması teknik olarak mümkün ama görüntü satın alma gerekir. Google'daki Maxar çekimlerinin aslı burada; maliyet yüksek. https://developers.maxar.com/docs/discovery/ |
| **ESA Third Party Missions / Copernicus Contributing Missions** (Pléiades, SPOT) | Doğrulanmadı | Proje önerisi + 4–6 hafta değerlendirme. Uygunluk: **ESA üye devletleri, Kanada, AB üyeleri**; Türkiye'den başvuru büyük olasılıkla uygun değil (bir AB/ESA ortağıyla mümkün olabilir). https://earth.esa.int/eogateway/catalog/pleiades-full-archive-and-tasking |
| **Airbus OneAtlas** | Doğrulanmadı | Ticari abonelik / deneme. Pléiades 0.5 m arşivi; Google'daki "CNES/Airbus" tarihlerinin aslı. |
| **Planet** (SkySat 0.5 m, PlanetScope 3 m) | Doğrulanmadı | Eğitim/araştırma programı ağırlıkla PlanetScope (3 m, çok kaba). SkySat arşivi 2018–2019'da bu noktalarda seyrek olabilir. |
| **Tianditu (天地图)** | Doğrulanmadı | API anahtarı Çin kaydı gerektiriyor; yalnızca güncel görüntü, tarihi sürüm sunmuyor (bilinen kadarıyla). |
| **Gaofen-1/2 (CRESDA), Jilin-1, SuperView-1** | Doğrulanmadı | Çin içi kayıt/ticari erişim; yabancı akademik erişim zor ve yavaş. |
| **Baidu / AMap karoları** | Önerilmez | Güncel görüntü; GCJ-02/BD-09 kayması var; tarihi sürüm yok. |
| **Bing Maps** | Önerilmez | Tarihi sürüm yok. |
| **Sentinel-2** | Uygun değil | 10 m, çok kaba. |

## 4. Öncelik sıralı öneri

1. **Google Earth geçmiş görüntüler + GEHistoricalImagery (hemen denenebilir, ücretsiz).**
   - Önce geliştirme uçuşlarında dene, TEST'e dokunmadan: uçuş 03 → 2018-11-14 (+22 gün), uçuş 09 → 2019-08-30 / 2019-10-10, uçuş 10 → 2019-08-24. `wayback_compare.py` ile veri seti haritası ve Wayback'e karşı karşılaştır.
   - Fayda net görülürse kural önceden sabitlenmeli: "uçuş tarihinden önceki en yakın tarih" ya da "aynı mevsimin en yakını". Sonra TEST uçuşları 02 → 2018-10-29 + 2019-09-21, 04 → 2018-11-14 + 2019-01-01, 08 → 2018-07-15 / 2019-08-26.
   - **Dürüstlük notu:** Gerçek kullanımda harita uçuştan önce alınmış olmalı. "Uçuş tarihinden sonraki en yakın" seçimi biraz iyimser bir üst sınır verir. İkisini ayrı raporla: önceki en yakın (gerçekçi) ve aynı mevsim (üst sınır).
2. **Uçuş 11 için Esri Wayback 2022-04-06** (mevcut `wayback_fetch.py` ile zaten iniyor).
3. **Lisans netleşmezse veya yayın için resmi kaynak gerekirse:** Maxar Discovery / Airbus OneAtlas üzerinden aynı tarihli sahnelerin akademik fiyat teklifi (Google'daki tarihler aynen orada). ESA TPM yolu yalnızca bir AB/ESA ortak kurumla mümkün.

**Bulunamayan:** Uçuş 11 için uçuş tarihine (2023-10) ±6 ay içinde Google Earth yüksek çözünürlüklü çekim yok; Wayback'te 2022-04 ve 2024-11 var. Uçuş 01/02'nin nehir üstü kısımları için hiçbir harita yardımcı olmaz.

## 5. Kaynak URL'leri
- UAV-VisLoc makalesi (Tablo II, harita kaynağı ve tarihleri): https://arxiv.org/html/2405.11936v1
- UAV-VisLoc GitHub: https://github.com/IntelliSensing/UAV-VisLoc
- GEHistoricalImagery: https://github.com/Mbucari/GEHistoricalImagery (v0.7.1, GPL-3.0)
- Google Earth Time Machine protokol notları: https://terrain-viewer.iconem.com/docs/dev/ge-historical/ ; Iconem GE_TimeMachine: https://github.com/Iconem/GE_TimeMachine
- Google geçmiş görüntüler (resmi, API yok): https://developers.google.com/maps/documentation/earth/historical-imagery
- Maxar Discovery API: https://developers.maxar.com/docs/discovery/
- ESA Pléiades arşivi (TPM/CCM): https://earth.esa.int/eogateway/catalog/pleiades-full-archive-and-tasking
- ESA SPOT 6-7 arşivi: https://earth.esa.int/eogateway/catalog/spot-6-to-7-full-archive-and-tasking-and-spotmaps-2-5-dataset

## 6. Yerel test dosyaları (geçici, projede değil)
Gecici calisma klasoru (`gehi/`):
- `GEHistoricalImagery` ikili dosyası,
- `av*.json` (uçuş başına tarih/kapsama poligonları), `cov.py` (kapsama hesabı),
- `t04_*.tif`, `t02_*.tif`, `t08_*.tif` (450 m'lik örnekler),
- `cmp04.jpg`, `cmp0208.jpg` (görsel karşılaştırmalar).
