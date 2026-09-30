#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from colonial_toponymy.anncsu import download_anncsu_national, download_istat_municipalities


def main():
    ap = argparse.ArgumentParser(description="Download official ANNCSU street data and the ISTAT municipality table.")
    ap.add_argument("--output-dir", default="data/raw/anncsu")
    ap.add_argument("--include-national-addresses", action="store_true", help="Large. Not needed for initial matching.")
    args = ap.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(download_anncsu_national(out, include_addresses=args.include_national_addresses))
    print(download_istat_municipalities(out / "Elenco-comuni-italiani.xlsx"))

if __name__ == "__main__":
    main()
