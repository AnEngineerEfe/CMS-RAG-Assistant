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

Üretim snapshot'ındaki 67 chunk'ın tamamı hakeme verilmiştir; örneklem
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
| Chunk | 67 |
| Geçerli judge çıktısı | 67 |
| Geçersiz çıktı | 0 |
| Kabul edilen | 67 |
| Coherence ortalaması | 4,119 |
| Self-containment ortalaması | 3,448 |
| Boundary quality ortalaması | 4,164 |
| Size fitness ortalaması | 3,955 |

Kabul oranı `%100` olsa da en zayıf boyut öz-yeterliliktir. Bu nedenle sonuç,
“chunk'lar geliştirilemez” şeklinde yorumlanmamalıdır. Tam metinler ve tekil
gerekçeler `stage1_chunks.csv` ile `stage1_chunk_judgments.csv` dosyalarındadır.

## 2. Aşama — Cevap ve kaynak değerlendirmesi

Altın veri setindeki 23 pozitif sorunun tamamı gerçek uygulama motoruna
sorulmuştur. Her cevap:

- LLM hakeminin faithfulness, relevance ve completeness puanlarından,
- cevabın altın belge/sayfalardan en az birini gerçekten kullanmasından

birlikte geçmek zorundadır.

İlk tur iki varyant cevabında doğru içerik fakat yanlış genel sayfa atfını,
eğitim/SOPA sorusunda ise yanlış genel cevap kuralını ortaya çıkarmıştır.
Kurallar ayrıntılı ürün sayfalarına bağlandıktan sonra sonuç `23/23` olmuştur.

Bu tur ayrıca LLM hakeminin yanlış genel SOPA cevabını kabul edebildiğini
göstermiştir. Dolayısıyla judge tek başına doğruluk ölçütü değildir; altın
belge/sayfa ve deterministik kontroller zorunludur.

## 3. Aşama — Chunk ve retrieval karşılaştırması

Aynı 23 pozitif soru, aynı embedding modeli ve `K=6` ile ölçülmüştür.

| Yaklaşım | Chunk | Chunk adedi | Hit@6 | MRR | Terim kapsama |
|---|---:|---:|---:|---:|---:|
| BM25 | 450 | 136 | %100 | 0,935 | %95,7 |
| FAISS dense | 450 | 136 | %91,3 | 0,692 | %91,3 |
| Hybrid RRF | 450 | 136 | %100 | 0,857 | %95,7 |
| BM25 | 900 | 67 | %100 | 0,899 | %100 |
| FAISS dense | 900 | 67 | %91,3 | 0,808 | %93,5 |
| Hybrid RRF | 900 | 67 | %100 | 0,884 | %100 |
| Hybrid + tam reranker | 900 | 67 | %100 | 0,627 | %100 |
| Hybrid + kanıt kapısı | 900 | 67 | %100 | 0,884 | %100 |
| BM25 | 1350 | 48 | %100 | 0,826 | %100 |
| FAISS dense | 1350 | 48 | %95,7 | 0,768 | %93,5 |
| Hybrid RRF | 1350 | 48 | %95,7 | 0,891 | %95,7 |

Mevcut corpus için 900 karakter ve 150 karakter overlap dengeli seçimdir.
BM25 altın sette güçlüdür; ancak üretimde paraphrase dayanıklılığı için dense ve
sözcüksel adayların RRF ile birleştirilmesi korunmuştur.

Tam cross-encoder reranking, aynı Hit@6 değerine rağmen MRR'ı düşürmüş ve
gecikmeyi büyütmüştür. Bu nedenle reranker tüm sıralamayı değiştirmek yerine
ilk hibrit kanıtları doğrulayan bir kapı olarak kullanılmaktadır. Nihai 33
vakalı kabul turunda bu tasarım:

- TP/TN/FP/FN: `23/10/0/0`
- Hit@6: `%100`
- MRR: `0,8841`
- Ortalama retrieval: `1508,7 ms`
- p95 retrieval: `2056,7 ms`

üretmiştir.

## 4. Aşama — FAISS ve gerçek pgvector

Docker içindeki PostgreSQL 16 + pgvector üzerinde geçici ve kalıcı olmayan bir
tablo kurulmuştur. FAISS ve pgvector:

- aynı 67 önceden hesaplanmış embedding,
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

# Geçici gerçek pgvector servisi
docker compose -f evaluation\pgvector\compose.yaml up -d --wait
.\.venv\Scripts\python.exe -m scripts.run_pgvector_benchmark
docker compose -f evaluation\pgvector\compose.yaml down
```

Nihai birleşik çıktılar
`evaluation/results/quality-latest/` klasöründedir.
