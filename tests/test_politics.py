import pytest

from colonial_toponymy.politics import classify_lists, load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules("config/party_families.yml")


@pytest.mark.parametrize("raw,expected", [
    ("FORZA ITALIA | FRATELLI D'ITALIA | LEGA | INSIEME PER ROMA", "centrodestra"),
    ("FRATELLI D'ITALIA GIORGIA MELONI", "centrodestra"),
    ("PARTITO DEMOCRATICO | ALLEANZA VERDI E SINISTRA | CIVICA X", "centrosinistra"),
    ("PARTITO DEMOCRATICO | ITALIA VIVA | AZIONE", "centrosinistra"),
    ("MOVIMENTO 5 STELLE | PROGETTO COMUNE", "m5s"),
    ("MOVIMENTO 5 STELLE | PARTITO DEMOCRATICO", "centrosinistra"),
    ("LEGA | PARTITO DEMOCRATICO", "altro"),
    ("SUEDTIROLER VOLKSPARTEI (SVP)", "altro"),
    ("INSIEME PER IL FUTURO | AZIONE CIVICA", "civica"),
    ("LEGAMBIENTE PER IL TERRITORIO", "civica"),
    ("UNIONE DI CENTROSINISTRA | CIVICA X", "centrosinistra"),
    ("- Lista non Pervenuta -", "n.d."),
    ("", "n.d."),
    (None, "n.d."),
])
def test_classify_lists(rules, raw, expected):
    assert classify_lists(raw, rules) == expected
