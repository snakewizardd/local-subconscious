from contextlib import redirect_stdout
from io import StringIO
from math import gcd

import pandas as pd
import streamlit as st


def compute_lattice(N: int, a: float, max_k: int = 24):
    """
    Build the even-multiple lattice for target Na.

    A value from lower stack ja at multiplier k is a hit when
    it also appears somewhere in the target Na even-multiple table.

    Parameters
    ----------
    N:
        Target coefficient. Example: N=8 builds the 8a lattice.
    a:
        Any nonzero scale constant.
    max_k:
        Largest multiplier considered. Only even k values are used.
    """

    if N < 2:
        raise ValueError("N must be at least 2.")

    if a == 0:
        raise ValueError("a must be nonzero.")

    even_k = list(range(2, max_k + 1, 2))

    # Actual finite target set: (Na) * 2, (Na) * 4, ...
    target_values = {
        (N * a) * target_k
        for target_k in even_k
    }

    # ---------- Full matrix ----------

    full_data = {
        "k": even_k,
        f"{N}a = {N * a:g}": [
            (N * a) * k for k in even_k
        ],
    }

    # Descending lower stacks: (N-1)a through a
    for j in range(N - 1, 0, -1):
        full_data[f"{j}a = {j * a:g}"] = [
            (j * a) * k for k in even_k
        ]

    full_matrix = pd.DataFrame(full_data)

    # ---------- Hits-only matrix ----------

    hits_data = {
        "k": even_k,
        f"{N}a = {N * a:g}": [
            (N * a) * k for k in even_k
        ],
    }

    unique_hits = set()

    for j in range(N - 1, 0, -1):
        column = []

        for k in even_k:
            value = (j * a) * k

            if value in target_values:
                column.append(value)
                unique_hits.add(value)
            else:
                column.append(None)

        hits_data[f"{j}a hits"] = column

    hits_matrix = pd.DataFrame(hits_data)

    # ---------- Structural explanation ----------

    explanations = []

    for j in range(N - 1, 0, -1):
        # A target hit requires:
        #
        # (ja)k = (Na)r
        #
        # where r is even.
        #
        # Therefore 2N divides jk.
        period = (2 * N) // gcd(j, 2 * N)

        explanations.append({
            "stack": f"{j}a",
            "coefficient": j,
            "shared_factor_with_2N": gcd(j, 2 * N),
            "required_k_multiple": period,
            "rule": f"k must be divisible by {period}",
        })

    explanation_table = pd.DataFrame(explanations)

    # ---------- Display ----------

    print(f"\nTARGET LATTICE: {N}a")
    print(f"a = {a}")
    print(f"{N}a = {N * a}")
    print(f"Even multipliers: {even_k}")

    print("\nFULL MATRIX")
    print(full_matrix.to_string(index=False))

    print("\nHITS-ONLY MATRIX")
    print(hits_matrix.to_string(index=False, na_rep=""))

    print("\nUNIQUE HIT VALUES")
    print(sorted(unique_hits))

    print("\nWHY EACH STACK HITS")
    print(explanation_table.to_string(index=False))

    print("\nGENERAL HIT CONDITION")
    print("(ja)k is a hit when (ja)k = (Na)r for some even r.")
    print("After cancelling a: jk = Nr.")
    print("Because r is even: 2N must divide jk.")

    return {
        "full_matrix": full_matrix,
        "hits_matrix": hits_matrix,
        "unique_hits": sorted(unique_hits),
        "explanation": explanation_table,
    }


