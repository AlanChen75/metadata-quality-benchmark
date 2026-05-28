#!/usr/bin/env python3
"""Re-collect Semantic Scholar metadata with an authenticated API key.

The original verify_fast.py queried S2 in parallel with no retry/backoff, so
~77% of requests were silently dropped by the free shared pool (HTTP 429) and
recorded as found=False. This script re-queries every DOI politely:

  - authenticated via S2 API key (env var S2_API_KEY)
  - 1.1s delay between requests (below the 1 req/s ceiling)
  - exponential backoff on HTTP 429 (5/10/20/40/60/90/120s, up to 7 retries)

Output schema for each DOI mirrors fetch_s2() in verify_fast.py exactly, so the
result can be merged back into verification_results.jsonl for re-analysis.

Usage:
    S2_API_KEY=<key> python3 recollect_s2.py \
        --dois data/s2_recollect_dois.txt \
        --output data/s2_recollected.jsonl
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

S2_FIELDS = "title,authors,year,venue,journal,externalIds"
DELAY_SECONDS = 1.1
# Backoff schedule for the rate-limited free tier: a 429 waits up to
# 5+10+20+40+60+90+120 = 345s across 7 retries before being recorded as failed.
BACKOFF_SCHEDULE = (5, 10, 20, 40, 60, 90, 120)


def fetch_s2(doi: str, api_key: Optional[str]) -> dict:
    """Query S2 for one DOI. Returns the same dict shape as verify_fast.fetch_s2.

    api_key is optional: when None, the request hits the unauthenticated shared
    pool (5,000 req / 5 min global) and relies on backoff to ride out 429s.
    """
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/"
        f"DOI:{urllib.parse.quote(doi, safe='')}?fields={S2_FIELDS}"
    )
    headers = {"User-Agent": "MetadataQualityBenchmark/1.0"}
    if api_key:
        headers["x-api-key"] = api_key

    for attempt in range(len(BACKOFF_SCHEDULE) + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            authors = [a.get("name") for a in data.get("authors", []) if a.get("name")]
            ji = data.get("journal") or {}
            return {
                "source": "s2",
                "found": True,
                "title": data.get("title"),
                "authors": authors or None,
                "year": data.get("year"),
                "journal": ji.get("name") or data.get("venue"),
                "volume": ji.get("volume"),
                "pages": ji.get("pages"),
                "doi": (data.get("externalIds") or {}).get("DOI"),
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"source": "s2", "found": False, "http_status": 404}
            if exc.code == 429 and attempt < len(BACKOFF_SCHEDULE):
                time.sleep(BACKOFF_SCHEDULE[attempt])
                continue
            return {"source": "s2", "found": False, "http_status": exc.code}
        except Exception as exc:  # noqa: BLE001 - record reason, keep going
            return {"source": "s2", "found": False, "error": type(exc).__name__}
    return {"source": "s2", "found": False, "http_status": 429}


def load_done(output_path: str) -> set:
    """Resume support: DOIs already written are skipped on re-run."""
    done = set()
    if os.path.exists(output_path):
        for line in open(output_path):
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["doi"])
            except Exception:  # noqa: BLE001
                continue
    return done


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dois", required=True, help="text file, one DOI per line")
    parser.add_argument("--output", required=True, help="output jsonl path")
    args = parser.parse_args()

    api_key: Optional[str] = os.environ.get("S2_API_KEY") or None
    print(f"auth={'API key' if api_key else 'UNAUTHENTICATED (shared pool + backoff)'}", flush=True)

    dois = [d.strip() for d in open(args.dois) if d.strip()]
    done = load_done(args.output)
    todo = [d for d in dois if d not in done]
    print(f"total={len(dois)} already_done={len(done)} to_query={len(todo)}", flush=True)

    found = 0
    with open(args.output, "a") as out:
        for i, doi in enumerate(todo, 1):
            rec = fetch_s2(doi, api_key)
            found += int(bool(rec.get("found")))
            out.write(json.dumps({"doi": doi, "s2": rec}, ensure_ascii=False) + "\n")
            out.flush()
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  found_so_far={found}", flush=True)
            time.sleep(DELAY_SECONDS)

    print(f"DONE. queried={len(todo)} newly_found={found}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
