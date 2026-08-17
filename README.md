# CMS-RAG Assistant

Yerel çalışan, kaynak gösteren ve koleksiyon ayrımı uygulayan Combat Management
System (CMS) doküman asistanı.

Sistem; geliştirme/kurasyon aşamasında araştırılmış kamuya açık kaynakları PDF
bilgi paketlerine dönüştürür ve belge embeddinglerini önceden hesaplar. Normal
çalışma sırasında internet araştırması yapmaz: hazır yerel snapshot üzerinden
FAISS semantik arama, BM25, Reciprocal Rank Fusion ve cross-encoder reranking
uygular; seçilen kanıtları yerel Ollama modeline verir.

## Çalışma modeli

```text
GELİŞTİRME / KÜRASYON (internet yalnız burada)
Birincil kamu kaynakları → küratörlü metin → PDF → chunk → embedding snapshot

NORMAL KULLANIM (çevrimdışı)
Kullanıcı sorusu → hazır snapshot → hibrit arama → yerel Ollama → kaynaklı cevap
```

Model PDF'leri “ezberlemez”; RAG tasarımında doğrulanmış bilgi önceden
parçalanıp indekslenir, soru geldiğinde yalnız ilgili parçalar modele bağlam
olarak verilir. Böylece kaynak güncellenebilir, cevap izlenebilir ve çalışma
anında web taraması gerekmez.

## Özellikler

- SHA-256 tabanlı dosya kimliği ve aynı PDF'in tekrar yüklenmesini engelleme
- PDF imzası, boyut ve bozuk dosya kontrolleri
- Belge/sayfa/koleksiyon/otorite/URL meta verisini koruyan parçalama
- `Resmî`, `Açık kaynak` ve `Birleşik` sorgu kapsamları
- Hibrit arama: semantic FAISS + BM25 + RRF + reranking
- Türkçe CMS terimleri için kontrollü sorgu genişletme
- Üç turluk kontrollü sohbet bağlamı
- Ollama üzerinden yerel ve akışlı yanıt üretimi
- Her mesajla kalıcı kanıt kartları ve kaynak sayfası
- Kanıt kartından ilgili yerel PDF sayfasının görsel önizlemesi ve güvenli indirme
- Her tamamlanan soru için input, output, kullanılan model/motor, chunk doğruluğu ve
  TP/TN/FP/FN etiketini otomatik kaydeden canlı değerlendirme merkezi
- Canlı sayaçlardan ayrı tutulan altın set, LLM hakemi ve FAISS/pgvector referans raporları
- Ham soru/cevap saklamayan SHA-256 özetli yerel audit ve işletim görünürlüğü
- Beş PDF kaynağı ve gürültüden arındırılmış 77 chunk içeren sürümlenmiş snapshot
- Normal kullanımda belge embeddinglerini yeniden hesaplamayan hızlı açılış
- Çalışma anında kapalı web erişimi ve yalnız yerel üretim
- Belge silme, yeniden indeksleme ve güvenli boş-bilgi-tabani davranışı
- Aynı sohbetten canlı Swing iz durumu okuma ve açık kullanıcı onaylı MCP güncellemesi
- MCP yazma kilidi, atomik işlem, geri-okuma doğrulaması ve metinsiz yerel audit
- Geçerli komut alt kümeleri için ayrı onay, gemi tipi yazım önerisi ve yön esas-açı dönüşümü
- Gemi tipi önerilerinde konuşma bağlamlı evet/hayır takibi ve kısa tip komutları

## Gereksinimler

- Python 3.11 veya üzeri
- Ollama
- MCP iz kontrolü için Java 21 JDK
- En az 8 GB RAM
- Yalnız ilk geliştirici hazırlığında model ağırlıklarını kurmak için internet;
  normal soru-cevap çalışmasında internet gerekmez

