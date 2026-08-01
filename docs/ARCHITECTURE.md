# CMS-RAG Kurumsal Mimari

## 1. Amaç ve kapsam

CMS-RAG Assistant, Combat Management System ve HAVELSAN ADVENT hakkında yerel
dokümanlardan denetlenebilir yanıt üretir. Tasarımın ana ilkesi, modelin genel
bilgisinden çok getirilen kanıtı esas almak ve farklı otoritedeki kaynakları
birbirine karıştırmamaktır.

Sistem bir operasyonel komuta-kontrol bileşeni değildir; kamuya açık bilgi keşfi,
eğitim, araştırma ve sunum hazırlığı için tasarlanmıştır.

Araştırma ve kaynak kurasyonu geliştirme aşamasında yapılır. Normal soru-cevap
çalışması internet kullanmaz; önceden üretilmiş yerel PDF paketi ve embedding
snapshot'ı yüklenir.

## 2. Güven sınırı ve veri sınıfları

| Koleksiyon | İçerik | Otorite | Kullanım |
|---|---|---|---|
| `official` | Hazır ADVENT broşürü ve HAVELSAN kamu içeriği | Üretici/resmî | Ürün özellikleri ve ADVENT iddiaları |
| `open_source` | NATO ve U.S. Navy kamu referansları | Açık/kamu | Genel C2, veri ve sorumlu yapay zekâ bağlamı |
| `all` | İki koleksiyonun birleşik görünümü | Kaynak bazında korunur | Geniş araştırma |

Her parça; belge adı, sayfa, kaynak yolu, koleksiyon, otorite ve kaynak URL'sini
taşır. Açık kaynak bağlamı, ürün-spesifik resmî iddia gibi sunulmaz.

## 3. Katmanlar ve bağımlılık yönü

```text
app.py
  |
  v
presentation/  ---- Streamlit ekranı, durum ve kullanıcı etkileşimi
  |
  v
application/   ---- RAG kullanım senaryosu ve iş akışı orkestrasyonu
  |        \
  v         v
domain/     infrastructure/
  ^         ---- PDF, depolama, embedding, FAISS, BM25 ve reranker
  |
  +------------- Katmanlar arası modeller ve saf karar kuralları
```

- `domain`, başka bir proje katmanına veya Streamlit/Ollama/FAISS gibi bir
  teknolojiye bağımlı değildir.
- `infrastructure`, yalnız alan modellerini kullanır ve dosya/arama ayrıntılarını
  uygulama katmanından gizler.
- `application`, domain kuralları ile altyapı uygulamalarını tek kullanım
  senaryosunda birleştirir.
- `presentation`, kullanıcı etkileşimini yürütür; retrieval veya depolama iş
  kuralı içermez.
- Kök `app.py`, Streamlit'in sabit çalıştırma hedefidir ve yalnız sunum
  orkestratörünü çağırır.

Bu bağımlılık sınırları `tests/test_architecture.py` ile otomatik korunur.

## 4. Bileşenler

```text
Streamlit UI
  |
  v
RAGEngine
  +-- KnowledgeManifest -- hazır PDF kaynakları, otorite ve SHA-256
  +-- PreparedSnapshot -- önceden hesaplanmış chunk + embedding
  +-- DocumentStore ------ SHA-256, manifest, tekrar engelleme, silme
  +-- PDFIngestor -------- PDF imzası, sayfa metni, parçalama
  +-- MarkdownIngestor --- front matter, koleksiyon ve otorite
  +-- QueryContextualizer  takip sorusu + Türkçe terim genişletme
  +-- HybridRetriever ---- FAISS + BM25 + RRF + cross-encoder
  +-- EvidenceResponder -- açık kanıta dayalı hızlı yanıt
  +-- Ollama ------------ yerel ve akışlı üretim
  +-- SourcePreview ----- data/ sınır kontrollü PDF sayfa görüntüsü
  +-- EvaluationPanel --- sürümlü benchmark ve LLM-hakem raporları
```

## 5. Sorgu hattı

```text
Soru + aynı kaynak kapsamındaki en fazla üç önceki tur
  -> sohbet dışı / kişisel soru güvenli reddi
  -> kontrollü bağlamlandırma
  -> Türkçe CMS terim genişletmesi
  -> seçili koleksiyon filtresi
  -> semantic ve lexical adaylar
  -> Reciprocal Rank Fusion
  -> cross-encoder reranking
  -> aynı sayfadaki tamamlayıcı parçaların birleştirilmesi
  -> yeterli kanıt kontrolü
  -> kanıt şablonu veya Ollama yanıt akışı
  -> cevapla birlikte kalıcı kanıt paketi
```

Semantik arama anlam yakınlığını, BM25 ise ürün adı, kısaltma ve teknik terim
eşleşmesini yakalar. RRF skor ölçeklerini doğrudan karşılaştırmadan iki sıralamayı
birleştirir. Cross-encoder son adayları soru-parça çifti olarak yeniden sıralar.

## 6. Hazır bilgi tabanı ve belge yaşam döngüsü

