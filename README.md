# Toponimi coloniali italiani

Progetto riproducibile per studiare quanti odonimi italiani, come vie, piazze, viali e larghi, sono
intitolati a figure pubbliche legate al colonialismo italiano, con particolare attenzione a Libia,
Eritrea, Etiopia e Somalia.

Il progetto distingue volutamente tre domande diverse:

1. **La persona ebbe un ruolo sostanziale nel colonialismo italiano?**
2. **L'odonimo italiano è effettivamente intitolato a quella persona?**
3. Quando esiste documentazione specifica, **l'intitolazione fu scelta proprio per celebrarne il ruolo coloniale?**

La terza domanda richiede fonti storiche o amministrative specifiche e non viene dedotta automaticamente.

## Fonti principali

Per l'inventario nazionale degli odonimi viene utilizzato **ANNCSU**, l'Archivio Nazionale dei Numeri
Civici e delle Strade Urbane. OpenStreetMap può essere usato come controllo o fonte geometrica aggiuntiva,
ma non come unica fonte per stabilire l'esistenza di un odonimo ufficiale.

Il registro delle persone è curato manualmente in:

```text
data/manual/people_registry.csv
```

La versione attuale contiene una lista estesa e conservativa. I nomi ambigui, per i quali l'odonimo è
verosimilmente riferito a un omonimo più noto, vengono esclusi per limitare i falsi positivi.

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Per i test:

```bash
python -m pip install -e '.[dev]'
pytest -q
```

## Pipeline

### 1. Individuazione di candidati da Wikipedia

```bash
python scripts/01_discover_people.py
```

Output locale:

```text
data/candidates/wikipedia_candidates.csv
```

Questa lista serve solo come supporto alla ricerca. Non viene considerata automaticamente un registro
storicamente verificato e, essendo completamente rigenerabile, non viene versionata nel repository.

È disponibile anche un helper sperimentale che prepara una tabella di revisione:

```bash
python scripts/01c_promote_candidates.py
```

che produce:

```text
data/candidates/candidate_review.csv
```

Lo script **non** modifica il registro manuale. La decisione finale su quali figure includere resta manuale,
in particolare per evitare falsi positivi, oppositori del colonialismo inclusi per semplice co-occorrenza
e casi di omonimia odonomastica.

È possibile anche estrarre candidati da libri o PDF locali:

```bash
python scripts/01b_extract_people_from_books.py libro1.pdf libro2.pdf
```

### 2. Download dello stradario ANNCSU

```bash
python scripts/02_download_anncsu.py
```

Scarica lo stradario nazionale e la tabella ISTAT dei comuni. I download ANNCSU grezzi non vengono
versionati su GitHub.

### 3. Matching tra persone e odonimi

```bash
python scripts/03_match_streets.py
```

Output principali:

```text
data/processed/street_matches.csv
data/processed/street_matches.parquet
data/processed/people_registry_used.csv
```

`people_registry_used.csv` è una copia esatta del registro utilizzato in quella specifica esecuzione e
viene resa scaricabile dalla dashboard per garantire la riproducibilità.

Il matching privilegia la precisione:

- nome completo esatto: accettato automaticamente;
- alias curato esatto: accettato automaticamente;
- solo cognome: ammesso soltanto se esplicitamente autorizzato nel registro;
- fuzzy matching: destinato a revisione manuale.

### 4. Coordinate geografiche

```bash
python scripts/04_geocode_matches.py
```

oppure, se gli archivi regionali ANNCSU sono già stati scaricati:

```bash
python scripts/04_geocode_matches.py --no-download
```

Per ogni odonimo viene calcolato un punto rappresentativo come mediana delle coordinate dei numeri civici
georiferiti disponibili. La copertura non è completa per tutti i comuni.

### 5. Date storiche di intitolazione e rimozione

Le date verificate manualmente possono essere inserite in:

```text
data/manual/street_history.csv
```

quindi unite ai dati con:

```bash
python scripts/05_merge_history.py
```

Le date di modifica degli oggetti OpenStreetMap non vengono usate come date di intitolazione.

### Luoghi pubblici intitolati (scuole, università, altri luoghi)

Oltre agli odonimi, il registro viene confrontato con i nomi di luoghi pubblici (ad esempio le scuole
intitolate ad Antonio Locatelli). Passi aggiuntivi, da eseguire prima di `05_merge_history.py`:

```bash
python scripts/02b_download_public_places.py    # oppure: make download-places
python scripts/03b_match_public_places.py       # oppure: make match-places
python scripts/05_merge_history.py
```

Fonti (URL e date di accesso in `config/sources.yml`; elenco dei file scaricati in
`data/raw/public_places/manifest.json`, cartella non versionata):

