from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import UploadResult


class DocumentStore:
    """Content-addressed local document repository with an auditable manifest."""

    _MANIFEST_NAME = "manifest.json"
    MAX_PDF_BYTES = 200 * 1024 * 1024

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._backfill_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.root / self._MANIFEST_NAME

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _safe_filename(name: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
        return clean or "document.pdf"

    def save_uploads(self, files) -> UploadResult:
        manifest = self._read_manifest()
        existing_hashes = {record["sha256"] for record in manifest["documents"]}
        added: list[str] = []
        duplicates: list[str] = []
        rejected: list[str] = []
        for uploaded in files:
            data = uploaded.getvalue()
            if not data.startswith(b"%PDF-") or len(data) > self.MAX_PDF_BYTES:
                rejected.append(uploaded.name)
                continue
            digest = self._hash(data)
            if digest in existing_hashes:
                duplicates.append(uploaded.name)
                continue
            storage_name = f"{digest}_{self._safe_filename(uploaded.name)}"
            (self.root / storage_name).write_bytes(data)
            manifest["documents"].append({
                "sha256": digest,
                "storage_name": storage_name,
                "display_name": uploaded.name,
                "size_bytes": len(data),
                "source_type": "user_uploaded_pdf",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            })
            existing_hashes.add(digest)
            added.append(uploaded.name)
        self._write_manifest(manifest)
        return UploadResult(added=added, duplicates=duplicates, rejected=rejected)

    def pdfs(self) -> list[Path]:
        return sorted(self.root.glob("*.pdf"))

    def records(self) -> list[dict]:
        return list(self._read_manifest()["documents"])

    def delete(self, sha256: str) -> bool:
        manifest = self._read_manifest()
        record = next((item for item in manifest["documents"] if item["sha256"] == sha256), None)
        if not record:
            return False
        path = self._storage_path(record["storage_name"])
        if path.exists():
            path.unlink()
        manifest["documents"] = [item for item in manifest["documents"] if item["sha256"] != sha256]
        self._write_manifest(manifest)
        return True

    def display_name(self, path: Path) -> str:
        record = next((item for item in self.records() if item["storage_name"] == path.name), None)
        return record["display_name"] if record else re.sub(r"^[a-f0-9]{64}_", "", path.name)

    def _backfill_manifest(self) -> None:
        manifest = self._read_manifest()
        known = {item["storage_name"] for item in manifest["documents"]}
        changed = False
        for path in self.pdfs():
            if path.name not in known:
                data = path.read_bytes()
                manifest["documents"].append({
                    "sha256": self._hash(data),
                    "storage_name": path.name,
                    "display_name": re.sub(r"^[a-f0-9]{64}_", "", path.name),
                    "size_bytes": len(data),
                    "source_type": "existing_local_pdf",
                    "ingested_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                })
                changed = True
        if changed:
            self._write_manifest(manifest)

    def _read_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"schema_version": 1, "documents": []}
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"schema_version": 1, "documents": []}
        if not isinstance(manifest, dict) or not isinstance(manifest.get("documents"), list):
            return {"schema_version": 1, "documents": []}
        return manifest

    def _write_manifest(self, manifest: dict) -> None:
        temporary = self.root / f".{self._MANIFEST_NAME}.tmp"
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.manifest_path)

    def _storage_path(self, storage_name: str) -> Path:
        """Resolve a manifest path without permitting traversal outside the store."""
        root = self.root.resolve()
        candidate = (root / storage_name).resolve()
        if candidate.parent != root:
            raise ValueError("Manifest contains an unsafe storage path.")
        return candidate