def render_app() -> None:
    st.set_page_config(
        page_title="Even-Multiple Lattice",
        page_icon="∷",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;600;700&display=swap');

        :root {
            --ink: #17201c;
            --paper: #f4f0e6;
            --accent: #cf4d2f;
            --signal: #147d68;
            --rule: #c9c0ae;
        }

        .stApp {
            color: var(--ink);
            background-color: var(--paper);
            background-image:
                linear-gradient(rgba(23, 32, 28, 0.045) 1px, transparent 1px),
                linear-gradient(90deg, rgba(23, 32, 28, 0.045) 1px, transparent 1px);
            background-size: 28px 28px;
        }

        html, body, [class*="st-"] {
            font-family: "Manrope", sans-serif;
        }

        code, pre, [data-testid="stDataFrame"] {
            font-family: "DM Mono", monospace;
        }

        .block-container {
            max-width: 1440px;
            padding-top: 7.5rem;
            padding-bottom: 4rem;
        }

        [data-testid="stNumberInput"] label p,
        [data-testid="stSlider"] label p,
        [data-testid="stSliderTickBar"] p,
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricValue"],
        [data-testid="stTab"] p {
            color: var(--ink) !important;
        }

        [data-testid="stTab"][aria-selected="true"] p {
            color: var(--accent) !important;
        }

        .lattice-header {
            border-top: 6px solid var(--ink);
            border-bottom: 1px solid var(--rule);
            padding: 1.2rem 0 1.35rem;
            margin-bottom: 1.4rem;
        }

        .lattice-kicker {
            color: var(--accent);
            font-family: "DM Mono", monospace;
            font-size: 0.78rem;
            font-weight: 500;
            text-transform: uppercase;
        }

        .lattice-title {
            color: var(--ink);
            font-size: clamp(2.3rem, 5vw, 5rem);
            font-weight: 700;
            line-height: 0.98;
            margin: 0.45rem 0 0;
        }

        .formula-strip {
            align-items: center;
            background: var(--ink);
            color: #fffdf7;
            display: flex;
            font-family: "DM Mono", monospace;
            justify-content: space-between;
            margin: 0.25rem 0 1.5rem;
            padding: 0.8rem 1rem;
        }

        .formula-strip strong {
            color: #f5b942;
        }

        [data-testid="stMetric"] {
            background: rgba(255, 253, 247, 0.7);
            border-left: 3px solid var(--signal);
            padding: 0.65rem 0.85rem;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--rule);
        }

        h2, h3 {
            color: var(--ink);
            letter-spacing: 0;
        }

        @media (max-width: 700px) {
            .block-container { padding-top: 5.5rem; }
            .formula-strip { align-items: flex-start; flex-direction: column; gap: 0.35rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <header class="lattice-header">
            <div class="lattice-kicker">Finite multiplicative structure</div>
            <h1 class="lattice-title">Even-Multiple Lattice</h1>
        </header>
        """,
        unsafe_allow_html=True,
    )

    control_one, control_two, control_three = st.columns([1, 1, 2])
    with control_one:
        target_n = st.number_input("Target coefficient N", min_value=2, value=8, step=1)
    with control_two:
        scale_a = st.number_input("Scale a", value=1.0, step=0.25, format="%.4f")
    with control_three:
        max_k = st.slider("Largest multiplier", min_value=2, max_value=100, value=24, step=2)

    if scale_a == 0:
        st.error("a must be nonzero.")
        st.stop()

    raw_output = StringIO()
    with redirect_stdout(raw_output):
        result = compute_lattice(int(target_n), float(scale_a), max_k)

    hit_count = len(result["unique_hits"])
    total_cells = (int(target_n) - 1) * (max_k // 2)
    populated_hits = int(result["hits_matrix"].iloc[:, 2:].notna().sum().sum())

    st.markdown(
        f"""
        <div class="formula-strip">
            <span>Target: <strong>{int(target_n)}a = {int(target_n) * scale_a:g}</strong></span>
            <span>Hit condition: <strong>2N | jk</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Unique values", hit_count)
    metric_two.metric("Hit cells", populated_hits)
    metric_three.metric("Lower-stack cells", total_cells)

    hits_tab, full_tab, rules_tab, raw_tab = st.tabs(
        ["Hits only", "Full matrix", "Stack rules", "Raw output"]
    )

    with hits_tab:
        st.subheader("Hits-only matrix")
        st.dataframe(result["hits_matrix"], width="stretch", hide_index=True)
        st.subheader("Unique hit values")
        if result["unique_hits"]:
            st.code(", ".join(f"{value:g}" for value in result["unique_hits"]), language=None)
        else:
            st.info("No hits occur in the selected multiplier range.")

    with full_tab:
        st.subheader("Full matrix")
        st.dataframe(result["full_matrix"], width="stretch", hide_index=True)

    with rules_tab:
        st.subheader("Why each stack hits")
        st.dataframe(result["explanation"], width="stretch", hide_index=True)
        st.latex(r"(ja)k = (Na)r,\quad r \in 2\mathbb{Z}\quad\Longrightarrow\quad 2N \mid jk")

    with raw_tab:
        st.subheader("Function output")
        st.code(raw_output.getvalue(), language="text")


if __name__ == "__main__":
    render_app()