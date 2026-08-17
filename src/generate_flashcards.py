"""Generate Anki flashcards (CSV + .apkg) from consolidated notes (local Ollama)."""
from __future__ import annotations

import csv

from rich.console import Console

from .config import Config, load_config
from .llm import local_chat
from .manifest import Manifest
from .util import ensure_dir, extract_json_block, load_json, save_json, slugify

console = Console()

_SYSTEM = "You extract atomic spaced-repetition flashcards. Respond with JSON only."

_PROMPT = """\
Domain: {domain}
Concept: {concept}

From the note below, produce 5-10 atomic flashcards. Each card: one focused question
and a short, self-contained answer. Return JSON:
{{"cards": [{{"q": "...", "a": "..."}}]}}

Note:
{note}
"""


def _cards_for(concept: dict, cfg: Config) -> list[dict]:
    slug = concept["slug"]
    note_path = cfg.path("output") / "notes" / f"{slug}.md"
    note = note_path.read_text(encoding="utf-8") if note_path.exists() else concept.get(
        "summary", concept["name"]
    )
    prompt = _PROMPT.format(domain=cfg.domain, concept=concept["name"], note=note)
    data = extract_json_block(local_chat(prompt, system=_SYSTEM, cfg=cfg))
    return [{"q": c["q"], "a": c["a"], "concept": concept["name"]} for c in data.get("cards", [])]


def _build_deck(cfg: Config, all_cards: list[dict]) -> None:
    import genanki

    out = ensure_dir(cfg.path("output") / "flashcards")

    with (out / f"{slugify(cfg.domain)}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "answer", "concept"])
        for c in all_cards:
            writer.writerow([c["q"], c["a"], c["concept"]])

    deck_id = abs(hash(cfg.domain)) % (10**10)
    model = genanki.Model(
        deck_id + 1,
        "Basic-Concept",
        fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "Concept"}],
        templates=[{
            "name": "Card",
            "qfmt": "{{Question}}<br><small>{{Concept}}</small>",
            "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
        }],
    )
    deck = genanki.Deck(deck_id, f"{cfg.domain}")
    for c in all_cards:
        deck.add_note(genanki.Note(model=model, fields=[c["q"], c["a"], c["concept"]]))
    genanki.Package(deck).write_to_file(str(out / f"{slugify(cfg.domain)}.apkg"))


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    tm = load_json(cfg.path("output") / "topic_map.json")
    if not tm:
        console.print("[yellow]No topic map; run topicmap first.[/]")
        return

    cards_dir = ensure_dir(cfg.path("data") / "cards")
    manifest = Manifest(cfg)

    for concept in tm["concepts"]:
        slug = concept["slug"]
        if not force and not manifest.needs(slug, "cards"):
            continue
        console.print(f"[cyan]cards[/] {concept['name']}")
        cards = _cards_for(concept, cfg)
        save_json(cards_dir / f"{slug}.json", cards)
        manifest.mark(slug, "cards")
        manifest.save()

    # Rebuild the aggregate deck from every concept's stored cards.
    all_cards: list[dict] = []
    for concept in tm["concepts"]:
        all_cards.extend(load_json(cards_dir / f"{concept['slug']}.json", default=[]))
    if all_cards:
        _build_deck(cfg, all_cards)
        console.print(f"[green]{len(all_cards)} cards -> output/flashcards/[/]")
    else:
        console.print("[yellow]no cards generated.[/]")