| `site_kind`      | Fonte                                                                                          | Note |
|------------------|------------------------------------------------------------------------------------------------|------|
| `odonimo`        | ANNCSU                                                                                         | come sopra |
| `scuola`         | MIM, Anagrafe scuole statali e paritarie (open data, ultimo anno scolastico disponibile)         | sedi e istituti di riferimento; senza coordinate. Trento, Bolzano e Valle d'Aosta non sono nel MIM: Trento da dati.trentino.it (PAT, CC0, istantanea 2014-09-10), Bolzano e Valle d'Aosta da elementi Wikidata (nessun elenco open data ufficiale trovato; copertura e denominatori approssimati), vedi `config/sources.yml` |
| `universita`     | MUR/USTAT: elenco degli atenei e collegi universitari (ultimo anno); Wikidata e OSM per le intitolazioni | pochi nomi intitolati a persone del registro |
| `luogo_pubblico` | Wikidata (proprietà P138 «intitolato a») e OpenStreetMap (biblioteche, municipi, ospedali, teatri, caserme, stadi, parchi, musei, aeroporti) | copertura parziale: non esiste un elenco nazionale di aule, sale o auditorium |

Regole di matching, le stesse degli odonimi con alcune cautele:

- i prefissi istituzionali vengono rimossi come i prefissi stradali (`I.C.`, `Istituto comprensivo`,
  `Liceo scientifico`, `Scuola primaria`, `Aula magna`, ...) e si provano anche le parti tra virgolette
  o separate da « - »;
- nome completo o alias esatto di una persona: accettato automaticamente;
- solo cognome (se `allow_surname_only`), iniziale + cognome (`A. LOCATELLI`) e fuzzy: sempre in revisione manuale;
- cognome come segmento a sé del nome (`PRIMARIA LOCATELLI`, `I.C. LOCATELLI-QUASIMODO`, `BORGORICCO-LOCATELLI`),
  tolte le parole istituzionali (anche tedesche: `Grundschule`, `Mittelschule`, `Oberschule`...): metodo
  `surname_in_name`, solo per scuole e università, sempre `needs_review`, anche se `allow_surname_only` è falso.
  Non scatta se il cognome è accompagnato da nome, iniziale o titolo (`GIANNI LOCATELLI`, `DON ANTONIO LOCATELLI`,
  `E. LOCATELLI`), se il nome è un indirizzo (`ZOGNO VIA LOCATELLI`), se due persone del registro hanno lo stesso
  cognome, né per i cognomi in `SURNAME_IN_NAME_EXCLUDED` (`places.py`): omonimi di comuni o località (Caneva,
  Bono, Scalea, Lessona...) o molto più noti/comuni (Gabelli, Martini, Antonelli, Giuliani...), valutati sui dati MIM;
  una scuola intitolata al solo cognome non è attribuita al plesso dal nome dell'istituto di riferimento (l'istituto
  è confrontato come riga a sé, senza duplicati);
- nomi che iniziano con un prefisso stradale (`VIA ADUA`) sono indirizzi, non intitolazioni, e vengono scartati;
- voci del registro dei luoghi e delle battaglie (Libia, Adua, ...): sempre in revisione manuale, perché
  una scuola in via Adua non è intitolata ad Adua;
- le corrispondenze Wikidata trovate tramite la persona a cui l'oggetto è intitolato sono sempre in revisione
  (omonimi possibili).

Colonne aggiunte a `dashboard_data.csv`: `site_kind`, `site_detail` (tipo di scuola, istituto, tipo OSM/Wikidata),
`total_kind_region` (numero di elementi dello stesso tipo nella regione, denominatore; per gli odonimi coincide con
`total_odonimi_region`), `coord_precision` (`street_median`, `point` oppure `municipality_centroid`),
`place_source` e `place_source_id`. Le scuole non hanno coordinate nella fonte: si usa il centroide del comune
(Wikidata), indicato in `coord_precision`. Per gli oggetti OSM il comune è dedotto dal tag `addr:city` o dal
centroide comunale più vicino nella stessa regione (approssimato). Il denominatore dei `luogo_pubblico` conta gli
oggetti OSM con nome delle categorie interrogate; le voci Wikidata non rientrano nel denominatore.

### Controllo politico dei comuni e delle regioni

```bash
python scripts/07_download_politics.py     # oppure: make politics
```

Scarica dall'Anagrafe degli amministratori locali e regionali del Ministero dell'Interno
(<https://dait.interno.gov.it/elezioni/open-data/amministratori-locali-e-regionali-in-carica>, file
`maggiororgano.csv` e `ammreg.csv`, aggiornati al 24/08/2026) il sindaco in carica di ogni comune e le liste
che lo sostengono, e produce:

```text
data/processed/municipality_politics.csv   # municipality_istat, municipality_name, region_name, mayor_list, party_family, election_date, source_url
data/processed/region_politics.csv         # region_name, president, coalition, election_date, source_url
```

