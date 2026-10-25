"""Matching of names of public places (schools, universities, libraries...) against the registry.

Streets are matched by `matcher.match_dataframe` after stripping road prefixes (via, piazza...).
Public places need the same idea with institutional prefixes (istituto comprensivo, liceo
scientifico, scuola primaria...) and a few extra cautions:

* a name that still starts with a road prefix is an address-based name ("SCUOLA VIA ADUA"),
  not a dedication, and is never matched;
* "A. LOCATELLI" (initial + surname) is only a review candidate;
* places/battles (Libia, Adua...) are never auto-accepted: a school in Via Adua is not named "Adua".
"""
from __future__ import annotations

import re

import pandas as pd

from .matcher import build_alias_records, match_odonimo
from .normalize import HONORIFICS, ROAD_PREFIXES, normalize_text, surname

ACRONYMS = {
    "ic", "ics", "ico", "iis", "isis", "isi", "iti", "itis", "itc", "itcg", "itg", "ita", "itn", "itt",
    "ipsia", "ipsar", "ipsss", "ipsc", "ipc", "ips", "ipia", "ipaa", "ipseoa", "ipsasr", "ist", "sms",
    "smsi", "sm", "sip", "smi", "cpia", "cfp", "ipi", "ite", "iss", "isa", "ipsct", "dd", "cd", "sec",
    "elem", "ssi", "ssg", "ssp",
}
# Single letters are never listed here: a leading "A." or "E." is an initial, not a conjunction.
INSTITUTION_WORDS = {
    "istituto", "istituti", "comprensivo", "comprensiva", "statale", "statali", "paritario", "paritaria",
    "parificata", "parificato", "non", "scuola", "scuole", "infanzia", "dell'infanzia", "materna",
    "dell'obbligo", "primaria", "primarie", "elementare", "elementari", "media", "medie", "secondaria",
    "grado", "primo", "secondo", "ii", "liceo", "scientifico", "classico", "linguistico", "artistico",
    "musicale", "coreutico", "scienze", "umane", "magistrale", "tecnico", "tecnica", "professionale",
    "industriale", "commerciale", "agrario", "aeronautico", "nautico", "alberghiero", "superiore",
    "direzione", "didattica", "didattico", "circolo", "convitto", "nazionale", "educandato", "provinciale",
    "istruzione", "adulti", "formazione", "professionali", "d'arte", "d'istruzione", "dell'istruzione",
    "sede", "plesso", "succursale", "sezione", "staccata", "associata", "coordinata", "ex",
    "pluricomprensivo", "polo", "paritari", "libera", "libero", "asilo", "nido", "infantile",
    "aula", "aule", "magna", "consiliare", "conferenze", "riunioni", "sala", "sale", "auditorium", "biblioteca", "teatro", "cinema", "palazzetto",
    "palasport", "stadio", "ospedale", "caserma", "parco", "giardino", "giardini", "centro", "comunale",
    "civica", "civico", "museo", "palazzo", "municipio", "universita", "collegio", "residenza",
    "dipartimento", "facolta", "aeroporto", "casa", "campo", "sportivo", "piscina", "sportiva",
    "polisportivo", "intitolata", "intitolato", "dedicata", "dedicato", "universitario", "universitaria",
    "studentesca", "studentato", "quadriennale",
    # lingua tedesca/ladina (Bolzano): Grundschule, Mittelschule, Oberschule...
    "grundschule", "mittelschule", "oberschule", "schule", "schulsprengel", "sprengel", "gymnasium",
    "realgymnasium", "lyzeum", "handelsoberschule", "fachoberschule", "berufsschule", "landesberufsschule",
    "fachschule", "kindergarten", "kindergarten", "schulzentrum", "schulstelle", "und", "fur", "lingua",
    "italiana", "tedesca", "ladina", "in", "scola", "elementara", "mesana", 
    "per", "di", "del", "della", "dello", "dei", "degli", "delle", "dell", "ed", "il", "la", "lo", "le",
    "gli", "in", "al", "alla", "allo", "ai", "agli", "alle", "da",
}
# Titles that precede a person's name in dedications. "don" and "san" are deliberately absent:
# "Don Antonio Locatelli" is a different person from "Antonio Locatelli".
EXTRA_TITLES = {"prof", "professor", "professore", "dott", "ing", "avv", "cav", "comm", "on", "sen"}
TRAILING_WORDS = {
    "scuola", "primaria", "infanzia", "elementare", "media", "secondaria", "sede", "plesso", "succursale",
    "statale", "paritaria", "grado", "primo", "secondo", "ic", "istituto", "comprensivo", "liceo",
}

