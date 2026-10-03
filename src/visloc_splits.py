"""UAV-VisLoc ayrimi -- ucus-bazli sonuclara BAKMADAN ONCE sabitlendi
(2026-10-03). Kural: en kucuk iki ucus (07 haric; 30 kare) ayar/kalibrasyon
icin, gerisi degerlendirme icin. Platform ayarlari (yaw konvansiyonu,
footprint araligi, harita calisma cozunurlugu, kalibrasyon katmani yeniden
uydurma) SADECE TUNE ucuslarinda yapilir."""
TUNE_FLIGHTS = ("05", "10")
EVAL_FLIGHTS = ("01", "02", "03", "04", "06", "08", "09", "11")

# E12 kalibrasyon transferi: EVAL ucuslari sahne-ayrik ikiye bolunur
# (sonuclara BAKMADAN, ucus numarasina gore alternatif). RECAL'de sadece
# kalibrasyon katmani yeniden uydurulur; TEST'te raporlanir.
RECAL_FLIGHTS = ("01", "03", "06", "09")
TEST_FLIGHTS = ("02", "04", "08", "11")
