# CMS-RAG Assistant

Yerel calisan, kaynak gosteren Combat Management System (CMS) dokuman asistani.

## Baslatma

```powershell
.\.venv\Scripts\Activate.ps1
ollama serve
streamlit run app.py
```

Ilk kullanimda sol panelden resmi PDF dokumanini yukleyin. Sistem PDF metnini
sayfa bilgisiyle isler, ayni dosyayi SHA-256 ile engeller ve yerel bilgi tabanini
yeniden kurar.

## Mimari

`PDF -> sayfa metni -> parcalama -> semantic (FAISS) + BM25 -> rerank -> Ollama -> kaynaklar`

Tum veriler `data/documents` altinda yerelde tutulur. Harici web taramasi veya
bulut API'si kullanilmaz.
