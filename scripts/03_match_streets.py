#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from colonial_toponymy.anncsu import load_istat_municipalities, load_stradario
from colonial_toponymy.matcher import load_registry, match_dataframe


def _load_authorities(people_path: str, places_path: str | None) -> pd.DataFrame:
    people = load_registry(people_path)
    if "entity_type" not in people:
        people["entity_type"] = "person"
    else:
        people["entity_type"] = people["entity_type"].replace("", "person")

    frames = [people]
    if places_path:
        p = Path(places_path)
        if p.exists():
            places = load_registry(p)
            if "entity_type" not in places:
                places["entity_type"] = "place"
            else:
                places["entity_type"] = places["entity_type"].replace("", "place")
            frames.append(places)
        else:
            print(f"Warning: place/battle registry not found: {p}")

    registry = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    if registry.duplicated(["person_id", "canonical_name"]).any():
        dup = registry.loc[
            registry.duplicated(["person_id", "canonical_name"], keep=False),
            ["person_id", "canonical_name"],
        ]
        raise ValueError(f"Duplicate authority identifiers:\n{dup.to_string(index=False)}")
    return registry


def main():
    ap = argparse.ArgumentParser(
        description="Match curated people plus colonial places/battles to official ANNCSU odonyms."
    )
    ap.add_argument("--stradario", default="data/raw/anncsu/stradario_nazionale.zip")
    ap.add_argument("--municipalities", default="data/raw/anncsu/Elenco-comuni-italiani.xlsx")
    ap.add_argument("--registry", default="data/manual/people_registry.csv", help="Curated people registry.")
    ap.add_argument(
        "--places-registry",
        default="data/manual/place_registry.csv",
        help="Curated places/battles registry. Pass an empty string to disable it.",
    )
    ap.add_argument("--output", default="data/processed/street_matches.csv")
    ap.add_argument(
        "--registry-snapshot",
        default="data/processed/people_registry_used.csv",
        help=(
            "Write the exact combined authority list used for this matching run here. "
            "The historical filename is kept for dashboard compatibility."
        ),
    )
    ap.add_argument("--fuzzy-threshold", type=int, default=93)
    args = ap.parse_args()

    streets = load_stradario(args.stradario)
    muni = load_istat_municipalities(args.municipalities)
    streets = streets.merge(muni, on="municipality_belfiore", how="left")

    registry = _load_authorities(args.registry, args.places_registry or None)

    registry_snapshot = Path(args.registry_snapshot)
    registry_snapshot.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(registry_snapshot, index=False)

    matches = match_dataframe(streets, registry, "odonimo", fuzzy_threshold=args.fuzzy_threshold)
    matches = matches.merge(
        registry,
        on=["person_id", "canonical_name"],
        how="left",
        suffixes=("", "_authority"),
    )

    denominators = (
        streets.groupby("region_name", dropna=False)
        .size()
        .rename("total_odonimi_region")
        .reset_index()
    )
    matches = matches.merge(denominators, on="region_name", how="left")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(args.output, index=False)
    matches.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)

    people_n = int((registry["entity_type"] == "person").sum())
    places_n = int((registry["entity_type"] != "person").sum())
    print(
        f"Matched {len(matches)} official odonyms using {people_n} people and "
        f"{places_n} places/battles. Review non-exact matches before publication."
    )
    print(f"Combined registry snapshot: {registry_snapshot}")
    if len(matches):
        print(matches["match_method"].value_counts().to_string())
        if "entity_type" in matches:
            print("\nBy entity type:")
            print(matches["entity_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
