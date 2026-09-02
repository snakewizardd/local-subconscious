"""Text -> atomic thoughts -> entity mind map.

Takes a block of text (arg, file, or stdin), asks Copilot CLI to decompose it
into atomic thoughts under a strict anti-boilerplate contract, then injects
each thought into a named entity via the live /api/entities API.

The prompt is written to defeat the specific failure mode of dumping text into
a semantic store: uniform sentence starts, meta-framing ("the author..."), and
enumerated boilerplate cause thoughts to cosine-cluster on their *shape*
instead of their *meaning*. This module names that failure explicitly in the
system contract given to the model.

Usage:
    python ingest_text.py --entity journal-2026-09-02 --file inputs/note.txt
    python ingest_text.py --entity essay-x --text "..." --dry-run
    Get-Content note.md | python ingest_text.py --entity essay-x --stdin

Requires: server running on 127.0.0.1:8000, LM Studio serving embeddings on
1234, and Copilot CLI installed at %APPDATA%\\npm\\copilot.cmd (or on PATH).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Iterable

import requests

API_BASE = "http://127.0.0.1:8000"
CLI_TIMEOUT_SECONDS = 240
DEFAULT_MODEL = "auto"
DEFAULT_EFFORT = "medium"
DEFAULT_CHUNK_CHARS = 3500
MIN_THOUGHT_CHARS = 6

# The anti-cluster contract. This is the load-bearing string in the whole
# pipeline. Every rule targets a concrete way that mass-ingested text
# collapses into false clusters in cosine space.
SPLITTER_PROMPT_TEMPLATE = """\
You are decomposing a block of source text into atomic thoughts that will be
injected as individual nodes into an associative semantic vector store. The
store uses sentence-embedding cosine similarity to draw edges between thoughts,
so uniform surface patterns (repeated prefixes, meta-framing, enumeration,
consistent voice shifts) create FALSE semantic bonds. Your job is to emit
thoughts that cluster only on real meaning.

Hard rules — violating any of these poisons the corpus:

1. Output ONE thought per line. Separate thoughts with a single blank line.
   No numbering, no bullets, no dashes, no headings, no surrounding quotes,
   no code fences. Just the thought text.

2. A thought is an *idea unit*, not a sentence unit. One paragraph often
   yields several thoughts. One sentence occasionally is one thought. If a
   sentence contains three claims stapled together, split them.

3. Preserve the source's voice and grammatical person. First-person source ->
   first-person thoughts. Essayistic source -> declarative thoughts in the
   same register. Never write "the author argues", "the text says", "the
   passage describes", or any other meta-framing. No third-person
   summarization of the source itself.

4. Deliberately vary how thoughts open. Do not let consecutive thoughts start
   with the same subject or the same connective ("The", "It", "This", "Also",
   "However", "Furthermore"). If two natural phrasings would collide,
   rephrase one so the openings differ.

5. Vary length across the batch. Some thoughts are five words. Some are
   thirty-five. Uniform length reads as uniform meaning in embedding space.

6. Preserve concrete nouns, proper names, numbers, dates, quoted phrases,
   and specific sensory images verbatim wherever possible. Abstract
   paraphrase destroys retrievability. Lift a phrase before you generalize
   it.

7. Do not invent, extrapolate, or add commentary. Only decompose what the
   source actually contains.

8. Emit ONLY the thoughts. No preamble ("Here are the thoughts:"), no trailing
   summary, no notes, no explanation of your process. First line of output is
   the first thought. Last line of output is the last thought.

{voice_clause}
---
SOURCE TEXT:
{chunk}
---

