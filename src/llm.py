"""Provider-agnostic LLM access: local Ollama for most work, cloud for consolidation."""
from __future__ import annotations

import time
from typing import Callable

from .config import Config, load_config


def _retry(fn: Callable, attempts: int = 3, base_delay: float = 1.5):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - surfaced after final attempt
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (2**i))
    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last}")


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += step
    return chunks


# --- Local (Ollama) --------------------------------------------------------

def _ollama_client(cfg: Config):
    import ollama

    return ollama.Client(host=cfg.ollama_host())


def local_chat(prompt: str, system: str | None = None, cfg: Config | None = None) -> str:
    cfg = cfg or load_config()
    model = cfg["llm"]["local"]["gen_model"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def call():
        client = _ollama_client(cfg)
        resp = client.chat(model=model, messages=messages)
        return resp["message"]["content"]

    return _retry(call)


def local_embed(texts: list[str], cfg: Config | None = None) -> list[list[float]]:
    cfg = cfg or load_config()
    model = cfg["llm"]["local"]["embed_model"]

    def call():
        client = _ollama_client(cfg)
        vectors = []
        for t in texts:
            resp = client.embeddings(model=model, prompt=t)
            vectors.append(resp["embedding"])
        return vectors

    return _retry(call)


# --- Cloud (OpenAI / Anthropic) -------------------------------------------

def cloud_chat(prompt: str, system: str | None = None, cfg: Config | None = None) -> str:
    cfg = cfg or load_config()
    cloud = cfg["llm"]["cloud"]
    provider = cloud["provider"].lower()
    api_key = cfg.cloud_api_key()

    if provider == "openai":
        def call():
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(
                model=cloud["model"],
                messages=messages,
                max_tokens=cloud.get("max_tokens", 4096),
            )
            return resp.choices[0].message.content or ""

        return _retry(call)

    if provider == "anthropic":
        def call():
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=cloud["model"],
                max_tokens=cloud.get("max_tokens", 4096),
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(
                block.text for block in resp.content if getattr(block, "type", "") == "text"
            )

        return _retry(call)

    raise ValueError(f"Unknown cloud provider: {provider!r} (use 'openai' or 'anthropic').")
