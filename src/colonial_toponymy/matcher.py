from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
    entity_type: str = "person"
    canonical_norm: str = ""


def load_registry(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "allow_surname_only" in df:
        df["allow_surname_only"] = df["allow_surname_only"].str.lower().isin({"1", "true", "yes", "y"})
    else:
        df["allow_surname_only"] = False
    return df


def load_authorities(people_path: str, places_path: str | None) -> pd.DataFrame:
    people = load_registry(people_path)
    if "entity_type" not in people:
        people["entity_type"] = "person"
    else:
        people["entity_type"] = people["entity_type"].replace("", "person")

    frames = [people]
    if places_path:
        p = Path(places_path)
        if p.exists():
            places = load_registry(p)
            if "entity_type" not in places:
                places["entity_type"] = "place"
            else:
                places["entity_type"] = places["entity_type"].replace("", "place")
            frames.append(places)
        else:
            print(f"Warning: place/battle registry not found: {p}")

    registry = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    if registry.duplicated(["person_id", "canonical_name"]).any():
        dup = registry.loc[
            registry.duplicated(["person_id", "canonical_name"], keep=False),
            ["person_id", "canonical_name"],
        ]
        raise ValueError(f"Duplicate authority identifiers:\n{dup.to_string(index=False)}")
    return registry


def build_alias_records(registry: pd.DataFrame) -> list[AliasRecord]:
    records: list[AliasRecord] = []
    person_mask = (
        registry["entity_type"].replace("", "person").eq("person")
        if "entity_type" in registry
        else pd.Series(True, index=registry.index)
    )
    surname_counts = registry.loc[person_mask, "canonical_name"].map(surname).value_counts().to_dict()

    for _, row in registry.iterrows():
        person_id = row["person_id"]
        canonical = row["canonical_name"]
        entity_type = str(row.get("entity_type", "person") or "person")
        aliases = [a.strip() for a in str(row.get("aliases", "")).split(";") if a.strip()]
        if canonical not in aliases:
            aliases.insert(0, canonical)
        seen = set()
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if not alias_norm or alias_norm in seen:
                continue
            seen.add(alias_norm)

            # A one-word canonical place name (Libia, Adua, Dogali, Asmara...) is a
            # complete authority label, not a surname-only person match.
            is_surname = (
                entity_type == "person"
                and len(alias_norm.split()) == 1
                and alias_norm == surname(canonical)
            )
            allowed = (
                is_surname
                and bool(row.get("allow_surname_only", False))
                and surname_counts.get(alias_norm, 0) == 1
            )
            records.append(
                AliasRecord(
                    person_id=person_id,
                    canonical_name=canonical,
                    alias=alias,
                    alias_norm=alias_norm,
                    match_kind=(
                        "surname"
                        if is_surname
                        else ("canonical" if alias == canonical else "alias")
                    ),
                    allow_surname_only=allowed,
                    entity_type=entity_type,
                    canonical_norm=normalize_text(canonical),
                )
            )
    return records


def initials_match(norm: str, rec: AliasRecord) -> bool:
    """True for 'a locatelli' vs 'antonio locatelli': leading initials plus the rest of the full name."""
    if rec.entity_type != "person":
        return False
    tokens = norm.split()
    k = 0
    while k < len(tokens) and len(tokens[k]) == 1 and tokens[k].isalpha():
        k += 1
    canon = rec.canonical_norm.split()
    if k == 0 or len(canon) <= k:
        return False
    return [t[0] for t in canon[:k]] == tokens[:k] and canon[k:] == tokens[k:]


def match_odonimo(
    odonimo: str,
    aliases: list[AliasRecord],
    fuzzy_threshold: int = 93,
    normalizer: Callable[..., str] = normalize_odonimo,
    allow_initials: bool = False,
) -> dict | None:
    norm = normalizer(odonimo, strip_honorifics=False)
    norm_no_title = normalizer(odonimo, strip_honorifics=True)
    variants = {norm, norm_no_title}

    best = None
    for rec in aliases:
        if allow_initials and rec.match_kind == "canonical" and initials_match(norm_no_title, rec):
            candidate = {
                "person_id": rec.person_id,
                "canonical_name": rec.canonical_name,
                "matched_alias": rec.alias,
                "match_score": 97.0,
                "match_method": "exact_initial_name",
                "odonimo_normalized": norm,
            }
            if best is None or candidate["match_score"] > best["match_score"]:
                best = candidate
            continue
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


def match_dataframe(
    streets: pd.DataFrame,
    registry: pd.DataFrame,
    odonym_col: str,
    fuzzy_threshold: int = 93,
) -> pd.DataFrame:
    aliases = build_alias_records(registry)
    rows = []
    for _, row in streets.iterrows():
        match = match_odonimo(str(row[odonym_col]), aliases, fuzzy_threshold=fuzzy_threshold)
        if match:
            out = row.to_dict()
            out.update(match)
            out["review_status"] = (
                "accepted_auto"
                if match["match_method"] in {"exact_canonical", "exact_alias"}
                else "needs_review"
            )
            rows.append(out)
    return pd.DataFrame(rows)
