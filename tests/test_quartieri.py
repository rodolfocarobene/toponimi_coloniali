import io
import json
import zipfile

import pandas as pd
import pytest

from colonial_toponymy.quartieri import (
    combine_named_sources,
    detect_street_clusters,
    load_city_lists,
    load_istat_localita,
    load_osm_quartieri,
    load_themed_districts,
    match_quartieri_dataframe,
    nearest_neighbourhood,
    normalize_quartiere_name,
    utm32n_to_wgs84,
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


def muni_frame():
    return pd.DataFrame({
        "municipality_belfiore": ["F205", "A794"], "municipality_istat": ["015146", "037006"],
        "municipality_name": ["Milano", "Bologna"], "region_name": ["Lombardia", "Emilia-Romagna"],
        "lon": [9.19, 11.34], "lat": [45.46, 44.49], "name_key": ["milano", "bologna"],
    })


def test_utm32n_single_zone_conversion_matches_known_points():
    # ISTAT uses UTM 32N for the whole country: Lecce is far east of the zone (easting > 1,000,000 m)
    lon, lat = utm32n_to_wgs84([1279438.466, 403108.773], [4507699.639, 5023879.728])
    assert (lon[0], lat[0]) == pytest.approx((18.1726, 40.3546), abs=1e-3)
    assert (lon[1], lat[1]) == pytest.approx((7.7628, 45.3617), abs=1e-3)


def test_load_istat_localita_skips_case_sparse_and_assigns_comune(tmp_path):
    header = "COD_REG\tCOD_UTS\tPRO_COM\tLOC_ID\tLOC\tTIPO_LOC\tNOME\tCENTRO_CL\tALTITUDINE\tPOP21\tFAM21\tABI21\tEDI21\tPOINT_X\tPOINT_Y"
    rows = [
        "3\t215\t15146\t1\t1\t2\tVillaggio Dalmazia\t0\t120\t10\t5\t6\t3\t514000,5\t5034000,2",
        "3\t215\t15146\t2\t2\t4\tCase sparse\t0\t120\t10\t5\t6\t3\t514100,5\t5034100,2",
        "8\t237\t37006\t3\t3\t1\tCirenaica\t1\t50\t10\t5\t6\t3\t686000,0\t4930000,0",
    ]
    (tmp_path / "istat").mkdir()
    with zipfile.ZipFile(tmp_path / "istat" / "LocalitaPuntuali_21.zip", "w") as z:
        z.writestr("Localita/Localita_2021_Point.csv", "\r\n".join([header, *rows]).encode("cp1252"))
    out = load_istat_localita(tmp_path, muni_frame())
    assert sorted(out["name"]) == ["Cirenaica", "Villaggio Dalmazia"]
    row = out[out["name"] == "Villaggio Dalmazia"].iloc[0]
    assert (row["municipality_name"], row["region_name"]) == ("Milano", "Lombardia")
    assert row["site_detail"] == "Località ISTAT (nucleo abitato)"
    assert 9.0 < row["lon"] < 9.5 and 45.0 < row["lat"] < 46.0


def test_load_city_lists_milano_nil_and_bologna_zone(tmp_path):
    city = tmp_path / "citta"
    city.mkdir()
    square = {"type": "Polygon", "coordinates": [[[9.0, 45.0], [9.2, 45.0], [9.2, 45.2], [9.0, 45.2], [9.0, 45.0]]]}
    (city / "milano_nil.geojson").write_text(json.dumps(
        {"features": [{"geometry": square, "properties": {"NIL": "MACIACHINI - MAGGIOLINA"}}]}))
    (city / "bologna_aree-statistiche.json").write_text(json.dumps(
        [{"area_statistica": "CIRENAICA", "geo_point_2d": {"lon": 11.36, "lat": 44.49}}]))
    out = load_city_lists(tmp_path, muni_frame())
    assert set(out["name"]) == {"Maciachini - Maggiolina", "Cirenaica"}
    milano = out[out["municipality_name"] == "Milano"].iloc[0]
    assert (milano["lon"], milano["lat"]) == pytest.approx((9.1, 45.1))
    assert out[out["municipality_name"] == "Bologna"].iloc[0]["site_detail"] == "Elenco ufficiale: area statistica"


def test_combine_named_sources_prefers_first_source_per_comune_and_name():
    def frame(source, name, istat="015146"):
        return pd.DataFrame([{"place_source": source, "name": name, "municipality_istat": istat}])

    out = combine_named_sources(frame("city", "Istria"), frame("osm", "Quartiere Istria"),
                                frame("istat", "Istria", istat="037006"), frame("istat", "Istria"))
    assert list(out["place_source"]) == ["city", "istat"]  # same name, other comune, is kept
    assert list(out["municipality_istat"]) == ["015146", "037006"]
