# CMS-RAG Kalite ve Bileşen Karşılaştırması

## 1. Aşama — Chunk Kalitesi

- Değerlendirilen: **67/67**
- Kabul oranı: **100.0%**
- Geçersiz judge çıktısı: **0**

## 2. Aşama — Bağımsız Cevap Hakemi

- Değerlendirilen pozitif cevap: **23**
- Katı başarı: **23/23**
- Katı başarı oranı: **100.0%**

## 3. Aşama — Retrieval Karşılaştırması

| Yaklaşım | Chunk | Adet | Hit@6 | MRR | Terim | P50 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 450 | 136 | 100.0% | 0.935 | 95.7% | 2.3 |
| faiss_dense | 450 | 136 | 91.3% | 0.692 | 91.3% | 52.7 |
| hybrid_rrf | 450 | 136 | 100.0% | 0.857 | 95.7% | 45.2 |
| bm25 | 900 | 67 | 100.0% | 0.899 | 100.0% | 1.4 |
| faiss_dense | 900 | 67 | 91.3% | 0.808 | 93.5% | 47.7 |
| hybrid_rrf | 900 | 67 | 100.0% | 0.884 | 100.0% | 45.6 |
| hybrid_rrf_reranker | 900 | 67 | 100.0% | 0.627 | 100.0% | 4901.6 |
| hybrid_rrf_evidence_gate | 900 | 67 | 100.0% | 0.884 | 100.0% | 1714.1 |
| bm25 | 1350 | 48 | 100.0% | 0.826 | 100.0% | 1.0 |
| faiss_dense | 1350 | 48 | 95.7% | 0.768 | 93.5% | 39.3 |
| hybrid_rrf | 1350 | 48 | 95.7% | 0.891 | 95.7% | 34.4 |

## 4. Aşama — FAISS / pgvector

- Aynı ilk-K sıralama oranı: **100.0%**
- FAISS Hit@6 / MRR: **91.3% / 0.808**
- pgvector Hit@6 / MRR: **91.3% / 0.808**
- Ortalama yalnız-arama gecikmesi: FAISS **0.84 ms**, pgvector **3.02 ms**

LLM hakemi tek başına mutlak doğruluk değildir; altın belge/sayfa, deterministik terim kontrolleri ve confusion matrix ile birlikte yorumlanır.
