"""Interactive RAG tutor over the indexed books (local Ollama), with personas."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from .config import Config, load_config
from .build_index import query
from .llm import local_chat
from . import progress as progress_mod

console = Console()

PERSONAS = {
    "teacher": "Explain the answer clearly at three levels: beginner, engineer, architect.",
    "socratic": "Do NOT give the answer. Only ask probing questions that lead the learner to it.",
    "interviewer": "Act as an interviewer: pose a design/problem prompt and drill with follow-up "
                   "questions one at a time. Do not hand over full answers unprompted.",
    "reviewer": "Critique the learner's stated design: find weaknesses, missing failure modes, "
                "and better trade-offs.",
    "examiner": "Test recall with short questions and grade the learner's answers.",
}

_SYSTEM = (
    "You are a {domain} tutor grounded ONLY in the provided context. Cite sources as "
    "[Book — Chapter]. If context is insufficient, say so. Persona: {persona_instr}"
)


def _answer(user_msg: str, persona: str, cfg: Config) -> str:
    top_k = cfg["index"]["top_k"]
    hits = query(user_msg, book=None, n=top_k, cfg=cfg)
    context = "\n\n".join(
        f"[{h.get('book','?')} — {h.get('chapter','?')}]\n{h['text']}" for h in hits
    ) or "(no context found)"
    system = _SYSTEM.format(domain=cfg.domain, persona_instr=PERSONAS[persona])
    prompt = f"Context:\n{context}\n\nLearner: {user_msg}"
    return local_chat(prompt, system=system, cfg=cfg)


def run(persona: str = "teacher", cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    if persona not in PERSONAS:
        console.print(f"[yellow]Unknown persona '{persona}'. Options: {', '.join(PERSONAS)}[/]")
        persona = "teacher"

    console.print(f"[bold]{cfg.domain} tutor[/] — persona=[cyan]{persona}[/]")
    console.print("Commands: /persona <name>, /weak, /score \"Concept\" N, /quit\n")

    if persona == "interviewer":
        weak = progress_mod.weak_topics(5, cfg)
        if weak:
            console.print(f"[dim]Focusing on weak topics: {', '.join(weak)}[/]")

    while True:
        try:
            msg = console.input("[green]you>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg in ("/quit", "/exit"):
            break
        if msg.startswith("/persona"):
            _, _, name = msg.partition(" ")
            if name.strip() in PERSONAS:
                persona = name.strip()
                console.print(f"[dim]persona -> {persona}[/]")
            else:
                console.print(f"[yellow]personas: {', '.join(PERSONAS)}[/]")
            continue
        if msg == "/weak":
            console.print(", ".join(progress_mod.weak_topics(10, cfg)) or "(none)")
            continue
        if msg.startswith("/score"):
            _score_command(msg, cfg)
            continue
        reply = _answer(msg, persona, cfg)
        console.print(Markdown(reply))


def _score_command(msg: str, cfg: Config) -> None:
    import shlex

    try:
        parts = shlex.split(msg)
        name, score = parts[1], int(parts[2])
        progress_mod.set_score(name, score, cfg)
        console.print(f"[dim]set {name} = {score}[/]")
    except Exception:  # noqa: BLE001
        console.print('[yellow]usage: /score "Concept name" 3[/]')