Emit the atomic thoughts now."""


@dataclass
class IngestReport:
    entity: str
    submitted: int = 0
    stored: int = 0
    duplicates: int = 0
    errors: int = 0
    thoughts: list[str] = field(default_factory=list)
    server_status: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Copilot CLI invocation
# ---------------------------------------------------------------------------

_CMD_LOADER_RE = re.compile(r'"([^"]+?\.js)"')


def _unwrap_shim(shim_path: str) -> list[str] | None:
    """Turn a .cmd/.bat npm shim into a direct `node <loader.js>` argv.

    This is load-bearing on Windows. A .cmd shim is executed through cmd.exe,
    and cmd.exe terminates its command line at the first newline — so the
    multi-line splitter prompt passed via `-p` silently arrives truncated to
    its first line and the model never sees the SOURCE TEXT. Calling node with
    the loader script directly goes through CreateProcess, which preserves
    newlines inside a single argument.
    """
    try:
        with open(shim_path, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
    except OSError:
        return None
    shim_dir = os.path.dirname(os.path.abspath(shim_path))
    for raw in _CMD_LOADER_RE.findall(body):
        loader = raw.replace("%dp0%", shim_dir + os.sep).replace("%~dp0", shim_dir + os.sep)
        loader = os.path.normpath(os.path.expandvars(loader))
        if not os.path.exists(loader):
            continue
        local_node = os.path.join(shim_dir, "node.exe")
        node = local_node if os.path.exists(local_node) else shutil.which("node")
        if node:
            return [node, loader]
    return None


def resolve_copilot() -> list[str] | None:
    """Return an argv prefix that invokes Copilot CLI, or None.

    Prefers a real executable or a direct node invocation over a .cmd shim,
    because only those can carry a multi-line prompt argument intact.
    """
    candidates: list[str] = []
    for name in ("copilot.exe", "copilot.cmd", "copilot.bat", "copilot"):
        path = shutil.which(name)
        if path and not path.lower().endswith(".ps1"):
            candidates.append(path)
    fallback = os.path.expandvars(r"%APPDATA%\npm\copilot.cmd")
    if os.path.exists(fallback):
        candidates.append(fallback)

    shims: list[str] = []
    for path in candidates:
        if path.lower().endswith((".cmd", ".bat")):
            unwrapped = _unwrap_shim(path)
            if unwrapped:
                return unwrapped
            shims.append(path)
        else:
            return [path]
    return [shims[0]] if shims else None


def ask_copilot(copilot_argv: list[str], prompt: str, model: str, effort: str) -> str:
    """Non-interactive Copilot CLI call in pure-completion mode.

    Copilot CLI is normally an agent — with --allow-all-tools it will happily
    grep the workspace and shell out. We suppress that with `--available-tools`
    (no args = empty allow-list = model cannot invoke any tool), and pin it
    down further with --no-ask-user, --disable-builtin-mcps, and
    --no-custom-instructions so nothing from the surrounding project bleeds
    into the decomposition. `-s` strips the stats banner from stdout; the
    stats footer still lands on stderr and is discarded.
    """
    argv = list(copilot_argv) + ["--model", model]
    # `auto` picks a model at request time and rejects --reasoning-effort;
    # only send the effort knob when we've pinned a specific model.
    if model.lower() != "auto":
        argv += ["--reasoning-effort", effort]
    argv += [
        "--allow-all-tools",       # still required for non-interactive mode
        "--available-tools",       # ...but expose an empty tool set
        "--no-ask-user",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-eager-powershell-resolution",
        "-s",
        "-p", prompt,
    ]
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CLI_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0 and not (result.stdout or "").strip():
        raise RuntimeError(
            f"Copilot CLI exited {result.returncode}: "
            f"{(result.stderr or '').strip()[:400]}"
        )
    return (result.stdout or "").strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, budget: int) -> list[str]:
    """Paragraph-aware chunker. Keeps paragraphs whole when possible;
    falls back to sentence-boundary splits for oversized paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    if len(text) <= budget:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in paragraphs:
        if len(para) > budget:
            # flush current buffer, then hard-split this giant paragraph on
            # sentence boundaries.
            if buf:
                chunks.append("\n\n".join(buf))
                buf, size = [], 0
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sub: list[str] = []
            sub_size = 0
            for sent in sentences:
                if sub_size + len(sent) + 1 > budget and sub:
                    chunks.append(" ".join(sub))
                    sub, sub_size = [], 0
                sub.append(sent)
                sub_size += len(sent) + 1
            if sub:
                chunks.append(" ".join(sub))
            continue
        if size + len(para) + 2 > budget and buf:
            chunks.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


