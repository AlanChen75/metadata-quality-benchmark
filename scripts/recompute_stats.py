#!/usr/bin/env python3
"""Compute significance tests and effect sizes from verification_results.jsonl.

Recomputes statistical_tests.json (chi-square tests for domain and source,
two- vs three-source comparison, field-level discrepancy distribution, and the
CrossRef/OpenAlex sensitivity analysis) from the cross-database verification output.

Usage:
    python3 recompute_stats.py --input data/verification_results.jsonl \
        --output results/statistical_tests.json
"""

import argparse
import json
from collections import Counter
from typing import List

from scipy.stats import chi2_contingency

FIELDS = ["title", "year", "journal", "volume", "pages", "doi", "authors"]
CORE_DBS = ["crossref", "openalex", "s2"]


def load(path: str) -> List[dict]:
    rows = []
    skipped = 0
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            skipped += 1
    if skipped:
        print(f"WARNING: skipped {skipped} malformed line(s) in {path}")
    return rows


def has_disagreement(rec: dict) -> bool:
    return rec["summary"]["fields_with_discrepancy"] > 0


def n_sources(rec: dict) -> int:
    return sum(1 for db in CORE_DBS
               if rec["databases"].get(db) and rec["databases"][db].get("found"))


def chi2_two_groups(table: List[List[int]]) -> dict:
    chi2, p, dof, _ = chi2_contingency(table, correction=False)
    return {"chi2": round(chi2, 3), "df": dof, "p_value": round(p, 6)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/verification_results.jsonl")
    ap.add_argument("--output", default="results/statistical_tests.json")
    args = ap.parse_args()

    rows = load(args.input)
    n = len(rows)

    # --- domain chi-square: domain x (>=1 disagreement) ---
    domains = sorted({r["meta"].get("domain", "?") for r in rows})
    dom_tab = []
    dom_rates = {}
    for dm in domains:
        sub = [r for r in rows if r["meta"].get("domain") == dm]
        disc = sum(1 for r in sub if has_disagreement(r))
        dom_tab.append([disc, len(sub) - disc])
        dom_rates[dm] = {"n": len(sub), "disc": disc, "rate": round(100 * disc / len(sub), 1)}

    # --- AI vs database-sampled chi-square: source x (>=1 disagreement) ---
    src_tab = []
    src_rates = {}
    for st in ["ai", "human"]:
        sub = [r for r in rows if r["meta"].get("source_type") == st]
        disc = sum(1 for r in sub if has_disagreement(r))
        src_tab.append([disc, len(sub) - disc])
        src_rates[st] = {"n": len(sub), "disc": disc, "rate": round(100 * disc / max(len(sub), 1), 1)}

    # --- two-source vs three-source citations ---
    two = [r for r in rows if n_sources(r) == 2]
    three = [r for r in rows if n_sources(r) == 3]

    # --- field-level discrepancy distribution ---
    field_disc = Counter()
    total_field_disc = 0
    for r in rows:
        for f in FIELDS:
            if r["comparisons"][f]["status"] not in ("unanimous", "all_missing"):
                field_disc[f] += 1
                total_field_disc += 1

    # --- CrossRef+OpenAlex-only sensitivity (citations found by BOTH) ---
    cr_oa = [r for r in rows
             if r["databases"].get("crossref", {}).get("found")
             and r["databases"].get("openalex", {}).get("found")]
    cr_oa_pairs = 0
    cr_oa_disc_pairs = 0
    cr_oa_cit_disc = 0
    for r in cr_oa:
        cit_has = False
        for f in FIELDS:
            comp = r["comparisons"][f]
            vals = comp.get("values", {})
            if "crossref" in vals and "openalex" in vals:
                cr_oa_pairs += 1
                if str(vals["crossref"]).lower() != str(vals["openalex"]).lower():
                    cr_oa_disc_pairs += 1
                    cit_has = True
        if cit_has:
            cr_oa_cit_disc += 1

    overall_disc = sum(1 for r in rows if has_disagreement(r))

    out = {
        "total_citations": n,
        "citations_with_disagreement": {
            "n": overall_disc, "rate_pct": round(100 * overall_disc / n, 1),
        },
        "chi_square_domain": chi2_two_groups(dom_tab),
        "domain_rates": dom_rates,
        "chi_square_ai_vs_database": chi2_two_groups(src_tab),
        "source_rates": src_rates,
        "two_vs_three_source": {
            "two_src": {"n": len(two), "disc": sum(1 for r in two if has_disagreement(r))},
            "three_src": {"n": len(three), "disc": sum(1 for r in three if has_disagreement(r))},
        },
        "error_type_distribution": dict(field_disc.most_common()),
        "total_field_discrepancies": total_field_disc,
        "cr_oa_only_sensitivity": {
            "n_citations_both": len(cr_oa),
            "checkable_pairs": cr_oa_pairs,
            "disagreeing_pairs": cr_oa_disc_pairs,
            "field_disc_rate_pct": round(100 * cr_oa_disc_pairs / max(cr_oa_pairs, 1), 1),
            "citations_with_disc_pct": round(100 * cr_oa_cit_disc / max(len(cr_oa), 1), 1),
        },
        "_note": "Recomputed after authenticated S2 re-collection; supersedes pre-recollect values.",
    }

    with open(args.output, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
