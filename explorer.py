import os
import numpy as np
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from vector_store import VectorStore

app = FastAPI(title="Project Subconscious Explorer")
vector_store = VectorStore()

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

@app.get("/api/thoughts")
def get_thoughts():
    """Returns the list of thoughts without embeddings for the sidebar feed."""
    data = vector_store.get_all_thoughts()
    ids = data.get("ids", [])
    documents = data.get("documents", [])

    if not ids:
        return {"thoughts": []}

    thoughts = []
    for i in range(len(ids)):
        text = documents[i] if i < len(documents) else ""
        thoughts.append({
            "id": ids[i],
            "text": text
        })
    return {"thoughts": thoughts}

@app.get("/api/graph")
def get_graph(threshold: float = 0.5):
    """
    Computes a similarity matrix between all embeddings and returns
    nodes and edges for the network graph.
    """
    data = vector_store.get_all_thoughts()
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    embeddings = data.get("embeddings", [])

    if not ids or len(embeddings) == 0:
        return {"nodes": [], "edges": []}

    if not isinstance(threshold, (int, float)) or np.isnan(threshold):
        threshold = 0.5

    nodes = []
    for i in range(len(ids)):
        text = documents[i] if i < len(documents) else ""
        short_text = text[:30] + "..." if len(text) > 30 else text
        nodes.append({
            "id": ids[i],
            "label": short_text,
            "title": text,
            "full_text": text
        })

    edges = []
    num_nodes = len(ids)
    if num_nodes == 1:
        return {"nodes": nodes, "edges": edges}

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if i >= len(embeddings) or j >= len(embeddings):
                continue
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim > threshold:
                edges.append({
                    "from": ids[i],
                    "to": ids[j],
                    "value": float(sim),
                    "title": f"Similarity: {sim:.2f}"
                })

    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    import uvicorn
    # Run with: uvicorn explorer:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)