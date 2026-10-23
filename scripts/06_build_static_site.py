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


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(f)]


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def build_html(rows: list[dict[str, str]], registry_csv: str, source: str) -> str:
    return f'''<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<meta name="color-scheme" content="light dark">
<title>Toponimi coloniali italiani</title>
<script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
<style>
:root {{
  --ink:#18201f; --muted:#66706d; --paper:#f4efe6; --card:var(--card);
  --line:#ddd5c7; --accent:#a4452a; --accent2:#335d5b; --accent3:#d9a441;
  --navy:#1f3032; --shadow:0 16px 45px rgba(30,38,35,.08);
  --surface:#fff; --line2:#d9d1c4; --line3:#b5a793; --hover:#f5f0e7; --zebra:#fcfaf6; --chip:#eef0ec; --chip2:#e1e6e1;
  --ink2:#37534f; --bg1:#e8dfd1; --aside:rgba(255,253,248,.92); --grid:#e9e2d8; --bar1:#335d5b; --bar2:#a4452a; --bar3:#d09a3a; --focus:#1d6f6b;
}}
:root[data-theme="dark"]{{
  color-scheme:dark;
  --ink:#e8ece9; --muted:#a6b1ad; --paper:#141b1b; --card:#1c2625; --line:#2f3d3b; --accent:#e07a5c; --accent2:#6fb0aa;
  --navy:#3b6866; --shadow:0 16px 45px rgba(0,0,0,.35);
  --surface:#232f2e; --line2:#3a4b49; --line3:#5b7471; --hover:#2a3836; --zebra:#202b2a; --chip:#2a3736; --chip2:#364644;
  --ink2:#c4d6d2; --bg1:#0f1515; --aside:rgba(28,38,37,.92); --grid:#2f3d3b; --bar1:#6fb0aa; --bar2:#e07a5c; --bar3:#e0b45a; --focus:#7fd0c9;
}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  color-scheme:dark;
  --ink:#e8ece9; --muted:#a6b1ad; --paper:#141b1b; --card:#1c2625; --line:#2f3d3b; --accent:#e07a5c; --accent2:#6fb0aa;
  --navy:#3b6866; --shadow:0 16px 45px rgba(0,0,0,.35);
  --surface:#232f2e; --line2:#3a4b49; --line3:#5b7471; --hover:#2a3836; --zebra:#202b2a; --chip:#2a3736; --chip2:#364644;
  --ink2:#c4d6d2; --bg1:#0f1515; --aside:rgba(28,38,37,.92); --grid:#2f3d3b; --bar1:#6fb0aa; --bar2:#e07a5c; --bar3:#e0b45a; --focus:#7fd0c9;
}}}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
body{{margin:0;background:linear-gradient(180deg,var(--bg1) 0,var(--paper) 280px,var(--paper) 100%);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.hero{{background:radial-gradient(circle at 85% 10%,rgba(217,164,65,.23),transparent 32%),linear-gradient(135deg,#172729,#294847);color:#fff;padding:42px max(28px,calc((100vw - 1500px)/2)) 34px;border-bottom:1px solid rgba(255,255,255,.12)}}
.eyebrow{{text-transform:uppercase;letter-spacing:.16em;font-size:.74rem;font-weight:800;color:#e4c47f;margin-bottom:12px}}
.hero h1{{font-family:Georgia,"Times New Roman",serif;font-size:clamp(2.15rem,4vw,4.3rem);line-height:.98;margin:0 0 18px;max-width:950px;font-weight:600}}
.hero p{{max-width:970px;color:#dae1de;font-size:1.02rem;line-height:1.65;margin:0}}
.hero .badges{{display:flex;flex-wrap:wrap;gap:9px;margin-top:22px}} .badge{{border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.07);padding:7px 11px;border-radius:999px;font-size:.78rem;color:#eef1ef}}
.shell{{max-width:1500px;margin:0 auto;padding:26px 28px 48px;display:grid;grid-template-columns:315px minmax(0,1fr);gap:22px}}
aside{{position:sticky;top:16px;align-self:start;background:var(--aside);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:var(--shadow);max-height:calc(100vh - 32px);overflow:auto}}
aside h2{{font-family:Georgia,serif;font-weight:600;margin:2px 0 4px;font-size:1.55rem}} .filter-intro{{color:var(--muted);font-size:.82rem;line-height:1.45;margin:0 0 15px}}
.filter-label{{display:flex;justify-content:space-between;align-items:center;font-weight:760;font-size:.82rem;margin:14px 0 6px;color:var(--ink)}}
.picker{{border:1px solid var(--line2);border-radius:12px;background:var(--surface)}} .picker[open]{{border-color:var(--line3);box-shadow:0 9px 28px rgba(38,45,43,.09)}}
.picker summary{{list-style:none;cursor:pointer;padding:10px 11px;display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:.84rem;color:var(--ink)}} .picker summary::-webkit-details-marker{{display:none}}
.picker-summary{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}} .picker-count{{min-width:24px;text-align:center;background:var(--chip);border-radius:999px;padding:2px 7px;font-size:.72rem;font-weight:800;color:var(--ink2)}}
.picker-menu{{border-top:1px solid var(--line);padding:9px}} .picker-search{{width:100%;border:1px solid var(--line2);border-radius:9px;padding:8px 9px;font:inherit;font-size:.82rem;outline:none;background:var(--zebra);color:var(--ink)}} .picker-search:focus{{border-color:#7d9892;box-shadow:0 0 0 3px rgba(51,93,91,.10)}}
.picker-options{{max-height:210px;overflow:auto;padding:5px 1px}} .picker-option{{display:flex;align-items:flex-start;gap:8px;padding:7px 6px;border-radius:8px;font-size:.81rem;line-height:1.25;cursor:pointer}} .picker-option:hover{{background:var(--hover)}} .picker-option input{{margin-top:2px;accent-color:var(--accent2)}}
.picker-footer{{display:flex;gap:7px;padding-top:6px}} .mini-btn{{border:0;border-radius:9px;padding:7px 9px;background:var(--chip);color:var(--ink);font-size:.76rem;font-weight:750;cursor:pointer}} .mini-btn:hover{{background:var(--chip2)}}
.toggle-row{{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--line2);background:var(--surface);border-radius:12px;padding:10px 11px;margin-top:13px;font-size:.82rem;font-weight:700}} .toggle-row input{{width:18px;height:18px;accent-color:var(--accent2)}}
.actions{{display:grid;gap:8px;margin-top:16px}} button.action{{border:0;border-radius:11px;padding:10px 12px;font:inherit;font-size:.81rem;font-weight:780;cursor:pointer;text-align:left}} button.primary{{background:var(--navy);color:#fff}} button.secondary{{background:var(--chip);color:var(--ink)}} button.action:focus-visible,.seg:focus-visible,.mini-btn:focus-visible,.picker summary:focus-visible,.theme-btn:focus-visible,input:focus-visible{{outline:2px solid var(--focus);outline-offset:2px}} button.action:hover{{filter:brightness(.98);transform:translateY(-1px)}}
main{{min-width:0}} .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}} .metric{{background:var(--card);border:1px solid var(--line);border-radius:17px;padding:16px 17px;box-shadow:0 8px 28px rgba(45,50,45,.04)}} .metric-label{{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800}} .metric b{{font-family:Georgia,serif;font-size:2.05rem;font-weight:600;display:block;margin-top:5px;color:var(--ink)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:19px;padding:18px;margin-bottom:14px;box-shadow:0 8px 28px rgba(45,50,45,.045)}} .card-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:8px}} .card h2{{font-family:Georgia,serif;font-weight:600;font-size:1.38rem;margin:0}} .card p.note{{color:var(--muted);font-size:.8rem;margin:4px 0 0;line-height:1.45}}
.segmented{{display:flex;flex-wrap:wrap;gap:6px}} .seg{{border:1px solid var(--line2);background:var(--chip);border-radius:999px;padding:6px 9px;font-size:.74rem;font-weight:700;color:var(--ink2);cursor:pointer}} .seg.active{{background:#294847;color:#fff;border-color:#294847}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} #map{{height:670px;border-radius:14px;overflow:hidden}} .map-note{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:var(--muted);font-size:.78rem;margin-top:9px}}
.status-dot{{width:8px;height:8px;border-radius:50%;background:#4c8b6f;display:inline-block}} .active-filters{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}} .active-chip{{background:var(--chip);border:1px solid var(--line2);border-radius:999px;padding:5px 9px;font-size:.73rem;color:var(--ink2)}}
.table-wrap{{overflow:auto;max-height:610px;border:1px solid var(--line);border-radius:12px}} table{{min-width:980px;border-collapse:separate;border-spacing:0;width:100%;font-size:.78rem;background:var(--surface)}} th{{position:sticky;top:0;background:#203536;color:#fff;text-align:left;padding:9px 10px;font-size:.72rem;letter-spacing:.03em;z-index:2}} td{{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}} tr:nth-child(even) td{{background:var(--zebra)}} tr:hover td{{background:var(--hover)}}
footer{{max-width:1500px;margin:0 auto;padding:0 28px 36px;color:var(--muted);font-size:.76rem}}
.theme-btn{{position:absolute;top:16px;right:20px;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.08);color:#fff;border-radius:999px;padding:6px 12px;font:inherit;font-size:.76rem;font-weight:700;cursor:pointer}} .hero{{position:relative}}
.filters-toggle{{display:none;width:100%;margin-bottom:12px;border:1px solid var(--line2);background:var(--card);color:var(--ink);border-radius:13px;padding:12px 14px;font:inherit;font-weight:780;font-size:.9rem;cursor:pointer;text-align:left;justify-content:space-between;align-items:center}}
.metric small{{display:block;color:var(--muted);font-size:.72rem;margin-top:2px}} .kind-tag{{display:inline-block;border-radius:999px;padding:1px 8px;font-size:.7rem;font-weight:700;background:var(--chip);color:var(--ink2)}} .empty{{padding:26px;text-align:center;color:var(--muted);font-size:.88rem}}
@media(max-width:1100px){{.shell{{grid-template-columns:1fr}}aside{{position:static;max-height:none}}.filters-toggle{{display:flex}}aside.collapsed{{display:none}}.metrics{{grid-template-columns:1fr 1fr}}}}
@media(max-width:760px){{.shell{{padding:16px 12px 34px}}.hero{{padding:34px 18px 30px}}.grid2{{grid-template-columns:1fr}}.metrics{{grid-template-columns:1fr 1fr}}#map{{height:540px}}}}
</style>
</head>
<body>
<section class="hero">
  <button class="theme-btn" id="themeBtn" type="button" aria-label="Cambia tema chiaro/scuro">Tema</button>
  <div class="eyebrow">Atlante della memoria coloniale</div>
  <h1>Toponimi italiani legati al colonialismo</h1>
  <p>Una mappa esplorativa delle intitolazioni (vie, piazze, scuole, università e altri luoghi pubblici) associate a persone, territori, città e battaglie con un legame documentato con il colonialismo italiano. La corrispondenza nominale non implica automaticamente che l'intitolazione sia stata deliberata per celebrare quello specifico ruolo storico.</p>
  <div class="badges"><span class="badge">ANNCSU · odonimi ufficiali</span><span class="badge">Scuole e università</span><span class="badge">Registro curato manualmente</span><span class="badge">Filtri interattivi</span></div>
</section>
<div class="shell">
<button class="filters-toggle" id="filtersToggle" type="button" aria-expanded="false" aria-controls="filters"><span>Filtri</span><span id="filtersCount">Nessun filtro attivo</span></button>
<aside id="filters" class="collapsed" aria-label="Filtri">
  <h2>Esplora</h2><p class="filter-intro">Apri un filtro e seleziona le voci. I risultati si aggiornano subito; ogni pannello ha il pulsante Azzera.</p>
  <div id="filter-kind"></div>
  <div id="filter-entity"></div>
  <div id="filter-include"></div>
  <div id="filter-exclude"></div>
  <div class="toggle-row"><span>Solo corrispondenze accettate</span><input id="accepted" type="checkbox" checked></div>
  <div id="filter-regions"></div>
  <div id="filter-roles"></div>
  <div id="filter-territories"></div>
  <div class="actions">
    <button id="reset" class="action secondary">↺ Azzera tutti i filtri</button>
    <button id="downloadData" class="action primary">↓ Scarica il CSV filtrato</button>
    <button id="downloadRegistry" class="action secondary">↓ Scarica il registro usato nel matching</button>
  </div>
</aside>
<main>
  <div id="activeFilters" class="active-filters"></div>
  <div id="emptyMsg" class="empty card" hidden>Nessun risultato con i filtri attuali. Prova ad azzerarli o a includere anche le corrispondenze non accettate.</div>
  <div class="metrics">
    <div class="metric"><span class="metric-label">Intitolazioni trovate</span><b id="m1">0</b></div>
    <div class="metric"><span class="metric-label">Comuni</span><b id="m2">0</b></div>
    <div class="metric"><span class="metric-label">Riferimenti distinti</span><b id="m3">0</b></div>
    <div class="metric"><span class="metric-label">Regioni</span><b id="m4">0</b></div>
  </div>
  <section class="card"><div class="card-head"><div><h2>Differenze regionali</h2><p class="note">Confronta il numero di intitolazioni e la loro diffusione territoriale. «Per 10.000» è normalizzato sul totale della stessa tipologia di sede nella regione.</p></div><div id="metricSeg" class="segmented"><button class="seg active" data-metric="abs">Assoluto</button><button class="seg" data-metric="norm">Per 10.000 sedi</button><button class="seg" data-metric="mun">Comuni</button></div></div><div id="regional" role="img" aria-label="Grafico a barre delle differenze regionali"></div></section>
  <div class="grid2"><section class="card"><div class="card-head"><div><h2>Riferimenti più rappresentati</h2><p class="note">Persone, luoghi e battaglie con più intitolazioni.</p></div></div><div id="figures"></div></section><section class="card"><div class="card-head"><div><h2>Categorie</h2><p class="note">Ruoli delle persone e tipologie dei riferimenti geografici.</p></div></div><div id="rolesChart"></div></section></div>
  <section class="card"><div class="card-head"><div><h2>Mappa interattiva</h2><p class="note">I colori distinguono le categorie del registro; la legenda è cliccabile. Passa il cursore (o tocca) un punto per vedere nome, tipologia e comune.</p></div></div><div id="map"></div><div class="map-note"><span class="status-dot"></span><span id="mapNote"></span></div></section>
  <section class="card"><div class="card-head"><div><h2>Dati</h2><p class="note">Anteprima dei primi 1.500 record dopo l'applicazione dei filtri.</p></div></div><div class="table-wrap"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><p class="note" id="count"></p></section>
</main>
</div>
<footer>Fonte dati dashboard: {source}</footer>
<script>
const DATA={js(rows)};
const REGISTRY={js(registry_csv)};
const PALETTE=['#a4452a','#335d5b','#d39a36','#6f5f91','#44759a','#9c5b6e','#68784f','#b26b3f','#4e7f80','#866f4c','#7a5576','#3d6a54','#9b7344','#516f8b'];
const ROLE_LABELS={{military:'Militare',political:'Politico',administration:'Amministrazione coloniale',political_and_administration:'Politica e amministrazione',military_and_administration:'Militare e amministrazione',military_political_administration:'Militare, politica e amministrazione',military_and_religious:'Militare e religioso',economic:'Economia e impresa',economic_and_colonization:'Economia e colonizzazione',political_economic_administration:'Politica, economia e amministrazione',cultural_or_scientific:'Cultura o scienza',religious:'Religioso',exploration_geography:'Esplorazione e geografia',propaganda_or_advocacy:'Propaganda e promozione coloniale',territory:'Territorio / colonia',city_or_locality:'Città o località',battle_or_campaign:'Battaglia / campagna'}};
const TERRITORY_LABELS={{Libya:'Libia',Ethiopia:'Etiopia',Somalia:'Somalia',Eritrea:'Eritrea','Italian East Africa':'Africa Orientale Italiana',Dodecanese:'Dodecaneso',Albania:'Albania'}};
const KIND_LABELS={{odonimo:'Vie e piazze',scuola:'Scuole',universita:'Università',luogo_pubblico:'Altri luoghi pubblici'}};
const KIND_ORDER=['odonimo','scuola','universita','luogo_pubblico'];
const kindOf=r=>r.site_kind||'odonimo';
const kindLabel=v=>KIND_LABELS[v||'odonimo']||v;
const ENTITY_LABELS={{person:'Persona',place:'Luogo / battaglia'}};
const roleLabel=v=>ROLE_LABELS[v]||(x=>x.charAt(0).toUpperCase()+x.slice(1))(String(v||'').replaceAll('_',' '));
const territoryLabel=v=>TERRITORY_LABELS[v]||v;
const entityLabel=v=>ENTITY_LABELS[v]||v||'Persona';
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const uniq=f=>[...new Set(DATA.map(r=>String(r[f]||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'it'));
DATA.forEach(r=>{{if(!r.site_kind)r.site_kind='odonimo'}});
const FILTERS={{kind:new Set(),entity:new Set(),include:new Set(),exclude:new Set(),regions:new Set(),roles:new Set(),territories:new Set()}};
let METRIC='abs';
function setupPicker(hostId,label,key,values,labelFn=x=>x){{
 const host=document.getElementById(hostId); host.innerHTML=`<div class="filter-label"><span>${{label}}</span></div><details class="picker"><summary><span class="picker-summary">Tutte</span><span class="picker-count">0</span></summary><div class="picker-menu"><input class="picker-search" type="search" placeholder="Cerca…"><div class="picker-options"></div><div class="picker-footer"><button class="mini-btn clear">Azzera</button></div></div></details>`;
 const opts=host.querySelector('.picker-options'), search=host.querySelector('.picker-search'), summary=host.querySelector('.picker-summary'), count=host.querySelector('.picker-count');
 function draw(query=''){{const q=query.trim().toLocaleLowerCase('it');opts.innerHTML=values.filter(v=>!q||String(labelFn(v)).toLocaleLowerCase('it').includes(q)).map(v=>`<label class="picker-option"><input type="checkbox" value="${{esc(v)}}" ${{FILTERS[key].has(v)?'checked':''}}><span>${{esc(labelFn(v))}}</span></label>`).join('');opts.querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{{input.checked?FILTERS[key].add(input.value):FILTERS[key].delete(input.value); updateSummary(); render();}}));}}
 function updateSummary(){{const n=FILTERS[key].size; count.textContent=n; summary.textContent=n?`${{n}} selezionat${{n===1?'o':'i'}}`:'Tutte';}}
 search.addEventListener('input',()=>draw(search.value)); host.querySelector('.clear').addEventListener('click',e=>{{e.preventDefault();FILTERS[key].clear();draw(search.value);updateSummary();render();}}); draw(); updateSummary();
 host._redraw=()=>{{draw(search.value);updateSummary();}};
}}
setupPicker('filter-kind','Tipo di sede','kind',KIND_ORDER.filter(k=>DATA.some(r=>r.site_kind===k)),kindLabel);
const entities=uniq('entity_type').map(x=>x||'person');
setupPicker('filter-entity','Tipologia','entity',entities,entityLabel);
setupPicker('filter-include','Mostra solo questi riferimenti','include',uniq('canonical_name'));
setupPicker('filter-exclude','Escludi riferimenti','exclude',uniq('canonical_name'));
setupPicker('filter-regions','Regioni','regions',uniq('region_name'));
setupPicker('filter-roles','Categorie','roles',uniq('role_category'),roleLabel);
const terr=[...new Set(DATA.flatMap(r=>String(r.territories||'').split(';').map(x=>x.trim()).filter(Boolean)))].sort((a,b)=>a.localeCompare(b,'it'));
setupPicker('filter-territories','Territori coloniali','territories',terr,territoryLabel);
function filtered(){{const acc=document.getElementById('accepted').checked;return DATA.filter(r=>{{if(FILTERS.kind.size&&!FILTERS.kind.has(kindOf(r)))return false;const et=r.entity_type||'person';if(FILTERS.entity.size&&!FILTERS.entity.has(et))return false;if(FILTERS.include.size&&!FILTERS.include.has(r.canonical_name))return false;if(FILTERS.exclude.has(r.canonical_name))return false;if(acc&&r.review_status&&!['accepted_auto','accepted_manual'].includes(r.review_status))return false;if(FILTERS.regions.size&&!FILTERS.regions.has(r.region_name))return false;if(FILTERS.roles.size&&!FILTERS.roles.has(r.role_category))return false;if(FILTERS.territories.size&&!String(r.territories||'').split(';').some(t=>FILTERS.territories.has(t.trim())))return false;return true}})}}
const u=(rows,f)=>new Set(rows.map(r=>r[f]).filter(Boolean)).size;
function counts(rows,f){{const m={{}};rows.forEach(r=>{{const k=r[f];if(k)m[k]=(m[k]||0)+1}});return m}}
const cssv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const BAR_CFG={{responsive:true,displayModeBar:false}};const short=(t,n=30)=>t.length>n?t.slice(0,n-1)+'…':t;
const isDark=()=>document.documentElement.dataset.theme==='dark'||(!document.documentElement.dataset.theme&&matchMedia('(prefers-color-scheme:dark)').matches);
const baseStyle=()=>{{const d=isDark();return{{version:8,sources:{{b:{{type:'raster',tileSize:256,tiles:['https://basemaps.cartocdn.com/'+(d?'dark_all':'light_all')+'/{{z}}/{{x}}/{{y}}.png'],attribution:'© OpenStreetMap, © CARTO'}}}},layers:[{{id:'bg',type:'background',paint:{{'background-color':d?'#1a2423':'#e9ece6'}}}},{{id:'b',type:'raster',source:'b'}}]}}}};
const plotLayout=extra=>Object.assign({{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{{family:'Inter, system-ui, sans-serif',color:cssv('--ink'),size:12}},margin:{{l:120,r:15,t:12,b:42}},xaxis:{{gridcolor:cssv('--grid'),zeroline:false}},yaxis:{{gridcolor:'rgba(0,0,0,0)',automargin:true}}}},extra||{{}});
function categoryOf(r){{return roleLabel(r.role_category||((r.entity_type||'person')==='place'?'city_or_locality':'person'))}}
function renderActiveFilters(){{const items=[];const add=(label,set,fmt=x=>x)=>{{if(set.size)items.push(`${{label}}: ${{[...set].map(fmt).join(', ')}}`)}};add('Sede',FILTERS.kind,kindLabel);add('Tipo',FILTERS.entity,entityLabel);add('Solo',FILTERS.include);add('Esclusi',FILTERS.exclude);add('Regioni',FILTERS.regions);add('Categorie',FILTERS.roles,roleLabel);add('Territori',FILTERS.territories,territoryLabel);activeFilters.innerHTML=items.map(x=>`<span class="active-chip">${{esc(x)}}</span>`).join('');const n=items.length+(document.getElementById('accepted').checked?0:1);filtersCount.textContent=n?`${{n}} attiv${{n===1?'o':'i'}}`:'Nessun filtro attivo'}}
function render(){{const rows=filtered();renderActiveFilters();m1.textContent=rows.length.toLocaleString('it-IT');m2.textContent=u(rows,'municipality_belfiore').toLocaleString('it-IT');m3.textContent=u(rows,'person_id').toLocaleString('it-IT');m4.textContent=u(rows,'region_name').toLocaleString('it-IT');
 const noData=!rows.length;document.getElementById('emptyMsg').hidden=!noData;let rg={{}};rows.forEach(r=>(rg[r.region_name]??=[]).push(r));let vals=Object.entries(rg).filter(([k])=>k).map(([k,v])=>{{let x=v.length;if(METRIC==='mun')x=u(v,'municipality_belfiore');if(METRIC==='norm'){{const den={{}};v.forEach(r=>{{const k=kindOf(r);if(!(k in den)){{const t=Number(r.total_kind_region||r.total_odonimi_region);den[k]=Number.isFinite(t)?t:0}}}});const t=Object.values(den).reduce((a,b)=>a+b,0);x=t?10000*v.length/t:null}}return[k,x]}}).filter(x=>x[1]!=null).sort((a,b)=>a[1]-b[1]);Plotly.react('regional',[{{type:'bar',orientation:'h',y:vals.map(x=>short(x[0])),text:vals.map(x=>x[0]),textposition:'none',hovertemplate:'%{{text}}: %{{x:,.1f}}<extra></extra>',x:vals.map(x=>x[1]),marker:{{color:cssv('--bar1')}}}}],plotLayout({{height:Math.max(360,vals.length*27),margin:{{l:10,r:15,t:8,b:40}}}}),BAR_CFG);
 let fc=Object.entries(counts(rows,'canonical_name')).sort((a,b)=>b[1]-a[1]).slice(0,18).sort((a,b)=>a[1]-b[1]);Plotly.react('figures',[{{type:'bar',orientation:'h',y:fc.map(x=>short(x[0])),text:fc.map(x=>x[0]),textposition:'none',hovertemplate:'%{{text}}: %{{x}}<extra></extra>',x:fc.map(x=>x[1]),marker:{{color:cssv('--bar2')}}}}],plotLayout({{height:500,margin:{{l:10,r:15,t:8,b:40}}}}),BAR_CFG);
 let rc=Object.entries(counts(rows,'role_category')).map(([k,v])=>[roleLabel(k),v]).sort((a,b)=>a[1]-b[1]);Plotly.react('rolesChart',[{{type:'bar',orientation:'h',y:rc.map(x=>short(x[0],34)),text:rc.map(x=>x[0]),textposition:'none',hovertemplate:'%{{text}}: %{{x}}<extra></extra>',x:rc.map(x=>x[1]),marker:{{color:cssv('--bar3')}}}}],plotLayout({{height:500,margin:{{l:10,r:15,t:8,b:40}}}}),BAR_CFG);
 let pts=rows.map(r=>[Number(r.lon),Number(r.lat),r]).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));const groups={{}};pts.forEach(x=>{{const c=categoryOf(x[2]);(groups[c]??=[]).push(x)}});const traces=Object.entries(groups).sort(([a],[b])=>a.localeCompare(b,'it')).map(([cat,g],i)=>({{type:'scattermap',mode:'markers',name:cat,lon:g.map(x=>x[0]),lat:g.map(x=>x[1]),customdata:g.map(x=>[x[2].odonimo,x[2].municipality_name,x[2].region_name,x[2].canonical_name,entityLabel(x[2].entity_type||'person'),territoryLabel(x[2].territories||''),kindLabel(kindOf(x[2]))+(x[2].site_detail?' · '+x[2].site_detail:'')]),hovertemplate:'<b>%{{customdata[0]}}</b><br>%{{customdata[6]}}<br>%{{customdata[1]}} · %{{customdata[2]}}<br><b>%{{customdata[3]}}</b> · %{{customdata[4]}}<br>%{{customdata[5]}}<extra>'+cat+'</extra>',marker:{{size:11,opacity:.86,color:PALETTE[i%PALETTE.length]}}}}));Plotly.react('map',traces,{{map:{{style:baseStyle(),center:{{lat:42.4,lon:12.5}},zoom:4.45}},paper_bgcolor:'rgba(0,0,0,0)',margin:{{l:0,r:0,t:0,b:70}},height:670,legend:{{orientation:'h',yanchor:'top',y:-0.01,x:0,tracegroupgap:2,itemsizing:'constant',bgcolor:cssv('--aside'),font:{{size:10,color:cssv('--ink')}}}}}},{{responsive:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d']}});mapNote.textContent=`${{pts.length.toLocaleString('it-IT')}} dei ${{rows.length.toLocaleString('it-IT')}} intitolazioni filtrate dispongono di coordinate rappresentative.`;
 const cols0=[['site_kind','Sede'],['odonimo','Denominazione'],['site_detail','Dettaglio'],['municipality_name','Comune'],['region_name','Regione'],['canonical_name','Riferimento'],['entity_type','Tipo'],['role_category','Categoria'],['territories','Territorio'],['match_method','Matching']];const cols=cols0.filter(([k])=>k!=='site_detail'||rows.some(r=>r.site_detail));thead.innerHTML='<tr>'+cols.map(x=>`<th>${{x[1]}}</th>`).join('')+'</tr>';tbody.innerHTML=rows.slice(0,1500).map(r=>'<tr>'+cols.map(([k])=>{{let v=r[k]||'';if(k==='site_kind')return`<td><span class="kind-tag">${{esc(kindLabel(kindOf(r)))}}</span></td>`;if(k==='role_category')v=roleLabel(v);if(k==='entity_type')v=entityLabel(v||'person');if(k==='territories')v=String(v).split(';').map(x=>territoryLabel(x.trim())).join('; ');return`<td>${{esc(v)}}</td>`}}).join('')+'</tr>').join('');count.textContent=`${{rows.length.toLocaleString('it-IT')}} record dopo i filtri.`;}}
function csvText(rows){{if(!rows.length)return'';const h=Object.keys(DATA[0]);const q=value=>{{let v=String(value??'');if(v.includes(',')||v.includes('"')||v.includes('\\n'))v='"'+v.replaceAll('"','""')+'"';return v}};return [h.join(','),...rows.map(r=>h.map(k=>q(r[k])).join(','))].join('\\n')}}
function download(name,text){{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([text],{{type:'text/csv;charset=utf-8'}}));a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}}
document.getElementById('accepted').addEventListener('change',render);
filtersToggle.addEventListener('click',()=>{{const c=filters.classList.toggle('collapsed');filtersToggle.setAttribute('aria-expanded',String(!c))}});
themeBtn.addEventListener('click',()=>{{const d=document.documentElement;const dark=d.dataset.theme==='dark'||(!d.dataset.theme&&matchMedia('(prefers-color-scheme:dark)').matches);d.dataset.theme=dark?'light':'dark';try{{localStorage.setItem('theme',d.dataset.theme)}}catch(e){{}}render()}});
document.querySelectorAll('#metricSeg .seg').forEach(btn=>btn.addEventListener('click',()=>{{METRIC=btn.dataset.metric;document.querySelectorAll('#metricSeg .seg').forEach(x=>x.classList.toggle('active',x===btn));render()}}));
reset.addEventListener('click',()=>{{Object.values(FILTERS).forEach(s=>s.clear());document.querySelectorAll('[id^="filter-"]').forEach(h=>h._redraw?.());accepted.checked=true;render()}});downloadData.addEventListener('click',()=>download('toponimi_coloniali_filtrati.csv',csvText(filtered())));downloadRegistry.addEventListener('click',()=>download('registro_matching_utilizzato.csv',REGISTRY));render();
</script>
</body></html>'''


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera la dashboard statica per GitHub Pages.")
    ap.add_argument("--data")
    ap.add_argument("--registry", default="data/processed/people_registry_used.csv")
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

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "index.html").write_text(
        build_html(rows, registry.read_text(encoding="utf-8-sig"), source),
        encoding="utf-8",
    )
    print(f"Dashboard statica generata: {out / 'index.html'}")


if __name__ == "__main__":
    main()
