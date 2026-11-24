.PHONY: install discover download download-places download-quartieri match match-places match-quartieri geocode history politics dashboard test all

# Il pacchetto installato nel venv puo' puntare a un altro checkout: usare sempre src/ di questo progetto.
export PYTHONPATH := src

install:
	python -m pip install -e .

discover:
	python scripts/01_discover_people.py

download:
	python scripts/02_download_anncsu.py

download-places:
	python scripts/02b_download_public_places.py

download-quartieri:
	python scripts/02c_download_quartieri.py

match:
	python scripts/03_match_streets.py

match-places:
	python scripts/03b_match_public_places.py

match-quartieri:
	python scripts/03c_match_quartieri.py

geocode:
	python scripts/04_geocode_matches.py

history:
	python scripts/05_merge_history.py

politics:
	python scripts/07_download_politics.py

dashboard:
	streamlit run app/dashboard.py

test:
	pytest -q

all: download download-places download-quartieri match match-places match-quartieri geocode history
