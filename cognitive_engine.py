"""Manual cognition client: POST a single thought, print the gravitational field it lands in."""
import json
import sys
import textwrap

import requests

ENTITY = "keel-2026-08-25"
ENDPOINT = f"http://127.0.0.1:8000/api/entities/{ENTITY}/thoughts"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python cognitive_engine.py \"<thought>\"", file=sys.stderr)
        return 2

    text = sys.argv[1].strip()
    if not text:
        print("empty thought", file=sys.stderr)
        return 2

    try:
        resp = requests.post(ENDPOINT, json={"text": text}, timeout=60)
    except requests.RequestException as e:
        print(f"network error: {e}", file=sys.stderr)
        return 1

    print(f"[POST {ENDPOINT}]")
    print(f"[HTTP {resp.status_code}]")

    try:
        payload = resp.json()
    except ValueError:
        print(resp.text)
        return 1 if resp.status_code >= 400 else 0

    status = payload.get("status", "?")
    entity = payload.get("entity", "?")
    print(f"status : {status}")
    print(f"entity : {entity}")
    print(f"thought: {text}")
    print("-" * 72)

    related = payload.get("related") or []
    if not related:
        print("(no reflection — the void answered. this is thought zero territory.)")
        return 0

    print(f"reflection ({len(related)} associated prior thought(s), nearest first):")
    for i, item in enumerate(related):
        # The API may return plain strings or {text, similarity, ...} dicts.
        if isinstance(item, dict):
            body = item.get("text") or item.get("thought") or json.dumps(item)
            sim = item.get("similarity")
            distance = item.get("distance")
            score_bits = []
            if sim is not None:
                score_bits.append(f"sim={sim:.4f}")
            if distance is not None:
                score_bits.append(f"dist={distance:.4f}")
            score = "  ".join(score_bits) if score_bits else "score=?"
        else:
            body = str(item)
            score = "score=?"
        wrapped = textwrap.fill(body, width=72, subsequent_indent="     ")
        print(f"  {i}. [{score}]")
        print(f"     {wrapped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
