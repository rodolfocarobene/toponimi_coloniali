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

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .matcher import build_alias_records, match_odonimo
from .normalize import HONORIFICS, ROAD_PREFIXES, _strip_leading_article, normalize_text
from .places import EXTRA_TITLES, name_variants
from .public_sources import ENTITY_COLUMNS, OSM_REGIONS, _attach_municipality, assign_nearest_municipality

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


# ---------------------------------------------------------------------------------------------------------
# ISTAT localities and official city lists (see scripts/02c_download_quartieri.py)
# ---------------------------------------------------------------------------------------------------------

ISTAT_LOCALITA_ZIP = "istat/LocalitaPuntuali_21.zip"
ISTAT_REGION_CODES = {
    1: "Piemonte", 2: "Valle d'Aosta/Vallée d'Aoste", 3: "Lombardia", 4: "Trentino-Alto Adige/Südtirol",
    5: "Veneto", 6: "Friuli-Venezia Giulia", 7: "Liguria", 8: "Emilia-Romagna", 9: "Toscana", 10: "Umbria",
    11: "Marche", 12: "Lazio", 13: "Abruzzo", 14: "Molise", 15: "Campania", 16: "Puglia", 17: "Basilicata",
    18: "Calabria", 19: "Sicilia", 20: "Sardegna",
}
# TIPO_LOC of the ISTAT census: 1 centro abitato, 2 nucleo abitato, 3 localita produttiva, 4 case sparse
ISTAT_LOCALITA_TYPES = {1: "centro abitato", 2: "nucleo abitato", 3: "localita produttiva"}


def utm32n_to_wgs84(easting, northing) -> tuple[np.ndarray, np.ndarray]:
    """Inverse transverse Mercator (Krueger series) for the ISTAT single-zone UTM 32N grid (ETRF2000 ~ WGS84).

    ISTAT uses zone 32N for the whole of Italy, so eastings reach 1.3 million m in Puglia: the series is
    accurate to well under a metre at that distance. Returns (lon, lat) in degrees."""
    e, n_ = np.asarray(easting, dtype=float), np.asarray(northing, dtype=float)
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    n = f / (2 - f)
    big_a = a / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    beta = [n / 2 - 2 * n**2 / 3 + 37 * n**3 / 96 - n**4 / 360, n**2 / 48 + n**3 / 15 - 437 * n**4 / 1440,
            17 * n**3 / 480 - 37 * n**4 / 840, 4397 * n**4 / 161280]
    delta = [2 * n - 2 * n**2 / 3 - 2 * n**3 + 116 * n**4 / 45, 7 * n**2 / 3 - 8 * n**3 / 5 - 227 * n**4 / 45,
             56 * n**3 / 15 - 136 * n**4 / 35, 4279 * n**4 / 630]
    xi, eta = n_ / (k0 * big_a), (e - 500000.0) / (k0 * big_a)
    xi_p, eta_p = xi.copy(), eta.copy()
    for j, b in enumerate(beta, start=1):
        xi_p = xi_p - b * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta_p = eta_p - b * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xi_p) / np.cosh(eta_p))
    lat = chi + sum(d * np.sin(2 * j * chi) for j, d in enumerate(delta, start=1))
    lon = np.radians(9.0) + np.arctan2(np.sinh(eta_p), np.cos(xi_p))
    return np.degrees(lon), np.degrees(lat)


def load_istat_localita(raw_dir: Path, muni: pd.DataFrame) -> pd.DataFrame:
    """Named localities of the ISTAT 2021 census (centri, nuclei abitati, localita produttive).

    Source: LocalitaPuntuali_21.zip (basi territoriali ISTAT), one point per locality, UTM 32N coordinates.
    "Case sparse" (TIPO_LOC 4) are not names and are skipped. PRO_COM codes of 2021 that no longer exist in the
    current ISTAT list (merged or renumbered municipalities) get the nearest municipality of the region."""
    path = raw_dir / ISTAT_LOCALITA_ZIP
    if not path.exists():
        return pd.DataFrame(columns=ENTITY_COLUMNS)
    with zipfile.ZipFile(path) as z:
        member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        raw = pd.read_csv(io.BytesIO(z.read(member)), sep="\t", encoding="cp1252", dtype=str, decimal=",")
    raw["TIPO_LOC"] = pd.to_numeric(raw["TIPO_LOC"], errors="coerce")
    raw = raw[raw["TIPO_LOC"].isin(ISTAT_LOCALITA_TYPES) & raw["NOME"].notna()].copy()
    lon, lat = utm32n_to_wgs84(raw["POINT_X"].str.replace(",", ".").astype(float),
                               raw["POINT_Y"].str.replace(",", ".").astype(float))
    df = pd.DataFrame({
        "place_source": "ISTAT, località abitate (basi territoriali 2021)", "place_source_id": raw["LOC_ID"].values,
        "name": raw["NOME"].str.strip().values, "site_kind": "quartiere",
        "site_detail": ("Località ISTAT (" + raw["TIPO_LOC"].map(ISTAT_LOCALITA_TYPES) + ")").values,
        "name_alt": "", "municipality_belfiore": "", "municipality_istat": raw["PRO_COM"].str.zfill(6).values,
        "municipality_name": "", "region_name": raw["COD_REG"].astype(int).map(ISTAT_REGION_CODES).values,
        "lon": lon, "lat": lat, "coord_precision": "point",
    })
    known = df["municipality_istat"].isin(set(muni["municipality_istat"]))
    df = pd.concat([_attach_municipality(df[known], muni, on="istat"),
                    assign_nearest_municipality(df[~known].assign(municipality_istat=""), muni)], ignore_index=True)
    df["lon"], df["lat"] = df["lon"].astype(float), df["lat"].astype(float)
    return df[ENTITY_COLUMNS].reset_index(drop=True)


