# Nihai Kabul Raporu

Tarih: 2026-08-18

## Sonuç

CMS-RAG Assistant, önceden araştırılmış ve küratör kontrolünden geçirilmiş kamuya
açık belgeleri çalışma anında internete çıkmadan kullanan yerel bir RAG asistanı
olarak doğrulanmıştır. Hazırlama hattı ile normal soru-cevap hattı birbirinden
ayrılmıştır. Normal kullanımda uygulama hazır PDF paketini, chunk meta verilerini
ve önceden hesaplanmış embedding snapshot'ını yükler.

Bu çalışma yalnızca kamuya açık kaynaklarla hazırlanmış bir ön çalışma ve araştırma
niteliğindedir. HAVELSAN'a ait şirket içi, özel, tasnifli veya erişim kısıtlı hiçbir
veri kullanılmamıştır.

## Ölçülen kabul sonuçları

| Kontrol | Sonuç |
|---|---:|
| Otomatik test | 149/149 başarılı |
| Retrieval kabul vakası | 8/8 başarılı |
| Gerçek yanıt kabul vakası | 7/7 başarılı |
| Hazır PDF kaynağı | 5 |
| İndekslenen anlamlı chunk | 77 |
| Önceden hesaplanmış embedding | 77 |
| 20-vaka confusion matrix | 15 TP / 4 TN / 0 FP / 1 FN |
| İkinci 20-vaka confusion matrix | 15 TP / 4 TN / 0 FP / 1 FN |
| İkinci exact chunk-köken eşleşmesi | 14/16 (%87,5) |
| 20-vaka accuracy / F1 | %95,0 / %96,77 |
| Exact chunk-köken başarı | 13/16 (%81,25) |
| pgvector Seri 1 confusion matrix | 15 TP / 4 TN / 0 FP / 1 FN |
| pgvector Seri 2 confusion matrix | 12 TP / 4 TN / 0 FP / 4 FN |
| FAISS–pgvector retrieval listesi eşitliği | 40/40 |
| 80 karakter altı gürültü chunk | 0 |
| PDF sayfası | 42/42 metinli |
| PDF metin karakteri | 50.802 |
| Snapshot yükleme | Başarılı |
| Çalışma anı web erişimi | Kapalı |
| Varsayılan model | qwen2.5:3b |

## Hazır bilgi tabanı

Paket aşağıdaki kamuya açık içeriklerden oluşturulmuştur:

- HAVELSAN ADVENT resmî ürün broşürü
- ADVENT CMS ve ürün ailesi kamuya açık araştırma özeti
- ADVENT-AI ve MAIN yapay zekâ entegrasyonu kamuya açık araştırma özeti
- Deniz C2, veri ve sorumlu yapay zekâ yönetişimi kamuya açık araştırma özeti
- Genel deniz CMS mühendisliği, sıfır güven ve güvenilir AI kamu araştırma özeti

Her araştırma PDF'i kaynak adreslerini, veri sınırını ve hazırlanma tarihini taşır.
Manifest, kaynak hash'lerini ve üretilen PDF'leri; snapshot ise chunk meta verileri
ile embedding matrisini sürümlenebilir biçimde saklar.

## Çalışma modeli

### Hazırlama aşaması

1. Birincil ve kamuya açık kaynaklar araştırılır.
2. İçerik kapsam ve kaynak kontrolünden geçirilir.
3. Metin çıkarılabilir PDF paketi oluşturulur.
4. Belgeler sayfa bilgisi korunarak chunk'lara ayrılır.
5. Embeddingler bir kez hesaplanır ve snapshot'a yazılır.

### Normal kullanım

1. Uygulama yerel manifesti ve snapshot'ı yükler.
2. Kullanıcı sorusu hibrit retrieval ile hazır kanıtlarda aranır.
3. FAISS, BM25, RRF ve cross-encoder sıralaması uygulanır.
4. Yerel Ollama modeli yalnız getirilen kanıta dayanarak cevap üretir.
5. Cevapla birlikte belge ve sayfa kaynakları gösterilir.

### Agentic kullanım

