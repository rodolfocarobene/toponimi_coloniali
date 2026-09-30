#!/usr/bin/env python3
"""Helper sperimentale per preparare una tabella di revisione dei candidati.

Non sostituisce la revisione storica manuale e non sovrascrive mai
``data/manual/people_registry.csv``. Il progetto pubblicato usa il registro
curato manualmente come autorità.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

KEYWORDS = {
    "governatore": 3,
    "ministro delle colonie": 4,
    "africa orientale italiana": 3,
    "guerra d'etiopia": 3,
    "guerra italo-turca": 3,
    "eritrea": 1,
    "libia": 1,
    "etiopia": 1,
    "somalia": 1,
    "coloniale": 1,
}
NON_PERSON = re.compile(
    r"^(guerra|battaglia|colonia|governatorato|trattato|palazzo|cinema|teatro|chiesa|forze armate|regio corpo|storia)\b",
    re.I,
)


def score(row: pd.Series) -> tuple[int, str]:
    title = str(row.get("title", ""))
    if NON_PERSON.search(title):
        return -100, "titolo non compatibile con una persona"
    text = " ".join(str(row.get(c, "")) for c in ["title", "snippet", "intro", "source_query"]).lower()
    found = []
    total = 0
    for key, value in KEYWORDS.items():
        if key in text:
            total += value
            found.append(key)
    return total, "; ".join(found)


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepara una tabella sperimentale di revisione dei candidati Wikipedia.")
    ap.add_argument("--input", default="data/candidates/wikipedia_candidates.csv")
    ap.add_argument("--output", default="data/candidates/candidate_review.csv")
    ap.add_argument("--min-score", type=int, default=4)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    df = df.drop_duplicates("title").copy()
    scored = df.apply(score, axis=1)
    df["relevance_score"] = [x[0] for x in scored]
    df["evidence"] = [x[1] for x in scored]
    df["suggested_review"] = df["relevance_score"].map(lambda x: "review" if x >= args.min_score else "exclude")
    df["warning"] = "NON usare automaticamente come registro: verificare persona, ruolo storico e omonimie odonomastiche."

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["suggested_review", "relevance_score"], ascending=[False, False]).to_csv(out, index=False)
    print(f"Scritta tabella di revisione: {out}")
    print("Il file data/manual/people_registry.csv non è stato modificato.")


if __name__ == "__main__":
    main()
