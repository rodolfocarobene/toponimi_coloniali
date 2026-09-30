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
scripts/                     pipeline e generatore del sito statico
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
