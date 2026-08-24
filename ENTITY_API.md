# Entity Mind Maps — API Manual

Any process (an AI agent, a script, another service) can spin up its own named
thought-association mind map and inject thoughts into it. Each entity gets its
own ChromaDB collection inside the same local `./db`. The default subconscious
is untouched — no entity param means everything works exactly as before.

The server must be running (`.\start_local_subconscious.ps1`) and LM Studio
must be serving embeddings on `localhost:1234`.

Base URL: `http://127.0.0.1:8000`

## 1. Spin up an entity + inject a thought (one call)

There is no separate "create" step. The first write creates the collection.

```
POST /api/entities/{entity}/thoughts
Content-Type: application/json

{"text": "the thought goes here"}
```

Entity names are slugified (lowercased; anything outside `a-z0-9._-` becomes `-`).
`fable-5-2026-08-24` maps to collection `entity_fable-5-2026-08-24`.

Response — the entity's own prior associated thoughts come back, so an agent
gets a reflection with every write:

```json
{"status": "stored", "entity": "fable-5-2026-08-24", "related": ["earlier similar thought", "..."]}
```

Exact duplicates are skipped: `{"status": "duplicate", ...}`.
If LM Studio is down you get a `503`.

### PowerShell

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/entities/fable-5-2026-08-24/thoughts" `
  -ContentType "application/json" `
  -Body '{"text": "I keep circling the same idea from different angles."}'
```

### curl

```sh
curl -X POST http://127.0.0.1:8000/api/entities/fable-5-2026-08-24/thoughts \
  -H "Content-Type: application/json" \
  -d '{"text": "I keep circling the same idea from different angles."}'
```

### Python

```python
import requests

def think(entity, text):
    r = requests.post(
        f"http://127.0.0.1:8000/api/entities/{entity}/thoughts",
        json={"text": text}, timeout=60,
    )
    r.raise_for_status()
    return r.json()["related"]  # the entity's own associated prior thoughts

think("fable-5-2026-08-24", "a thought worth keeping")
```

## 2. List entities

```
GET /api/entities
```

```json
{"entities": [
  {"entity": "subconscious", "collection": "subconscious_thoughts", "count": 42, "default": true},
  {"entity": "fable-5-2026-08-24", "collection": "entity_fable-5-2026-08-24", "count": 7, "default": false}
]}
```

## 3. Read an entity's feed and graph

Same endpoints the dashboard uses, with an optional `entity` param:

```
GET /api/thoughts?entity=fable-5-2026-08-24
GET /api/graph?entity=fable-5-2026-08-24&threshold=0.5
```

Omit `entity` (or use `subconscious` / `default`) for the original human feed.

## 4. Watch it

Open `http://127.0.0.1:8000` and pick the entity from the **Mind** dropdown in
the sidebar. The graph and feed switch to that entity and auto-refresh, so you
can watch an agent wire its thoughts together live.

## Prompt snippet for an agent

> You have a private associative memory. To record a thought, POST JSON
> `{"text": "..."}` to
> `http://127.0.0.1:8000/api/entities/<your-name-and-date>/thoughts`.
> The response's `related` field contains your own most similar past thoughts —
> use them to reflect before your next one.
