"""Sequence-bazli sabit train/val/test ayrimi (proje onerisi SS9.1).

2026-10-01'de, M2 parametre ayarlamasina BASLAMADAN ONCE sabitlendi.
Kural: tum ayarlama (M2 parametreleri, kalibrasyon modeli, gate esikleri,
R_nominal, REACQUIRE parametreleri) SADECE TRAIN ve VAL sekanslarinda
yapilir. TEST sekanslari configuration freeze'e kadar hicbir ayar
dongusunde kullanilmaz.

Dürüstlük notu: 2026-09-30 gecesi (donme hatasi bulunmadan, eslestirme
bozukken) tum 11 sekans tanilama amacli calistirildi. O sonuclar bu
ayrim icin kullanilmadi ve artik gecersiz (eslestirme o zaman calismiyordu).

Not: tum sekanslar ayni bolgenin uzerinde uctugu icin ayrim zamansal,
mekansal degil -- ayni harita bolgeleri train ve test'te gorunebilir.
"""

TRAIN_SEQUENCES = (
    "2023-03-16-18-04-01",  # long
    "2023-03-18-12-18-25",  # long
    "2023-03-18-12-47-05",  # long
    "2023-03-11-11-48-35",  # short
    "2023-03-16-16-58-43",  # short
    "2023-03-18-16-30-27",  # short
)
VAL_SEQUENCES = (
    "2023-03-18-15-01-14",  # long
    "2023-03-18-16-43-16",  # short
)
TEST_SEQUENCES = (
    "2023-03-18-14-38-32",  # long
    "2023-03-18-15-40-18",  # long
    "2023-03-18-16-55-37",  # short
)

assert not (set(TRAIN_SEQUENCES) & set(VAL_SEQUENCES))
assert not (set(TRAIN_SEQUENCES) & set(TEST_SEQUENCES))
assert not (set(VAL_SEQUENCES) & set(TEST_SEQUENCES))
assert len(TRAIN_SEQUENCES) + len(VAL_SEQUENCES) + len(TEST_SEQUENCES) == 11
