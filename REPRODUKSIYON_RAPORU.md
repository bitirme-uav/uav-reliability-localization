# Reprodüksiyon Raporu — öncelikli okuma listesindeki makaleler

Tarih: 2026-10-28. Kapsam: proje önerisi v6 §19'daki öncelikli okuma listesi (16 kalem).

## Bu rapor ne için

1. **Danışmana sunum:** Listedeki her makale için neyi yeniden çalıştırabildiğimizi, makale
   değeriyle bizim değerimizi ve projeye çıkarımını tek yerde toplar.
2. **Ekipteki insanlar ve AI ajanları için referans:** Bir makalenin sonucu, kodu ya da veri
   durumu gerektiğinde önce bu dosya okunur. Ayrıntılar `reproducibility/README.md` içinde,
   ham sayılar `reproducibility/results/` altındadır. Bu rapordaki her sayı o dosyalardan
   alınmış ve 2026-10-28'de karşılaştırılarak kontrol edilmiştir.

## Bu çalışma projeye ne kattı

**1. Çözmeye çalıştığımız problemin gerçek olduğunu literatürün kendi yöntemleriyle gösterdik.**
- İz bir kez kaybolunca geri gelmiyor. Bunu üç farklı yöntemde gördük: AerialVL protokolü
  (LT.6'da rotanın %75'i), Zhang vd. (LT.6'da son hata 1,2 km) ve Sequence Matching.
- Yanlış fix'ler küçük değil, büyük ve kendinden emin görünüyor:
  - AnyVisLoc'ta hatalar "ya hep ya hiç".
  - XIAN-Visloc'ta ilk sıradaki karo kilometrelerce uzak çıkabiliyor.
  - Yerde eğitilmiş VPR ağları ilk sırada ancak %30 civarında doğru karoyu buluyor.
- İncelenen yöntemlerin hiçbiri, bir fix'in ne zaman yanlış olduğunu güvenilir biçimde
  söylemiyor. Bu yöntemlerin bir kısmı kalite kapısı ve yerel yeniden konumlama kullanıyor.

**2. Projenin hedefi tam bu boşluk.**
- Proje her fix için kalibre edilmiş bir güvenilirlik tahmini üretiyor.
- Bu tahmine ve χ² kapısına göre fix kabul ya da reddediliyor.
- İz kaybolunca yeniden yakalama (REACQUIRE) başlıyor.
- Bu raporun gösterdiği şey problemin varlığı. Projenin bu problemi ne kadar çözdüğü ise
  projenin kendi deneylerinin konusu (`FINAL_RAPOR.md`). O deneylerdeki kapalı döngü eşik
  seçimi henüz bitmedi (§14).

**3. Tasarım kararlarına doğrudan dayanak sağladı.**
- Harita düzeltmesi şart: saf VO kilometrelerce sapıyor (§4).
- χ² kapısı ancak kovaryans doğruysa çalışıyor, bu yüzden kalibrasyon gerekli (§11).
- SatLoc'un güven formülü basıldığı haliyle ters çalışıyor ve UAV-VisLoc'ta bilgi taşımıyor
  (§8). Sezgisel güven skorlarına güvenilemiyor.
- SUE, eklenebilecek ucuz bir güvenilirlik özelliği (§7).

**4. Değerlendirme yöntemimizi belirledi.**
- AerialVL'nin başarı oranı iz kaybını gizleyebiliyor. Bu yüzden kayıp payını ve CTL'yi de
  raporlayacağız.
- Kapalı döngü sonuçları koşudan koşuya değişiyor. Bu yüzden birden fazla tohum (seed) ve
  medyan kullanacağız.

**5. Karşılaştırma için güvenilir referanslar elde ettik.**
- Birebir tekrarlananlar: SUE, Bi vd. Table 13, Bar-Shalom.
- Yakından tekrarlananlar: AerialVL Table III, AnyVisLoc R@1.
- Yayımlanan kod ve verinin makaleden farklı olduğu yerleri belgeledik (AnyVisLoc, Bi vd.).
  Bunlarla yanlış bir kıyas yapmayacağız.

Terimler:
- **Reprodüksiyon:** Yazarların kodu ve verisiyle (ya da makalenin tarif ettiği veriyle)
  aynı deneyi tekrar çalıştırmak.
- **Yeniden yazım:** Kod yayımlanmadığı için yöntemi makaleden kodlamak.
- **Başka veride:** Makalenin verisi kapalı olduğu için yöntemi açık bir veri setinde
  çalıştırmak. Bu durumda sayılar makaleyle birebir karşılaştırılamaz.

## 1. Özet

| # | Makale | Ne yapıldı | Sonuç |
|---|---|---|---|
| 1 | AerialVL (He vd., RA-L 2024), Table VII | Protokol, bizim lokalizatörümüzle (VO yok) | Birebir değil. ST.5 ve LT.5'te makalenin üstünde, LT.6'da iz kaybedildi |
| 16 | AerialVL, Table III (tek aşamalı VPR) | Reprodüksiyon (aynı veri, aynı ağırlıklar) | **Tekrarlandı:** 36 değerin 31'i ±2,5 puan içinde |
| 3 | SatLoc (Zhou vd., Remote Sens. 2025), Eq. (2) | Güven formülü bizim fix kayıtlarımızda | Formülde işaret hatası bulundu |
| 4 | Zhang vd. (UST 2026) | Yeniden yazım, AerialVL'de | ST.5 makale seviyesinde, LT.6'da iz kaybedildi |
| 5 | AnyVisLoc (Ye vd., CVPR-F 2026), Table 6 | Reprodüksiyon (yayımlanan kod ve veri) | R@1 tekrarlandı (61,9 / 61,6). A@5 m karşılaştırılamaz (94,4 / 74,1) |
| 6 | UAV-VisLoc (Xu vd., 2024), Table II | Veri seti istatistikleri | Büyük ölçüde tutuyor, küçük farklar var |
| 7 | Bar-Shalom vd. (2001), §5.3–5.4 | Simülasyon | **Tekrarlandı** |
| 8 | Sequence Matching (Wang vd., TGRS 2024) | Yeniden yazım, ALTO'da | Sıralama tekrarlandı, eşleştirme kısmen |
| 13 | Bi vd. (ISPRS J. 2026), XIAN-Visloc | Reprodüksiyon (yayımlanan kod ve ağırlıklar) | Table 13 **birebir**. XIAN-Visloc tabloları kısmen |
| 15 | SUE (Zaffar vd., CVPR 2024), Table 2 | Reprodüksiyon (St Lucia) | **Birebir** |
| 2, 9, 10, 11, 12, 14 | GeoVINS, UAVD4L, OrthoLoC, OrthoTrack, Ahmedelbadawi, Wang | — | Yapılamadı (§12) |

Donanım: dizüstü bilgisayar (RTX 4060, 8 GB) ve Kaggle (2× T4, 31 GB RAM).

## 2. AerialVL — Table III, tek aşamalı VPR (`reproducibility/aerialvl_vpr/`)

Veri ve kurulum:
- Veri: AerialVL'nin VPR bölümü, Hugging Face `hmf21/AerialVL` (76,5 GB). İçinde 14.096 harita
  karosu ve 18.361 sorgu var; iki sayı da makaledekiyle aynı.
- Ağırlıklar: Makalenin kullandığını söylediği MSLS ağırlıkları, Berton vd. benchmark'ı @ `4af5194`.
- Girdi boyutu benchmark varsayılanı olan 480×640. Üç karo seviyesi tek veritabanı olarak
  kullanıldı. Hiç ayar yapılmadı.

R@N (%), "makale → biz". Her hücrede iki değer var: 50 m / 100 m eşiği.

| Model | R@1 | R@5 | R@10 |
|---|---|---|---|
| NetVLAD-VGG16 | 24,0/44,4 → 24,8/42,9 | 50,0/64,1 → 48,9/62,8 | 60,2/71,8 → 59,6/71,1 |
| NetVLAD-R50 | 31,8/53,2 → 29,3/52,0 | 58,0/73,8 → 57,3/72,2 | 66,5/79,8 → 66,5/78,3 |
| NetVLAD-R101 | 28,6/51,5 → 30,7/53,8 | 56,3/71,9 → 58,7/74,0 | 65,5/78,6 → 68,1/79,7 |
| GeM-VGG16 | 17,6/33,1 → 21,2/37,0 | 42,4/55,1 → 44,6/58,2 | 53,1/62,7 → 54,7/67,0 |
| GeM-R50 | 27,3/48,4 → 27,8/50,2 | 54,9/69,7 → 55,8/70,0 | 65,7/78,5 → 67,4/77,6 |
| GeM-R101 | 30,4/54,7 → 31,0/57,2 | 62,4/77,0 → 61,0/76,4 | 72,5/83,5 → 70,7/82,3 |

- **Tekrarlandı.** 36 değerin 31'i ±2,5 puan içinde. Ortalama mutlak fark 1,6 puan, en büyük
  fark +4,3 (GeM-VGG16, R@10 100 m).
- **Projeye çıkarımı:** Yerde eğitilmiş global tanımlayıcılarla doğru karo (50 m içinde) ilk
  sırada ancak yaklaşık %30 oranında bulunuyor. Sadece aramaya dayanan bir fix çoğu zaman
  yanlış olur. Bu yüzden yerel eşleştirme ve güvenilirlik kontrolü gerekiyor.

## 3. AerialVL — Table VII protokolü (`reproducibility/aerialvl_table7.py`)

Protokol:
- Bilinen başlangıçtan sıralı hizalama yapılıyor.
- **Succ. Rate:** Kayıp olmayan kısımda hatanın 25 m altında kaldığı oran.
- **Kayıp:** Hatanın 50 m'yi geçtiği kareler.
- **MLE:** Kayıp kısım dışındaki ortalama hata.
- **CTL:** 50 m içinde konumlanan rota uzunluğu.

Makale dizilerinin adını vermiyor. Diziler uzunluk oranından eşlendi: ST.5 = `2023-03-18-16-43-16`,
LT.5 = `2023-03-18-15-01-14`, LT.6 = `2023-03-18-15-40-18`. Her ikinci kare kullanıldı (yaklaşık 1 s aralık).
Koşu Kaggle'da yapıldı.

| Dizi | Biz: Succ. / MLE | Biz: kayıp payı / CTL | Makale Comb.1 | Makale Comb.2 |
|---|---|---|---|---|
| ST.5 (603 kare, 4,52 km) | 98,6 % / 9,0 m | 2,8 % / 4,39 km | 71,41 % / 20,01 m | 79,57 % / 22,27 m |
| LT.5 (945 kare, 6,86 km) | 86,7 % / 15,0 m | 21,1 % / 5,41 km | 40,87 % / 26,92 m | 83,27 % / 14,22 m |
| LT.6 (1.302 kare, 9,84 km) | 89,5 % / 13,5 m | **75,4 %** / 2,42 km | 70,05 % / 17,89 m | 88,04 % / 17,50 m |

- **Birebir değil.** Bizde görsel odometri yok; tahmin, kabul edilen fix'lerden sabit hızla
  yapılıyor. Kabul kapısı projenin dondurulmuş E3 eşiği (inlier oranı ≥ 0,367). Arama yarıçapı
  60 m, kurtarma araması 300 m.
- **LT.6'da iz kayboldu.** İz 372. karede kayboldu ve geri gelmedi. Medyan hata 7,4 km, rotanın
  sadece %22'sinde hata 25 m'nin altında. Buna rağmen Succ. Rate %89,5 görünüyor, çünkü bu ölçüt
  kayıp kısmı saymıyor. Succ. Rate tek başına raporlanmamalı; kayıp payı ve CTL ile birlikte
  verilmeli.
- **LT.5'te de iz kayboldu.** İz 896. karede (945 kareden) kesin olarak kayboldu.

## 4. Zhang vd. (UST 2026) — yeniden yazım, AerialVL'de (`reproducibility/aerialvl_zhang.py`)

Durum: Kod yok. Veri, Tianjin'de yapılmış iki özel uçuş ve yayımlanmamış.

Yeniden yazılan kısımlar (Eq. 5–10):
- Homografi tabanlı görsel odometri.
- Belirli karelerde haritaya hizalama.
- Kalite kapısı.
- Yerel yeniden konumlama ve saf VO karşılaştırması.

Makaleden sapmalar:
- XFeat yerine SuperPoint + LightGlue kullanıldı. Makale, yöntemin özellik çıkarıcıdan
  bağımsız olduğunu söylüyor.
- Haritaya hizalama dönüşümü bir benzerlik dönüşümü.
- Makale kapı eşiklerini vermiyor. Eşikleri sonuçlara bakmadan önce sabitledik: eşleşme ≥ 30,
  inlier ≥ 20, oran ≥ 0,367, yeniden izdüşüm ≤ 3 px, düzeltme ≤ 30 m, yeniden konumlama 3×3
  ızgara / 60 m.

Makalenin kendi verisinde (Table II) ortalama hata 8,1 m ve 8,4 m, 10 m içinde kalma oranı %80,3
ve %86,8. Rotalar 0,6 km ve 1,8 km.

| Dizi | Ortalama | Medyan | Maks. | Son | ≤10 m | ≤20 m | Yeniden konumlama |
|---|---|---|---|---|---|---|---|
| ST.5 | **8,8** | 7,5 | 35,3 | 2,7 | 71,0 % | 95,4 % | 74 |
| ST.5, saf VO | 1003,1 | 1092,4 | 1702,0 | 1700,6 | 0,7 % | 4,5 % | |
| LT.5 | 21,4 | 11,7 | 154,3 | 127,1 | 39,5 % | 76,6 % | 220 |
| LT.5, saf VO | 7934,3 | 3163,3 | 1.215.487,7 | 3914,1 | 0,0 % | 1,3 % | |
| LT.6 | 353,7 | 25,1 | 1387,3 | 1215,8 | 28,5 % | 46,3 % | 681 |
| LT.6, saf VO | 1482,8 | 1184,5 | 3079,2 | 2172,4 | 0,9 % | 2,2 % | |

- **ST.5:** Makale seviyesinde, 2,5–7,5 kat daha uzun bir rotada.
- **LT.6:** Düzeltmeler kabul edilmemeye başladı; 6.447 adaydan 260'ı kabul edildi. Yeniden
  konumlama ızgarası izi tekrar yakalayamadı.
- **Saf VO:** Üç dizide de kilometrelerce sapıyor. Bu, makalenin "harita düzeltmesi şart"
  bulgusuyla uyumlu.
- **Table VII ölçütleriyle:** Aynı koşular ST.5 98,5 % / 8,8 m / kayıp 0 %, LT.5 94,0 % / 12,6 m /
  10,4 %, LT.6 84,9 % / 14,0 m / 39,5 % veriyor. VO'lu Zhang, VO'suz Table VII döngümüzden daha
  geç kayboluyor. İkisi de yeniden konumlama menzilini aşan bir hatadan sonra toparlanamıyor.
- **Tekrarlanabilirlik:** ST.5 Kaggle'da tekrar koşuldu. Medyan 7,1 m çıktı (dizüstünde 7,5 m),
  ama ortalama 10,8 m (8,8 m) ve en büyük hata 91,0 m (35,3 m). Kapalı döngü sonuçları yola
  bağımlı: medyan kararlı, ortalama ve en büyük hata tek koşudan yorumlanmamalı.
- **Önerideki ifade:** `src/gates.py` içinde Zhang'a özgü bir kapı yok. Önerideki Zhang
  karşılaştırması kavramsal düzeyde.

## 5. AnyVisLoc (Ye vd., CVPR-F 2026) — Table 6 (`reproducibility/anyvisloc_run.py`)

Kurulum:
- Yöntem: CAMP ile arama, RoMa ile eşleştirme, ilk 5 adayı yeniden sıralama, P3P, hava
  fotoğrafı haritası.
- Kod: UAV-AVL/Benchmark @ `6c8f798`, yanında bellek yaması (yönteme dokunmuyor).
- Veri: 24 sahne, her sahnenin her 10. görüntüsü, toplam 2.018 görüntü.
- Koşu Kaggle'da yapıldı ve hiçbir sahne hata vermedi.

| | n | R@1 | A@1 m | A@3 m | A@5 m | A@10 m | A@20 m |
|---|---|---|---|---|---|---|---|
| Makale, Table 6 | ~18.000 | 61,6 | | | 74,1 | 87,7 | 94,2 |
| Biz | 2.018 | **61,9** | 71,1 | 92,7 | 94,4 | 95,7 | 96,5 |

- **Arama tekrarlandı.**
- **Konum doğruluğu karşılaştırılamaz.** 2026-07-01'de depo yenilendi ve veri seti de değişti: üç sahne
  çıkarıldı, iki sahne eklendi ve PnP artık kamera bozulma katsayılarını kullanıyor. Makalenin
  %74,1'i bugün açık olan kod ve veriyle yeniden üretilemez.
- **Hata dağılımı:** Kalan yaklaşık %5'lik hata "ya hep ya hiç" türünde. Scene_06 ve Scene_21'de
  A@5 m ile A@20 m neredeyse eşit; yani yanlış bir fix birkaç metre değil, çok uzak çıkıyor.
  Güvenilirlik kapısının yakalaması gereken durum tam olarak bu.
- **İlk dizüstü koşusu kullanılmamalı.** O koşu 9 sahneden oluşuyor ve A@5 m 96,8 veriyor; zor
  sahneler eksik olduğu için reprodüksiyon olarak alıntılanmamalı.
- **Table 4 SP+LG satırları koşulmadı.** Script bu seçeneği destekliyor (`--matcher SP_LG`).

## 6. Bi vd. (ISPRS J. 2026), XIAN-Visloc (`reproducibility/bi_xian_visloc/`)

Kurulum: Kod VERYBC/UCVL @ `020c3e6`, yayımlanan BEMN-Tiny ve BEMN-Base ağırlıkları. Sadece
değerlendirme yapıldı. Koşu Kaggle'da.

| Ayar | Makale R@1 / AP / Dis@1 | Biz |
|---|---|---|
| Aynı alan, BEMN-T, tam yöntem | 74,14 / 71,90 / 216,49 m | 76,18 / 73,88 / 477,56 m |
| Aynı alan, BEMN-B, yöntemsiz | 75,53 / 73,94 / 164,41 m | 79,40 / 78,50 / 366,83 m |
| Farklı alan (Weinan), BEMN-T, yöntemsiz | 53,76 / 43,58 / 645,20 m | 80,28 / 64,44 / 240,50 m |
| Gerçek uçuş 1, BEMN-T w/SC (Table 13) | 56,00 / 40,06 / 1027,41 m | **56,00 / 40,06 / 1027,41 m** |

- **Yayımlanan ağırlık hangi model?** Yayımlanan BEMN-T ağırlığı, makalenin gerçek uçuş modeli
  (§5.9). Table 13 iki ondalığa kadar birebir çıkıyor. Bu model XIAN-Visloc'un test uçuşlarını da
  görmüş olabilir. Bu yüzden Table 4/7/9 tam olarak yeniden üretilemez ve bu ağırlıklarla
  "görülmemiş alan" başarısı iddia edilmemeli.
- **Dis@1 makaledekinin yaklaşık iki katı.** Dis@1 bir ortalama ve birkaç büyük hata onu
  belirliyor. Uçuş 16'da sorguların %16'sı 500 m'den uzak, en büyük hata 16 km.
- **Bulunan kod/veri sorunları:**
  - `target_size = (3,3)` hatası.
  - Veri yolu `Xian_visloc` içermezse kod çöküyor.
  - Hazır karo kütüphanesinde bir kopya karo var.
  - Merkez bölge eşleştirme 31 GB RAM'e sığmıyor.
- **Bitmeyen koşular:** BEMN-B'nin tam yöntemi ve gerçek uçuş 3.

## 7. SUE (Zaffar vd., CVPR 2024) — Table 2, St Lucia (`reproducibility/sue_check.py`)

Değiştirilmemiş `sue.py` (`tudelft-iv/SUE` @ `24bdae5`) çalıştırıldı. Sonuçlar AUC-PR, 1.464 sorgu:

| | L2 | PA | BTL | STUN | SUE | SIFT-R | DELF-R | SP-R |
|---|---|---|---|---|---|---|---|---|
| Makale / README | 0,7970 | 0,7735 | 0,3419 | 0,6628 | 0,8849 | 0,9313 | 0,9719 | 0,9736 |
| Biz | 0,7971 | 0,7735 | 0,3419 | 0,6629 | 0,8850 | 0,9313 | 0,9719 | 0,9736 |

- **Birebir.** Sadece St Lucia sütunu yapılabildi; diğer veri setleri bu biçimde yayımlanmamış.
- **Mesafe ağırlığı (eğim λ) şart.** λ = 0 olduğunda SUE 0,669 veriyor, yani L2'den kötü. λ = 350
  olduğunda 0,885. Makaledeki 200–400 aralığının kararlı olduğu doğrulandı.
- **Kırpma hatası önemsiz.** Kod sadece pozitif sapmaları 500 m'de kırpıyor. Simetrik kırpma
  0,887 veriyor; etkisi ihmal edilebilir.
- **Projeye çıkarımı:** SUE, arama sonuçlarındaki ilk K karonun konum dağılımından ucuz bir ek
  güvenilirlik özelliği olabilir. Ancak kalibre bir olasılık değil.
- **Pickle güvenliği:** Pickle dosyası sadece Kaggle sanal makinesinde açıldı. Pickle yüklenirken
  kod çalıştırabilir.

## 8. SatLoc (Zhou vd., Remote Sens. 2025) — Eq. (2) güven C1 (`reproducibility/satloc_c1.py`)

SatLoc verisi 529 GB olduğu için indirilemedi. Formül projenin açık döngü fix kayıtlarında
değerlendirildi. Ölçüt, "hata ≤ 10 m" etiketi için AUROC.

| Veri | C_score (basıldığı gibi) | C_score (işaret düzeltilmiş) | C1 düzeltilmiş, w = 0,5 |
|---|---|---|---|
| AerialVL TEST | 0,243 | 0,757 | 0,773 |
| AnyVisLoc TEST | 0,218 | 0,782 | 0,753 |
| ALTO TEST | 0,349 | 0,651 | 0,633 |
| VPAIR TEST | 0,329 | 0,671 | 0,655 |
| UAV-VisLoc TEST | 0,486 | 0,514 | 0,494 |

- **Formülde işaret hatası var.** Basıldığı haliyle formül, en iyi eşleşme öne çıktıkça güveni
  düşürüyor. Bu, makalenin metniyle çelişiyor ve fix'leri ters sıralıyor.
- **Düzeltilmiş hali projeninkiyle aynı.** İşaret düzeltilince formül, projenin SatLoc tarzı
  sezgisel skoruyla aynı oluyor.
- **GSD terimi çoğu veride zarar veriyor.** Sadece AerialVL'de biraz katkı sağlıyor.
- **UAV-VisLoc'ta bilgi yok.** AUROC yaklaşık 0,5; skor bu veride iyi fix'i kötüsünden ayıramıyor.
- **Yaklaşıklık:** Bizim kayıtlarımızda sadece ikinci en iyi skor var (M = 1).

## 9. Sequence Matching (Wang vd., TGRS 2024) — ALTO (`reproducibility/seqmatch_alto.py`)

Kod sitesi kapalı olduğu için yöntem yeniden yazıldı: ISOMAP ile sıralama (Alg. 1) ve LoFTR ile
sıralı eşleştirme. Bizim ALTO Val, makalenin test bölümü (1.684 / 459 görüntü; makalede
1.683 / 458).

**Sıralama:**

| | Makale | Biz |
|---|---|---|
| S-ACC, ISOMAP (AlexNet, k = 3) | 0,990 | **1,000** |
| S-ACC, PCA / t-SNE | 0,004 / 0,004 | 0,007 / 0,037 |
| k taraması | k ∈ [3, 8] için kararlı | k = 3–8 için ≥ 0,99 |

AlexNet özelliği evrişim çıkışı (pool5, 9216 boyut) olmalı. fc7 ile k = 3'te sonuç 0,00 çıkıyor.
Diğer omurgalarda bizim sonuçlarımız ≤ 0,03, makalede 0,36–0,71. Makale bu omurgalar için hangi
katmanı kullandığını söylemiyor. Sıralama (AlexNet en iyi) tutuyor, ara değerler tutmuyor.

**Eşleştirme (Table I "Ours", M = 10):**

| | R@1 | R@5 | mAP |
|---|---|---|---|
| Makale | 41,63 | 99,11 | 69,42 |
| Biz, 256 px, makaledeki pencere | 35,21 | 75,30 | 54,21 |
| Aynı koşu, ilk 1.300 kare | 41,1 | 91,9 | 65,2 |
| Biz, 500 px, pencere bir yama geriden | 40,50 | 83,31 | 59,91 |

- **İz kaybı:** Pencere sadece ileri baktığı için iz kayınca gerçek yama pencerenin dışında
  kalıyor ve iz geri gelmiyor. Son 384 karede R@1 %15'e düşüyor. Makale bir kurtarma
  mekanizması tarif etmiyor.
- **Makalenin R@5'i sadece iz tutarken yakalanıyor.** 500 px'te pencere bir yama geriden
  başlatılınca ilk yaklaşık 900 karede R@5 %99,9. Tüm rotada ise R@5 %83,3.

## 10. UAV-VisLoc (Xu vd., 2024) — Table II (`reproducibility/uav_visloc_stats.py`)

Makalede konumlama deneyi yok; yeniden üretilebilecek kısım veri seti istatistikleri.

- **Sayılar:** 6.774 görüntü (makalede 6.742), 11 uçuş, 14 harita dosyası. Uçuş 09'un haritası
  4 parça.
- **Uyan alanlar:** Görüntü boyutu, çekim ayı ve yükseklik (±1 m) tüm uçuşlarda tutuyor. Harita
  boyutu 11 uçuşun 10'unda tutuyor; uçuş 06'nın yayımlanan haritası daha büyük.
- **Yön açısı Φ:** 6 uçuşta ilk karenin değeriyle tutuyor. 02, 04, 06 ve 10'da yaklaşık
  160–180° fark var.
- **Uçuş 07:** Duruş (attitude) sütunları yok ve tarih alanı bozuk.

## 11. Bar-Shalom vd. (2001) — §5.3–5.4 (`reproducibility/barshalom_consistency.py`)

DWNA Kalman örneği kitaptaki gibi simüle edildi: 100 adım, 50 Monte Carlo koşusu.

- **Deterministik değerler birebir tutuyor:** Kararlı durum kazançları [0,75, 0,50] ve
  [0,901, 0,942]; χ² eşikleri ve NEES/NIS bölgeleri.
- **Rastgele sayımlar beklenen aralıkta.** Örnek: uyumsuz filtrede tek koşuda 5,99'u aşan NEES
  noktası kitapta 41/100, bizde 43/100.
- **Proje kapısı için ek deney:** İnovasyon kovaryansı 2 / 4 / 9 kat küçük tahmin edilirse
  2 serbestlik dereceli χ² kapısı (α = 0,05) doğru fix'lerin %22 / %47 / %72'sini reddediyor.
  Kovaryans doğruyken bu oran %5. FINAL_RAPOR'daki "kovaryans yanlış belirlendiğinde χ² kapısı
  çöküyor" bulgusunun mekanizması bu.

## 12. Yapılamayanlar

| # | Makale | Neden |
|---|---|---|
| 2 | GeoVINS (Li vd., T-RO 2025) | Kod yok. Veri rosbag olarak Baidu'da ve çok büyük |
| 9 | UAVD4L (Wu vd., 3DV 2024) | Kod var, veri çok büyük |
| 10 | OrthoLoC (Dhaouadi vd., NeurIPS 2025) | Kod var, veri 287 GB |
| 11 | OrthoTrack (Dhaouadi vd., ECCV 2026) | Kod sadece duyuruldu, MovingDrone verisi büyük |
| 12 | Ahmedelbadawi vd. (SPIE 2025) | Ne kod ne veri var |
| 14 | Wang vd. (ISPRS Archives 2026) | Kod yok, veri yazarların kendi uçuşları ve yayımlanmamış |

## 13. Projeye çıkarımlar

Her madde yukarıdaki bölümlere dayanıyor.

1. **Yanlış fix'ler büyük ve kendinden emin görünüyor.**
   - Arama ilk sırada çoğu zaman yanlış karoyu veriyor (§2: R@1 ≈ %30).
   - İyi sistemlerde bile kalan hatalar "ya hep ya hiç" (§5).
   - Ortalama hatayı birkaç kilometrelik hata belirliyor (§6).
   - Bu, güvenilirlik kapısının neden gerektiğini gösteriyor.
2. **Kapalı döngüde iz bir kez kaybolunca geri gelmiyor.** AerialVL döngümüz, Zhang ve Sequence
   Matching'in üçü de bunu gösteriyor (§3, §4, §9). Bu yöntemlerin yerel yeniden konumlama ya da
   kurtarma adımları, menzil dışına çıkmış bir izi toparlamıyor. Yeniden yakalama (REACQUIRE) ve güvenilirlik kontrolü projenin asıl katkı alanı.
3. **Harita düzeltmesi şart.** Saf VO 4,5–9,8 km'lik rotalarda kilometrelerce sapıyor (§4).
4. **Değerlendirmede tek bir başarı ölçütü yetmez.**
   - Succ. Rate kayıp kısmı gizleyebiliyor (§3); kayıp payı ve CTL de raporlanmalı.
   - Kapalı döngüde ortalama ve en büyük hata koşudan koşuya değişiyor (§4). Birden fazla tohum
     (seed) ve medyan kullanılmalı.
5. **Güven skorları dikkatle kullanılmalı.**
   - SatLoc'un formülü basıldığı haliyle ters çalışıyor ve UAV-VisLoc'ta bilgi taşımıyor (§8).
   - SUE ucuz bir ek özellik olabilir (§7).
   - χ² kapısı doğru kovaryansa bağlı (§11). Bu, kalibre edilmiş güvenilirlik modeli fikrini
     destekliyor.
6. **Yayımlanan kod ve veri makaledekiyle aynı olmayabilir** (§5 AnyVisLoc, §6 Bi). Bu
   kaynaklara atıf yapılırken commit ve veri sürümü de verilmeli.

## 14. Açık işler

- AnyVisLoc Table 4 SP+LG satırları koşulmadı.
- Bi vd.: BEMN-B tam yöntemi bellek nedeniyle çalışmadı. Gerçek uçuş 3 bitmedi.
- AerialVL Table VII ve Zhang LT.5/LT.6 koşularının kare bazlı logları Kaggle sanal makinesiyle
  silindi. Repoda sadece özetler var.
- Bu rapordan ayrı olarak, projenin kendi deneyi olan kapalı döngü eşik seçiminin 24 koşusunun
  14'ü bekliyor (`outputs/thr_dev/cmds_rest.txt`). Bu koşular `outputs/calibration_models.pkl`
  ve `outputs/reliability_v2_bundle.pkl` dosyalarını istiyor.

## 15. Bu dosyayı kullanacak ajanlar için notlar

- **Doğruluk kaynağı:** `reproducibility/results/` altındaki dosyalar esastır. Bir koşu
  tekrarlanırsa sonuç dosyası, `reproducibility/README.md` ve bu rapor birlikte güncellenmeli.
  Dosyada olmayan bir sayı yazılmamalı.
- **Birebir olmayan sonuçlar:** "Birebir değil" ya da "karşılaştırılamaz" diye işaretlenen
  sonuçlar (§3, §4, §5 A@5 m, §6 Dis@1) makale reprodüksiyonu diye sunulmamalı.
- **Proje kuralları:** Etiket eşikleri (10 m ve 25 m) sonuçlara bakıldıktan sonra
  değiştirilmez. Ayar sadece train/val dizilerinde yapılır. Kapı ve güvenilirlik modeli girdi
  olarak hatadan türetilen hiçbir nicelik kullanmaz.
- **Kaggle:**
  - Repo private olduğu için Kaggle'dan klonlanamıyor; kod dosyaları elle aktarılıyor.
  - Bölünmüş zip'ler birleştirilmeden okunabiliyor (`SplitFile`, `aerialvl_vpr/avl_vpr.py`).
  - `/kaggle/working` 20 GB ile sınırlı.
- **Pickle güvenliği:** Üçüncü taraf pickle dosyaları ekip makinelerinde açılmamalı.