# ---------------------------------------------------------------------------
# Model output cleanup
# ---------------------------------------------------------------------------

_ENUM_PREFIX_RE = re.compile(r"^\s*(?:[-*\u2022\u2013\u2014]|\d+[.)])\s+")
_QUOTED_RE = re.compile(r'^\s*["\u201c\u2018\']\s*(.*?)\s*["\u201d\u2019\']\s*$')
_META_PREAMBLE_RE = re.compile(
    r"^(here are|the following|below (?:are|is)|thought[s]?\s*:|extracted|"
    r"okay,? here|sure,? here|i(?:'ve| have) extracted)",
    re.IGNORECASE,
)


def clean_thoughts(raw: str) -> list[str]:
    """Split the model's response into individual thought strings and strip
    the shapes we told it not to emit — belt-and-suspenders for the prompt."""
    if not raw:
        return []
    # Sever any accidental preamble line before the first blank line.
    lines = [ln.rstrip() for ln in raw.split("\n")]

    # Drop leading obvious preambles.
    while lines and _META_PREAMBLE_RE.match(lines[0].strip()):
        lines.pop(0)

    # Split on blank lines to get thought blocks; within a block, join runaway
    # wraps back into one line so multiline poetic thoughts survive.
    thoughts: list[str] = []
    block: list[str] = []
    for line in lines + [""]:
        stripped = line.strip()
        if not stripped:
            if block:
                thoughts.append(" ".join(block).strip())
                block = []
            continue
        block.append(stripped)

    cleaned: list[str] = []
    for t in thoughts:
        t = _ENUM_PREFIX_RE.sub("", t).strip()
        m = _QUOTED_RE.match(t)
        if m:
            t = m.group(1).strip()
        # Kill remaining wrapping backticks / trailing commas the model likes.
        t = t.strip("`").strip().rstrip(",;")
        if len(t) < MIN_THOUGHT_CHARS:
            continue
        # Reject anything that still reads as meta-commentary about the source.
        if re.match(r"^(the (author|text|passage|source|piece|article)|"
                    r"this (text|passage|excerpt|piece) )", t, re.IGNORECASE):
            continue
        cleaned.append(t)
    return cleaned


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

