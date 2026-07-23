# Kurumsal Hedef Mimari

## Güven sınırı

`havelsan` ve `open_source` iki bağımsız koleksiyondur. Her belgeye
`collection`, `authority`, `source_path`, `document` ve `page` meta verileri
eklenir. Arayüzde kullanıcı yalnızca resmî koleksiyonu ya da iki koleksiyonun
birleşimini seçer; birleşimde kaynak kimliği yanıta taşınır.

## Sorgu hattı

```text
Soru → koleksiyon seçimi → her koleksiyonda Dense(FAISS) + BM25
     → adayların tekilleştirilmesi → CrossEncoder reranking
     → kaynak etiketli bağlam → yerel Ollama → yanıt + kaynaklar
```

## İşletim kuralları

- `data/source_catalog.json` kaynak envanteridir; rastgele web taraması yoktur.
- İndirme betiği yalnızca katalogdaki HTTPS URL’lerini alır ve erişim zamanını saklar.
- Kısıtlı STANAG/MIL-STD veya lisansı belirsiz materyal indekse eklenmez.
- FAISS yerel seri hâle getirilmiş indeks açarken pickle kullandığından indeks
  klasörü güvenilen, yazma erişimi sınırlı bir dizinde tutulmalıdır.