_DOTTED = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_PAREN = re.compile(r"\([^)]*\)")
_QUOTED = re.compile(r"[\"“”«»]([^\"“”«»]{3,})[\"“”«»]|(?<![\w])'([^']{3,})'(?![\w])")
_SEG_SPLIT = re.compile(r"[\"“”«»]|(?<![\w])'|'(?![\w])|\s*[-–—/,;*]\s*")
_SPLIT = re.compile(r"\s[-–—/]\s|\s*[,;]\s*|\s*\*\s*")


def _collapse_acronyms(raw: str) -> str:
    def repl(m: re.Match) -> str:
        collapsed = m.group(0).replace(".", "")
        return collapsed if collapsed.lower() in ACRONYMS else m.group(0)

    return _DOTTED.sub(repl, raw)


def normalize_place_name(text: str, strip_honorifics: bool = False) -> str:
    """Normalize a school/university/place name: drop leading and trailing institutional words.

    Road prefixes are intentionally kept so address-based names never equal a registry alias.
    """
    tokens = normalize_text(_collapse_acronyms(_PAREN.sub(" ", str(text or "")))).split()
    tokens = [t for t in (t.strip("'") for t in tokens) if t]
    leading = INSTITUTION_WORDS | ACRONYMS
    while tokens and tokens[0] in leading:
        tokens.pop(0)
    while tokens and tokens[-1] in TRAILING_WORDS:
        tokens.pop()
    if strip_honorifics:
        titles = HONORIFICS | EXTRA_TITLES
        while tokens and tokens[0] in titles:
            tokens.pop(0)
    return " ".join(tokens)


def name_variants(raw: str) -> list[str]:
    """Candidate strings for one official name: the whole name, quoted parts, ' - ' separated parts."""
    raw = _collapse_acronyms(str(raw or ""))
    variants = [raw]
    for m in _QUOTED.finditer(raw):
        variants.append(m.group(1) or m.group(2))
    variants.extend(p for p in _SPLIT.split(_PAREN.sub(" ", raw)) if p and p.strip())
    seen, out = set(), []
    for v in variants:
        key = v.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def is_address_name(norm: str) -> bool:
    first = norm.split()[0] if norm else ""
    return first in ROAD_PREFIXES


def match_place_name(raw: str, aliases, fuzzy_threshold: int = 93) -> dict | None:
    best = None
    for variant in name_variants(raw):
        if is_address_name(normalize_place_name(variant)):
            continue
        m = match_odonimo(
            variant,
            aliases,
            fuzzy_threshold=fuzzy_threshold,
            normalizer=normalize_place_name,
            allow_initials=True,
        )
        if m and (best is None or m["match_score"] > best["match_score"]):
            m["matched_text"] = variant
            best = m
    return best


