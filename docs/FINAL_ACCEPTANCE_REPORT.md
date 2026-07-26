# Nihai Kabul Raporu

Tarih: 2026-07-26

## Sonuç

CMS-RAG Assistant; kod, veri, retrieval, yerel üretim, Streamlit arayüzü,
temiz-Git yeniden üretilebilirliği ve canlı kullanıcı yolculuğu katmanlarında
doğrulanmıştır.

## Ölçülen kabul sonuçları

| Kontrol | Sonuç |
|---|---:|
| Otomatik test | 30/30 başarılı |
| Retrieval kabul vakası | 4/4 başarılı |
| İndekslenen chunk | 59 |
| PDF sayfası | 34/34 metinli |
| PDF metin karakteri | 32.129 |
| Boş chunk | 0 |
| Geçersiz sayfa meta verisi | 0 |
| Eksik kaynak yolu | 0 |
| Streamlit health | HTTP 200 |
| Streamlit root | HTTP 200 |
| 8501 dinleyici sayısı | 1 |
| Varsayılan model | qwen2.5:3b |

## Temiz Git arşivi

`git archive HEAD` ile oluşturulan bağımsız klasörde:

- çalışma manifestinin arşivde bulunmadığı doğrulandı;
- uygulama manifesti kendisi oluşturdu;
- sürümlenen ADVENT broşürü `advent_cms.pdf` olarak tanındı;
- otomatik testler ve retrieval kabul seti yeniden çalıştırıldı.

## Kaynak doğrulaması

- HAVELSAN ADVENT ürün sayfası erişilebilir ve yerel resmî özet güncel ürün
  bilgileriyle eşleştirilmiştir.
- NATO URL'sinin Digital Transformation Implementation Strategy 2.0 sayfasına
  yönlendiği doğrulanmış; yerel açık-kaynak özet güncel resmî metne göre
  yenilenmiştir.
- Ürün-spesifik resmî iddialar ile genel NATO bağlamı ayrı koleksiyonlarda
  tutulmaktadır.

## Retrieval ve cevap güvenilirliği

- Semantic FAISS, BM25, RRF ve cross-encoder sıralaması birlikte çalışmaktadır.
- Resmî kapsam yalnızca `official`, açık kapsam yalnızca `open_source`
  koleksiyonundan sonuç döndürmüştür.
- Tüm skorların sonlu olduğu doğrulanmıştır.
- Aynı sayfadaki tamamlayıcı parçalar kaybolmadan tek kanıtta birleştirilmiştir.
- Sohbet geçmişi kaynak kapsamına göre izole edilmiştir.
- Resmî ADVENT turundan sonra açık-kaynak NATO sorusu sorulduğunda cevapta
  desteklenmeyen ADVENT ilişkisi oluşmadığı doğrulanmıştır.
- Başarılı cevaplarda metin içi `[SOURCE n]` etiketi zorunludur.

## Hata ve kötüye kullanım testleri

- PDF olmayan içerik reddedilir.
- 200 MB üzerindeki PDF reddedilir.
- Aynı içerik hash'i ikinci kez saklanmaz.
- Bozuk PDF tüm indekslemeyi durdurmaz.
- Manifest yol taşmasıyla depo dışına silme engellenir.
- Ollama hatasında ilgisiz kaynak kartı gösterilmez.
- Kişisel/alan dışı soru kaynak uydurulmadan reddedilir.
- Türkçe karakter bozulması, TODO/gizli anahtar ve tehlikeli dinamik çalıştırma
  kalıpları için statik tarama temizdir.

## Canlı görünür kullanıcı yolculuğu

Aynı Chrome oturumunda:

1. `ADVENT nedir?` resmî kapsamda kaynaklı tamamlandı.
2. Kapsam gerçek seçim olayıyla `open_source` olarak değiştirildi.
3. NATO birlikte çalışabilirlik sorusu yalnızca
   `nato-interoperability.md`, sayfa 1 kaynağıyla cevaplandı.
4. NATO cevabında önceki ADVENT konuşmasından bilgi sızıntısı olmadı.
5. `Ben kimim?` güvenli ret verdi ve kanıt paketi sayısını artırmadı.

## Bağımlılık denetimi

`pip check` sonucu temizdir. `pip-audit` aracı yerel sanal ortama kurulmuştur;
ancak çevrimiçi CVE sorgusu kurulu paket envanterini harici güvenlik servisine
göndereceği için ek açık izin olmadan çalıştırılmamıştır.

## Bilinen mimari sınırlar

- OCR katmanı yoktur.
- Vektör indeks süreç başlangıcında yeniden kurulur.
- Sistem tek kullanıcılı yerel çalışma istasyonunu hedefler.
- Kritik iddialar gösterilen asıl belge ve sayfadan doğrulanmalıdır.
