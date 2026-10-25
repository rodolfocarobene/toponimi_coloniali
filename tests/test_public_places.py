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


def sin(names, reg=None):
    out = match_places_dataframe(pd.DataFrame({"name": names}), registry() if reg is None else reg, "name")
    return out


def test_surname_in_name_is_review_only():
    names = [
        "PRIMARIA LOCATELLI",
        "I.C. LOCATELLI-QUASIMODO",
        "SECON. I GR. LOCATELLI-ORIANI",
        "I.C. VIGONE - LOCATELLI",
        "BORGORICCO-LOCATELLI *",
        'BERGAMO "DONADONI" -LOCATELLI',
        'BRIGNANO G. D\'ADDA "LOCATELLI"',
        "LICEO SCIENTIFICO QUADRIENNALE LOCATELLI",
    ]
    out = sin(names)
    assert len(out) == len(names)
    assert set(out["person_id"]) == {"locatelli_antonio"}
    assert set(out["match_method"]) == {"surname_in_name"}
    assert set(out["review_status"]) == {"needs_review"}


def test_surname_in_name_negatives():
    for name in [
        "GIANNI LOCATELLI",
        "EMILIO LOCATELLI",
        "DON ANTONIO LOCATELLI",
        "E. LOCATELLI",
        "ZOGNO VIA LOCATELLI",
        "SCUOLA PRIMARIA VIA LOCATELLI",
        "I.C. LOCATELLI4",
    ]:
        assert sin([name]).empty, name


def test_surname_in_name_skips_excluded_ambiguous_and_places():
    reg = registry()
    extra = pd.DataFrame([
        {"person_id": "martini_ferdinando", "canonical_name": "Ferdinando Martini", "aliases": "Martini",
         "allow_surname_only": False, "entity_type": "person"},
        {"person_id": "rossi_a", "canonical_name": "Anna Rossetti", "aliases": "Rossetti",
         "allow_surname_only": False, "entity_type": "person"},
        {"person_id": "rossi_b", "canonical_name": "Carlo Rossetti", "aliases": "Rossetti",
         "allow_surname_only": False, "entity_type": "person"},
    ])
    reg = pd.concat([reg, extra], ignore_index=True)
    assert sin(["IC MARTINI"], reg).empty  # famous homonyms excluded
    assert sin(["IC ROSSETTI"], reg).empty  # surname shared by two registry people
    assert "surname_in_name" not in set(sin(["IC ADUA", "IC ADWA-AMBA ALAGI"], reg)["match_method"])


def test_surname_in_name_does_not_replace_stronger_match():
    out = sin(["IC ANTONIO LOCATELLI", "A. LOCATELLI"])
    assert set(out["match_method"]) == {"exact_canonical", "exact_initial_name"}


def test_german_institutional_words_are_stripped():
    assert normalize_place_name("Grundschule Antonio Locatelli") == "antonio locatelli"
    assert normalize_place_name("Mittelschule Locatelli") == "locatelli"
    assert normalize_place_name("Schulsprengel Bozen - Oberschule Locatelli") == "bozen oberschule locatelli"
    out = sin(["Grundschule Antonio Locatelli", "Oberschule LOCATELLI", "scuola primaria in lingua italiana di Laives \"Locatelli\""])
    assert len(out) == 3


def test_autonomous_schools_loader(tmp_path):
    from colonial_toponymy.public_sources import load_autonomous_schools

    (tmp_path / "scuole_TN_istituzioni_scolastiche_2014.xml").write_text(
        """<?xml version="1.0" encoding="ISO-8859-1"?>
<soggetti-formativi>
<istituzione-scolastica codiceOrigine="1" denominazione="IC Trento 1">
<tipologia-istituzione codiceOrigine="1" descrizione="Istituto comprensivo"/>
<sede codiceOrigine="9" descrizione="X"><comune codiceOrigine="1" descrizione="TRENTO"/></sede>
<unita-didattica codiceOrigine="10" denominazione="Scuola primaria F. Crispi">
<sede codiceOrigine="9" descrizione="X"><comune codiceOrigine="1" descrizione="TRENTO"/></sede>
</unita-didattica>
</istituzione-scolastica>
<istituzione-scolastica codiceOrigine="2" denominazione="Circolo di coordinamento n 1">
<tipologia-istituzione codiceOrigine="2" descrizione="Circolo di coordinamento pedagogico"/>
</istituzione-scolastica>
</soggetti-formativi>""",
        encoding="iso-8859-1",
    )
    (tmp_path / "wikidata_schools_bz_ao.csv").write_text(
        "item,itemLabel,istat\n"
        "http://www.wikidata.org/entity/Q1,Leo Santifaller,021008\n"
        "http://www.wikidata.org/entity/Q2,Q2,021008\n"
        "http://www.wikidata.org/entity/Q3,Primaria Aosta,007003\n"
    )
    muni = pd.DataFrame({
        "municipality_belfiore": ["L378", "A952", "A326"],
        "municipality_istat": ["022205", "021008", "007003"],
        "municipality_name": ["Trento", "Bolzano", "Aosta"],
        "region_name": ["Trentino-Alto Adige/Südtirol"] * 2 + ["Valle d'Aosta/Vallée d'Aoste"],
        "name_key": ["trento", "bolzano", "aosta"],
        "lon": [11.1, 11.3, 7.3], "lat": [46.0, 46.5, 45.7],
    })
    ents, totals = load_autonomous_schools(tmp_path, muni)
    assert sorted(ents["name"]) == ["IC Trento 1", "Leo Santifaller", "Primaria Aosta", "Scuola primaria F. Crispi"]
    assert totals["Trentino-Alto Adige/Südtirol"] == 2  # 1 unit of IC Trento 1 + Santifaller
    assert totals["Valle d'Aosta/Vallée d'Aoste"] == 1
