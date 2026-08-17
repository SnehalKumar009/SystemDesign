#!/usr/bin/env python3
"""CLI orchestrator for the study toolkit.

Usage:
  python run.py extract [--force]
  python run.py index [--force]
  python run.py topicmap [--force]
  python run.py notes [--force]
  python run.py questions [--force]
  python run.py cards [--force]
  python run.py roadmap
  python run.py progress
  python run.py tutor [--persona teacher|socratic|interviewer|reviewer|examiner]
  python run.py all [--force]
"""
from __future__ import annotations

import argparse

from src import (
    build_index,
    consolidate_notes,
    extract,
    generate_flashcards,
    generate_questions,
    progress,
    roadmap,
    topic_map,
    tutor,
)


def _run_all(force: bool) -> None:
    extract.run(force=force)
    build_index.run(force=force)
    topic_map.run(force=force)
    consolidate_notes.run(force=force)
    generate_questions.run(force=force)
    generate_flashcards.run(force=force)
    roadmap.run()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("extract", "index", "topicmap", "notes", "questions", "cards", "all"):
        p = sub.add_parser(name)
        p.add_argument("--force", action="store_true", help="rebuild from scratch")

    sub.add_parser("roadmap")
    sub.add_parser("progress")
    t = sub.add_parser("tutor")
    t.add_argument("--persona", default="teacher")

    args = parser.parse_args()
    force = getattr(args, "force", False)

    match args.command:
        case "extract":
            extract.run(force=force)
        case "index":
            build_index.run(force=force)
        case "topicmap":
            topic_map.run(force=force)
        case "notes":
            consolidate_notes.run(force=force)
        case "questions":
            generate_questions.run(force=force)
        case "cards":
            generate_flashcards.run(force=force)
        case "roadmap":
            roadmap.run()
        case "progress":
            progress.run()
        case "tutor":
            tutor.run(persona=args.persona)
        case "all":
            _run_all(force)


if __name__ == "__main__":
    main()
