# Reprodüksiyon Çalışması — Özet Rapor

BBM479 · Edge-AI UAV Görsel Lokalizasyon Projesi · 28 Ekim 2026

## Amaç

Proje önerisindeki öncelikli okuma listesinde 16 kalem var. Bunlardan yeniden
çalıştırılabilenleri tekrar ettik. Amaç iki şeydi:

1. Makalelerin sonuçlarını doğrulamak.
2. Projenin ele aldığı problemin gerçekten var olduğunu göstermek. Problem, yanlış bir
   konum düzeltmesinin (fix) kabul edilmesi ve izin kaybolması.

Ayrıntılı rapor, kod ve ham sonuçlar proje deposunda: `REPRODUKSIYON_RAPORU.md` ve
`reproducibility/`.

## Sonuçlar

| Makale | Yapılan | Sonuç |
|---|---|---|
| AerialVL (He vd., RA-L 2024), Table III | Reprodüksiyon: aynı veri ve ağırlıklar | **Tekrarlandı.** 36 değerin 31'i ±2,5 puan içinde |
| AerialVL, Table VII | Protokol, bizim lokalizatörümüzle (görsel odometri yok) | Birebir değil. ST.5 ve LT.5'te makalenin üstünde, LT.6'da iz kayboldu |
| Zhang vd. (UST 2026) | Kod ve veri yok; yöntemi yeniden yazıp AerialVL'de koştuk | ST.5'te makale seviyesinde (8,8 m). LT.6'da iz kayboldu |
| AnyVisLoc (Ye vd., CVPR-F 2026) | Reprodüksiyon: yayımlanan kod ve veri | R@1 tekrarlandı (61,9 / 61,6). A@5 m karşılaştırılamaz, çünkü kod ve veri değişti |
| Bi vd. (ISPRS J. 2026), XIAN-Visloc | Reprodüksiyon: yayımlanan kod ve ağırlıklar | Table 13 **birebir**. Diğer tablolar kısmen tuttu |
| SUE (Zaffar vd., CVPR 2024) | Reprodüksiyon (St Lucia) | **Birebir** |
| Bar-Shalom vd. (2001), §5.3–5.4 | Simülasyon | **Tekrarlandı** |
| Sequence Matching (Wang vd., TGRS 2024) | Kod erişilemedi; yeniden yazıldı (ALTO) | Sıralama adımı tekrarlandı, eşleştirme kısmen |
| SatLoc (Zhou vd., 2025), güven formülü | Veri çok büyük (529 GB); formül bizim kayıtlarımızda denendi | Formülde işaret hatası bulundu |
| UAV-VisLoc (Xu vd., 2024) | Veri seti istatistikleri | Büyük ölçüde tutuyor, küçük farklar var |
| GeoVINS, UAVD4L, OrthoLoC, OrthoTrack, Ahmedelbadawi vd., Wang vd. | Yapılamadı | Kod ya da veri yok, ya da veri çok büyük |

## Öne çıkan bulgular

**1. Yanlış fix'ler sık ve büyük.**

- AerialVL'de, yer görüntüleriyle eğitilmiş ağlar doğru harita karosunu ilk sırada yalnızca
  %30 civarında buluyor.
- AnyVisLoc'ta kalan hatalar "ya hep ya hiç" türünde. Yanlış fix birkaç metre değil, çok uzak
  çıkıyor.
- XIAN-Visloc'ta ilk sıradaki karo kilometrelerce uzak çıkabiliyor (bir uçuşta en büyük hata
  16 km).

**2. Yanlış fix kabul edilince iz kayboluyor ve geri gelmiyor.**
Bunu üç farklı yöntemde gördük: AerialVL protokolü, Zhang vd. ve Sequence Matching.

- AerialVL LT.6'da rotanın %75'i kayıp.
- Zhang yönteminde LT.6'nın son hatası 1,2 km.
- Bu yöntemlerin kalite kapıları ve yerel yeniden konumlama adımları izi kurtaramadı.

**3. İncelenen yöntemlerin hiçbiri kalibre bir hata olasılığı vermiyor.**
Kullanılanlar ham skorlar, eşikler ve elle seçilmiş ağırlıklar.

