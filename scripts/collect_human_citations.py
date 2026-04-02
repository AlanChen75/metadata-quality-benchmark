#!/usr/bin/env python3
"""
Collect human-authored citations by sampling DOIs from CrossRef
across 5 academic domains using subject-based filtering.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

DOMAINS = {
    "cs_ml": {
        "query": "transformer natural language processing",
        "filter": "has-abstract:true,from-pub-date:2018-01-01,until-pub-date:2025-12-31",
        "target": 152,
    },
    "finance": {
        "query": "credit risk machine learning",
        "filter": "has-abstract:true,from-pub-date:2015-01-01,until-pub-date:2025-12-31",
        "target": 152,
    },
    "biomedicine": {
        "query": "deep learning medical image analysis",
        "filter": "has-abstract:true,from-pub-date:2016-01-01,until-pub-date:2025-12-31",
        "target": 152,
    },
    "engineering": {
        "query": "smart building energy efficiency IoT",
        "filter": "has-abstract:true,from-pub-date:2015-01-01,until-pub-date:2025-12-31",
        "target": 152,
    },
    "social_science": {
        "query": "ESG disclosure sustainability reporting",
        "filter": "has-abstract:true,from-pub-date:2015-01-01,until-pub-date:2025-12-31",
        "target": 152,
    },
}

MAILTO = "d11351004@mail.ntust.edu.tw"


def fetch_crossref_sample(query, filter_str, rows=152, offset=0):
    """Fetch DOIs from CrossRef search API."""
    params = urllib.parse.urlencode({
        "query": query,
        "filter": filter_str,
        "rows": rows,
        "offset": offset,
        "sort": "relevance",
        "select": "DOI,title,author,published-print,published-online,container-title,volume,issue,page",
        "mailto": MAILTO,
    })
    url = f"https://api.crossref.org/works?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    items = data.get("message", {}).get("items", [])
    citations = []
    for item in items:
        doi = item.get("DOI")
        if not doi:
            continue

        authors = []
        for a in item.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        title = item.get("title", [None])[0] if item.get("title") else None

        year = None
        for df in ["published-print", "published-online"]:
            if df in item and item[df].get("date-parts"):
                parts = item[df]["date-parts"][0]
                if parts and parts[0]:
                    year = parts[0]
                    break

        citations.append({
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": year,
            "journal": item.get("container-title", [None])[0] if item.get("container-title") else None,
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("page"),
            "source_type": "human",
        })

    return citations


def main():
    all_human = {}
    total = 0

    for domain, config in DOMAINS.items():
        print(f"\n[{domain}] Fetching {config['target']} citations...", file=sys.stderr)
        try:
            citations = fetch_crossref_sample(
                config["query"],
                config["filter"],
                rows=config["target"],
            )
            all_human[domain] = citations
            total += len(citations)
            print(f"  [{domain}] Got {len(citations)} citations", file=sys.stderr)
        except Exception as e:
            print(f"  [{domain}] ERROR: {e}", file=sys.stderr)
            all_human[domain] = []

        time.sleep(1)

    # Save
    output_path = os.path.join(OUTPUT_DIR, "citations_human.json")
    with open(output_path, "w") as f:
        json.dump({
            "source": "human",
            "method": "CrossRef search API sampling",
            "domains": {k: {"citations": v, "count": len(v)} for k, v in all_human.items()},
        }, f, indent=2, ensure_ascii=False)

    print(f"\nTotal: {total} human citations → {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