1. LangGraph isteği bilgi, canlı MCP kontrolü veya güvenli ret rotasına ayırır.
2. Bilgi rotasında retrieval, kanıt yeterliliği, üretim ve atıf doğrulama ayrı
   checkpoint'li düğümlerde çalışır.
3. PostgreSQL yapılandırıldığında konuşmalar uygulama yeniden başlatıldıktan sonra
   listelenebilir ve kaynak kartlarıyla geri yüklenebilir.
4. MCP yazması `interrupt()` noktasında durur; açık operatör onayı olmadan araç çağrılmaz.
5. Onay veya ret aynı thread üzerinde graph'ı devam ettirir; bekleyen onay yeniden
   başlatma sonrasında da kurtarılabilir.
6. Düğüm arızaları belgesiz cevap üretmeden güvenli sonuca çevrilir; rota, doğrulama,
   onarım sayısı ve süre kullanıcıya gösterilir.

Bu akışta web taraması, çalışma anı araştırması veya çekirdek belgelerin yeniden
embedding edilmesi yoktur.

## Retrieval ve cevap güvenilirliği

- ADVENT su üstü rolü, iz yönetimi, taktik veri bağları ve NATO birlikte
  çalışabilirliği test edilmiştir.
- ADVENT-AI operatör desteği, MAIN bakım destek asistanı, NATO sorumlu yapay zekâ
  ilkeleri ve ADVENT ROTA sorguları doğru hazırlanmış kaynaklara yönelmiştir.
- Tüm sekiz kabul vakasında beklenen belge/koleksiyon ve anahtar içerik bulunmuştur.
- Yedi gerçek uygulama yanıtında beklenen kavram, kaynak kararı ve atıf birlikte
  karşılaştırılmış; takip soruları ve desteklenmeyen menzil sorusu doğru sınıflanmıştır.
- Güçlü kanıt bulunduğunda modelin yanlış güvenli-ret üretmesi, soru-odaklı kanıt
  özeti ve kaynaklı çıkarımsal yedekle engellenir.
- Başarılı cevaplarda metin içi `[SOURCE n]` etiketi ve açılabilir kaynak kartı
  korunur.
- Sohbet geçmişi takip sorularını destekler; önceki mesajların kaynakları ekranda
  kaybolmaz.

## Veri güvenliği ve hata davranışı

- PDF olmayan içerik ve 200 MB üzerindeki dosya reddedilir.
- Aynı içerik SHA-256 özetiyle ikinci kez saklanmaz.
- Hazır çekirdek kaynaklar kullanıcı ek belge yönetiminden silinemez.
- Bozuk ek PDF, çekirdek indeksin yüklenmesini engellemez.
- Manifest yol taşmasıyla proje dışı dosya erişimi engellenir.
- Ollama hatasında ilgisiz kaynak kartı gösterilmez.
- Kişisel veya kapsam dışı sorularda kaynak uydurulmadan güvenli ret verilir.
- Şirket içi, özel ve tasnifli veri kapsam dışıdır.

## Yeniden üretim

Hazır bilgi tabanı aşağıdaki komutla yeniden üretilebilir:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_knowledge_base
```

Bu işlem PDF'leri, manifesti, chunk'ları ve embedding snapshot'ını birlikte yeniler.
Normal kullanıcı bu komutu çalıştırmak zorunda değildir.

## Bilinen mimari sınırlar

- Görüntü tabanlı taranmış PDF'ler için OCR katmanı yoktur.
- Yerel model kalitesi donanım ve seçilen Ollama modeline bağlıdır.
- FAISS bellekte hazır embeddinglerden kurulur; çok kullanıcılı kurumsal kullanım
  için kalıcı ve sunucu tabanlı vektör deposu gerekir.
- Gerçek PostgreSQL pgvector, aynı iki 20-vaka setinde ayrı backend olarak
  doğrulanmıştır; üretim varsayılanı değiştirilmeden kurumsal geçiş yolu hazırdır.
- Bu sürüm tek kullanıcılı yerel çalışma istasyonunu hedefler.
- Kaynak güncellemesi otomatik değildir; kürasyon ve snapshot hazırlama hattı
  kontrollü biçimde yeniden çalıştırılmalıdır.
- Kritik iddialar gösterilen asıl belge ve sayfadan doğrulanmalıdır.
