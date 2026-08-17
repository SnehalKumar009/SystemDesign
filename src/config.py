"""Loads config.yaml and resolves paths relative to the project root."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


class Config:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def domain(self) -> str:
        return self._data.get("domain", "the subject")

    @property
    def goal(self) -> str:
        return self._data.get("goal", "")

    def path(self, key: str) -> Path:
        """Resolve a configured path (under `paths:`) to an absolute path."""
        rel = self._data["paths"][key]
        p = Path(rel)
        return p if p.is_absolute() else ROOT / p

    def cloud_api_key(self) -> str:
        env = self._data["llm"]["cloud"]["api_key_env"]
        key = os.environ.get(env, "").strip()
        if not key:
            raise RuntimeError(
                f"Cloud LLM API key missing. Set the {env} environment variable "
                "(see .env.example)."
            )
        return key

    def ollama_host(self) -> str:
        local = self._data["llm"]["local"]
        return os.environ.get(local["host_env"], local["default_host"])


@lru_cache(maxsize=1)
def load_config() -> Config:
    with (ROOT / "config.yaml").open("r", encoding="utf-8") as f:
        return Config(yaml.safe_load(f))
