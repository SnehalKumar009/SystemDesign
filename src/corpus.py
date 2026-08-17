"""Load extracted book/chapter JSON produced by extract.py."""
from __future__ import annotations

from .config import Config, load_config
from .util import load_json


def load_books(cfg: Config | None = None) -> list[dict]:
    cfg = cfg or load_config()
    extracted = cfg.path("extracted")
    books = [load_json(p) for p in sorted(extracted.glob("*.json"))]
    return [b for b in books if b]


def iter_chapters(cfg: Config | None = None):
    for book in load_books(cfg):
        for ch in book["chapters"]:
            yield book, ch
