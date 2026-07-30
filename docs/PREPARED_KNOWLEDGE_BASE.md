# Önceden Hazırlanmış Çevrimdışı Bilgi Tabanı

## Amaç

Uygulama kullanıcı sorusu geldiği anda internet araştırması yapmaz. Araştırma,
kaynak doğrulama, PDF üretimi, parçalama ve belge embedding hesaplama işlemleri
geliştirme aşamasında tamamlanır. Çalışma anında yalnız hazır yerel snapshot,
yerel embedding/reranker modelleri ve Ollama kullanılır.

## Veri sınırı

Bu çalışma, HAVELSAN'ın deniz savaş yönetim sistemleri alanındaki kamuya açık
çalışma ve ürünleri ile kamuya açıklanmış yapay zekâ entegrasyonu süreçlerine
yönelik bir ön çalışma ve araştırmadır. HAVELSAN şirket verisi, şirket içi bilgi,
tasnifli içerik veya kişisel veri kullanılmamıştır.

## Kaynak paketi

| Belge | Sınıf | İçerik |
|---|---|---|
| Resmî ADVENT broşürü | HAVELSAN resmî | Ürün ailesi ve teknik yetenekler |
| `advent_cms_kamuya_acik_arastirma.pdf` | HAVELSAN resmî/küratörlü | CMS işlevleri ve ürün ailesi |
| `advent_ai_kamuya_acik_arastirma.pdf` | HAVELSAN resmî/küratörlü | MAIN ve ADVENT-AI kamu açıklamaları |
| `deniz_c2_veri_ai_yonetisim_arastirma.pdf` | Açık resmî kaynak | NATO veri/AI ilkeleri ve deniz C2 örnekleri |

Her küratörlü PDF kapsam açıklaması, kurasyon tarihi ve kaynak URL'leri taşır.
`data/knowledge_base/manifest.json`, koleksiyon/otorite/ana kaynak metadata
sözleşmesidir.

## Hazırlama hattı

```text
knowledge_base/content/*.md
        │
        ▼
scripts/build_knowledge_base.py
        │
        ├── data/knowledge_base/sources/*.pdf
        ├── data/knowledge_base/manifest.json
        └── data/knowledge_base/snapshot/
              ├── snapshot.json
              └── embeddings.npy
```

Komut:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_knowledge_base
```

Snapshot, chunk metinlerini, belge/sayfa/koleksiyon/otorite/URL metadatasını,
kaynak SHA-256 değerlerini ve önceden hesaplanmış normalize embeddingleri içerir.

## Çalışma hattı

1. Uygulama `snapshot.json` ve `embeddings.npy` dosyalarını yerelden yükler.
2. FAISS indeksi hazır vektörlerle bellekte kurulur; çekirdek PDF'ler yeniden
   embeddinglenmez.
3. BM25 ve RRF sözcüksel/semantik sonuçları birleştirir.
4. Yerel reranker en ilgili kanıtları seçer.
5. Yalnız seçilen kanıt yerel Ollama modeline gönderilir.
6. Cevap belge ve sayfayla gösterilir.

Sonradan eklenen kullanıcı PDF'leri çekirdek snapshottan ayrılır ve yalnız yeni
belgelerin embeddingleri hesaplanır. Çekirdek kaynaklar kullanıcı arayüzünden
silinemez.

## Güncelleme politikası

Web araştırması yalnız planlı kurasyon sürümünde yapılır. Bir kaynak değiştiğinde:

1. Birincil resmî sayfa yeniden doğrulanır.
2. İlgili `knowledge_base/content` metni ve erişim tarihi güncellenir.
3. Hazırlama komutu çalıştırılır.
4. PDF metin çıkarımı, manifest, snapshot ve retrieval testleri çalıştırılır.
5. Değişiklik ayrı Git dalında incelenip birleştirilir.

Bu ayrım, “çalışırken araştıran ajan” ile “önceden hazırlanmış RAG asistanı”
arasındaki mimari sınırı açık tutar.