## Kurulum

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:3b
```

Bir terminalde Ollama'yı, ikinci terminalde uygulamayı çalıştırın:

```powershell
ollama serve
```

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

MCP Swing entegrasyonu da kullanılacaksa Java modülünü temiz kurulumda bir kez
derleyin veya tüm yerel başlangıç kontrollerini yapan yardımcı komutu kullanın:

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
cd ..
.\scripts\run_local.ps1
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.
Embedding/reranker ağırlıkları yerelde bulunur ve uygulama varsayılan olarak
çevrimdışı modda açılır. Çalışma sırasında web kaynağı indirilmez.

Varsayılan `qwen2.5:3b`, CPU tabanlı makinelerde etkileşimli kullanım için
seçilmiştir. Daha güçlü donanımda 7B kalite modu kullanılabilir:

```powershell
ollama pull qwen2.5:7b
$env:CMS_RAG_MODEL="qwen2.5:7b"
streamlit run app.py
```

## Kullanım

1. Uygulamayı açın; beş belgeli hazır bilgi tabanı otomatik yüklenir.
2. Sorgu kapsamını `Birleşik`, `Yalnızca resmî` veya `Yalnızca açık kaynak`
   olarak seçin.
3. ADVENT/CMS veya kamuya açıklanmış AI entegrasyonu hakkında sorunuzu yazın.
4. Yanıtın altındaki kanıt paketinden belgeyi, sayfayı, otoriteyi ve varsa
   kaynak URL'sini denetleyin.
5. `Sayfa … · PDF önizle` ile kullanılan sayfanın görüntüsünü doğrudan açın.
6. Sol paneldeki `Değerlendirme merkezi` üzerinden o andan itibaren otomatik biriken
   canlı test tablosunu, confusion matrix'i ve sürümlü referans raporlarını inceleyin.
7. Canlı tabloyu gerektiğinde UTF-8 CSV olarak indirin veya yalnız bu deney kayıtlarını
   `Canlı kayıtları sıfırla` düğmesiyle temizleyin.
8. `İz durumunu göster` ile canlı Swing değerlerini okuyun. Değişiklik için örneğin
   `Hızı 24,5 knot yap` yazın ve gösterilen işlem planını ayrıca onaylayın.

Ek PDF zorunlu değildir. Gerektiğinde `İsteğe bağlı ek belge` alanından yalnızca
kamuya açık veya kullanım yetkiniz bulunan PDF eklenebilir. Aynı içerik ikinci
kez saklanmaz. Çekirdek bilgi tabanı arayüzden silinemez.

## Bilgi tabanını hazırlama

Kaynak araştırması güncellendiğinde geliştirici araçlarını kurup tek komut
çalıştırın:

```powershell
python -m pip install -r requirements-tools.txt
.\.venv\Scripts\python.exe -m scripts.build_knowledge_base
```

Komut dört küratörlü PDF'yi, `manifest.json` dosyasını ve belge embedding
snapshot'ını yeniden üretir. Normal kullanıcı bu komutu çalıştırmaz.

## Mimari

```text
Önceden küratörlenmiş PDF bilgi paketi
  -> geliştirme aşamasında sayfa bazlı parçalama ve embedding
  -> sürümlenmiş yerel snapshot
  -> normal kullanımda snapshot yükleme
  -> semantic FAISS + BM25
  -> Reciprocal Rank Fusion
  -> cross-encoder reranking
  -> koleksiyon filtresi ve kanıt birleştirme
  -> kaynaklı hızlı yanıt veya yerel Ollama akışı
  -> kalıcı sohbet ve kanıt kartları
```

Katmanlı proje yapısı:

```text
app.py                         İnce Streamlit giriş noktası
src/cms_rag/
  domain/                      Veri modelleri ve saf iş kuralları
  application/                 RAG kullanım senaryosu orkestrasyonu
  infrastructure/              PDF, manifest, FAISS, BM25 ve reranker
  presentation/                Sohbet, PDF önizleme ve değerlendirme paneli
data/
  documents/                   İçerik adresli PDF deposu
  knowledge_base/
    sources/                   Önceden hazırlanmış kamuya açık PDF paketi
    snapshot/                  Chunk meta verisi ve hazır embedding matrisi
  references/official/         Doğrulanmış üretici kaynakları
  references/open_source/      Doğrulanmış açık/kamu kaynakları
