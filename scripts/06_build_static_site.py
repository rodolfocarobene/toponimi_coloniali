#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DATA_DEFAULTS = [
    Path("data/processed/dashboard_data.csv"),
    Path("data/processed/street_matches_geocoded.csv"),
    Path("data/processed/street_matches.csv"),
]
POLITICS_DEFAULT = Path("data/processed/municipality_politics.csv")
REGION_POLITICS_DEFAULT = Path("data/processed/region_politics.csv")

# Solo le colonne usate dalla scheda Politica: il CSV completo resta in data/processed.
POLITICS_COLUMNS = ["municipality_istat", "party_family", "n_odonimi"]
# Colonne del registro ripetute su ogni riga: si omettono dove coincidono col registro e la pagina le ricostruisce.
REGISTRY_ROW_COLUMNS = [
    "aliases", "connection_summary", "connection_summary_it", "source_url", "wikidata_qid",
    "allow_surname_only", "status", "period",
]
REGION_POLITICS_COLUMNS = ["region_name", "president", "coalition", "election_date", "source_url"]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "") for k, v in row.items() if k} for row in csv.DictReader(f)]


def load_optional(path: Path | None, columns: list[str]) -> list[dict[str, str]] | None:
    """Righe di un CSV facoltativo ridotte alle colonne note; None se il file manca."""
    if path is None or not path.exists():
        return None
    return [{c: row.get(c, "").strip() for c in columns} for row in load_rows(path)]


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


