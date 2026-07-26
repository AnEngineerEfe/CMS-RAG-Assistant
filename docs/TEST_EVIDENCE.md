# Test Kaniti

Tekrar calistirilabilir test komutu:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kapsanan davranislar:

- Ayni PDF iceriginin ikinci kez saklanmamasi.
- Depodaki dosyanin arayuzde hash olmadan gosterilmesi.
- PDF parcaciklarinda belge ve sayfa bilgisinin korunmasi.
- Belge yuklenmeden soru soruldugunda guvenli yonlendirme verilmesi.
- Kisa takip sorusunun onceki soruyu retrieval sorgusuna katmasi.

## Son Calistirma Sonucu

2026-07-26 tarihinde yerel ortamda `7/7` otomatik test basarili oldu.
Yuklenmis ADVENT brosuruyle iki turlu kontrol de yapildi:

1. `ADVENT nedir?` yaniti brosurun 3. sayfasini kaynak olarak verdi.
2. `Ornekleri var mi?` takip sorusu ADVENT MARTI, ADVENT UFUK ve ADVENT
   MUREN varyantlarini 4, 22, 26 ve 28. sayfalardan kaynaklayarak verdi.
