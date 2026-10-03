# Araştırma görevi: UAV-VisLoc uçuşları için tarihi uyan uydu haritası bulmak

## Bağlam (kısa)

GPS'siz İHA lokalizasyonu üzerine çalışıyoruz. Drone kamerasının aşağı bakan görüntüsü bir uydu haritasıyla eşleştiriliyor (SuperPoint + LightGlue + RANSAC) ve drone'un konumu bulunuyor. Bulunan konumun güvenilir olup olmadığına da kalibre bir model karar veriyor.

Bu sistem iki veri setinde iyi çalışıyor:
- AerialVL: karelerin %57'si 10 m içinde.
- AnyVisLoc: karelerin %66'sı 10 m içinde.

**UAV-VisLoc veri setinde ise eşleştirme çöküyor:** test uçuşlarında karelerin sadece %13'ü 10 m içinde bulunuyor.

Ana şüphe şu: veri setiyle gelen uydu haritaları drone uçuşundan **farklı yıl ve mevsimde** çekilmiş. Örneğin bir uçuşta drone yemyeşil tarla görürken haritada kuru, bej toprak var. Ayrıca bazı bölgelerde arada yeni binalar yapılmış ya da yıkılmış.

Elimizdeki eşleştiriciler (SuperPoint, ALIKED, LoFTR, DISK) bu görünüm farkını aşamadı. **Uçuş tarihine (ve mevsimine) yakın çekilmiş, yüksek çözünürlüklü bir uydu görüntüsü bulabilirsek** sorunun büyük kısmı çözülebilir.

## Senden istenen

Aşağıdaki her uçuş bölgesi için **uçuş tarihine olabildiğince yakın** (ideal: aynı yıl ve aynı mevsim) bir uydu ya da hava görüntüsü kaynağı bul.

**Görüntü gereksinimleri:**
- **Çözünürlük:** ≤ 0.5 m/piksel ideal, ≤ 1 m kabul edilebilir. Sentinel-2 (10 m) **çok kaba**, işe yaramaz.
- **Tarih:** Uçuş tarihine yakın. Aynı mevsim farklı yıldan daha önemli olabilir. Mümkünse uçuş tarihinden **önce** çekilmiş olsun: gerçek kullanımda drone, uçuştan önce mevcut olan haritayı kullanır.
- **Coğrafi doğruluk:** Konum hatası ≤ 5 m. Görüntü coğrafi referanslı olmalı (GeoTIFF ya da köşe koordinatları bilinen karolar).
- **Erişim:** Ücretsiz ya da akademik/deneme lisansıyla, araştırmada kullanılabilir. Mümkünse programla indirilebilir (API, WMTS/XYZ karo servisi ya da toplu indirme).
- Lisans koşullarını (araştırmada kullanım, yayında gösterim) mutlaka belirt.

## Uçuşlar

Bütün uçuşlar Çin'de. Yükseklik deniz seviyesinden (m); yer kapsamı her karede yaklaşık 300–600 m. Tarihler drone uçuşunun ilk karesinden alındı.

| Uçuş | Grup | Uçuş tarihi | Kare | Boylam aralığı | Enlem aralığı | Yükseklik (m) | Bölge |
|---|---|---|---|---|---|---|---|
| 01 | RECAL | 2018-09-17 | 817 | 115.9747–115.9934 | 29.7054–29.7723 | 403–409 | Changjiang (Jiujiang civarı, Yangtze kıyısı) |
| 02 | **TEST** | 2018-09-18 | 1071 | 116.0406–116.0593 | 29.7285–29.8154 | 402–408 | Changjiang |
| 03 | RECAL | 2018-10-23 | 768 | 119.8098–119.8969 | 32.2928–32.3541 | 465–468 | Taizhou (Jiangsu) |
| 04 | **TEST** | 2018-10-24 | 738 | 119.9105–119.9493 | 32.1556–32.2513 | 539–547 | Taizhou |
| 05 | TUNE | 2016-06-27 | 473 | 102.3413–102.3644 | 24.6511–24.6660 | 2307–2319 | Yunnan |
| 06 | RECAL | 2022-10-09 | 344 | 109.6370–109.6614 | 32.3392–32.3726 | 499–842 | Zhuxi (Hubei) |
| 08 | **TEST** | 2019-06-14 | 1033 | 120.1402–120.2508 | 30.9065–30.9453 | 545–553 | Huzhou (Zhejiang) |
| 09 | RECAL | 2019-06-15 | 766 | 120.0348–120.1460 | 30.9150–30.9975 | 546–547 | Huzhou |
| 10 | TUNE | 2018-09-05 | 144 | 115.7770–115.7930 | 40.3421–40.3542 | 772–774 | Huailai (Hebei) |
| 11 | **TEST** | 2023-10-19 | 590 | 101.0173–101.0893 | 38.8093–38.8506 | 1971–2575 | Shandan (Gansu) |

Arama alanı olarak uçuş kutusunun her yanına ~1 km pay eklenmesi yeterli. **Öncelik TEST uçuşlarında (02, 04, 08, 11)**, sonra RECAL uçuşlarında (01, 03, 06, 09).

## Şimdiye kadar denenenler

### 1. Veri setinin kendi haritaları
`satellite01.tif` … `satellite11.tif`, yaklaşık 0.25 m/px. Kaynakları ve çekim tarihleri veri setinde belirtilmemiş. Görsel olarak bazı uçuşlarda mevsim farkı açık.

