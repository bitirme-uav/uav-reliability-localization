# Sistem Rehberi: GPS'siz Drone İçin "Güvenilir mi?" Diyen Harita Eşleştirme

*Yapay zekâyı az bilen biri için baştan sona anlatım. Tarih: 2026-10-03.*

Bu dosyayı okuduğunda şunları anlamış olmalısın:
- Ne problemi çözüyoruz?
- Sistem hangi parçalardan oluşuyor ve her parça ne yapıyor?
- "Kalibrasyon" tam olarak ne demek?
- Deneyleri nasıl yaptık; neden bu kadar "dondurma", "TEST'e dokunmama" diyoruz?
- Sonuçlar ne gösterdi: neler çalıştı, neler çalışmadı?
- Şu an ne yapıyoruz ve sırada ne var?

Teknik ayrıntılar `FINAL_RAPOR.md` dosyasında. Bu dosya onun "anlaşılır" versiyonu.

---

## 1. Problem: GPS olmadan drone nerede olduğunu nasıl bilir?

Drone normalde konumunu GPS'ten alır. GPS bazen yoktur:
- sinyal karıştırılmıştır (jamming),
- sahte sinyal gönderiliyordur (spoofing),
- vadi, şehir arası, kapalı alan gibi nedenlerle sinyal zayıftır.

GPS yokken drone'un elinde iki şey kalır:

1. **Kendi hareket sensörleri (IMU, hız, pusula).** "Şu hızla şu yöne 10 saniye gittim, demek ki şuradayım" diye tahmin eder. Buna **ölü hesap (dead reckoning)** denir. Sorunu: küçük hatalar zamanla birikir. 10 dakika sonra drone kendini 100–500 m yanlış yerde sanabilir. Bu birikmiş hataya **drift (kayma)** diyoruz.

2. **Aşağı bakan kamera.** Drone altındaki araziyi görür. Elimizde o bölgenin **uydu haritası** varsa, "kameramın gördüğü şey haritanın neresi?" sorusunu sorarak gerçek konumunu bulabilir. Bu bulunan konuma **fix** (konum düzeltmesi) diyoruz.

**Fikir basit:** Drift ile kayan konumu, belli aralıklarla kamera-harita eşleştirmesiyle düzelt.

**Asıl zorluk:** Kamera-harita eşleştirmesi **bazen yanlış sonuç verir** ve bunu kendisi bilmez. Örneğin:
- birbirine benzeyen tarlalar ve evler,
- harita farklı mevsimde çekilmiş (drone yeşil tarla görüyor, haritada kahverengi toprak var),
- su, orman gibi ayırt edici özelliği olmayan yerler,
- harita çekildikten sonra yapılan yeni binalar.

Yanlış bir fix'i "doğru" diye kabul edersen drone'u **daha da yanlış** yere götürürsün. Bu, hiç düzeltme yapmamaktan daha tehlikeli olabilir.

**Projenin ana sorusu:** Bulunan her fix için "Bu konuma ne kadar güvenebilirim?" sorusunu güvenilir şekilde cevaplayabilir miyiz? Cevaba göre fix'i **kabul et / zayıf kabul et / reddet**.

---

## 2. Büyük resim: sistem nasıl çalışıyor?

Bir benzetme: Şehirde yürüyen ama haritası olan birini düşün.
- Adım sayarak nerede olduğunu tahmin ediyor (ölü hesap).
- Arada bir etrafına bakıp haritayla karşılaştırıyor (kamera eşleştirmesi).
- Gördüğü şey haritada **belirgin bir yere** (meydan, kule) uyuyorsa konumunu düzeltiyor.
- "Bu sokak da öbürü gibi" diye **emin olamıyorsa** düzeltmiyor ya da az düzeltiyor.
- Uzun süre hiçbir şey eşleşmezse "kayboldum" diyor, daha geniş bir alanda dikkatlice arıyor ve tek bir eşleşmeye değil, **iki tutarlı eşleşmeye** güvenince konumunu güncelliyor.

Bizim sistemin akışı tam olarak bu:

