from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

FAMILIES = ("centrodestra", "centrosinistra", "m5s", "civica", "altro", "n.d.")


def normalize_list_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    text = re.sub(r"[^A-Z0-9+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_rules(path: str | Path = "config/party_families.yml") -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_compiled"] = {
        fam: [re.compile(p) for p in patterns] for fam, patterns in cfg["families"].items()
    }
    return cfg


def classify_lists(raw, rules: dict) -> str:
    """Classifica il testo grezzo delle liste di sostegno in una famiglia (vedi config/party_families.yml)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or not str(raw).strip():
        return "n.d."
    segments = [normalize_list_text(seg) for seg in str(raw).split("|")]
    segments = [seg for seg in segments if seg]
    if not segments or any(m in seg for seg in segments for m in rules.get("none_markers", [])):
        return "n.d."
    found = {
        fam
        for seg in segments
        for fam, patterns in rules["_compiled"].items()
        if any(p.search(seg) for p in patterns)
    }
    if not found:
        return "civica"
    if "centrodestra" in found:
        return "centrodestra" if found <= {"centrodestra", "neutro"} else "altro"
    if "centrosinistra" in found:
        return "centrosinistra"
    if "m5s" in found:
        return "m5s"
    return "altro"
