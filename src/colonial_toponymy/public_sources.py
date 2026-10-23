"""Loaders for the public-place datasets downloaded by scripts/02b_download_public_places.py.

Every loader returns a DataFrame with the same columns (see ENTITY_COLUMNS), one row per named entity,
plus (where the source is a full inventory) a Series of per-region totals used as denominator.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .normalize import normalize_text

ENTITY_COLUMNS = [
    "place_source", "place_source_id", "name", "site_kind", "site_detail", "name_alt",
    "municipality_belfiore", "municipality_istat", "municipality_name", "region_name",
    "lon", "lat", "coord_precision",
]

# ISO 3166-2 area codes used by Overpass, with the region spelling used by the ISTAT table.
OSM_REGIONS = {
    "IT-65": "Abruzzo", "IT-77": "Basilicata", "IT-78": "Calabria", "IT-72": "Campania",
    "IT-45": "Emilia-Romagna", "IT-36": "Friuli-Venezia Giulia", "IT-62": "Lazio", "IT-42": "Liguria",
    "IT-25": "Lombardia", "IT-57": "Marche", "IT-67": "Molise", "IT-21": "Piemonte", "IT-75": "Puglia",
    "IT-88": "Sardegna", "IT-82": "Sicilia", "IT-52": "Toscana", "IT-32": "Trentino-Alto Adige/Südtirol",
    "IT-55": "Umbria", "IT-23": "Valle d'Aosta/Vallée d'Aoste", "IT-34": "Veneto",
}

_POINT = re.compile(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=ENTITY_COLUMNS)


def latest_file(raw_dir: Path, pattern: str) -> Path | None:
    files = sorted(raw_dir.glob(pattern))
    return files[-1] if files else None


def load_municipalities(istat: pd.DataFrame, raw_dir: Path) -> pd.DataFrame:
    """ISTAT municipalities plus lon/lat of the municipality centroid (Wikidata P625) where available."""
    muni = istat.copy()
    muni["name_key"] = muni["municipality_name"].map(normalize_text)
    path = raw_dir / "wikidata_comuni.csv"
    if path.exists():
        wd = pd.read_csv(path, dtype=str).fillna("")
        pts = wd["coord"].str.extract(_POINT).astype(float)
        wd["lon"], wd["lat"] = pts[0], pts[1]
        by_name = wd.assign(name_key=wd["cLabel"].map(normalize_text)).drop_duplicates("name_key", keep=False)
        wd = wd.drop_duplicates("istat")[["istat", "lon", "lat"]]
        muni = muni.merge(wd, left_on="municipality_istat", right_on="istat", how="left").drop(columns="istat")
        # Some ISTAT codes (e.g. Sardinian municipalities) differ from Wikidata P635: fall back to the unique name.
        missing = muni["lon"].isna()
        fallback = muni.loc[missing, ["name_key"]].merge(
            by_name[["name_key", "lon", "lat"]], on="name_key", how="left"
        )
        muni.loc[missing, ["lon", "lat"]] = fallback[["lon", "lat"]].values
    else:
        muni["lon"] = muni["lat"] = float("nan")
    return muni


def _attach_municipality(df: pd.DataFrame, muni: pd.DataFrame, on: str) -> pd.DataFrame:
    """Fill municipality/region (and municipality-centroid lon/lat where there is no point) from ISTAT."""
    cols = ["municipality_belfiore", "municipality_istat", "municipality_name", "region_name", "lon", "lat"]
    key = {"belfiore": "municipality_belfiore", "istat": "municipality_istat"}[on]
    lookup = muni[[key, *[c for c in cols if c != key]]].drop_duplicates(key)
    lookup = lookup.rename(columns={c: f"{c}__m" for c in cols if c != key})
    had_point = df["lon"].notna()
    out = df.merge(lookup, on=key, how="left")
    for c in cols:
        if c == key:
            continue
        blank = out[c].isna() | (out[c].astype(str) == "")
        out.loc[blank, c] = out.loc[blank, f"{c}__m"]
        out = out.drop(columns=f"{c}__m")
    out.loc[~had_point.values & out["lon"].notna(), "coord_precision"] = "municipality_centroid"
    return out


def load_schools(raw_dir: Path, muni: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """MIM Anagrafe scuole: one entity per school site (sede) and one per reference institute."""
    frames, year = [], ""
    for prefix, label in (("SCUANAGRAFESTAT", "statale"), ("SCUANAGRAFEPAR", "paritaria")):
        path = latest_file(raw_dir, f"{prefix}*.csv")
        if path is None:
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df["_regime"] = label
        year = str(df["ANNOSCOLASTICO"].iloc[0]) if len(df) else year
        frames.append(df)
    if not frames:
        return _empty(), pd.Series(dtype=int)
    raw = pd.concat(frames, ignore_index=True).fillna("")
    for col in ("CODICEISTITUTORIFERIMENTO", "DENOMINAZIONEISTITUTORIFERIMENTO"):
        if col not in raw:
            raw[col] = ""
    year_label = f"{year[:4]}/{year[4:]}" if len(year) == 6 else year
    source = f"MIM Anagrafe scuole {year_label}"

    sedi = pd.DataFrame({
        "place_source": source,
        "place_source_id": raw["CODICESCUOLA"],
        "name": raw["DENOMINAZIONESCUOLA"],
        "site_kind": "scuola",
        "site_detail": (
            raw["DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA"].str.capitalize()
            + " " + raw["_regime"]
            + raw["DENOMINAZIONEISTITUTORIFERIMENTO"].map(lambda s: f"; istituto: {s}" if s else "")
        ),
        "name_alt": "",
        "municipality_belfiore": raw["CODICECOMUNESCUOLA"].str.upper(),
    })
    # The institute (e.g. "I.C. A. LOCATELLI") is a named entity of its own, located at its main site.
    with_inst = raw[raw["CODICEISTITUTORIFERIMENTO"] != ""].copy()
    main_site = raw.drop_duplicates("CODICESCUOLA").set_index("CODICESCUOLA")["CODICECOMUNESCUOLA"].str.upper()
    inst = with_inst.drop_duplicates(["CODICEISTITUTORIFERIMENTO", "DENOMINAZIONEISTITUTORIFERIMENTO"])
    istituti = pd.DataFrame({
        "place_source": source,
        "place_source_id": inst["CODICEISTITUTORIFERIMENTO"],
        "name": inst["DENOMINAZIONEISTITUTORIFERIMENTO"],
        "site_kind": "scuola",
        "site_detail": "Istituto di riferimento (" + inst["_regime"] + ")",
        "name_alt": "",
        "municipality_belfiore": inst["CODICEISTITUTORIFERIMENTO"].map(main_site).fillna(inst["CODICECOMUNESCUOLA"].str.upper()),
    })
    sedi["is_sede"], istituti["is_sede"] = True, False
    entities = pd.concat([sedi, istituti], ignore_index=True)
    entities["municipality_istat"] = entities["municipality_name"] = entities["region_name"] = ""
    entities["lon"] = entities["lat"] = float("nan")
    entities["coord_precision"] = ""
    entities = _attach_municipality(entities, muni, "belfiore")
    denominator = (
        entities[entities["is_sede"]].drop_duplicates("place_source_id").groupby("region_name").size()
    )
    return entities[ENTITY_COLUMNS], denominator.rename("total_kind_region")


def _read_mur_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="cp1252", dtype=str).fillna("")


def _city_candidates(prefix: str) -> list[str]:
    prefix = re.sub(r"\s*\([A-Z]{2}\)", "", prefix)
    out = [prefix]
    out += [p for p in re.split(r"\s+e\s+|-|\s+di\s+", prefix) if p != prefix]
    return [normalize_text(c) for c in out if c.strip()]


def load_universities(raw_dir: Path, muni: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """MUR USTAT: atenei (by name, located by the city before ' - ') and collegi universitari."""
    rows = []
    by_name = muni.drop_duplicates("name_key").set_index("name_key")
    path = latest_file(raw_dir, "mur_*_atenei_strutture.csv")
    if path is not None:
        year = re.search(r"mur_(\d{4})_", path.name).group(1)
        df = _read_mur_csv(path).drop_duplicates("COD_Ateneo")
        for _, r in df.iterrows():
            name = r["NOME_ATENEO"].strip()
            city = name.split(" - ", 1)[0]
            key = next((c for c in _city_candidates(city) if c in by_name.index), None)
            m = by_name.loc[key] if key else None
            rows.append({
                "place_source": f"MUR USTAT atenei {year}", "place_source_id": f"ateneo:{r['COD_Ateneo']}",
                "name": name, "site_kind": "universita", "site_detail": "Ateneo", "name_alt": "",
                "municipality_belfiore": m["municipality_belfiore"] if m is not None else "",
                "municipality_istat": m["municipality_istat"] if m is not None else "",
                "municipality_name": m["municipality_name"] if m is not None else "",
                "region_name": m["region_name"] if m is not None else "",
                "lon": m["lon"] if m is not None else float("nan"),
                "lat": m["lat"] if m is not None else float("nan"),
                "coord_precision": "municipality_centroid" if m is not None else "",
            })
    path = latest_file(raw_dir, "mur_*_collegi_alloggi_comune.csv")
    if path is not None:
        year = re.search(r"mur_(\d{4})_", path.name).group(1)
        df = _read_mur_csv(path)
        for _, r in df.drop_duplicates(["CODICE_COLLEGIO", "NOME_COMUNE"]).iterrows():
            m = by_name.loc[normalize_text(r["NOME_COMUNE"])] if normalize_text(r["NOME_COMUNE"]) in by_name.index else None
            rows.append({
                "place_source": f"MUR USTAT collegi universitari {year}",
                "place_source_id": f"collegio:{r['CODICE_COLLEGIO']}:{r['NOME_COMUNE']}",
                "name": r["NOME_COLLEGIO"].replace("''", "").replace('"', "").strip(),
                "site_kind": "universita", "site_detail": "Collegio universitario", "name_alt": "",
                "municipality_belfiore": m["municipality_belfiore"] if m is not None else "",
                "municipality_istat": m["municipality_istat"] if m is not None else "",
                "municipality_name": m["municipality_name"] if m is not None else r["NOME_COMUNE"].title(),
                "region_name": m["region_name"] if m is not None else r["NOME_REGIONE"],
                "lon": m["lon"] if m is not None else float("nan"),
                "lat": m["lat"] if m is not None else float("nan"),
                "coord_precision": "municipality_centroid" if m is not None else "",
            })
    if not rows:
        return _empty(), pd.Series(dtype=int)
    entities = pd.DataFrame(rows)[ENTITY_COLUMNS]
    denominator = entities.groupby("region_name").size().rename("total_kind_region")
    return entities, denominator


_SCHOOL_TYPE = re.compile(r"scuol|liceo|istitut|asilo|accademia|convitto|educandato", re.I)
_STREET_OR_AWARD_TYPE = re.compile(
    r"strad|via |viale|piazz|corso|largo|vicolo|ponte|galleria|monument|premi|coppa|trofeo|lungo|odonim|"
    r"toponim|opera|evento|competizione",
    re.I,
)
_UNIVERSITY_TYPE = re.compile(r"universit|facolt|dipartiment|collegio|ateneo|politecnic", re.I)


def load_wikidata(raw_dir: Path, muni: pd.DataFrame) -> pd.DataFrame:
    """Wikidata items in Italy 'named after' a registry person. Schools are skipped (covered by MIM)."""
    path = raw_dir / "wikidata_named_after.csv"
    if not path.exists():
        return _empty()
    df = pd.read_csv(path, dtype=str).fillna("")
    if df.empty:
        return _empty()
    df = df[~df["itemLabel"].str.fullmatch(r"Q\d+")]
    df = df[~df["typeLabel"].str.contains(_SCHOOL_TYPE) & ~df["typeLabel"].str.contains(_STREET_OR_AWARD_TYPE)]
    # P131* also walks up to provinces/regions (2-3 digit codes): keep municipality codes only.
    df["istat"] = df["istat"].where(df["istat"].str.fullmatch(r"\d{6}"), "")
    pts = df["coord"].str.extract(_POINT).astype(float)
    df["lon"], df["lat"] = pts[0], pts[1]
    grouped = (
        df.groupby("item", as_index=False)
        .agg(
            name=("itemLabel", "first"),
            honoree=("honoreeLabel", "first"),
            honoree_description=("honoreeDescription", "first"),
            types=("typeLabel", lambda s: ", ".join(sorted({x for x in s if x}))),
            istat=("istat", lambda s: next((x for x in s if x), "")),
            lon=("lon", "first"),
            lat=("lat", "first"),
        )
    )
    grouped = grouped[(grouped["istat"] != "") | grouped["lon"].notna()]
    kind = grouped["types"].str.contains(_UNIVERSITY_TYPE).map({True: "universita", False: "luogo_pubblico"})
    entities = pd.DataFrame({
        "place_source": "Wikidata (P138 intitolato a)",
        "place_source_id": grouped["item"].str.rsplit("/", n=1).str[-1],
        "name": grouped["name"],
        "site_kind": kind,
        "site_detail": grouped["types"] + "; intitolato a: " + grouped["honoree"]
        + grouped["honoree_description"].map(lambda s: f" ({s})" if s else ""),
        "name_alt": grouped["honoree"],
        "municipality_belfiore": "", "municipality_istat": grouped["istat"],
        "municipality_name": "", "region_name": "",
        "lon": grouped["lon"], "lat": grouped["lat"],
        "coord_precision": grouped["lon"].notna().map({True: "point", False: ""}),
    })
    entities = _attach_municipality(entities, muni, "istat")
    entities["region_name"] = entities["region_name"].fillna("")
    return entities[ENTITY_COLUMNS]


def _osm_kind_detail(tags: dict) -> tuple[str, str]:
    amenity = tags.get("amenity", "")
    if amenity in {"university", "college"}:
        return "universita", f"OSM amenity={amenity}"
    for key in ("amenity", "military", "leisure", "tourism", "aeroway"):
        if tags.get(key):
            return "luogo_pubblico", f"OSM {key}={tags[key]}"
    return "luogo_pubblico", "OSM"


def load_osm(raw_dir: Path, muni: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """OSM candidates (name contains a registry name) and per-region totals by site_kind."""
    rows, totals = [], []
    for iso, region in OSM_REGIONS.items():
        path = raw_dir / f"osm_{iso}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        elements = data.get("elements", [])
        counts = [e for e in elements if e.get("type") == "count"]
        if len(counts) >= 2:
            totals.append({"region_name": region, "site_kind": "luogo_pubblico", "n": int(counts[0]["tags"]["total"])})
            totals.append({"region_name": region, "site_kind": "universita", "n": int(counts[1]["tags"]["total"])})
        for e in elements:
            if e.get("type") == "count":
                continue
            tags = e.get("tags", {})
            lon = e.get("lon", (e.get("center") or {}).get("lon"))
            lat = e.get("lat", (e.get("center") or {}).get("lat"))
            kind, detail = _osm_kind_detail(tags)
            rows.append({
                "place_source": "OpenStreetMap (Overpass)", "place_source_id": f"{e['type']}/{e['id']}",
                "name": tags.get("name", ""), "site_kind": kind, "site_detail": detail,
                "name_alt": tags.get("official_name", ""),
                "municipality_belfiore": "", "municipality_istat": "",
                "municipality_name": tags.get("addr:city", ""), "region_name": region,
                "lon": lon, "lat": lat, "coord_precision": "point" if lon is not None else "",
            })
    entities = pd.DataFrame(rows, columns=ENTITY_COLUMNS) if rows else _empty()
    return entities, pd.DataFrame(totals, columns=["region_name", "site_kind", "n"])


def assign_nearest_municipality(entities: pd.DataFrame, muni: pd.DataFrame) -> pd.DataFrame:
    """Fill municipality for point entities lacking one.

    Uses the municipality named in addr:city when it exists in the region, otherwise the nearest
    centroid within the same region. Approximate (not point-in-polygon): only for display.
    """
    out = entities.copy()
    cand = muni.dropna(subset=["lon", "lat"])
    for idx, row in out[(out["municipality_istat"] == "") & out["lon"].notna()].iterrows():
        pool = cand[cand["region_name"] == row["region_name"]]
        if pool.empty:
            continue
        named = pool[pool["name_key"] == normalize_text(row["municipality_name"])]
        if len(named) == 1:
            near = named.iloc[0]
        else:
            d = (pool["lon"] - float(row["lon"])) ** 2 + ((pool["lat"] - float(row["lat"])) * 1.3) ** 2
            near = pool.loc[d.idxmin()]
        out.loc[idx, ["municipality_belfiore", "municipality_istat"]] = near["municipality_belfiore"], near["municipality_istat"]
        out.at[idx, "municipality_name"] = near["municipality_name"]
    return out