```
 ┌──────────────┐   tahmini konum    ┌────────────────────┐
 │ Ölü hesap /  │ ─────────────────▶ │ Haritadan, tahmini │
 │ Kalman filtre│   + belirsizlik    │ konum etrafında bir│
 └──────▲───────┘                    │ parça kes          │
        │                            └─────────┬──────────┘
        │                                      ▼
        │                            ┌────────────────────┐
        │                            │ Kamera görüntüsü ile│
        │                            │ harita parçasını    │
        │                            │ eşleştir → FIX      │
        │                            └─────────┬──────────┘
        │                                      ▼
        │                            ┌────────────────────┐
        │                            │ GÜVENİLİRLİK MODELİ │
        │                            │ "Bu fix doğru mu?"  │
        │                            │ → olasılık (0–1)    │
        │                            └─────────┬──────────┘
        │                                      ▼
        │          kabul / zayıf kabul / ret   │
        └──────────────────────────────────────┘
```

Aşağıda her kutuyu tek tek anlatıyorum.

---

## 3. Parça 1: Ölü hesap ve Kalman filtresi (konum tahmini)

**Kalman filtresi**, birden fazla belirsiz bilgiyi birleştirip en iyi tahmini çıkaran klasik bir matematik aracıdır. Elinde iki şey tutar:
- **Tahmini konum** (ör. "doğuya 1200 m, kuzeye 300 m"),
- **Belirsizlik** (ör. "±50 m kadar yanılıyor olabilirim"). Teknik adı **kovaryans**.

Her adımda:
1. **Tahmin:** Hıza göre konumu ilerletir ve belirsizliği büyütür (zaman geçtikçe daha emin olmaz).
2. **Düzeltme:** Bir fix gelirse, fix'in güvenilirliğine ve kendi belirsizliğine göre ikisinin arasında bir yere geçer. Fix çok güvenilirse fix'e doğru çok gider, değilse az gider.

**Bizde gerçek drone yok.** O yüzden drift'i bilgisayarda **simüle ediyoruz** (`src/drift_simulator.py`). Gerçek konumu biliyoruz (veri setinde var). Üstüne yapay hatalar ekliyoruz:
- sabit sapma,
- hız ve ölçek hatası,
- rastgele yürüyüş,
- pusula sapması,
- ani sıçrama (ör. 300 m).

Üç şiddet seviyesi var: hafif, orta, şiddetli.

**Önemli bir ayrıntı: "doğru" ve "yanlış-belirtilmiş" filtre.** Gerçekte filtre, drift'in ne kadar kötü olduğunu tam bilmez. Bazen kendine fazla güvenir: "±10 m'lik hatam var" der, oysa hata 200 m'dir. Bunu da test ediyoruz:
- *Doğru filtre:* Drift'in gerçek şiddetini biliyor.
- *Yanlış-belirtilmiş filtre:* Hep "hafif drift" sanıyor.

İleride göreceğin gibi bu fark çok önemli çıktı.

---

## 4. Parça 2: Kamera görüntüsünü haritada bulmak (lokalizer)

Dosya: `src/localization_pipeline.py`

### 4.1 Harita parçası kesme
Tüm haritada aramak hem yavaş hem hataya açık. Filtrenin tahmini konumu etrafında bir **arama penceresi** kesiyoruz. Pencerenin yarıçapı belirsizliğe göre ayarlanıyor: r = 3 × belirsizlik, en az 60 m, en fazla 400 m. Büyük pencerelerde önce kaba bir tarama, sonra en umut verici yerde ince arama yapıyoruz ("karolu arama").

### 4.2 Özellik noktaları ve eşleştirme
Burada iki **hazır yapay zekâ modeli** kullanıyoruz. Bunları biz eğitmedik, internette eğitilmiş hâlde var:
- **SuperPoint:** Bir görüntüde köşe, kenar kesişimi gibi **ayırt edici noktaları** bulur ve her noktayı bir sayı dizisiyle (parmak izi gibi) tarif eder.
- **LightGlue:** İki görüntüdeki noktaları karşılaştırıp "şu nokta şununla aynı" diye **eşleştirir**.

### 4.3 RANSAC: yanlış eşleşmeleri ayıklamak
Eşleşmelerin bir kısmı yanlıştır. **RANSAC** şu mantıkla çalışır: "Rastgele birkaç eşleşme seç, bunlardan bir dönüşüm (kaydırma + döndürme + ölçek) hesapla, kaç eşleşme bu dönüşüme uyuyor say; bunu çok kez tekrarla, en çok uyanı seç." Bu dönüşüme uyan eşleşmelere **inlier** denir. Inlier sayısı çoksa eşleşme genelde iyidir, ama her zaman değil.

Dönüşüm bulununca, drone görüntüsünün merkezinin haritada nereye düştüğü hesaplanır. Bu nokta **fix**'tir.

