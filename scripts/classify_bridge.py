#!/usr/bin/env python3
"""Classify inter-database field disagreements as variant or substantive.

Applies the normalization rules described in the manuscript (abbreviation,
initials vs. full names, diacritics, hyphen variants, "&"/"and", case) to each
disagreement and labels it variant / substantive / AMBIGUOUS. AMBIGUOUS rows are
left for manual review.

Usage:
    python3 classify_bridge.py --input data/audit_bridge_worksheet.csv \
        --output data/audit_bridge_classified.csv
"""

import argparse
import csv
import html
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List

VARIANT = "variant"
SUBSTANTIVE = "substantive"
AMBIGUOUS = "AMBIGUOUS"


def norm(s: str) -> str:
    s = html.unescape(s or "").lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def values(row: dict) -> List[str]:
    return [v for v in (row["crossref"], row["openalex"], row["s2"]) if v and v.strip()]


def is_abbrev(a: str, b: str) -> bool:
    """True if one token list is an order-preserving abbreviation of the other."""
    wa, wb = a.split(), b.split()
    short, long = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if not short:
        return False
    li = 0
    for tok in short:
        while li < len(long) and not long[li].startswith(tok[0]):
            li += 1
        if li >= len(long):
            return False
        li += 1
    return True


def _deaccent(s: str) -> str:
    """Strip diacritics and unify hyphen variants for name comparison."""
    s = re.sub(r"[‐-―−]", "-", s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def author_list(author_str: str) -> List[str]:
    return [a.strip() for a in re.split(r";", html.unescape(author_str or "")) if a.strip()]


def surnames(author_str: str) -> List[str]:
    out = []
    for a in author_list(author_str):
        toks = [t for t in re.split(r"[\s,]+", _deaccent(a).lower())
                if t and t not in ("dr", "dr.", "prof", "prof.", "mr", "mr.", "ms")]
        if toks:
            out.append(toks[-1])
    return sorted(out)


def classify(field: str, vals: List[str]) -> str:
    nvals = [norm(v) for v in vals]
    if len(set(nvals)) == 1:
        return VARIANT  # differ only by punctuation/case/&/HTML entity

    if field == "year":
        try:
            yrs = [int(re.search(r"\d{4}", v).group()) for v in vals]
            return VARIANT if max(yrs) - min(yrs) <= 1 else SUBSTANTIVE
        except (AttributeError, ValueError):
            return AMBIGUOUS

    if field == "authors":
        counts = {len(author_list(v)) for v in vals}
        if len(counts) > 1:
            return SUBSTANTIVE  # different author count = missing/extra author
        sets = {tuple(surnames(v)) for v in vals}
        if len(sets) == 1:
            return VARIANT  # same people (diacritics/initials/full-name differences)
        return AMBIGUOUS  # same count, different surnames -> name order/romanization, human decides

    if field == "journal":
        # all pairwise either abbreviation or near-equal -> variant
        for i in range(len(nvals)):
            for j in range(i + 1, len(nvals)):
                if nvals[i] == nvals[j] or is_abbrev(nvals[i], nvals[j]):
                    continue
                if SequenceMatcher(None, nvals[i], nvals[j]).ratio() >= 0.85:
                    continue
                return AMBIGUOUS  # genuinely different journal strings
        return VARIANT

    if field == "title":
        ratios = [SequenceMatcher(None, nvals[i], nvals[j]).ratio()
                  for i in range(len(nvals)) for j in range(i + 1, len(nvals))]
        m = min(ratios) if ratios else 1.0
        if m >= 0.95:
            return VARIANT
        if m < 0.80:
            return SUBSTANTIVE
        return AMBIGUOUS

    if field in ("pages", "volume"):
        firsts = [re.split(r"[-–—]", v.strip())[0].strip() for v in vals]
        if len(set(firsts)) == 1:
            return VARIANT  # same start page/volume, only range/dash differs
        return SUBSTANTIVE

    return AMBIGUOUS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/audit_bridge_worksheet.csv")
    ap.add_argument("--output", default="data/audit_bridge_classified.csv")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input)))
    counts = {VARIANT: 0, SUBSTANTIVE: 0, AMBIGUOUS: 0}
    for r in rows:
        label = classify(r["field"], values(r))
        r["auto_label"] = label
        r["needs_human"] = "YES" if label == AMBIGUOUS else ""
        counts[label] += 1

    fields = list(rows[0].keys())
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    print(f"classified {n} bridge rows:")
    for k, v in counts.items():
        print(f"  {k:12} {v} ({100*v/n:.0f}%)")
    print(f"-> {counts[AMBIGUOUS]} rows need human adjudication ({args.output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