# Il template è una stringa normale (non una f-string): i segnaposto __NOME__ vengono sostituiti in build_html.
TEMPLATE = r'''<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>try{var t=new URLSearchParams(location.hash.slice(1)).get("theme")||localStorage.getItem("theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}</script>
<meta name="color-scheme" content="light dark">
<title>Toponimi coloniali italiani</title>
<script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
<style>
:root {
  --ink:#18201f; --muted:#5d6764; --paper:#f4efe6; --card:#fffdf8;
  --line:#ddd5c7; --accent:#a4452a; --accent2:#335d5b; --accent3:#d9a441;
  --navy:#1f3032; --shadow:0 16px 45px rgba(30,38,35,.08);
  --surface:#fff; --line2:#d9d1c4; --line3:#b5a793; --hover:#f5f0e7; --zebra:#fcfaf6; --chip:#eef0ec; --chip2:#e1e6e1;
  --ink2:#37534f; --bg1:#e8dfd1; --aside:rgba(255,253,248,.92); --grid:#e9e2d8; --bar1:#335d5b; --bar2:#a4452a; --bar3:#d09a3a; --focus:#1d6f6b;
  --warn-bg:#fbe9c9; --warn-ink:#6b4510; --note-bg:#f1ece0; --sel:#294847;
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ink:#e8ece9; --muted:#a6b1ad; --paper:#141b1b; --card:#1c2625; --line:#2f3d3b; --accent:#e07a5c; --accent2:#6fb0aa;
  --navy:#3b6866; --shadow:0 16px 45px rgba(0,0,0,.35);
  --surface:#232f2e; --line2:#3a4b49; --line3:#5b7471; --hover:#2a3836; --zebra:#202b2a; --chip:#2a3736; --chip2:#364644;
  --ink2:#c4d6d2; --bg1:#0f1515; --aside:rgba(28,38,37,.92); --grid:#2f3d3b; --bar1:#6fb0aa; --bar2:#e07a5c; --bar3:#e0b45a; --focus:#7fd0c9;
  --warn-bg:#4a3a1c; --warn-ink:#f0d49a; --note-bg:#222e2d; --sel:#3b6866;
}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --ink:#e8ece9; --muted:#a6b1ad; --paper:#141b1b; --card:#1c2625; --line:#2f3d3b; --accent:#e07a5c; --accent2:#6fb0aa;
  --navy:#3b6866; --shadow:0 16px 45px rgba(0,0,0,.35);
  --surface:#232f2e; --line2:#3a4b49; --line3:#5b7471; --hover:#2a3836; --zebra:#202b2a; --chip:#2a3736; --chip2:#364644;
  --ink2:#c4d6d2; --bg1:#0f1515; --aside:rgba(28,38,37,.92); --grid:#2f3d3b; --bar1:#6fb0aa; --bar2:#e07a5c; --bar3:#e0b45a; --focus:#7fd0c9;
  --warn-bg:#4a3a1c; --warn-ink:#f0d49a; --note-bg:#222e2d; --sel:#3b6866;
}}
*{box-sizing:border-box} html{scroll-behavior:smooth}
::selection{background:var(--accent3);color:#18201f}
body{margin:0;background:linear-gradient(180deg,var(--bg1) 0,var(--paper) 280px,var(--paper) 100%);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.hero{background:radial-gradient(circle at 85% 10%,rgba(217,164,65,.23),transparent 32%),linear-gradient(135deg,#172729,#294847);color:#fff;padding:18px max(28px,calc((100vw - 1500px)/2)) 30px;border-bottom:1px solid rgba(255,255,255,.12)}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:26px}
.brand{font-size:.84rem;font-weight:700;color:#e4c47f;min-width:0}
.hero h1{font-family:Georgia,"Times New Roman",serif;font-size:clamp(2.05rem,4vw,4rem);line-height:1;margin:0 0 16px;max-width:950px;font-weight:600;text-wrap:balance}
.hero p{max-width:900px;color:#dae1de;font-size:1rem;line-height:1.6;margin:0}
.hero .badges{display:flex;flex-wrap:wrap;gap:9px;margin-top:20px} .badge{border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.07);padding:7px 11px;border-radius:999px;font-size:.78rem;color:#eef1ef}
.theme-btn{flex:none;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.08);color:#fff;border-radius:999px;padding:6px 12px;font:inherit;font-size:.76rem;font-weight:700;cursor:pointer}
.tabs{position:sticky;top:0;z-index:30;display:flex;gap:4px;background:var(--paper);border-bottom:1px solid var(--line);padding:0 max(28px,calc((100vw - 1500px)/2));overflow-x:auto}
.tab-btn{border:0;background:none;color:var(--muted);font:inherit;font-size:.92rem;font-weight:700;padding:14px 16px 12px;cursor:pointer;border-bottom:3px solid transparent;white-space:nowrap}
.tab-btn:hover{color:var(--ink)} .tab-btn[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
.shell{max-width:1500px;margin:0 auto;padding:22px 28px 40px;display:grid;grid-template-columns:315px minmax(0,1fr);gap:22px}
.page{max-width:1500px;margin:0 auto;padding:22px 28px 40px}
[hidden]{display:none!important}
aside{position:sticky;top:64px;align-self:start;background:var(--aside);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:var(--shadow);max-height:calc(100vh - 80px);overflow:auto}
aside h2{font-family:Georgia,serif;font-weight:600;margin:2px 0 4px;font-size:1.55rem} .filter-intro{color:var(--muted);font-size:.82rem;line-height:1.45;margin:0 0 15px}
.filter-label{display:flex;justify-content:space-between;align-items:center;font-weight:760;font-size:.82rem;margin:14px 0 6px;color:var(--ink)}
.picker{border:1px solid var(--line2);border-radius:12px;background:var(--surface)} .picker[open]{border-color:var(--line3);box-shadow:0 9px 28px rgba(38,45,43,.09)}
.picker summary{list-style:none;cursor:pointer;padding:10px 11px;display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:.84rem;color:var(--ink)} .picker summary::-webkit-details-marker{display:none}
.picker-summary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap} .picker-count{min-width:24px;text-align:center;background:var(--chip);border-radius:999px;padding:2px 7px;font-size:.72rem;font-weight:800;color:var(--ink2)}
.picker-menu{border-top:1px solid var(--line);padding:9px} .picker-search{width:100%;border:1px solid var(--line2);border-radius:9px;padding:8px 9px;font:inherit;font-size:.82rem;background:var(--zebra);color:var(--ink)}
.picker-options{max-height:210px;overflow:auto;padding:5px 1px} .picker-option{display:flex;align-items:flex-start;gap:8px;padding:7px 6px;border-radius:8px;font-size:.81rem;line-height:1.25;cursor:pointer} .picker-option:hover{background:var(--hover)} .picker-option input{margin-top:2px;accent-color:var(--accent2)}
.picker-footer{display:flex;gap:7px;padding-top:6px} .mini-btn{border:0;border-radius:9px;padding:7px 10px;background:var(--chip);color:var(--ink);font:inherit;font-size:.76rem;font-weight:750;cursor:pointer} .mini-btn:hover{background:var(--chip2)} .mini-btn:disabled{opacity:.5;cursor:default}
.actions{display:grid;gap:8px;margin-top:16px} button.action{border:0;border-radius:11px;padding:10px 12px;font:inherit;font-size:.81rem;font-weight:780;cursor:pointer;text-align:left} button.primary{background:var(--navy);color:#fff} button.secondary{background:var(--chip);color:var(--ink)} button.action:hover{filter:brightness(.98)}
:is(button,input,select,summary,a):focus-visible{outline:2px solid var(--focus);outline-offset:2px}
main{min-width:0}
.toolbar{background:var(--card);border:1px solid var(--line);border-radius:19px;padding:16px 18px;margin-bottom:14px;box-shadow:0 8px 28px rgba(45,50,45,.045)}
.searchbox{position:relative;display:flex;align-items:center}
.searchbox svg{position:absolute;left:15px;width:20px;height:20px;color:var(--muted);pointer-events:none}
.searchbox input{width:100%;border:1.5px solid var(--line3);border-radius:14px;background:var(--surface);color:var(--ink);font:inherit;font-size:1.08rem;padding:15px 44px 15px 46px}
.searchbox input::placeholder{color:var(--muted)} .searchbox input:focus{border-color:var(--focus)}
.searchbox input::-webkit-search-cancel-button{display:none}
.search-clear{position:absolute;right:8px;border:0;background:var(--chip);color:var(--ink2);width:30px;height:30px;border-radius:50%;font-size:1.1rem;line-height:1;cursor:pointer}
.toolbar-row{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;margin-top:12px}
.seg-group{display:inline-flex;border:1px solid var(--line3);border-radius:12px;overflow:hidden;background:var(--chip)}
.seg-group button{border:0;background:none;color:var(--ink2);font:inherit;font-size:.82rem;font-weight:700;padding:9px 13px;cursor:pointer}
.seg-group button+button{border-left:1px solid var(--line3)}
.seg-group button[aria-pressed="true"]{background:var(--sel);color:#fff}
.seg-group .n{font-weight:800;margin-left:4px}
.linkbtn{border:0;background:none;color:var(--accent2);font:inherit;font-size:.82rem;font-weight:700;text-decoration:underline;text-underline-offset:3px;cursor:pointer;padding:4px 0}
.result-line{margin:12px 0 0;font-size:.88rem;color:var(--ink);display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center}
.result-line b{font-size:1rem}
.caution{margin:8px 0 0;font-size:.78rem;color:var(--muted);line-height:1.45}
.help{margin-top:12px;background:var(--note-bg);border-radius:12px;padding:12px 14px;font-size:.82rem;line-height:1.5}
.help dl{margin:8px 0 0;display:grid;grid-template-columns:max-content 1fr;gap:5px 14px} .help dt{font-weight:750} .help dd{margin:0;color:var(--muted)}
.help p{margin:0}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px} .metric{background:var(--card);border:1px solid var(--line);border-radius:17px;padding:14px 17px;box-shadow:0 8px 28px rgba(45,50,45,.04)} .metric-label{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800} .metric b{font-family:Georgia,serif;font-size:1.9rem;font-weight:600;display:block;margin-top:4px;color:var(--ink)}
.card{background:var(--card);border:1px solid var(--line);border-radius:19px;padding:18px;margin-bottom:14px;box-shadow:0 8px 28px rgba(45,50,45,.045)} .card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:10px;flex-wrap:wrap} .card h2{font-family:Georgia,serif;font-weight:600;font-size:1.38rem;margin:0} .card p.note,.note{color:var(--muted);font-size:.8rem;margin:4px 0 0;line-height:1.5;max-width:75ch}
.segmented{display:flex;flex-wrap:wrap;gap:6px} .seg{border:1px solid var(--line2);background:var(--chip);border-radius:999px;padding:6px 10px;font:inherit;font-size:.76rem;font-weight:700;color:var(--ink2);cursor:pointer} .seg[aria-pressed="true"]{background:var(--sel);color:#fff;border-color:var(--sel)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px} #map{height:640px;border-radius:14px;overflow:hidden} .map-note{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:var(--muted);font-size:.78rem;margin-top:9px}
.status-dot{width:8px;height:8px;border-radius:50%;background:#4c8b6f;display:inline-block}
.active-filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px} .active-filters:empty{display:none}
.active-chip{display:inline-flex;align-items:center;gap:6px;background:var(--chip);border:1px solid var(--line2);border-radius:999px;padding:4px 6px 4px 10px;font:inherit;font-size:.74rem;color:var(--ink2);cursor:pointer;max-width:100%} .active-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap} .active-chip i{font-style:normal;font-weight:800;width:18px;height:18px;border-radius:50%;background:var(--chip2);display:inline-grid;place-items:center;flex:none}
.detail{margin-top:12px;border:1px solid var(--line2);background:var(--surface);border-radius:14px;padding:14px 16px;font-size:.85rem;line-height:1.5}
.detail h3{margin:0 0 2px;font-size:1.02rem} .detail .sub{color:var(--muted);margin:0 0 8px}
.detail dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0} .detail dt{color:var(--muted);font-weight:700} .detail dd{margin:0}
.detail .hint{color:var(--muted);margin:0}
.detail-head{display:flex;justify-content:space-between;gap:10px}
a{color:var(--accent2);text-underline-offset:3px} a:hover{color:var(--accent)}
.table-wrap{overflow:auto;max-height:620px;border:1px solid var(--line);border-radius:12px}
table{min-width:1050px;border-collapse:separate;border-spacing:0;width:100%;font-size:.78rem;background:var(--surface)}
th{position:sticky;top:0;background:#203536;color:#fff;text-align:left;padding:0;font-size:.72rem;letter-spacing:.03em;z-index:2}
th button{all:unset;box-sizing:border-box;display:block;width:100%;cursor:pointer;padding:10px;white-space:nowrap} th button:focus-visible{outline:2px solid #fff;outline-offset:-3px}
th[aria-sort="ascending"] button::after{content:" \25B2";font-size:.62rem} th[aria-sort="descending"] button::after{content:" \25BC";font-size:.62rem}
td{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis}
tr:nth-child(even) td{background:var(--zebra)} tbody tr{cursor:pointer} tbody tr:hover td{background:var(--hover)} tbody tr.sel td{background:var(--chip2)}
tbody tr:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
.table-foot{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:10px}
.kind-tag{display:inline-block;border-radius:999px;padding:1px 8px;font-size:.7rem;font-weight:700;background:var(--chip);color:var(--ink2)}
.flag{display:inline-block;border-radius:999px;padding:1px 8px;font-size:.7rem;font-weight:800;background:var(--warn-bg);color:var(--warn-ink)}
.ok-tag{color:var(--muted);font-size:.74rem}
.empty{padding:22px;text-align:center;color:var(--muted);font-size:.9rem}
.empty button{margin-left:6px}
.callout{background:var(--note-bg);border-radius:14px;padding:14px 18px;margin-bottom:16px;font-size:.88rem;line-height:1.55;max-width:90ch} .callout b{color:var(--ink)}
.ref-tools{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin-bottom:14px}
.ref-tools .searchbox{flex:1 1 320px;max-width:520px} .ref-tools .searchbox input{font-size:1rem;padding:12px 42px 12px 44px}
.ref-tools select{font:inherit;font-size:.85rem;border:1px solid var(--line3);background:var(--surface);color:var(--ink);border-radius:10px;padding:10px 10px}
.ref-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.ref-card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:8px}
.ref-card.flash{animation:flash 2.2s cubic-bezier(.16,1,.3,1)}
@keyframes flash{0%{box-shadow:0 0 0 3px var(--accent3)}100%{box-shadow:0 0 0 3px transparent}}
.ref-card h3{font-family:Georgia,serif;font-weight:600;font-size:1.15rem;margin:0}
.ref-tags{display:flex;flex-wrap:wrap;gap:6px}
.ref-meta{margin:0;color:var(--muted);font-size:.8rem}
.ref-sum{margin:0;font-size:.88rem;line-height:1.5}
.ref-foot{margin-top:auto;padding-top:8px;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;font-size:.82rem;border-top:1px solid var(--line)}
.ref-foot .cnt{flex:1 1 100%}
.pol-table{width:100%;min-width:0;font-size:.82rem} .pol-table th{position:static;padding:9px 10px;background:var(--chip);color:var(--ink)} .pol-table td{white-space:normal} .pol-table td.num,.pol-table th.num{text-align:right}
footer{max-width:1500px;margin:0 auto;padding:0 28px 36px;color:var(--muted);font-size:.76rem}
.filters-toggle{display:none;width:100%;margin-bottom:12px;border:1px solid var(--line2);background:var(--card);color:var(--ink);border-radius:13px;padding:12px 14px;font:inherit;font-weight:780;font-size:.9rem;cursor:pointer;text-align:left;justify-content:space-between;align-items:center}
@media(max-width:1100px){.shell{grid-template-columns:1fr}aside{position:static;max-height:none}.filters-toggle{display:flex}aside.collapsed{display:none}.metrics{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.shell{padding:14px 12px 30px}.page{padding:14px 12px 30px}.hero{padding:14px 16px 26px}.topbar{margin-bottom:20px}.tabs{padding:0 8px}.grid2{grid-template-columns:1fr}#map{height:520px}.toolbar{padding:14px}.seg-group{width:100%}.seg-group button{flex:1;padding:10px 6px;font-size:.78rem}.help dl,.detail dl{grid-template-columns:1fr;gap:0}.help dt,.detail dt{margin-top:6px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.ref-card.flash{animation:none}}
</style>
</head>
<body>
<section class="hero">
  <div class="topbar"><span class="brand">Atlante della memoria coloniale</span><button class="theme-btn" id="themeBtn" type="button" aria-label="Cambia tema chiaro/scuro">Tema</button></div>
  <h1>Toponimi italiani legati al colonialismo</h1>
  <p>Una mappa esplorativa delle intitolazioni (vie, piazze, scuole, università e altri luoghi pubblici) associate a persone, territori, città e battaglie con un legame documentato con il colonialismo italiano. La corrispondenza nominale non implica automaticamente che l'intitolazione sia stata deliberata per celebrare quello specifico ruolo storico.</p>
  <div class="badges"><span class="badge">ANNCSU · odonimi ufficiali</span><span class="badge">Scuole e università</span><span class="badge">Registro curato manualmente</span></div>
</section>
<nav class="tabs" role="tablist" aria-label="Sezioni">
  <button class="tab-btn" role="tab" id="tabbtn-esplora" aria-controls="tab-esplora" data-tab="esplora" aria-selected="true">Esplora</button>
  <button class="tab-btn" role="tab" id="tabbtn-perche" aria-controls="tab-perche" data-tab="perche" aria-selected="false" tabindex="-1">Perché questi nomi</button>
  <button class="tab-btn" role="tab" id="tabbtn-politica" aria-controls="tab-politica" data-tab="politica" aria-selected="false" tabindex="-1">Politica</button>
</nav>

<div id="tab-esplora" role="tabpanel" aria-labelledby="tabbtn-esplora">
<div class="shell">
<button class="filters-toggle" id="filtersToggle" type="button" aria-expanded="false" aria-controls="filters"><span>Altri filtri</span><span id="filtersCount">Nessun filtro attivo</span></button>
<aside id="filters" class="collapsed" aria-label="Filtri">
  <h2>Filtri</h2><p class="filter-intro">Apri un filtro e seleziona le voci: i risultati si aggiornano subito. La ricerca e lo stato di verifica sono in alto.</p>
  <div id="filter-kind"></div>
  <div id="filter-entity"></div>
  <div id="filter-include"></div>
  <div id="filter-exclude"></div>
  <div id="filter-regions"></div>
  <div id="filter-roles"></div>
  <div id="filter-territories"></div>
  <div class="actions">
    <button id="reset" class="action secondary" type="button">Azzera tutti i filtri</button>
    <button id="downloadData" class="action primary" type="button">Scarica il CSV filtrato</button>
    <button id="downloadRegistry" class="action secondary" type="button">Scarica il registro usato nel matching</button>
  </div>
</aside>
<main>
  <section class="toolbar" role="search" aria-label="Ricerca">
    <label class="sr" for="q">Cerca nome, comune o riferimento</label>
    <div class="searchbox">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input id="q" type="search" placeholder="Cerca nome, comune o riferimento…" autocomplete="off" spellcheck="false">
      <button class="search-clear" id="qClear" type="button" aria-label="Cancella la ricerca" hidden>&times;</button>
    </div>
    <div class="toolbar-row">
      <div class="seg-group" id="revSeg" role="group" aria-label="Stato di verifica">
        <button type="button" data-rev="auto" aria-pressed="true">Verificate automaticamente</button>
        <button type="button" data-rev="all" aria-pressed="false">Includi da verificare<span class="n" id="pendingN"></span></button>
      </div>
      <button class="linkbtn" id="helpToggle" type="button" aria-expanded="false" aria-controls="helpBox">Come leggere le corrispondenze</button>
    </div>
    <p class="result-line" id="resultLine" aria-live="polite"></p>
    <p class="caution">Una corrispondenza di nome non implica che l'intitolazione celebri il ruolo coloniale della persona o del luogo.</p>
    <div class="help" id="helpBox" hidden>
      <p><b>Verificate automaticamente</b>: il nome completo o un alias del registro compare nella denominazione. <b>Da verificare</b>: corrispondenze meno sicure (nomi simili, solo cognome non autorizzato), che richiedono un controllo manuale e non sono ancora confermate.</p>
      <dl id="methodHelp"></dl>
    </div>
  </section>
  <div id="activeFilters" class="active-filters"></div>
  <div id="emptyMsg" class="empty card" hidden></div>
  <div class="metrics">
    <div class="metric"><span class="metric-label">Intitolazioni trovate</span><b id="m1">0</b></div>
    <div class="metric"><span class="metric-label">Comuni</span><b id="m2">0</b></div>
    <div class="metric"><span class="metric-label">Riferimenti distinti</span><b id="m3">0</b></div>
    <div class="metric"><span class="metric-label">Regioni</span><b id="m4">0</b></div>
  </div>
  <section class="card" id="mapCard"><div class="card-head"><div><h2>Mappa interattiva</h2><p class="note">I colori distinguono le categorie del registro; la legenda è cliccabile. Passa il cursore sopra un punto per i dettagli, toccalo o cliccalo per aprire la scheda qui sotto. I punti più chiari sono posizioni approssimate (centro del comune).</p></div></div><div id="map"></div><div class="map-note"><span class="status-dot"></span><span id="mapNote"></span></div><div class="detail" id="detail" aria-live="polite"></div></section>
  <section class="card" id="dataCard"><div class="card-head"><div><h2>Dati</h2><p class="note">Clicca un&#8217;intestazione per ordinare, una riga per vederla sulla mappa.</p></div></div><div class="table-wrap"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><div class="table-foot"><span class="note" id="count"></span><button class="mini-btn" id="moreBtn" type="button">Mostra altri</button><button class="mini-btn" id="allBtn" type="button">Mostra tutti</button></div></section>
  <section class="card"><div class="card-head"><div><h2>Differenze regionali</h2><p class="note">Confronta il numero di intitolazioni e la loro diffusione territoriale. «Per 10.000» è normalizzato sul totale della stessa tipologia di sede nella regione.</p></div><div id="metricSeg" class="segmented"><button class="seg" type="button" data-metric="abs" aria-pressed="true">Assoluto</button><button class="seg" type="button" data-metric="norm" aria-pressed="false">Per 10.000 sedi</button><button class="seg" type="button" data-metric="mun" aria-pressed="false">Comuni</button></div></div><div id="regional" role="img" aria-label="Grafico a barre delle differenze regionali"></div></section>
  <div class="grid2"><section class="card"><div class="card-head"><div><h2>Riferimenti più rappresentati</h2><p class="note">Persone, luoghi e battaglie con più intitolazioni.</p></div></div><div id="figures"></div></section><section class="card"><div class="card-head"><div><h2>Categorie</h2><p class="note">Ruoli delle persone e tipologie dei riferimenti geografici.</p></div></div><div id="rolesChart"></div></section></div>
</main>
</div>
</div>

<div id="tab-perche" role="tabpanel" aria-labelledby="tabbtn-perche" hidden>
<div class="page">
  <div class="callout"><b>Perché questi nomi.</b> Una scheda per ogni riferimento del registro curato: chi o cosa è, quale legame con il colonialismo italiano è documentato e quante intitolazioni compaiono nei dati attuali. Le descrizioni sono quelle del registro curato; dove manca la traduzione italiana compare l'originale inglese. Il fatto che un nome compaia non implica che l'intitolazione celebri quel ruolo.</div>
  <div class="ref-tools">
    <div class="searchbox"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><label class="sr" for="pq">Cerca tra i riferimenti</label><input id="pq" type="search" placeholder="Cerca un riferimento…" autocomplete="off"><button class="search-clear" id="pqClear" type="button" aria-label="Cancella la ricerca" hidden>&times;</button></div>
    <div class="seg-group" id="pentSeg" role="group" aria-label="Tipologia"><button type="button" data-ent="" aria-pressed="true">Tutti</button><button type="button" data-ent="person" aria-pressed="false">Persone</button><button type="button" data-ent="place" aria-pressed="false">Luoghi e battaglie</button></div>
    <label class="sr" for="psort">Ordina</label>
    <select id="psort"><option value="count">Più intitolazioni</option><option value="name">Nome A–Z</option></select>
    <span class="note" id="pcount"></span>
  </div>
  <div class="ref-grid" id="refGrid"></div>
</div>
</div>

<div id="tab-politica" role="tabpanel" aria-labelledby="tabbtn-politica" hidden>
<div class="page" id="polRoot"></div>
</div>

<footer>Fonte dati dashboard: __SOURCE__</footer>
<script>
const DATA=__DATA__;
const REGISTRY_CSV=__REGISTRY_CSV__;
const REGISTRY=__REGISTRY_ROWS__;
const POLITICS=__POLITICS__;
const REGION_POLITICS=__REGION_POLITICS__;
const CSV_KEYS=Object.keys(DATA[0]||{});
const PALETTE=['#a4452a','#335d5b','#d39a36','#6f5f91','#44759a','#9c5b6e','#68784f','#b26b3f','#4e7f80','#866f4c','#7a5576','#3d6a54','#9b7344','#516f8b'];
const ROLE_LABELS={military:'Militare',political:'Politico',administration:'Amministrazione coloniale',political_and_administration:'Politica e amministrazione',military_and_administration:'Militare e amministrazione',military_political_administration:'Militare, politica e amministrazione',military_and_religious:'Militare e religioso',economic:'Economia e impresa',economic_and_colonization:'Economia e colonizzazione',political_economic_administration:'Politica, economia e amministrazione',cultural_or_scientific:'Cultura o scienza',religious:'Religioso',exploration_geography:'Esplorazione e geografia',propaganda_or_advocacy:'Propaganda e promozione coloniale',territory:'Territorio / colonia',city_or_locality:'Città o località',battle_or_campaign:'Battaglia / campagna'};
const TERRITORY_LABELS={Libya:'Libia',Ethiopia:'Etiopia',Somalia:'Somalia',Eritrea:'Eritrea','Italian East Africa':'Africa Orientale Italiana',Dodecanese:'Dodecaneso',Albania:'Albania'};
const KIND_LABELS={odonimo:'Vie e piazze',scuola:'Scuole',universita:'Università',luogo_pubblico:'Altri luoghi pubblici'};
const KIND_ORDER=['odonimo','scuola','universita','luogo_pubblico'];
const ENTITY_LABELS={person:'Persona',place:'Luogo / battaglia'};
const METHODS=[
 ['exact_canonical','Nome completo','Il nome completo del riferimento compare nella denominazione.'],
 ['exact_alias','Alias','Compare un nome alternativo registrato (titolo, variante, soprannome).'],
 ['exact_surname','Solo cognome (autorizzato)','Compare il solo cognome, ammesso solo per riferimenti per cui il registro lo consente.'],
 ['exact_initial_name','Iniziale + cognome','Iniziale del nome seguita dal cognome (es. «G. Cognome»).'],
 ['honoree_exact_canonical','Wikidata: dedicato a','Il luogo è collegato su Wikidata alla persona a cui è dedicato.'],
 ['fuzzy_full_or_alias','Nome simile','Corrispondenza approssimata: richiede sempre una verifica manuale.'],
 ['surname_in_name','Solo cognome nel nome','Il cognome compare dentro una denominazione più lunga: poco sicura.']];
const METHOD_LABELS=Object.fromEntries(METHODS.map(m=>[m[0],m[1]]));
const humanize=v=>{const x=String(v||'').replaceAll('_',' ').trim();return x.charAt(0).toUpperCase()+x.slice(1)};
const roleLabel=v=>ROLE_LABELS[v]||humanize(v);
const territoryLabel=v=>TERRITORY_LABELS[v]||v;
const kindLabel=v=>KIND_LABELS[v||'odonimo']||v;
const entityLabel=v=>ENTITY_LABELS[v]||v||'Persona';
const methodLabel=v=>METHOD_LABELS[v]||humanize(v)||'—';
const territoriesText=s=>String(s||'').split(';').map(x=>territoryLabel(x.trim())).filter(Boolean).join('; ');
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const fmt=n=>Number(n).toLocaleString('it-IT');
const fmt1=n=>Number(n).toLocaleString('it-IT',{maximumFractionDigits:1});
const fmt2=n=>Number(n).toLocaleString('it-IT',{maximumFractionDigits:2});
const summaryOf=g=>g.connection_summary_it||g.connection_summary||'';
const safeUrl=u=>/^https?:\/\//i.test(u||'')?u:'';
const $=id=>document.getElementById(id);
const OK_STATUS=['accepted_auto','accepted_manual'];
const kindOf=r=>r.site_kind||'odonimo';
{const reg=new Map(REGISTRY.map(g=>[g.person_id,g]));DATA.forEach(r=>{const g=reg.get(r.person_id);if(g)for(const k of __REGISTRY_ROW_COLUMNS__)if(!(k in r)&&k in g)r[k]=g[k]})}
DATA.forEach((r,i)=>{r._i=i;r.site_kind=r.site_kind||'odonimo';r._ok=!r.review_status||OK_STATUS.includes(r.review_status);r._s=norm([r.odonimo,r.municipality_name,r.canonical_name,r.site_detail].join(' '));});
const PID_BY_NAME={};DATA.forEach(r=>{if(r.canonical_name&&r.person_id)PID_BY_NAME[r.canonical_name]=r.person_id});
const uniq=f=>[...new Set(DATA.map(r=>String(r[f]||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'it'));
const statusText=r=>r._ok?(r.review_status==='accepted_manual'?'Verificata a mano':'Verificata automaticamente'):'Da verificare';
const hasCoords=r=>Number.isFinite(parseFloat(r.lon))&&Number.isFinite(parseFloat(r.lat))&&r.lon!==''&&r.lat!=='';
const precisionShort=r=>r.coord_precision==='municipality_centroid'?'Posizione approssimata (centro del comune)':'';
const precisionFull=r=>({municipality_centroid:'Approssimata: centro del comune',street_median:'Stimata dagli accessi geocodificati della via',point:'Puntuale'})[r.coord_precision]||(hasCoords(r)?'Disponibile':'Non disponibile');

/* ---------- stato ---------- */
const FILTERS={kind:new Set(),entity:new Set(),include:new Set(),exclude:new Set(),regions:new Set(),roles:new Set(),territories:new Set()};
const HASH_PARAM={kind:'sede',entity:'tipo',include:'ref',exclude:'escludi',regions:'regione',roles:'categoria',territories:'territorio'};
let TAB='esplora',METRIC='abs',REVIEW_AUTO=true,QT=[],SELECTED=null,SORT={k:null,dir:1},SHOWN=100,PAGE=100,CARD='',PM='share',PSIZE='all';
let PQ='',PENT='',PSORT='count';
const dirty={esplora:true,perche:true,politica:true};
const cssv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const isDark=()=>document.documentElement.dataset.theme==='dark'||(!document.documentElement.dataset.theme&&matchMedia('(prefers-color-scheme:dark)').matches);
const baseStyle=()=>isDark()?'carto-darkmatter':'carto-positron';

/* ---------- hash ---------- */
function stateToHash(){const p=new URLSearchParams();
 if(TAB!=='esplora')p.set('tab',TAB);
 const q=$('q').value.trim();if(q)p.set('q',q);
 if(!REVIEW_AUTO)p.set('rev','all');
 for(const k in FILTERS)[...FILTERS[k]].forEach(v=>p.append(HASH_PARAM[k],v));
 if(METRIC!=='abs')p.set('metric',METRIC);
 if(PQ)p.set('pq',PQ);if(PENT)p.set('pent',PENT);if(PSORT!=='count')p.set('psort',PSORT);if(CARD)p.set('card',CARD);
 if(PM!=='share')p.set('pm',PM);if(PSIZE!=='all')p.set('psize',PSIZE);
 const th=new URLSearchParams(location.hash.slice(1)).get('theme');if(th)p.set('theme',th);
 return p.toString()}
function syncHash(push){const h=stateToHash();const url=location.pathname+location.search+(h?'#'+h:'');
 try{(push?history.pushState:history.replaceState).call(history,null,'',url)}catch(e){}}
function applyHash(){const p=new URLSearchParams(location.hash.slice(1));
 TAB=['perche','politica'].includes(p.get('tab'))?p.get('tab'):'esplora';
 $('q').value=p.get('q')||'';QT=norm($('q').value).split(' ').filter(Boolean);
 REVIEW_AUTO=p.get('rev')!=='all';
 for(const k in FILTERS){FILTERS[k]=new Set(p.getAll(HASH_PARAM[k]))}
 METRIC=['abs','norm','mun'].includes(p.get('metric'))?p.get('metric'):'abs';
 PQ=p.get('pq')||'';PENT=['person','place'].includes(p.get('pent'))?p.get('pent'):'';PSORT=p.get('psort')==='name'?'name':'count';CARD=p.get('card')||'';
 PM=p.get('pm')==='p10k'?'p10k':'share';PSIZE=p.get('psize')==='big'?'big':'all';
 $('pq').value=PQ;$('psort').value=PSORT;
 document.querySelectorAll('[id^="filter-"]').forEach(h=>h._redraw?.());
 SHOWN=PAGE;
 Object.keys(dirty).forEach(k=>dirty[k]=true);
 showTab(TAB,{noSync:true});}

/* ---------- tab ---------- */
function showTab(t,opts={}){TAB=t;
 document.querySelectorAll('.tab-btn').forEach(b=>{const on=b.dataset.tab===t;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1});
 ['esplora','perche','politica'].forEach(k=>$('tab-'+k).hidden=k!==t);
 draw();
 if(t==='perche'&&CARD){const el=$('ref-'+CARD);if(el){el.scrollIntoView({block:'center'});el.classList.remove('flash');void el.offsetWidth;el.classList.add('flash')}}
 if(!opts.noSync)syncHash(opts.push)}
function draw(){if(!dirty[TAB])return;dirty[TAB]=false;({esplora:renderExplore,perche:renderRefs,politica:renderPolitics})[TAB]()}
function refresh(){dirty.esplora=true;if(TAB==='esplora')draw();syncHash()}
document.querySelectorAll('.tab-btn').forEach(b=>{b.addEventListener('click',()=>{CARD='';showTab(b.dataset.tab,{push:true})});b.addEventListener('keydown',e=>{const bs=[...document.querySelectorAll('.tab-btn')];const i=bs.indexOf(b);const n=e.key==='ArrowRight'?bs[(i+1)%bs.length]:e.key==='ArrowLeft'?bs[(i+bs.length-1)%bs.length]:null;if(n){e.preventDefault();n.focus();n.click()}})});
window.addEventListener('hashchange',applyHash);

/* ---------- filtri ---------- */
function setupPicker(hostId,label,key,values,labelFn=x=>x){
 const host=$(hostId);host.innerHTML=`<div class="filter-label"><span>${label}</span></div><details class="picker"><summary><span class="picker-summary">Tutte</span><span class="picker-count">0</span></summary><div class="picker-menu"><input class="picker-search" type="search" aria-label="Cerca in ${esc(label)}" placeholder="Cerca…"><div class="picker-options"></div><div class="picker-footer"><button class="mini-btn clear" type="button">Azzera</button></div></div></details>`;
 const opts=host.querySelector('.picker-options'),search=host.querySelector('.picker-search'),summary=host.querySelector('.picker-summary'),count=host.querySelector('.picker-count');
 function drawOpts(query=''){const q=norm(query);opts.innerHTML=values.filter(v=>!q||norm(labelFn(v)).includes(q)).map(v=>`<label class="picker-option"><input type="checkbox" value="${esc(v)}" ${FILTERS[key].has(v)?'checked':''}><span>${esc(labelFn(v))}</span></label>`).join('');opts.querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{input.checked?FILTERS[key].add(input.value):FILTERS[key].delete(input.value);updateSummary();SHOWN=PAGE;refresh()}))}
 function updateSummary(){const n=FILTERS[key].size;count.textContent=n;summary.textContent=n?`${n} selezionat${n===1?'o':'i'}`:'Tutte'}
 search.addEventListener('input',()=>drawOpts(search.value));
 host.querySelector('.clear').addEventListener('click',e=>{e.preventDefault();FILTERS[key].clear();drawOpts(search.value);updateSummary();SHOWN=PAGE;refresh()});
 drawOpts();updateSummary();host._redraw=()=>{drawOpts(search.value);updateSummary()};}
setupPicker('filter-kind','Tipo di sede','kind',KIND_ORDER.filter(k=>DATA.some(r=>r.site_kind===k)),kindLabel);
setupPicker('filter-entity','Tipologia','entity',[...new Set(DATA.map(r=>r.entity_type||'person'))],entityLabel);
setupPicker('filter-include','Mostra solo questi riferimenti','include',uniq('canonical_name'));
setupPicker('filter-exclude','Escludi riferimenti','exclude',uniq('canonical_name'));
setupPicker('filter-regions','Regioni','regions',uniq('region_name'));
setupPicker('filter-roles','Categorie','roles',uniq('role_category'),roleLabel);
const TERR=[...new Set(DATA.flatMap(r=>String(r.territories||'').split(';').map(x=>x.trim()).filter(Boolean)))].sort((a,b)=>a.localeCompare(b,'it'));
setupPicker('filter-territories','Territori coloniali','territories',TERR,territoryLabel);
function matches(r,skipReview){
 if(FILTERS.kind.size&&!FILTERS.kind.has(kindOf(r)))return false;
 if(FILTERS.entity.size&&!FILTERS.entity.has(r.entity_type||'person'))return false;
 if(FILTERS.include.size&&!FILTERS.include.has(r.canonical_name))return false;
 if(FILTERS.exclude.has(r.canonical_name))return false;
 if(!skipReview&&REVIEW_AUTO&&!r._ok)return false;
 if(FILTERS.regions.size&&!FILTERS.regions.has(r.region_name))return false;
 if(FILTERS.roles.size&&!FILTERS.roles.has(r.role_category))return false;
 if(FILTERS.territories.size&&!String(r.territories||'').split(';').some(t=>FILTERS.territories.has(t.trim())))return false;
 for(const t of QT)if(!r._s.includes(t))return false;
 return true}
const filtered=()=>DATA.filter(r=>matches(r,false));

/* ---------- esplora ---------- */
const u=(rows,f)=>new Set(rows.map(r=>r[f]).filter(Boolean)).size;
function counts(rows,f){const m={};rows.forEach(r=>{const k=r[f];if(k)m[k]=(m[k]||0)+1});return m}
const BAR_CFG={responsive:true,displayModeBar:false};const short=(t,n=30)=>t.length>n?t.slice(0,n-1)+'…':t;
const plotLayout=extra=>Object.assign({paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Inter, system-ui, sans-serif',color:cssv('--ink'),size:12},margin:{l:120,r:15,t:12,b:42},xaxis:{gridcolor:cssv('--grid'),zeroline:false},yaxis:{gridcolor:'rgba(0,0,0,0)',automargin:true}},extra||{});
function categoryOf(r){return roleLabel(r.role_category||((r.entity_type||'person')==='place'?'city_or_locality':'person'))}
function barChart(id,items,color,tpl,extra){Plotly.react(id,[{type:'bar',orientation:'h',y:items.map(x=>short(x[0],34)),text:items.map(x=>x[0]),textposition:'none',hovertemplate:tpl,x:items.map(x=>x[1]),marker:{color:cssv(color)}}],plotLayout(extra),BAR_CFG)}
function clearFilter(k){if(k==='q'){$('q').value='';QT=[]}else if(k==='rev')REVIEW_AUTO=true;else{FILTERS[k].clear();$('filter-'+({kind:'kind',entity:'entity',include:'include',exclude:'exclude',regions:'regions',roles:'roles',territories:'territories'})[k])._redraw()}SHOWN=PAGE;refresh()}
function renderChips(){const items=[];const add=(label,k,fmtFn=x=>x)=>{if(FILTERS[k].size)items.push([k,`${label}: ${[...FILTERS[k]].map(fmtFn).join(', ')}`])};
 if(QT.length)items.push(['q',`Ricerca: ${$('q').value.trim()}`]);if(!REVIEW_AUTO)items.push(['rev','Incluse le corrispondenze da verificare']);
 add('Sede','kind',kindLabel);add('Tipo','entity',entityLabel);add('Solo','include');add('Esclusi','exclude');add('Regioni','regions');add('Categorie','roles',roleLabel);add('Territori','territories',territoryLabel);
 $('activeFilters').innerHTML=items.map(([k,t])=>`<button type="button" class="active-chip" data-k="${k}" aria-label="Rimuovi filtro: ${esc(t)}"><span>${esc(t)}</span><i aria-hidden="true">&times;</i></button>`).join('');
 $('activeFilters').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>clearFilter(b.dataset.k)));
 const n=items.filter(([k])=>k!=='q'&&k!=='rev').length;$('filtersCount').textContent=n?`${n} attiv${n===1?'o':'i'}`:'Nessun filtro attivo'}
function renderExplore(){
 const base=DATA.filter(r=>matches(r,true));const rows=REVIEW_AUTO?base.filter(r=>r._ok):base;const pending=base.filter(r=>!r._ok).length;
 $('revSeg').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.rev==='auto')===REVIEW_AUTO)));
 $('pendingN').textContent=pending?` (${fmt(pending)})`:'';
 $('qClear').hidden=!$('q').value;
 renderChips();
 $('m1').textContent=fmt(rows.length);$('m2').textContent=fmt(u(rows,'municipality_belfiore'));$('m3').textContent=fmt(u(rows,'person_id'));$('m4').textContent=fmt(u(rows,'region_name'));
 let rl=`<span><b>${fmt(rows.length)}</b> ${rows.length===1?'risultato':'risultati'}</span>`;
 if(REVIEW_AUTO&&pending)rl+=`<span>${fmt(pending)} ${pending===1?'corrispondenza da verificare nascosta':'corrispondenze da verificare nascoste'} <button class="linkbtn" type="button" id="incl">Includi</button></span>`;
 else if(!REVIEW_AUTO&&pending)rl+=`<span>di cui ${fmt(pending)} da verificare</span>`;
 if(rows.length)rl+=`<button class="linkbtn" type="button" id="toTable">Vai alla tabella</button>`;
 $('resultLine').innerHTML=rl;
 $('incl')?.addEventListener('click',()=>setReview(false));$('toTable')?.addEventListener('click',()=>$('dataCard').scrollIntoView({behavior:'smooth'}));
 const em=$('emptyMsg');em.hidden=!!rows.length;
 if(!rows.length){em.innerHTML=(REVIEW_AUTO&&pending?`Nessun risultato tra le corrispondenze verificate, ma ce ne sono ${fmt(pending)} da verificare. <button class="mini-btn" type="button" id="incl2">Mostrale</button>`:'Nessun risultato con i filtri attuali. Controlla l\'ortografia o azzera i filtri.');$('incl2')?.addEventListener('click',()=>setReview(false))}
 /* grafici */
 let rg={};rows.forEach(r=>(rg[r.region_name]??=[]).push(r));
 let vals=Object.entries(rg).filter(([k])=>k).map(([k,v])=>{let x=v.length;if(METRIC==='mun')x=u(v,'municipality_belfiore');if(METRIC==='norm'){const den={};v.forEach(r=>{const kk=kindOf(r);if(!(kk in den)){const t=Number(r.total_kind_region||r.total_odonimi_region);den[kk]=Number.isFinite(t)?t:0}});const t=Object.values(den).reduce((a,b)=>a+b,0);x=t?10000*v.length/t:null}return[k,x]}).filter(x=>x[1]!=null).sort((a,b)=>a[1]-b[1]);
 barChart('regional',vals,'--bar1','%{text}: %{x:,.1f}<extra></extra>',{height:Math.max(360,vals.length*27),margin:{l:10,r:15,t:8,b:40}});
 const fc=Object.entries(counts(rows,'canonical_name')).sort((a,b)=>b[1]-a[1]).slice(0,18).sort((a,b)=>a[1]-b[1]);
 barChart('figures',fc,'--bar2','%{text}: %{x}<extra></extra>',{height:500,margin:{l:10,r:15,t:8,b:40}});
 const rc=Object.entries(counts(rows,'role_category')).map(([k,v])=>[roleLabel(k),v]).sort((a,b)=>a[1]-b[1]);
 barChart('rolesChart',rc,'--bar3','%{text}: %{x}<extra></extra>',{height:500,margin:{l:10,r:15,t:8,b:40}});
 LAST_ROWS=rows;drawMap();renderDetail();renderTable();}
function setReview(auto){REVIEW_AUTO=auto;SHOWN=PAGE;refresh()}
let LAST_ROWS=[],MAP_BOUND=false;
function hoverHtml(r,cat){const L=[`<b>${esc(r.odonimo)}</b>`];
 L.push(esc(kindLabel(kindOf(r))+(r.site_detail?' · '+r.site_detail:'')));
 L.push(esc(r.municipality_name)+' · '+esc(r.region_name));
 L.push(`<b>${esc(r.canonical_name)}</b> · ${esc(entityLabel(r.entity_type||'person'))}`);
 if(r.territories)L.push(esc(territoriesText(r.territories)));
 L.push('Corrispondenza: '+esc(methodLabel(r.match_method)));
 if(!r._ok)L.push('<b>Da verificare</b>');
 const p=precisionShort(r);if(p)L.push('<i>'+p+'</i>');
 L.push(esc(cat));return L.join('<br>')}
function drawMap(){const rows=LAST_ROWS;
 const pts=rows.filter(hasCoords);const groups={};pts.forEach(r=>{(groups[categoryOf(r)]??=[]).push(r)});
 const traces=Object.entries(groups).sort(([a],[b])=>a.localeCompare(b,'it')).map(([cat,g],i)=>({type:'scattermap',mode:'markers',name:cat,lon:g.map(r=>+r.lon),lat:g.map(r=>+r.lat),customdata:g.map(r=>r._i),text:g.map(r=>hoverHtml(r,cat)),hoverinfo:'text',marker:{size:g.map(r=>r.coord_precision==='municipality_centroid'?9:11),opacity:g.map(r=>r.coord_precision==='municipality_centroid'?.38:.86),color:PALETTE[i%PALETTE.length]}}));
 traces.push({type:'scattermap',mode:'markers',name:'Selezione',showlegend:false,hoverinfo:'skip',lon:SELECTED&&hasCoords(SELECTED)?[+SELECTED.lon]:[],lat:SELECTED&&hasCoords(SELECTED)?[+SELECTED.lat]:[],marker:{size:26,opacity:.3,color:cssv('--ink')}});
 Plotly.react('map',traces,{uirevision:'map',map:{style:baseStyle(),center:{lat:42.4,lon:12.5},zoom:4.45},paper_bgcolor:'rgba(0,0,0,0)',margin:{l:0,r:0,t:0,b:70},legend:{orientation:'h',yanchor:'top',y:-0.01,x:0,tracegroupgap:2,itemsizing:'constant',bgcolor:cssv('--aside'),font:{size:10,color:cssv('--ink')}}},{responsive:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d']}).then(()=>{
  if(!MAP_BOUND){MAP_BOUND=true;$('map').on('plotly_click',e=>{const p=e.points&&e.points[0];if(p&&p.customdata!=null)selectRow(DATA[p.customdata],{zoom:false})})}});
 const approx=pts.filter(r=>r.coord_precision==='municipality_centroid').length;
 $('mapNote').textContent=`${fmt(pts.length)} dei ${fmt(rows.length)} intitolazioni filtrate hanno coordinate`+(approx?`; ${fmt(approx)} approssimate al centro del comune (punti più chiari).`:'.')}
function selectRow(r,opts={}){SELECTED=r;renderDetail();drawMap();
 document.querySelectorAll('#tbody tr').forEach(tr=>tr.classList.toggle('sel',+tr.dataset.i===r._i));
 if(opts.zoom&&hasCoords(r)){const z=r.coord_precision==='municipality_centroid'?11:r.coord_precision==='point'?16:15;Plotly.relayout('map',{'map.center':{lat:+r.lat,lon:+r.lon},'map.zoom':z})}
 if(opts.scroll)$('mapCard').scrollIntoView({behavior:'smooth',block:'start'})}
function renderDetail(){const d=$('detail'),r=SELECTED;
 if(!r){d.innerHTML='<p class="hint">Clicca un punto sulla mappa o una riga della tabella per vedere i dettagli e il motivo della corrispondenza.</p>';return}
 const reg=REGISTRY.find(x=>x.person_id===r.person_id);const src=reg&&safeUrl(reg.source_url);
 d.innerHTML=`<div class="detail-head"><div><h3>${esc(r.odonimo)}</h3><p class="sub">${esc(kindLabel(kindOf(r)))}${r.site_detail?' · '+esc(r.site_detail):''} · ${esc(r.municipality_name)} (${esc(r.region_name)})</p></div><button class="mini-btn" type="button" id="detailClose" aria-label="Chiudi la scheda">Chiudi</button></div>
 <dl><dt>Riferimento</dt><dd>${r.person_id?`<a href="#tab=perche&card=${encodeURIComponent(r.person_id)}" data-card="${esc(r.person_id)}">${esc(r.canonical_name)}</a>`:esc(r.canonical_name)} · ${esc(entityLabel(r.entity_type||'person'))}${r.role_category?' · '+esc(roleLabel(r.role_category)):''}</dd>
 <dt>Corrispondenza</dt><dd>${esc(methodLabel(r.match_method))} ${r._ok?'':'<span class="flag">da verificare</span>'}</dd>
 <dt>Stato</dt><dd>${esc(statusText(r))}</dd>
 <dt>Posizione</dt><dd>${esc(precisionFull(r))}</dd>${src?`<dt>Fonte del riferimento</dt><dd><a href="${esc(src)}" target="_blank" rel="noopener noreferrer">Fonte</a></dd>`:''}</dl>`;
 $('detailClose').addEventListener('click',()=>{SELECTED=null;renderDetail();drawMap();document.querySelectorAll('#tbody tr.sel').forEach(t=>t.classList.remove('sel'))});
 bindCardLinks(d)}
function bindCardLinks(root){root.querySelectorAll('a[data-card]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();goToCard(a.dataset.card)}))}
function goToCard(pid){CARD=pid;PQ='';$('pq').value='';PENT='';dirty.perche=true;showTab('perche',{push:true})}
/* tabella */
const COLS=[['site_kind','Sede',r=>kindLabel(kindOf(r))],['odonimo','Denominazione',r=>r.odonimo],['site_detail','Dettaglio',r=>r.site_detail],['municipality_name','Comune',r=>r.municipality_name],['region_name','Regione',r=>r.region_name],['canonical_name','Riferimento',r=>r.canonical_name],['entity_type','Tipo',r=>entityLabel(r.entity_type||'person')],['role_category','Categoria',r=>roleLabel(r.role_category)],['territories','Territorio',r=>territoriesText(r.territories)],['match_method','Corrispondenza',r=>methodLabel(r.match_method)],['_ok','Stato',r=>r._ok?'Verificata':'Da verificare']];
function cellHtml(k,r){
 if(k==='site_kind')return`<td><span class="kind-tag">${esc(kindLabel(kindOf(r)))}</span></td>`;
 if(k==='canonical_name')return`<td>${r.person_id?`<a href="#tab=perche&card=${encodeURIComponent(r.person_id)}" data-card="${esc(r.person_id)}" title="Perché questo nome">${esc(r.canonical_name)}</a>`:esc(r.canonical_name)}</td>`;
 if(k==='_ok')return`<td>${r._ok?'<span class="ok-tag">Verificata</span>':'<span class="flag">da verificare</span>'}</td>`;
 const v=COLS.find(c=>c[0]===k)[2](r)||'';return`<td title="${esc(v)}">${esc(v)}</td>`}
function renderTable(){const rows=LAST_ROWS.slice();
 const cols=COLS.filter(([k])=>k!=='site_detail'||rows.some(r=>r.site_detail));
 if(SORT.k){const f=COLS.find(c=>c[0]===SORT.k)[2];const key=SORT.k==='_ok'?(r=>r._ok?1:0):f;rows.sort((a,b)=>{const x=key(a),y=key(b);return(typeof x==='number'?x-y:String(x||'').localeCompare(String(y||''),'it',{numeric:true}))*SORT.dir})}
 $('thead').innerHTML='<tr>'+cols.map(([k,l])=>`<th scope="col" data-k="${k}" aria-sort="${SORT.k===k?(SORT.dir>0?'ascending':'descending'):'none'}"><button type="button" aria-label="Ordina per ${esc(l)}">${esc(l)}</button></th>`).join('')+'</tr>';
 $('thead').querySelectorAll('th').forEach(th=>th.querySelector('button').addEventListener('click',()=>{const k=th.dataset.k;SORT=SORT.k===k?(SORT.dir>0?{k,dir:-1}:{k:null,dir:1}):{k,dir:1};renderTable()}));
 const shown=rows.slice(0,SHOWN);
 $('tbody').innerHTML=shown.map(r=>`<tr data-i="${r._i}" tabindex="0" class="${SELECTED&&SELECTED._i===r._i?'sel':''}">`+cols.map(([k])=>cellHtml(k,r)).join('')+'</tr>').join('');
 $('tbody').querySelectorAll('tr').forEach(tr=>{const act=()=>selectRow(DATA[+tr.dataset.i],{zoom:true,scroll:true});tr.addEventListener('click',act);tr.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target===tr)act()})});
 bindCardLinks($('tbody'));
 $('count').textContent=rows.length?`${fmt(Math.min(SHOWN,rows.length))} di ${fmt(rows.length)} record.`:'Nessun record.';
 $('moreBtn').hidden=$('allBtn').hidden=rows.length<=SHOWN;$('moreBtn').textContent=`Mostra altri ${Math.min(PAGE,rows.length-SHOWN)}`}
$('moreBtn').addEventListener('click',()=>{SHOWN+=PAGE;renderTable()});$('allBtn').addEventListener('click',()=>{SHOWN=1e9;renderTable()});
/* download */
function csvText(rows){if(!rows.length)return'';const q=value=>{let v=String(value??'');if(/[",\n\r]/.test(v))v='"'+v.replaceAll('"','""')+'"';return v};return [CSV_KEYS.join(','),...rows.map(r=>CSV_KEYS.map(k=>q(r[k])).join(','))].join('\n')}
function download(name,text){const a=document.createElement('a');const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}

/* ---------- perché questi nomi ---------- */
$('methodHelp').innerHTML=METHODS.map(m=>`<dt>${esc(m[1])}</dt><dd>${esc(m[2])}</dd>`).join('');
function refCounts(){const m={};DATA.forEach(r=>{if(!r.person_id)return;const c=m[r.person_id]??={ok:0,pending:0};r._ok?c.ok++:c.pending++});return m}
function renderRefs(){const C=refCounts();const q=norm(PQ).split(' ').filter(Boolean);
 $('pentSeg').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ent===PENT)));$('pqClear').hidden=!PQ;
 let list=REGISTRY.map(g=>({g,c:C[g.person_id]||{ok:0,pending:0},s:norm([g.canonical_name,g.aliases,summaryOf(g),territoriesText(g.territories),roleLabel(g.role_category),g.period].join(' '))}))
  .filter(x=>(!PENT||(x.g.entity_type||'person')===PENT)&&q.every(t=>x.s.includes(t)));
 list.sort((a,b)=>PSORT==='name'?a.g.canonical_name.localeCompare(b.g.canonical_name,'it'):((b.c.ok+b.c.pending)-(a.c.ok+a.c.pending))||a.g.canonical_name.localeCompare(b.g.canonical_name,'it'));
 $('pcount').textContent=`${fmt(list.length)} di ${fmt(REGISTRY.length)} riferimenti`;
 $('refGrid').innerHTML=list.length?list.map(({g,c})=>{const tot=c.ok+c.pending;const src=safeUrl(g.source_url);const terr=territoriesText(g.territories);
  return`<article class="ref-card" id="ref-${esc(g.person_id)}"><h3>${esc(g.canonical_name)}</h3><div class="ref-tags"><span class="kind-tag">${esc(entityLabel(g.entity_type||'person'))}</span><span class="kind-tag">${esc(roleLabel(g.role_category))}</span></div>
  ${(terr||g.period)?`<p class="ref-meta">${esc([terr,g.period].filter(Boolean).join(' · '))}</p>`:''}
  <p class="ref-sum">${esc(summaryOf(g))}</p>
  <div class="ref-foot"><span class="cnt">${tot?`<b>${fmt(c.ok)}</b> intitolazioni verificate`+(c.pending?` · <b>${fmt(c.pending)}</b> <span class="flag">da verificare</span>`:''):'Nessuna intitolazione nei dati attuali'}</span>${src?`<a href="${esc(src)}" target="_blank" rel="noopener noreferrer">Fonte</a>`:''}<button class="mini-btn" type="button" data-show="${esc(g.person_id)}" ${tot?'':'disabled'}>Mostra sulla mappa</button></div></article>`}).join(''):'<div class="empty card">Nessun riferimento corrisponde alla ricerca.</div>';
 $('refGrid').querySelectorAll('[data-show]').forEach(b=>b.addEventListener('click',()=>showOnMap(b.dataset.show)))}
function showOnMap(pid){const g=REGISTRY.find(x=>x.person_id===pid);if(!g)return;const c=refCounts()[pid]||{ok:0,pending:0};
 Object.values(FILTERS).forEach(s=>s.clear());FILTERS.include.add(g.canonical_name);$('q').value='';QT=[];REVIEW_AUTO=!(c.ok===0&&c.pending>0);SHOWN=PAGE;CARD='';
 document.querySelectorAll('[id^="filter-"]').forEach(h=>h._redraw?.());dirty.esplora=true;showTab('esplora',{push:true});$('mapCard').scrollIntoView({behavior:'smooth'})}
let pqT;$('pq').addEventListener('input',()=>{PQ=$('pq').value.trim();CARD='';clearTimeout(pqT);pqT=setTimeout(()=>{dirty.perche=true;draw();syncHash()},120)});
$('pqClear').addEventListener('click',()=>{$('pq').value='';PQ='';dirty.perche=true;draw();syncHash();$('pq').focus()});
$('psort').addEventListener('change',()=>{PSORT=$('psort').value;CARD='';dirty.perche=true;draw();syncHash()});
$('pentSeg').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{PENT=b.dataset.ent;CARD='';dirty.perche=true;draw();syncHash()}));

/* ---------- politica ---------- */
const FAMILIES=['centrodestra','centrosinistra','m5s','altro','civica','n.d.'];
const FAMILY_LABELS={centrodestra:'Centrodestra',centrosinistra:'Centrosinistra',m5s:'Movimento 5 Stelle',civica:'Liste civiche (senza partito)',altro:'Altro','n.d.':'Dato non disponibile'};
const COALITIONS=['centrodestra','centrosinistra','altro','n.d.'];
const FAMILY_COLORS={centrodestra:'#44759a',centrosinistra:'#a4452a',m5s:'#d39a36',civica:'#97a09c',altro:'#6f5f91','n.d.':'#c4c8c6'};
const famOf=v=>{v=String(v||'').trim().toLowerCase();return FAMILIES.includes(v)?v:'n.d.'};
const coalOf=v=>{v=String(v||'').trim().toLowerCase();return COALITIONS.includes(v)?v:'n.d.'};
const pct=x=>fmt1(100*x)+'%';
function polMunicipal(){const byCode=new Map();POLITICS.forEach(p=>byCode.set(String(p.municipality_istat||'').padStart(6,'0'),p));
 const cnt=new Map(),streets=new Map();const outside=new Set();
 DATA.forEach(r=>{if(!r._ok)return;const p=byCode.get(r.municipality_istat_y);if(!p){outside.add(r.municipality_belfiore||r.municipality_name);return}cnt.set(p,(cnt.get(p)||0)+1);if(kindOf(r)==='odonimo')streets.set(p,(streets.get(p)||0)+1)});
 const nOd=p=>Number(p.n_odonimi)||0;const hasN=POLITICS.some(p=>nOd(p)>0);
 let thr=0;if(hasN){const ns=POLITICS.map(nOd).filter(n=>n>0).sort((a,b)=>a-b);thr=ns[Math.floor(ns.length*2/3)]}
 const pool=PSIZE==='big'&&hasN?POLITICS.filter(p=>nOd(p)>=thr):POLITICS;
 const g={};FAMILIES.forEach(f=>g[f]={f,n:0,withAny:0,total:0,streets:0,odo:0});
 pool.forEach(p=>{const x=g[famOf(p.party_family)];x.n++;const c=cnt.get(p)||0;if(c)x.withAny++;x.total+=c;x.streets+=streets.get(p)||0;x.odo+=nOd(p)});
 return{groups:FAMILIES.map(f=>g[f]).filter(x=>x.n),outside:outside.size,matched:[...cnt.keys()].length,hasN,thr,poolN:pool.length}}
function polRegional(){const per={};
 DATA.forEach(r=>{const k=r.region_name;if(!k)return;const x=per[k]??={region:k,ok:0,den:{}};if(r._ok)x.ok++;const kk=kindOf(r);if(!(kk in x.den)){const t=Number(r.total_kind_region||r.total_odonimi_region);x.den[kk]=Number.isFinite(t)?t:0}});
 const pol=new Map((REGION_POLITICS||[]).map(p=>[norm(p.region_name),p]));
 const regions=Object.values(per).map(x=>{const total=Object.values(x.den).reduce((a,b)=>a+b,0);const p=pol.get(norm(x.region));return{region:x.region,ok:x.ok,total,per10k:total?10000*x.ok/total:null,coal:coalOf(p&&p.coalition),president:p?p.president:'',src:p?safeUrl(p.source_url):''}}).filter(x=>x.per10k!=null);
 const g={};COALITIONS.forEach(c=>g[c]={c,n:0,ok:0,total:0});regions.forEach(x=>{const y=g[x.coal];y.n++;y.ok+=x.ok;y.total+=x.total});
 return{regions:regions.sort((a,b)=>b.per10k-a.per10k),groups:COALITIONS.map(c=>g[c]).filter(x=>x.n)}}
function renderPolitics(){const root=$('polRoot');
 const caveat=`<div class="callout"><b>Come leggere questi dati.</b> La maggior parte dei nomi è stata assegnata decenni fa, spesso in epoca coloniale o fascista. L'amministrazione attuale indica quindi chi governa oggi luoghi che conservano questi nomi, <b>non chi li ha scelti</b>. Il confronto è descrittivo: mostra correlazioni, non cause. Le liste civiche non sono attribuite a nessun partito. Sono conteggiate solo le corrispondenze verificate.</div>`;
 if(!POLITICS&&!REGION_POLITICS){root.innerHTML=caveat+`<section class="card"><div class="empty">Dati non ancora disponibili. Questa sezione si attiva quando in <code>data/processed</code> sono presenti <code>municipality_politics.csv</code> (sindaci) e, per il confronto regionale, <code>region_politics.csv</code> (presidenti di Regione).</div></section>`;return}
 let html=caveat;
 if(POLITICS){const m=polMunicipal();
  const pm=PM==='p10k'&&!m.hasN?'share':PM;
  html+=`<section class="card"><div class="card-head"><div><h2>Comuni, per famiglia politica del sindaco</h2><p class="note">${fmt(POLITICS.length)} comuni con dato politico; ${fmt(m.matched)} hanno almeno una intitolazione verificata nei dati.${m.outside?` ${fmt(m.outside)} comuni con intitolazioni non hanno un dato politico corrispondente.`:''} Le liste civiche e i comuni senza dato non sono partiti: sono in grigio. Il confronto grezzo risente della dimensione del comune (le liste civiche prevalgono nei comuni piccoli, che hanno meno vie).${m.hasN?'':' Il totale degli odonimi per comune non è disponibile: è mostrata solo la quota di comuni.'}</p></div>
  <div style="display:grid;gap:8px;justify-items:end"><div class="segmented" id="pmSeg"><button class="seg" type="button" data-pm="share" aria-pressed="${pm==='share'}">Quota con almeno una</button>${m.hasN?`<button class="seg" type="button" data-pm="p10k" aria-pressed="${pm==='p10k'}">Per 10.000 odonimi</button>`:''}</div>
  ${m.hasN?`<div class="segmented" id="psizeSeg" role="group" aria-label="Dimensione dei comuni"><button class="seg" type="button" data-size="all" aria-pressed="${PSIZE==='all'}">Tutti i comuni</button><button class="seg" type="button" data-size="big" aria-pressed="${PSIZE==='big'}">Solo comuni grandi (terzo superiore per odonimi)</button></div>`:''}</div></div>
  ${PSIZE==='big'&&m.hasN?`<p class="note" style="margin:0 0 8px">Comuni grandi: almeno ${fmt(m.thr)} odonimi (${fmt(m.poolN)} comuni).</p>`:''}
  <div id="polChart" role="img" aria-label="Grafico per famiglia politica del sindaco"></div>
  <div class="table-wrap" style="max-height:none"><table class="pol-table"><thead><tr><th scope="col">Famiglia politica</th><th class="num" scope="col">Comuni</th><th class="num" scope="col">Con almeno una</th><th class="num" scope="col">Quota</th><th class="num" scope="col">Intitolazioni (vie)</th>${m.hasN?'<th class="num" scope="col">Per 10.000 odonimi</th>':''}</tr></thead><tbody>${m.groups.map(x=>`<tr><td>${esc(FAMILY_LABELS[x.f])}</td><td class="num">${fmt(x.n)}</td><td class="num">${fmt(x.withAny)}</td><td class="num">${pct(x.withAny/x.n)}</td><td class="num">${fmt(x.streets)}</td>${m.hasN?`<td class="num">${x.odo?fmt1(10000*x.streets/x.odo):'—'}</td>`:''}</tr>`).join('')}</tbody></table></div></section>`}
 if(REGION_POLITICS){html+=`<section class="card"><div class="card-head"><div><h2>Regioni, per coalizione del presidente</h2><p class="note">Intitolazioni verificate ogni 10.000 sedi della stessa tipologia nella regione, con il colore della coalizione che governa oggi la Regione.</p></div></div><div id="polRegChart" role="img" aria-label="Grafico regionale per coalizione"></div><div id="polRegTable"></div></section>`}
 html+=`<p class="note" style="margin:0">Fonti: Ministero dell'Interno, Anagrafe degli amministratori locali e regionali (in carica al 24/08/2026); per alcune coalizioni e per i presidenti di Campania e Marche, Wikipedia. I link alle fonti sono nei CSV <code>municipality_politics.csv</code> e <code>region_politics.csv</code>.</p>`;
 root.innerHTML=html;
  if(POLITICS){const m=polMunicipal();const pm=PM==='p10k'&&!m.hasN?'share':PM;
  const items=m.groups.filter(x=>pm==='share'||x.odo).map(x=>({y:`${FAMILY_LABELS[x.f]} (${fmt(x.n)} comuni)`,x:pm==='share'?100*x.withAny/x.n:10000*x.streets/x.odo,f:x.f,n:x.n,withAny:x.withAny,streets:x.streets})).reverse();
  Plotly.react('polChart',[{type:'bar',orientation:'h',y:items.map(i=>i.y),x:items.map(i=>i.x),marker:{color:items.map(i=>FAMILY_COLORS[i.f])},text:items.map(i=>fmt1(i.x)+(pm==='share'?'%':'')),textposition:'outside',cliponaxis:false,hovertext:items.map(i=>pm==='share'?`${i.withAny} su ${i.n} comuni`:`${i.streets} intitolazioni in ${i.n} comuni`),hoverinfo:'text'}],plotLayout({height:Math.max(260,items.length*52+60),margin:{l:10,r:50,t:8,b:40},xaxis:{gridcolor:cssv('--grid'),zeroline:false,title:{text:pm==='share'?'% di comuni con almeno una intitolazione verificata':'intitolazioni verificate (vie e piazze) ogni 10.000 odonimi'}}}),BAR_CFG);
  $('pmSeg').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{PM=b.dataset.pm;dirty.politica=true;draw();syncHash()}));
  $('psizeSeg')?.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{PSIZE=b.dataset.size;dirty.politica=true;draw();syncHash()}))}
 if(REGION_POLITICS){const R=polRegional();const byC=c=>R.regions.filter(x=>x.coal===c);
  const traces=COALITIONS.filter(c=>byC(c).length).map(c=>{const rs=byC(c).slice().reverse();return{type:'bar',orientation:'h',name:FAMILY_LABELS[c]||c,y:rs.map(x=>x.region),x:rs.map(x=>x.per10k),marker:{color:FAMILY_COLORS[c]},hovertext:rs.map(x=>`${x.region}: ${fmt1(x.per10k)} per 10.000 (${x.ok} intitolazioni)`),hoverinfo:'text'}});
  const order=R.regions.map(x=>x.region).reverse();
  Plotly.react('polRegChart',traces,plotLayout({height:Math.max(360,R.regions.length*27+60),barmode:'stack',margin:{l:10,r:15,t:8,b:40},yaxis:{categoryorder:'array',categoryarray:order,automargin:true},legend:{orientation:'h',y:-0.08},xaxis:{gridcolor:cssv('--grid'),zeroline:false,title:{text:'per 10.000 sedi'}}}),BAR_CFG);
  $('polRegTable').innerHTML=`<div class="table-wrap" style="max-height:none;margin-top:12px"><table class="pol-table"><thead><tr><th scope="col">Coalizione</th><th class="num" scope="col">Regioni</th><th class="num" scope="col">Intitolazioni verificate</th><th class="num" scope="col">Per 10.000 sedi</th></tr></thead><tbody>${R.groups.map(x=>`<tr><td>${esc(FAMILY_LABELS[x.c]||x.c)}</td><td class="num">${fmt(x.n)}</td><td class="num">${fmt(x.ok)}</td><td class="num">${x.total?fmt1(10000*x.ok/x.total):'—'}</td></tr>`).join('')}</tbody></table></div>
  <div class="table-wrap" style="max-height:420px;margin-top:12px"><table class="pol-table"><thead><tr><th scope="col">Regione</th><th scope="col">Presidente</th><th scope="col">Coalizione</th><th class="num" scope="col">Intitolazioni</th><th class="num" scope="col">Per 10.000</th></tr></thead><tbody>${R.regions.map(x=>`<tr><td>${esc(x.region)}</td><td>${x.src?`<a href="${esc(x.src)}" target="_blank" rel="noopener noreferrer">${esc(x.president||'Fonte')}</a>`:esc(x.president||'—')}</td><td>${esc(FAMILY_LABELS[x.coal]||x.coal)}</td><td class="num">${fmt(x.ok)}</td><td class="num">${fmt1(x.per10k)}</td></tr>`).join('')}</tbody></table></div>`}}

/* ---------- eventi globali ---------- */
let qT;$('q').addEventListener('input',()=>{QT=norm($('q').value).split(' ').filter(Boolean);$('qClear').hidden=!$('q').value;SHOWN=PAGE;clearTimeout(qT);qT=setTimeout(refresh,140)});
$('q').addEventListener('keydown',e=>{if(e.key==='Enter'){clearTimeout(qT);refresh();$('dataCard').scrollIntoView({behavior:'smooth'})}});
$('qClear').addEventListener('click',()=>{$('q').value='';QT=[];SHOWN=PAGE;refresh();$('q').focus()});
$('revSeg').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>setReview(b.dataset.rev==='auto')));
$('helpToggle').addEventListener('click',()=>{const h=$('helpBox');h.hidden=!h.hidden;$('helpToggle').setAttribute('aria-expanded',String(!h.hidden))});
$('filtersToggle').addEventListener('click',()=>{const c=$('filters').classList.toggle('collapsed');$('filtersToggle').setAttribute('aria-expanded',String(!c))});
$('themeBtn').addEventListener('click',()=>{const d=document.documentElement;d.dataset.theme=isDark()?'light':'dark';try{localStorage.setItem('theme',d.dataset.theme)}catch(e){}
 const p=new URLSearchParams(location.hash.slice(1));if(p.has('theme')){p.set('theme',d.dataset.theme);try{history.replaceState(null,'',location.pathname+location.search+'#'+p.toString())}catch(e){}}
 Object.keys(dirty).forEach(k=>dirty[k]=true);draw()});
document.querySelectorAll('#metricSeg .seg').forEach(btn=>btn.addEventListener('click',()=>{METRIC=btn.dataset.metric;document.querySelectorAll('#metricSeg .seg').forEach(x=>x.setAttribute('aria-pressed',String(x===btn)));refresh()}));
$('reset').addEventListener('click',()=>{Object.values(FILTERS).forEach(s=>s.clear());document.querySelectorAll('[id^="filter-"]').forEach(h=>h._redraw?.());$('q').value='';QT=[];REVIEW_AUTO=true;SHOWN=PAGE;refresh()});
$('downloadData').addEventListener('click',()=>download('toponimi_coloniali_filtrati.csv',csvText(filtered())));
$('downloadRegistry').addEventListener('click',()=>download('registro_matching_utilizzato.csv',REGISTRY_CSV));
applyHash();
</script>
</body></html>'''