### 4.4 Yapmak zorunda kaldığımız düzeltmeler
- **Yön:** Bu eşleştirici modeller görüntü dönükse iyi çalışmaz. Drone görüntüsünü pusula açısına göre "kuzey yukarı" olacak şekilde döndürüyoruz.
- **Ölçek:** Drone ne kadar yüksekte, görüntü yerde kaç metreyi kapsıyor? Birkaç ölçek deneyip en çok eşleşeni seçiyoruz.
- **Eğik kamera (AnyVisLoc):** Kamera aşağıya dik değil, eğik bakıyorsa görüntüyü önce sanal olarak "tepeden bakış"a çeviriyoruz. Bunun için IMU'dan gelen kamera açılarını kullanıyoruz.
- **Kamera ofseti:** Kamera görüntüsünün merkezi drone'un tam altına denk gelmeyebilir (montaj, gövde eğikliği). Bunu ölçüp sabit bir düzeltme ekledik.

---

## 5. Parça 3: Güvenilirlik modeli (projenin kalbi)

Dosyalar: `src/reliability_model.py`, `src/eval_calibration.py`

### 5.1 Ne öğreniyor?
Her fix için bir dizi **ipucu (özellik)** çıkarıyoruz:
- kaç eşleşme bulundu, kaçı inlier, inlier oranı,
- eşleşmeler görüntüye yayılmış mı, yoksa bir köşede mi toplanmış,
- RANSAC dönüşümü ne kadar "temiz" (yeniden izdüşüm hatası, koşul sayısı),
- en iyi aday ile ikinci en iyi aday arasındaki fark (iki farklı yer de iyi eşleşiyorsa şüpheli),
- bulunan ölçek beklenenle uyumlu mu,
- **Mahalanobis mesafesi:** Fix, filtrenin beklediği yere ne kadar uzak? Belirsizliğe göre ölçülür. "Beklediğimden 3 belirsizlik birimi uzakta" gibi.

Model bu ipuçlarına bakıp tek bir sayı üretiyor: **"Bu fix'in doğru olma olasılığı"** (0 ile 1 arası).

"Doğru" ne demek? Biz baştan sabitledik: **gerçek konuma 10 m'den yakınsa doğru (güvenli), değilse yanlış.** Bu etikete sonradan hiç dokunmadık.

### 5.2 Nasıl öğreniyor? (eğitim)
1. Eğitim uçuşlarındaki binlerce kare için kasıtlı olarak farklı koşullarda fix ürettik. Tahmini konum 0, 30, 80, 200, 300 m hatalı; belirsizlik farklı. Buna **açık-döngü veri seti** diyoruz: filtre yok, sadece "şu koşulda lokalizer ne yaptı" kaydı.
2. Her fix için ipuçlarını ve gerçek hatayı (doğru/yanlış etiketi) kaydettik.
3. Bir **sınıflandırıcı** eğittik: ipuçlarından etiketi tahmin etmeyi öğrenen bir model.
   - **Lojistik regresyon:** En basit modellerden. İpuçlarını ağırlıklarla toplayıp olasılığa çevirir.
   - **Gradient boosting (GBM):** Çok sayıda küçük karar ağacının toplamı. "Inlier < 20 ise ve Mahalanobis > 3 ise → büyük ihtimalle yanlış" gibi kuralları kendisi öğrenir.

Bu modeller küçük ve hızlı (<1 ms). Derin sinir ağı değiller. "Yapay zekâ"nın ağır kısmı eşleştiricide; güvenilirlik modeli hafif bir istatistik katmanı.

### 5.3 KALİBRASYON NEDİR? (en çok sorulan kısım)

"Kalibrasyon" kelimesi bu projede **üç farklı anlamda** geçiyor. Karışıklık bundan çıkıyor.

#### Anlam 1: Olasılık kalibrasyonu (projenin adındaki "Calibrated")
Bir model "%80 eminim" diyorsa, gerçekten de böyle dediği durumların **%80'inde haklı çıkmalı**. Buna **iyi kalibre edilmiş model** denir.

Hava durumu benzetmesi: Bir meteorolog 100 farklı gün için "yağmur ihtimali %30" diyor. Bu günlerin yaklaşık 30'unda yağmur yağmışsa meteorolog iyi kalibre edilmiştir. 70'inde yağmışsa "%30" sözü anlamsızdır, ne kadar iyi sıralama yaparsa yapsın.

**Neden önemli?** Biz eşik koyacağız: "olasılık > 0.8 ise kabul et". Model'in 0.8'i gerçekten %80 doğruluk demiyorsa bu eşik bizi yanıltır.