1. Kamuya açık birincil kaynaklar geliştirme aşamasında doğrulanır.
2. Küratörlü içerik, kapsam ve kaynakça taşıyan PDF paketlerine dönüştürülür.
3. PDF'ler sayfa bazında parçalanır; embeddingler önceden hesaplanıp snapshot'a yazılır.
4. Uygulama açılışında snapshot yüklenir; çekirdek PDF'ler yeniden embeddinglenmez.
5. İsteğe bağlı ek dosya PDF imzası ve boyut sınırıyla doğrulanır.
6. Ek içerik SHA-256 ile kimliklendirilir; aynı hash yeniden saklanmaz.
7. Yalnız yeni ek belgenin chunk ve embeddingleri hazır indekse eklenir.
8. Çekirdek kaynaklar arayüzden silinemez; ek belgeler manifest üzerinden yönetilir.

Bozuk veya metinsiz bir PDF tüm indeksleme işlemini çökertmez; belge atlanır.

## 7. Yanıt güvenilirliği

- Kaynaksız kişisel/sohbet soruları retrieval çalıştırmadan reddedilir.
- Kanıt yetersizse sistem açıkça yeterli kaynak bulunamadığını söyler.
- Kaynak etiketleri cevap metni ile kanıt kartları arasında korunur.
- Takip soruları yalnızca sınırlı sohbet bağlamıyla genişletilir.
- Resmî, açık-kaynak ve birleşik kapsamların sohbet geçmişleri birbirine
  taşınmaz; bir koleksiyondaki ürün iddiası diğer koleksiyonun cevabını
  kirletemez.
- Güncel NATO birlikte çalışabilirlik soruları, doğrulanmış açık-kaynak
  kaydından deterministik olarak cevaplanır.
- Üretim istemi yalnızca verilen bağlamı kullanmaya ve desteklenmeyen iddia
  üretmemeye yönlendirir.
- Ollama istemcisi 120 saniye zaman aşımı, 160 token cevap bütçesi, 2.048 token
  bağlam sınırı ve 30 dakika sıcak tutma süresiyle sınırlandırılmıştır. Model
  token bütçesinde durursa yalnız yarım kalan cümle, aynı kanıt bağlamıyla ve
  96 tokenlık tek bir kontrollü devam çağrısıyla tamamlanır.
- CPU tabanlı etkileşimli kullanımda varsayılan model `qwen2.5:3b`dir;
  `CMS_RAG_MODEL` ile daha büyük bir yerel model seçilebilir.

## 8. Güvenlik ve gizlilik

- Doküman içeriği yerel Ollama dışında bir üretim servisine gönderilmez.
- Çalışma anında web taraması veya HTTP kaynak çağrısı yoktur; araştırma yalnız
  sürümlü kurasyon hattında yapılır.
- HTML kaynak alıntıları arayüzde kaçışlanır.
- PDF önizlemesi yalnız çözümlenmiş yolu proje `data/` dizini altında kalan
  `.pdf` dosyalarını kabul eder; dizin geçişi ve dış dosya erişimi reddedilir.
- Dosya adı depolama yolu olarak kullanılmaz; içerik hash'i kullanılır.
- Kamuya açık resmî başlangıç broşürü dışında, yüklenen çalışma verisi sürüm
  kontrolü dışında tutulur.

Üretim ortamı için önerilen ek kontroller: kullanıcı kimliği, rol bazlı erişim,
disk şifreleme, merkezi audit kaydı, kötü amaçlı dosya taraması, kaynak onay
iş akışı ve ağ çıkış politikası.

## 9. İşletim ve gözlemlenebilirlik

Arayüz; hazır kaynak sayısı, toplam aktif belge, snapshot durumu, çalışma-anı web
erişiminin kapalı olduğu, indeks parça sayısı, aktif model, arama yöntemi ve her
yanıtın kanıt paketini gösterir. Kanıt sayfası yerel PDF görüntüsü olarak
denetlenebilir. Değerlendirme merkezi; confusion matrix, Hit@6, MRR, gecikme,
chunk rubriği, cevap hakemi ve FAISS/pgvector karşılaştırmasını sürümlü JSON
raporlarından okur.

## 10. Kod açıklama standardı

- Her kaynak modülü katmanın amacını açıklayan Türkçe bir modül docstring'i
  taşır.
- Her sınıf ve fonksiyon; sorumluluğunu, girdi/çıktı davranışını veya güvenlik
  kararını açıklayan Türkçe docstring'e sahiptir.
- Yorumlar sözdizimini tekrar etmez; kapsam izolasyonu, RRF, hash tabanlı tekrar
  engelleme ve kanıt gizleme gibi ilk bakışta görünmeyen kararların nedenini
  belgeler.
- Bu kural `ArchitectureGuardTests` tarafından AST üzerinden denetlenir.

## 11. Bilinen sınırlar

- Görüntü tabanlı taranmış PDF'ler için OCR katmanı yoktur.
- Kaynak yenileme otomatik değildir; birincil kaynaklar gözden geçirilip PDF ve
  snapshot hazırlama hattı yeniden çalıştırılır.
- Yerel model kalitesi donanım ve seçilen Ollama modeline bağlıdır.
- FAISS bellekte hazır embeddinglerden kurulur. Çok büyük/çok kullanıcılı
  koleksiyonlar için kalıcı ve sunucu tabanlı vektör deposu gerekir.
- Bu sürüm tek kullanıcılı yerel çalışma istasyonu hedefler.
