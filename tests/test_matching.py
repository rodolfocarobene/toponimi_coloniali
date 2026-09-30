import pandas as pd

from colonial_toponymy.matcher import build_alias_records, match_odonimo
from colonial_toponymy.normalize import normalize_odonimo


def registry():
    return pd.DataFrame([
        {
            "person_id": "badoglio",
            "canonical_name": "Pietro Badoglio",
            "aliases": "Pietro Badoglio;Badoglio",
            "allow_surname_only": True,
            "entity_type": "person",
        },
        {
            "person_id": "martini",
            "canonical_name": "Ferdinando Martini",
            "aliases": "Ferdinando Martini;Martini",
            "allow_surname_only": False,
            "entity_type": "person",
        },
        {
            "person_id": "place_libia",
            "canonical_name": "Libia",
            "aliases": "Libia",
            "allow_surname_only": False,
            "entity_type": "place",
        },
        {
            "person_id": "place_adua",
            "canonical_name": "Adua",
            "aliases": "Adua;Adwa",
            "allow_surname_only": False,
            "entity_type": "place",
        },
        {
            "person_id": "place_amba_aradam",
            "canonical_name": "Amba Aradam",
            "aliases": "Amba Aradam;Amba-Aradam",
            "allow_surname_only": False,
            "entity_type": "place",
        },
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


def test_single_word_place_is_not_treated_as_surname():
    aliases = build_alias_records(registry())
    assert match_odonimo("Largo Libia", aliases)["person_id"] == "place_libia"
    assert match_odonimo("Via Adua", aliases)["person_id"] == "place_adua"


def test_multiword_battle_place_matches_after_road_prefix():
    aliases = build_alias_records(registry())
    match = match_odonimo("Corso Amba Aradam", aliases)
    assert match is not None
    assert match["person_id"] == "place_amba_aradam"
    assert match["match_method"] == "exact_canonical"
