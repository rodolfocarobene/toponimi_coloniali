from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz.fuzz import ratio

from .normalize import normalize_odonimo, normalize_text, surname


@dataclass(frozen=True)
class AliasRecord:
    person_id: str
    canonical_name: str
    alias: str
    alias_norm: str
    match_kind: str
    allow_surname_only: bool


def load_registry(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "allow_surname_only" in df:
        df["allow_surname_only"] = df["allow_surname_only"].str.lower().isin({"1", "true", "yes", "y"})
    else:
        df["allow_surname_only"] = False
    return df


def build_alias_records(registry: pd.DataFrame) -> list[AliasRecord]:
    records: list[AliasRecord] = []
    surname_counts = registry["canonical_name"].map(surname).value_counts().to_dict()
    for _, row in registry.iterrows():
        person_id = row["person_id"]
        canonical = row["canonical_name"]
        aliases = [a.strip() for a in str(row.get("aliases", "")).split(";") if a.strip()]
        if canonical not in aliases:
            aliases.insert(0, canonical)
        seen = set()
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if not alias_norm or alias_norm in seen:
                continue
            seen.add(alias_norm)
            is_surname = len(alias_norm.split()) == 1 and alias_norm == surname(canonical)
            allowed = bool(row.get("allow_surname_only", False)) and surname_counts.get(alias_norm, 0) == 1
            records.append(AliasRecord(
                person_id=person_id,
                canonical_name=canonical,
                alias=alias,
                alias_norm=alias_norm,
                match_kind="surname" if is_surname else ("canonical" if alias == canonical else "alias"),
                allow_surname_only=allowed,
            ))
    return records


def match_odonimo(odonimo: str, aliases: list[AliasRecord], fuzzy_threshold: int = 93) -> dict | None:
    norm = normalize_odonimo(odonimo, strip_honorifics=False)
    norm_no_title = normalize_odonimo(odonimo, strip_honorifics=True)
    variants = {norm, norm_no_title}

    best = None
    for rec in aliases:
        if rec.match_kind == "surname" and not rec.allow_surname_only:
            continue
        if rec.alias_norm in variants:
            score = 100
            method = f"exact_{rec.match_kind}"
        else:
            if rec.match_kind == "surname":
                continue
            sname = surname(rec.canonical_name)
            if sname and sname not in norm.split():
                continue
            score = max(ratio(rec.alias_norm, v) for v in variants if v)
            if score < fuzzy_threshold:
                continue
            method = "fuzzy_full_or_alias"
        candidate = {
            "person_id": rec.person_id,
            "canonical_name": rec.canonical_name,
            "matched_alias": rec.alias,
            "match_score": float(score),
            "match_method": method,
            "odonimo_normalized": norm,
        }
        if best is None or candidate["match_score"] > best["match_score"]:
            best = candidate
    return best


def match_dataframe(streets: pd.DataFrame, registry: pd.DataFrame, odonym_col: str,
                    fuzzy_threshold: int = 93) -> pd.DataFrame:
    aliases = build_alias_records(registry)
    rows = []
    for _, row in streets.iterrows():
        match = match_odonimo(str(row[odonym_col]), aliases, fuzzy_threshold=fuzzy_threshold)
        if match:
            out = row.to_dict()
            out.update(match)
            out["review_status"] = (
                "accepted_auto" if match["match_method"] in {"exact_canonical", "exact_alias"}
                else "needs_review"
            )
            rows.append(out)
    return pd.DataFrame(rows)
