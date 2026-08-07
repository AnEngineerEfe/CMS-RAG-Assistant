# İleri RAG Değerlendirmesi

## Amaç

Bu çalışma üç soruyu ayrı deneylerle cevaplar:

1. Üretilen chunk'lar anlamlı, öz-yeterli ve doğru sınırlara sahip mi?
2. RAG cevapları doğru belge ve sayfaya dayanıyor mu?
3. Chunk boyutu, retrieval yaklaşımı ve vektör veritabanı seçimi sonucu nasıl
   etkiliyor?

Üretim modeli `qwen2.5:3b`, bağımsız hakem modeli farklı aileden
`llama3.2:3b` olarak tutulmuştur. Her iki model de Ollama üzerinden yerel
çalışmış, çalışma anında internet veya şirket içi veri kullanılmamıştır.

## 1. Aşama — Chunk kalite hakemi

Üretim snapshot'ındaki 77 chunk'ın tamamı hakeme verilmiştir; örneklem
kullanılmamıştır. Her chunk dört boyutta 1–5 arasında değerlendirilmiştir:

- Coherence: tek ve anlaşılır konu
- Self-containment: dış bağlam olmadan yeterli anlam
- Boundary quality: kırık kelime veya bariz yarım düşünce olmaması
- Size fitness: retrieval için ne aşırı kısa ne gereksiz uzun olması

Bir chunk ancak dört puanın tamamı en az 3 ise kabul edilir. Judge JSON
şemasındaki eksik, aralık dışı veya kendi `acceptable` kararıyla çelişen sonuç
başarılı sayılmaz. Uzun koşu her chunk sonrasında cache'e yazılır.

| Ölçüm | Sonuç |
|---|---:|
| Chunk | 77 |
| Geçerli judge çıktısı | 77 |
| Geçersiz çıktı | 0 |
| Kabul edilen | 77 |
| Coherence ortalaması | 4,104 |
| Self-containment ortalaması | 3,429 |
| Boundary quality ortalaması | 4,169 |
| Size fitness ortalaması | 3,961 |

Kabul oranı `%100` olsa da en zayıf boyut öz-yeterliliktir. Bu nedenle sonuç,
“chunk'lar geliştirilemez” şeklinde yorumlanmamalıdır. Tam metinler ve tekil
gerekçeler `stage1_chunks.csv` ile `stage1_chunk_judgments.csv` dosyalarındadır.

## 2. Aşama — Cevap ve kaynak değerlendirmesi

Genişletilmiş altın veri setindeki 30 pozitif sorunun tamamı gerçek uygulama motoruna
sorulmuştur. Her cevap:

- LLM hakeminin faithfulness, relevance ve completeness puanlarından,
- cevabın altın belge/sayfalardan en az birini gerçekten kullanmasından

birlikte geçmek zorundadır.

İlk tur iki varyant cevabında doğru içerik fakat yanlış genel sayfa atfını,
eğitim/SOPA sorusunda ise yanlış genel cevap kuralını ortaya çıkarmıştır.
Kurallar ayrıntılı ürün sayfalarına bağlandıktan sonra ilk set `23/23` olmuştur.
Genişletilmiş tur, iz füzyonu parafrazında doğru sayfa getirilmesine rağmen
cevabın dolaylı kaldığını göstermiş; doğrudan sayfa-9 kanıt kuralı eklendikten
sonra nihai sonuç `30/30` olmuştur.

Bu tur ayrıca LLM hakeminin yanlış genel SOPA cevabını kabul edebildiğini
göstermiştir. Dolayısıyla judge tek başına doğruluk ölçütü değildir; altın
belge/sayfa ve deterministik kontroller zorunludur.

## 3. Aşama — Chunk ve retrieval karşılaştırması

Bu tablodaki chunk adetleri, karşılaştırmanın çalıştırıldığı önceki 67-chunk
corpus konfigürasyonuna aittir; 77-chunk güncel snapshot'ın Aşama-1 sonucu ile
karıştırılmaz. Yaklaşım karşılaştırması yeniden çalıştırıldığında tablo aynı
komutla yenilenebilir.

Aynı 30 pozitif soru, aynı embedding modeli ve `K=6` ile ölçülmüştür.

