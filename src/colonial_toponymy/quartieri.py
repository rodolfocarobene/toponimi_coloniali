"""Neighbourhoods (quartieri): named ones from OpenStreetMap, curated themed districts and clusters of streets.

Three kinds of rows share site_kind="quartiere":

* named neighbourhoods whose name contains a registry name ("Quartiere Istria", "Cirenaica"): matched like
  public places. People are auto-accepted only on an exact canonical name or alias. Places/battles are
  always needs_review: a neighbourhood called "Libia" may be a dedication, an old toponym or a local name;
* curated themed districts (config/quartieri_tematici.yml), e.g. the informal "Quartiere Africano" of Rome:
  the name contains no registry name, the colonial theme is documented by a source;
* detected clusters: at least N distinct colonial-themed streets (accepted street matches) within a given
  radius, found from geocoded street matches. Always needs_review (match_method "cluster_streets").
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .matcher import build_alias_records, match_odonimo
from .normalize import HONORIFICS, ROAD_PREFIXES, _strip_leading_article, normalize_text
from .places import EXTRA_TITLES, name_variants
from .public_sources import ENTITY_COLUMNS, OSM_REGIONS, assign_nearest_municipality

CLUSTER_PERSON_ID = "cluster"
CLUSTER_CANONICAL_NAME = "Cluster di odonimi coloniali"
THEME_PERSON_PREFIX = "tema_"
THEME_CANONICAL_NAME = "Quartiere a tema coloniale"

# Generic words in front of a neighbourhood name: "Quartiere Istria", "Rione Libia", "Villaggio Eritrea".
QUARTIERE_WORDS = {
    "quartiere", "quartieri", "rione", "zona", "villaggio", "borgata", "borgo", "frazione", "localita",
    "nucleo", "lido", "area", "comparto", "settore", "residence",
}
OSM_PLACE_TAGS = ("quarter", "neighbourhood", "suburb")


def normalize_quartiere_name(text: str, strip_honorifics: bool = False) -> str:
    tokens = normalize_text(text).split()
    tokens = [t for t in (t.strip("'") for t in tokens) if t]
    while tokens and tokens[0] in QUARTIERE_WORDS:
        tokens = _strip_leading_article(tokens[1:]) if len(tokens) > 1 else []
    if strip_honorifics:
        titles = HONORIFICS | EXTRA_TITLES
        while tokens and tokens[0] in titles:
            tokens.pop(0)
    return " ".join(tokens)


def match_quartiere_name(raw: str, aliases, fuzzy_threshold: int = 93) -> dict | None:
    """Best registry match for one neighbourhood name (whole name or one of its quoted/split parts)."""
    best = None
    for variant in name_variants(raw):
        if normalize_text(variant).split()[:1] and normalize_text(variant).split()[0] in ROAD_PREFIXES - QUARTIERE_WORDS:
            continue  # "Via Istria" is an address, not a neighbourhood
        m = match_odonimo(variant, aliases, fuzzy_threshold=fuzzy_threshold, normalizer=normalize_quartiere_name)
        if m and (best is None or m["match_score"] > best["match_score"]):
            m["matched_text"] = variant
            best = m
    return best


def match_quartieri_dataframe(entities: pd.DataFrame, registry: pd.DataFrame, fuzzy_threshold: int = 93) -> pd.DataFrame:
    """Match the `name` of every neighbourhood against the registry (each distinct name once).

    Auto-accept only people with an exact canonical name or alias. A bare surname (allow_surname_only) is
    only a review candidate and there is no surname_in_name tier: a neighbourhood called "Locatelli" is far more
    likely a local name than the colonial figure.
    """
    aliases = build_alias_records(registry)
    entity_type = dict(zip(registry["person_id"], registry["entity_type"]))
    cache: dict[str, dict | None] = {}
    rows = []
    for rec in entities.to_dict("records"):
        name = str(rec["name"])
        if name not in cache:
            cache[name] = match_quartiere_name(name, aliases, fuzzy_threshold)
        match = cache[name]
        if not match:
            continue
        out = dict(rec)
        out.update(match)
        auto = (
            match["match_method"] in {"exact_canonical", "exact_alias"}
            and entity_type.get(match["person_id"], "person") == "person"
        )
        out["review_status"] = "accepted_auto" if auto else "needs_review"
        rows.append(out)
    return pd.DataFrame(rows)


def load_osm_quartieri(raw_dir: Path, muni: pd.DataFrame) -> pd.DataFrame:
    """Named neighbourhoods from the Overpass files written by scripts/02c_download_quartieri.py.

    Elements: place=quarter|neighbourhood|suburb nodes/ways/relations and admin_level 9/10 boundaries.
    The municipality is the one in addr:city when it exists in the region, else the nearest centroid in the
    region (approximate, see assign_nearest_municipality). One row per distinct (comune, normalized name):
    a node and a boundary with the same name count once, points preferred.
    """
    rows = []
    for iso, region in OSM_REGIONS.items():
        for path in sorted(raw_dir.glob(f"osm_quartieri_{iso}.json")):
            for e in json.loads(path.read_text(encoding="utf-8")).get("elements", []):
                tags = e.get("tags", {})
                lon = e.get("lon", (e.get("center") or {}).get("lon"))
                lat = e.get("lat", (e.get("center") or {}).get("lat"))
                if not tags.get("name") or lon is None:
                    continue
                kind = tags.get("place") or f"boundary admin_level={tags.get('admin_level', '')}"
                rows.append({
                    "place_source": "OpenStreetMap (Overpass)", "place_source_id": f"{e['type']}/{e['id']}",
                    "name": tags["name"], "site_kind": "quartiere", "site_detail": f"OSM {kind}",
                    "name_alt": tags.get("official_name", "") or tags.get("alt_name", ""),
                    "municipality_belfiore": "", "municipality_istat": "",
                    "municipality_name": tags.get("addr:city", ""),
                    "region_name": region, "lon": lon, "lat": lat, "coord_precision": "point",
                    "_point": e["type"] == "node",
                })
    if not rows:
        return pd.DataFrame(columns=ENTITY_COLUMNS)
    df = pd.DataFrame(rows)
    df["_key"] = df["name"].map(normalize_quartiere_name)
    df = df[df["_key"] != ""].copy()
    df["lon"], df["lat"] = df["lon"].astype(float), df["lat"].astype(float)
    df = assign_nearest_municipality(df, muni)
    # nodes before relations/ways so that the point is kept
    df = df.sort_values("_point", ascending=False, kind="stable")
    df = df[~df.duplicated(["municipality_istat", "_key"])]
    return df.drop(columns=["_point", "_key"]).reset_index(drop=True)


def region_totals(entities: pd.DataFrame) -> pd.Series:
    """Number of named neighbourhoods per region (denominator of total_kind_region)."""
    return entities.groupby("region_name").size().rename("total_kind_region")


def load_themed_districts(path: str | Path) -> list[dict]:
    import yaml

    p = Path(path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    items = data.get("quartieri", [])
    required = {"id", "name", "comune", "lat", "lon", "description", "source_url", "source_title"}
    for item in items:
        missing = required - set(item)
        if missing:
            raise ValueError(f"themed district {item.get('id', item.get('name'))}: missing {sorted(missing)}")
    return items


def haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


def detect_street_clusters(streets: pd.DataFrame, min_streets: int = 5, radius_m: float = 600.0) -> list[dict]:
    """Greedy radius clusters of distinct streets, computed per municipality.

    `streets` needs: municipality_belfiore, odonimo, odonimo_normalized, lat, lon. Streets of the same
    municipality with the same normalized name count once (segments of one street, via/piazza twins). Take
    the street with most neighbours within radius_m, cluster = the unassigned streets within radius_m of it,
    repeat while at least min_streets remain. Clusters are therefore at most 2*radius_m wide (no chaining).
    Returns dicts with: municipality_belfiore, indices (row labels of `streets`), lat, lon (median centre),
    radius_m (max distance from the centre).
    """
    df = streets.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    clusters = []
    for belfiore, grp in df.groupby("municipality_belfiore"):
        grp = grp.drop_duplicates("odonimo_normalized")
        if len(grp) < min_streets:
            continue
        lat, lon = grp["lat"].to_numpy(), grp["lon"].to_numpy()
        dist = haversine_m(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
        free = np.ones(len(grp), dtype=bool)
        while free.sum() >= min_streets:
            within = (dist <= radius_m) & free[None, :]
            counts = np.where(free, within.sum(axis=1), 0)
            seed = int(counts.argmax())
            if counts[seed] < min_streets:
                break
            members = np.flatnonzero(within[seed])
            clat, clon = float(np.median(lat[members])), float(np.median(lon[members]))
            spread = haversine_m(lat[members], lon[members], clat, clon)
            clusters.append({
                "municipality_belfiore": belfiore,
                "indices": list(grp.index[members]),
                "lat": clat, "lon": clon, "radius_m": float(spread.max()),
            })
            free[members] = False
    return sorted(clusters, key=lambda c: -len(c["indices"]))


def nearest_neighbourhood(lat: float, lon: float, entities: pd.DataFrame, max_m: float = 1000.0) -> str:
    """Name of the OSM neighbourhood nearest to a point within max_m ("" if none).

    Distance only: the municipality of the OSM entities is approximate."""
    pool = entities[entities["lat"].notna()]
    if pool.empty:
        return ""
    d = haversine_m(pool["lat"].astype(float), pool["lon"].astype(float), lat, lon)
    i = int(np.argmin(d))
    return str(pool.iloc[i]["name"]) if d[i] <= max_m else ""
