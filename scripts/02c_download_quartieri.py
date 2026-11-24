#!/usr/bin/env python3
"""Download the named neighbourhoods of Italy from OpenStreetMap (Overpass), region by region.

Elements: place=quarter|neighbourhood|suburb (nodes, ways, relations) and administrative boundaries of
admin_level 9 and 10 (quartieri, circoscrizioni, municipi), all with a name. Only centres and tags are
fetched (no geometry). Output: data/raw/quartieri/osm_quartieri_<ISO 3166-2>.json and manifest.json.
Wikidata is not used: its neighbourhoods are a subset of those in OSM.

Other named areas (config/sources.yml, quartieri.istat_localita and quartieri.city_lists): the ISTAT 2021
localities (LocalitaPuntuali_21.zip) in data/raw/quartieri/istat/ and the official neighbourhood lists of
Milano, Bologna and Torino in data/raw/quartieri/citta/. Use --skip-osm or --skip-extra to limit the run.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import requests
import yaml

from colonial_toponymy.public_sources import OSM_REGIONS

HEADERS = {"User-Agent": "toponimi-coloniali-research/0.1 (university research; low-volume, polite)"}
PAUSE = 10  # seconds between regions


def build_query(iso: str) -> str:
    return f"""[out:json][timeout:240];
area["ISO3166-2"="{iso}"]->.r;
(
  nwr(area.r)["name"]["place"~"^(quarter|neighbourhood|suburb)$"];
  rel(area.r)["name"]["boundary"="administrative"]["admin_level"~"^(9|10)$"];
);
out center tags;"""


def fetch(endpoint: str, query: str, region: str) -> bytes | None:
    for attempt in range(3):
        try:
            r = requests.post(endpoint, data={"data": query}, headers=HEADERS, timeout=300)
            if r.status_code == 200:
                return r.content
            print(f"  {region}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            print(f"  {region}: {type(exc).__name__}")
        time.sleep(30 * (attempt + 1))
    return None


def download_file(url: str, dest: Path) -> bytes | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=300)
            if r.status_code == 200:
                return r.content
            print(f"  {dest.name}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            print(f"  {dest.name}: {type(exc).__name__}")
        time.sleep(15 * (attempt + 1))
    return None


def download_extra(cfg: dict, out: Path, manifest: dict, manifest_path: Path, force: bool) -> None:
    """ISTAT localities and city lists: plain file downloads, listed in the manifest with URL, date and size."""
    items = [{**cfg["istat_localita"], "source": "ISTAT, basi territoriali 2021, localita' puntuali (CC BY 4.0)"}]
    items += cfg.get("city_lists", [])
    for item in items:
        dest = out / item["file"]
        if dest.exists() and not force:
            print(f"  skip {dest} (exists; use --force to refresh)")
            continue
        content = download_file(item["url"], dest)
        if content is None:
            print(f"  WARNING: download failed for {item['url']}; re-run to retry")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        manifest[item["file"]] = {
            "source": item["source"], "url": item["url"], "accessed": date.today().isoformat(), "bytes": len(content),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  saved {dest} ({len(content) / 1e6:.2f} MB)")
        time.sleep(cfg["istat_localita"].get("pause_seconds", 5))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", default="data/raw/quartieri")
    ap.add_argument("--sources-config", default="config/sources.yml")
    ap.add_argument("--only", nargs="+", choices=sorted(OSM_REGIONS), help="ISO 3166-2 codes (default: all regions)")
    ap.add_argument("--skip-osm", action="store_true", help="Do not query Overpass.")
    ap.add_argument("--skip-extra", action="store_true", help="Do not download the ISTAT localities and the city lists.")
    ap.add_argument("--force", action="store_true", help="Download again even if the file already exists.")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.sources_config).read_text(encoding="utf-8"))["quartieri"]
    endpoint = cfg["overpass_endpoint"]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if not args.skip_extra and not args.only:
        download_extra(cfg, out, manifest, manifest_path, args.force)

    for iso, region in OSM_REGIONS.items():
        if args.skip_osm or (args.only and iso not in args.only):
            continue
        dest = out / f"osm_quartieri_{iso}.json"
        if dest.exists() and not args.force:
            print(f"  skip {dest} (exists; use --force to refresh)")
            continue
        content = fetch(endpoint, build_query(iso), region)
        if content is None:
            print(f"  WARNING: Overpass failed for {region}; re-run to retry")
            continue
        dest.write_bytes(content)
        manifest[dest.name] = {
            "source": f"OpenStreetMap via Overpass ({region}), place=quarter|neighbourhood|suburb + admin_level 9/10",
            "url": endpoint, "accessed": date.today().isoformat(), "bytes": len(content),
            "osm_base_timestamp": json.loads(content).get("osm3s", {}).get("timestamp_osm_base", ""),
        }
        print(f"  saved {dest} ({len(content) / 1e6:.2f} MB)")
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        time.sleep(PAUSE)


if __name__ == "__main__":
    main()
