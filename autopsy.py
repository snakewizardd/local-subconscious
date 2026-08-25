"""Comparative topological autopsy: human default corpus vs synthetic entity namespace.

Pings the live FastAPI backend only (no direct DB access), rebuilds each mind's
pairwise cosine similarity matrix from /api/graph, and compares geometry.
"""
import sys
import numpy as np
import requests

BASE = "http://127.0.0.1:8000"


def fetch_matrix(entity=None):
    params = {"threshold": -1.0}
    if entity:
        params["entity"] = entity
    graph = requests.get(f"{BASE}/api/graph", params=params, timeout=120).json()
    ids = [n["id"] for n in graph["nodes"]]
    idx = {node_id: i for i, node_id in enumerate(ids)}
    n = len(ids)
    sim = np.eye(n)
    for e in graph["edges"]:
        i, j = idx[e["from"]], idx[e["to"]]
        sim[i, j] = sim[j, i] = e["value"]
    texts = [n_["full_text"] for n_ in graph["nodes"]]
    return sim, texts


def autopsy(name, sim):
    n = sim.shape[0]
    iu = np.triu_indices(n, k=1)
    pair = sim[iu]

    # Effective dimensionality: participation ratio of Gram-matrix eigenvalues.
    eig = np.linalg.eigvalsh(sim)
    eig = np.clip(eig, 0, None)
    p = eig / eig.sum()
    eff_dim = 1.0 / np.sum(p**2)
    entropy = -np.sum(p[p > 0] * np.log(p[p > 0])) / np.log(n)

    stats = {
        "nodes": n,
        "pairs": pair.size,
        "mean_sim": pair.mean(),
        "std_sim": pair.std(),
        "min_sim": pair.min(),
        "max_sim": pair.max(),
        "median_sim": np.median(pair),
        "density@0.5": float((pair > 0.5).mean()),
        "density@0.6": float((pair > 0.6).mean()),
        "density@0.7": float((pair > 0.7).mean()),
        "effective_dim": eff_dim,
        "spectral_entropy": entropy,  # 1.0 = perfectly spread, 0.0 = single axis
    }
    print(f"\n=== {name} ===")
    for k, v in stats.items():
        print(f"  {k:>16}: {v:.4f}" if isinstance(v, float) else f"  {k:>16}: {v}")
    return stats


if __name__ == "__main__":
    human_sim, human_texts = fetch_matrix()
    synth_sim, synth_texts = fetch_matrix("fable-5-2026-08-24")

    h = autopsy("HUMAN  subconscious_thoughts", human_sim)
    s = autopsy("SYNTH  entity_fable-5-2026-08-24", synth_sim)

    print("\n=== GEOMETRIC DIFFERENCE (human - synth) ===")
    for k in ("mean_sim", "std_sim", "density@0.5", "effective_dim", "spectral_entropy"):
        print(f"  {k:>16}: {h[k] - s[k]:+.4f}")

    print(f"\n  human occupies {h['effective_dim']:.2f} effective dims across {h['nodes']} thoughts"
          f" ({h['effective_dim']/h['nodes']:.1%} of possible spread)")
    print(f"  synth occupies {s['effective_dim']:.2f} effective dims across {s['nodes']} thoughts"
          f" ({s['effective_dim']/s['nodes']:.1%} of possible spread)")

    print("\n--- synth namespace contents (my prior shadow) ---")
    for t in synth_texts:
        print(f"  * {t[:110]}")
