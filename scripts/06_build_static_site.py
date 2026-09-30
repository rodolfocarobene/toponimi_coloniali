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
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Toponimi coloniali italiani</title>
<script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
<style>
body{{font-family:system-ui,sans-serif;margin:0;color:#17171c}}header{{padding:24px 30px 8px}}header p{{color:#666;max-width:1100px}}
.layout{{display:grid;grid-template-columns:300px 1fr;gap:18px;padding:18px 30px 40px}}aside{{background:#f6f6f7;border:1px solid #ddd;border-radius:10px;padding:16px;align-self:start;position:sticky;top:10px}}
label{{display:block;font-weight:600;font-size:.88rem;margin:12px 0 5px}}select,button{{width:100%;font:inherit}}select{{min-height:38px}}select[multiple]{{min-height:110px}}button{{margin-top:8px;padding:9px}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.metric,.card{{border:1px solid #ddd;border-radius:10px;padding:12px;margin-bottom:12px}}.metric b{{font-size:1.7rem}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
#map{{height:650px}}table{{border-collapse:collapse;width:100%;font-size:.82rem}}th,td{{border-bottom:1px solid #eee;padding:6px;text-align:left;white-space:nowrap}}.table{{overflow:auto;max-height:600px}}
@media(max-width:900px){{.layout{{grid-template-columns:1fr}}aside{{position:static}}.grid2{{grid-template-columns:1fr}}.metrics{{grid-template-columns:1fr 1fr}}}}
</style>
</head><body>
<header><h1>Toponimi italiani legati al colonialismo</h1><p>Dashboard di ricerca. Una corrispondenza indica che l'odonimo è associato a una figura presente nel registro curato; non dimostra, da sola, che il comune abbia scelto il nome specificamente per celebrarne il ruolo coloniale.</p></header>
<div class="layout"><aside><h2>Filtri</h2>
<label>Mostra solo queste figure</label><select id="include" multiple></select>
<label>Escludi queste figure</label><select id="exclude" multiple></select>
<label><input id="accepted" type="checkbox" checked style="width:auto"> Solo corrispondenze accettate</label>
<label>Regioni</label><select id="regions" multiple></select>
<label>Categorie di ruolo</label><select id="roles" multiple></select>
<label>Territori coloniali</label><select id="territories" multiple></select>
<label>Metrica regionale</label><select id="metric"><option value="abs">Odonimi trovati (valore assoluto)</option><option value="norm">Per 10.000 odonimi ANNCSU</option><option value="mun">Comuni con almeno una corrispondenza</option></select>
<button id="reset">Azzera filtri</button><button id="downloadData">Scarica il CSV filtrato</button><button id="downloadRegistry">Scarica il registro dei nomi usato per il matching</button>
</aside><main>
<div class="metrics"><div class="metric">Odonimi trovati<br><b id="m1">0</b></div><div class="metric">Comuni<br><b id="m2">0</b></div><div class="metric">Figure rappresentate<br><b id="m3">0</b></div><div class="metric">Regioni<br><b id="m4">0</b></div></div>
<div class="card"><h2>Differenze regionali</h2><div id="regional"></div></div>
<div class="grid2"><div class="card"><h2>Figure più rappresentate</h2><div id="figures"></div></div><div class="card"><h2>Categorie di ruolo</h2><div id="rolesChart"></div></div></div>
<div class="card"><h2>Mappa interattiva</h2><div id="map"></div><small id="mapNote"></small></div>
<div class="card"><h2>Dati</h2><div class="table"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><small id="count"></small></div>
<small>Fonte dati dashboard: {source}</small>
</main></div>
<script>
const DATA={js(rows)}; const REGISTRY={js(registry_csv)};
const roleLabel=v=>String(v||'').replaceAll('_',' '); const territoryLabel=v=>({{Libya:'Libia',Ethiopia:'Etiopia',Somalia:'Somalia',Eritrea:'Eritrea','Italian East Africa':'Africa Orientale Italiana'}}[v]||v);
const uniq=f=>[...new Set(DATA.map(r=>String(r[f]||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'it'));
const selected=id=>[...document.getElementById(id).selectedOptions].map(o=>o.value);
function fill(id,vals,label=x=>x){{const e=document.getElementById(id);e.innerHTML=vals.map(v=>`<option value="${{v.replaceAll('&','&amp;').replaceAll('"','&quot;')}}">${{label(v)}}</option>`).join('')}}
fill('include',uniq('canonical_name')); fill('exclude',uniq('canonical_name')); fill('regions',uniq('region_name')); fill('roles',uniq('role_category'),roleLabel);
const terr=[...new Set(DATA.flatMap(r=>String(r.territories||'').split(';').map(x=>x.trim()).filter(Boolean)))].sort(); fill('territories',terr,territoryLabel);
function filt(){{const inc=new Set(selected('include')),exc=new Set(selected('exclude')),reg=new Set(selected('regions')),roles=new Set(selected('roles')),terr=new Set(selected('territories')),acc=document.getElementById('accepted').checked;return DATA.filter(r=>{{if(inc.size&&!inc.has(r.canonical_name))return false;if(exc.has(r.canonical_name))return false;if(acc&&r.review_status&&!['accepted_auto','accepted_manual'].includes(r.review_status))return false;if(reg.size&&!reg.has(r.region_name))return false;if(roles.size&&!roles.has(r.role_category))return false;if(terr.size&&!String(r.territories||'').split(';').some(t=>terr.has(t.trim())))return false;return true}})}}
const u=(rows,f)=>new Set(rows.map(r=>r[f]).filter(Boolean)).size;
function counts(rows,f){{const m={{}};rows.forEach(r=>{{const k=r[f];if(k)m[k]=(m[k]||0)+1}});return m}}
function render(){{const rows=filt();m1.textContent=rows.length.toLocaleString('it-IT');m2.textContent=u(rows,'municipality_belfiore').toLocaleString('it-IT');m3.textContent=u(rows,'person_id').toLocaleString('it-IT');m4.textContent=u(rows,'region_name').toLocaleString('it-IT');
let rg={{}};rows.forEach(r=>(rg[r.region_name]??=[]).push(r));let vals=Object.entries(rg).filter(([k])=>k).map(([k,v])=>{{let x=v.length;if(metric.value==='mun')x=u(v,'municipality_belfiore');if(metric.value==='norm'){{const t=Number(v[0].total_odonimi_region);x=t?10000*v.length/t:null}}return[k,x]}}).filter(x=>x[1]!=null).sort((a,b)=>a[1]-b[1]);Plotly.react('regional',[{{type:'bar',orientation:'h',y:vals.map(x=>x[0]),x:vals.map(x=>x[1])}}],{{margin:{{l:130,t:10}}}},{{responsive:true,displaylogo:false}});
let fc=Object.entries(counts(rows,'canonical_name')).sort((a,b)=>b[1]-a[1]).slice(0,20).sort((a,b)=>a[1]-b[1]);Plotly.react('figures',[{{type:'bar',orientation:'h',y:fc.map(x=>x[0]),x:fc.map(x=>x[1])}}],{{margin:{{l:150,t:10}},height:480}},{{responsive:true,displaylogo:false}});
let rc=Object.entries(counts(rows,'role_category')).map(([k,v])=>[roleLabel(k),v]).sort((a,b)=>a[1]-b[1]);Plotly.react('rolesChart',[{{type:'bar',orientation:'h',y:rc.map(x=>x[0]),x:rc.map(x=>x[1])}}],{{margin:{{l:160,t:10}},height:480}},{{responsive:true,displaylogo:false}});
let pts=rows.map(r=>[Number(r.lon),Number(r.lat),r]).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));Plotly.react('map',[{{type:'scattermap',mode:'markers',lon:pts.map(x=>x[0]),lat:pts.map(x=>x[1]),text:pts.map(x=>`${{x[2].odonimo}}<br>${{x[2].municipality_name}}<br>${{x[2].canonical_name}}`),hoverinfo:'text',marker:{{size:12,opacity:.85}}}}],{{map:{{style:'open-street-map',center:{{lat:42.5,lon:12.5}},zoom:4.5}},margin:{{l:0,r:0,t:0,b:0}},height:650}},{{responsive:true,displaylogo:false}});mapNote.textContent=`${{pts.length}} dei ${{rows.length}} odonimi filtrati dispongono di coordinate rappresentative.`;
const cols=['odonimo','municipality_name','province_name','region_name','canonical_name','role_category','territories','match_method','match_score','review_status'];thead.innerHTML='<tr>'+cols.map(c=>`<th>${{c}}</th>`).join('')+'</tr>';tbody.innerHTML=rows.slice(0,1500).map(r=>'<tr>'+cols.map(c=>`<td>${{String(r[c]||'')}}</td>`).join('')+'</tr>').join('');count.textContent=`${{rows.length}} record`;}}
function csv(rows){{if(!rows.length)return'';const h=Object.keys(DATA[0]);const q=v=>{{v=String(v??'');const needsQuotes=v.includes(',')||v.includes('"')||v.includes('\\n');return needsQuotes?'"'+v.replaceAll('"','""')+'"':v}};return[h.join(','),...rows.map(r=>h.map(k=>q(r[k])).join(','))].join('\\n')}}
function dl(name,text){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{{type:'text/csv;charset=utf-8'}}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}}
['include','exclude','regions','roles','territories','metric','accepted'].forEach(id=>document.getElementById(id).addEventListener('change',render));reset.onclick=()=>{{['include','exclude','regions','roles','territories'].forEach(id=>[...document.getElementById(id).options].forEach(o=>o.selected=false));accepted.checked=true;metric.value='abs';render()}};downloadData.onclick=()=>dl('toponimi_coloniali_filtrati.csv',csv(filt()));downloadRegistry.onclick=()=>dl('registro_nomi_utilizzato.csv',REGISTRY);render();
</script></body></html>'''


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
    (out / "index.html").write_text(build_html(rows, registry.read_text(encoding="utf-8-sig"), source), encoding="utf-8")
    print(f"Dashboard statica generata: {out / 'index.html'}")


if __name__ == "__main__":
    main()