def _polygon_centroid(geometry: dict) -> tuple[float, float]:
    """Area-weighted centroid of the largest outer ring of a (Multi)Polygon in lon/lat (planar, display only)."""
    rings = [geometry["coordinates"][0]] if geometry["type"] == "Polygon" else [p[0] for p in geometry["coordinates"]]
    best, best_area = None, -1.0
    for ring in rings:
        pts = np.asarray(ring, dtype=float)
        x, y = pts[:, 0], pts[:, 1]
        cross = x[:-1] * y[1:] - x[1:] * y[:-1]
        area = cross.sum() / 2
        if abs(area) > best_area and area != 0:
            best_area = abs(area)
            best = (float(((x[:-1] + x[1:]) * cross).sum() / (6 * area)), float(((y[:-1] + y[1:]) * cross).sum() / (6 * area)))
    return best if best else (float(np.mean([c[0] for c in rings[0]])), float(np.mean([c[1] for c in rings[0]])))


def _display_name(name: str) -> str:
    """'MAGGIORE - MUSOCCO' -> 'Maggiore - Musocco' (some official lists are in capitals)."""
    if name != name.upper():
        return name.strip()
    return re.sub(r"(?<=\w)'(\w)", lambda m: "'" + m.group(1).lower(), name.strip().title())


def load_city_lists(raw_dir: Path, muni: pd.DataFrame) -> pd.DataFrame:
    """Official neighbourhood lists of the cities that publish open data (data/raw/quartieri/citta/).

    Milano: NIL (Nuclei d'Identita Locale) in force (PGT 2030) and the obsolete 2012 list, polygons -> centroid.
    Bologna: quartieri, zone, aree statistiche and zone di prossimita (Opendatasoft, centre given).
    Torino: zone statistiche (centre in Gauss-Boaga: the municipality centroid is used instead).
    Each file is optional. One row per file entry, deduplicated later by comune and normalized name."""
    d = raw_dir / "citta"
    rows: list[dict] = []

    def add(city, source, kind, name, lon=None, lat=None):
        if name and str(name).strip():
            rows.append({"city": city, "place_source": source, "name": _display_name(str(name)), "site_detail": kind,
                         "lon": lon, "lat": lat})

    for fname, kind, src in [
        ("milano_nil.geojson", "NIL vigente, PGT 2030", "Comune di Milano, dati aperti (CC BY)"),
        ("milano_nil_obsoleti_pgt2012.geojson", "NIL obsoleto, PGT 2012", "Comune di Milano, dati aperti (CC BY)"),
    ]:
        if (d / fname).exists():
            for f in json.loads((d / fname).read_text(encoding="utf-8"))["features"]:
                lon, lat = _polygon_centroid(f["geometry"])
                add("Milano", src, f"Elenco ufficiale: {kind}", f["properties"].get("NIL"), lon, lat)
    bologna = [
        ("bologna_quartieri-di-bologna.json", "quartiere", "quartiere"),
        ("bologna_zone-del-comune-di-bologna.json", "nomezona", "zona"),
        ("bologna_aree-statistiche.json", "area_statistica", "area statistica"),
        ("bologna_zone_urbanistiche.json", "zona_prossimita", "zona di prossimità"),
    ]
    for fname, field, kind in bologna:
        if (d / fname).exists():
            for r in json.loads((d / fname).read_text(encoding="utf-8")):
                pt = r.get("geo_point_2d") or {}
                add("Bologna", "Comune di Bologna, open data (CC BY 4.0)", f"Elenco ufficiale: {kind}", r.get(field),
                    pt.get("lon"), pt.get("lat"))
    if (d / "torino_zone_statistiche_csv.zip").exists():
        with zipfile.ZipFile(d / "torino_zone_statistiche_csv.zip") as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            zs = pd.read_csv(io.BytesIO(z.read(member)), sep=";", encoding="cp1252", dtype=str, usecols=["DENOM"])
        for name in zs["DENOM"]:
            add("Torino", "Città di Torino, dati aperti (CC BY)", "Elenco ufficiale: zona statistica", name)
    if not rows:
        return pd.DataFrame(columns=ENTITY_COLUMNS)
    df = pd.DataFrame(rows)
    key = muni.drop_duplicates("name_key").set_index("name_key")
    df["_nk"] = df["city"].map(normalize_text)
    df = df[df["_nk"].isin(key.index)].copy()
    df["municipality_istat"] = df["_nk"].map(key["municipality_istat"])
    df["place_source_id"] = df["city"].str.lower() + ":" + df["name"]
    df["site_kind"], df["name_alt"], df["coord_precision"] = "quartiere", "", "centroid"
    df["municipality_belfiore"], df["municipality_name"], df["region_name"] = "", "", ""
    df["lon"], df["lat"] = pd.to_numeric(df["lon"]), pd.to_numeric(df["lat"])
    df = _attach_municipality(df, muni, on="istat")
    return df[ENTITY_COLUMNS]


def combine_named_sources(*frames: pd.DataFrame) -> pd.DataFrame:
    """Concatenate named-area sources, earlier frames win: one row per (municipality_istat, normalized name)."""
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False)
    df["_key"] = df["name"].map(normalize_quartiere_name)
    df = df[df["_key"] != ""]
    df = df[~df.duplicated(["municipality_istat", "_key"])]
    return df.drop(columns="_key").reset_index(drop=True)


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
