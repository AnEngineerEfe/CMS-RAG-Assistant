# CMS-RAG Kalite ve Bileşen Karşılaştırması

## 1. Aşama — Chunk Kalitesi

- Değerlendirilen: **77/77**
- Kabul oranı: **100.0%**
- Geçersiz judge çıktısı: **0**

## 2. Aşama — Bağımsız Cevap Hakemi

- Değerlendirilen pozitif cevap: **30**
- Katı başarı: **30/30**
- Katı başarı oranı: **100.0%**

## 3. Aşama — Retrieval Karşılaştırması

| Yaklaşım | Chunk | Adet | Hit@6 | MRR | Terim | P50 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 450 | 136 | 100.0% | 0.933 | 96.7% | 1.1 |
| faiss_dense | 450 | 136 | 90.0% | 0.682 | 90.0% | 43.7 |
| hybrid_rrf | 450 | 136 | 100.0% | 0.851 | 96.7% | 49.9 |
| bm25 | 900 | 67 | 100.0% | 0.906 | 100.0% | 0.9 |
| faiss_dense | 900 | 67 | 90.0% | 0.758 | 91.7% | 38.3 |
| hybrid_rrf | 900 | 67 | 100.0% | 0.836 | 100.0% | 37.6 |
| hybrid_rrf_reranker | 900 | 67 | 100.0% | 0.836 | 100.0% | 1646.1 |
| hybrid_rrf_evidence_gate | 900 | 67 | 100.0% | 0.836 | 100.0% | 1919.1 |
| bm25 | 1350 | 48 | 100.0% | 0.867 | 100.0% | 1.0 |
| faiss_dense | 1350 | 48 | 93.3% | 0.739 | 91.7% | 83.3 |
| hybrid_rrf | 1350 | 48 | 96.7% | 0.856 | 96.7% | 42.8 |

## 4. Aşama — FAISS / pgvector

- Aynı ilk-K sıralama oranı: **100.0%**
- FAISS Hit@6 / MRR: **90.0% / 0.750**
- pgvector Hit@6 / MRR: **90.0% / 0.750**
- Ortalama yalnız-arama gecikmesi: FAISS **0.35 ms**, pgvector **0.58 ms**

LLM hakemi tek başına mutlak doğruluk değildir; altın belge/sayfa, deterministik terim kontrolleri ve confusion matrix ile birlikte yorumlanır.
