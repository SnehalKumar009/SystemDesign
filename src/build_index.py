"""Embed chapter chunks into a persistent Chroma collection (incremental append)."""
from __future__ import annotations

from rich.console import Console
from tqdm import tqdm

from .config import Config, load_config
from .corpus import load_books
from .llm import chunk_text, local_embed
from .manifest import Manifest
from .util import ensure_dir

console = Console()


def _get_collection(cfg: Config):
    import chromadb

    ensure_dir(cfg.path("chroma"))
    client = chromadb.PersistentClient(path=str(cfg.path("chroma")))
    return client, client.get_or_create_collection(
        name=cfg["index"]["collection"], metadata={"hnsw:space": "cosine"}
    )


def query(concept: str, book: str | None, n: int, cfg: Config | None = None) -> list[dict]:
    """Retrieve top-n passages for a concept, optionally restricted to one book."""
    cfg = cfg or load_config()
    _, coll = _get_collection(cfg)
    emb = local_embed([concept], cfg)[0]
    where = {"book": book} if book else None
    res = coll.query(query_embeddings=[emb], n_results=n, where=where)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return [{"text": d, **m} for d, m in zip(docs, metas)]


def run(force: bool = False, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    client, coll = _get_collection(cfg)
    manifest = Manifest(cfg)

    if force:
        client.delete_collection(cfg["index"]["collection"])
        _, coll = _get_collection(cfg)
        for name in list(manifest.data["books"]):
            manifest.data["books"][name]["indexed"] = False

    max_chars = cfg["chunking"]["max_chars"]
    overlap = cfg["chunking"]["overlap"]
    unindexed = set(manifest.unindexed_books()) if not force else None

    for book in load_books(cfg):
        pdf_name = book["path"]
        if unindexed is not None and pdf_name not in unindexed:
            console.print(f"[dim]skip (indexed): {book['book']}[/]")
            continue
        console.print(f"[cyan]indexing[/] {book['book']}")
        ids, embeddings, docs, metas = [], [], [], []
        for ch in book["chapters"]:
            chunks = chunk_text(ch["text"], max_chars, overlap)
            for ci, chunk in enumerate(tqdm(chunks, desc=ch["title"][:40], leave=False)):
                if not chunk.strip():
                    continue
                vec = local_embed([chunk], cfg)[0]
                ids.append(f"{book['slug']}::{ch['index']}::{ci}")
                embeddings.append(vec)
                docs.append(chunk)
                metas.append({
                    "book": book["book"],
                    "chapter": ch["title"],
                    "chapter_index": ch["index"],
                    "page_start": ch["page_start"],
                })
        if ids:
            coll.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
        manifest.mark_indexed(pdf_name)

    manifest.save()
    console.print("[green]index up to date.[/]")
