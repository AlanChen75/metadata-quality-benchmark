#!/usr/bin/env python3
"""
Build a unified JSONL batch file for cross-database verification.
Combines all AI-generated and human-authored citations.
"""

import json
import glob
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUTPUT = os.path.join(DATA_DIR, "all_citations.jsonl")


def main():
    all_citations = []

    # 1. Claude citations (5 domain files)
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "citations_claude_*.json"))):
        data = json.load(open(f))
        domain = data["domain"]
        for cit in data["citations"]:
            doi = cit.get("doi")
            if doi and not doi.startswith("10.48550"):  # Skip arXiv DOIs
                all_citations.append({
                    "doi": doi,
                    "source_type": "ai",
                    "llm": "claude",
                    "llm_type": "commercial",
                    "domain": domain,
                    "original_metadata": cit,
                })

    # 2. Other LLM citations (4 files)
    llm_configs = {
        "citations_gpt5nano.json": ("gpt-4.1-nano", "commercial"),
        "citations_gemini.json": ("gemini-3-flash", "commercial"),
        "citations_llama70b.json": ("llama-3.3-70b", "open_source"),
        "citations_llama8b.json": ("llama-3.1-8b", "open_source"),
    }

    for fname, (llm_name, llm_type) in llm_configs.items():
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        data = json.load(open(fpath))
        for domain, domain_data in data["domains"].items():
            for cit in domain_data.get("citations", []):
                doi = cit.get("doi")
                if doi and not doi.startswith("10.48550"):
                    all_citations.append({
                        "doi": doi,
                        "source_type": "ai",
                        "llm": llm_name,
                        "llm_type": llm_type,
                        "domain": domain,
                        "original_metadata": cit,
                    })

    # 3. Human citations
    human_path = os.path.join(DATA_DIR, "citations_human.json")
    if os.path.exists(human_path):
        data = json.load(open(human_path))
        for domain, domain_data in data["domains"].items():
            for cit in domain_data.get("citations", []):
                doi = cit.get("doi")
                if doi:
                    all_citations.append({
                        "doi": doi,
                        "source_type": "human",
                        "llm": "none",
                        "llm_type": "none",
                        "domain": domain,
                        "original_metadata": {
                            "title": cit.get("title"),
                            "authors": cit.get("authors"),
                            "year": cit.get("year"),
                            "journal": cit.get("journal"),
                            "volume": cit.get("volume"),
                            "pages": cit.get("pages"),
                        },
                    })

    # Deduplicate by DOI (keep first occurrence)
    seen = set()
    unique = []
    for cit in all_citations:
        doi_lower = cit["doi"].lower()
        if doi_lower not in seen:
            seen.add(doi_lower)
            unique.append(cit)

    # Write JSONL
    with open(OUTPUT, "w") as f:
        for cit in unique:
            f.write(json.dumps(cit, ensure_ascii=False) + "\n")

    # Stats
    by_source = {}
    by_domain = {}
    by_llm = {}
    for cit in unique:
        by_source[cit["source_type"]] = by_source.get(cit["source_type"], 0) + 1
        by_domain[cit["domain"]] = by_domain.get(cit["domain"], 0) + 1
        if cit["source_type"] == "ai":
            by_llm[cit["llm"]] = by_llm.get(cit["llm"], 0) + 1

    print(f"Total unique citations: {len(unique)}", file=sys.stderr)
    print(f"\nBy source:", file=sys.stderr)
    for k, v in sorted(by_source.items()):
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nBy domain:", file=sys.stderr)
    for k, v in sorted(by_domain.items()):
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nBy LLM (AI only):", file=sys.stderr)
    for k, v in sorted(by_llm.items()):
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nOutput: {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
