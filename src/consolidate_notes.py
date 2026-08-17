"""Consolidated per-concept notes that merge all books (cloud LLM)."""
from __future__ import annotations

from rich.console import Console

from .config import Config, load_config
from .build_index import query
from .llm import cloud_chat
from .manifest import Manifest
from .util import ensure_dir, load_json

console = Console()

_SYSTEM = (
    "You are an expert {domain} teacher and technical writer. You synthesize multiple "
    "sources into one authoritative, interview-ready study note. Be precise and concrete."
)

_PROMPT = """\
Concept: {concept}
Domain: {domain}

Below are passages about this concept drawn from different books. Synthesize ONE
consolidated note in Markdown with these sections:

1. **Core definition** — the consensus across sources.
2. **What each book emphasizes** — attribute insights per book ("<Book> stresses ...").
3. **Conflicts / differing views** — flag where sources disagree (or say "none noted").
4. **Trade-offs**.
5. **Failure modes / what can go wrong**.
6. **Interview angle** — how this is tested and how to answer well.
7. **When NOT to use it**.
8. A small Mermaid diagram (```mermaid) if it aids understanding.

Only use the passages plus well-established knowledge; do not invent book-specific claims.

Passages:
{passages}
"""


def _gather(concept: dict, cfg: Config) -> str:
    per_book = cfg["consolidation"]["passages_per_book"]
    books = sorted({s["book"] for s in concept.get("sources", [])})
    blocks = []
    for book in books:
        hits = query(concept["name"], book=book, n=per_book, cfg=cfg)
        for h in hits:
            blocks.append(f"[{book} — {h.get('chapter','?')}]\n{h['text']}")
    return "\n\n---\n\n".join(blocks) if blocks else "(no passages retrieved)"


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    tm = load_json(cfg.path("output") / "topic_map.json")
    if not tm:
        console.print("[yellow]No topic map; run topicmap first.[/]")
        return

    notes_dir = ensure_dir(cfg.path("output") / "notes")
    manifest = Manifest(cfg)
    system = _SYSTEM.format(domain=cfg.domain)

    for concept in tm["concepts"]:
        slug = concept["slug"]
        if not force and not manifest.needs(slug, "notes"):
            console.print(f"[dim]skip note (up to date): {concept['name']}[/]")
            continue
        console.print(f"[cyan]note[/] {concept['name']}")
        passages = _gather(concept, cfg)
        prompt = _PROMPT.format(concept=concept["name"], domain=cfg.domain, passages=passages)
        note = cloud_chat(prompt, system=system, cfg=cfg)
        header = f"# {concept['name']}\n\n_Consolidated from: " + ", ".join(
            sorted({s["book"] for s in concept.get("sources", [])})
        ) + "_\n\n"
        (notes_dir / f"{slug}.md").write_text(header + note, encoding="utf-8")
        manifest.mark(slug, "notes")
        manifest.save()

    console.print("[green]notes up to date.[/]")
