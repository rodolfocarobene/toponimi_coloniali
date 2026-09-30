#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from colonial_toponymy.anncsu import (
    _normalize_region_label,
    download_region_address_file,
    representative_coordinates,
)


def main():
    ap = argparse.ArgumentParser(description="Attach representative coordinates using ANNCSU regional address files.")
    ap.add_argument("--matches", default="data/processed/street_matches.csv")
    ap.add_argument("--raw-dir", default="data/raw/anncsu")
    ap.add_argument("--output", default="data/processed/street_matches_geocoded.csv")
    ap.add_argument("--no-download", action="store_true", help="Only use already downloaded regional indirizzario ZIPs.")
    args = ap.parse_args()

    matches = pd.read_csv(args.matches, dtype=str).fillna("")
    all_coords = []
    raw = Path(args.raw_dir)
    regions_processed = 0
    for region, sub in matches.groupby("region_name"):
        if not region:
            continue
        safe = '_'.join(_normalize_region_label(region).split())
        zip_path = raw / f"indirizzario_{safe}.zip"
        if not zip_path.exists() and not args.no_download:
            print(f"Downloading ANNCSU address file for {region}...")
            try:
                zip_path = download_region_address_file(region, raw)
            except Exception as exc:
                # Geocoding is an enrichment step. A missing/unavailable
                # regional archive must not discard the matched odonyms or
                # abort processing of the other regions.
                print(f"Warning: skipping geocoding for {region}: {exc}")
                continue
        if not zip_path.exists():
            print(f"Skipping {region}: no regional address ZIP")
            continue
        regions_processed += 1
        ids = set(sub["progressivo_odonimo"].astype(str))
        coords = representative_coordinates(zip_path, ids)
        all_coords.append(coords)

    if regions_processed == 0 and args.no_download:
        raise SystemExit(
            "No ANNCSU regional address ZIPs were found in "
            f"{raw}. The --no-download option only works after those archives have "
            "already been downloaded. Run this command once WITHOUT --no-download:\n"
            "  python scripts/04_geocode_matches.py"
        )

    coords = pd.concat(all_coords, ignore_index=True).drop_duplicates("progressivo_odonimo") if all_coords else pd.DataFrame()
    out = matches.merge(coords, on="progressivo_odonimo", how="left") if len(coords) else matches.copy()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    out.to_parquet(Path(args.output).with_suffix(".parquet"), index=False)
    print(f"Wrote {len(out)} matched odonyms; {out.get('lat', pd.Series(dtype=float)).notna().sum()} have representative coordinates.")

if __name__ == "__main__":
    main()
