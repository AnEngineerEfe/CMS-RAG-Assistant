# CMS-RAG Assistant

Yerelde calisan, kaynak kaniti gosteren CMS dokuman asistani.

## Calistirma

```powershell
.\.venv\Scripts\Activate.ps1
ollama serve
ollama pull qwen2.5:7b
streamlit run app.py
```

Varsayilan model `qwen2.5:7b`'dir. Daha dusuk donanimli bilgisayarlarda
istege bagli olarak daha kucuk bir yerel model secilebilir:

```powershell
$env:CMS_RAG_OLLAMA_MODEL="qwen2.5:7b"
streamlit run app.py
```

## Veri kurallari

- `data/raw/havelsan/`: resmi kaynaklar ve kullanici PDF yuklemeleri
- `data/raw/open_source/`: onayli kamu kaynaklari
- PDF'ler SHA-256 icerigiyle tekillestirilir; ayni icerik ikinci kez indekslenmez.
- Kaynak, koleksiyon, yetki seviyesi ve sayfa bilgisi yanitta gorunur.

Kabul degerlendirmesi:

```powershell
python -m scripts.evaluate_retrieval
python -m unittest discover -s tests -v
```
