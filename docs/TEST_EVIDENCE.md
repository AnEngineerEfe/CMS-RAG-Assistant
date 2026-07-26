# Test ve Kabul Kanıtı

Bu belge yalnızca tekrar çalıştırılabilir otomasyon sonuçlarını kaydeder.

## Komutlar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval
```

## Otomatik test kapsamı

- İçerik hash'i ile yinelenen PDF engelleme
- PDF olmayan ve bozuk PDF girdilerinin güvenli reddi
- Manifestte özgün ad ve meta veri korunması
- Belgenin dosya ve manifestten güvenli silinmesi
- PDF parçalarında belge ve sayfa bilgisinin korunması
- Markdown front matter içinden koleksiyon, otorite ve URL okunması
- Belgesiz bilgi tabanında güvenli yönlendirme
- Takip sorusunun sınırlı sohbet bağlamıyla genişletilmesi
- Kişisel/sohbet sorularına kaynak uydurmadan ret
- Resmî/açık kaynak koleksiyon filtreleri
- Aynı sayfadaki tamamlayıcı kanıtların birleştirilmesi
- Kaynakların her asistan mesajında korunması
- Streamlit arayüzünde üç turluk gerçek kullanıcı yolculuğu
- Kaynaksız yanıtta ilgisiz kanıt kartlarının gösterilmemesi

## Retrieval kabul seti

`scripts/evaluate_retrieval` dört sabit davranışı ölçer:

1. ADVENT'in su üstü platform rolü için resmî kaynak ve beklenen sayfa
2. İz yönetimi sorgusu için ilgili CMS terimleri
3. Taktik veri bağı sorgusunda Link 11 ve Link 16'nın birlikte korunması
4. NATO birlikte çalışabilirlik sorgusunun `open_source` koleksiyonundan gelmesi

Her vaka; beklenen koleksiyon, belge/sayfa ve anahtar terimleri denetler.
Sonuç `docs/retrieval_evaluation_report.json` dosyasına yazılır.

## Arayüz kabul senaryosu

Streamlit `AppTest` ile aynı oturumda şu akış otomatikleştirilmiştir:

1. `Savaş Gemisi ADVENT'te ne yapar?`
2. `Başka hangi platformlarda kullanılır?`
3. `Ben kimim?`

İlk iki yanıtın belgeli olması, ikinci sorunun bir takip sorusu olarak anlaşılması,
önceki kaynakların kaybolmaması ve üçüncü soruda kaynak uydurulmaması beklenir.

## Canlı servis kontrolü

Uygulama ayrı bir Streamlit sürecinde başlatılır ve sağlık endpoint'inin HTTP 200
döndürmesi denetlenir. Bu kontrol; import, başlangıç indeksleme ve web sunucusunun
birlikte ayağa kalkabildiğini doğrular.

## Son doğrulama

2026-07-26 tarihinde temiz kabul turunda:

- Python kaynak derlemesi: başarılı
- Otomatik testler: `26/26` başarılı
- Retrieval kabul seti: `4/4` başarılı
- İndekslenen kanıt parçası: `57`
- Streamlit sağlık endpoint'i: `HTTP 200`
- Ollama: erişilebilir
- Varsayılan yerel üretim modeli: `qwen2.5:3b`
- İsteğe bağlı kalite modeli: `qwen2.5:7b` kurulu

Bu değerler, yukarıdaki komutların aynı çalışma alanında yeniden çalıştırılmasıyla
elde edilmiştir.
