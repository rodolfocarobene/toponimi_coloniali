#!/usr/bin/env python3
"""Download the open datasets used to look for registry names beyond streets.

Sources (details and access dates in config/sources.yml):
  schools      MIM "Anagrafe scuole" (statali + paritarie), latest school year in the catalog
  universities MUR/USTAT "Strutture atenei" and "Collegi universitari", latest year
  wikidata     municipality centroids and items "named after" a registry person (SPARQL)
  osm          OpenStreetMap (Overpass) libraries, town halls, hospitals, theatres, barracks,
               stadiums, parks, museums, airports, universities whose name contains a registry name
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

from colonial_toponymy.matcher import load_registry
from colonial_toponymy.normalize import normalize_text
from colonial_toponymy.public_sources import OSM_REGIONS

HEADERS = {"User-Agent": "toponimi-coloniali-research/0.1 (university research; low-volume, polite)"}
MANIFEST_REF: dict = {}  # filled by main(); lets skipped files still be listed
PAUSE = 3  # seconds between requests to the same service


def get(url: str, retries: int = 2, **kwargs) -> requests.Response:
    timeout = kwargs.pop("timeout", 120)
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(10 * (attempt + 1))


def save(path: Path, content: bytes, manifest: dict, source: str, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    manifest[path.name] = {"source": source, "url": url, "accessed": date.today().isoformat(), "bytes": len(content)}
    print(f"  saved {path} ({len(content) / 1e6:.2f} MB)")


def wanted(path: Path, force: bool) -> bool:
    if path.exists() and not force:
        if path.name not in MANIFEST_REF:
            stat = path.stat()
            MANIFEST_REF[path.name] = {
                "source": "downloaded in an earlier run", "accessed": date.fromtimestamp(stat.st_mtime).isoformat(),
                "bytes": stat.st_size,
            }
        print(f"  skip {path} (exists; use --force to refresh)")
        return False
    return True


def download_schools(out: Path, manifest: dict, force: bool, cfg: dict) -> None:
    base = cfg["mim_catalog_base"]
    catalog = get(cfg["mim_catalog_page"]).text
    for prefix in ("SCUANAGRAFESTAT", "SCUANAGRAFEPAR"):
        names = sorted(set(re.findall(rf"{prefix}(\d{{8}}\d*)\.csv", catalog)))
        if not names:
            raise SystemExit(f"No {prefix} file found in the MIM catalog page")
        latest = f"{prefix}{names[-1]}.csv"
        dest = out / latest
        if wanted(dest, force):
            url = f"{base}/{latest}"
            save(dest, get(url, timeout=300).content, manifest, "MIM Anagrafe scuole", url)
            time.sleep(PAUSE)


def _latest_ckan_year(api: str, pattern: str) -> str:
    packages = get(f"{api}/package_list").json()["result"]
    years = sorted(int(m.group(1)) for p in packages if (m := re.fullmatch(pattern, p)))
    return str(years[-1])


def download_universities(out: Path, manifest: dict, force: bool, cfg: dict) -> None:
    api = cfg["mur_ckan_api"]
    jobs = [
        (r"(\d{4})-contribuzione-e-interventi-atenei", "Strutture atenei", "atenei_strutture"),
        (r"(\d{4})-collegi-universitari", "Collegi Alloggi per comune", "collegi_alloggi_comune"),
    ]
    for pattern, resource_name, stem in jobs:
        year = _latest_ckan_year(api, pattern)
        package = pattern.replace(r"(\d{4})", year)
        dest = out / f"mur_{year}_{stem}.csv"
        if not wanted(dest, force):
            continue
        resources = get(f"{api}/package_show", params={"id": package}).json()["result"]["resources"]
        res = next(r for r in resources if resource_name in r["name"])
        save(dest, get(res["url"]).content, manifest, f"MUR USTAT {package}", res["url"])
        time.sleep(PAUSE)


def sparql(query: str, endpoint: str) -> bytes:
    for attempt in range(3):
        r = requests.post(
            endpoint,
            data={"query": query},
            headers={**HEADERS, "Accept": "text/csv"},
            timeout=180,
        )
        if r.status_code == 200:
            return r.content
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    raise RuntimeError("SPARQL request failed")


def registry_names(people_path: str) -> list[str]:
    people = load_registry(people_path)
    names: set[str] = set()
    for _, row in people.iterrows():
        for alias in [row["canonical_name"], *str(row.get("aliases", "")).split(";")]:
            alias = alias.strip()
            if len(alias.split()) >= 2:
                names.add(alias)
    return sorted(names)


def download_wikidata(out: Path, manifest: dict, force: bool, cfg: dict, people_path: str) -> None:
    endpoint = cfg["wikidata_sparql"]
    dest = out / "wikidata_comuni.csv"
    if wanted(dest, force):
        query = """SELECT ?cLabel ?istat ?coord WHERE {
  ?c wdt:P31 wd:Q747074 ; wdt:P635 ?istat ; wdt:P625 ?coord .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it". }
}"""
        save(dest, sparql(query, endpoint), manifest, "Wikidata (comuni, P635 + P625)", endpoint)
        time.sleep(PAUSE)

    dest = out / "wikidata_named_after.csv"
    if not wanted(dest, force):
        return
    names = registry_names(people_path)
    frames = []
    for i in range(0, len(names), 30):
        values = " ".join(f'"{n}"@{lang}' for n in names[i : i + 30] for lang in ("it", "en"))
        query = f"""SELECT DISTINCT ?item ?itemLabel ?honoree ?honoreeLabel ?honoreeDescription ?typeLabel ?coord ?istat WHERE {{
  VALUES ?hl {{ {values} }}
  ?honoree rdfs:label ?hl .
  ?item wdt:P138 ?honoree ; wdt:P17 wd:Q38 .
  OPTIONAL {{ ?item wdt:P31 ?type . }}
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  OPTIONAL {{ ?item wdt:P131* ?m . ?m wdt:P635 ?istat . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
}}"""
        frames.append(pd.read_csv(io.BytesIO(sparql(query, endpoint)), dtype=str))
        time.sleep(PAUSE)
    merged = pd.concat(frames, ignore_index=True).drop_duplicates()
    save(dest, merged.to_csv(index=False).encode("utf-8"), manifest, "Wikidata (P138 named after registry people)", endpoint)


def overpass_regex(registry: pd.DataFrame) -> str:
    """Case-insensitive superset of the registry names (last token of person aliases, whole place names)."""
    accents = {"a": "aàáâä", "e": "eèéêë", "i": "iìíîï", "o": "oòóôö", "u": "uùúûü"}
    terms: set[str] = set()
    for _, row in registry.iterrows():
        is_person = row.get("entity_type", "person") in ("", "person")
        canonical_tokens = normalize_text(row["canonical_name"]).replace("'", " ").split()
        for alias in [row["canonical_name"], *str(row.get("aliases", "")).split(";")]:
            tokens = normalize_text(alias).replace("'", " ").split()
            if not tokens:
                continue
            # surname for people (aliases that do not end in it, e.g. "Duca degli Abruzzi", stay whole)
            if is_person and tokens[-1] == canonical_tokens[-1]:
                term = tokens[-1]
            else:
                term = " ".join(tokens)
            if len(term) >= 4:
                terms.add(term)
    def pattern(term: str) -> str:
        return "".join(f"[{accents[c]}]" if c in accents else ("[ '’-]" if c == " " else c) for c in term)
    return "(" + "|".join(pattern(t) for t in sorted(terms)) + ")"


def download_osm(out: Path, manifest: dict, force: bool, cfg: dict, regex: str) -> None:
    endpoint = cfg["overpass_endpoint"]
    for iso, region in OSM_REGIONS.items():
        dest = out / f"osm_{iso}.json"
        if not wanted(dest, force):
            continue
        query = f"""[out:json][timeout:180];
area["ISO3166-2"="{iso}"]->.r;
(
  nwr(area.r)["name"]["amenity"~"^(library|townhall|hospital|clinic|theatre|cinema|community_centre|arts_centre|courthouse|police|fire_station|social_centre|events_venue|conference_centre)$"];
  nwr(area.r)["name"]["military"="barracks"];
  nwr(area.r)["name"]["leisure"~"^(stadium|sports_centre|park|garden|swimming_pool)$"];
  nwr(area.r)["name"]["tourism"="museum"];
  nwr(area.r)["name"]["aeroway"="aerodrome"];
)->.L;
nwr(area.r)["name"]["amenity"~"^(university|college)$"]->.U;
.L out count;
.U out count;
nwr.L["name"~"{regex}",i];
out center tags;
nwr.U["name"~"{regex}",i];
out center tags;"""
        r = None
        for attempt in range(3):
            try:
                r = requests.post(endpoint, data={"data": query}, headers=HEADERS, timeout=240)
                if r.status_code == 200:
                    break
            except requests.RequestException as exc:
                print(f"  {region}: {type(exc).__name__}")
                r = None
            time.sleep(30 * (attempt + 1))
        if r is None or r.status_code != 200:
            print(f"  WARNING: Overpass failed for {region}; re-run to retry")
            continue
        save(dest, r.content, manifest, f"OpenStreetMap via Overpass ({region})", endpoint)
        time.sleep(10)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", default="data/raw/public_places")
    ap.add_argument("--sources-config", default="config/sources.yml")
    ap.add_argument("--registry", default="data/manual/people_registry.csv")
    ap.add_argument("--places-registry", default="data/manual/place_registry.csv")
    ap.add_argument("--only", nargs="+", choices=["schools", "universities", "wikidata", "osm"])
    ap.add_argument("--force", action="store_true", help="Download again even if the file already exists.")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.sources_config).read_text(encoding="utf-8"))["public_places"]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    MANIFEST_REF.update(manifest)
    todo = set(args.only or ["schools", "universities", "wikidata", "osm"])

    if "schools" in todo:
        print("MIM Anagrafe scuole")
        download_schools(out, manifest, args.force, cfg)
    if "universities" in todo:
        print("MUR USTAT atenei e collegi")
        download_universities(out, manifest, args.force, cfg)
    if "wikidata" in todo:
        print("Wikidata")
        download_wikidata(out, manifest, args.force, cfg, args.registry)
    if "osm" in todo:
        print("OpenStreetMap / Overpass")
        frames = [load_registry(args.registry)]
        frames[0]["entity_type"] = "person"
        if Path(args.places_registry).exists():
            places = load_registry(args.places_registry)
            places["entity_type"] = "place"
            frames.append(places)
        download_osm(out, manifest, args.force, cfg, overpass_regex(pd.concat(frames, ignore_index=True)))
    manifest = {**MANIFEST_REF, **manifest}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
