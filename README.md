# Cross-Database Bibliographic Metadata Consistency Benchmark

Replication materials for the paper:

> **Beyond Existence Checks: A Cross-Database Benchmark of Bibliographic Metadata Consistency Across Academic Domains and LLM-Generated Citations**
>
> Chung-Kuang Chen, Shu-Hao Liang, Teng-Shih Wang

## Repository Structure

```
data/               Raw citation data and verification results
  all_citations.jsonl          Complete corpus (1,246 citations)
  verification_results.jsonl   Cross-database verification output
  citations_*.json             Domain- and source-specific subsets
  excluded_records.csv         8 empty-metadata duplicate records removed in revision
  bridge_inventory.csv         Rule-based variant/substantive labels for
                               Semantic Scholar disagreements (see below)
scripts/            Generation, verification, and analysis scripts
  prompts.json                 Exact LLM prompt template and model configuration
  generate_citations.py        LLM citation-generation harness
  verify_fast.py               Cross-database verification pipeline
  verify_citation.py           Single-citation verification tool
  recollect_s2.py              Authenticated Semantic Scholar re-collection
  collect_human_citations.py   CrossRef sampling script
  analyze_results.py           Statistical analysis
  recompute_stats.py           Significance tests and effect sizes
  classify_bridge.py           Variant/substantive classification rules
results/            Analysis outputs
  analysis_results.json        Aggregated results
  statistical_tests.json       Statistical test outputs
figures/            Publication-ready figures (PNG, SVG, PDF)
```

## Requirements

- Python 3.9+
- Standard library only for verification and analysis
- `scipy` for `recompute_stats.py`; a free Semantic Scholar API key for `recollect_s2.py`

## LLM Citation Generation

The 491 LLM-generated citations were produced with the exact prompt template in
`scripts/prompts.json` (a single fixed template applied identically to all five
models, requesting 25 references per domain published 2015–2025). Each model was
accessed through its public inference API:

| Model | Provider |
|-------|----------|
| GPT-4.1-nano | OpenAI |
| Gemini 3 Flash | Google |
| Llama 3.3 70B, Llama 3.1 8B | Groq |
| Claude Opus 4.6 | Anthropic |

**Access infrastructure.** Requests were routed through a single self-hosted API
gateway in the authors' compute environment that provides a unified interface to
the underlying public provider APIs (OpenAI, Google, Groq, Anthropic), so that all
models could be invoked through one consistent call path with shared logging and
rate handling. The gateway performs no prompt rewriting and no post-processing of
responses: it forwards the exact prompt template and returns the raw model output
verbatim. It is an operational convenience and is **not required for reproduction** —
the same prompts and models can be queried directly through each provider's public
API. The internal label `ai_hub_llm_chat` in `prompts.json` refers to this gateway
routing and is equivalent to a direct call to the corresponding provider.

## Semantic Scholar Re-collection

Semantic Scholar records were re-collected with `scripts/recollect_s2.py` using an
authenticated API key, a 1.1-second inter-request interval, and exponential backoff,
which separates genuine non-coverage (HTTP 404) from rate-limited responses (HTTP 429).
This supersedes an earlier unauthenticated parallel-query procedure that had recorded
rate-limited responses as non-coverage. See the paper's Appendix B for the effect on
reported coverage and statistics.

## Usage

```bash
# Single-citation verification
python scripts/verify_citation.py --doi "10.1038/s41598-023-41032-5"

# Batch verification
python scripts/verify_fast.py data/all_citations.jsonl

# Re-collect Semantic Scholar (requires API key)
S2_API_KEY=<key> python scripts/recollect_s2.py --dois <doi_list> --output data/s2_recollected.jsonl

# Reproduce analysis and statistics
python scripts/analyze_results.py --input data/verification_results.jsonl --output-dir results/
python scripts/recompute_stats.py --input data/verification_results.jsonl --output results/statistical_tests.json
```

## Data Description

The dataset comprises 1,246 bibliographic citations:
- **491 LLM-generated** citations from five models (Claude, GPT-4.1-nano, Gemini, Llama 70B, Llama 8B)
- **755 database-sampled** citations from CrossRef

Each citation was queried against three scholarly databases (CrossRef, OpenAlex,
Semantic Scholar) across seven metadata fields (title, authors, year, journal,
volume, pages, DOI).
