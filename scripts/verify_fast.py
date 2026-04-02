#!/usr/bin/env python3
"""
Fast cross-database verification using concurrent requests.
CrossRef + OpenAlex run in parallel, then S2 with minimal delay.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

CROSSREF_MAILTO = "d11351004@mail.ntust.edu.tw"


def fetch_crossref(doi):
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}?mailto={CROSSREF_MAILTO}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())["message"]
        authors = [f"{a.get('given','')} {a.get('family','')}".strip() for a in data.get("author", [])]
        year = None
        for df in ["published-print", "published-online", "issued"]:
            if df in data and data[df].get("date-parts"):
                parts = data[df]["date-parts"][0]
                if parts and parts[0]:
                    year = parts[0]
                    break
        return {"source": "crossref", "found": True,
                "title": (data.get("title") or [None])[0],
                "authors": authors or None, "year": year,
                "journal": (data.get("container-title") or [None])[0],
                "volume": data.get("volume"), "issue": data.get("issue"),
                "pages": data.get("page"), "doi": data.get("DOI")}
    except:
        return {"source": "crossref", "found": False}


def fetch_openalex(doi):
    url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi, safe='')}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        authors = [a.get("author", {}).get("display_name") for a in data.get("authorships", []) if a.get("author", {}).get("display_name")]
        loc = data.get("primary_location", {}) or {}
        journal = (loc.get("source") or {}).get("display_name")
        biblio = data.get("biblio", {}) or {}
        pages = f"{biblio.get('first_page','')}-{biblio.get('last_page','')}" if biblio.get("first_page") else None
        return {"source": "openalex", "found": True,
                "title": data.get("title"), "authors": authors or None,
                "year": data.get("publication_year"), "journal": journal,
                "volume": biblio.get("volume"), "issue": biblio.get("issue"),
                "pages": pages, "doi": (data.get("doi") or "").replace("https://doi.org/", "") or None}
    except:
        return {"source": "openalex", "found": False}


def fetch_s2(doi):
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='')}?fields=title,authors,year,venue,journal,externalIds"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetadataQualityBenchmark/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        authors = [a.get("name") for a in data.get("authors", []) if a.get("name")]
        ji = data.get("journal") or {}
        return {"source": "s2", "found": True,
                "title": data.get("title"), "authors": authors or None,
                "year": data.get("year"),
                "journal": ji.get("name") or data.get("venue"),
                "volume": ji.get("volume"), "pages": ji.get("pages"),
                "doi": (data.get("externalIds") or {}).get("DOI")}
    except:
        return {"source": "s2", "found": False}


def compare_fields(results):
    fields = ["title", "year", "journal", "volume", "pages", "doi", "authors"]
    comparisons = {}
    for field in fields:
        values = {}
        for r in results:
            if r["found"] and r.get(field) is not None:
                values[r["source"]] = r[field]
        if not values:
            comparisons[field] = {"status": "all_missing", "values": {}}
        else:
            normed = set()
            for v in values.values():
                if isinstance(v, list):
                    normed.add(tuple(sorted(str(x).lower().strip() for x in v)))
                else:
                    normed.add(str(v).lower().strip())
            status = "unanimous" if len(normed) == 1 else ("all_different" if len(normed) == len(values) else "partial_agreement")
            comparisons[field] = {"status": status, "values": values, "sources_found": len(values)}
    return comparisons


def verify_one(doi):
    # All three APIs in parallel
    with ThreadPoolExecutor(max_workers=3) as ex:
        cr_future = ex.submit(fetch_crossref, doi)
        oa_future = ex.submit(fetch_openalex, doi)
        s2_future = ex.submit(fetch_s2, doi)
        cr = cr_future.result()
        oa = oa_future.result()
        s2 = s2_future.result()
    time.sleep(0.5)  # global rate limit between citations

    all_results = [cr, oa, s2]
    comparisons = compare_fields(all_results)

    return {
        "doi": doi,
        "databases": {r["source"]: r for r in all_results},
        "comparisons": comparisons,
        "summary": {
            "databases_found": sum(1 for r in all_results if r["found"]),
            "databases_total": 3,
            "fields_unanimous": sum(1 for c in comparisons.values() if c["status"] == "unanimous"),
            "fields_with_discrepancy": sum(1 for c in comparisons.values() if c["status"] in ("partial_agreement", "all_different")),
            "fields_all_missing": sum(1 for c in comparisons.values() if c["status"] == "all_missing"),
        }
    }


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/all_citations.jsonl"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/verification_results.jsonl"

    citations = [json.loads(l) for l in open(input_file) if l.strip()]
    total = len(citations)
    print(f"Verifying {total} citations...", file=sys.stderr)

    with open(output_file, "w") as out:
        for i, cit in enumerate(citations):
            doi = cit.get("doi", "")
            if not doi:
                continue
            if (i + 1) % 50 == 0 or i == 0:
                print(f"[{i+1}/{total}] {doi}", file=sys.stderr)

            try:
                result = verify_one(doi)
                result["meta"] = {k: v for k, v in cit.items() if k != "doi" and k != "original_metadata"}
                result["meta"]["domain"] = cit.get("domain", "unknown")
                result["meta"]["source_type"] = cit.get("source_type", "unknown")
                result["meta"]["llm"] = cit.get("llm", "none")
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()
            except Exception as e:
                print(f"  ERROR {doi}: {e}", file=sys.stderr)

    print(f"Done. {total} citations → {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
