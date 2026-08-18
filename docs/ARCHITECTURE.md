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

### 5.1 Kontrollü Agentic LangGraph hattı

Klasik sorgu hattı karşılaştırma ve geri dönüş için korunur. Kullanıcı kenar
panelinden agentic modu açtığında aynı domain, retrieval, üretim ve audit servisleri
LangGraph tarafından ayrı ve checkpoint'li düğümler olarak orkestre edilir:

```text
girdi doğrulama
  -> deterministik route (bilgi / MCP / güvenli ret)
  -> deterministik ön cevap kontrolü
  -> bağlamlı retrieval sorgusu planlama
  -> FAISS veya pgvector hibrit retrieval + BM25 + reranking
  -> kanıt yeterlilik kapısı
  -> yalnız yeterli kanıtta yerel Ollama üretimi
  -> kaynak kimliği ve cümle bütünlüğü doğrulaması
  -> gerekirse tek deterministik atıf onarımı
  -> audit + kısa konuşma belleği + checkpoint
```

MCP route'u LangGraph'in serbestçe yazma aracı çağırmasına izin vermez. Yazma niyeti
`interrupt()` ile checkpoint üzerinde durur; doğal dil doğrulaması ve işlem planı
gösterildikten sonra operatör onayı alınır. MCP yazması, yazma kilidi, stale-state
kontrolü ve geri-okuma doğrulamasından geçer; graph aynı `thread_id` üzerinde
`Command(resume=...)` ile tamamlanır. Salt-okunur MCP çağrıları onay istemez.
Hassas/tasnifli veri route'u retrieval
ve model çağrısından önce sonlanır. Graph state içindeki kanıtlar özel Python
nesneleri olarak değil, sıkı msgpack/JSON uyumlu alanlar biçiminde saklanır.

Agentic doğrulama döngüsü üstten sınırlıdır: model ikinci kez serbest cevap
üretmez; yalnız atıf ve tamamlanmış cümle biçimi deterministik olarak bir kez
onarılabilir. Onarım da doğrulamayı geçmezse cevap ve kanıt kartları gizlenir.

#### Checkpoint yaşam döngüsü

- `CMS_RAG_CHECKPOINT_DSN` yoksa `InMemorySaver` kullanılır; bu seçenek yerel
  geliştirme ve otomatik testler içindir.
- DSN verildiğinde `PostgresSaver` bağlantısı Streamlit resource cache ile tek
  yaşam döngüsünde tutulur ve uygulama kapanırken kapatılır.
- PostgreSQL tabloları ilk kullanımda `setup()` ile hazırlanır. Yapılandırılmış
  kalıcı altyapı çalışmazsa sistem sessizce geçici belleğe geçmez.
- DSN yalnızca composition-root seviyesinde okunur; graph state, olay listesi,
  audit ve arayüz metnine eklenmez. Hata metinleri sürücü ayrıntılarını ve
  parolayı gizler.
- `JsonPlusSerializer`, özel msgpack modüllerinin yüklenmesini kabul etmeyecek
  biçimde kurulur. Graph state yalnızca temel JSON/msgpack tiplerinden oluşur.
- Her sohbet `thread_id` ile ayrı tutulur; arayüzde oturum temizlendiğinde yeni
  thread kimliği üretilir ve eski kalıcı kayıt yeni sohbete karışmaz.
- Tamamlanmış konuşmalar checkpoint deposundan özetlenir; ilk soru başlık olur ve
  seçilen thread'in kullanıcı mesajları, cevapları ve kaynak kartları yeniden kurulur.
- Operatör onayı bekleyen MCP thread'i ayrı durumuyla listelenir. Uygulama yeniden
  başlatılsa bile aynı checkpoint seçilip plan yeniden gösterilebilir ve güvenli biçimde
  onaylanabilir veya reddedilebilir.
- Planlama, retrieval, kanıt kapısı, üretim ve onarım düğümleri hata sınırlarına sahiptir.
  Bağımlılık arızasında kaynak dışı cevap üretilmez; güvenli sonuç ve düğüm olayı
  checkpoint'e yazılır.

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
- Yerel audit olayı ham soru, cevap veya belge metni saklamaz; sorguyu kısaltılmış
  SHA-256 özetiyle, sonucu ise kapsam, gecikme ve belge/sayfa metadatasıyla kaydeder.
- Mentör değerlendirmesi için açıkça istenen ham input/output kayıtları audit'ten ayrı,
  Git dışında tutulan `data/evaluation/live_tests.jsonl` deney deposunda saklanır.
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
denetlenebilir. Değerlendirme merkezi her tamamlanan kullanıcı turunu input, output,
model/üretim yolu, chunk kalite kararı ve TP/TN/FP/FN etiketiyle canlı tabloya ekler.
Gerçek sınıf önce altın-set eşleşmesinden, eşleşme yoksa etiketi görünür bırakılan
otomatik kanıt denetiminden gelir. Hit@6, MRR, chunk/cevap hakemi ve FAISS/pgvector
sonuçları canlı sayaçlara karıştırılmadan ayrı referans sekmesinde gösterilir.
İşletim/audit sekmesi ham kullanıcı içeriği olmadan operasyon metadatasını sunar.

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

## 12. MCP Swing demonstrasyon sınırı

`mcp-swing-demo` bağımsız bir Java modülüdür ve Python RAG çalışma zamanına
bağlanmaz. Modül içinde bağımlılık yönü `presentation/infrastructure → application
→ domain` şeklindedir. Swing ekranı ve MCP adaptörü aynı `TrackStateService`
durumunu kullanır; böylece arayüzden ve model aracından gelen değişiklikler tek
doğrulama hattından geçer. MCP STDIO aktarımı yalnız izinli get/set araçlarını
açar; genel amaçlı kod, dosya, ağ veya kabuk erişimi sunmaz. Değişiklik kaynağı
`OPERATOR` veya `MCP` olarak son 100 olaylık bellek içi audit listesine yazılır.
Operatör arayüzündeki yazma kilidi modelin `set_*` araçlarını anında reddederken
salt okunur araçları kullanılabilir bırakır.