### 2. Esri World Imagery Wayback
Kaynak: livingatlas.arcgis.com/wayback. Arşivde 196 sürüm var ve sorgu ile programla karo indirdik. Her uçuş noktasında bulunan farklı çekim tarihleri:

| Uçuş | Uçuş tarihi | Wayback'teki çekimler (kaynak, çözünürlük) |
|---|---|---|
| 01 | 2018-09 | 2021-07-22 (Maxar 0.5 m), 2025-07-24 (Vantor 0.34 m) |
| 02 | 2018-09 | 2021-07-22 (Maxar 0.5 m) |
| 03 | 2018-10 | 2020-06-04, 2023-01-16 (Maxar 0.31 m), 2025-05-01 (Vantor 0.34 m) |
| 04 | 2018-10 | 2020-06-04 (Maxar 0.31 m), 2025-04-25 (Vantor 0.34 m) |
| 06 | 2022-10 | 2013-11-24 (Maxar 0.6 m), 2024-08-19 (Vantor 0.31 m) |
| 08 | 2019-06 | 2021-05-29, 2023-01-27 (Maxar ~0.5 m), 2025-01-30 (Vantor 0.34 m) |
| 09 | 2019-06 | 2021-05-29, 2023-01-27 (Maxar ~0.5 m), 2025-01-19, 2025-07-13 (Vantor 0.34 m) |
| 11 | 2023-10 | 2022-04-06 (Maxar 0.46 m), 2024-11-13 (Vantor 0.31 m) |

**Sorun:** 2018–2019 uçuşları için o yıllara ait çekim yok; en yakını 2020–2021.

Deneme sonuçları (geliştirme uçuşları, 30 kare, prior 30 m hatalı; oranlar 10 m içinde bulunan kare yüzdesi):
- **Uçuş 03:** Veri seti haritası %40 → Wayback 2020-06 haritası **%73**. Eşleşen nokta sayısı 64'ten 146'ya çıktı. Wayback 2025 haritası ise kötü (%47, karelerin %30'unda eşleşme yok). **Harita tarihi açıkça fark yaratıyor.**
- **Uçuş 01:** Hiçbir haritayla düzelmedi (%3–10). Kareler büyük ölçüde nehir (Yangtze) üstünde, şehir kısmı da yeniden yapılmış. Bu uçuş harita değişikliğiyle muhtemelen kurtarılamaz.
- 09 ve 06 karşılaştırmaları henüz bitmedi.

## Araştırılabilecek kaynak fikirleri

Kontrol edilmedi; sadece başlangıç noktası:

- **Google Earth Pro "geçmiş görüntüler"** (historical imagery). Çin için çok sayıda tarih olabilir. Ancak programla indirme lisans açısından sorunlu; resmi bir yol var mı?
- **Çin kaynakları:**
  - Tianditu (天地图; resmi Çin ulusal haritası, WMTS, API anahtarı gerekir; tarihi sürüm var mı?)
  - Gaofen-1/2 (GF-1/GF-2, 0.8–2 m; CRESDA / China Centre for Resources Satellite Data and Application, akademik erişim)
  - Jilin-1 (Chang Guang Satellite, 0.5–0.75 m, ticari ama akademik program olabilir)
  - Baidu ve AMap (Gaode) karoları (GCJ-02 / BD-09 koordinat kayması var; dönüşüm gerekir)
- **Ticari arşivler (akademik/deneme erişimi):** Maxar (SecureWatch / Maxar Discovery), Planet (PlanetScope 3 m çok kaba olabilir, SkySat 0.5 m), Airbus (Pléiades 0.5 m, SPOT 1.5 m; OneAtlas deneme), SuperView-1 (0.5 m).
- **ESA Third Party Missions / Copernicus Contributing Missions:** Pléiades, SPOT ve benzeri görüntülere araştırma önerisiyle ücretsiz erişim imkânı.
- **USGS EarthExplorer:** Çin için yüksek çözünürlüklü kayıt az ama kontrol edilebilir.
- **Bing Maps:** Görüntü tarihi metadata ile alınabiliyor mu, tarihi sürüm var mı?
- **Benzer çalışmalar:** UAV-VisLoc'u kullanan diğer makalelerde (GitHub: IntelliSensing/UAV-VisLoc) harita kaynağı ya da tarih bilgisi verilmiş mi? Veri seti yazarlarının haritaları nereden aldığı biliniyor mu?

## Beklenen çıktı

Her uçuş için:
1. Bulunan kaynak(lar): ad, URL, erişim yöntemi (API/karo/indirme), lisans özeti.
2. Mevcut çekim tarihleri ve çözünürlük; uçuş tarihine en yakın olanı.
3. Programla indirmek için gereken adımlar: endpoint, kimlik doğrulama, karo şeması/koordinat sistemi ve varsa koordinat kayması (GCJ-02 vb.).
4. Tahmini maliyet ya da erişim süresi (başvuru gerekiyorsa).

Bulunamayan uçuşlar için neden bulunamadığını da yaz.

## Bizim tarafta entegrasyon

Uygun görüntü bulunursa entegrasyon basit. `src/wayback_fetch.py`, verilen bir uçuş bölgesi için XYZ/WMTS karolarını indirip EPSG:4326 GeoTIFF'e çeviriyor; `src/wayback_compare.py` ise aynı karelerde haritaları karşılaştırıyor. Başka bir karo kaynağı için çoğunlukla URL şablonunu değiştirmek yeterli.

Proje: `/media/davut/disk2/proje/uav_reliability_localization` (ayrıntılar `FINAL_RAPOR.md` §11–12).
