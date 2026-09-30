from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Toponimi coloniali italiani", page_icon="🗺️", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #f4efe6; color: #18201f; }
    [data-testid="stSidebar"] { background: #203536; }
    [data-testid="stSidebar"] * { color: #f4f1ea; }
    [data-testid="stMetric"] { background:#fffdf8; border:1px solid #ddd5c7; border-radius:16px; padding:14px 16px; }
    .hero { background:linear-gradient(135deg,#172729,#315250); color:white; padding:28px 32px; border-radius:20px; margin-bottom:18px; }
    .hero .eyebrow { color:#e4c47f; text-transform:uppercase; letter-spacing:.14em; font-weight:800; font-size:.75rem; }
    .hero h1 { font-family:Georgia,serif; font-size:2.7rem; line-height:1.02; margin:.35rem 0 .7rem; font-weight:600; }
    .hero p { color:#dce4e0; max-width:1000px; margin:0; line-height:1.55; }
    div[data-testid="stPlotlyChart"] { background:#fffdf8; border:1px solid #ddd5c7; border-radius:18px; padding:8px; }
    h2,h3 { font-family:Georgia,serif !important; color:#203536 !important; }
    .block-container { padding-top:1.7rem; max-width:1500px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero"><div class="eyebrow">Atlante della memoria coloniale</div>
    <h1>Toponimi italiani legati al colonialismo</h1>
    <p>Odonimi ufficiali ANNCSU associati a persone, territori, città e battaglie presenti in un registro curato. Una corrispondenza nominale non dimostra, da sola, che l'intitolazione sia stata scelta specificamente per celebrare quel ruolo storico.</p></div>
    """,
    unsafe_allow_html=True,
)

ROLE_LABELS = {
    "military": "Militare", "political": "Politico", "administration": "Amministrazione coloniale",
    "political_and_administration": "Politica e amministrazione coloniale",
    "military_and_administration": "Militare e amministrazione coloniale",
    "military_political_administration": "Militare, politica e amministrazione coloniale",
    "military_and_religious": "Militare e religioso", "economic": "Economia e impresa",
    "cultural_or_scientific": "Cultura o scienza", "religious": "Religioso",
    "exploration_geography": "Esplorazione e geografia", "propaganda_or_advocacy": "Propaganda e promozione coloniale",
    "territory": "Territorio / colonia", "city_or_locality": "Città o località", "battle_or_campaign": "Battaglia / campagna",
}
ENTITY_LABELS = {"person": "Persona", "place": "Luogo / battaglia"}
TERRITORY_LABELS = {"Libya": "Libia", "Eritrea": "Eritrea", "Ethiopia": "Etiopia", "Somalia": "Somalia", "Italian East Africa": "Africa Orientale Italiana", "Dodecanese": "Dodecaneso", "Albania": "Albania"}


def role_label(v: str) -> str:
    return ROLE_LABELS.get(v, str(v).replace("_", " ").capitalize())


def entity_label(v: str) -> str:
    return ENTITY_LABELS.get(v or "person", v or "Persona")


def territory_label(v: str) -> str:
    return TERRITORY_LABELS.get(v, v)


def reset_filters() -> None:
    for key in ["entity_filter", "include_filter", "exclude_filter", "region_filter", "role_filter", "territory_filter"]:
        st.session_state[key] = []
    st.session_state["accepted_filter"] = True


DEFAULTS = [Path("data/processed/dashboard_data.parquet"), Path("data/processed/street_matches_geocoded.parquet"), Path("data/processed/street_matches.parquet")]
path = next((p for p in DEFAULTS if p.exists()), None)
if path is None:
    st.info("Nessun dato elaborato trovato. Esegui gli script 02 → 03 → 04 → 05 dalla radice del progetto.")
    st.stop()

df = pd.read_parquet(path).fillna("")
if "entity_type" not in df:
    df["entity_type"] = "person"
else:
    df["entity_type"] = df["entity_type"].replace("", "person")
base_df = df.copy()

with st.sidebar:
    st.header("Esplora")
    st.caption("Le selezioni sono chip removibili con ×.")
    st.button("↺ Azzera tutti i filtri", on_click=reset_filters, use_container_width=True)
    selected_entities = st.multiselect("Tipologia", sorted(base_df["entity_type"].unique()), format_func=entity_label, key="entity_filter")
    options = sorted(x for x in base_df["canonical_name"].unique() if x)
    selected = st.multiselect("Mostra solo questi riferimenti", options, key="include_filter")
    excluded = st.multiselect("Escludi riferimenti", options, key="exclude_filter")
    accepted = st.checkbox("Solo corrispondenze accettate", value=True, key="accepted_filter")
    selected_regions = st.multiselect("Regioni", sorted(x for x in base_df["region_name"].unique() if x), key="region_filter")
    selected_roles = st.multiselect("Categorie", sorted(x for x in base_df["role_category"].unique() if x), format_func=role_label, key="role_filter")
    terr = sorted({t.strip() for s in base_df["territories"] for t in str(s).split(";") if t.strip()})
    selected_terr = st.multiselect("Territori coloniali", terr, format_func=territory_label, key="territory_filter")

    if selected_entities: df = df[df["entity_type"].isin(selected_entities)]
    if selected: df = df[df["canonical_name"].isin(selected)]
    if excluded: df = df[~df["canonical_name"].isin(excluded)]
    if accepted and "review_status" in df: df = df[df["review_status"].isin(["accepted_auto", "accepted_manual"])]
    if selected_regions: df = df[df["region_name"].isin(selected_regions)]
    if selected_roles: df = df[df["role_category"].isin(selected_roles)]
    if selected_terr: df = df[df["territories"].map(lambda s: any(t in str(s).split(";") for t in selected_terr))]

    snap = Path("data/processed/people_registry_used.csv")
    if snap.exists(): st.download_button("↓ Scarica il registro usato nel matching", snap.read_bytes(), "registro_matching_utilizzato.csv", "text/csv", use_container_width=True)

c1,c2,c3,c4 = st.columns(4)
c1.metric("Odonimi trovati", f"{len(df):,}")
c2.metric("Comuni", f"{df['municipality_belfiore'].nunique():,}")
c3.metric("Riferimenti", f"{df['person_id'].nunique():,}")
c4.metric("Regioni", f"{df['region_name'].nunique():,}")

st.subheader("Differenze regionali")
metric = st.radio("Metrica", ["Odonimi trovati", "Per 10.000 odonimi ANNCSU", "Comuni con almeno una corrispondenza"], horizontal=True, label_visibility="collapsed")
if metric == "Odonimi trovati": regional = df.groupby("region_name").size().reset_index(name="value")
elif metric == "Per 10.000 odonimi ANNCSU":
    regional = df.groupby("region_name").agg(matches=("progressivo_odonimo","size"),total=("total_odonimi_region","first")).reset_index(); regional["total"] = pd.to_numeric(regional["total"],errors="coerce"); regional["value"] = 10000*regional["matches"]/regional["total"]
else: regional = df.groupby("region_name")["municipality_belfiore"].nunique().reset_index(name="value")
regional = regional[regional["region_name"]!=""].sort_values("value")
fig = px.bar(regional,x="value",y="region_name",orientation="h"); fig.update_traces(marker_color="#335d5b"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig,use_container_width=True)

left,right = st.columns(2)
with left:
    st.subheader("Riferimenti più rappresentati")
    top=df.groupby("canonical_name").size().nlargest(20).sort_values().reset_index(name="odonimi"); fig=px.bar(top,x="odonimi",y="canonical_name",orientation="h"); fig.update_traces(marker_color="#a4452a"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig,use_container_width=True)
with right:
    st.subheader("Categorie")
    cat=df.groupby("role_category").size().sort_values().reset_index(name="odonimi"); cat["label"]=cat["role_category"].map(role_label); fig=px.bar(cat,x="odonimi",y="label",orientation="h"); fig.update_traces(marker_color="#d09a3a"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig,use_container_width=True)

if {"lat","lon"}.issubset(df.columns):
    map_df=df.copy(); map_df["lat"]=pd.to_numeric(map_df["lat"],errors="coerce"); map_df["lon"]=pd.to_numeric(map_df["lon"],errors="coerce"); map_df=map_df.dropna(subset=["lat","lon"])
    if len(map_df):
        st.subheader("Mappa interattiva")
        map_df["categoria"] = map_df["role_category"].map(role_label)
        fig=px.scatter_map(map_df,lat="lat",lon="lon",hover_name="odonimo",hover_data=["municipality_name","region_name","canonical_name","entity_type","territories"],color="categoria",zoom=4.6,height=680)
        fig.update_traces(marker={"size":11,"opacity":.86}); fig.update_layout(map_style="carto-positron",map=dict(center={"lat":42.4,"lon":12.5},zoom=4.6),margin=dict(l=0,r=0,t=0,b=0),paper_bgcolor="rgba(0,0,0,0)",legend_title_text="Categoria")
        st.plotly_chart(fig,use_container_width=True); st.caption(f"{len(map_df):,} dei {len(df):,} odonimi filtrati dispongono di coordinate rappresentative.")

st.subheader("Dati")
cols=[c for c in ["odonimo","municipality_name","province_name","region_name","canonical_name","entity_type","role_category","territories","match_method","match_score","review_status","source_url"] if c in df]
display=df[cols].copy()
if "entity_type" in display: display["entity_type"]=display["entity_type"].map(entity_label)
if "role_category" in display: display["role_category"]=display["role_category"].map(role_label)
st.dataframe(display,use_container_width=True,hide_index=True)
st.download_button("↓ Scarica il CSV filtrato",df.to_csv(index=False).encode("utf-8"),"toponimi_coloniali_filtrati.csv","text/csv")
