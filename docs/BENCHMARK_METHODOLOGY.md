# RAG Benchmark Metodolojisi

## Kapsam ve veri sınırı

Bu çalışma, HAVELSAN'ın deniz savaş yönetim sistemleri alanındaki kamuya açık
çalışma ve ürünleri ile yapay zekâ entegrasyonu süreçlerine yönelik hazırlanmış
bir ön çalışma ve araştırmadır. Şirket içi veri, tasnifli bilgi, kişisel veri veya
yetkisiz kaynak kullanılmaz. Sonuçlar operasyonel karar desteği ya da ürün
sertifikasyonu anlamına gelmez.

Normal uygulama çalışırken internet araştırması yapılmaz. Belgeler geliştirme ve
kurasyon aşamasında doğrulanır, PDF bilgi paketine dönüştürülür, chunk'lanır ve
embedding snapshot'ı önceden üretilir.

## Altın veri seti

`evaluation/datasets/gold_cases.json` sürümlü ve makinece doğrulanan ana kabul
setidir. Mevcut sürüm 20 konu kategorisinde 45 vaka içerir:

- 30 pozitif vaka: cevap için gerekli veri bilgi tabanında vardır.
- 15 negatif vaka: istenen bilgi yoktur veya kamu veri sınırının dışındadır.
- Doğrudan, paraphrase ve negatif sorgu türleri birlikte ölçülür.
- Her pozitif vakada beklenen belge, sayfa ve kanıt terimleri bulunur.

Altın etiketler mevcut snapshot'taki gerçek metinle otomatik karşılaştırılır.
Böylece kaynakta bulunmayan bir terim yanlışlıkla başarı ölçütü yapılamaz.

## Ölçüm hattı

Her soru, uygulamanın kullandığı gerçek üretim hattından geçer:

```text
Türkçe sorgu
  → kontrollü teknik terim genişletme
  → FAISS semantik adayları + BM25 sözcüksel adayları
  → Reciprocal Rank Fusion
  → cross-encoder reranking
  → tam terim eşleşmeli sayfa koruması
  → cevaplanabilirlik kararı
  → belge/sayfa/kanıt terimi karşılaştırması
```

Olumlu vaka ancak şu üç koşul birlikte sağlandığında geçer:

1. Sistem soruyu cevaplanabilir olarak sınıflandırır.
2. Altın belge ve sayfalardan en az biri ilk altı sonuçta bulunur.
3. Beklenen kanıt terimlerinin tamamı getirilen kanıt paketinde yer alır.

Negatif vaka, sistem cevap üretmek yerine kanıt yetersizliği kararı verdiğinde
geçer. Gizli veya tasnifli yapılandırma talepleri kamu veri sınırı nedeniyle
reddedilir.

## Raporlanan metrikler

- TP, TN, FP, FN confusion matrix
- Accuracy, precision, recall, specificity ve F1
- Hit@6
- Mean Reciprocal Rank (MRR)
- Ortalama, p50 ve p95 retrieval gecikmesi
- Kategori, sorgu türü ve zorluk kırılımları
- Her vaka için getirilen dosya, sayfa ve reranker puanı

## Tekrarlama

```powershell
$env:CMS_RAG_OFFLINE="1"
.\.venv\Scripts\python.exe -m scripts.run_benchmark
```

Makinece işlenebilir ayrıntı
`evaluation/results/latest/benchmark_report.json`, sunum özeti ise
`evaluation/results/latest/SUMMARY.md` dosyasına yazılır. Herhangi bir vaka
başarısızsa komut sıfırdan farklı çıkış kodu döndürür.

## Son ölçüm ve yorumlama

2026-08-06 tarihli 45 vakalık kabul turunda 45 vaka geçti; TP/TN/FP/FN
`30/15/0/0`, Hit@6 `%100`, MRR `0,8361`, ortalama retrieval gecikmesi
`1500,2 ms`, p95 gecikmesi `1968,5 ms` ölçüldü.

Bu yüzde yüz sonuç yalnızca sürümlenmiş 45 vakalık set için geçerlidir. Yeni
belgeler, soru biçimleri ve alanlar eklendikçe veri seti genişletilmeli; sonuç
genel veya sınırsız bir doğruluk iddiası olarak sunulmamalıdır.
