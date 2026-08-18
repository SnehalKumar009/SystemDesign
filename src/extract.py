"""Extract PDFs in SOURCE/ into per-book chapter JSON. Incremental via manifest."""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from rich.console import Console

from .config import Config, load_config
from .manifest import Manifest
from .util import ensure_dir, save_json, slugify

console = Console()

_CHAPTER_RE = re.compile(r"^\s*(chapter\s+\d+|part\s+\d+|\d+\.\s+\S)", re.IGNORECASE)


def _extract_images(doc: "fitz.Document", pstart: int, pend: int) -> str:
    """TODO: images are not yet handled — only the text layer is extracted.

    Planned: pull page images via ``page.get_images`` / ``page.get_pixmap``,
    then OCR (pytesseract) or caption them with a vision LLM, and append the
    resulting text to the chapter so diagrams/figures feed into chunking,
    embeddings, notes and the tutor. Returns "" until implemented.
    """
    return ""


def _chapters_from_toc(doc: "fitz.Document") -> list[dict]:
    toc = doc.get_toc(simple=True)  # [level, title, page]
    tops = [(t, p) for lvl, t, p in toc if lvl == 1 and p >= 1]
    if len(tops) < 2:
        return []
    # Sub-headings (TOC levels 2-3) expose per-chapter sub-topics to the topic map.
    subs = [(t, p) for lvl, t, p in toc if lvl in (2, 3) and p >= 1]
    chapters = []
    for i, (title, start) in enumerate(tops):
        end = tops[i + 1][1] - 1 if i + 1 < len(tops) else doc.page_count
        start_idx = max(0, start - 1)
        text = "\n".join(doc[p].get_text() for p in range(start_idx, min(end, doc.page_count)))
        sections = [t.strip() for t, p in subs if start <= p <= end]
        chapters.append({
            "index": i + 1,
            "title": title.strip(),
            "sections": sections,
            "text": text,
            "page_start": start,
            "page_end": end,
        })
    return chapters


def _chapters_from_headings(doc: "fitz.Document") -> list[dict]:
    """Fallback when no usable TOC: split on chapter-like heading lines."""
    boundaries: list[tuple[int, str]] = []
    for pno in range(doc.page_count):
        for line in doc[pno].get_text().splitlines()[:6]:
            if _CHAPTER_RE.match(line):
                boundaries.append((pno, line.strip()))
                break
    if len(boundaries) < 2:
        return _fixed_windows(doc)
    chapters = []
    for i, (pstart, title) in enumerate(boundaries):
        pend = boundaries[i + 1][0] if i + 1 < len(boundaries) else doc.page_count
        text = "\n".join(doc[p].get_text() for p in range(pstart, pend))
        chapters.append({
            "index": i + 1,
            "title": title,
            "sections": [],
            "text": text,
            "page_start": pstart + 1,
            "page_end": pend,
        })
    return chapters


def _fixed_windows(doc: "fitz.Document", pages_per: int = 20) -> list[dict]:
    chapters = []
    for i, start in enumerate(range(0, doc.page_count, pages_per)):
        end = min(start + pages_per, doc.page_count)
        text = "\n".join(doc[p].get_text() for p in range(start, end))
        chapters.append({
            "index": i + 1,
            "title": f"Section {i + 1} (pp. {start + 1}-{end})",
            "sections": [],
            "text": text,
            "page_start": start + 1,
            "page_end": end,
        })
    return chapters


def extract_pdf(pdf_path: Path) -> dict:
    doc = fitz.open(pdf_path)
    chapters = _chapters_from_toc(doc) or _chapters_from_headings(doc)
    doc.close()
    return {
        "book": pdf_path.stem,
        "slug": slugify(pdf_path.stem),
        "path": str(pdf_path.name),
        "chapters": chapters,
    }


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    source = cfg.path("source")
    out_dir = ensure_dir(cfg.path("extracted"))
    manifest = Manifest(cfg)

    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]No PDFs found in {source}[/].")
        return

    for pdf in pdfs:
        if not force and not manifest.book_changed(pdf):
            console.print(f"[dim]skip (unchanged): {pdf.name}[/]")
            continue
        console.print(f"[cyan]extracting[/] {pdf.name}")
        data = extract_pdf(pdf)
        save_json(out_dir / f"{data['slug']}.json", data)
        manifest.mark_extracted(pdf)
        n_sections = sum(len(ch.get("sections", [])) for ch in data["chapters"])
        console.print(f"  -> {len(data['chapters'])} chapters, {n_sections} sections")

    manifest.save()