- SatLoc'un güven formülü, makalede basıldığı haliyle ters çalışıyor. İşareti düzeltilince
  çalışıyor, ama UAV-VisLoc'ta iyi fix'i kötüsünden ayıramıyor (AUROC ≈ 0,5).
- SUE ancak mesafe ağırlığıyla işe yarıyor. Ağırlık olmadan basit L2 skorundan kötü.
- χ² testi, filtrenin kovaryansı küçük tahmin edilince doğru fix'leri reddediyor. Kovaryans 2
  kat küçükse %22, 9 kat küçükse %72.

**4. Değerlendirme için çıkan uyarılar.**

- AerialVL'nin başarı oranı, izin kaybolduğu kısmı saymıyor. LT.6'da iz rotanın %75'inde
  kayıp, ama başarı oranı %89,5 görünüyor. Bu yüzden kayıp payı da raporlanmalı.
- Kapalı döngüde ortalama ve en büyük hata koşudan koşuya değişiyor; medyan kararlı. Bu,
  önerideki beş tohum (seed) ile tekrarlama planını destekliyor.
- Yayımlanan kod ve veri makaledekinden farklı olabiliyor. AnyVisLoc'un deposu makaleden
  sonra güncellenmiş. Bi vd.'nin yayımlanan ağırlığı, makaledeki gerçek uçuş modeli çıktı.
  Bu yüzden atıflarda kod ve veri sürümü de belirtilmeli.

## Projeye katkısı

- **Problemin varlığını literatürün kendi yöntemleriyle gösterdik.** Yanlış fix'ler büyük ve
  kendinden emin görünüyor. Kabul edildiklerinde iz kayboluyor.
- **Projenin önerdiği şey tam bu boşluğa denk geliyor.** Öneride, χ² testinden önce hafif bir
  sınıflandırıcı (lojistik regresyon, random forest ya da XGBoost) her fix için kalibre bir
  "T metreden uzak" olasılığı üretiyor. Bunu Zhang'dan uyarlanmış kapı ile karşılaştırıyoruz.
  χ² testi iki politikada da ortak.
- **Temel yöntemler hazır.** Zhang kapısı yeniden yazıldı ve AerialVL'de çalışıyor. χ²
  testinin zayıf noktası ölçüldü. SatLoc ve SUE'nin hangi biçimde karşılaştırılacağı
  netleşti.
- **Bu çalışma problemi gösteriyor, çözümü değil.** Önerilen yöntemin işe yarayıp yaramadığı
  projenin kendi deneylerinde ölçülecek.

## Öneri metniyle ilgili tespitler

1. **Birincil ölçüt iki yerde farklı.** Özet ve Problem Tanımı'nda ana ölçüt "100 deneme
   başına zararlı düzeltme". Methodology §5'te ise ayrım ve kalibrasyon ölçütleri birincil.
   Tek bir tanımda birleştirilmeli.
2. **AerialVL "79.6–88.0%" ifadesi.** Bu oran rotanın tamamı için değil, iz kaybolmayan kısım
   için hesaplanıyor. Metinde bu belirtilmeli.
3. **AnyVisLoc %74,1 değeri.** Makaleye göre doğru. Ama bugünkü açık kod ve veriyle aynı
   kurulum %94,4 veriyor. Açık sürümü kullanırsak bizim başlangıç değerimiz farklı olacak.
4. **Etiket eşiği T.** Öneride geçici olarak 25 m, mevcut kodda 10 m. Test dizilerine
   dokunmadan önce tek bir değerde sabitlenmeli.
5. **XIAN-Visloc.** Georeferans doğru. Ancak CSV'lerde zaman damgası ve kamera duruşu yok.
   Lisans henüz kontrol edilmedi.

## Açık işler

- AnyVisLoc Table 4'ün SP+LG satırları koşulmadı.
- Bi vd.: BEMN-B tam yöntemi bellek yetmediği için çalışmadı. Gerçek uçuş 3 tamamlanmadı.
- Projenin kendi kapalı döngü eşik seçimi deneyinde 24 koşudan 14'ü bekliyor.

Donanım: RTX 4060 (8 GB) dizüstü bilgisayar ve Kaggle (2× T4).
