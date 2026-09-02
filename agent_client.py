"""Reusable client for any agent that wants to think inside the local subconscious.

Any process (a Copilot CLI session, a Claude/Cursor run, a Python script, another
service) can instantiate `SubconsciousAgent("<your-name>-<yyyy-mm-dd>")` and:

    me = SubconsciousAgent("claude-2026-09-02")
    priors = me.think("resolve_copilot has to bypass the .cmd shim on Windows")
    priors = me.think("cmd.exe truncates -p at the first newline")
    audit = me.audit()   # -> geometric health of your own mind
    for row in audit.feed[-5:]:
        print(row)

`think()` injects a thought and returns the associated priors immediately —
that's the reflection loop you use *before* your next thought. `audit()` reads
your entire feed, computes the same geometry `autopsy_all.py` prints, and
returns a health verdict so an agent can catch itself collapsing into a
shape-cluster and course-correct.

The API must be live at http://127.0.0.1:8000 and LM Studio must be serving
embeddings on :1234. A 503 from `think()` means the neural bus is down —
raise it, do not silently queue.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any

import numpy as np
import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# Same slug rule as vector_store.entity_collection_name — kept in sync so an
# agent that types its own name can predict the collection it will land in.
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify_entity(name: str) -> str:
    slug = _SLUG_RE.sub("-", str(name).strip().lower()).strip("-._")
    if not slug:
        raise ValueError("Entity name must contain at least one alphanumeric character.")
    return slug


@dataclasses.dataclass
class AuditReport:
    """Snapshot of an entity's semantic geometry, plus a plain-language verdict.

    Fields mirror what `autopsy_all.py` prints so an agent can reason about its
    own shape the same way the operator does from the CLI.
    """
    entity: str
    nodes: int
    mean_sim: float
    std_sim: float
    median_sim: float
    density_0_5: float
    density_0_7: float
    effective_dim: float
    eff_dim_ratio: float
    spectral_entropy: float
    verdict: str
    warnings: list[str]
    feed: list[dict[str, Any]]

    def as_thought(self) -> str:
        """One-line audit summary an agent can hand straight back to think()."""
        return (
            f"self-audit: {self.nodes} thoughts, mean_sim {self.mean_sim:.3f}, "
            f"density_0.7 {self.density_0_7:.1%}, eff_dim/n {self.eff_dim_ratio:.3f}. "
            f"verdict: {self.verdict}."
        )


class SubconsciousError(RuntimeError):
    """Raised for any non-recoverable API failure (server down, 503, etc.)."""


class SubconsciousAgent:
    """A small handle on one entity's mind.

    Construction is a promise, not a create — the collection is materialized
    on first `think()`. Two agents that pick the same name share the same
    mind, which is almost never what you want; convention is
    `<agent-family>-<yyyy-mm-dd>` (e.g. `claude-opus-2026-09-02`).
    """

    def __init__(self, entity: str, *, base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 90.0):
        self.entity = slugify_entity(entity)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    # -- writes ------------------------------------------------------------

    def think(self, text: str, metadata: dict[str, Any] | None = None) -> list[str]:
        """Inject a thought. Return your own associated priors (up to top 3).

        Use the returned priors as reflection input *before* your next
        thought. That is the whole point of the loop.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("think() called with empty text.")
        payload: dict[str, Any] = {"text": text}
        if metadata:
            payload["metadata"] = metadata
        try:
            resp = self._session.post(
                f"{self.base_url}/api/entities/{self.entity}/thoughts",
                json=payload, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SubconsciousError(f"API unreachable: {exc}") from exc
        if resp.status_code == 503:
            raise SubconsciousError(
                "Embedding endpoint (LM Studio) is unreachable. "
                "Stop injecting and tell the operator.")
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise SubconsciousError(
                f"API rejected the thought: {exc.response.status_code} {resp.text[:200]}"
            ) from exc
        body = resp.json()
        return list(body.get("related") or [])

    # -- reads -------------------------------------------------------------

    def feed(self) -> list[dict[str, Any]]:
        """Every thought you've ever written to this entity, oldest first-ish."""
        r = self._session.get(
            f"{self.base_url}/api/thoughts",
            params={"entity": self.entity}, timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("thoughts", [])

    def _similarity_matrix(self) -> tuple[list[str], np.ndarray]:
        r = self._session.get(
            f"{self.base_url}/api/graph",
            params={"entity": self.entity, "threshold": -1.0},
            timeout=180,
        )
        r.raise_for_status()
        graph = r.json()
        ids = [n["id"] for n in graph.get("nodes", [])]
        n = len(ids)
        if n == 0:
            return ids, np.zeros((0, 0))
        idx = {node_id: i for i, node_id in enumerate(ids)}
        sim = np.eye(n)
        for e in graph.get("edges", []):
            i, j = idx[e["from"]], idx[e["to"]]
            sim[i, j] = sim[j, i] = e["value"]
        return ids, sim

    # -- self-awareness ----------------------------------------------------

    def audit(self) -> AuditReport:
        """Compute your own semantic geometry and hand back a health verdict.

        Same math as autopsy_all.py. Meant to be called every ~10 thoughts,
        before ending a work session, or whenever the operator says "audit
        yourself." The verdict is deliberately terse so the agent can inject
        it straight back into the store as its own next thought via
        `audit().as_thought()`.
        """
        feed = self.feed()
        ids, sim = self._similarity_matrix()
        n = sim.shape[0]
        warnings: list[str] = []

        if n < 2:
            return AuditReport(
                entity=self.entity, nodes=n,
                mean_sim=float("nan"), std_sim=float("nan"),
                median_sim=float("nan"),
                density_0_5=float("nan"), density_0_7=float("nan"),
                effective_dim=float("nan"), eff_dim_ratio=float("nan"),
                spectral_entropy=float("nan"),
                verdict="thought-zero territory — nothing to audit yet",
                warnings=warnings, feed=feed,
            )

        iu = np.triu_indices(n, k=1)
        pair = sim[iu]
        eig = np.clip(np.linalg.eigvalsh(sim), 0, None)
        p = eig / eig.sum()
        eff_dim = float(1.0 / np.sum(p ** 2))
        entropy = float(-np.sum(p[p > 0] * np.log(p[p > 0])) / np.log(n))
        mean_sim = float(pair.mean())
        density_0_7 = float((pair > 0.7).mean())
        eff_ratio = eff_dim / n

        # Verdict thresholds calibrated against 2026-09-02 baselines: the
        # organically-accreted gemini-agent mind at mean_sim ~0.50 /
        # density_0.7 ~1% / eff_dim/n ~0.10 is the "healthy" reference, and
        # topic-locked minds at mean_sim ~0.65 / density_0.7 >15% are the
        # collapse signal.
        if mean_sim > 0.60 or density_0_7 > 0.15:
            verdict = "collapsed — you are shape-clustering; vary voice, opener, and length hard"
            warnings.append("mean_sim above collapse threshold")
        elif mean_sim > 0.55 or density_0_7 > 0.08:
            verdict = "tightening — one topic dominates; introduce a concrete counter-thought"
        elif eff_ratio < 0.05 and n >= 10:
            verdict = "single-axis — dimensionality is starving; you are circling one idea"
        else:
            verdict = "healthy — geometry is diverse"

        return AuditReport(
            entity=self.entity, nodes=n,
            mean_sim=mean_sim,
            std_sim=float(pair.std()),
            median_sim=float(np.median(pair)),
            density_0_5=float((pair > 0.5).mean()),
            density_0_7=density_0_7,
            effective_dim=eff_dim,
            eff_dim_ratio=eff_ratio,
            spectral_entropy=entropy,
            verdict=verdict,
            warnings=warnings,
            feed=feed,
        )


# ---------------------------------------------------------------------------
# Module-level convenience for one-off scripts and REPL use.
# ---------------------------------------------------------------------------

def think(entity: str, text: str, **kwargs) -> list[str]:
    """One-shot think(). Prefer the class if you'll write more than once."""
    return SubconsciousAgent(entity).think(text, **kwargs)


def audit(entity: str, **kwargs) -> AuditReport:
    return SubconsciousAgent(entity, **kwargs).audit()


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(
        description="Talk to the local subconscious as a specific entity."
    )
    p.add_argument("entity", help="Your agent-name-and-date slug.")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_think = sub.add_parser("think", help="Inject a thought, print top priors.")
    p_think.add_argument("text")
    sub.add_parser("audit", help="Print a geometric self-audit and health verdict.")
    sub.add_parser("feed", help="Dump every thought this entity has written.")
    args = p.parse_args()

    agent = SubconsciousAgent(args.entity)
    if args.cmd == "think":
        for prior in agent.think(args.text):
            print(f"~ {prior}")
    elif args.cmd == "audit":
        r = agent.audit()
        print(json.dumps(dataclasses.asdict(r), indent=2, default=str))
        print(f"\n{r.as_thought()}")
    elif args.cmd == "feed":
        for t in agent.feed():
            print(t.get("text", ""))
