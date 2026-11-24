#!/usr/bin/env python3
"""Neighbourhoods (site_kind "quartiere"): named matches, curated themed districts, detected street clusters.

Input: data/raw/quartieri/ (scripts/02c_download_quartieri.py: OpenStreetMap, ISTAT localities 2021 and the official
lists of Milano, Bologna and Torino), config/quartieri_tematici.yml and the
geocoded street matches (scripts/04_geocode_matches.py). The municipality centroids (Wikidata) are read from
data/raw/public_places/ (read-only). Output: data/processed/quartieri_matches.csv, merged by 05_merge_history.py.

Rows by match_method:
  exact_* / fuzzy_* / honoree-less name matches   named area whose name contains a registry name (official
                                                  city lists, OSM, ISTAT localities, deduplicated by comune and
                                                  normalized name in this order of priority)
  curated_theme                                   themed district of the config file (person_id tema_<id>)
  cluster_streets                                 >= min_streets distinct accepted colonial streets within
                                                  radius_m (person_id "cluster"), always needs_review
Themed districts that contain a detected cluster absorb it (cluster_n_streets is filled, no duplicate row).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from colonial_toponymy.anncsu import load_istat_municipalities
from colonial_toponymy.matcher import load_authorities
from colonial_toponymy.normalize import normalize_text
from colonial_toponymy.public_sources import load_municipalities
from colonial_toponymy.quartieri import (
    CLUSTER_CANONICAL_NAME,
    CLUSTER_PERSON_ID,
    THEME_CANONICAL_NAME,
    THEME_PERSON_PREFIX,
    detect_street_clusters,
    haversine_m,
    combine_named_sources,
    load_city_lists,
    load_istat_localita,
    load_osm_quartieri,
    load_themed_districts,
    match_quartieri_dataframe,
    nearest_neighbourhood,
    region_totals,
)

STREET_LIST_LIMIT = 10


def _street_list(odonimi: list[str], limit: int = STREET_LIST_LIMIT) -> str:
    names = sorted(set(odonimi))
    shown = "; ".join(names[:limit])
    return shown + (f" e altre {len(names) - limit}" if len(names) > limit else "")


def _territory_counts(series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in series:
        for t in str(value).split(";"):
            if t.strip():
                counts[t.strip()] = counts.get(t.strip(), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def named_rows(osm: pd.DataFrame, registry: pd.DataFrame, fuzzy_threshold: int) -> pd.DataFrame:
    matches = match_quartieri_dataframe(osm, registry, fuzzy_threshold=fuzzy_threshold)
    if matches.empty:
        return matches
    matches = matches.merge(registry, on=["person_id", "canonical_name"], how="left", suffixes=("", "_authority"))
    matches["odonimo"] = matches["name"]
    return matches


def themed_rows(items: list[dict], muni: pd.DataFrame, clusters: list[dict], streets: pd.DataFrame,
                max_m: float) -> tuple[pd.DataFrame, set[int]]:
    rows, absorbed = [], set()
    for item in items:
        m = muni[muni["name_key"] == normalize_text(item["comune"])]
        if len(m) != 1:
            raise SystemExit(f"themed district {item['id']}: comune {item['comune']!r} not found uniquely in ISTAT")
        m = m.iloc[0]
        detail, n_streets = item["description"].strip(), ""
        for i, c in enumerate(clusters):
            near = c["municipality_belfiore"] == m["municipality_belfiore"] and \
                haversine_m(c["lat"], c["lon"], item["lat"], item["lon"]) <= max_m
            if near:
                absorbed.add(i)
                n_streets = len(c["indices"])
                detail += f" Rilevate {n_streets} vie con riferimenti coloniali entro {round(c['radius_m'], -1):.0f} m dal centro."
                break
        rows.append({
            "place_source": "Elenco curato config/quartieri_tematici.yml", "place_source_id": item["id"],
            "odonimo": item["name"], "name": item["name"], "site_kind": "quartiere", "site_detail": detail,
            "municipality_belfiore": m["municipality_belfiore"], "municipality_istat": m["municipality_istat"],
            "municipality_name": m["municipality_name"], "region_name": m["region_name"],
            "lon": item["lon"], "lat": item["lat"], "coord_precision": "approx_center",
            "person_id": THEME_PERSON_PREFIX + item["id"], "canonical_name": THEME_CANONICAL_NAME,
            "matched_alias": item["name"], "match_score": 100.0, "match_method": "curated_theme",
            "odonimo_normalized": normalize_text(item["name"]), "review_status": "accepted_manual",
            "entity_type": "theme", "territories": item.get("territories", ""), "role_category": "",
            "connection_summary_it": item["description"].strip(), "source_url": item["source_url"],
            "cluster_n_streets": n_streets,
        })
    return pd.DataFrame(rows), absorbed


def cluster_rows(clusters: list[dict], absorbed: set[int], streets: pd.DataFrame, osm: pd.DataFrame,
                 name_max_m: float, radius_m: float) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(clusters):
        if i in absorbed:
            continue
        sub = streets.loc[c["indices"]]
        first = sub.iloc[0]
        quartiere = nearest_neighbourhood(c["lat"], c["lon"], osm, name_max_m)
        n = len(c["indices"])
        counts = _territory_counts(sub["territories"])
        territories = ";".join(counts)  # same format as the registry, most frequent first
        rows.append({
            "place_source": "Rilevato da odonimi ANNCSU geocodificati",
            "place_source_id": f"cluster:{c['municipality_belfiore']}:{c['lat']:.4f}_{c['lon']:.4f}",
            "odonimo": quartiere or f"Area di {first['municipality_name']}", "site_kind": "quartiere",
            "site_detail": f"{n} vie con riferimenti coloniali entro {radius_m:.0f} m dal centro ("
            + ", ".join(f"{t} {k}" for t, k in counts.items())
            + "): "
            + _street_list(list(sub["odonimo"])),
            "municipality_belfiore": c["municipality_belfiore"], "municipality_istat": first["municipality_istat_x"],
            "municipality_name": first["municipality_name"], "region_name": first["region_name"],
            "lon": c["lon"], "lat": c["lat"], "coord_precision": "cluster_centroid",
            "person_id": CLUSTER_PERSON_ID, "canonical_name": CLUSTER_CANONICAL_NAME, "matched_alias": "",
            "match_score": float(n), "match_method": "cluster_streets", "odonimo_normalized": "",
            "review_status": "needs_review", "entity_type": "cluster", "territories": territories, "role_category": "",
            "connection_summary_it": (
                f"Raggruppamento rilevato automaticamente di {n} vie intitolate a persone e luoghi del registro "
                "(match accettati) a meno di %.0f m dal centro. Il nome dell'area e' quello del quartiere OSM "
                "piu' vicino (entro %.0f m) e non e' verificato." % (radius_m, name_max_m)
            ),
            "source_url": "", "cluster_n_streets": n,
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", default="data/raw/quartieri")
    ap.add_argument("--comuni-raw-dir", default="data/raw/public_places", help="holds wikidata_comuni.csv (read-only)")
    ap.add_argument("--municipalities", default="data/raw/anncsu/Elenco-comuni-italiani.xlsx")
    ap.add_argument("--registry", default="data/manual/people_registry.csv")
    ap.add_argument("--places-registry", default="data/manual/place_registry.csv")
    ap.add_argument("--streets", default="data/processed/street_matches_geocoded.csv")
    ap.add_argument("--themed", default=None, help="default: from config/sources.yml")
    ap.add_argument("--sources-config", default="config/sources.yml")
    ap.add_argument("--output", default="data/processed/quartieri_matches.csv")
    ap.add_argument("--fuzzy-threshold", type=int, default=93)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.sources_config).read_text(encoding="utf-8"))["quartieri"]
    cl_cfg = cfg["cluster"]
    registry = load_authorities(args.registry, args.places_registry or None)
    muni = load_municipalities(load_istat_municipalities(args.municipalities), Path(args.comuni_raw_dir))

    osm = load_osm_quartieri(Path(args.raw_dir), muni)
    city = load_city_lists(Path(args.raw_dir), muni)
    istat = load_istat_localita(Path(args.raw_dir), muni)
    # order of priority for duplicates: official city list, OSM, ISTAT locality
    entities = combine_named_sources(city, osm, istat)
    totals = region_totals(entities)
    print(f"Named areas: {len(entities)} (distinct by comune and name): official lists {len(city)}, OSM {len(osm)}, "
          f"ISTAT localities {len(istat)} before deduplication")
    print(entities.groupby("place_source").size().to_string())
    # name of the area nearest to a cluster: only sources with real coordinates (no ISTAT localities, no centroids)
    nearby_names = combine_named_sources(city[city["coord_precision"] != "municipality_centroid"], osm)

    named = named_rows(entities, registry, args.fuzzy_threshold)
    print(f"Named matches: {len(named)}")

    streets = pd.read_csv(args.streets, dtype=str).fillna("")
    streets = streets[(streets["review_status"] == "accepted_auto") & (streets["lat"] != "")]
    clusters = detect_street_clusters(streets, cl_cfg["min_streets"], cl_cfg["radius_m"])
    print(f"Clusters (>= {cl_cfg['min_streets']} streets within {cl_cfg['radius_m']} m): {len(clusters)}")

    themed, absorbed = themed_rows(
        load_themed_districts(args.themed or cfg["themed_districts"]), muni, clusters, streets, cl_cfg["name_max_distance_m"]
    )
    if not themed.empty and not named.empty:
        # a themed district replaces a named match located in its own area (e.g. OSM "Cirenaica" in Bologna)
        near = pd.Series(False, index=named.index)
        for _, t in themed.iterrows():
            d = haversine_m(named["lat"].astype(float), named["lon"].astype(float), t["lat"], t["lon"])
            near |= (d <= 1500) & (named["municipality_belfiore"] == t["municipality_belfiore"]) \
                & (named["coord_precision"] != "municipality_centroid")
        if near.any():
            print("Named matches replaced by themed districts:", ", ".join(named.loc[near, "name"] + " (" + named.loc[near, "municipality_name"] + ")"))
        named = named[~near]
    detected = cluster_rows(clusters, absorbed, streets, nearby_names, cl_cfg["name_max_distance_m"], cl_cfg["radius_m"])

    out = pd.concat([named, themed, detected], ignore_index=True, sort=False)
    out["progressivo_odonimo"] = out["place_source_id"]
    out["dug"], out["duf"] = "", out["odonimo"]
    out["municipality_istat_x"] = out["municipality_istat_y"] = out["municipality_istat"]
    out["cluster_n_streets"] = pd.to_numeric(out["cluster_n_streets"], errors="coerce").astype("Int64")
    out["total_kind_region"] = out["region_name"].map(totals).astype("Int64")
    out = out.drop(columns=["municipality_istat", "name_alt", "name"], errors="ignore")
    out = out.sort_values(["region_name", "municipality_name", "odonimo"]).reset_index(drop=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    out.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)
    print(out.groupby(["match_method", "review_status"]).size().to_string())
    print(f"Wrote {args.output} ({len(out)} rows)")


if __name__ == "__main__":
    main()
