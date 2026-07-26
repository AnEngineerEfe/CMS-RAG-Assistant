# CMS-RAG Nihai Teslimatlar

## Dosyalar

- `CMS-RAG_Nihai_Teknik_Dokumantasyon.docx`  
  Projenin amacı, kapsamı, veri güven modeli, katmanlı mimarisi, belge yaşam
  döngüsü, hibrit RAG hattı, yerel model davranışı, güvenlik, kullanıcı arayüzü,
  kurulum, test kanıtları, Git akışı, sorun giderme, yol haritası, sunum planı ve
  terimler sözlüğünü kapsayan nihai Word belgesidir.

- `CMS-RAG_Nihai_Proje_Sunumu.pptx`  
  16:9 oranında, 17 slayttan oluşan sunum dosyasıdır. Mimari, RAG pipeline,
  güven modeli, konuşma izolasyonu, test skorları, Git akışı, kurulum, yol
  haritası ve canlı demo senaryosu yerleşik şekil ve diyagramlarla anlatılır.

## Sunum önerisi

Normal anlatım için 12–15 dakika, canlı demo için ayrıca 3 dakika ayırın.
Demo sırası:

1. `ADVENT nedir?`
2. `Örnekleri var mı?`
3. `Bunların görevleri nelerdir?`
4. Kapsamı açık/kamu yaparak NATO birlikte çalışabilirlik sorusu
5. `Ben kimim?` ile güvenli ret

## Yeniden üretim

```powershell
.\.venv\Scripts\python.exe scripts\generate_final_deliverables.py
```

Betik her iki Office dosyasını yeniden üretir; Word kapsamını, PowerPoint slayt
sayısını, temel anlatı başlıklarını ve slayt sınırı taşmalarını otomatik doğrular.