knowledge_base/content/        PDF üretiminde kullanılan küratörlü kaynak metinleri
scripts/                       Tekrarlanabilir değerlendirme araçları
tests/                         Birim, UI ve mimari sınır testleri
docs/                          Mimari, Git akışı ve kabul kanıtları
```

Bağımlılık yönü `presentation → application → domain` biçimindedir.
`infrastructure`, alan modellerini uygular; `domain` hiçbir üst katmana bağımlı
değildir. Mimari testler bu sınırı ve kaynak sınıf/fonksiyonlarının açıklama
taşımasını otomatik olarak korur.

Ayrıntılı tasarım için [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), dal ve
sürüm politikası için [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md), test
kanıtları için [docs/TEST_EVIDENCE.md](docs/TEST_EVIDENCE.md) dosyasına bakın.

Bilgi kapsamı [docs/COVERAGE_MATRIX.md](docs/COVERAGE_MATRIX.md), 45 vakalık
bilimsel kabul hattı ise
[docs/BENCHMARK_METHODOLOGY.md](docs/BENCHMARK_METHODOLOGY.md) içinde
açıklanmıştır.
Bağımsız LLM hakemi, chunk boyutu, retrieval bileşenleri ve gerçek pgvector
karşılaştırması [docs/ADVANCED_EVALUATION.md](docs/ADVANCED_EVALUATION.md)
belgesinde raporlanır.

## Nihai sunum teslimatları

- [Nihai Teknik Dokümantasyon](deliverables/CMS-RAG_Nihai_Teknik_Dokumantasyon.docx)
- [Nihai Proje Sunumu](deliverables/CMS-RAG_Nihai_Proje_Sunumu.pptx)
- [Teslimat kullanım rehberi](deliverables/README.md)

Her iki Office dosyası aşağıdaki komutla aynı proje verilerinden yeniden
üretilebilir ve yapısal olarak doğrulanabilir:

```powershell
.\.venv\Scripts\python.exe scripts\generate_final_deliverables.py
```

## Test ve kabul

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval
.\.venv\Scripts\python.exe -m scripts.run_benchmark
.\.venv\Scripts\python.exe -m scripts.run_quality_evaluation
.\.venv\Scripts\python.exe -m scripts.run_chunk_lineage_evaluation
.\.venv\Scripts\python.exe -m scripts.run_chunk_lineage_evaluation `
  --dataset evaluation\datasets\chunk_lineage_20_round2.json `
  --output evaluation\results\lineage-round2
.\.venv\Scripts\python.exe -m scripts.run_pgvector_benchmark
.\scripts\run_pgvector_lineage_suite.ps1
```

Pgvector komutu, yerel `cms_rag_eval` veritabanındaki pgvector ile FAISS'i aynı
embedding ve sorular üzerinde kıyaslar. PostgreSQL parolası terminalde gizli
olarak istenir ve hiçbir proje dosyasına kaydedilmez.

Son komut, mevcut iki bağımsız 20-vaka veri setini değiştirmeden bu kez yoğun
arama katmanında gerçek PostgreSQL pgvector kullanır. BM25, RRF, reranker, küçük
RAG modeli ve büyük chunk hakemi sabit tutulur. Böylece FAISS ile pgvector
arasındaki karşılaştırmada değişen tek deneysel bileşen yoğun vektör backend'idir.
Parola yalnız çalışan PowerShell sürecinin ortamında tutulur ve iki seri sonunda
temizlenir.

İkinci komut, sabit kabul sorularının beklenen sayfa/koleksiyon/terimleri getirip
getirmediğini denetler ve raporu `docs/retrieval_evaluation_report.json`
dosyasına yazar.

Üçüncü komut; 23 pozitif ve 10 negatif altın vakada TP/TN/FP/FN,
precision/recall/specificity/F1, Hit@6, MRR ve gecikme metriklerini üretir.
Ayrıntılı rapor `evaluation/results/latest/benchmark_report.json` dosyasındadır.

İki chunk-köken komutu, birbirinden ve kendi içinde farklı 16'şar pozitif kaynak
chunk'ı ile 4'er kaynak-dışı negatif kontrolü çalıştırır. Sorular Codex büyük
modelle geliştirme zamanında hazırlanıp sürümlenmiş,
cevaplar yerel `qwen2.5:3b` ile üretilmiş ve retrieval adayları ayrı bir
`qwen2.5:7b` oturumunda değerlendirilmiştir.

### Seri 1 · L01–L20 confusion matrix

| Gerçek \ Tahmin | Pozitif | Negatif |
|---|---:|---:|
| Pozitif · bilgi mevcut | **TP 15** | **FN 1** |
| Negatif · bilgi mevcut değil | **FP 0** | **TN 4** |

Accuracy `%95,0`, precision `%100`, recall `%93,75`, specificity `%100` ve F1
`%96,77` olmuştur. Exact başlangıç-chunk ve bağımsız hakem eşleşmesi `13/16`
(`%81,25`) düzeyindedir. Ayrıntılı, vaka bazlı JSON/CSV ve matris özeti
`evaluation/results/lineage-latest/` altında sürümlenir.

### Seri 2 · N01–N20 confusion matrix

| Gerçek \ Tahmin | Pozitif | Negatif |
|---|---:|---:|
| Pozitif · bilgi mevcut | **TP 15** | **FN 1** |
| Negatif · bilgi mevcut değil | **FP 0** | **TN 4** |

İkinci bağımsız seride de accuracy `%95,0`, precision `%100`, recall `%93,75`,
specificity `%100` ve F1 `%96,77` olmuştur. Exact başlangıç-chunk ve bağımsız
hakem eşleşmesi `14/16` (`%87,5`) düzeyindedir. İkinci serinin ayrıntılı JSON,
CSV, cache ve matris özeti `evaluation/results/lineage-round2/` altında tutulur.
İki seri birlikte `40` vaka, `32` farklı pozitif kaynak chunk'ı ve `8` farklı
negatif kontrol içerir; matrisler birbirine eklenmeden ayrı raporlanır.

