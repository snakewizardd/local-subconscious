# Even-Multiple Lattice Explorer

**Status:** preserved experiment; not connected to the production pipeline.

This Streamlit tool builds the finite even-multiple lattice for a target
coefficient `N`, scale `a`, and bounded multiplier horizon. It preserves the
original `compute_lattice` function and uses that function directly to render
the full matrix, hits-only matrix, unique intersections, and the GCD-derived
rule for every lower stack.

## Why It Belongs Here

Local Subconscious already has processes operating at different timescales:

- `cron_vision.py --interval N` supports periodic visual capture.
- The browser explorer refreshes its feed and graph every 15 seconds.
- Stored thought metadata includes timestamps.
- Backlog issue #7 proposes resurfacing forgotten thoughts and detecting drift.

The lattice is a deterministic way to inspect when integer-related cadences
meet at selected checkpoints. If `a` is a base time quantum, `Na` is an anchor
cadence, and `ja` is a faster cadence, the tool marks a hit when an
even-numbered event from the lower cadence lands on an even-numbered anchor
event within the selected horizon:

```text
(ja)k = (Na)r, where k and r are even
```

After cancelling `a`, the structural condition is:

```text
2N divides jk
```

The period shown for a lower stack is therefore:

```text
2N / gcd(j, 2N)
```

This is narrower than a general-purpose scheduler: it intentionally studies
even checkpoints and a finite range. That restriction is part of the
experiment, not a claim about all schedule collisions.

## Concrete Application: Cadence Coalescing

Take the explorer's current 15-second refresh as `a=15`, and a five-minute
visual capture as `N=20`, so `Na=300` seconds. For the `1a` stack, the first
selected alignment is at `k=40`:

```text
15 * 40 = 300 * 2 = 600 seconds
```

A future coordinator could use such intersections to batch graph refresh,
capture indexing, summary generation, or maintenance at shared boundaries
instead of waking independent heavy jobs at nearly the same time. The current
application does not coordinate these jobs; the explorer only makes the
alignment structure visible.

## Future Hypothesis: Temporal Edges

The semantic graph currently answers *which thoughts are close in meaning*.
Timestamped recurrence could eventually add a separate question: *which
clusters return on related rhythms, and when do those rhythms align?*

One testable path would be:

1. Estimate coarse recurrence intervals for sufficiently populated semantic
   clusters from stored timestamps.
2. Treat one review or consolidation interval as `N` and cluster intervals as
   lower coefficients `j` after quantization to a common base unit `a`.
3. Use lattice hits as candidate resurfacing windows, then measure whether they
   produce more useful reflections than fixed or random timing.

Frequent alignment would correspond to a large shared factor with `2N`; rare
alignment would correspond to a small shared factor. This is a hypothesis
about a scheduling signal, not evidence that cognition itself follows this
lattice.

The experiment should move out of `misc` only if either:

- collision-aware batching measurably reduces duplicate work or wakeups, or
- temporal-lattice resurfacing performs better than a fixed/random baseline on
  an explicit usefulness measure.

## Run It

From the repository root, using the project virtual environment:

```powershell
.\venv\Scripts\python.exe -m pip install -r .\misc\lattice_explorer\requirements.txt
.\venv\Scripts\python.exe -m streamlit run .\misc\lattice_explorer\app.py
```

Streamlit normally opens the app at `http://localhost:8501`.

## Programmatic Use

```python
from misc.lattice_explorer.app import compute_lattice

result = compute_lattice(N=20, a=15, max_k=100)
print(result["unique_hits"])
```