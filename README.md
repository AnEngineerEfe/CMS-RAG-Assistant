# CMS-RAG Assistant

Yerel çalışan, kaynak gösteren ve koleksiyon ayrımı uygulayan Combat Management
System (CMS) doküman asistanı.

Sistem; kullanıcı tarafından yüklenen resmî PDF'leri, seçilmiş HAVELSAN resmî
içeriğini ve açık/kamu kaynaklarını ayrı yetki sınıflarıyla indeksler. Yanıtlar
FAISS semantik arama, BM25, Reciprocal Rank Fusion ve cross-encoder reranking
sonucunda seçilen kanıtlara dayanır.

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
- Belge silme, yeniden indeksleme ve güvenli boş-bilgi-tabani davranışı

## Gereksinimler

- Python 3.11 veya üzeri
- Ollama
- En az 8 GB RAM; embedding ve reranker modellerinin ilk açılışta indirilmesi
  için internet erişimi

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

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.
Embedding ve reranker ağırlıkları bir kez indirildikten sonra katı çevrimdışı
çalışma için uygulamayı başlatmadan önce `$env:CMS_RAG_OFFLINE="1"` ayarlanabilir.

Varsayılan `qwen2.5:3b`, CPU tabanlı makinelerde etkileşimli kullanım için
seçilmiştir. Daha güçlü donanımda 7B kalite modu kullanılabilir:

```powershell
ollama pull qwen2.5:7b
$env:CMS_RAG_MODEL="qwen2.5:7b"
streamlit run app.py
```

## Kullanım

1. Sol panelden yalnızca kamuya açık veya kullanım yetkiniz bulunan resmî PDF'i
   seçin.
2. `Belgeyi doğrula ve indeksle` düğmesine basın. Aynı içerik yeniden seçilirse
   ikinci bir kayıt oluşturulmaz.
3. Sorgu kapsamını `Birleşik`, `Yalnızca resmî` veya `Yalnızca açık kaynak`
   olarak seçin.
4. Yanıtın altındaki kanıt paketinden belgeyi, sayfayı, otoriteyi ve varsa
   kaynak URL'sini denetleyin.

`İndeksi yenile` mevcut yerel belgeleri yeniden işler.
Belge satırındaki silme işlemi hem dosyayı hem manifest kaydını kaldırır ve
indeksi yeniler.

## Mimari

```text
PDF + seçilmiş Markdown kaynakları
  -> doğrulama ve meta veri
  -> sayfa bazlı parçalama
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
  presentation/                Streamlit tema, bileşen, sidebar ve sohbet akışı
data/
  documents/                   İçerik adresli PDF deposu
  references/official/         Doğrulanmış üretici kaynakları
  references/open_source/      Doğrulanmış açık/kamu kaynakları
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
```

İkinci komut, sabit kabul sorularının beklenen sayfa/koleksiyon/terimleri getirip
getirmediğini denetler ve raporu `docs/retrieval_evaluation_report.json`
dosyasına yazar.

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
