# Cross-Database Bibliographic Metadata Consistency Benchmark

Replication materials for the paper:

> **Beyond Existence Checks: A Cross-Database Benchmark of Bibliographic Metadata Consistency Across Academic Domains and LLM-Generated Citations**
>
> Chung-Kuang Chen, Shu-Hao Liang, Teng-Shih Wang

## Repository Structure

```
data/               Raw citation data and verification results
  all_citations.jsonl          Complete corpus (1,254 citations)
  verification_results.jsonl   Cross-database verification output
  citations_*.json             Domain- and source-specific subsets
scripts/            Analysis and verification scripts
  verify_fast.py               Cross-database verification pipeline
  verify_citation.py           Single-citation verification tool
  collect_human_citations.py   CrossRef sampling script
  analyze_results.py           Statistical analysis
  gen_fig*.py                  Figure generation scripts
results/            Analysis outputs
  analysis_results.json        Aggregated results
  statistical_tests.json       Statistical test outputs
figures/            Publication-ready figures (SVG + PNG)
```

## Requirements

- Python 3.9+
- No external packages required (uses only standard library)

## Usage

### Verify a single citation

```bash
python scripts/verify_citation.py --doi "10.1038/s41598-023-41032-5"
```

### Run batch verification

```bash
python scripts/verify_fast.py data/all_citations.jsonl
```

### Reproduce analysis

```bash
python scripts/analyze_results.py
```

## Data Description

The dataset comprises 1,254 bibliographic citations:
- **499 LLM-generated** citations from five models (Claude, GPT, Gemini, Llama 70B, Llama 8B)
- **755 database-sampled** citations from CrossRef

Each citation was queried against three scholarly databases (CrossRef, OpenAlex, Semantic Scholar) across seven metadata fields (title, authors, year, journal, volume, pages, DOI).

## APIs Used

All verification queries use publicly available APIs with no authentication required:
- [CrossRef REST API](https://api.crossref.org/)
- [OpenAlex API](https://api.openalex.org/)
- [Semantic Scholar API](https://api.semanticscholar.org/)

## License

This dataset and code are released under the [MIT License](LICENSE).
