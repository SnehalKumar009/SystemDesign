"""Tracks per-PDF content hashes and per-concept generation state for incremental runs."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .config import Config, load_config
from .util import load_json, save_json


def file_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Manifest:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        self.path = self.cfg.path("manifest")
        self.data = load_json(self.path, default={"books": {}, "concepts": {}})
        self.data.setdefault("books", {})
        self.data.setdefault("concepts", {})

    def save(self) -> None:
        save_json(self.path, self.data)

    # --- books ---
    def book_changed(self, pdf_path: str | Path) -> bool:
        name = Path(pdf_path).name
        rec = self.data["books"].get(name)
        return rec is None or rec.get("hash") != file_hash(pdf_path)

    def mark_extracted(self, pdf_path: str | Path) -> None:
        name = Path(pdf_path).name
        self.data["books"][name] = {
            "hash": file_hash(pdf_path),
            "extracted": True,
            "indexed": False,
        }

    def mark_indexed(self, pdf_name: str) -> None:
        self.data["books"].setdefault(pdf_name, {})["indexed"] = True

    def unindexed_books(self) -> list[str]:
        return [n for n, r in self.data["books"].items() if not r.get("indexed")]

    # --- concepts ---
    def set_concept_sources(self, slug: str, books: list[str]) -> bool:
        """Store which books feed a concept. Returns True if the source set changed."""
        rec = self.data["concepts"].setdefault(slug, {"books": [], "notes": False,
                                                       "questions": False, "cards": False})
        changed = sorted(rec.get("books", [])) != sorted(books)
        rec["books"] = books
        if changed:
            rec["notes"] = rec["questions"] = rec["cards"] = False
        return changed

    def needs(self, slug: str, stage: str) -> bool:
        rec = self.data["concepts"].get(slug, {})
        return not rec.get(stage, False)

    def mark(self, slug: str, stage: str) -> None:
        self.data["concepts"].setdefault(slug, {})[stage] = True

    def invalidate_concepts_for_books(self, changed_books: set[str]) -> None:
        for rec in self.data["concepts"].values():
            if changed_books.intersection(rec.get("books", [])):
                rec["notes"] = rec["questions"] = rec["cards"] = False
