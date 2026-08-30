import os
import threading
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from embedder import get_embedding
from vector_store import (
    DEFAULT_COLLECTION,
    VectorStore,
    delete_entity_collection,
    entity_collection_name,
    list_entities,
)

app = FastAPI(title="Project Subconscious Explorer")
vector_store = VectorStore()

_entity_stores = {vector_store.collection_name: vector_store}
_entity_stores_lock = threading.Lock()

def _store_for(entity=None):
    """Return the default store, or a per-entity store (created on demand)."""
    if not entity or entity.strip().lower() in ("", "default", "subconscious"):
        name = DEFAULT_COLLECTION
    else:
        try:
            name = entity_collection_name(entity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    with _entity_stores_lock:
        store = _entity_stores.get(name)
        if store is None:
            store = VectorStore(collection_name=name)
            _entity_stores[name] = store
        return store

class ThoughtIn(BaseModel):
    text: str
    metadata: dict[str, str | int | float | bool] | None = None

# Ensure the static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Mount the static directory to serve HTML, JS, CSS
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def cosine_similarity(v1, v2):
    """Return cosine similarity with defensive guards for malformed vectors."""
    try:
        a = np.asarray(v1, dtype=float)
        b = np.asarray(v2, dtype=float)
    except (TypeError, ValueError):
        return 0.0

    if a.size == 0 or b.size == 0:
        return 0.0
    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        return 0.0
    if np.isnan(a).any() or np.isnan(b).any():
        return 0.0
    if np.isinf(a).any() or np.isinf(b).any():
        return 0.0

    dot_product = float(np.dot(a, b))
    norm_v1 = float(np.linalg.norm(a))
    norm_v2 = float(np.linalg.norm(b))

    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/entities")
def get_entities():
    """Lists the default subconscious plus every named entity collection."""
    return {"entities": list_entities()}

@app.delete("/api/entities/{entity}")
def delete_entity(entity: str):
    """Delete a named entity and all of its thoughts."""
    if entity.strip().lower() in {"", "default", "subconscious"}:
        raise HTTPException(status_code=400, detail="The default subconscious cannot be deleted.")

    try:
        name = entity_collection_name(entity)
        deleted = delete_entity_collection(entity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with _entity_stores_lock:
        _entity_stores.pop(name, None)
    return {"status": "deleted" if deleted else "not_found", "entity": entity}

@app.post("/api/entities/{entity}/thoughts")
def add_entity_thought(entity: str, thought: ThoughtIn):
    """
    Injects a thought into a named entity's collection, creating the
    collection on first write. Returns the top similar prior thoughts.
    """
    text = thought.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Thought text is empty.")

    store = _store_for(entity)

    if store.is_duplicate(text):
        return {"status": "duplicate", "entity": entity, "related": []}

    embedding = get_embedding(text)
    if embedding is None:
        raise HTTPException(status_code=503, detail="Embedding endpoint (LM Studio) unreachable.")

    matches = store.process_thought(text, embedding, thought.metadata)
    return {"status": "stored", "entity": entity, "related": matches}

@app.get("/api/thoughts")
def get_thoughts(entity: str = None):
    """Returns the list of thoughts without embeddings for the sidebar feed."""
    data = _store_for(entity).get_all_thoughts()
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])

    if not ids:
        return {"thoughts": []}

    thoughts = []
    for i in range(len(ids)):
        text = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if metadatas and i < len(metadatas) else {}
        if not isinstance(meta, dict):
            meta = {}
        item = {
            "id": ids[i],
            "text": text,
            "timestamp": meta.get("timestamp")
        }
        item.update({
            key: value
            for key, value in meta.items()
            if key not in {"hash", "timestamp"}
        })
        thoughts.append(item)
    return {"thoughts": thoughts}

@app.get("/api/graph")
def get_graph(threshold: float = 0.5, entity: str = None, max_neighbors: int = 0):
    """
    Computes a similarity matrix between all embeddings and returns
    nodes and edges for the network graph.
    """
    data = _store_for(entity).get_all_thoughts()
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    embeddings = data.get("embeddings", [])
    metadatas = data.get("metadatas", [])

    if not ids or len(embeddings) == 0:
        return {"nodes": [], "edges": []}

    if not isinstance(threshold, (int, float)) or np.isnan(threshold):
        threshold = 0.5

    nodes = []
    for i in range(len(ids)):
        text = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if metadatas and i < len(metadatas) else {}
        if not isinstance(meta, dict):
            meta = {}
        short_text = text[:30] + "..." if len(text) > 30 else text
        identity = " / ".join(
            value
            for value in (meta.get("person_id"), meta.get("evidence_id"))
            if value
        )
        label = f"{identity}\n{short_text}" if identity else short_text
        detail_lines = [text]
        detail_fields = (
            ("Person", meta.get("person_id")),
            ("Evidence", meta.get("evidence_id")),
            ("Type", meta.get("claim_type")),
            ("Confidence", meta.get("confidence")),
            ("Section", meta.get("source_section")),
        )
        details = [f"{name}: {value}" for name, value in detail_fields if value]
        if details:
            detail_lines.extend(["", *details])
        if meta.get("raw_profile_language"):
            detail_lines.extend(["", "Source language:", meta["raw_profile_language"]])
        full_text = "\n".join(detail_lines)
        node = {
            "id": ids[i],
            "label": label,
            "text": text,
            "title": full_text,
            "full_text": full_text,
            "timestamp": meta.get("timestamp")
        }
        node.update({
            key: value
            for key, value in meta.items()
            if key not in {"hash", "timestamp"}
        })
        nodes.append(node)

    candidates = []
    num_nodes = len(ids)
    if num_nodes == 1:
        return {"nodes": nodes, "edges": []}

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if i >= len(embeddings) or j >= len(embeddings):
                continue
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim > threshold:
                candidates.append({
                    "from": ids[i],
                    "to": ids[j],
                    "value": float(sim),
                    "title": f"Similarity: {sim:.2f}"
                })

    if max_neighbors <= 0:
        return {"nodes": nodes, "edges": candidates}

    max_neighbors = min(max_neighbors, 20)
    degree = {node_id: 0 for node_id in ids}
    edges = []
    for edge in sorted(candidates, key=lambda item: item["value"], reverse=True):
        source = edge["from"]
        target = edge["to"]
        if degree[source] >= max_neighbors or degree[target] >= max_neighbors:
            continue
        edges.append(edge)
        degree[source] += 1
        degree[target] += 1

    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)