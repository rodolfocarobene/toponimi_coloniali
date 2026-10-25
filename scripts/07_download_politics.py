#!/usr/bin/env python3
"""Scarica e normalizza i dati sull'orientamento politico delle amministrazioni comunali e regionali.

Fonte: Ministero dell'Interno, Anagrafe degli amministratori locali e regionali (open data).
Output: data/processed/municipality_politics.csv e data/processed/region_politics.csv.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from colonial_toponymy.anncsu import load_stradario
from colonial_toponymy.politics import classify_lists, load_rules

BASE = "https://dait.interno.gov.it/documenti"
PAGE = "https://dait.interno.gov.it/elezioni/open-data/amministratori-locali-e-regionali-in-carica"
FILES = {"maggiororgano.csv": "sindaci e commissari", "ammreg.csv": "amministratori regionali"}
HEADERS = {"User-Agent": "ItalianColonialToponymyResearch/0.1 (ricerca universitaria, open data)"}
# Varianti ortografiche dell'Anagrafe rispetto all'elenco ISTAT.
NAME_ALIASES = {"vallecrosia al mare": "vallecrosia", "mojo alcantara": "moio alcantara"}
LIST_COL = "lista_appartenenza/collegamento"


def download(raw_dir: Path, refresh: bool) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in FILES:
        dest = raw_dir / name
        if dest.exists() and not refresh:
            continue
        url = f"{BASE}/{name}"
        r = requests.get(url, headers=HEADERS, timeout=180)
        r.raise_for_status()
        dest.write_bytes(r.content)
        header = r.content[:300].decode("utf-8", "replace").splitlines()
        manifest[name] = {
            "url": url,
            "page": PAGE,
            "downloaded": date.today().isoformat(),
            "bytes": len(r.content),
            "header": header[:2],
            "licence": "non dichiarata sulla pagina open data del Ministero dell'Interno; dati pubblici, verificare le condizioni d'uso",
        }
        print(f"scaricato {url} ({len(r.content)} byte)")
        time.sleep(2)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def read_anagrafe(path: Path) -> pd.DataFrame:
    # Le prime due righe sono titolo e data di aggiornamento.
    return pd.read_csv(path, sep=";", skiprows=2, dtype=str, keep_default_na=False)


def name_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")


def load_istat(path: Path) -> pd.DataFrame:
    x = pd.read_excel(path, dtype=str, keep_default_na=False)
    return pd.DataFrame({
        "municipality_istat": x["Codice Comune formato alfanumerico"].str.zfill(6),
        "istat_name": x["Denominazione in italiano"],
        "istat_name_full": x["Denominazione (Italiana e straniera)"],
        "sigla": x["Sigla automobilistica"],
        "region_code": x["Codice Regione"].str.zfill(2),
        "region_name": x["Denominazione Regione"],
    })


def build_municipalities(maggior: pd.DataFrame, istat: pd.DataFrame, rules: dict, source_url: str):
    mayors = maggior[maggior["descrizione_carica"] == "Sindaco"].copy()
    keys = {}
    for col in ("istat_name", "istat_name_full"):
        for _, r in istat.iterrows():
            for part in re.split(r"\s*/\s*", r[col]) + [r[col]]:
                keys.setdefault((name_key(part), r["sigla"]), set()).add(r["municipality_istat"])
    codes, how = [], []
    for _, r in mayors.iterrows():
        name = NAME_ALIASES.get(name_key(r["denominazione_comune"]), name_key(r["denominazione_comune"]))
        cand = keys.get((name, r["sigla_provincia"]), set())
        if len(cand) == 1:
            codes.append(next(iter(cand)))
            how.append("nome+sigla")
        else:
            # Ripiego: stesso nome nella stessa regione, se univoco.
            reg = istat[istat["region_code"] == r["codice_regione"]]
            hit = {c for (k, _), cs in keys.items() if k == name for c in cs}
            hit &= set(reg["municipality_istat"])
            codes.append(next(iter(hit)) if len(hit) == 1 else None)
            how.append("nome+regione" if len(hit) == 1 else "non_trovato")
    mayors["municipality_istat"] = codes
    mayors["match_how"] = how
    unmatched = mayors[mayors["municipality_istat"].isna()]
    mayors = mayors.dropna(subset=["municipality_istat"])
    dup = mayors["municipality_istat"].duplicated(keep=False)
    if dup.any():
        print(f"ATTENZIONE: {dup.sum()} righe con codice ISTAT duplicato; tengo la piu' recente")
        # Preferisce la riga con una lista indicata, poi la piu' recente.
        mayors = mayors.assign(_l=mayors[LIST_COL].map(lambda v: classify_lists(v, rules) != "n.d."),
                               _d=parse_date(mayors["data_elezione"])).sort_values(["_l", "_d"]).drop_duplicates(
            "municipality_istat", keep="last")
    mayors = mayors.merge(istat[["municipality_istat", "istat_name", "region_name"]], on="municipality_istat")
    out = pd.DataFrame({
        "municipality_istat": mayors["municipality_istat"],
        "municipality_name": mayors["istat_name"],
        "region_name": mayors["region_name"],
        "mayor_list": mayors[LIST_COL],
        "party_family": mayors[LIST_COL].map(lambda v: classify_lists(v, rules)),
        "election_date": parse_date(mayors["data_elezione"]),
        "source_url": source_url,
    }).sort_values("municipality_istat")
    return out, unmatched


def build_regions(ammreg: pd.DataFrame, istat: pd.DataFrame, rules: dict, source_url: str) -> pd.DataFrame:
    names = istat.drop_duplicates("region_code").set_index("region_code")["region_name"]
    pres = ammreg[ammreg["descrizione_carica"].str.contains("Presidente della regione", na=False)].copy()
    overrides = rules.get("region_coalition_overrides", {})
    rows = []
    for _, r in pres.iterrows():
        region = names.get(r["codice_regione"].zfill(2), r["denominazione_regione"])
        family = classify_lists(r[LIST_COL], rules)
        url = source_url
        if region in overrides:
            family, url = overrides[region]["coalition"], overrides[region]["source_url"]
        coalition = family if family in ("centrodestra", "centrosinistra") else "altro"
        rows.append({
            "region_name": region,
            "president": f"{r['nome'].title()} {r['cognome'].title()}",
            "coalition": coalition,
            "election_date": parse_date(pd.Series([r["data_elezione"]])).iloc[0],
            "source_url": url,
        })
    have = {r["region_name"] for r in rows}
    rows += [dict(a, source_url=a["source_url"]) for a in rules.get("region_additions", []) if a["region_name"] not in have]
    return pd.DataFrame(rows).sort_values("region_name")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", default="data/raw/politics")
    ap.add_argument("--municipalities", default="data/raw/anncsu/Elenco-comuni-italiani.xlsx")
    ap.add_argument("--stradario", default="data/raw/anncsu/stradario_nazionale.zip")
    ap.add_argument("--rules", default="config/party_families.yml")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--no-download", action="store_true", help="usa solo i file gia' in data/raw/politics")
    ap.add_argument("--refresh", action="store_true", help="riscarica anche se i file esistono")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    if not args.no_download:
        download(raw_dir, args.refresh)
    rules = load_rules(args.rules)
    istat = load_istat(Path(args.municipalities))

    muni, unmatched = build_municipalities(
        read_anagrafe(raw_dir / "maggiororgano.csv"), istat, rules, f"{BASE}/maggiororgano.csv")
    regions = build_regions(read_anagrafe(raw_dir / "ammreg.csv"), istat, rules, f"{BASE}/ammreg.csv")

    # Denominatore: numero totale di odonimi ANNCSU per comune (stesso conteggio di 03_match_streets.py).
    streets = load_stradario(args.stradario).groupby("municipality_belfiore").size()
    bel = pd.read_excel(args.municipalities, dtype=str, keep_default_na=False)
    bel = dict(zip(bel["Codice Comune formato alfanumerico"].str.zfill(6), bel["Codice Catastale del Comune"]))
    muni["n_odonimi"] = muni["municipality_istat"].map(bel).map(streets).fillna(0).astype(int)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    muni.to_csv(out_dir / "municipality_politics.csv", index=False)
    regions.to_csv(out_dir / "region_politics.csv", index=False)

    print(f"\nComuni con sindaco in carica: {len(muni)} su {len(istat)} comuni ISTAT; "
          f"sindaci non agganciati all'ISTAT: {len(unmatched)}")
    if len(unmatched):
        print(unmatched[["denominazione_comune", "sigla_provincia"]].head(20).to_string(index=False))
    cov = (istat.merge(muni[["municipality_istat", "party_family"]], on="municipality_istat", how="left")
           .assign(has=lambda d: d["party_family"].notna()).groupby("region_name")["has"].agg(["sum", "size"]))
    cov.columns = ["con_sindaco", "comuni_istat"]
    print("\nCopertura per regione:\n" + cov.to_string())
    print("\nFamiglie (comuni):\n" + muni["party_family"].value_counts().to_string())
    print("\nPresidenti di regione:\n" + regions[["region_name", "president", "coalition"]].to_string(index=False))
    missing = sorted(set(istat["region_name"]) - set(regions["region_name"]))
    if missing:
        print(f"\nRegioni senza presidente nei dati: {missing}")


if __name__ == "__main__":
    main()
