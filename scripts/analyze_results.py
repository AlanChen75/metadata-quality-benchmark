#!/usr/bin/env python3
"""
Phase 7: Results Analysis
Analyzes cross-database verification results and generates tables/figures.

Usage:
    python3 analyze_results.py --input data/verification_results.jsonl --output-dir results/
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List


def load_results(path: str) -> List[dict]:
    """Load verification results from JSONL."""
    results = []
    with open(path) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def compute_db_field_accuracy(results: List[dict], ground_truth: Dict = None) -> dict:
    """
    RQ1: Database × Field accuracy matrix.
    Without ground truth, measure inter-database agreement.
    With ground truth, measure accuracy against publisher data.
    """
    databases = ["crossref", "openalex", "s2", "scholar"]
    fields = ["title", "year", "journal", "volume", "pages", "doi", "authors"]

    # Count agreements per DB×field
    matrix = {db: {f: {"total": 0, "unanimous": 0, "has_value": 0} for f in fields} for db in databases}

    for result in results:
        comparisons = result.get("comparisons", {})
        for field in fields:
            comp = comparisons.get(field, {})
            values = comp.get("values", {})
            status = comp.get("status", "all_missing")

            for db in databases:
                if db in values and values[db] is not None:
                    matrix[db][field]["has_value"] += 1
                    matrix[db][field]["total"] += 1
                    if status == "unanimous":
                        matrix[db][field]["unanimous"] += 1
                elif db not in values:
                    # DB didn't return this citation
                    pass
                else:
                    matrix[db][field]["total"] += 1

    # Compute rates
    accuracy = {}
    for db in databases:
        accuracy[db] = {}
        for field in fields:
            m = matrix[db][field]
            if m["has_value"] > 0:
                accuracy[db][field] = {
                    "coverage": m["has_value"] / max(m["total"], 1),
                    "agreement_rate": m["unanimous"] / m["has_value"] if m["has_value"] > 0 else 0,
                    "n": m["has_value"],
                }
            else:
                accuracy[db][field] = {"coverage": 0, "agreement_rate": 0, "n": 0}

    return accuracy


def compute_domain_variation(results: List[dict]) -> dict:
    """
    RQ2: Cross-domain variation in metadata quality.
    """
    domain_stats = defaultdict(lambda: {"total": 0, "discrepancies": 0, "fields_checked": 0})

    for result in results:
        domain = result.get("meta", {}).get("domain", "unknown")
        summary = result.get("summary", {})
        domain_stats[domain]["total"] += 1
        domain_stats[domain]["discrepancies"] += summary.get("fields_with_discrepancy", 0)
        domain_stats[domain]["fields_checked"] += summary.get("fields_unanimous", 0) + summary.get("fields_with_discrepancy", 0)

    # Compute rates
    domain_rates = {}
    for domain, stats in domain_stats.items():
        if stats["fields_checked"] > 0:
            domain_rates[domain] = {
                "n_citations": stats["total"],
                "discrepancy_rate": stats["discrepancies"] / stats["fields_checked"],
                "avg_discrepancies_per_citation": stats["discrepancies"] / stats["total"],
            }

    return domain_rates


def compute_group_comparison(results: List[dict]) -> dict:
    """
    RQ3: Group A (GS only) vs B (CR+OA+S2) vs C (all four).
    Measure discrepancy detection rate per group.
    """
    groups = {
        "A_gs_only": ["scholar"],
        "B_cr_oa_s2": ["crossref", "openalex", "s2"],
        "C_all_four": ["crossref", "openalex", "s2", "scholar"],
    }

    group_stats = {g: {"detected": 0, "total_fields": 0, "coverage": 0} for g in groups}

    for result in results:
        comparisons = result.get("comparisons", {})
        for field, comp in comparisons.items():
            values = comp.get("values", {})

            for group_name, group_dbs in groups.items():
                group_values = {db: v for db, v in values.items() if db in group_dbs and v is not None}
                group_stats[group_name]["total_fields"] += 1

                if len(group_values) >= 2:
                    # Can detect discrepancy
                    unique = set(str(v).lower().strip() for v in group_values.values())
                    if len(unique) > 1:
                        group_stats[group_name]["detected"] += 1

                if group_values:
                    group_stats[group_name]["coverage"] += 1

    group_results = {}
    for g, stats in group_stats.items():
        group_results[g] = {
            "detection_rate": stats["detected"] / max(stats["total_fields"], 1),
            "coverage_rate": stats["coverage"] / max(stats["total_fields"], 1),
            "discrepancies_found": stats["detected"],
        }

    return group_results


def compute_ai_vs_human(results: List[dict]) -> dict:
    """
    RQ4: AI-generated vs human-authored citation metadata quality.
    """
    source_stats = defaultdict(lambda: {"total": 0, "discrepancies": 0, "fields_checked": 0})

    for result in results:
        source = result.get("meta", {}).get("source_type", "unknown")  # "ai" or "human"
        llm = result.get("meta", {}).get("llm", "unknown")
        key = f"{source}_{llm}" if source == "ai" else "human"

        summary = result.get("summary", {})
        source_stats[key]["total"] += 1
        source_stats[key]["discrepancies"] += summary.get("fields_with_discrepancy", 0)
        source_stats[key]["fields_checked"] += summary.get("fields_unanimous", 0) + summary.get("fields_with_discrepancy", 0)

    rates = {}
    for key, stats in source_stats.items():
        if stats["fields_checked"] > 0:
            rates[key] = {
                "n_citations": stats["total"],
                "discrepancy_rate": stats["discrepancies"] / stats["fields_checked"],
                "avg_discrepancies_per_citation": stats["discrepancies"] / stats["total"],
            }

    return rates


def generate_table_markdown(data: dict, title: str) -> str:
    """Generate a markdown table from analysis results."""
    lines = [f"## {title}\n"]

    if not data:
        lines.append("*No data available*\n")
        return "\n".join(lines)

    # Auto-detect structure
    first_val = next(iter(data.values()))
    if isinstance(first_val, dict):
        # Nested dict — make a table
        inner_keys = list(first_val.keys())
        header = "| | " + " | ".join(str(k) for k in inner_keys) + " |"
        sep = "|---|" + "|".join("---" for _ in inner_keys) + "|"
        lines.extend([header, sep])

        for row_key, row_data in data.items():
            vals = []
            for ik in inner_keys:
                v = row_data.get(ik, "")
                if isinstance(v, float):
                    v = f"{v:.3f}"
                vals.append(str(v))
            lines.append(f"| {row_key} | " + " | ".join(vals) + " |")
    else:
        # Simple key-value
        lines.extend(["| Key | Value |", "|---|---|"])
        for k, v in data.items():
            if isinstance(v, float):
                v = f"{v:.3f}"
            lines.append(f"| {k} | {v} |")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze cross-database verification results")
    parser.add_argument("--input", required=True, help="JSONL verification results file")
    parser.add_argument("--output-dir", default="results", help="Output directory for tables and figures")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading results...", file=sys.stderr)
    results = load_results(args.input)
    print(f"Loaded {len(results)} verification results", file=sys.stderr)

    # RQ1: Database × Field accuracy
    print("Computing RQ1: DB × Field accuracy...", file=sys.stderr)
    db_field = compute_db_field_accuracy(results)

    # RQ2: Domain variation
    print("Computing RQ2: Domain variation...", file=sys.stderr)
    domain_var = compute_domain_variation(results)

    # RQ3: Group comparison
    print("Computing RQ3: Group comparison...", file=sys.stderr)
    group_comp = compute_group_comparison(results)

    # RQ4: AI vs Human
    print("Computing RQ4: AI vs Human...", file=sys.stderr)
    ai_human = compute_ai_vs_human(results)

    # Save results
    all_results = {
        "rq1_db_field_accuracy": db_field,
        "rq2_domain_variation": domain_var,
        "rq3_group_comparison": group_comp,
        "rq4_ai_vs_human": ai_human,
        "summary": {
            "total_citations": len(results),
            "databases_queried": 4,
            "metadata_fields": 7,
        }
    }

    output_json = os.path.join(args.output_dir, "analysis_results.json")
    with open(output_json, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {output_json}", file=sys.stderr)

    # Generate markdown tables
    tables_md = "# Analysis Results\n\n"
    tables_md += generate_table_markdown(group_comp, "Table 4: Comparison Group Effectiveness")
    tables_md += generate_table_markdown(domain_var, "Table 3: Domain Variation")
    tables_md += generate_table_markdown(ai_human, "Table 5: AI vs Human Citation Quality")

    tables_path = os.path.join(args.output_dir, "tables.md")
    with open(tables_path, "w") as f:
        f.write(tables_md)
    print(f"Tables saved to {tables_path}", file=sys.stderr)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
