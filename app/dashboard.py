from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Toponimi coloniali italiani", layout="wide")
st.title("Toponimi italiani legati al colonialismo")
st.caption(
    "Dashboard di ricerca. Una corrispondenza indica che l'odonimo è associato a una figura "
    "presente nel registro curato; non dimostra, da sola, che il comune abbia scelto il nome "
    "specificamente per celebrarne il ruolo coloniale."
)

ROLE_LABELS = {
    "military": "Militare",
    "political": "Politico",
    "administration": "Amministrazione coloniale",
    "political_and_administration": "Politica e amministrazione coloniale",
    "military_and_administration": "Militare e amministrazione coloniale",
    "military_political_administration": "Militare, politica e amministrazione coloniale",
    "military_and_religious": "Militare e religioso",
    "economic": "Economia e impresa",
    "cultural_or_scientific": "Cultura o scienza",
    "religious": "Religioso",
    "exploration_geography": "Esplorazione e geografia",
    "propaganda_or_advocacy": "Propaganda e promozione coloniale",
}

TERRITORY_LABELS = {
    "Libya": "Libia",
    "Eritrea": "Eritrea",
    "Ethiopia": "Etiopia",
    "Somalia": "Somalia",
    "Italian East Africa": "Africa Orientale Italiana",
    "Dodecanese": "Dodecaneso",
    "Albania": "Albania",
}

COLUMN_LABELS = {
    "odonimo": "Odonimo",
    "municipality_name": "Comune",
    "province_name": "Provincia",
    "region_name": "Regione",
    "canonical_name": "Figura",
    "role_category": "Ruolo",
    "territories": "Territori coloniali",
    "match_method": "Metodo di corrispondenza",
    "match_score": "Punteggio",
    "review_status": "Stato revisione",
    "source_url": "Fonte",
    "named_year": "Anno di intitolazione",
    "removed_year": "Anno di rimozione",
}


def role_label(value: str) -> str:
    return ROLE_LABELS.get(value, value.replace("_", " ").capitalize())


def territory_label(value: str) -> str:
    return TERRITORY_LABELS.get(value, value)


DEFAULTS = [
    Path("data/processed/dashboard_data.parquet"),
    Path("data/processed/street_matches_geocoded.parquet"),
    Path("data/processed/street_matches.parquet"),
]
path = next((p for p in DEFAULTS if p.exists()), None)
if path is None:
    st.info("Nessun dato elaborato trovato. Esegui gli script 02 → 03 → 04 → 05 dalla radice del progetto.")
    st.stop()

df = pd.read_parquet(path).fillna("")
if "match_score" in df:
    df["match_score_num"] = pd.to_numeric(df["match_score"], errors="coerce")

figure_options = sorted(x for x in df.get("canonical_name", pd.Series(dtype=str)).unique() if x)

with st.sidebar:
    st.header("Filtri")
    selected_figures = st.multiselect(
        "Mostra solo queste figure",
        figure_options,
        help="Selezionando uno o più nomi vengono mantenuti soltanto gli odonimi associati a queste figure.",
    )
    excluded_figures = st.multiselect(
        "Escludi queste figure",
        figure_options,
        help="Le figure selezionate qui vengono rimosse da statistiche, grafici e mappa. L'esclusione ha precedenza sull'inclusione.",
    )
    if selected_figures:
        df = df[df["canonical_name"].isin(selected_figures)]
    if excluded_figures:
        df = df[~df["canonical_name"].isin(excluded_figures)]

    accepted_only = st.checkbox("Solo corrispondenze accettate", value=True)
    if accepted_only and "review_status" in df:
        df = df[df["review_status"].isin(["accepted_auto", "accepted_manual"])]

    regions = sorted(x for x in df.get("region_name", pd.Series(dtype=str)).unique() if x)
    selected_regions = st.multiselect("Regioni", regions)
    if selected_regions:
        df = df[df["region_name"].isin(selected_regions)]

    roles = sorted(x for x in df.get("role_category", pd.Series(dtype=str)).unique() if x)
    selected_roles = st.multiselect("Categorie di ruolo", roles, format_func=role_label)
    if selected_roles:
        df = df[df["role_category"].isin(selected_roles)]

    territory_options = sorted({t.strip() for s in df.get("territories", pd.Series(dtype=str)) for t in str(s).split(";") if t.strip()})
    selected_territories = st.multiselect("Territori coloniali", territory_options, format_func=territory_label)
    if selected_territories:
        df = df[df["territories"].map(lambda s: any(t in str(s).split(";") for t in selected_territories))]

    st.divider()
    registry_snapshot = Path("data/processed/people_registry_used.csv")
    if registry_snapshot.exists():
        st.download_button(
            "Scarica il registro dei nomi usato per il matching",
            registry_snapshot.read_bytes(),
            file_name="registro_nomi_utilizzato.csv",
            mime="text/csv",
            help="Copia esatta del registro usato dallo script 03 nell'ultima esecuzione del matching.",
            use_container_width=True,
        )
    else:
        st.caption("Esegui nuovamente lo script 03 per creare la copia esatta del registro usato nel matching.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Odonimi trovati", f"{len(df):,}")