def inject_thought(entity: str, text: str, metadata: dict | None = None,
                   session: requests.Session | None = None) -> dict:
    session = session or requests
    resp = session.post(
        f"{API_BASE}/api/entities/{entity}/thoughts",
        json={"text": text, **({"metadata": metadata} if metadata else {})},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def build_prompt(chunk: str, voice: str | None) -> str:
    voice_clause = ""
    if voice:
        voice_clause = (
            f"Additional voice constraint from the operator: {voice.strip()}\n"
            "Honor it, but not at the cost of any of the eight rules above.\n"
        )
    return SPLITTER_PROMPT_TEMPLATE.format(
        chunk=chunk.strip(),
        voice_clause=voice_clause,
    )


def read_source(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    if args.stdin or not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --text, --file, or pipe text via --stdin.")


def ingest(
    entity: str,
    source_text: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    voice: str | None = None,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    dry_run: bool = False,
    source_label: str | None = None,
    verbose: bool = True,
) -> IngestReport:
    """The public entry point. Returns a summary report."""
    copilot_argv = resolve_copilot()
    if not copilot_argv:
        raise RuntimeError(
            "Copilot CLI not found. Install it and ensure copilot.cmd is on PATH."
        )
    if verbose:
        print(f"[copilot] launcher: {' '.join(copilot_argv)}")

    chunks = chunk_text(source_text, chunk_chars)
    if verbose:
        print(f"[chunker] {len(chunks)} chunk(s), "
              f"{sum(len(c) for c in chunks)} chars total")

    all_thoughts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        if verbose:
            print(f"[copilot {i}/{len(chunks)}] model={model} "
                  f"effort={effort} chars={len(chunk)}")
        prompt = build_prompt(chunk, voice)
        t0 = time.time()
        raw = ask_copilot(copilot_argv, prompt, model, effort)
        elapsed = time.time() - t0
        thoughts = clean_thoughts(raw)
        if verbose:
            print(f"[copilot {i}/{len(chunks)}] {len(thoughts)} thought(s) "
                  f"in {elapsed:.1f}s")
        all_thoughts.extend(thoughts)

    # Intra-batch dedupe (case- and whitespace-insensitive) so the model
    # repeating an idea across chunks doesn't hit the API twice.
    seen: set[str] = set()
    deduped: list[str] = []
    for t in all_thoughts:
        key = re.sub(r"\s+", " ", t.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)

    report = IngestReport(entity=entity, thoughts=deduped)

    if dry_run:
        if verbose:
            print(f"[dry-run] would inject {len(deduped)} thought(s) into "
                  f"entity '{entity}'.")
        return report

    session = requests.Session()
    metadata: dict = {"source": "ingest_text.py"}
    if source_label:
        metadata["source_label"] = source_label

    for idx, t in enumerate(deduped, 1):
        report.submitted += 1
        try:
            payload = inject_thought(entity, t, metadata, session)
            status = payload.get("status", "?")
            report.server_status.append(status)
            if status == "stored":
                report.stored += 1
            elif status == "duplicate":
                report.duplicates += 1
            if verbose:
                marker = {"stored": "+", "duplicate": "="}.get(status, "?")
                preview = t if len(t) <= 80 else t[:77] + "..."
                print(f"[{idx:>3}/{len(deduped)}] {marker} {status:<9} {preview}")
        except requests.HTTPError as exc:
            report.errors += 1
            report.server_status.append(f"error:{exc.response.status_code}")
            if verbose:
                print(f"[{idx:>3}/{len(deduped)}] ! HTTP {exc.response.status_code}: {exc}")
        except requests.RequestException as exc:
            report.errors += 1
            report.server_status.append("error:network")
            if verbose:
                print(f"[{idx:>3}/{len(deduped)}] ! network: {exc}")

    if verbose:
        print(f"\n[done] entity='{entity}' "
              f"submitted={report.submitted} stored={report.stored} "
              f"duplicate={report.duplicates} error={report.errors}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Decompose text into atomic thoughts and inject them "
                    "into a named entity mind map.",
    )
    p.add_argument("--entity", required=True,
                   help="Target entity name (created on first write).")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="Inline text block.")
    src.add_argument("--file", help="Path to a UTF-8 text file.")
    src.add_argument("--stdin", action="store_true",
                     help="Read source from stdin.")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Copilot CLI model (default: {DEFAULT_MODEL}).")
    p.add_argument("--reasoning-effort", default=DEFAULT_EFFORT,
                   choices=["none", "minimal", "low", "medium", "high"],
                   help="Copilot CLI reasoning effort.")
    p.add_argument("--voice", default=None,
                   help="Optional voice/register hint appended to the prompt.")
    p.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS,
                   help="Chunk budget in characters.")
    p.add_argument("--source-label", default=None,
                   help="Optional metadata tag stored on every injected thought.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the extracted thoughts without injecting.")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output.")

    args = p.parse_args()
    text = read_source(args)
    if not text.strip():
        print("Empty source text.", file=sys.stderr)
        return 2

    report = ingest(
        entity=args.entity,
        source_text=text,
        model=args.model,
        effort=args.reasoning_effort,
        voice=args.voice,
        chunk_chars=args.chunk_chars,
        dry_run=args.dry_run,
        source_label=args.source_label,
        verbose=not args.quiet,
    )

    if args.dry_run:
        print("\n----- extracted thoughts -----")
        for t in report.thoughts:
            print(t)
            print()
    return 0 if report.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
