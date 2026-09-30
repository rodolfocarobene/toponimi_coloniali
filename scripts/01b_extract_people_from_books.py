#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import fitz
import pandas as pd


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        doc = fitz.open(path)
        return "\n".join(page.get_text("text") for page in doc)
    return path.read_text(encoding="utf-8", errors="replace")


def candidates_spacy(text: str):
    try:
        import spacy
        try:
            nlp = spacy.load("it_core_news_sm")
        except OSError:
            return None
        doc = nlp(text)
        return [ent.text.strip() for ent in doc.ents if ent.label_ in {"PER", "PERSON"} and 1 < len(ent.text.split()) <= 5]
    except ImportError:
        return None


def candidates_regex(text: str):
    pattern = re.compile(r"\b(?:[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’-]+\s+){1,3}[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’-]+\b")
    return pattern.findall(text)


def context(text: str, name: str, radius: int = 180) -> str:
    idx = text.find(name)
    if idx < 0:
        return ""
    start, end = max(0, idx-radius), min(len(text), idx+len(name)+radius)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    return snippet[:420]


def main():
    ap = argparse.ArgumentParser(description="Extract candidate person names from local books/PDFs for manual historical review.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--output", default="data/candidates/book_candidates.csv")
    args = ap.parse_args()

    aggregate = Counter()
    sources = defaultdict(set)
    snippets = {}
    method = "regex"
    for p in map(Path, args.inputs):
        text = read_text(p)
        names = candidates_spacy(text)
        if names is not None:
            method = "spacy_it_core_news_sm"
        else:
            names = candidates_regex(text)
        for name in names:
            clean = re.sub(r"\s+", " ", name).strip(" ,.;:()[]")
            if len(clean) < 5:
                continue
            aggregate[clean] += 1
            sources[clean].add(p.name)
            snippets.setdefault(clean, context(text, name))

    rows = [{"candidate_name": n, "mentions": c, "source_files": ";".join(sorted(sources[n])),
             "example_context": snippets[n], "extraction_method": method, "review_status": "candidate_unreviewed"}
            for n, c in aggregate.most_common()]
    out = pd.DataFrame(rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out)} candidates to {args.output}")

if __name__ == "__main__":
    main()
