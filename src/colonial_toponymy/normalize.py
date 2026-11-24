from __future__ import annotations

import re
import unicodedata

ROAD_PREFIXES = {
    "via", "viale", "piazza", "piazzale", "corso", "largo", "vicolo", "vico", "strada",
    "contrada", "salita", "discesa", "lungomare", "lungarno", "rotonda", "borgo",
    "galleria", "passaggio", "passeggiata", "riva", "calle", "campo", "fondamenta",
}
# Preposizioni articolate tra prefisso e nome: "VIA DELL'AMBA ARADAM", "PIAZZA DEI CINQUECENTO".
ARTICLES = {"di", "d'", "del", "dello", "della", "dell'", "dei", "degli", "delle", "dal", "dalla"}
HONORIFICS = {
    "generale", "gen", "maresciallo", "ammiraglio", "colonnello", "tenente", "maggiore",
    "capitano", "onorevole", "senatore", "conte", "duca", "principe", "padre", "frate",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize_text(text: str) -> str:
    text = strip_accents(str(text or "")).lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    # ANNCSU scrive l'accento finale come apostrofo: "MACALLE'" = "Macallè".
    text = re.sub(r"(?<=[a-z])'(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_odonimo(text: str, strip_honorifics: bool = False) -> str:
    norm = normalize_text(text)
    tokens = norm.split()
    while tokens and tokens[0] in ROAD_PREFIXES:
        tokens.pop(0)
    if tokens and tokens[0] != norm.split()[0]:
        tokens = _strip_leading_article(tokens)
    if strip_honorifics:
        while tokens and tokens[0] in HONORIFICS:
            tokens.pop(0)
    return " ".join(tokens)


def _strip_leading_article(tokens: list[str]) -> list[str]:
    first = tokens[0]
    if first in ARTICLES:
        return tokens[1:]
    for art in ("dell'", "d'"):
        if first.startswith(art) and len(first) > len(art):
            return [first[len(art):]] + tokens[1:]
    return tokens


def surname(name: str) -> str:
    tokens = normalize_text(name).split()
    return tokens[-1] if tokens else ""
