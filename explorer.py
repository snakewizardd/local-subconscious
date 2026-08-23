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
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/thoughts")
def get_thoughts():
    """Returns the list of thoughts without embeddings for the sidebar feed."""
    data = vector_store.get_all_thoughts()
    
    thoughts = []
    for i in range(len(data.get("ids", []))):
        thoughts.append({
            "id": data["ids"][i],
            "text": data["documents"][i]
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
    
    if not ids:
        return {"nodes": [], "edges": []}
        
    nodes = []
    for i in range(len(ids)):
        # Provide a short label for the node, but full text for the tooltip
        short_text = documents[i][:30] + "..." if len(documents[i]) > 30 else documents[i]
        nodes.append({
            "id": ids[i],
            "label": short_text,
            "title": documents[i],  # Used for hover tooltips
            "full_text": documents[i]
        })
        
    edges = []
    num_nodes = len(ids)
    
    # Calculate pairwise cosine similarity to build edges
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim > threshold:
                edges.append({
                    "from": ids[i],
                    "to": ids[j],
                    "value": sim, # Line thickness based on similarity
                    "title": f"Similarity: {sim:.2f}"
                })
                
    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    import uvicorn
    # Run with: uvicorn explorer:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)