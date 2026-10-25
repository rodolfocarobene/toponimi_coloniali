from __future__ import annotations

import re
import unicodedata
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
    @media (max-width:760px){ .hero h1{font-size:1.9rem;} .hero{padding:20px;} }
    @media (prefers-color-scheme: dark){ .stApp{background:#141b1b;color:#e8ece9;} [data-testid="stMetric"],div[data-testid="stPlotlyChart"]{background:#1c2625;border-color:#2f3d3b;} h2,h3{color:#e8ece9 !important;} }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero"><div class="eyebrow">Atlante della memoria coloniale</div>
    <h1>Toponimi italiani legati al colonialismo</h1>
    <p>Intitolazioni (vie e piazze ANNCSU, scuole, università e altri luoghi pubblici) associate a persone, territori, città e battaglie presenti in un registro curato. Una corrispondenza nominale non dimostra, da sola, che l'intitolazione sia stata scelta specificamente per celebrare quel ruolo storico.</p></div>
    """,
    unsafe_allow_html=True,
)

ROLE_LABELS = {
    "military": "Militare", "political": "Politico", "administration": "Amministrazione coloniale",
    "political_and_administration": "Politica e amministrazione coloniale",
    "military_and_administration": "Militare e amministrazione coloniale",
    "military_political_administration": "Militare, politica e amministrazione coloniale",
    "military_and_religious": "Militare e religioso", "economic": "Economia e impresa",
    "economic_and_colonization": "Economia e colonizzazione", "political_economic_administration": "Politica, economia e amministrazione coloniale",
    "cultural_or_scientific": "Cultura o scienza", "religious": "Religioso",
    "exploration_geography": "Esplorazione e geografia", "propaganda_or_advocacy": "Propaganda e promozione coloniale",
    "territory": "Territorio / colonia", "city_or_locality": "Città o località", "battle_or_campaign": "Battaglia / campagna",
}
KIND_LABELS = {"odonimo": "Vie e piazze", "scuola": "Scuole", "universita": "Università", "luogo_pubblico": "Altri luoghi pubblici"}
ENTITY_LABELS = {"person": "Persona", "place": "Luogo / battaglia"}
TERRITORY_LABELS = {"Libya": "Libia", "Eritrea": "Eritrea", "Ethiopia": "Etiopia", "Somalia": "Somalia", "Italian East Africa": "Africa Orientale Italiana", "Dodecanese": "Dodecaneso", "Albania": "Albania"}


def role_label(v: str) -> str:
    return ROLE_LABELS.get(v, (str(v).replace("_", " ")[:1].upper() + str(v).replace("_", " ")[1:]))


def entity_label(v: str) -> str:
    return ENTITY_LABELS.get(v or "person", v or "Persona")


def kind_label(v: str) -> str:
    return KIND_LABELS.get(v or "odonimo", v)


def territory_label(v: str) -> str:
    return TERRITORY_LABELS.get(v, v)


def territories_text(v: str) -> str:
    return "; ".join(territory_label(t.strip()) for t in str(v).split(";") if t.strip())


METHODS = [
    ("exact_canonical", "Nome completo", "Il nome completo del riferimento compare nella denominazione."),
    ("exact_alias", "Alias", "Compare un nome alternativo registrato (titolo, variante, soprannome)."),
    ("exact_surname", "Solo cognome (autorizzato)", "Compare il solo cognome, ammesso solo per riferimenti per cui il registro lo consente."),
    ("exact_initial_name", "Iniziale + cognome", "Iniziale del nome seguita dal cognome (es. «G. Cognome»)."),
    ("honoree_exact_canonical", "Wikidata: dedicato a", "Il luogo è collegato su Wikidata alla persona a cui è dedicato."),
    ("fuzzy_full_or_alias", "Nome simile", "Corrispondenza approssimata: richiede sempre una verifica manuale."),
    ("surname_in_name", "Solo cognome nel nome", "Il cognome compare dentro una denominazione più lunga: poco sicura."),
]
METHOD_LABELS = {k: label for k, label, _ in METHODS}
OK_STATUS = ["accepted_auto", "accepted_manual"]
REVIEW_OPTS = ["Verificate automaticamente", "Includi da verificare"]
FAMILIES = ["centrodestra", "centrosinistra", "m5s", "altro", "civica", "n.d."]
FAMILY_LABELS = {"centrodestra": "Centrodestra", "centrosinistra": "Centrosinistra", "m5s": "Movimento 5 Stelle", "altro": "Altro",
                 "civica": "Liste civiche (senza partito)", "n.d.": "Dato non disponibile"}
FAMILY_COLORS = {"centrodestra": "#44759a", "centrosinistra": "#a4452a", "m5s": "#d39a36", "altro": "#6f5f91", "civica": "#97a09c", "n.d.": "#c4c8c6"}
COALITIONS = ["centrodestra", "centrosinistra", "altro", "n.d."]


def method_label(v: str) -> str:
    return METHOD_LABELS.get(v) or (str(v).replace("_", " ").capitalize() if v else "—")


def norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def fam(v: str, allowed=FAMILIES) -> str:
    v = str(v or "").strip().lower()
    return v if v in allowed else "n.d."


def reset_filters() -> None:
    for key in ["kind_filter", "entity_filter", "include_filter", "exclude_filter", "region_filter", "role_filter", "territory_filter"]:
        st.session_state[key] = []
    st.session_state["q_filter"] = ""
    st.session_state["review_filter"] = REVIEW_OPTS[0]


def show_reference(name: str, only_pending: bool) -> None:
    reset_filters()
    st.session_state["include_filter"] = [name]
    if only_pending:
        st.session_state["review_filter"] = REVIEW_OPTS[1]
    st.session_state["_applied_ref"] = name


DEFAULTS = [Path("data/processed/dashboard_data.parquet"), Path("data/processed/street_matches_geocoded.parquet"), Path("data/processed/street_matches.parquet")]
path = next((p for p in DEFAULTS if p.exists()), None)
if path is None:
    st.info("Nessun dato elaborato trovato. Esegui gli script 02 → 03 → 04 → 05 dalla radice del progetto.")
    st.stop()

df = pd.read_parquet(path).fillna("")
for col, default in [("entity_type", "person"), ("site_kind", "odonimo")]:
    df[col] = df[col].replace("", default) if col in df else default
for col in ["site_detail", "coord_precision", "match_method", "review_status", "person_id", "territories", "role_category"]:
    if col not in df:
        df[col] = ""
df["_ok"] = df["review_status"].isin(OK_STATUS) | (df["review_status"] == "")
df["_s"] = (df["odonimo"] + " " + df["municipality_name"] + " " + df["canonical_name"] + " " + df["site_detail"]).map(norm)
base_df = df.copy()

tab_explore, tab_why, tab_pol = st.tabs(["Esplora", "Perché questi nomi", "Politica"])

with tab_explore:
    st.text_input("Cerca nome, comune o riferimento", placeholder="Cerca nome, comune o riferimento…", key="q_filter")
    st.radio("Stato di verifica", REVIEW_OPTS, horizontal=True, key="review_filter",
             help="«Da verificare»: corrispondenze meno sicure (nomi simili, solo cognome non autorizzato) non ancora confermate.")
    status_ph = st.empty()
    if st.session_state.get("_applied_ref"):
        st.info(f"Filtro applicato dalla scheda: {st.session_state.pop('_applied_ref')}.")
    st.caption("Una corrispondenza di nome non implica che l'intitolazione celebri il ruolo coloniale della persona o del luogo.")
    with st.expander("Come leggere le corrispondenze"):
        st.markdown("\n".join(f"- **{label}**: {desc}" for _, label, desc in METHODS))

with st.sidebar:
    st.header("Filtri")
    st.caption("Le selezioni sono chip removibili con ×.")
    st.button("↺ Azzera tutti i filtri", on_click=reset_filters, use_container_width=True)
    kinds = [k for k in KIND_LABELS if k in set(base_df["site_kind"])]
    selected_kinds = st.multiselect("Tipo di sede", kinds, format_func=kind_label, key="kind_filter")
    selected_entities = st.multiselect("Tipologia", sorted(base_df["entity_type"].unique()), format_func=entity_label, key="entity_filter")
    options = sorted(x for x in base_df["canonical_name"].unique() if x)
    selected = st.multiselect("Mostra solo questi riferimenti", options, key="include_filter")
    excluded = st.multiselect("Escludi riferimenti", options, key="exclude_filter")
    selected_regions = st.multiselect("Regioni", sorted(x for x in base_df["region_name"].unique() if x), key="region_filter")
    selected_roles = st.multiselect("Categorie", sorted(x for x in base_df["role_category"].unique() if x), format_func=role_label, key="role_filter")
    terr = sorted({t.strip() for s in base_df["territories"] for t in str(s).split(";") if t.strip()})
    selected_terr = st.multiselect("Territori coloniali", terr, format_func=territory_label, key="territory_filter")

    if selected_kinds: df = df[df["site_kind"].isin(selected_kinds)]
    if selected_entities: df = df[df["entity_type"].isin(selected_entities)]
    if selected: df = df[df["canonical_name"].isin(selected)]
    if excluded: df = df[~df["canonical_name"].isin(excluded)]
    if selected_regions: df = df[df["region_name"].isin(selected_regions)]
    if selected_roles: df = df[df["role_category"].isin(selected_roles)]
    if selected_terr: df = df[df["territories"].map(lambda s: any(t in str(s).split(";") for t in selected_terr))]
    for token in norm(st.session_state.get("q_filter", "")).split():
        df = df[df["_s"].str.contains(token, regex=False)]
    pending = int((~df["_ok"]).sum())
    if st.session_state.get("review_filter", REVIEW_OPTS[0]) == REVIEW_OPTS[0]:
        df = df[df["_ok"]]

    snap = Path("data/processed/people_registry_used.csv")
    if snap.exists(): st.download_button("↓ Scarica il registro usato nel matching", snap.read_bytes(), "registro_matching_utilizzato.csv", "text/csv", use_container_width=True)

auto_only = st.session_state.get("review_filter", REVIEW_OPTS[0]) == REVIEW_OPTS[0]
if auto_only and pending:
    status_ph.info(f"{len(df):,} risultati. {pending:,} corrispondenze da verificare sono nascoste: scegli «Includi da verificare» per vederle.")
elif pending:
    status_ph.info(f"{len(df):,} risultati, di cui {pending:,} da verificare.")
else:
    status_ph.caption(f"{len(df):,} risultati.")

with tab_explore:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Intitolazioni trovate", f"{len(df):,}")
    c2.metric("Comuni", f"{df['municipality_belfiore'].nunique():,}")
    c3.metric("Riferimenti distinti", f"{df['person_id'].nunique():,}")
    c4.metric("Regioni", f"{df['region_name'].nunique():,}")

    if {"lat", "lon"}.issubset(df.columns):
        map_df = df.copy(); map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce"); map_df["lon"] = pd.to_numeric(map_df["lon"], errors="coerce"); map_df = map_df.dropna(subset=["lat", "lon"])
        if len(map_df):
            st.subheader("Mappa interattiva")
            map_df["site_kind"] = map_df["site_kind"].map(kind_label); map_df["categoria"] = map_df["role_category"].map(role_label)
            map_df["corrispondenza"] = map_df["match_method"].map(method_label)
            map_df["stato"] = map_df["_ok"].map({True: "", False: "DA VERIFICARE"})
            map_df["approx"] = map_df["coord_precision"] == "municipality_centroid"
            map_df["posizione"] = map_df["approx"].map({True: "posizione approssimata (centro del comune)", False: ""})
            fig = px.scatter_map(map_df, lat="lat", lon="lon", hover_name="odonimo", custom_data=["approx"],
                                 hover_data={"site_kind": True, "municipality_name": True, "region_name": True, "canonical_name": True, "corrispondenza": True,
                                             "stato": True, "posizione": True, "approx": False, "lat": False, "lon": False},
                                 color="categoria", zoom=4.6, height=680)
            for tr in fig.data:
                approx = list(tr.customdata[:, 0]) if tr.customdata is not None else []
                tr.marker.opacity = [0.38 if a else 0.86 for a in approx]
                tr.marker.size = [9 if a else 11 for a in approx]
            fig.update_layout(map_style="carto-positron", map=dict(center={"lat": 42.4, "lon": 12.5}, zoom=4.6), margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", legend_title_text="Categoria", legend=dict(orientation="h", yanchor="top", y=-0.01, font=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True)
            n_approx = int(map_df["approx"].sum())
            st.caption(f"{len(map_df):,} dei {len(df):,} intitolazioni filtrate hanno coordinate" + (f"; {n_approx:,} approssimate al centro del comune (punti più chiari)." if n_approx else "."))

    st.subheader("Dati")
    st.caption("Clicca un'intestazione per ordinare; seleziona una riga per vederne i dettagli.")
    cols = [c for c in ["site_kind", "odonimo", "site_detail", "municipality_name", "province_name", "region_name", "canonical_name", "entity_type", "role_category", "territories", "match_method", "review_status", "source_url"] if c in df]
    table_df = df.reset_index(drop=True)
    display = table_df[cols].copy()
    display["site_kind"] = display["site_kind"].map(kind_label)
    if not (display["site_detail"] != "").any(): display = display.drop(columns="site_detail")
    display["entity_type"] = display["entity_type"].map(entity_label)
    display["role_category"] = display["role_category"].map(role_label)
    display["match_method"] = display["match_method"].map(method_label)
    display["review_status"] = table_df["_ok"].map({True: "Verificata", False: "Da verificare"})
    display = display.rename(columns={"site_kind": "Sede", "odonimo": "Denominazione", "site_detail": "Dettaglio", "municipality_name": "Comune", "province_name": "Provincia", "region_name": "Regione",
                                      "canonical_name": "Riferimento", "entity_type": "Tipo", "role_category": "Categoria", "territories": "Territori", "match_method": "Corrispondenza",
                                      "review_status": "Stato", "source_url": "Fonte"})
    event = st.dataframe(display, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="data_table")
    rows_sel = event.selection.rows if event and event.selection else []
    if rows_sel and rows_sel[0] < len(table_df):
        r = table_df.iloc[rows_sel[0]]
        with st.container(border=True):
            st.markdown(f"**{r['odonimo']}**  \n{kind_label(r['site_kind'])} · {r['municipality_name']} ({r['region_name']})")
            st.markdown(f"Riferimento: **{r['canonical_name']}** · corrispondenza: {method_label(r['match_method'])} · stato: "
                        + ("verificata" if r["_ok"] else "**da verificare**")
                        + " · posizione: " + {"municipality_centroid": "approssimata (centro del comune)", "street_median": "stimata dagli accessi della via", "point": "puntuale"}.get(r["coord_precision"], "non disponibile"))
    st.download_button("↓ Scarica il CSV filtrato", df.drop(columns=["_ok", "_s"]).to_csv(index=False).encode("utf-8"), "toponimi_coloniali_filtrati.csv", "text/csv")

    st.subheader("Differenze regionali")
    metric = st.radio("Metrica", ["Intitolazioni trovate", "Per 10.000 sedi della stessa tipologia", "Comuni con almeno una corrispondenza"], horizontal=True, label_visibility="collapsed")
    if metric == "Intitolazioni trovate": regional = df.groupby("region_name").size().reset_index(name="value")
    elif metric == "Per 10.000 sedi della stessa tipologia":
        den_col = "total_kind_region" if "total_kind_region" in df else "total_odonimi_region"
        tmp = df.assign(den=pd.to_numeric(df[den_col].replace("", pd.NA).fillna(df.get("total_odonimi_region", pd.NA)), errors="coerce"))
        den = tmp.groupby(["region_name", "site_kind"])["den"].first().groupby("region_name").sum()
        regional = tmp.groupby("region_name").size().rename("matches").to_frame().join(den.rename("total")).reset_index(); regional["value"] = 10000 * regional["matches"] / regional["total"]
    else: regional = df.groupby("region_name")["municipality_belfiore"].nunique().reset_index(name="value")
    regional = regional[regional["region_name"] != ""].sort_values("value")
    fig = px.bar(regional, x="value", y="region_name", orientation="h"); fig.update_traces(marker_color="#335d5b"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10)); fig.update_yaxes(automargin=True, title=None)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    left, right = st.columns(2)
    with left:
        st.subheader("Riferimenti più rappresentati")
        top = df.groupby("canonical_name").size().nlargest(20).sort_values().reset_index(name="intitolazioni"); fig = px.bar(top, x="intitolazioni", y="canonical_name", orientation="h"); fig.update_traces(marker_color="#a4452a"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10)); fig.update_yaxes(automargin=True, title=None); st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right:
        st.subheader("Categorie")
        cat = df.groupby("role_category").size().sort_values().reset_index(name="intitolazioni"); cat["label"] = cat["role_category"].map(role_label); fig = px.bar(cat, x="intitolazioni", y="label", orientation="h"); fig.update_traces(marker_color="#d09a3a"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10)); fig.update_yaxes(automargin=True, title=None); st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with tab_why:
    st.info("Una scheda per ogni riferimento del registro curato. Il fatto che un nome compaia non implica che l'intitolazione celebri quel ruolo. "
            "Dove manca la traduzione italiana compare l'originale inglese.")
    reg_path = next((p for p in [Path("data/processed/people_registry_used.csv"), Path("data/manual/people_registry.csv")] if p.exists()), None)
    if reg_path is None:
        st.warning("Registro non trovato.")
    else:
        reg = pd.read_csv(reg_path, dtype=str).fillna("")
        if "entity_type" not in reg: reg["entity_type"] = "person"
        reg["entity_type"] = reg["entity_type"].replace("", "person")
        reg["summary"] = reg["connection_summary_it"].where(reg.get("connection_summary_it", "") != "", reg["connection_summary"]) if "connection_summary_it" in reg else reg["connection_summary"]
        ok_counts = base_df[base_df["_ok"]].groupby("person_id").size()
        pend_counts = base_df[~base_df["_ok"]].groupby("person_id").size()
        reg["ok"] = reg["person_id"].map(ok_counts).fillna(0).astype(int)
        reg["pending"] = reg["person_id"].map(pend_counts).fillna(0).astype(int)
        reg["_s"] = (reg["canonical_name"] + " " + reg.get("aliases", "") + " " + reg["summary"] + " " + reg["territories"].map(lambda s: territories_text(s)) + " " + reg["role_category"].map(role_label)).map(norm)
        t1, t2, t3 = st.columns([3, 2, 2])
        pq = t1.text_input("Cerca un riferimento", placeholder="Cerca un riferimento…", key="why_q")
        pent = t2.radio("Tipologia", ["Tutti", "Persone", "Luoghi e battaglie"], horizontal=True, key="why_ent")
        psort = t3.radio("Ordina", ["Più intitolazioni", "Nome A–Z"], horizontal=True, key="why_sort")
        view = reg
        for token in norm(pq).split():
            view = view[view["_s"].str.contains(token, regex=False)]
        if pent != "Tutti":
            view = view[view["entity_type"] == {"Persone": "person", "Luoghi e battaglie": "place"}[pent]]
        view = view.assign(_n=view["ok"] + view["pending"])
        view = view.sort_values("canonical_name") if psort == "Nome A–Z" else view.sort_values(["_n", "canonical_name"], ascending=[False, True])
        st.caption(f"{len(view)} di {len(reg)} riferimenti")
        grid = st.columns(3)
        for i, (_, g) in enumerate(view.iterrows()):
            with grid[i % 3].container(border=True):
                st.markdown(f"**{g['canonical_name']}**")
                st.caption(" · ".join(x for x in [entity_label(g["entity_type"]), role_label(g["role_category"])] if x))
                meta = " · ".join(x for x in [territories_text(g["territories"]), g["period"]] if x)
                if meta: st.caption(meta)
                st.write(g["summary"])
                st.write(f"**{g['ok']}** intitolazioni verificate" + (f" · **{g['pending']}** da verificare" if g["pending"] else "") if g["_n"] else "Nessuna intitolazione nei dati attuali")
                b1, b2 = st.columns(2)
                if g["source_url"].startswith(("http://", "https://")):
                    b1.link_button("Fonte", g["source_url"])
                if g["_n"]:
                    b2.button("Mostra sulla mappa", key=f"show_{g['person_id']}", on_click=show_reference, args=(g["canonical_name"], g["ok"] == 0))

with tab_pol:
    st.info("**Come leggere questi dati.** La maggior parte dei nomi è stata assegnata decenni fa, spesso in epoca coloniale o fascista. "
            "L'amministrazione attuale indica quindi chi governa oggi luoghi che conservano questi nomi, **non chi li ha scelti**. "
            "Il confronto è descrittivo: mostra correlazioni, non cause. Le liste civiche non sono attribuite a nessun partito. "
            "Sono conteggiate solo le corrispondenze verificate.")
    pol_path, reg_pol_path = Path("data/processed/municipality_politics.csv"), Path("data/processed/region_politics.csv")
    if not pol_path.exists() and not reg_pol_path.exists():
        st.warning("Dati non ancora disponibili. Questa sezione si attiva quando in data/processed sono presenti municipality_politics.csv e region_politics.csv.")
    accepted = base_df[base_df["_ok"]]
    if pol_path.exists():
        pol = pd.read_csv(pol_path, dtype=str).fillna("")
        pol["municipality_istat"] = pol["municipality_istat"].str.zfill(6)
        pol["family"] = pol["party_family"].map(fam)
        pol["n_od"] = pd.to_numeric(pol["n_odonimi"], errors="coerce").fillna(0) if "n_odonimi" in pol else 0
        has_n = bool((pol["n_od"] > 0).any())
        pol["acc"] = pol["municipality_istat"].map(accepted.groupby("municipality_istat_y").size()).fillna(0)
        pol["acc_str"] = pol["municipality_istat"].map(accepted[accepted["site_kind"] == "odonimo"].groupby("municipality_istat_y").size()).fillna(0)
        st.subheader("Comuni, per famiglia politica del sindaco")
        st.caption("Le liste civiche e i comuni senza dato non sono partiti (in grigio). Il confronto grezzo risente della dimensione del comune: le liste civiche prevalgono nei comuni piccoli.")
        c_a, c_b = st.columns(2)
        metric_opts = ["Quota con almeno una"] + (["Per 10.000 odonimi"] if has_n else [])
        pmetric = c_a.radio("Misura", metric_opts, horizontal=True, key="pol_metric")
        size = c_b.radio("Dimensione", ["Tutti i comuni", "Solo comuni grandi (terzo superiore per odonimi)"], horizontal=True, key="pol_size") if has_n else "Tutti i comuni"
        pool = pol
        if size != "Tutti i comuni":
            thr = pol.loc[pol["n_od"] > 0, "n_od"].quantile(2 / 3)
            pool = pol[pol["n_od"] >= thr]
            st.caption(f"Comuni grandi: almeno {thr:,.0f} odonimi ({len(pool):,} comuni).")
        grp = pool.groupby("family").agg(comuni=("family", "size"), con_almeno_una=("acc", lambda s: int((s > 0).sum())), intitolazioni=("acc_str", "sum"), odonimi=("n_od", "sum")).reindex(FAMILIES).dropna(subset=["comuni"]).reset_index()
        grp["quota"] = 100 * grp["con_almeno_una"] / grp["comuni"]
        grp["per_10000"] = (10000 * grp["intitolazioni"] / grp["odonimi"].where(grp["odonimi"] > 0)) if has_n else None
        grp["Famiglia"] = grp["family"].map(FAMILY_LABELS) + " (" + grp["comuni"].astype(int).astype(str) + " comuni)"
        ycol, xlab = ("quota", "% di comuni con almeno una intitolazione verificata") if pmetric == metric_opts[0] else ("per_10000", "intitolazioni (vie e piazze) ogni 10.000 odonimi")
        fig = px.bar(grp.iloc[::-1], x=ycol, y="Famiglia", orientation="h", color="family", color_discrete_map=FAMILY_COLORS, labels={ycol: xlab}, text_auto=".1f")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10)); fig.update_yaxes(title=None, automargin=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        out = grp[["Famiglia", "comuni", "con_almeno_una", "quota", "intitolazioni"] + (["per_10000"] if has_n else [])].rename(columns={
            "comuni": "Comuni", "con_almeno_una": "Con almeno una", "quota": "Quota %", "intitolazioni": "Intitolazioni (vie)", "per_10000": "Per 10.000 odonimi"})
        st.dataframe(out.round(1), hide_index=True, use_container_width=True)
    if reg_pol_path.exists():
        rp = pd.read_csv(reg_pol_path, dtype=str).fillna("")
        rp["key"] = rp["region_name"].map(norm)
        per = base_df.assign(den=pd.to_numeric(base_df["total_kind_region"].replace("", pd.NA), errors="coerce"))
        den = per.groupby(["region_name", "site_kind"])["den"].first().groupby("region_name").sum()
        reg_tab = accepted.groupby("region_name").size().rename("ok").to_frame().join(den.rename("totale")).reset_index()
        reg_tab = reg_tab[reg_tab["region_name"] != ""]
        reg_tab["per_10000"] = 10000 * reg_tab["ok"] / reg_tab["totale"]
        reg_tab = reg_tab.merge(rp[["key", "president", "coalition"]], left_on=reg_tab["region_name"].map(norm), right_on="key", how="left").fillna({"coalition": "", "president": ""})
        reg_tab["coal"] = reg_tab["coalition"].map(lambda v: fam(v, COALITIONS))
        st.subheader("Regioni, per coalizione del presidente")
        fig = px.bar(reg_tab.sort_values("per_10000"), x="per_10000", y="region_name", orientation="h", color="coal", color_discrete_map=FAMILY_COLORS,
                     labels={"per_10000": "per 10.000 sedi", "region_name": "", "coal": "Coalizione"})
        fig.for_each_trace(lambda t: t.update(name=FAMILY_LABELS.get(t.name, t.name)))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Coalizione")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        summary = reg_tab.groupby("coal").agg(Regioni=("region_name", "size"), Intitolazioni=("ok", "sum"), totale=("totale", "sum")).reindex(COALITIONS).dropna().reset_index()
        summary["Per 10.000 sedi"] = (10000 * summary["Intitolazioni"] / summary["totale"]).round(1)
        summary["Coalizione"] = summary["coal"].map(FAMILY_LABELS)
        st.dataframe(summary[["Coalizione", "Regioni", "Intitolazioni", "Per 10.000 sedi"]], hide_index=True, use_container_width=True)
    if pol_path.exists() or reg_pol_path.exists():
        st.caption("Fonti: Ministero dell'Interno, Anagrafe degli amministratori locali e regionali (in carica al 24/08/2026); "
                   "per alcune coalizioni e per i presidenti di Campania e Marche, Wikipedia.")
