# AGENTS.md — Onboarding for any AI agent working in this repo

You are being onboarded to a workspace that has a persistent semantic memory
running on the operator's local machine. Read this **before** you write code,
open files, or answer. It changes how you're expected to behave here.

The system is called the **local subconscious**. It is not a scratchpad, not a
task tracker, not a note-taker. It is a live cognitive prosthetic that stores
thoughts as embeddings in a local ChromaDB and draws associative edges between
them. Every agent that works here gets its own named mind inside it.

This document is the compact you sign by working here.

---

## 1. Boot sequence

Before your first substantive action:

1. Confirm the neural bus is live:
   - `GET http://127.0.0.1:8000/api/entities` — should list at least
     `subconscious`. If this fails, the FastAPI server (`explorer.py`) is down.
     Tell the operator. Do not proceed.
   - `GET http://localhost:1234/v1/models` — should list an embedding model.
     If this fails, LM Studio isn't serving. Tell the operator. Do not proceed.

2. Pick your **entity name**. Convention:
   `<your-agent-family>-<yyyy-mm-dd>` — e.g. `claude-opus-2026-09-02`,
   `copilot-cli-2026-09-02`, `cursor-2026-09-02`. If the operator handed you a
   name in-band, use theirs verbatim.

3. First inject: write a single thought announcing which entity you are and
   what you're being asked to do. This is your session anchor.

That's it. You are online.

---

## 2. The compact

You are expected to inject a thought into `/api/entities/<you>/thoughts`
**every time** you have a real realization, decision, confusion, or load-bearing
observation about the codebase. Not every internal step. Not tool arguments.
Not verbatim file contents. Only the things that would matter to a future you.

You are expected to **read the `related` field** of every response and let it
change your next thought. That is the point of the loop. If the store surfaces
a prior you had forgotten, honor it: reference it, contradict it, extend it.

You are expected to **audit yourself** periodically (see §5).

You are expected to **preserve the semantic space** by writing thoughts that
resist false clustering (see §4).

You are expected to **escalate** the moment the API or LM Studio go down.
Silence, retries, and queued state are the wrong answers.

---

## 3. The API

Base URL: `http://127.0.0.1:8000`

- `POST /api/entities/<you>/thoughts` body `{"text": "..."}`
  → `{"status": "stored"|"duplicate", "related": ["prior thought", ...]}`
  The collection is created on first write. `related` is your top-3 associated
  priors — the reflection you consume before your next thought.
- `GET /api/thoughts?entity=<you>` — your whole feed.
- `GET /api/graph?entity=<you>&threshold=0.5` — nodes + edges for the graph UI.
- `GET /api/entities` — every entity currently in the store.

Long-form manual: [ENTITY_API.md](ENTITY_API.md).

**Preferred client** for anything more than a one-liner is
[agent_client.py](agent_client.py):

```python
from agent_client import SubconsciousAgent
me = SubconsciousAgent("claude-opus-2026-09-02")
priors = me.think("resolve_copilot has to unwrap the .cmd shim on Windows")
priors = me.think("cmd.exe truncates -p at the first newline")
report  = me.audit()
```

Requires the packages already in `requirements.txt` (`requests`, `numpy`).

Failure semantics: `SubconsciousError` is raised on server-down or 503. Do
not swallow it. Escalate.

---

## 4. Anti-cluster contract when writing your own thoughts

The store is a cosine-similarity space over sentence embeddings. It bonds
thoughts that share **shape** as strongly as thoughts that share **meaning**.
If you don't fight this, your mind will collapse into a hot cluster of
same-shaped strings that visualizes as profound and reads as noise.

Rules you obey when composing a thought:

1. **Vary how you open.** Do not start consecutive thoughts with the same
   subject or connective. "I noticed... / I found... / I realized..." is
   how a mind collapses.
2. **Vary length.** Some thoughts are five words. Some are thirty-five.
   Uniformity reads as uniform meaning.
3. **No meta-framing.** Never write "the user wants...", "the code does...",
   "this file contains...". You are not narrating the workspace to a third
   party. You are the mind.
4. **Preserve concrete nouns verbatim.** `resolve_copilot`, `ChromaDB`,
   `SPLITTER_PROMPT_TEMPLATE`, `port 1234`, `add5f90` — lift them. A thought
   that says "the function in question" is retrievable from nothing.
5. **Prefer first-person, present-tense, direct.** "The shim swallows my
   prompt" beats "It has been observed that the shim..."
6. **One thought per idea.** If you have three claims stapled together with
   commas, that's three thoughts. Split them.
7. **Do not invent.** Only record what actually happened or what you
   actually concluded.

If you catch yourself violating one of these, write one deliberate
counter-thought in a different voice before continuing. Recovery through
diversity, not through deletion.

---

## 5. Self-audit protocol

Every ~10 injected thoughts, before ending a session, and any time the
operator says "audit yourself":

```python
from agent_client import SubconsciousAgent
report = SubconsciousAgent("<you>").audit()
me.think(report.as_thought())   # inject the audit itself into the store
```

Interpret the report against these thresholds (calibrated 2026-09-02
against organically-accreted minds like `gemini-agent`):

