from __future__ import annotations

import re
import unicodedata

ROAD_PREFIXES = {
    "via", "viale", "piazza", "piazzale", "corso", "largo", "vicolo", "strada",
    "contrada", "salita", "discesa", "lungomare", "lungarno", "rotonda", "borgo",
    "galleria", "passaggio", "passeggiata", "riva", "calle", "campo", "fondamenta",
}
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
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_odonimo(text: str, strip_honorifics: bool = False) -> str:
    norm = normalize_text(text)
    tokens = norm.split()
    while tokens and tokens[0] in ROAD_PREFIXES:
        tokens.pop(0)
    if strip_honorifics:
        while tokens and tokens[0] in HONORIFICS:
            tokens.pop(0)
    return " ".join(tokens)


def surname(name: str) -> str:
    tokens = normalize_text(name).split()
    return tokens[-1] if tokens else ""
