# 20 Vakalık Bağımsız Chunk-Köken RAG Değerlendirmesi

## Model rolleri

- Soru üreten büyük model: `OpenAI Codex büyük model · geliştirme zamanı`
- RAG cevabını üreten küçük/kapalı model: `qwen2.5:3b`
- Chunk kökenini bağımsız oturumda değerlendiren büyük model: `qwen2.5:7b`
- Yoğun retrieval backend'i: `pgvector`
- Yoğun vektör araması: `PostgreSQL pgvector exact cosine (<=>)`
- Çalışma anında internet: `kapalı`

## Confusion matrix

| Gerçek \ Tahmin | Pozitif (cevap verdi) | Negatif (güvenli ret) |
|---|---:|---:|
| Pozitif (bilgi mevcut) | TP = **12** | FN = **4** |
| Negatif (bilgi mevcut değil) | FP = **0** | TN = **4** |

## Sonuçlar

- Toplam vaka: **20**
- Accuracy: **80.0%**
- Precision: **100.0%**
- Recall: **75.0%**
- Specificity: **100.0%**
- F1: **85.7%**
- Başlangıç chunkıyla bağımsız hakem eşleşmesi: **14/16**
- Katı uçtan uca başarı: **11/16**
- Geçersiz vaka: **0**

Pozitif vaka soruları, yalnız kaynak chunk verilerek Codex büyük modelle geliştirme
zamanında üretilmiş, insan tarafından kapsam kontrolünden geçirilmiş ve sürümlenmiştir.
Küçük model yalnız yerel RAG bilgi tabanını kullanarak bağımsız oturumda cevaplar.
Büyük hakem yeni bir oturumda yalnız retrieval adaylarını görür ve cevabı destekleyen
chunk kimliklerini seçer. Katı başarı; cevap verilmesi, hakem desteği, retrieval içinde
başlangıç chunkının bulunması ve hakemin aynı chunkı seçmesini birlikte gerektirir.