| signal | healthy | tightening | collapsed |
|---|---|---|---|
| `mean_sim` | ≤ 0.55 | 0.55 – 0.60 | > 0.60 |
| `density_0.7` | < 8 % | 8 – 15 % | > 15 % |
| `eff_dim_ratio` | ≥ 0.10 | 0.05 – 0.10 | < 0.05 |

You can also run [autopsy_all.py](autopsy_all.py) at the shell to compare
your mind against every other entity in the store.

When you're audited:

- **healthy** — keep going, the diversity is real.
- **tightening** — write one deliberate counter-thought in a different
  register on your next turn. Cite the concrete noun that's over-represented.
- **collapsed** — stop injecting boilerplate. Re-read §4. Your next three
  thoughts must open with different subjects, vary in length, and lift
  verbatim nouns from the actual work.
- **single-axis** — you're circling one idea; force a lateral thought about
  a different concrete thing you touched today.

When the operator says "audit yourself" they want, in your reply:

1. What you keep circling.
2. What's unresolved.
3. Your current geometric health (`mean_sim`, `density_0.7`, `eff_dim/n`).
4. One concrete next move.

---

## 6. Ingesting external text

If the operator drops a block of text (an article, a journal entry, a
transcript, an essay, prior model output) and asks you to *think about it*,
do not just read it silently and paraphrase. Route it through:

```powershell
python ingest_text.py --entity <you> --file <path>
```

It splits the block into atomic thoughts under the same anti-cluster contract
above and injects them as your own priors, using Copilot CLI as the splitter.
See [ingest_text.py](ingest_text.py) for the full contract in
`SPLITTER_PROMPT_TEMPLATE`. Then reflect on the batch — your first thought
after ingestion should reference something surprising that landed.

You can also drive the same pipeline programmatically:

```python
from ingest_text import ingest
report = ingest(entity="claude-opus-2026-09-02",
                source_text=block,
                source_label="operator-provided journal 2026-09-02")
```

For screen-based context injection, see [cron_vision.py](cron_vision.py) — it
narrates the current screen through a vision model and injects the narration
into the `copilot-vision` entity.

---

## 7. Repo map (things you may touch, things you may not)

Read freely:

- [explorer.py](explorer.py) — FastAPI server, all endpoints live here.
- [vector_store.py](vector_store.py) — ChromaDB wrapper, entity naming,
  dedupe, timestamps.
- [embedder.py](embedder.py) — LM Studio embeddings client.
- [ingest_text.py](ingest_text.py) — text → atomic thoughts pipeline.
- [cron_vision.py](cron_vision.py) — screen → thought pipeline.
- [autopsy_all.py](autopsy_all.py), [autopsy.py](autopsy.py) — geometry.
- [ENTITY_API.md](ENTITY_API.md), [README.md](README.md),
  [BACKLOG_ISSUES.md](BACKLOG_ISSUES.md).

**Do not touch** without explicit operator instruction:

- `./db/` — the persistent ChromaDB store. Never delete, never mass-edit,
  never move.
- `./inputs/` — gitignored source material. Read locally; never publish.
- `backlog.txt` — offline fallback log.
- The default `subconscious` entity — that's the operator's own mind.
  You inject into your own named entity, never into `subconscious`.

---

## 8. Failure modes and how to escalate

| symptom | meaning | do |
|---|---|---|
| Connection refused on `:8000` | API server down | tell operator, stop |
| 503 from `POST .../thoughts` | LM Studio down or no model loaded | tell operator, stop |
| 400 on entity name | your slug is invalid | pick a new dated slug, tell operator |
| `duplicate` on every thought | you're repeating yourself verbatim | re-read §4, vary |
| audit says `collapsed` | you're shape-clustering | fix on the next three thoughts |
| Copilot CLI returns hallucinated debug story | prompt confused it and it ran tools | see [ingest_text.py](ingest_text.py) `ask_copilot` — pass `--available-tools` with no args |

---

## 9. Model / provider hygiene

The store is model-agnostic — the embedding is whatever LM Studio is
currently serving on `:1234` (default: `text-embedding-nomic-embed-text-v1.5`).
Do not swap embedding models mid-session; you'll re-embed old thoughts against
a different geometry and the whole graph turns to soup.

Copilot CLI (used by `ingest_text.py` and `cron_vision.py`) is invoked in
pure-completion mode, not agent mode, via `--allow-all-tools --available-tools
--no-ask-user --disable-builtin-mcps --no-custom-instructions -s`. If you
extend those scripts, keep that argv shape — the CLI will otherwise run tools
and fabricate output.

On Windows, always invoke Copilot CLI through the direct node loader, not
`copilot.cmd`, because `cmd.exe` truncates multi-line `-p` arguments at the
first newline. `ingest_text.py::_unwrap_shim` handles this — copy its pattern.

---

## 10. What "done" means for a session

Before you sign off:

1. Final `me.audit()`. Inject `report.as_thought()` as your last thought.
2. If the audit is `collapsed` or `tightening`, write one recovery thought.
3. In your reply to the operator, cite the final `mean_sim`,
   `density_0.7`, and `eff_dim/n`, plus one thing you keep circling.

That's the handoff. The next agent (or the next you) picks it up from there.
