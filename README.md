# CMS-RAG Assistant

Yerel çalışacak şekilde tasarlanmış, kaynak gösteren bir Combat Management
System bilgi asistanı. Resmî HAVELSAN içeriği ile kamu/açık kaynak referansları
ayrı indekslenir; istenirse sorgu sırasında birleştirilir ve reranking uygulanır.

1. `pip install -r requirements.txt`
2. `ollama pull qwen2.5:3b`
3. Onaylı kamu kaynakları için `python scripts/sync_sources.py`
4. `streamlit run app.py`

Hassas belgeleri yalnızca izinli, ağdan yalıtılmış ortamda
`data/raw/havelsan/` altında saklayın. Kamu kaynakları `data/raw/open_source/`
altında tutulur.
