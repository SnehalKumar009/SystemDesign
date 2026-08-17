"""Generate mock interview Q&A per concept (local Ollama)."""
from __future__ import annotations

from rich.console import Console

from .config import Config, load_config
from .llm import local_chat
from .manifest import Manifest
from .util import ensure_dir, load_json

console = Console()

_SYSTEM = "You are a senior {domain} interviewer writing practice questions with model answers."

_PROMPT = """\
Domain: {domain}
Concept: {concept}

Using the study note below, write practice interview questions in Markdown.
Include a mix:
- 3 conceptual questions (with follow-ups),
- 2 applied/design questions,
- tag each question difficulty: (easy|medium|hard).
For every question, provide a concise **model answer**.

Study note:
{note}
"""


def _note_text(slug: str, cfg: Config) -> str | None:
    p = cfg.path("output") / "notes" / f"{slug}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    tm = load_json(cfg.path("output") / "topic_map.json")
    if not tm:
        console.print("[yellow]No topic map; run topicmap first.[/]")
        return

    q_dir = ensure_dir(cfg.path("output") / "questions")
    manifest = Manifest(cfg)
    system = _SYSTEM.format(domain=cfg.domain)

    for concept in tm["concepts"]:
        slug = concept["slug"]
        if not force and not manifest.needs(slug, "questions"):
            console.print(f"[dim]skip questions (up to date): {concept['name']}[/]")
            continue
        note = _note_text(slug, cfg) or concept.get("summary", concept["name"])
        console.print(f"[cyan]questions[/] {concept['name']}")
        prompt = _PROMPT.format(domain=cfg.domain, concept=concept["name"], note=note)
        md = local_chat(prompt, system=system, cfg=cfg)
        (q_dir / f"{slug}.md").write_text(f"# {concept['name']} — Q&A\n\n{md}", encoding="utf-8")
        manifest.mark(slug, "questions")
        manifest.save()

    console.print("[green]questions up to date.[/]")
