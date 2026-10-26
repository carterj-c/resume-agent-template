#!/usr/bin/env python3
"""
Deterministic resume/JD match scanner for the resume-tailoring agent.

Runs four independent, increasingly permissive layers of match analysis and
appends the result to a persistent log for later verification of whether
any of this actually correlates with callback/interview outcomes.

Layer 0 - Parseability     : can a dumb ATS text-extractor even read this PDF sanely?
Layer 1 - Exact/stem match : required/preferred terms from a human-curated JD extract,
                             matched against the resume by exact/stemmed string match.
                             This is the closest proxy to what a real ATS gate does.
Layer 2 - TF-IDF & BM25    : whole-document ranking signal, corpus = past JDs in inputs/ (incl. archive/).
                             Secondary signal only - never gates anything.
Layer 3 - Embeddings       : sentence-transformer cosine similarity, used to (a) get an
                             overall semantic-fit number and (b) find near-miss rewording
                             opportunities for terms Layer 1 marked missing.

Usage:
    scoring/score_resume.py \
        --resume outputs/acme-analyst/resume.pdf \
        --jd inputs/acme-analyst.txt \
        --requirements outputs/acme-analyst/requirements.json \
        --company Acme --role "Analyst" \
        --out outputs/acme-analyst/ats_scan.json \
        --log logs/scan_log.jsonl
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = REPO_ROOT / "inputs"

SECTION_HEADERS = ["education", "experience", "skills", "projects"]


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def get_pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return -1


def layer0_parseability(text: str, page_count: int) -> dict:
    notes = []
    lower = text.lower()

    missing_sections = [h for h in SECTION_HEADERS if h not in lower]
    if missing_sections:
        notes.append(f"Section headers not detected by plain-text scan: {missing_sections}")

    # Glued-word heuristic: a naive ATS parser that loses whitespace on column
    # breaks produces abnormally long "words". Flag if too many appear.
    words = re.findall(r"[A-Za-z]+", text)
    long_words = [w for w in words if len(w) > 18]
    if len(long_words) > 3:
        notes.append(f"{len(long_words)} suspiciously long tokens found (possible glued columns): {long_words[:5]}")

    bullet_lines = [l for l in text.splitlines() if l.strip().startswith(("-", "–", "•", "*"))]
    if len(bullet_lines) < 5:
        notes.append(f"Only {len(bullet_lines)} bullet lines detected in extracted text - bullets may not be surviving parsing.")

    if page_count != 1:
        notes.append(f"Page count is {page_count}, not 1.")

    return {
        "pass": len(notes) == 0,
        "page_count": page_count,
        "notes": notes,
    }


def _stem_tokens(text: str, stemmer) -> set:
    words = re.findall(r"[A-Za-z0-9+#.]+", text.lower())
    return {stemmer.stemWord(w) for w in words}


def _term_hit(term: str, resume_text: str, resume_tokens: set, stemmer) -> bool:
    term_lower = term.lower().strip()
    if term_lower in resume_text.lower():
        return True
    term_tokens = _stem_tokens(term_lower, stemmer)
    if not term_tokens:
        return False
    return term_tokens.issubset(resume_tokens)


def layer1_keyword_match(requirements: dict, resume_text: str, stemmer) -> dict:
    resume_tokens = _stem_tokens(resume_text, stemmer)

    def score_group(terms):
        found, missing = [], []
        for t in terms:
            (found if _term_hit(t, resume_text, resume_tokens, stemmer) else missing).append(t)
        return found, missing

    required = requirements.get("required", [])
    preferred = requirements.get("preferred", [])

    req_found, req_missing = score_group(required)
    pref_found, pref_missing = score_group(preferred)

    return {
        "required_total": len(required),
        "required_found": req_found,
        "required_missing": req_missing,
        "required_coverage_pct": round(100 * len(req_found) / len(required), 1) if required else None,
        "preferred_total": len(preferred),
        "preferred_found": pref_found,
        "preferred_missing": pref_missing,
        "preferred_coverage_pct": round(100 * len(pref_found) / len(preferred), 1) if preferred else None,
    }


def _load_jd_corpus(exclude_path: Path) -> list:
    corpus = []
    # rglob, so archived JDs (inputs/archive/) stay in the background corpus —
    # otherwise the corpus would shrink toward empty as applications complete.
    for f in sorted(INPUTS_DIR.rglob("*.txt")):
        if f.resolve() == exclude_path.resolve():
            continue
        corpus.append(f.read_text(errors="ignore"))
    return corpus


def layer2_tfidf_bm25(jd_text: str, resume_text: str, jd_path: Path) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from rank_bm25 import BM25Okapi

    # TF-IDF cosine: fit on this JD + resume + other past JDs as background corpus
    # (without a corpus, IDF is degenerate for a two-document comparison).
    background = _load_jd_corpus(jd_path)
    corpus = [jd_text, resume_text] + background
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf = vectorizer.fit_transform(corpus)
    tfidf_cosine = float(cosine_similarity(tfidf[0], tfidf[1])[0][0])

    # BM25: JD as query, {resume + background JDs} as the document set, so the
    # resume's rank/score can be read against other real JDs, not in a vacuum.
    tokenized_docs = [re.findall(r"[a-z0-9+#.]+", d.lower()) for d in [resume_text] + background]
    bm25 = BM25Okapi(tokenized_docs)
    query_tokens = re.findall(r"[a-z0-9+#.]+", jd_text.lower())
    scores = bm25.get_scores(query_tokens)
    resume_bm25 = float(scores[0])
    other_scores = sorted(scores[1:], reverse=True)
    percentile = (
        round(100 * sum(1 for s in other_scores if resume_bm25 > s) / len(other_scores), 1)
        if other_scores else None
    )

    return {
        "tfidf_cosine": round(tfidf_cosine, 4),
        "bm25_score": round(resume_bm25, 4),
        "bm25_percentile_vs_past_jds": percentile,
        "bm25_corpus_size": len(other_scores),
    }


_EMBED_MODEL = None


def _get_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBED_MODEL


def layer3_embeddings(jd_text: str, resume_text: str, requirements: dict) -> dict:
    from sentence_transformers import util

    model = _get_embed_model()

    overall = float(util.cos_sim(
        model.encode(jd_text, convert_to_tensor=True),
        model.encode(resume_text, convert_to_tensor=True),
    )[0][0])

    bullet_lines = [
        l.strip().lstrip("-–•* ").strip()
        for l in resume_text.splitlines()
        if l.strip().startswith(("-", "–", "•", "*")) and len(l.strip()) > 8
    ]
    missing = requirements.get("_layer1_required_missing", [])
    near_misses = []
    if missing and bullet_lines:
        bullet_embeds = model.encode(bullet_lines, convert_to_tensor=True)
        for term in missing:
            term_embed = model.encode(term, convert_to_tensor=True)
            sims = util.cos_sim(term_embed, bullet_embeds)[0]
            best_idx = int(sims.argmax())
            best_score = float(sims[best_idx])
            if best_score >= 0.45:
                near_misses.append({
                    "missing_required_term": term,
                    "closest_resume_bullet": bullet_lines[best_idx],
                    "similarity": round(best_score, 3),
                    "note": "Semantically close but not an exact/stemmed match - verify the "
                            "underlying fact genuinely supports this term before rewording; "
                            "do not force it in if it doesn't.",
                })

    return {
        "overall_semantic_similarity": round(overall, 4),
        "near_miss_reword_candidates": near_misses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resume", required=True, type=Path, help="Path to compiled resume PDF")
    parser.add_argument("--jd", required=True, type=Path, help="Path to JD text file")
    parser.add_argument("--requirements", required=True, type=Path, help="Path to requirements.json (see scoring/requirements.schema.json)")
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--out", type=Path, help="Where to write the full ats_scan.json report")
    parser.add_argument("--log", type=Path, default=REPO_ROOT / "logs" / "scan_log.jsonl", help="Append-only JSONL log")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip Layer 3 (faster, for quick iteration)")
    args = parser.parse_args()

    import snowballstemmer
    stemmer = snowballstemmer.stemmer("english")

    resume_text = extract_pdf_text(args.resume)
    page_count = get_pdf_page_count(args.resume)
    jd_text = args.jd.read_text(errors="ignore")
    requirements = json.loads(args.requirements.read_text())

    layer0 = layer0_parseability(resume_text, page_count)
    layer1 = layer1_keyword_match(requirements, resume_text, stemmer)
    layer2 = layer2_tfidf_bm25(jd_text, resume_text, args.jd)

    if args.skip_embeddings:
        layer3 = {"skipped": True}
    else:
        requirements_with_missing = dict(requirements, _layer1_required_missing=layer1["required_missing"])
        layer3 = layer3_embeddings(jd_text, resume_text, requirements_with_missing)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "company": args.company,
        "role": args.role,
        "resume_path": str(args.resume),
        "jd_path": str(args.jd),
        "layer0_parseability": layer0,
        "layer1_keyword_match": layer1,
        "layer2_tfidf_bm25": layer2,
        "layer3_embeddings": layer3,
    }

    print(json.dumps(report, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2))

    args.log.parent.mkdir(parents=True, exist_ok=True)
    log_row = {
        "timestamp": report["timestamp"],
        "company": args.company,
        "role": args.role,
        "layer0_pass": layer0["pass"],
        "page_count": layer0["page_count"],
        "required_coverage_pct": layer1["required_coverage_pct"],
        "required_missing": layer1["required_missing"],
        "preferred_coverage_pct": layer1["preferred_coverage_pct"],
        "tfidf_cosine": layer2["tfidf_cosine"],
        "bm25_score": layer2["bm25_score"],
        "bm25_percentile_vs_past_jds": layer2["bm25_percentile_vs_past_jds"],
        "embedding_similarity": layer3.get("overall_semantic_similarity"),
        "outcome": None,
    }
    with args.log.open("a") as f:
        f.write(json.dumps(log_row) + "\n")

    if not layer0["pass"]:
        print("\nWARNING: Layer 0 parseability check failed - see notes above.", file=sys.stderr)


if __name__ == "__main__":
    main()
