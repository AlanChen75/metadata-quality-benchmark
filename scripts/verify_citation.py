#!/usr/bin/env python3
"""
Cross-database citation metadata verification tool.
Queries CrossRef, OpenAlex, and Semantic Scholar
for each citation, then compares metadata across sources.

Usage:
    python3 verify_citation.py --doi "10.1038/s41598-023-41032-5"
    python3 verify_citation.py --batch citations.jsonl --output results.jsonl
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional

# Rate limiting config
RATE_LIMITS = {
    "crossref": 0.5,    # 2 req/sec (polite pool)
    "openalex": 0.1,    # 10 req/sec (free key)
    "s2": 1.1,          # 1 req/sec (free key)
}

CROSSREF_MAILTO = "d11351004@mail.ntust.edu.tw"
OPENALEX_KEY = ""  # Set via env or config
S2_KEY = ""  # Set via env or config


@dataclass
class DBMetadata:
    """Metadata returned by a single database."""
    source: str
    found: bool
    title: Optional[str] = None
    authors: Optional[list] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    raw: Optional[dict] = None


def fetch_crossref(doi: str) -> DBMetadata:
    """Query CrossRef API for DOI metadata."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}?mailto={CROSSREF_MAILTO}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())["message"]

        authors = []
        for a in data.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        year = None
        for date_field in ["published-print", "published-online", "issued"]:
            if date_field in data and data[date_field].get("date-parts"):
                parts = data[date_field]["date-parts"][0]
                if parts and parts[0]:
                    year = parts[0]
                    break

        return DBMetadata(
            source="crossref",
            found=True,
            title=data.get("title", [None])[0] if data.get("title") else None,
            authors=authors if authors else None,
            year=year,
            journal=data.get("container-title", [None])[0] if data.get("container-title") else None,
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("page"),
            doi=data.get("DOI"),
        )
    except Exception as e:
        return DBMetadata(source="crossref", found=False, raw={"error": str(e)})


def fetch_openalex(doi: str) -> DBMetadata:
    """Query OpenAlex API for DOI metadata."""
    url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi, safe='')}"
    if OPENALEX_KEY:
        url += f"?api_key={OPENALEX_KEY}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        authors = []
        for a in data.get("authorships", []):
            name = a.get("author", {}).get("display_name")
            if name:
                authors.append(name)

        journal = None
        loc = data.get("primary_location", {})
        if loc and loc.get("source"):
            journal = loc["source"].get("display_name")

        biblio = data.get("biblio", {})

        return DBMetadata(
            source="openalex",
            found=True,
            title=data.get("title"),
            authors=authors if authors else None,
            year=data.get("publication_year"),
            journal=journal,
            volume=biblio.get("volume"),
            issue=biblio.get("issue"),
            pages=f"{biblio.get('first_page', '')}-{biblio.get('last_page', '')}" if biblio.get("first_page") else None,
            doi=data.get("doi", "").replace("https://doi.org/", "") if data.get("doi") else None,
        )
    except Exception as e:
        return DBMetadata(source="openalex", found=False, raw={"error": str(e)})


def fetch_s2(doi: str) -> DBMetadata:
    """Query Semantic Scholar API for DOI metadata."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='')}?fields=title,authors,year,venue,journal,externalIds"
    headers = {"User-Agent": "MetadataQualityBenchmark/1.0"}
    if S2_KEY:
        headers["x-api-key"] = S2_KEY
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        authors = [a.get("name") for a in data.get("authors", []) if a.get("name")]

        journal_info = data.get("journal", {})
        journal = journal_info.get("name") if journal_info else data.get("venue")
        volume = journal_info.get("volume") if journal_info else None
        pages = journal_info.get("pages") if journal_info else None

        ext_ids = data.get("externalIds", {})
        doi_val = ext_ids.get("DOI")

        return DBMetadata(
            source="s2",
            found=True,
            title=data.get("title"),
            authors=authors if authors else None,
            year=data.get("year"),
            journal=journal,
            volume=volume,
            pages=pages,
            doi=doi_val,
        )
    except Exception as e:
        return DBMetadata(source="s2", found=False, raw={"error": str(e)})


def compare_field(field_name: str, values: dict) -> dict:
    """Compare a metadata field across databases.

    Returns comparison result with agreement level.
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    if not non_null:
        return {"field": field_name, "status": "all_missing", "values": values, "agreement": None}

    unique_vals = set()
    for v in non_null.values():
        if isinstance(v, list):
            unique_vals.add(tuple(sorted(str(x).lower().strip() for x in v)))
        else:
            unique_vals.add(str(v).lower().strip())

    if len(unique_vals) == 1:
        status = "unanimous"
    elif len(unique_vals) == len(non_null):
        status = "all_different"
    else:
        status = "partial_agreement"

    return {
        "field": field_name,
        "status": status,
        "values": {k: v for k, v in values.items()},
        "agreement": len(non_null) - len(unique_vals) + 1 if len(unique_vals) > 0 else 0,
        "sources_found": len(non_null),
        "sources_total": len(values),
    }


def verify_single(doi: str) -> dict:
    """Verify a single DOI across all databases."""
    results = {}

    # CrossRef
    results["crossref"] = fetch_crossref(doi)
    time.sleep(RATE_LIMITS["crossref"])

    # OpenAlex
    results["openalex"] = fetch_openalex(doi)
    time.sleep(RATE_LIMITS["openalex"])

    # Semantic Scholar
    results["s2"] = fetch_s2(doi)
    time.sleep(RATE_LIMITS["s2"])

    # Cross-database comparison
    fields = ["title", "year", "journal", "volume", "pages", "doi"]
    comparisons = {}
    for field in fields:
        field_values = {}
        for db_name, db_result in results.items():
            if db_result.found:
                field_values[db_name] = getattr(db_result, field, None)
        comparisons[field] = compare_field(field, field_values)

    # Author comparison (special handling — list comparison)
    author_values = {}
    for db_name, db_result in results.items():
        if db_result.found and db_result.authors:
            author_values[db_name] = db_result.authors
    comparisons["authors"] = compare_field("authors", author_values)

    return {
        "doi": doi,
        "databases": {k: asdict(v) for k, v in results.items()},
        "comparisons": comparisons,
        "summary": {
            "databases_found": sum(1 for r in results.values() if r.found),
            "databases_total": len(results),
            "fields_unanimous": sum(1 for c in comparisons.values() if c["status"] == "unanimous"),
            "fields_with_discrepancy": sum(1 for c in comparisons.values() if c["status"] in ("partial_agreement", "all_different")),
            "fields_all_missing": sum(1 for c in comparisons.values() if c["status"] == "all_missing"),
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Cross-database citation metadata verification")
    parser.add_argument("--doi", help="Single DOI to verify")
    parser.add_argument("--batch", help="JSONL file with DOIs to verify (one per line, field: doi)")
    parser.add_argument("--output", default="results.jsonl", help="Output JSONL file")
    args = parser.parse_args()

    if args.doi:
        result = verify_single(args.doi)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.batch:
        with open(args.batch) as f:
            citations = [json.loads(line) for line in f if line.strip()]

        total = len(citations)
        with open(args.output, "w") as out:
            for i, cit in enumerate(citations):
                doi = cit.get("doi", "")
                if not doi:
                    continue
                print(f"[{i+1}/{total}] Verifying {doi}...", file=sys.stderr)
                result = verify_single(doi)
                result["meta"] = {k: v for k, v in cit.items() if k != "doi"}
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()

        print(f"Done. {total} citations verified → {args.output}", file=sys.stderr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