**Nasıl yapılıyor?** Sınıflandırıcının ham çıktısının üstüne küçük bir "düzeltme katmanı" eklenir. Bizde **isotonic regresyon** kullanıldı: "Ham çıktı 0.6 olan fix'lerin gerçekte kaçta kaçı doğruydu?" tablosunu veriden öğrenip çıktıyı bu tabloya göre yeniden ölçekler. Sıralamayı bozmaz, sadece sayıları "dürüst" yapar.

**Nasıl ölçülüyor?**
- **Güvenilirlik diyagramı:** Yatay eksende modelin söylediği olasılık, dikey eksende gerçekleşen oran. Mükemmel kalibrasyon = köşegen çizgi. (`outputs/figures/*_reliability_diagram.png`)
- **ECE (Expected Calibration Error):** Bu diyagramın köşegenden ortalama sapması. 0'a yakın = iyi.

#### Anlam 2: Yeniden kalibrasyon (yeni bölgeye uyarlama)
Model AerialVL'de eğitildi. Başka bir ülkede, başka kamerada "0.8" yine "%80" mi demek? Genelde hayır. Ortam değişince oranlar kayar. **Yeniden kalibrasyon** şu demek: modelin kendisini (ağaçları, ağırlıkları) değiştirmeden, sadece en üstteki düzeltme katmanını ve eşikleri **yeni bölgeden biraz veriyle** yeniden ayarlamak. Az veri ister, ucuzdur. Raporlardaki "RECAL" grubu bunun için ayrılmış uçuş ve sahneler.

#### Anlam 3: Kamera/geometri düzeltmesi (benim gevşekçe "kalibrasyon" dediğim)
Kamera görüntüsünün merkezi ile drone'un tam altı arasındaki sistematik kaymayı düzelten küçük formül (`src/visloc_attitude.py`, `src/boresight.py`). Bu bir yapay zekâ kalibrasyonu değil, geometri düzeltmesi. Son mesajlarda "10 m içi oranı artırmak için eğiklik düzeltmesini yeniden uyduralım" dediğim şey bu.

### 5.4 Model iyi mi, nasıl anlıyoruz? (metrikler)

| Metrik | Ne ölçer | Basitçe |
|---|---|---|
| **AUROC** | Doğru ve yanlış fix'leri **sıralama** başarısı | Rastgele bir doğru fix ile rastgele bir yanlış fix verilse, model doğruya daha yüksek puan verir mi? 0.5 = yazı tura, 1.0 = mükemmel. |
| **AUPRC** | Benzer, ama doğru fix'lerin bulunmasına odaklı | Yüksek = iyi |
| **ECE** | Kalibrasyon hatası | Düşük = iyi (bkz. 5.3) |
| **Kapsam (coverage)** | Fix'lerin yüzde kaçını kabul ediyoruz | Yüksek = daha çok düzeltme |
| **Risk** | Kabul ettiklerimizin yüzde kaçı aslında yanlış | Düşük = daha güvenli |

**Risk–kapsam eğrisi:** Eşiği yavaşça gevşettikçe kabul oranı artar, ama yanlış kabul de artar. İyi model aynı kabul oranında daha düşük risk verir: eğrisi daha **aşağıda** kalır. Bu, projenin en önemli grafiği. (`outputs/figures/*_risk_coverage.png`)

### 5.5 Karar: kabul / zayıf kabul / ret
Model'in olasılığına iki eşik koyduk. Eşikler doğrulama (VAL) verisinde, "kabul edilenlerin en fazla %20'si yanlış olsun" kuralıyla seçildi:
- **Yüksek güven → kabul:** Fix normal ağırlıkla filtreye girer.
- **Orta güven → zayıf kabul (down-weight):** Fix'in belirsizliği 4 kat büyük varsayılır; filtre az etkilenir.
- **Düşük güven → ret:** Fix kullanılmaz, ölü hesapla devam edilir.

### 5.6 Karşılaştırdığımız rakipler (baseline'lar)
"Bizim model iyi" demek için onu daha basit yöntemlerle yarıştırdık:
- **Ham skor:** Sadece inlier oranına bak.
- **SatLoc-tarzı sezgisel:** Literatürdeki elle yazılmış bir güven formülü.
- **Chi-square testi:** Klasik yöntem. Fix, filtrenin beklediği yere istatistiksel olarak yeterince yakınsa kabul et.

---

## 6. Parça 4: Kaybolunca ne olur? (REACQUIRE modu)

