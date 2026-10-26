# ATS match scanner

Deterministic, local, no-API-calls scoring of a tailored resume against a JD.
Four layers, run every time, none of them a single blended "score":

| Layer | What | Why |
|---|---|---|
| 0 - Parseability | `pdftotext -layout` extraction sanity checks (sections present, no glued columns, bullets survive, 1 page) | The single biggest real-ATS failure mode is a resume that doesn't parse, not one that doesn't match |
| 1 - Exact/stem match | Required/preferred terms (human-curated from the JD) matched against the resume by exact or stemmed match | Closest proxy to what a real ATS keyword gate actually does |
| 2 - TF-IDF & BM25 | Whole-document ranking signal against a corpus of past JDs in `inputs/` | Secondary ranking signal, not a gate - what recruiters' internal sort might look like |
| 3 - Embeddings | sentence-transformer cosine similarity, overall + per-missing-term near-miss finder | Catches paraphrase gaps (e.g. "capital markets" vs "financial markets") Layer 1 can't see - a diagnostic for honest rewording, not a score to maximize |

## Requirements extraction is a human/agent step, not a script

`requirements.json` (see `requirements.schema.json`) is produced by the tailoring
agent while reading the JD in Step 2 - extracting "required" vs "preferred" terms
is a semantic-understanding task. The script only does deterministic matching
against that curated list.

## Usage

```
source .venv/bin/activate
python3 scoring/score_resume.py \
  --resume outputs/<company>-<role>/resume.pdf \
  --jd inputs/<company>-<role>.txt \
  --requirements outputs/<company>-<role>/requirements.json \
  --company <Company> --role "<Role>" \
  --out outputs/<company>-<role>/ats_scan.json
```

Appends one row per run to `logs/scan_log.jsonl` (not overwritten - append-only)
regardless of `--out`. Each row has an `outcome` field, initially `null` - fill
it in by hand later (`"interview"`, `"rejected"`, `"no_response"`, etc.) once
you hear back, so the log can eventually be checked for whether any of these
scores actually correlates with real outcomes.

## Setup

Dependencies live in `.venv/` (scikit-learn, rank_bm25, sentence-transformers,
snowballstemmer) - not committed. Recreate with:

```
python3 -m venv .venv && source .venv/bin/activate
pip install scikit-learn rank_bm25 snowballstemmer sentence-transformers
```
