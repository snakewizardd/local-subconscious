# Local Subconscious — Issue Backlog

> Target branch: `subconscious`
> Scope: remaining scale, fidelity, and v2 work.
> Philosophy: keep it local, keep it sovereign, keep it small.

---

## Completed — v1 Hardening

### Issue #1 — Dedup thoughts on insert `bug` `P0` `correctness`
**Status:** Complete. Normalized SHA-256 hashes prevent duplicate inserts, and legacy entries without hash metadata are compared by normalized document text before embedding.

**Problem.** The capture path in `main.py` → `vector_store.py` has no "have I seen this string" check before embedding and upserting. Repeated thoughts stack as separate nodes, each with its own UUID. Proof: `backlog.txt` contains `i really liked the little mermaid vinyl` twice.

**Why it matters.** A thought is maximally similar to its own copy. Duplicate nodes fabricate artificially tight clusters and pull the graph topology toward whatever you happen to re-type, so the visualization starts *lying* about your associative structure.

**Fix.**
- Normalize the input string (trim, lowercase, collapse whitespace).
- Hash it (e.g. `hashlib.sha256`) and store the hash as ChromaDB metadata or check existing docs before `upsert`.
- On collision: skip insert (or bump a `count` field if you want frequency signal later).

**Acceptance criteria.**
- Entering the same normalized thought twice results in exactly one node.
- No behavioral change for genuinely distinct thoughts.

---

### Issue #2 — Vendor vis.js locally (kill the last cloud dependency) `privacy` `P0`
**Status:** Complete. `vis-network.min.js` is vendored and served from `static/vendor/`.

**Problem.** `static/index.html` loads vis-network from `https://unpkg.com/...`. The README asserts *"No API keys. No cloud. Absolute privacy"* and *"runs natively on your hardware."* The **data path** honors this (embeddings + ChromaDB are fully local), but the **render layer** hits a CDN on every explorer load, so the airgap claim is technically false.

**Why it matters.** It's the single thread hanging off an otherwise sealed system, and it's a one-line fix to make the headline claim literally true.

**Fix.**
- Download `vis-network.min.js` into `static/vendor/`.
- Point the `<script>` tag at the local copy.
- Add `static/vendor/` as tracked (it's a dependency, not bloat).

**Acceptance criteria.**
- Explorer renders the graph with the network cable unplugged.

---

### Issue #3 — Finish / audit `explorer.py` read path `bug` `P1`
**Status:** Complete. Both API endpoints handle empty, single-node, malformed-vector, and legacy-null-metadata cases; regression tests cover the legacy path.

**Problem.** In the stored version, `get_thoughts()` computes `data` but the visible body doesn't return it, and `get_graph()` pulls `ids/documents/embeddings` but the node/edge assembly + `cosine_similarity` loop isn't clearly wired through. The app runs (screenshots prove it), so this is either a truncation or a mid-refactor — but the read half is noticeably less finished/defensive than `main.py`.

**Fix.**
- Confirm `get_thoughts()` returns `{ "thoughts": [{ "id", "text" }, ...] }`.
- Confirm `get_graph(threshold)` returns `{ "nodes": [...], "edges": [...] }` with `edges` carrying the similarity value (frontend already shows "Similarity: 0.46" tooltips).
- Add basic guards: empty DB, single-node DB (no pairs), NaN/zero-norm vectors.

**Acceptance criteria.**
- `/api/thoughts` and `/api/graph?threshold=` both return well-formed JSON on empty, 1-node, and n-node databases.

---

## Completed — Recency Context

### Issue #4 — Recency coloring / time axis `enhancement` `P1`
**Status:** Complete. New thoughts store UTC timestamps, the feed sorts by them, and graph nodes use a dim-to-bright recency gradient. Legacy thoughts remain visible with the base color.

**Problem.** ChromaDB has insertion order and `backlog.txt` has ISO timestamps, but the graph is timeless. The README promises *"connections form across completely different eras of your life"* — which currently **cannot render**, because era is not an axis or a color.

**Fix.**
- Store a timestamp in ChromaDB metadata at insert (UUID already implies order; make it explicit).
- Color nodes on a recency gradient (recent = bright, old = dim) in `app.js` node styling.
- Optional stretch: a second slider or brush to filter the graph to a time window.

**Acceptance criteria.**
- Nodes visibly encode age; an old thought bonding to a new one is legible as a cross-era link.

---

### Issue #5 — Re-tune Barnes-Hut for larger graphs `enhancement` `P2`
**Problem.** `springLength: 150`, `gravitationalConstant: -2000` is tuned for ~10 nodes. Labels already collide at threshold 0.45; at a few hundred nodes it becomes soup — i.e. it degrades exactly when the corpus becomes valuable.

**Fix.**
- Scale `gravitationalConstant` / `springLength` as a function of node count, or expose them as advanced sliders.
- Consider hiding labels until zoom, or label-on-hover only.

**Acceptance criteria.**
- Graph stays readable (non-overlapping labels, stable layout) at 100+ nodes.

---

### Issue #6 — Sharpen semantic fidelity on short strings `enhancement` `P2`
**Problem.** Cosine similarity on very short strings is lossy. "i really love naamah" and "i really liked the little mermaid" bind partly on surface syntax ("i really l...") rather than meaning — so some edges are string-rhyme, not semantic kinship.

**Fix (pick one, cheapest first).**
- Encourage longer thought-strings (soft min-length nudge in the capture UI).
- Add an optional reranker / cross-encoder pass over the top-k before drawing edges.
- Experiment with a stronger local embed model if LM Studio can serve one.

**Acceptance criteria.**
- Manual spot-check: top-3 matches are semantically related, not just lexically similar.

---

## Milestone 3 — Make the Mirror Talk Back (the real v2)

### Issue #7 — Operationalize association, don't just display it `feature` `P1`
**Problem (the actual thesis gap).** The tool is a beautiful **read-only mirror**. The capture daemon already computes top-3 matches on every insert — then shows them and throws them away. The "it associates, it doesn't search" claim is currently *displayed* but not *operationalized*. Nothing acts on the structure.

**Candidate behaviors (scope one at a time).**
- **Cluster labels:** auto-name dense clusters ("these 7 thoughts are one latent project").
- **Resurfacing:** when a new thought lands near a forgotten old one, surface the old one in the reflection panel — the mirror *reminds* you.
- **Drift detection:** flag when your recent thoughts are pulling toward a new region of latent space.
- **Interlocutor mode:** feed the top-k neighbors back into a local chat model so the reflection *responds* instead of just listing.

**Acceptance criteria.**
- The system tells you at least one thing about your own corpus you didn't already know.

---

## Priority summary

| Next at scale | Do for v2 |
|---|---|
| #5 physics re-tune | #7 make it talk back |
| #6 semantic fidelity | |

**One-line verdict:** v1 hardening is complete. #5 and #6 are scale/fidelity work; #7 is the gap between "reflects your mind" and "converses with it."
