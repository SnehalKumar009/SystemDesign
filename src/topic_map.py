"""Build a cross-book concept taxonomy (topic map) from chapter titles."""
from __future__ import annotations

from rich.console import Console

from .config import Config, load_config
from .corpus import load_books
from .llm import local_chat
from .manifest import Manifest
from .util import ensure_dir, extract_json_block, save_json, slugify
from . import progress as progress_mod

console = Console()

_SYSTEM = (
    "You are a curriculum designer. You organize source material about {domain} "
    "into a clean, de-duplicated list of teachable concepts. Respond with JSON only."
)

_PROMPT = """\
Goal: {goal}

Below are chapters from several books about {domain}. Each chapter lists its
sub-section headings and a short opening excerpt so you can see the sub-topics it
covers. Build a consolidated, GRANULAR concept map.

Rules:
- Produce 35-50 canonical concepts. Favor granularity: treat distinct sub-topics as
  separate concepts (e.g. replication, partitioning, and transactions/isolation are
  three separate concepts, not one "data storage" concept).
- Use the per-chapter "sections" as candidate concepts; promote meaningful sub-topics
  into their own concept rather than folding them into a broad umbrella.
- Merge only TRUE duplicates across books; never collapse genuinely distinct sub-topics.
- For each concept, list which book+chapter(s) teach it (only ones that actually do).
- Give an ordered "prereqs" list (names of other concepts that should be learned first).
- Order concepts foundational -> advanced.

Chapters:
{chapters}

Return JSON:
{{"concepts": [
  {{"name": "Concept name",
    "summary": "one sentence",
    "sources": [{{"book": "Book title", "chapter": "Chapter title"}}],
    "prereqs": ["Other concept name"]}}
]}}
"""


def _snippet(text: str, max_chars: int = 500) -> str:
    """Collapse whitespace and return the first ``max_chars`` of chapter text."""
    snippet = " ".join((text or "").split())[:max_chars]
    return snippet + "..." if len(snippet) == max_chars else snippet


def _chapters_blob(books: list[dict]) -> str:
    lines = []
    for b in books:
        lines.append(f"# Book: {b['book']}")
        for ch in b["chapters"]:
            lines.append(f"  - {ch['title']}")
            sections = ch.get("sections") or []
            if sections:
                lines.append("      sections: " + "; ".join(sections))
            snippet = _snippet(ch.get("text", ""))
            if snippet:
                lines.append(f"      excerpt: {snippet}")
    return "\n".join(lines)


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    books = load_books(cfg)
    if not books:
        console.print("[yellow]No extracted books; run extract first.[/]")
        return

    console.print("[cyan]building topic map[/] ...")
    system = _SYSTEM.format(domain=cfg.domain)
    prompt = _PROMPT.format(domain=cfg.domain, goal=cfg.goal, chapters=_chapters_blob(books))
    raw = local_chat(prompt, system=system, cfg=cfg)
    data = extract_json_block(raw)

    concepts = data.get("concepts", [])
    for c in concepts:
        c["slug"] = slugify(c["name"])

    out_dir = ensure_dir(cfg.path("output"))
    save_json(out_dir / "topic_map.json", {"domain": cfg.domain, "concepts": concepts})
    _write_md(out_dir / "topic_map.md", cfg, concepts)

    # Track concept->books in the manifest; invalidate downstream work on change.
    manifest = Manifest(cfg)
    for c in concepts:
        book_names = sorted({s["book"] for s in c.get("sources", [])})
        manifest.set_concept_sources(c["slug"], book_names)

    # Drop artifacts for concepts that no longer exist in the regenerated map.
    valid_slugs = {c["slug"] for c in concepts}
    manifest.prune_concepts(valid_slugs)
    manifest.save()
    _prune_stale_files(cfg, valid_slugs)
    progress_mod.prune([c["name"] for c in concepts], cfg)

    progress_mod.seed(concepts, cfg)
    console.print(f"[green]{len(concepts)} concepts mapped -> output/topic_map.md[/]")


def _prune_stale_files(cfg: Config, valid_slugs: set[str]) -> None:
    """Remove per-concept output files whose slug is no longer in the map."""
    targets = [
        (cfg.path("output") / "notes", "*.md"),
        (cfg.path("output") / "questions", "*.md"),
        (cfg.path("data") / "cards", "*.json"),
    ]
    for directory, pattern in targets:
        if not directory.exists():
            continue
        for path in directory.glob(pattern):
            if path.stem not in valid_slugs:
                path.unlink()
                console.print(f"[yellow]pruned stale {path.relative_to(cfg.path('output').parent)}[/]")


def _write_md(path, cfg: Config, concepts: list[dict]) -> None:
    lines = [f"# {cfg.domain} — Concept Map", ""]
    for c in concepts:
        lines.append(f"## {c['name']}")
        if c.get("summary"):
            lines.append(f"_{c['summary']}_")
        srcs = ", ".join(f"{s['book']} — {s['chapter']}" for s in c.get("sources", []))
        lines.append(f"- **Sources:** {srcs or 'n/a'}")
        if c.get("prereqs"):
            lines.append(f"- **Prereqs:** {', '.join(c['prereqs'])}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
