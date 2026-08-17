"""Mastery tracker (0-6 per concept) stored in progress.yaml."""
from __future__ import annotations

import yaml

from .config import Config, load_config

LEVELS = {
    0: "Never heard of it",
    1: "Recognize the term",
    2: "Can explain it",
    3: "Can implement it",
    4: "Can design with it",
    5: "Can defend trade-offs",
    6: "Can teach it",
}


def _load(cfg: Config) -> dict:
    path = cfg.path("progress")
    if not path.exists():
        return {"scores": {}}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"scores": {}}


def _save(cfg: Config, data: dict) -> None:
    path = cfg.path("progress")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=True, allow_unicode=True)


def seed(concepts: list[dict], cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    data = _load(cfg)
    scores = data.setdefault("scores", {})
    for c in concepts:
        scores.setdefault(c["name"], 0)
    _save(cfg, data)


def set_score(name: str, score: int, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    score = max(0, min(6, score))
    data = _load(cfg)
    data.setdefault("scores", {})[name] = score
    _save(cfg, data)


def weak_topics(limit: int = 10, cfg: Config | None = None) -> list[str]:
    cfg = cfg or load_config()
    scores = _load(cfg).get("scores", {})
    return [n for n, _ in sorted(scores.items(), key=lambda kv: kv[1])[:limit]]


def run(cfg: Config | None = None) -> None:
    """Print the current mastery table."""
    from rich.console import Console
    from rich.table import Table

    cfg = cfg or load_config()
    scores = _load(cfg).get("scores", {})
    table = Table(title=f"{cfg.domain} — Mastery")
    table.add_column("Concept")
    table.add_column("Score", justify="right")
    table.add_column("Meaning")
    for name, s in sorted(scores.items(), key=lambda kv: kv[1]):
        table.add_row(name, str(s), LEVELS.get(s, ""))
    Console().print(table)
