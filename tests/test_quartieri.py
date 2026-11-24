import json

import pandas as pd
import pytest

from colonial_toponymy.quartieri import (
    detect_street_clusters,
    load_osm_quartieri,
    load_themed_districts,
    match_quartieri_dataframe,
    nearest_neighbourhood,
    normalize_quartiere_name,
)


def registry():
    return pd.DataFrame([
        {"person_id": "locatelli_antonio", "canonical_name": "Antonio Locatelli",
         "aliases": "Antonio Locatelli;Locatelli", "allow_surname_only": True, "entity_type": "person"},
        {"person_id": "place_istria", "canonical_name": "Istria", "aliases": "Istria",
         "allow_surname_only": False, "entity_type": "place"},
        {"person_id": "place_cirenaica", "canonical_name": "Cirenaica", "aliases": "Cirenaica",
         "allow_surname_only": False, "entity_type": "place"},
    ])


def entities(*names):
    return pd.DataFrame({"name": list(names), "site_kind": "quartiere"})


def test_normalize_strips_generic_words_and_articles():
    assert normalize_quartiere_name("Quartiere Istria") == "istria"
    assert normalize_quartiere_name("Rione dell'Istria") == "istria"
    assert normalize_quartiere_name("Villaggio Antonio Locatelli") == "antonio locatelli"


def test_place_named_neighbourhood_always_needs_review():
    m = match_quartieri_dataframe(entities("Istria", "Quartiere Cirenaica"), registry())
    assert set(m["person_id"]) == {"place_istria", "place_cirenaica"}
    assert (m["review_status"] == "needs_review").all()
    assert (m["match_method"] == "exact_canonical").all()


def test_person_exact_name_auto_accepted_bare_surname_only_review():
    m = match_quartieri_dataframe(entities("Quartiere Antonio Locatelli", "Locatelli", "Navigli"), registry())
    by_name = {r["name"]: r for r in m.to_dict("records")}
    assert set(by_name) == {"Quartiere Antonio Locatelli", "Locatelli"}
    assert by_name["Quartiere Antonio Locatelli"]["review_status"] == "accepted_auto"
    assert by_name["Quartiere Antonio Locatelli"]["person_id"] == "locatelli_antonio"
    assert by_name["Locatelli"]["review_status"] == "needs_review"


def test_address_name_is_not_a_neighbourhood():
    assert match_quartieri_dataframe(entities("Via Istria", "Piazza Cirenaica"), registry()).empty


def test_load_osm_quartieri_dedupes_and_assigns_comune(tmp_path):
    muni = pd.DataFrame({
        "municipality_belfiore": ["F205", "A794"], "municipality_istat": ["015146", "037006"],
        "municipality_name": ["Milano", "Bologna"], "region_name": ["Lombardia", "Emilia-Romagna"],
        "lon": [9.19, 11.34], "lat": [45.46, 44.49], "name_key": ["milano", "bologna"],
    })
    elements = [
        {"type": "node", "id": 1, "lat": 45.47, "lon": 9.2, "tags": {"name": "Istria", "place": "neighbourhood"}},
        {"type": "relation", "id": 2, "center": {"lat": 45.47, "lon": 9.2},
         "tags": {"name": "Quartiere Istria", "boundary": "administrative", "admin_level": "10"}},
        {"type": "node", "id": 3, "lat": 45.5, "lon": 9.1, "tags": {"place": "suburb"}},
    ]
    (tmp_path / "osm_quartieri_IT-25.json").write_text(json.dumps({"elements": elements}))
    out = load_osm_quartieri(tmp_path, muni)
    assert len(out) == 1
    assert out.iloc[0]["place_source_id"] == "node/1"
    assert out.iloc[0]["municipality_name"] == "Milano"
    assert nearest_neighbourhood(45.471, 9.201, out) == "Istria"
    assert nearest_neighbourhood(45.6, 9.201, out) == ""


def test_themed_districts_config_has_verified_sources():
    items = load_themed_districts("config/quartieri_tematici.yml")
    assert {"quartiere_africano_roma", "cirenaica_bologna"} <= {i["id"] for i in items}
    assert all(i["source_url"].startswith("https://") for i in items)


def test_themed_district_missing_source_is_rejected(tmp_path):
    p = tmp_path / "q.yml"
    p.write_text("quartieri:\n  - {id: x, name: X, comune: Roma, lat: 1, lon: 1, description: d}\n")
    with pytest.raises(ValueError):
        load_themed_districts(p)


def street(i, comune, lat, lon, name=None):
    return {"municipality_belfiore": comune, "odonimo": name or f"VIA {i}", "odonimo_normalized": (name or f"via {i}").lower(),
            "lat": str(lat), "lon": str(lon)}


def test_cluster_detection_on_synthetic_points():
    base_lat, base_lon = 41.93, 12.52
    # 6 streets within ~200 m, 4 streets 5 km away (too few), 5 streets in another comune
    rows = [street(i, "H501", base_lat + i * 0.0003, base_lon + i * 0.0003) for i in range(6)]
    rows += [street(10 + i, "H501", base_lat + 0.05 + i * 0.0003, base_lon) for i in range(4)]
    rows += [street(20 + i, "A944", base_lat, base_lon + i * 0.0003) for i in range(5)]
    df = pd.DataFrame(rows)
    clusters = detect_street_clusters(df, min_streets=5, radius_m=600)
    assert sorted((c["municipality_belfiore"], len(c["indices"])) for c in clusters) == [("A944", 5), ("H501", 6)]
    rome = next(c for c in clusters if c["municipality_belfiore"] == "H501")
    assert abs(rome["lat"] - (base_lat + 0.00075)) < 0.001
    assert rome["radius_m"] < 600


def test_cluster_counts_distinct_streets_only():
    rows = [street(i, "H501", 41.93, 12.52 + i * 0.0002, name="VIA ADUA") for i in range(6)]
    rows[0]["odonimo_normalized"] = "adua"
    for r in rows:
        r["odonimo_normalized"] = "adua"
    assert detect_street_clusters(pd.DataFrame(rows), min_streets=5) == []


def test_cluster_radius_splits_long_chain():
    # 12 streets along a line, 150 m apart (1.65 km): no single 600 m radius covers them, but two clusters do
    rows = [street(i, "H501", 41.93, 12.52 + i * 0.0018) for i in range(12)]
    clusters = detect_street_clusters(pd.DataFrame(rows), min_streets=5, radius_m=600)
    assert len(clusters) >= 1
    assert all(c["radius_m"] <= 600 for c in clusters)