Büyük bir drift (ör. ani 300 m sıçrama) olduğunda tuhaf bir tuzak var:
- Filtre kendini yanlış yerde sanıyor ama bundan habersiz.
- Kamera **doğru** konumu buluyor.
- Ama doğru konum, filtrenin beklediğinden çok uzakta. Mahalanobis ve chi-square kontrolleri doğru fix'i "tutarsız" diye **reddediyor**.
- Sonuç: Drone sonsuza kadar yanlış yerde kalıyor.

**Çözüm (REACQUIRE):**
1. Arka arkaya 3 fix reddedilirse "galiba kayboldum" moduna geç.
2. Arama penceresini en büyüğe (400 m) aç.
3. Mahalanobis kontrolünü geçici olarak askıya al; sadece görüntü kalitesine bakan modeli kullan.
4. **Ama tek bir iyi görünen fix'e güvenme.** İki ayrı fix'in birbiriyle tutarlı olmasını bekle (**2-fix teyidi**). İkisi arasındaki farkın, o sürede drone'un kat ettiği yolla uyumlu olması gerekiyor (25 m tolerans).

**Sonuç (AerialVL TEST):** 2-fix teyidiyle 12 denemenin 12'sinde 18–21 saniyede kurtardı, **hiç yanlış kabul yapmadı**. Teyitsiz sürüm de kurtardı ama 15 kez yanlış konuma atladı. Yani asıl koruma teyit adımından geliyor.

---

## 7. Deneyleri nasıl yaptık? (dürüstlük kuralları)

### 7.1 Veriyi üçe bölmek: TRAIN / VAL / TEST
- **TRAIN (eğitim):** Model burada öğrenir.
- **VAL (doğrulama):** Ayarlar ve eşikler burada seçilir.
- **TEST:** Hiçbir şey ayarlanmaz. En sonda **bir kez** bakılır.

Neden? Öğrenciye sınavdan önce soruları gösterirsen, aldığı not gerçek bilgisini göstermez. TEST verisine bakıp bir şey ayarlarsak sonuç şişer ve gerçek dünyada tutmaz. Bölme uçuş bazında yapıldı: aynı uçuşun kareleri hem eğitimde hem testte olamaz, çünkü ardışık kareler neredeyse aynıdır.

### 7.2 Config freeze (dondurma)
TEST'e geçmeden önce kodun ve ayarların tamamının parmak izini (SHA-256) aldık (`outputs/config_freeze.json`). TEST'ten sonra tekrar kontrol ettik: hiçbir şey değişmemiş. Bu, "test sonucunu görüp kodu değiştirdin mi?" sorusuna kanıtlı cevap.

### 7.3 Simülatör: Gazebo değil, "veri seti tekrar oynatma"
Gerçek drone uçurmuyoruz, Gazebo da kullanmıyoruz. Python'da yazılmış bir simülatör var:
- Gerçek uçuş kayıtlarındaki görüntüler ve gerçek konumlar sırayla oynatılıyor.
- Üstüne yapay drift ekleniyor.
- Her 5/10/20/40 saniyede bir lokalizer çağrılıyor.
- Filtre ve karar politikası çalıştırılıyor; sonunda konum hatası (RMSE) ölçülüyor.

Görüntüler gerçek, drift simüle. Bu, gerçek kamera görüntüsünün zorluğunu korurken binlerce senaryoyu ucuza denememizi sağlıyor.

### 7.4 Karşılaştırılan politikalar (E1–E10)

| Kod | Politika | Açıklama |
|---|---|---|
| E1 | Sadece drift | Hiç düzeltme yok (en kötü referans) |
| E2 | Hepsini kabul et | Her fix'e güven |
| E3 | Ham skor eşiği | Inlier oranı yüksekse kabul |
| E4 | SatLoc-tarzı | Elle yazılmış güven formülü |
| E5 | Chi-square | Klasik istatistik kapısı |
| E6 | Kalibre, sadece görüntü | Bizim model, Mahalanobis'siz |
| **E7** | **Kalibre, görüntü + Mahalanobis** | **Bizim ana model** |
| E8 | E7 + chi-square | İkisi birden |
| E9 | Rastgele | Şans referansı |
| E10 | Kâhin | Gerçek etiketi bilen hile modeli (karşılaştırma için) |

**E11:** REACQUIRE deneyi (bölüm 6).

---

## 8. Veri setleri