### pgvector · Seri 1 · L01–L20 confusion matrix

| Gerçek \ Tahmin | Pozitif | Negatif |
|---|---:|---:|
| Pozitif · bilgi mevcut | **TP 15** | **FN 1** |
| Negatif · bilgi mevcut değil | **FP 0** | **TN 4** |

Accuracy `%95,0`, precision `%100`, recall `%93,75`, specificity `%100` ve F1
`%96,77` ölçülmüştür. Exact başlangıç-chunk/hakem eşleşmesi `13/16` (`%81,25`),
geçersiz vaka sayısı `0` olmuştur. Ayrıntılı tablo ve kanıtlar
`evaluation/results/pgvector-lineage-latest/` altındadır.

### pgvector · Seri 2 · N01–N20 confusion matrix

| Gerçek \ Tahmin | Pozitif | Negatif |
|---|---:|---:|
| Pozitif · bilgi mevcut | **TP 12** | **FN 4** |
| Negatif · bilgi mevcut değil | **FP 0** | **TN 4** |

Accuracy `%80,0`, precision `%100`, recall `%75,0`, specificity `%100` ve F1
`%85,71` ölçülmüştür. Exact başlangıç-chunk/hakem eşleşmesi `14/16` (`%87,5`),
katı uçtan uca başarı `11/16` ve geçersiz vaka sayısı `0` olmuştur. Ayrıntılı
çıktılar `evaluation/results/pgvector-lineage-round2/` altındadır.

Her iki pgvector serisinde de retrieval chunk listesi karşılık gelen FAISS
serisiyle `20/20` aynı kalmıştır. Seri 1'in matris hücreleri de `20/20` aynıyken,
Seri 2'de `17/20` hücre aynı kalmış; N02, N07 ve N10 cevapları katı beklenen-terim
kapsamasını tamamlayamadığı için FN olmuştur. Dolayısıyla bu üç fark pgvector'ın
farklı kanıt getirmesinden değil, aynı kanıt üzerindeki yerel üretim çıktısının
ifade/tamlık değişkenliğinden kaynaklanır. Tek koşulu bu sonuç, backend hız veya
doğruluk üstünlüğü olarak genellenmemelidir.

## Veri ve güvenlik sınırı

- Uygulama rastgele web taraması yapmaz. Web kaynakları incelenip yerel Markdown
  kayıtları olarak seçilmiştir.
- Yanıt üretimi Ollama ile yereldir; doküman metni bir bulut LLM servisine
  gönderilmez.
- Yalnızca tasnif dışı, kamuya açık veya kullanım yetkisi bulunan belgeler
  sisteme alınmalıdır.
- Bu bir operasyonel karar sistemi değildir. Kritik iddialar her zaman gösterilen
  asıl belge ve sayfadan doğrulanmalıdır.
- Kamuya açık resmî ADVENT broşürü, temiz kurulumda kabul testlerinin
  tekrarlanabilmesi için başlangıç belgesi olarak sürümlenir. Sonradan yüklenen
  PDF'ler ve manifest ise `.gitignore` ile sürüm kontrolü dışında tutulur.

## MCP Swing demonstrasyonu

`mcp-swing-demo/`, RAG uygulamasından bağımsız bir Java 21 modülüdür. Yerel bir
Swing iz ekranındaki hız, yön ve gemi tipi alanlarını resmî Java MCP SDK üzerinden
okuyan ve değiştiren on kontrollü araç sunar. Operatör, model yazma yetkisini
arayüzden kilitleyebilir; son 100 değişiklik kaynak bilgisiyle canlı tabloda izlenir. Gerçek sistem ya da şirket verisi
kullanmaz; yapay zekâ–operatör arayüzü entegrasyonunu güvenli bir demonstrasyonla
gösterir.

```powershell
cd mcp-swing-demo
.\mvnw.cmd clean verify
java -jar target\mcp-swing-demo.jar
```

Kurulum, mimari, araç kataloğu ve MCP istemci ayarı için
[docs/MCP_SWING_DEMO.md](docs/MCP_SWING_DEMO.md) belgesine bakın.
CMS-RAG sohbetinden yapılan onaylı entegrasyonun niyet ayrımı, güvenlik kararları,
örnekleri ve ölçek sınırı [docs/MCP_ASSISTANT_INTEGRATION.md](docs/MCP_ASSISTANT_INTEGRATION.md)
içinde açıklanır.
