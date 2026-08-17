# Study Toolkit (domain-agnostic)

Turn a folder of PDFs into consolidated study notes, mock interview Q&A, Anki
flashcards, a retrieval-augmented chat tutor, and a weekly roadmap.

- **Local Ollama** powers the topic map, questions, flashcards, embeddings and tutor.
- A **cloud LLM** (OpenAI or Anthropic) synthesizes the consolidated concept notes.
- **Incremental**: drop a new PDF in `SOURCE/` and only the delta is processed.
- **Domain-agnostic**: change `config.yaml` and it works for any subject.

> Ollama runs on the **host** (not in Docker). Defaults: `qwen3-coder:30b` for
> generation and `nomic-embed-text` for embeddings — change them in `config.yaml`.

## Layout
```
SOURCE/            put your PDFs here
src/               pipeline modules
output/            notes, questions, flashcards, roadmap, topic_map
data/              extracted JSON, Chroma index, manifest, per-concept cards
config.yaml        subject + model settings
progress.yaml      mastery tracker (0-6 per concept)
```

## Run locally

1. Install [Ollama](https://ollama.com) and pull models:
   ```powershell
   ollama pull qwen3-coder:30b
   ollama pull nomic-embed-text
   ```
2. Python env + deps:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Set the cloud key (for consolidated notes):
   ```powershell
   $env:OPENAI_API_KEY = "sk-..."
   ```
4. Put PDFs in `SOURCE/`, then run the pipeline:
   ```powershell
   python run.py all
   ```

### Individual stages
```
python run.py extract      # PDFs -> chapter JSON
python run.py index        # embed chapters into Chroma
python run.py topicmap     # cross-book concept map (+ seed progress.yaml)
python run.py notes        # consolidated per-concept notes (cloud LLM)
python run.py questions    # mock interview Q&A
python run.py cards        # Anki CSV + .apkg
python run.py roadmap      # weekly study plan
python run.py progress     # show mastery table
python run.py tutor --persona interviewer
```
Add `--force` to any generation stage to rebuild from scratch.

### Tutor personas
`teacher` · `socratic` · `interviewer` · `reviewer` · `examiner`
In-chat commands: `/persona <name>`, `/weak`, `/score "Concept" 3`, `/quit`.

## Run locally (Linux / Ubuntu)

Recreate the virtual environment on Linux — do NOT reuse a Windows `.venv/`.
Uses your existing host Ollama models (no pull needed if you already have
`qwen3-coder:30b` and `nomic-embed-text`).

```bash
ollama list                   # confirm the models exist

# Python env + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Cloud key for consolidated notes
export OPENAI_API_KEY="sk-..."

# Run
python run.py all
python run.py tutor --persona interviewer
```

## Run with Docker

Ollama runs on the **host**; only the app is containerized. Each subject is an
isolated compose project (own network + volumes).

Prerequisites on the host:
```bash
# Ollama must be reachable from containers -> bind to all interfaces, not just 127.0.0.1
sudo systemctl edit ollama    # add:  [Service]\n Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
ollama list                   # confirm qwen3-coder:30b and nomic-embed-text are present
```

Then:
```bash
cp .env.example .env          # set OPENAI_API_KEY (and COMPOSE_PROJECT_NAME)
# put your PDFs in SOURCE/

docker compose up --build -d  # builds app, runs `all` against host Ollama
docker compose logs -f app    # watch the pipeline progress

# interactive tutor (after the pipeline finishes)
docker compose run --rm app tutor --persona interviewer
```

`app` is a batch job: it runs `all` once and exits (check `docker compose ps`).
Re-run or run a single stage later:
```bash
docker compose run --rm app all
docker compose run --rm app notes --force
```

> The container reaches host Ollama via `host.docker.internal` (mapped to the
> host gateway). If it can't connect, verify Ollama is bound to `0.0.0.0:11434`
> and the host firewall allows the docker bridge.

## Reuse for another subject
1. Set `domain`, `goal`, `project` in `config.yaml` (and `COMPOSE_PROJECT_NAME` in `.env`).
2. Replace the PDFs in `SOURCE/`.
3. `python run.py all` (or `docker compose run --rm app all`).

Different subjects use separate compose projects, so their networks and data never mix.
