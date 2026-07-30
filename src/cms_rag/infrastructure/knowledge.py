"""Önceden küratörlenmiş yerel PDF bilgi tabanını manifest üzerinden yükler."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import Chunk
from .ingest import PDFIngestor
from .retrieval import HybridRetriever


def load_manifest(knowledge_root: Path) -> dict:
    """Bilgi tabanı manifestini doğrular ve sözlük olarak döndürür."""

    manifest_path = knowledge_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Desteklenmeyen bilgi tabanı manifest şeması.")
    if not isinstance(manifest.get("sources"), list):
        raise ValueError("Bilgi tabanı manifestinde sources listesi bulunamadı.")
    return manifest


def manifest_paths(data_dir: Path) -> list[Path]:
    """Manifestteki kaynak yollarını güvenli biçimde data dizini altında çözer."""

    knowledge_root = data_dir / "knowledge_base"
    data_root = data_dir.resolve()
    paths: list[Path] = []
    for record in load_manifest(knowledge_root)["sources"]:
        candidate = (data_dir / record["path"]).resolve()
        if data_root not in candidate.parents:
            raise ValueError("Bilgi tabanı kaynağı data dizini dışına çıkamaz.")
        paths.append(candidate)
    return paths


def load_curated_chunks(data_dir: Path) -> list[Chunk]:
    """Her PDF'i manifestteki koleksiyon, otorite ve URL bilgisiyle parçalar."""

    knowledge_root = data_dir / "knowledge_base"
    manifest = load_manifest(knowledge_root)
    data_root = data_dir.resolve()
    chunks: list[Chunk] = []
    ingestor = PDFIngestor()
    for record in manifest["sources"]:
        path = (data_dir / record["path"]).resolve()
        if data_root not in path.parents or not path.exists():
            raise FileNotFoundError(f"Bilgi tabanı kaynağı bulunamadı: {path}")
        document_chunks = ingestor.load(
            [path],
            collection=record["collection"],
            authority=record["authority"],
        )
        source_url = record.get("source_url", "")
        chunks.extend(
            [
                Chunk(
                    text=chunk.text,
                    document=chunk.document,
                    page=chunk.page,
                    source_path=chunk.source_path,
                    collection=chunk.collection,
                    authority=chunk.authority,
                    source_url=source_url,
                )
                for chunk in document_chunks
            ]
        )
    return chunks


def supplemental_document_paths(data_dir: Path, snapshot_dir: Path) -> list[Path]:
    """Snapshot'ta bulunmayan kullanıcı PDF'lerini ek belge olarak ayırır."""

    included_hashes = HybridRetriever.snapshot_source_hashes(snapshot_dir)
    return [
        path
        for path in sorted((data_dir / "documents").glob("*.pdf"))
        if HybridRetriever.file_sha256(path) not in included_hashes
    ]
