import pandas as pd

from colonial_toponymy.matcher import build_alias_records, match_odonimo
from colonial_toponymy.normalize import normalize_odonimo


def registry():
    return pd.DataFrame([
        {"person_id": "badoglio", "canonical_name": "Pietro Badoglio", "aliases": "Pietro Badoglio;Badoglio", "allow_surname_only": True},
        {"person_id": "martini", "canonical_name": "Ferdinando Martini", "aliases": "Ferdinando Martini;Martini", "allow_surname_only": False},
    ])


def test_normalize_road_prefix():
    assert normalize_odonimo("Via Generale Pietro Badoglio") == "generale pietro badoglio"


def test_exact_full_name_with_honorific():
    aliases = build_alias_records(registry())
    m = match_odonimo("Via Generale Pietro Badoglio", aliases)
    assert m is not None
    assert m["person_id"] == "badoglio"


def test_surname_allowed_only_when_enabled():
    aliases = build_alias_records(registry())
    assert match_odonimo("Via Badoglio", aliases)["person_id"] == "badoglio"
    assert match_odonimo("Via Martini", aliases) is None