# Segment-leading tokens that are not part of a dedication ("SECON. I GR. LOCATELLI-ORIANI").
SEGMENT_NOISE = {"secon", "gr", "i", "iii", "iv", "sup", "inf", "1", "2", "3"}
# Surnames excluded from the surname_in_name tier (judged on the MIM data, see README):
SURNAME_IN_NAME_EXCLUDED = {
    # also the name of a comune or locality: "CANEVA - SARONE", "SM SCALEA", "BONO", "GALLIANO-ROSSINI"
    "aosta", "bono", "caneva", "lessona", "orero", "scalea", "galliano", "saletta",
    # homonyms far more famous or more common than the registry person (Aristide Gabelli, Alessandro
    # Antonelli, Cesare Balbo...): a bare surname is almost never the colonial figure
    "gabelli", "martini", "antonelli", "giuliani", "bertolini", "gasparini", "gandolfi", "nasi",
    "martino", "vecchi", "balbo", "volpi", "tassoni", "raggi", "rava", "feo", "zoli", "lucchese",
    "pintor", "corni", "mombelli",
}


def surname_in_name_index(registry: pd.DataFrame, excluded: set[str] | None = None) -> dict[str, dict]:
    """surname -> person, for registry persons with a unique single-token surname."""
    excluded = SURNAME_IN_NAME_EXCLUDED if excluded is None else excluded
    persons = registry[registry["entity_type"].replace("", "person").eq("person")]
    by_surname: dict[str, list] = {}
    for _, row in persons.iterrows():
        sname = surname(row["canonical_name"])
        if len(sname) >= 4 and sname not in excluded:
            by_surname.setdefault(sname, []).append(row)
    # A surname shared by 2+ registry people cannot be attributed to one of them: skipped.
    return {s: {"person_id": r[0]["person_id"], "canonical_name": r[0]["canonical_name"]}
            for s, r in by_surname.items() if len(r) == 1}


def segments(raw: str) -> list[str]:
    """Name segments: split on quotes, hyphens (with or without spaces), slashes, commas, stars."""
    text = _collapse_acronyms(_PAREN.sub(" ", str(raw or "")))
    return [p for p in _SEG_SPLIT.split(text) if p and p.strip()]


def match_surname_in_name(raw: str, index: dict[str, dict]) -> dict | None:
    """Review-only tier: a registry surname that is a whole segment of the name once institutional
    words are stripped ("PRIMARIA LOCATELLI", "I.C. LOCATELLI-QUASIMODO"). Never when a first name,
    initial or title accompanies the surname, nor for address names."""
    for seg in segments(raw):
        norm = normalize_place_name(seg)
        tokens = norm.split()
        while tokens and tokens[0] in SEGMENT_NOISE:
            tokens.pop(0)
        if len(tokens) != 1 or tokens[0] not in index:
            continue
        if is_address_name(normalize_text(seg)):
            continue
        person = index[tokens[0]]
        return {
            **person,
            "matched_alias": tokens[0].title(),
            "match_score": 90.0,
            "match_method": "surname_in_name",
            "odonimo_normalized": norm,
            "matched_text": seg.strip(),
        }
    return None


def match_places_dataframe(
    places: pd.DataFrame,
    registry: pd.DataFrame,
    name_col: str,
    fuzzy_threshold: int = 93,
    surname_in_name: bool = True,
) -> pd.DataFrame:
    """Like matcher.match_dataframe, for public-place names. Same review rules, plus: place/battle
    entries and initial+surname forms are never auto-accepted; the surname_in_name tier (surname as
    a standalone segment) is a fallback, always needs_review."""
    aliases = build_alias_records(registry)
    sin_index = surname_in_name_index(registry) if surname_in_name else {}
    entity_type = dict(zip(registry["person_id"], registry["entity_type"]))
    rows = []
    for _, row in places.iterrows():
        match = match_place_name(str(row[name_col]), aliases, fuzzy_threshold=fuzzy_threshold)
        if not match and sin_index:
            match = match_surname_in_name(str(row[name_col]), sin_index)
        if not match:
            continue
        out = row.to_dict()
        out.update(match)
        auto = (
            match["match_method"] in {"exact_canonical", "exact_alias"}
            and entity_type.get(match["person_id"], "person") == "person"
        )
        out["review_status"] = "accepted_auto" if auto else "needs_review"
        rows.append(out)
    return pd.DataFrame(rows)