def build_html(
    rows: list[dict[str, str]],
    registry_csv: str,
    source: str,
    registry_rows: list[dict[str, str]] | None = None,
    politics: list[dict[str, str]] | None = None,
    region_politics: list[dict[str, str]] | None = None,
) -> str:
    if registry_rows is None:
        registry_rows = list(csv.DictReader(registry_csv.splitlines()))
    by_id = {r.get("person_id"): r for r in registry_rows}
    rows = [
        {
            k: v
            for k, v in row.items()
            if not (k in REGISTRY_ROW_COLUMNS and v == by_id.get(row.get("person_id"), {}).get(k))
        }
        for row in rows
    ]
    replacements = {
        "__SOURCE__": source.replace("&", "&amp;").replace("<", "&lt;"),
        "__DATA__": js(rows),
        "__REGISTRY_CSV__": js(registry_csv),
        "__REGISTRY_ROWS__": js(registry_rows),
        "__REGISTRY_ROW_COLUMNS__": js(REGISTRY_ROW_COLUMNS),
        "__POLITICS__": js(politics),
        "__REGION_POLITICS__": js(region_politics),
    }
    html = TEMPLATE
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera la dashboard statica per GitHub Pages.")
    ap.add_argument("--data")
    ap.add_argument("--registry", default="data/processed/people_registry_used.csv")
    ap.add_argument("--politics", default=str(POLITICS_DEFAULT), help="CSV facoltativo: sindaci per comune")
    ap.add_argument("--region-politics", default=str(REGION_POLITICS_DEFAULT), help="CSV facoltativo: presidenti di Regione")
    ap.add_argument("--output-dir", default="docs")
    ap.add_argument("--allow-empty", action="store_true")
    args = ap.parse_args()

    data_path = Path(args.data) if args.data else next((p for p in DATA_DEFAULTS if p.exists()), None)
    if data_path is None:
        if not args.allow_empty:
            raise FileNotFoundError("Nessun CSV elaborato trovato")
        rows, source = [], "dati elaborati non ancora pubblicati"
    else:
        rows, source = load_rows(data_path), str(data_path)

    registry = Path(args.registry)
    if not registry.exists() and args.allow_empty:
        registry = Path("data/manual/people_registry.csv")
    if not registry.exists():
        raise FileNotFoundError(f"Registro non trovato: {registry}")
    registry_csv = registry.read_text(encoding="utf-8-sig")
    registry_rows = load_rows(registry)

    politics = load_optional(Path(args.politics), POLITICS_COLUMNS)
    region_politics = load_optional(Path(args.region_politics), REGION_POLITICS_COLUMNS)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "index.html").write_text(
        build_html(rows, registry_csv, source, registry_rows, politics, region_politics),
        encoding="utf-8",
    )
    print(
        f"Dashboard statica generata: {out / 'index.html'} "
        f"(politica comuni: {'sì' if politics is not None else 'no'}, regioni: {'sì' if region_politics is not None else 'no'})"
    )


if __name__ == "__main__":
    main()
