# CLAUDE.md — toponimi_coloniali

Pipeline riproducibile che conta gli odonimi italiani (ANNCSU) intitolati a figure, luoghi e battaglie
del colonialismo italiano (Libia, Eritrea, Etiopia, Somalia), con dashboard Streamlit e sito statico
su GitHub Pages. Dettagli metodologici e pipeline completa: `README.md`.

## Scope
Matching e pipeline, dashboard (Streamlit + sito statico), ricerca storica (registri), test e robustezza.

## Lingua
Italiano per documentazione, testo dell'interfaccia, messaggi di commit e commenti nuovi
(seguire lo stile dei commit esistenti: soggetto breve all'indicativo, es. "Corregge matching dei luoghi").
Identificatori Python in inglese, come nel codice attuale.

## Ambiente e comandi
- Virtualenv: `/home/rodolfo/Venv/poutpurri` (il pacchetto è già installato in modalità editable).
  Usare `/home/rodolfo/Venv/poutpurri/bin/python`; non installare nulla a livello di sistema.
- `pytest` non è ancora installato nel venv: per i test serve `python -m pip install -e '.[dev]'` (chiedere prima).
- Test: `pytest -q` (oppure `make test`). Eseguirli dopo ogni modifica a `src/` o agli script di matching.
- Pipeline: `make download | match | geocode | history`, poi `python scripts/06_build_static_site.py`.
- Dashboard locale: `streamlit run app/dashboard.py`.

## Struttura
- `src/colonial_toponymy/`: libreria (`normalize.py`, `matcher.py`, `anncsu.py`, `io_utils.py`).
- `scripts/01*–06_*.py`: passi numerati della pipeline; `06_build_static_site.py` genera `docs/index.html`.
- `config/sources.yml`: query Wikipedia, URL ANNCSU/ISTAT, soglie di matching.
- `data/manual/`: registri curati a mano (`people_registry.csv`, `place_registry.csv`, `street_history.csv`).
- `data/processed/`: output derivati; solo `dashboard_data.csv` e `people_registry_used.csv` sono versionati.
- `data/raw/`: download ANNCSU grezzi, non versionati.

## Principi metodologici (da rispettare nel codice e nei testi)
- Precisione prima del recall: nome completo o alias esatto accettati automaticamente; solo cognome
  solo se `allow_surname_only=true`; fuzzy sempre in revisione manuale.
- Una corrispondenza odonimo–persona non implica che l'intitolazione celebri il ruolo coloniale:
  non dedurlo mai automaticamente né affermarlo nei testi.
- Escludere nomi ambigui (omonimi più noti); non usare le date di modifica OSM come date di intitolazione.
- Ogni voce storica deve avere una fonte verificabile in `source_url`; non inventare fonti, date o QID.

## Regole di sicurezza
- **Segreti:** non stampare, loggare, committare né inviare a servizi esterni chiavi API, token,
  password, chiavi SSH o contenuti di `.env`. Se se ne trova uno, segnalarlo senza copiarlo.
- **Git:** niente commit, push o PR se non richiesto esplicitamente. Mai force-push, mai riscrivere
  history già pubblicata, mai `git reset --hard` / `git clean -f` / `git checkout .` su lavoro non committato.
- **Cancellazione:** non cancellare, sovrascrivere o spostare file/cartelle senza chiedere prima
  (incluse redirezioni che troncano file). Non toccare nulla fuori dal progetto.
- **`data/manual/`:** solo proposte. Suggerire righe (con fonte) e attendere approvazione prima di modificare.
- **`data/raw/`:** sola lettura.
- **Download pesanti:** chiedere prima di eseguire `02_download_anncsu.py` o `04_geocode_matches.py`
  senza `--no-download`.
- **Pubblicazione:** chiedere prima di modificare `.github/workflows/` o i CSV versionati in
  `data/processed/`: un push su `main` li pubblica su GitHub Pages.
- Niente `sudo`, installazioni globali o modifiche alla configurazione di sistema/shell.
- File temporanei nella scratchpad, non nel progetto.