| Yaklaşım | Chunk | Chunk adedi | Hit@6 | MRR | Terim kapsama |
|---|---:|---:|---:|---:|---:|
| BM25 | 450 | 136 | %100 | 0,933 | %96,7 |
| FAISS dense | 450 | 136 | %90,0 | 0,682 | %90,0 |
| Hybrid RRF | 450 | 136 | %100 | 0,851 | %96,7 |
| BM25 | 900 | 67 | %100 | 0,906 | %100 |
| FAISS dense | 900 | 67 | %90,0 | 0,758 | %91,7 |
| Hybrid RRF | 900 | 67 | %100 | 0,836 | %100 |
| Hybrid + tam reranker | 900 | 67 | %100 | 0,836 | %100 |
| Hybrid + kanıt kapısı | 900 | 67 | %100 | 0,836 | %100 |
| BM25 | 1350 | 48 | %100 | 0,867 | %100 |
| FAISS dense | 1350 | 48 | %93,3 | 0,739 | %91,7 |
| Hybrid RRF | 1350 | 48 | %96,7 | 0,856 | %96,7 |

Mevcut corpus için 900 karakter ve 150 karakter overlap dengeli seçimdir.
BM25 altın sette güçlüdür; ancak üretimde paraphrase dayanıklılığı için dense ve
sözcüksel adayların RRF ile birleştirilmesi korunmuştur.

Tam cross-encoder reranking, aynı Hit@6 değerine rağmen MRR'ı düşürmüş ve
gecikmeyi büyütmüştür. Bu nedenle reranker tüm sıralamayı değiştirmek yerine
ilk hibrit kanıtları doğrulayan bir kapı olarak kullanılmaktadır. Genişletilmiş
nihai 45 vakalı kabul turunda bu tasarım:

- TP/TN/FP/FN: `30/15/0/0`
- Hit@6: `%100`
- MRR: `0,7694`
- Ortalama retrieval: `1438,3 ms`
- p95 retrieval: `1750,2 ms`

üretmiştir.

## 4. Aşama — FAISS ve gerçek pgvector

Docker içindeki PostgreSQL 16 + pgvector üzerinde geçici ve kalıcı olmayan bir
tablo kurulmuştur. FAISS ve pgvector:

- karşılaştırma tarihinde kullanılan aynı 67 önceden hesaplanmış embedding,
- exact cosine,
- aynı 23 sorgu vektörü,
- aynı koleksiyon filtresi ve K=6

ile karşılaştırılmıştır.

| Backend | Hit@6 | MRR | Ortalama yalnız-arama |
|---|---:|---:|---:|
| FAISS | %91,3 | 0,808 | 0,84 ms |
| pgvector | %91,3 | 0,808 | 3,02 ms |

İlk altı sonuç sırası 23/23 sorguda aynıdır. Bu küçük ve tek süreçli corpus'ta
FAISS daha hızlıdır. pgvector; kalıcı merkezi veri, SQL metadata filtreleri,
eşzamanlı kullanıcılar ve yatay/operasyonel yönetim gerektiğinde anlamlıdır.
Dolayısıyla mevcut yerel demo için FAISS korunmuş, pgvector kurumsal ölçekleme
seçeneği olarak doğrulanmıştır.

## Tekrarlama

```powershell
# Chunk, cevap ve retrieval deneyleri
.\.venv\Scripts\python.exe -m scripts.run_quality_evaluation

# Yalnız yeni snapshot chunklarını değerlendirip mevcut raporu koruma
.\.venv\Scripts\python.exe -m scripts.refresh_chunk_quality_stage

# 20 vakalık bağımsız chunk-köken deneyi
.\.venv\Scripts\python.exe -m scripts.run_chunk_lineage_evaluation

# Yerel PostgreSQL (pgAdmin'de cms_rag_eval ve vector uzantısı hazır olmalı)
.\.venv\Scripts\python.exe -m scripts.run_pgvector_benchmark
```

Komut varsayılan olarak `postgres@localhost:5432/cms_rag_eval` hedefine bağlanır
ve parolayı terminalde görünmeden ister. Parola rapora, loga veya Git'e yazılmaz.
Farklı kullanıcı ya da port için `--user` ve `--port` seçenekleri kullanılabilir.
Deney yalnız bağlantı oturumuna ait geçici tablo oluşturur; mevcut kullanıcı
tablolarını silmez veya değiştirmez.

Nihai birleşik çıktılar
`evaluation/results/quality-latest/` klasöründedir.
