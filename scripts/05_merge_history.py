#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from colonial_toponymy.normalize import normalize_odonimo


def main():
    ap = argparse.ArgumentParser(description="Merge manually verified naming/removal dates from municipal or research sources.")
    ap.add_argument("--matches", default="data/processed/street_matches_geocoded.csv")
    ap.add_argument("--history", default="data/manual/street_history.csv")
    ap.add_argument("--output", default="data/processed/dashboard_data.csv")
    args = ap.parse_args()

    matches = pd.read_csv(args.matches, dtype=str).fillna("")
    history = pd.read_csv(args.history, dtype=str).fillna("")
    if history.empty:
        out = matches
    else:
        matches["_odonimo_key"] = matches["odonimo"].map(normalize_odonimo)
        history["_odonimo_key"] = history["odonimo"].map(normalize_odonimo)
        keys = ["municipality_belfiore", "person_id", "_odonimo_key"]
        cols = keys + [c for c in history.columns if c not in keys and c != "odonimo"]
        out = matches.merge(history[cols], on=keys, how="left", suffixes=("", "_history"))
        out = out.drop(columns=["_odonimo_key"])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    out.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)
    print(f"Wrote dashboard dataset to {args.output}")

if __name__ == "__main__":
    main()
