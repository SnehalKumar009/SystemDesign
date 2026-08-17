"""Small shared helpers: slugify, JSON IO, path helpers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def slugify(text: str, max_len: int = 60) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_json_block(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM response, tolerating prose/fences."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = min(
        [i for i in (candidate.find("{"), candidate.find("[")) if i != -1],
        default=-1,
    )
    if start == -1:
        raise ValueError("No JSON found in model response.")
    depth = 0
    opener = candidate[start]
    closer = "}" if opener == "{" else "]"
    for i in range(start, len(candidate)):
        c = candidate[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return json.loads(candidate[start : i + 1])
    raise ValueError("Unbalanced JSON in model response.")
