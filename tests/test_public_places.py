import pandas as pd

from colonial_toponymy.matcher import build_alias_records
from colonial_toponymy.places import (
    match_place_name,
    match_places_dataframe,
    normalize_place_name,
)


def registry():
    return pd.DataFrame([
        {
            "person_id": "locatelli_antonio",
            "canonical_name": "Antonio Locatelli",
            "aliases": "Antonio Locatelli;Locatelli",
            "allow_surname_only": False,
            "entity_type": "person",
        },
        {
            "person_id": "badoglio_pietro",
            "canonical_name": "Pietro Badoglio",
            "aliases": "Pietro Badoglio;Badoglio",
            "allow_surname_only": True,
            "entity_type": "person",
        },
        {
            "person_id": "place_adua",
            "canonical_name": "Adua",
            "aliases": "Adua;Adwa",
            "allow_surname_only": False,
            "entity_type": "place",
        },
        {
            "person_id": "place_amba_alagi",
            "canonical_name": "Amba Alagi",
            "aliases": "Amba Alagi",
            "allow_surname_only": False,
            "entity_type": "place",
        },
    ])


def match(name):
    return match_place_name(name, build_alias_records(registry()))


def test_institutional_prefix_is_stripped():
    assert normalize_place_name("I.C. ANTONIO LOCATELLI") == "antonio locatelli"
    assert normalize_place_name("ISTITUTO COMPRENSIVO STATALE 'ANTONIO LOCATELLI'") == "antonio locatelli"
    assert normalize_place_name("LICEO SCIENTIFICO STATALE Antonio Locatelli - sede") == "antonio locatelli"


def test_locatelli_school_full_name_is_accepted():
    for name in [
        "ANTONIO LOCATELLI",
        "I.C. ANTONIO LOCATELLI",
        'IST.TEC. AERONAUTICO "ANTONIO LOCATELLI"',
        "SCUOLA PRIMARIA ANTONIO LOCATELLI - BERGAMO",
    ]:
        m = match(name)
        assert m is not None, name
        assert m["person_id"] == "locatelli_antonio"
        assert m["match_method"] == "exact_canonical"


def test_prefixed_name_in_dataframe_is_auto_accepted():
    schools = pd.DataFrame({"name": ["ISTITUTO COMPRENSIVO 'ANTONIO LOCATELLI'", "I.C. ROMA 1"]})
    out = match_places_dataframe(schools, registry(), "name")
    assert len(out) == 1
    assert out.iloc[0]["review_status"] == "accepted_auto"


def test_initial_and_surname_needs_review():
    for name in ["A. LOCATELLI", 'COVO "A.LOCATELLI"', "ISTITUTO COMPRENSIVO 'A. LOCATELLI'"]:
        m = match(name)
        assert m["person_id"] == "locatelli_antonio"
        assert m["match_method"] == "exact_initial_name"
    out = match_places_dataframe(pd.DataFrame({"name": ["A.LOCATELLI"]}), registry(), "name")
    assert out.iloc[0]["review_status"] == "needs_review"


def test_wrong_initial_or_surname_only_is_not_matched():
    assert match("B. LOCATELLI") is None
    assert match("I.C. LOCATELLI") is None  # surname-only not allowed for Locatelli
    assert match("DON ANTONIO LOCATELLI") is None  # a different person (priest)
    assert match("GIANNI LOCATELLI") is None


def test_surname_only_when_allowed_is_review_not_auto():
    out = match_places_dataframe(pd.DataFrame({"name": ["IC BADOGLIO"]}), registry(), "name")
    assert out.iloc[0]["match_method"] == "exact_surname"
    assert out.iloc[0]["review_status"] == "needs_review"


def test_address_based_school_names_are_false_positives():
    assert match("SCUOLA PRIMARIA VIA ADUA") is None
    assert match("VIA ANTONIO LOCATELLI") is None
    assert match("ZOGNO VIA LOCATELLI") is None


def test_place_registry_entry_is_never_auto_accepted():
    out = match_places_dataframe(
        pd.DataFrame({"name": ["SCUOLA PRIMARIA ADUA", "IC AMBA ALAGI"]}), registry(), "name"
    )
    assert set(out["person_id"]) == {"place_adua", "place_amba_alagi"}
    assert set(out["review_status"]) == {"needs_review"}


def test_unrelated_school_names_do_not_match():
    for name in ["LICEO CLASSICO DANTE ALIGHIERI", "IC ROMA 1", "SCUOLA INFANZIA ANNA FRANK"]:
        assert match(name) is None