| Veri seti | Ne | Bizdeki rolü |
|---|---|---|
| **AerialVL** | Tek bölge, 11 uçuş, aşağı bakan kamera | **Ana veri.** Model burada eğitildi, eşikler burada seçildi, TEST burada yapıldı. |
| **UAV-VisLoc** | Çin'in 8 bölgesi, 11 uçuş, 400–2500 m irtifa | **Transfer testi:** model hiç görmediği bölgede çalışıyor mu? |
| **AnyVisLoc** | 24 sahne, düşük irtifa (150–340 m), **eğik** kamera, farklı kameralar | **Transfer testi.** |

**Transfer (cross-dataset) testi** şu demek: AerialVL'de eğitilip dondurulan sistemi, hiç değiştirmeden başka bir veri setinde çalıştırıyoruz. Üç şekilde baktık:
- **A) Dondurulmuş:** Hiçbir şeye dokunma.
- **B) Yeniden kalibre (anlam 2):** Sadece en üst düzeltme katmanını ve eşikleri yeni bölgenin RECAL uçuş/sahnelerinde ayarla, sonra TEST uçuş/sahnelerinde ölç.
- **C) Yeniden eğitim (referans):** Modeli yeni bölgenin RECAL verisinde baştan eğit. Bu bir "üst sınır" fikri versin diye.

---

## 9. Sonuçlar: ne öğrendik?

### 9.1 AerialVL (ana deney): başarılı
- **Lokalizer:** Test uçuşlarında median hata 8.7 m; karelerin %57'si 10 m içinde.
- **Güvenilirlik modeli:** AUROC **0.887**. Ham skor 0.783, SatLoc 0.760, chi-square 0.608.
- **Risk sözü tuttu mu?** VAL'de "%20 risk" için seçilen eşik TEST'te fix'lerin %37'sini **%17 riskle** kabul etti: söz tutuldu. Ham skor aynı yöntemle sadece %6'sını kabul etti ve riski %34 çıktı: söz tutulmadı.
- **Navigasyon (filtre doğruyken):** En düşük hata bizim modelde (E7, median 19 m). Hiç düzeltme yapmamak 84 m.
- **Uyarı (filtre kendine fazla güvenirken):** Mahalanobis kullanan bütün yöntemler (bizimki dahil) doğru fix'leri reddedip çöktü. PDF bunu önceden hipotez olarak yazmıştı (H4/H5) ve doğrulandı. Çaresi REACQUIRE.
- **REACQUIRE + 2-fix teyidi:** 12/12 kurtarma, 0 yanlış kabul.

### 9.2 AnyVisLoc (transfer): başarılı
- **Lokalizer:** Test sahnelerinde median 4.7 m; %66'sı 10 m içinde. AerialVL'den bile iyi.
- **Güvenilirlik modeli, hiç dokunulmadan:** AUROC **0.929**. Başka ülke, başka şehir, başka kamera, ve eğitildiği yerden bile iyi ayırt ediyor.
- **Dondurulmuş eşik:** Kabul edilenlerin sadece %2.2'si yanlış, ama fix'lerin yalnızca %21'i kabul ediliyor. Güvenli ama aşırı temkinli.
- **Yeniden kalibre edilince:** Kabul %77'ye çıkıyor, risk %24 (hedef %20'nin biraz üstü).
- *Not:* İlk denemede tamamen başarısızdı. Sebep veri değil, benim kamera açılarını yanlış okumamdı. Veri setinin resmi kodunu inceleyince düzeldi.

### 9.3 UAV-VisLoc (transfer): başarısız, ama sebebi anlaşıldı
- **Lokalizer çöktü:** Sadece %13'ü 10 m içinde.
- Lokalizer çökünce güvenilirlik modelinin yapabileceği tek şey "reddet" demek. Bunu doğru yapıyor (kabul ettikleri %17 riskli), ama neredeyse hiçbir şey kabul etmediği için navigasyona katkısı yok.
- **Çöküşün sebepleri:**
  - Harita ile uçuş arasında **yıl/mevsim farkı**. Bir uçuşta drone yeşil görürken harita kahverengi.
  - **Nehir ve su üstü** kareler: eşleşecek bir şey yok.
  - **Ormanlık, dağlık arazi**: dokular birbirine benziyor, yükseklik farkı görüntüyü bozuyor.
  - Bazı yerlerde arada **yeni yapılaşma**.

### 9.4 Ana ders
> **Güvenilirlik modeli farklı bölgelere taşınıyor. Ama (1) eşiklerin o bölgede yeniden ayarlanması gerekiyor, ve (2) sistemin işe yaraması, kamera-harita eşleştirmesinin o bölgede çalışmasına bağlı.**

