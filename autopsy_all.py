"""One-shot geometric comparison across every named mind, via the live API.

Prints per-entity: node count, mean/std pairwise cosine similarity, density at
thresholds, effective dimensionality (participation ratio of Gram eigenvalues),
and spectral entropy. A healthy mind has low mean sim, high effective dim, and
high entropy. A boilerplate-collapsed batch shows the opposite.
"""
import sys
import numpy as np
import requests

BASE = "http://127.0.0.1:8000"


def fetch_matrix(entity=None):
    params = {"threshold": -1.0}
    if entity:
        params["entity"] = entity
    graph = requests.get(f"{BASE}/api/graph", params=params, timeout=180).json()
    ids = [n["id"] for n in graph["nodes"]]
    if not ids:
        return np.zeros((0, 0))
    idx = {node_id: i for i, node_id in enumerate(ids)}
    n = len(ids)
    sim = np.eye(n)
    for e in graph["edges"]:
        i, j = idx[e["from"]], idx[e["to"]]
        sim[i, j] = sim[j, i] = e["value"]
    return sim


def stats(name, sim):
    n = sim.shape[0]
    if n < 2:
        print(f"\n=== {name} === (n={n}, insufficient)")
        return None
    iu = np.triu_indices(n, k=1)
    pair = sim[iu]
    eig = np.clip(np.linalg.eigvalsh(sim), 0, None)
    p = eig / eig.sum()
    eff_dim = 1.0 / np.sum(p ** 2)
    entropy = -np.sum(p[p > 0] * np.log(p[p > 0])) / np.log(n)
    row = {
        "nodes": n,
        "mean_sim": pair.mean(),
        "std_sim": pair.std(),
        "median_sim": float(np.median(pair)),
        "density_0.5": float((pair > 0.5).mean()),
        "density_0.7": float((pair > 0.7).mean()),
        "effective_dim": eff_dim,
        "eff_dim_ratio": eff_dim / n,
        "spectral_entropy": entropy,
    }
    print(f"\n=== {name} ===")
    for k, v in row.items():
        print(f"  {k:>18}: {v:.4f}" if isinstance(v, float) else f"  {k:>18}: {v}")
    return row


def main():
    entities = requests.get(f"{BASE}/api/entities", timeout=30).json()["entities"]
    rows = {}
    for ent in entities:
        name = ent["entity"]
        if ent["count"] < 2:
            continue
        sim = fetch_matrix(None if ent["default"] else name)
        rows[name] = stats(name, sim)

    print("\n=== ranked by effective-dim ratio (higher = healthier spread) ===")
    ranked = sorted(
        ((n, r["eff_dim_ratio"], r["mean_sim"], r["nodes"])
         for n, r in rows.items() if r),
        key=lambda t: -t[1],
    )
    print(f"  {'entity':<32} {'eff/n':>8} {'mean':>8} {'n':>5}")
    for name, ratio, mean, n in ranked:
        print(f"  {name:<32} {ratio:>8.4f} {mean:>8.4f} {n:>5}")


if __name__ == "__main__":
    sys.exit(main() or 0)