I file grezzi restano in `data/raw/politics/` (con `manifest.json`). Le liste del sindaco sono classificate in
`party_family` (`centrodestra`, `centrosinistra`, `m5s`, `civica`, `altro`, `n.d.`) con le parole chiave
documentate in `config/party_families.yml`; il testo originale resta in `mayor_list`. Regole in breve: la
classificazione guarda tutte le liste collegate al sindaco; "civica" significa solo che nessun partito
riconosciuto compare nel nome delle liste (una civica sostenuta di fatto da un partito resta "civica");
centrodestra insieme a centrosinistra o M5S dà "altro"; M5S con il centrosinistra dà "centrosinistra";
Azione, Italia Viva e partiti autonomisti (SVP, Union Valdôtaine) sono neutri. `n.d.` indica lista assente
o "Lista non pervenuta" nel dato ufficiale (frequente in Sicilia, Friuli-Venezia Giulia, Valle d'Aosta e
Trentino-Alto Adige). Il codice ISTAT è ricavato da nome e sigla di provincia (l'Anagrafe non riporta il
codice catastale) ed è verificato sull'elenco ISTAT dei comuni. Per il join con `dashboard_data.csv` usare
`municipality_istat` contro `municipality_istat_y` (o il codice Belfiore tradotto con l'elenco ISTAT):
`municipality_istat_x` è obsoleto per alcuni comuni sardi.

I presidenti di Campania e Marche non sono nel file regionale del Ministero e sono aggiunti a mano in
`config/party_families.yml` con fonte; il Trentino-Alto Adige non ha un presidente di regione eletto direttamente
e non compare in `region_politics.csv`.

**Cautela metodologica.** I nomi delle vie sono stati assegnati per lo più decenni fa: chi governa oggi
non è chi ha intitolato. Il controllo politico attuale non spiega le intitolazioni, al massimo descrive chi
le mantiene; le liste civiche dei piccoli comuni nascondono spesso appartenenze di partito. Qualsiasi
differenza tra gruppi è una correlazione, non un nesso causale, e dipende anche da dimensione dei comuni e
geografia.

### 6. Dashboard locale

```bash
streamlit run app/dashboard.py
```

La dashboard consente di:

- selezionare una o più figure specifiche;
- escludere una o più figure specifiche;
- filtrare per regione, ruolo e territorio coloniale;
- mostrare solo le corrispondenze accettate;
- confrontare le regioni con conteggi assoluti o normalizzati;
- visualizzare una mappa interattiva centrata sull'Italia;
- scaricare il CSV filtrato;
- scaricare il registro esatto dei nomi utilizzato per il matching.

## GitHub Pages

GitHub Pages non esegue applicazioni Python/Streamlit. Per questo il progetto contiene anche un generatore
statico che crea una dashboard HTML/JavaScript equivalente:

```bash
python scripts/06_build_static_site.py
```

La dashboard viene generata in:

```text
docs/index.html
```

Il workflow:

```text
.github/workflows/pages.yml
```

ricostruisce e pubblica automaticamente il sito quando cambiano il generatore o i due file derivati usati
per la pubblicazione:

```text
data/processed/dashboard_data.csv
data/processed/people_registry_used.csv
```

Gli archivi ANNCSU grezzi e gli altri output intermedi rimangono esclusi da Git tramite `.gitignore`.

Per attivare GitHub Pages nel repository, selezionare:

**Settings → Pages → Build and deployment → Source → GitHub Actions**

Per questo repository il sito sarà normalmente disponibile all'indirizzo:

```text
https://rodolfocarobene.github.io/toponimi_coloniali/
```

## Aggiornare i dati pubblicati

Dopo aver eseguito la pipeline localmente, committare i due file leggeri usati dalla dashboard pubblica:

```bash
git add data/processed/dashboard_data.csv data/processed/people_registry_used.csv
git commit -m "Aggiorna dati dashboard"
git push
```

Il workflow GitHub Pages rigenererà automaticamente il sito.

## Struttura del progetto

```text
app/                         dashboard Streamlit
scripts/                     pipeline e generatore del sito statico (02b/03b: luoghi pubblici)
src/colonial_toponymy/       libreria Python
config/                      configurazione delle fonti
data/manual/                 registro curato e dati storici manuali
data/candidates/             output di discovery rigenerabili
data/processed/              output derivati
data/raw/                    download grezzi, non versionati
.github/workflows/           pubblicazione GitHub Pages
```

## Nota metodologica

Una corrispondenza tra odonimo e persona indica che il nome ufficiale è compatibile con una figura presente
nel registro. Non implica automaticamente che l'intitolazione sia stata deliberata per celebrarne
specificamente l'attività coloniale. Questa distinzione deve essere mantenuta anche nell'interpretazione dei
risultati aggregati.
