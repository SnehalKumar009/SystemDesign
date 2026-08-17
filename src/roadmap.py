"""Derive a weekly study roadmap from the topic map's prerequisite ordering."""
from __future__ import annotations

from rich.console import Console

from .config import Config, load_config
from .util import ensure_dir, load_json, slugify

console = Console()


def _topo_order(concepts: list[dict]) -> list[dict]:
    by_name = {c["name"]: c for c in concepts}
    ordered: list[dict] = []
    visited: set[str] = set()
    temp: set[str] = set()

    def visit(name: str):
        if name in visited or name not in by_name:
            return
        if name in temp:  # cycle guard
            return
        temp.add(name)
        for pre in by_name[name].get("prereqs", []):
            visit(pre)
        temp.discard(name)
        visited.add(name)
        ordered.append(by_name[name])

    for c in concepts:  # preserves foundational->advanced hint from topic map
        visit(c["name"])
    return ordered


def run(per_week: int = 4, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    tm = load_json(cfg.path("output") / "topic_map.json")
    if not tm:
        console.print("[yellow]No topic map; run topicmap first.[/]")
        return

    ordered = _topo_order(tm["concepts"])
    lines = [f"# {cfg.domain} — Study Roadmap", "", f"_Goal: {cfg.goal}_", ""]
    for i in range(0, len(ordered), per_week):
        week = i // per_week + 1
        lines.append(f"## Week {week}")
        for c in ordered[i : i + per_week]:
            note = f"output/notes/{slugify(c['name'])}.md"
            lines.append(f"- **{c['name']}** — {c.get('summary','')} ([note]({note}))")
        lines.append("")

    out = ensure_dir(cfg.path("output") / "roadmap")
    (out / "study_plan.md").write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]roadmap -> output/roadmap/study_plan.md ({len(ordered)} concepts)[/]")