UAV-VisLoc ile AnyVisLoc arasındaki fark bunu net gösteriyor. Model aynı; eşleştirme çalışınca model de çalışıyor.

---

## 10. Şu an ne yapıyoruz? (2026-10-03 öğleden sonra)

### 10.1 UAV-VisLoc'u kurtarma denemesi: daha uygun haritalar
Hipotez: Uçuş tarihine yakın çekilmiş bir harita eşleşmeyi iyileştirir.
- **Esri Wayback:** Ücretsiz arşiv, 2014'ten beri sürümler. Ama 2018–2019 uçuşları için o yıllara ait çekim yok.
- **Google Earth geçmiş görüntüleri:** Uçuşlara günler veya haftalar mesafede çekimler var. Açık kaynaklı bir araçla indirildi. (Akademik ödev kapsamında kullanılıyor; Google'ın koşulları ticari ve otonom kullanımı yasaklıyor.)
- İki araştırma ajanı ayrı ayrı aynı tarihleri buldu: `UAV_VISLOC_HARITA_BULGULAR.md`, `/media/davut/disk2/dataset/uav_visloc_map_research/README.md`.

**Harita seçim kuralları** (test uçuşlarına bakmadan sabitlendi):
- **K1 (gerçekçi):** Her karede "veri setinin haritası" ve "Google'ın uçuştan **önceki** en yakın çekimi" ile eşleştir. En çok inlier vereni seç. Gerçek konum kullanılmıyor, sahada da yapılabilir.
- **K2 (geriye dönük):** Uçuştan **sonraki** çekimler de dahil. "En iyi ihtimalle ne olurdu" sorusu için.

**İlk sonuç (K1, test uçuşları, prior hatası 0/30 m):**

| | 10 m içi | 25 m içi | 100 m+ / bulunamadı |
|---|---|---|---|
| Veri setinin haritası | %13 | %45 | %25 |
| K1 | %14 | %52 | %19 |

Kaba eşleşme iyileşti; uçuş 08'de 25 m içi oran %35'ten %58'e çıktı. Ama 10 m içi oran neredeyse aynı kaldı. Bu, eşleşmenin bulunduğunu ama 10–25 m'lik **sistematik bir kayma** kaldığını düşündürüyor. Muhtemel sebep kamera/eğiklik düzeltmesi (5.3, anlam 3).

**Arka planda çalışan:** K1'in RECAL uçuşları, ardından K2'nin TEST ve RECAL uçuşları (toplam ~4–5 saat). Bellek sınırı yüzünden işler tek tek çalışıyor.

### 10.1b Sonuçlar (akşam güncellemesi; ayrıntı `FINAL_RAPOR.md` §13)
- **Yeni haritalar:** K2 ile 25 m içi oran %45'ten %58'e çıktı, ama 10 m içi oran ~%15'te kaldı. Kalan hata sistematik değil, rastgele (±10–13 m). 400–550 m yükseklikte 1° açı hatası yerde ~9 m ediyor. Yani bu platformda 10 m hedefi fiziksel olarak zor.
- **Karışık eğitim** (AerialVL + AnyVisLoc + UAV-VisLoc):
  - Model **her veri setinde daha iyi ayırt ediyor** (AUROC: 0.887 → 0.899, 0.929 → 0.964, 0.795 → 0.881).
  - Olasılıkları **çok daha dürüst** (kalibrasyon hatası 3–13 kat düştü).
  - **Hiç görmediği** veri setinde bile, sadece AerialVL ile eğitilen modelden genelde daha iyi.
  - **Ama:** Tek bir ortak eşik her bölgede risk sözünü tutamıyor. Her bölgeye o bölgenin küçük verisiyle kendi eşiğini vermek gerekiyor.

### 10.2 Sırada ne var?
1. **Eğiklik/kamera düzeltmesini yeni haritalarla RECAL uçuşlarında yeniden uydurmak**, sonra TEST'te bir kez ölçmek. Hedef: 10 m içi oranı yükseltmek.
2. **Güvenilirlik modelini üç veri setinin karışımıyla eğitmek:** AerialVL + AnyVisLoc RECAL + UAV-VisLoc RECAL. Sonra görmediği TEST sahnelerinde ölçmek. Amaç: eşiklerin bölgeden bölgeye daha az kayması.
3. **Jetson Orin'de hız ölçümü (M11):** Donanım gelince.
4. AnyVisLoc'ta kapalı-döngü simülasyon: zaman bilgisi olmadığı için şimdilik yapılamadı.

---

## 11. Sözlük

| Terim | Anlamı |
|---|---|
| **Fix** | Kamera-harita eşleştirmesinden bulunan konum |
| **Prior** | Filtrenin, fix gelmeden önceki tahmini konumu |
| **Drift** | Ölü hesaptaki birikmiş hata |
| **Kovaryans / belirsizlik** | Filtrenin "ne kadar yanılıyor olabilirim" ölçüsü |
| **Mahalanobis mesafesi** | Fix'in prior'dan uzaklığı, belirsizlik cinsinden ("kaç sigma uzakta") |
| **Chi-square kapısı** | Mahalanobis mesafesi istatistiksel sınırı aşarsa fix'i reddeden klasik yöntem |
| **Inlier** | RANSAC'ın bulduğu dönüşüme uyan, doğru sayılan eşleşme |
| **SuperPoint / LightGlue** | Hazır görüntü eşleştirme yapay zekâ modelleri (nokta bul / eşleştir) |
| **RANSAC** | Yanlış eşleşmeleri ayıklayan rastgele deneme yöntemi |
| **Kalibrasyon** | Model "%80" dediğinde gerçekten %80 doğru çıkması (bkz. 5.3) |
| **Isotonic regresyon** | Model çıktısını gerçek oranlara göre yeniden ölçekleyen düzeltme katmanı |
| **AUROC** | Doğru/yanlış ayırt etme gücü; 0.5 şans, 1.0 mükemmel |
| **ECE** | Kalibrasyon hatası; düşük iyi |
| **Kapsam / risk** | Kabul oranı / kabul edilenlerdeki yanlış oranı |
| **Açık-döngü** | Filtresiz; sadece "bu koşulda lokalizer ne yaptı" kaydı |
| **Kapalı-döngü** | Filtre + karar politikası + drift'in birlikte çalıştığı simülasyon |
| **RMSE** | Uçuş boyunca ortalama konum hatası (büyük hatalara daha çok ceza verir) |
| **TRAIN / VAL / TEST** | Eğitim / ayar / son sınav verisi |
| **RECAL** | Yeni bölgede yeniden kalibrasyon için ayrılmış veri |
| **TUNE** | Yeni veri setine teknik uyum (eksen yönü, ölçek) için bakılan veri |
| **Config freeze** | Kod ve ayarların TEST öncesi dondurulup parmak izinin alınması |
| **REACQUIRE** | "Kayboldum" modu: geniş arama + 2-fix teyidi |
| **Transfer / cross-dataset** | Bir veri setinde eğitileni başka bir veri setinde değiştirmeden denemek |
| **Nadir** | Tam aşağıya bakış |
| **Wayback / Google geçmiş görüntüler** | Farklı tarihlerde çekilmiş uydu görüntüsü arşivleri |

---

## 12. Dosyalar nerede?

| Ne | Yer |
|---|---|
| Ana rapor (tüm sayılar, tablolar) | `FINAL_RAPOR.md` |
| Bu rehber | `SISTEM_REHBERI.md` |
| Lokalizer | `src/localization_pipeline.py` |
| Güvenilirlik modeli | `src/reliability_model.py` |
| Açık-döngü veri üretimi | `src/build_fix_dataset.py`, `src/visloc_build_fix_dataset.py`, `src/anyvisloc_build_fix_dataset.py` |
| Kalibrasyon değerlendirmesi | `src/eval_calibration.py`, `src/visloc_eval_calibration.py` |
| Drift simülatörü / navigasyon | `src/drift_simulator.py`, `src/run_nav_sim.py` |
| REACQUIRE | `src/run_reacquire.py` |
| Veri bölmeleri | `src/splits.py`, `src/visloc_splits.py`, `src/anyvisloc_splits.py` |
| Harita indirme / karşılaştırma | `src/wayback_fetch.py`, `src/gehi_fetch.py`, `src/wayback_compare.py` |
| Grafikler | `outputs/figures/` |
| Eğitilmiş modeller ve eşikler | `outputs/calibration_models.pkl`, `outputs/thresholds.json` |
| Veri setleri ve haritalar | `/media/davut/disk2/proje/uav_vloc_datasets/` |
| Orijinal öneri (PDF) | `/home/davut/Desktop/proje/drone/linux_drone_ws/Calibrated Reliability-Aware RGB Map Relocalization for GPS-GNSS-Denied UAV Navigation.pdf` |
