#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from colonial_toponymy.anncsu import load_istat_municipalities, load_stradario
from colonial_toponymy.matcher import load_registry, match_dataframe


def main():
    ap = argparse.ArgumentParser(description="Match the verified person authority list to official ANNCSU odonyms.")
    ap.add_argument("--stradario", default="data/raw/anncsu/stradario_nazionale.zip")
    ap.add_argument("--municipalities", default="data/raw/anncsu/Elenco-comuni-italiani.xlsx")
    ap.add_argument("--registry", default="data/manual/people_registry.csv")
    ap.add_argument("--output", default="data/processed/street_matches.csv")
    ap.add_argument(
        "--registry-snapshot",
        default="data/processed/people_registry_used.csv",
        help="Copy the exact registry CSV used for this matching run here.",
    )
    ap.add_argument("--fuzzy-threshold", type=int, default=93)
    args = ap.parse_args()

    streets = load_stradario(args.stradario)
    muni = load_istat_municipalities(args.municipalities)
    streets = streets.merge(muni, on="municipality_belfiore", how="left")
    registry = load_registry(args.registry)

    registry_source = Path(args.registry)
    registry_snapshot = Path(args.registry_snapshot)
    registry_snapshot.parent.mkdir(parents=True, exist_ok=True)
    if registry_source.resolve() != registry_snapshot.resolve():
        shutil.copyfile(registry_source, registry_snapshot)

    matches = match_dataframe(streets, registry, "odonimo", fuzzy_threshold=args.fuzzy_threshold)
    matches = matches.merge(registry, on=["person_id", "canonical_name"], how="left", suffixes=("", "_person"))

    denominators = streets.groupby("region_name", dropna=False).size().rename("total_odonimi_region").reset_index()
    matches = matches.merge(denominators, on="region_name", how="left")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(args.output, index=False)
    matches.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)
    print(f"Matched {len(matches)} official odonyms. Review non-exact matches before publication.")
    print(f"Registry snapshot: {registry_snapshot}")
    if len(matches):
        print(matches["match_method"].value_counts().to_string())

if __name__ == "__main__":
    main()
