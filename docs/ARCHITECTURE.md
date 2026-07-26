# CMS-RAG Kurumsal Mimari

## 1. Amaç ve kapsam

CMS-RAG Assistant, Combat Management System ve HAVELSAN ADVENT hakkında yerel
dokümanlardan denetlenebilir yanıt üretir. Tasarımın ana ilkesi, modelin genel
bilgisinden çok getirilen kanıtı esas almak ve farklı otoritedeki kaynakları
birbirine karıştırmamaktır.

Sistem bir operasyonel komuta-kontrol bileşeni değildir; kamuya açık bilgi keşfi,
eğitim, araştırma ve sunum hazırlığı için tasarlanmıştır.

## 2. Güven sınırı ve veri sınıfları

| Koleksiyon | İçerik | Otorite | Kullanım |
|---|---|---|---|
| `official` | Yüklenen resmî PDF ve HAVELSAN seçilmiş içeriği | Üretici/resmî | Ürün özellikleri ve ADVENT iddiaları |
| `open_source` | NATO gibi kamuya açık referanslar | Açık/kamu | Genel C2 ve birlikte çalışabilirlik bağlamı |
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
  +-- DocumentStore ------ SHA-256, manifest, tekrar engelleme, silme
  +-- PDFIngestor -------- PDF imzası, sayfa metni, parçalama
  +-- MarkdownIngestor --- front matter, koleksiyon ve otorite
  +-- QueryContextualizer  takip sorusu + Türkçe terim genişletme
  +-- HybridRetriever ---- FAISS + BM25 + RRF + cross-encoder
  +-- EvidenceResponder -- açık kanıta dayalı hızlı yanıt
  +-- Ollama ------------ yerel ve akışlı üretim
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

## 6. Belge yaşam döngüsü

1. Dosya PDF imzası ve boyut sınırıyla doğrulanır.
2. İçerik SHA-256 ile kimliklendirilir.
3. Aynı hash manifestte varsa tekrar saklanmaz.
4. Özgün görünen ad, boyut, kaynak tipi ve zaman manifestte tutulur.
5. İndeks, mevcut belgeler ve seçilmiş referanslardan yeniden kurulabilir.
6. Silme, doğrulanmış manifest kaydı ile dosyayı kaldırır ve indeksi yeniler.

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
- Ollama istemcisi 120 saniye zaman aşımı, 96 token cevap sınırı ve 30 dakika
  sıcak tutma süresiyle sınırlandırılmıştır.
- CPU tabanlı etkileşimli kullanımda varsayılan model `qwen2.5:3b`dir;
  `CMS_RAG_MODEL` ile daha büyük bir yerel model seçilebilir.

## 8. Güvenlik ve gizlilik

- Doküman içeriği yerel Ollama dışında bir üretim servisine gönderilmez.
- Rastgele web taraması yoktur; kaynaklar kontrollü biçimde seçilip depoya alınır.
- HTML kaynak alıntıları arayüzde kaçışlanır.
- Dosya adı depolama yolu olarak kullanılmaz; içerik hash'i kullanılır.
- Kamuya açık resmî başlangıç broşürü dışında, yüklenen çalışma verisi sürüm
  kontrolü dışında tutulur.

Üretim ortamı için önerilen ek kontroller: kullanıcı kimliği, rol bazlı erişim,
disk şifreleme, merkezi audit kaydı, kötü amaçlı dosya taraması, kaynak onay
iş akışı ve ağ çıkış politikası.

## 9. İşletim ve gözlemlenebilirlik

Arayüz; yüklü belge sayısı, indeks parça sayısı, aktif model, arama yöntemi ve her
yanıtın kanıt paketini gösterir. Yeniden indeksleme deterministik bir kurtarma
yoludur. Retrieval kabul raporu makinece okunabilir JSON olarak üretilir.

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
- Kaynak yenileme otomatik değildir; seçilmiş referanslar gözden geçirilerek
  güncellenir.
- Yerel model kalitesi donanım ve seçilen Ollama modeline bağlıdır.
- FAISS indeksi süreç başlangıcında yeniden kurulur; çok büyük koleksiyonlar için
  kalıcı vektör deposu gerekir.
- Bu sürüm tek kullanıcılı yerel çalışma istasyonu hedefler.
