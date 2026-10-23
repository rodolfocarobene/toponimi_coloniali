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
    ap.add_argument(
        "--public-places",
        default="data/processed/public_place_matches.csv",
        help="Matches on schools/universities/other public places (03b). Skipped if the file is missing.",
    )
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
    out["site_kind"] = "odonimo"
    out["site_detail"] = ""
    out["total_kind_region"] = out["total_odonimi_region"]
    out["coord_precision"] = out["lat"].map(lambda v: "street_median" if v != "" else "")
    out["place_source"] = "ANNCSU"
    out["place_source_id"] = out["progressivo_odonimo"]

    public_path = Path(args.public_places)
    if public_path.exists():
        public = pd.read_csv(public_path, dtype=str).fillna("")
        # Dates of naming/removal are only curated for streets; extra columns of the history file stay empty.
        out = pd.concat([out, public], ignore_index=True, sort=False).fillna("")
        print(f"Added {len(public)} public-place matches from {public_path}")
    else:
        print(f"No public-place matches at {public_path}: dashboard data contains streets only.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    out.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)
    print(f"Wrote dashboard dataset to {args.output} ({len(out)} rows)")
    print(out.groupby(["site_kind", "review_status"]).size().to_string())

if __name__ == "__main__":
    main()
