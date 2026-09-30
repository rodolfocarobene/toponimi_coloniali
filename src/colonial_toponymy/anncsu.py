from __future__ import annotations

import re
import shutil
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .io_utils import read_first_csv_from_zip, resolve_column, standardize_columns

DEFAULT_LANDING = "https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/Accedi-ai-servizi-di-dowload-massivo-in-Open-data/"
ISTAT_MUNICIPALITIES = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ItalianColonialToponymyResearch/0.1; +https://www.anncsu.gov.it/)",
    "Accept": "text/html,application/xhtml+xml,application/zip,*/*;q=0.8",
}


def get_download_links(landing_url: str = DEFAULT_LANDING) -> dict[str, str]:
    r = requests.get(landing_url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = {}
    for a in soup.find_all("a", href=True):
        label = " ".join(a.get_text(" ", strip=True).split())
        if "Stradario" in label or "Indirizzario" in label:
            out[label] = urljoin(landing_url, a["href"])
    return out


def download_file(url: str, destination: str | Path, referer: str = DEFAULT_LANDING) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = dict(HEADERS)
    headers["Referer"] = referer
    with requests.get(url, headers=headers, stream=True, timeout=180, allow_redirects=True) as r:
        r.raise_for_status()
        with destination.open("wb") as f:
            shutil.copyfileobj(r.raw, f)
    return destination


def download_anncsu_national(output_dir: str | Path, include_addresses: bool = False,
                              landing_url: str = DEFAULT_LANDING) -> dict[str, Path]:
    links = get_download_links(landing_url)
    wanted = ["Stradario Nazionale"] + (["Indirizzario Nazionale"] if include_addresses else [])
    outputs = {}
    for label in wanted:
        if label not in links:
            raise KeyError(f"Could not find {label!r} on ANNCSU download page")
        name = "stradario_nazionale.zip" if label.startswith("Stradario") else "indirizzario_nazionale.zip"
        outputs[label] = download_file(links[label], Path(output_dir) / name, referer=landing_url)
        time.sleep(1)
    return outputs


def _normalize_region_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _region_labels_match(requested: str, available: str) -> bool:
    requested_n = _normalize_region_label(requested)
    available_n = _normalize_region_label(available)
    if requested_n == available_n:
        return True
    return requested_n.startswith(available_n + " ") or available_n.startswith(requested_n + " ")


def download_region_address_file(region_name: str, output_dir: str | Path,
                                 landing_url: str = DEFAULT_LANDING) -> Path:
    links = get_download_links(landing_url)
    prefix = "Indirizzario regione "
    candidates = []
    for label in links:
        if not label.lower().startswith(prefix.lower()):
            continue
        anncsu_region = label[len(prefix):].strip()
        if _region_labels_match(region_name, anncsu_region):
            candidates.append(label)
    if not candidates:
        available = [label[len(prefix):].strip() for label in links if label.lower().startswith(prefix.lower())]
        raise KeyError(f"No ANNCSU regional address download found for {region_name!r}. Available regions: {available}")
    target = min(candidates, key=len)
    safe = re.sub(r"[^a-z0-9]+", "_", _normalize_region_label(region_name)).strip("_")
    return download_file(links[target], Path(output_dir) / f"indirizzario_{safe}.zip", referer=landing_url)


def download_istat_municipalities(destination: str | Path, url: str = ISTAT_MUNICIPALITIES) -> Path:
    return download_file(url, destination, referer="https://www.istat.it/")


def load_istat_municipalities(xlsx_path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, dtype=str).fillna("")
    df = standardize_columns(df)
    belfiore = resolve_column(df.columns, ["codice catastale del comune", "codice catastale", "codice_belfiore"], required=False)
    municipality = resolve_column(df.columns, ["denominazione in italiano", "denominazione del comune", "denominazione_comune"], required=False)
    region = resolve_column(df.columns, ["denominazione regione", "denominazione_regione"], required=False)
    province = resolve_column(df.columns, ["denominazione dell'unita territoriale sovracomunale", "denominazione provincia", "denominazione_provincia"], required=False)
    istat = resolve_column(df.columns, ["codice comune formato alfanumerico", "codice comune formato numerico", "codice_istat"], required=False)
    out = pd.DataFrame()
    if belfiore: out["municipality_belfiore"] = df[belfiore].str.strip().str.upper()
    if municipality: out["municipality_name"] = df[municipality].str.strip()
    if region: out["region_name"] = df[region].str.strip()
    if province: out["province_name"] = df[province].str.strip()
    if istat: out["municipality_istat"] = df[istat].str.strip()
    return out.drop_duplicates()


def load_stradario(zip_path: str | Path) -> pd.DataFrame:
    df = standardize_columns(read_first_csv_from_zip(zip_path))
    progressivo = resolve_column(df.columns, ["progressivo_nazionale", "progressivo odonimo", "progressivo_odonimo"])
    codice_comune = resolve_column(df.columns, ["codice_comune", "codice catastale del comune", "codice_catastale", "codice_belfiore"])
    codice_istat = resolve_column(df.columns, ["codice_istat", "codice istat", "codice comune istat"], required=False)
    odonimo = resolve_column(df.columns, ["odonimo", "denominazione_odonimo", "denominazione odonimo"], required=False)

    out = pd.DataFrame({
        "progressivo_odonimo": df[progressivo].astype(str).str.strip(),
        "municipality_belfiore": df[codice_comune].astype(str).str.strip().str.upper(),
    })
    if codice_istat:
        out["municipality_istat"] = df[codice_istat].astype(str).str.strip()
    if odonimo:
        out["odonimo"] = df[odonimo].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        out["dug"] = ""
        out["duf"] = out["odonimo"]
    else:
        dug = resolve_column(df.columns, ["dug", "denominazione urbanistica generica"], required=False)
        duf = resolve_column(df.columns, ["duf", "denominazione urbanistica ufficiale", "denominazione ufficiale"])
        out["dug"] = df[dug].astype(str).str.strip() if dug else ""
        out["duf"] = df[duf].astype(str).str.strip()
        out["odonimo"] = (out["dug"] + " " + out["duf"]).str.replace(r"\s+", " ", regex=True).str.strip()
    return out


def iter_address_chunks(zip_path: str | Path, chunksize: int = 250_000):
    for chunk in read_first_csv_from_zip(zip_path, chunksize=chunksize):
        yield standardize_columns(chunk)


def representative_coordinates(address_zip: str | Path, progressivi: set[str]) -> pd.DataFrame:
    parts = []
    for df in iter_address_chunks(address_zip):
        prog = resolve_column(df.columns, ["progressivo_nazionale_odonimo", "progressivo_odonimo", "progressivoodonimo"], required=False)
        if prog is None:
            prog = resolve_column(df.columns, ["progressivo_nazionale"], required=False)
        x = resolve_column(df.columns, ["coord_x_comune", "coordx", "coord_x", "longitudine", "longitude", "lon", "x"], required=False)
        y = resolve_column(df.columns, ["coord_y_comune", "coordy", "coord_y", "latitudine", "latitude", "lat", "y"], required=False)
        if not prog or not x or not y:
            continue
        sub = df[df[prog].astype(str).isin(progressivi)][[prog, x, y]].copy()
        if sub.empty:
            continue
        sub.columns = ["progressivo_odonimo", "lon", "lat"]
        sub["lon"] = pd.to_numeric(sub["lon"].str.replace(",", ".", regex=False), errors="coerce")
        sub["lat"] = pd.to_numeric(sub["lat"].str.replace(",", ".", regex=False), errors="coerce")
        sub = sub[sub["lon"].between(5, 20) & sub["lat"].between(34, 49)]
        parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=["progressivo_odonimo", "lon", "lat", "n_geocoded_accesses"])
    allc = pd.concat(parts, ignore_index=True)
    return (allc.groupby("progressivo_odonimo")
            .agg(lon=("lon", "median"), lat=("lat", "median"), n_geocoded_accesses=("lon", "size"))
            .reset_index())