c2.metric("Comuni", f"{df.get('municipality_belfiore', pd.Series(dtype=str)).nunique():,}")
c3.metric("Figure rappresentate", f"{df.get('person_id', pd.Series(dtype=str)).nunique():,}")
c4.metric("Regioni", f"{df.get('region_name', pd.Series(dtype=str)).nunique():,}")

st.subheader("Differenze regionali")
metric_labels = {
    "Odonimi trovati (valore assoluto)": "absolute",
    "Per 10.000 odonimi ANNCSU": "normalized",
    "Comuni con almeno una corrispondenza": "municipalities",
}
metric_label = st.radio("Metrica", list(metric_labels), horizontal=True)
metric = metric_labels[metric_label]
if metric == "absolute":
    regional = df.groupby("region_name").size().reset_index(name="value")
elif metric == "normalized" and "total_odonimi_region" in df:
    regional = df.groupby("region_name").agg(matches=("progressivo_odonimo", "size"), total=("total_odonimi_region", "first")).reset_index()
    regional["total"] = pd.to_numeric(regional["total"], errors="coerce")
    regional["value"] = 10_000 * regional["matches"] / regional["total"]
else:
    regional = df.groupby("region_name")["municipality_belfiore"].nunique().reset_index(name="value")
regional = regional[regional["region_name"] != ""].sort_values("value")
st.plotly_chart(px.bar(regional, x="value", y="region_name", orientation="h", labels={"value": metric_label, "region_name": "Regione"}), use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Figure più rappresentate")
    top = df.groupby("canonical_name").size().nlargest(20).sort_values().reset_index(name="odonimi")
    st.plotly_chart(px.bar(top, x="odonimi", y="canonical_name", orientation="h", labels={"canonical_name": "Figura", "odonimi": "Odonimi"}), use_container_width=True)
with right:
    st.subheader("Categorie di ruolo")
    roles_df = df.groupby("role_category").size().sort_values().reset_index(name="odonimi")
    roles_df["ruolo"] = roles_df["role_category"].map(role_label)
    st.plotly_chart(px.bar(roles_df, x="odonimi", y="ruolo", orientation="h", labels={"ruolo": "Ruolo", "odonimi": "Odonimi"}), use_container_width=True)

if {"lat", "lon"}.issubset(df.columns):
    map_df = df.copy()
    map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce")
    map_df["lon"] = pd.to_numeric(map_df["lon"], errors="coerce")
    map_df = map_df.dropna(subset=["lat", "lon"])
    if len(map_df):
        st.subheader("Mappa interattiva")
        map_df["ruolo_visualizzato"] = map_df.get("role_category", "").map(role_label)
        hover = [c for c in ["odonimo", "municipality_name", "region_name", "canonical_name", "ruolo_visualizzato", "territories", "match_method"] if c in map_df]
        fig = px.scatter_map(
            map_df,
            lat="lat",
            lon="lon",
            hover_name="odonimo",
            hover_data=hover,
            color="ruolo_visualizzato" if "ruolo_visualizzato" in map_df else None,
            zoom=4.8,
            height=650,
            labels={"ruolo_visualizzato": "Ruolo"},
        )
        fig.update_traces(marker={"size": 11, "opacity": 0.9})
        fig.update_layout(
            map_style="open-street-map",
            map=dict(center={"lat": 42.5, "lon": 12.5}, zoom=4.8),
            margin=dict(l=0, r=0, t=0, b=0),
            legend_title_text="Ruolo",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{len(map_df):,} dei {len(df):,} odonimi filtrati dispongono di coordinate rappresentative.")

if "named_year" in df.columns:
    years = pd.to_numeric(df["named_year"], errors="coerce")
    hist = df.loc[years.notna()].copy()
    hist["named_year"] = years[years.notna()].astype(int)
    if len(hist):
        st.subheader("Cronologia documentata delle intitolazioni")
        yearly = hist.groupby("named_year").size().reset_index(name="new_dedications")
        st.plotly_chart(px.bar(yearly, x="named_year", y="new_dedications", labels={"named_year": "Anno di intitolazione", "new_dedications": "Nuove intitolazioni"}), use_container_width=True)
        st.caption("Sono incluse soltanto le voci con una data di intitolazione verificata indipendentemente. Le date di modifica di OpenStreetMap non vengono usate come date di intitolazione.")

st.subheader("Dati")
show_cols = [c for c in ["odonimo", "municipality_name", "province_name", "region_name", "canonical_name", "role_category", "territories", "match_method", "match_score", "review_status", "source_url", "named_year", "removed_year"] if c in df]
display_df = df[show_cols].copy()
if "role_category" in display_df:
    display_df["role_category"] = display_df["role_category"].map(role_label)
if "territories" in display_df:
    display_df["territories"] = display_df["territories"].map(lambda s: "; ".join(territory_label(x.strip()) for x in str(s).split(";") if x.strip()))
display_df = display_df.rename(columns=COLUMN_LABELS)
sort_cols = [COLUMN_LABELS[c] for c in ["region_name", "municipality_name", "odonimo"] if c in show_cols]
st.dataframe(display_df.sort_values(sort_cols), use_container_width=True, hide_index=True)

st.download_button("Scarica il CSV filtrato", df.to_csv(index=False).encode("utf-8"), "toponimi_coloniali_filtrati.csv", "text/csv")
