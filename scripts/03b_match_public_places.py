#!/usr/bin/env python3
"""Match registry names against schools, universities and other public places.

Input: files downloaded by scripts/02b_download_public_places.py.
Output: data/processed/public_place_matches.csv, same columns as street_matches.csv plus
site_kind, site_detail, total_kind_region, coord_precision, place_source, place_source_id.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from colonial_toponymy.anncsu import load_istat_municipalities
from colonial_toponymy.matcher import load_authorities
from colonial_toponymy.places import match_places_dataframe
from colonial_toponymy.public_sources import (
    ENTITY_COLUMNS,
    assign_nearest_municipality,
    load_autonomous_schools,
    load_municipalities,
    load_osm,
    load_schools,
    load_universities,
    load_wikidata,
)


def _match_names(entities: pd.DataFrame, registry: pd.DataFrame, fuzzy_threshold: int) -> pd.DataFrame:
    """Match each distinct name once, then attach the result to every entity with that name.

    Wikidata items are also matched on the label of the person they are named after ("name_alt");
    such matches are never auto-accepted because the label alone cannot rule out a homonym.
    """
    texts = pd.concat(
        [
            pd.DataFrame({"match_text": entities["name"], "via": "name"}),
            pd.DataFrame({
                "match_text": entities.loc[entities["place_source"].str.startswith("Wikidata"), "name_alt"],
                "via": "honoree",
            }),
        ]
    )
    texts = texts[texts["match_text"] != ""].drop_duplicates()
    matched = match_places_dataframe(texts, registry, "match_text", fuzzy_threshold=fuzzy_threshold)
    if matched.empty:
        return matched
    # A bare surname is no evidence for a Wikidata honoree label (those are full names).
    matched = matched[~((matched["via"] == "honoree") & (matched["match_method"] == "surname_in_name"))]
    matched.loc[matched["via"] == "honoree", "review_status"] = "needs_review"
    matched.loc[matched["via"] == "honoree", "match_method"] = (
        "honoree_" + matched.loc[matched["via"] == "honoree", "match_method"]
    )
    keys = {(r["match_text"], r["via"]): r for r in matched.to_dict("records")}
    rows = []
    for rec in entities.to_dict("records"):
        hits = [keys.get((rec["name"], "name")), keys.get((rec["name_alt"], "honoree"))]
        hits = [h for h in hits if h]
        if not hits:
            continue
        # Bare-surname candidates only for organisations (schools, universities), not buildings/parks/streets.
        if rec["site_kind"] not in ("scuola", "universita"):
            hits = [h for h in hits if h["match_method"] != "surname_in_name"]
        if not hits:
            continue
        best = max(hits, key=lambda h: (h["review_status"] == "accepted_auto", h["match_score"]))
        out = dict(rec)
        out.update({k: best[k] for k in (
            "person_id", "canonical_name", "matched_alias", "match_score", "match_method",
            "odonimo_normalized", "review_status",
        )})
        rows.append(out)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", default="data/raw/public_places")
    ap.add_argument("--municipalities", default="data/raw/anncsu/Elenco-comuni-italiani.xlsx")
    ap.add_argument("--registry", default="data/manual/people_registry.csv")
    ap.add_argument("--places-registry", default="data/manual/place_registry.csv")
    ap.add_argument("--output", default="data/processed/public_place_matches.csv")
    ap.add_argument("--fuzzy-threshold", type=int, default=93)
    args = ap.parse_args()

    raw = Path(args.raw_dir)
    registry = load_authorities(args.registry, args.places_registry or None)
    muni = load_municipalities(load_istat_municipalities(args.municipalities), raw)

    schools, school_totals = load_schools(raw, muni)
    aut_schools, aut_totals = load_autonomous_schools(raw, muni)
    universities, university_totals = load_universities(raw, muni)
    wikidata = load_wikidata(raw, muni)
    osm, osm_totals = load_osm(raw, muni)
    print(
        f"Entities: {len(schools)} schools/institutes (+{len(aut_schools)} from Trento, Bolzano, Valle d'Aosta), {len(universities)} universities/colleges, "
        f"{len(wikidata)} Wikidata items, {len(osm)} OSM candidates (name contains a registry name)."
    )

    entities = pd.concat([schools, aut_schools, universities, wikidata, osm], ignore_index=True)[ENTITY_COLUMNS].fillna("")
    matches = _match_names(entities, registry, args.fuzzy_threshold)
    if matches.empty:
        raise SystemExit("No public-place matches found.")
    matches["lon"] = pd.to_numeric(matches["lon"], errors="coerce")
    matches["lat"] = pd.to_numeric(matches["lat"], errors="coerce")
    matches = assign_nearest_municipality(matches, muni)

    # A school matched both as site and as institute (same code, same person) counts once.
    matches = matches.sort_values(["review_status", "match_score"], ascending=[True, False])
    matches = matches.drop_duplicates(["place_source", "place_source_id", "person_id"])

    totals = pd.concat(
        [
            pd.concat([school_totals, aut_totals]).groupby(level=0).sum().reset_index().assign(site_kind="scuola").rename(columns={"total_kind_region": "n"}),
            university_totals.reset_index().assign(site_kind="universita").rename(columns={"total_kind_region": "n"}),
            osm_totals,
        ]
    ).groupby(["region_name", "site_kind"], as_index=False)["n"].sum().rename(columns={"n": "total_kind_region"})
    matches = matches.merge(totals, on=["region_name", "site_kind"], how="left")
    matches["total_kind_region"] = matches["total_kind_region"].astype("Int64")

    matches = matches.rename(columns={"place_source_id": "progressivo_odonimo", "name": "odonimo"})
    matches["place_source_id"] = matches["progressivo_odonimo"]
    matches["dug"], matches["duf"] = "", matches["odonimo"]
    matches["municipality_istat_x"] = matches["municipality_istat_y"] = matches["municipality_istat"]
    matches = matches.drop(columns=["municipality_istat", "name_alt"])
    matches = matches.merge(registry, on=["person_id", "canonical_name"], how="left", suffixes=("", "_authority"))
    matches = matches.sort_values(["site_kind", "region_name", "municipality_name", "odonimo"])

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(args.output, index=False)
    matches.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)

    print(f"Matched {len(matches)} public places. Review non-exact matches before publication.")
    print(matches.groupby(["site_kind", "match_method"]).size().to_string())
    print(matches.groupby(["site_kind", "review_status"]).size().to_string())
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
