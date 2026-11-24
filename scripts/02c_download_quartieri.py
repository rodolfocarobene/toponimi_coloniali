#!/usr/bin/env python3
"""Download the named neighbourhoods of Italy from OpenStreetMap (Overpass), region by region.

Elements: place=quarter|neighbourhood|suburb (nodes, ways, relations) and administrative boundaries of
admin_level 9 and 10 (quartieri, circoscrizioni, municipi), all with a name. Only centres and tags are
fetched (no geometry). Output: data/raw/quartieri/osm_quartieri_<ISO 3166-2>.json and manifest.json.
Wikidata is not used: its neighbourhoods are a subset of those in OSM.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", default="data/raw/quartieri")
    ap.add_argument("--sources-config", default="config/sources.yml")
    ap.add_argument("--only", nargs="+", choices=sorted(OSM_REGIONS), help="ISO 3166-2 codes (default: all regions)")
    ap.add_argument("--force", action="store_true", help="Download again even if the file already exists.")
    args = ap.parse_args()

    endpoint = yaml.safe_load(Path(args.sources_config).read_text(encoding="utf-8"))["quartieri"]["overpass_endpoint"]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for iso, region in OSM_REGIONS.items():
        if args.only and iso not in args.only:
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
