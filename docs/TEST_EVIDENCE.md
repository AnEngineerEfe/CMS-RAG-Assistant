# Test ve Kabul Kanıtı

Bu belge yalnızca tekrar çalıştırılabilir otomasyon sonuçlarını kaydeder.

## Komutlar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval
.\.venv\Scripts\python.exe -m scripts.evaluate_answers
.\.venv\Scripts\python.exe -m scripts.run_benchmark
.\scripts\run_pgvector_lineage_suite.ps1
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
- Sohbet geçmişinin kaynak kapsamları arasında izole edilmesi
- Kişisel/sohbet sorularına kaynak uydurmadan ret
- Resmî/açık kaynak koleksiyon filtreleri
- NATO açık-kaynak cevabında ürün ilişkisi uydurulmaması
- Aynı sayfadaki tamamlayıcı kanıtların birleştirilmesi
- Kaynakların her asistan mesajında korunması
- Streamlit arayüzünde üç turluk gerçek kullanıcı yolculuğu
- Kaynaksız yanıtta ilgisiz kanıt kartlarının gösterilmemesi
- Ollama hata mesajında retrieval kanıtlarının gizlenmesi
- Streamlit giriş noktasının ince ve iş mantığından arındırılmış kalması
- Domain, application, infrastructure ve presentation bağımlılık yönleri
- Tüm kaynak sınıf ve fonksiyonlarının Türkçe işlev açıklaması taşıması
- Küratörlü PDF'lerin metin çıkarımı ve açık veri sınırı taşıması
- Manifestin beş kamuya açık kaynak ve kapalı çalışma-anı web erişimi bildirmesi
- Snapshot chunk/embedding sayılarının bire bir eşleşmesi
- Hazır resmî broşürün ek belge yönetiminden silinememesi
- Motorun belge embeddinglerini yeniden üretmeden snapshot yüklemesi

- Altın veri setindeki belge, sayfa ve kanıt terimlerinin snapshot'ta bulunması
- TP/TN/FP/FN, Hit@6, MRR ve retrieval gecikmesinin gerçek üretim hattında ölçülmesi
- Reranker'ın kısa fakat tam terim eşleşmeli kanıt sayfalarını düşürmemesi
- Kaynakta bulunmayan teknik nitelikler ve gizli yapılandırma taleplerinin reddi

## Retrieval kabul seti

`scripts/evaluate_retrieval` sekiz sabit davranışı ölçer:

1. ADVENT'in su üstü platform rolü için resmî kaynak ve beklenen sayfa
2. İz yönetimi sorgusu için ilgili CMS terimleri
3. Taktik veri bağı sorgusunda Link 11 ve Link 16'nın birlikte korunması
4. NATO birlikte çalışabilirlik sorgusunun `open_source` koleksiyonundan gelmesi
5. ADVENT-AI operatör desteği
6. MAIN bakım destek asistanı
7. NATO sorumlu yapay zekâ ilkeleri
8. ADVENT ROTA görevleri

Her vaka; beklenen koleksiyon, belge/sayfa ve anahtar terimleri denetler.
Sonuç `docs/retrieval_evaluation_report.json` dosyasına yazılır.

## Gerçek yanıt kabul seti

`scripts.evaluate_answers`, uygulamanın kullanıcıya verdiği gerçek yanıtı yedi
senaryoda şu dört ölçütle kıyaslar:

1. Soru cevaplanabilir mi, yoksa güvenli ret mi verilmelidir?
2. Beklenen kavramların tamamı cevapta bulunuyor mu?
3. Cevap `[SOURCE n]` atfı taşıyor mu?
4. Gösterilen belge ve sayfa kaynakları cevap kararıyla tutarlı mı?

Set; ADVENT tanımı, iki ardışık takip sorusu, ADVENT-AI, MAIN, sorumlu yapay zekâ
ve belgede bulunmayan füze menzili sorusunu kapsar. Sonuç
`docs/answer_evaluation_report.json` dosyasına yazılır.

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

2026-08-10 tarihinde hazır bilgi tabanı ve bağımsız değerlendirme kabul turunda:

- Python kaynak derlemesi: başarılı
- Otomatik testler: `85/85` başarılı
- Retrieval kabul seti: `8/8` başarılı
- Gerçek yanıt kabul seti: `7/7` başarılı
- Altın benchmark: `45/45` başarılı (`30 TP / 15 TN / 0 FP / 0 FN`)
- Altın benchmark Hit@6: `%100`
- Altın benchmark MRR: `0,7694`
- Bağımsız chunk hakemi: `77/77` geçerli, `0` geçersiz çıktı
- 20-vaka confusion matrix: `15 TP / 4 TN / 0 FP / 1 FN`
- 20-vaka accuracy / F1: `%95,0 / %96,77`
- Exact chunk-köken katı başarı: `13/16` (`%81,25`)
- İkinci 20-vaka confusion matrix: `15 TP / 4 TN / 0 FP / 1 FN`
- İkinci 20-vaka accuracy / F1: `%95,0 / %96,77`
- İkinci exact chunk-köken katı başarı: `14/16` (`%87,5`)
- pgvector birinci 20-vaka matrisi: `15 TP / 4 TN / 0 FP / 1 FN`
- pgvector ikinci 20-vaka matrisi: `12 TP / 4 TN / 0 FP / 4 FN`
- pgvector Seri 1 / Seri 2 accuracy: `%95,0 / %80,0`
- pgvector Seri 1 / Seri 2 exact köken eşleşmesi: `13/16 / 14/16`
- FAISS–pgvector retrieval chunk listesi eşitliği: `40/40`
- Bağımsız cevap hakemi + altın kaynak kapısı: `30/30`
- FAISS / gerçek pgvector ilk-6 sıra eşitliği: `30/30`
- FAISS / pgvector exact-cosine Hit@6: `%90,0 / %90,0`
- FAISS / pgvector exact-cosine MRR: `0,7500 / 0,7500`
- FAISS / pgvector ortalama yalnız-arama: `0,352 / 0,581 ms`
- Chunk-köken cache kayıtlarının FAISS ve pgvector backend'leri arasında izole edilmesi
- Genişletilmiş hibrit retrieval MRR: `0,7694`
- Optimize ortalama retrieval gecikmesi: `1438,3 ms`
- Hazır PDF kaynağı: `5`
- İndekslenen anlamlı kanıt parçası: `77`
- Önceden hesaplanmış embedding satırı: `77`
- 80 karakter altı gürültü chunk: `0`
- Snapshot yükleme: başarılı
- Streamlit sağlık endpoint'i: `HTTP 200`
- Ollama: erişilebilir
- Varsayılan yerel üretim modeli: `qwen2.5:3b`
- İsteğe bağlı kalite modeli: `qwen2.5:7b` kurulu

Bu değerler, yukarıdaki komutların aynı çalışma alanında yeniden çalıştırılmasıyla
elde edilmiştir.
