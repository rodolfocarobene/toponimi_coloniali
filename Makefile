.PHONY: install discover download match geocode history dashboard test all

install:
	python -m pip install -e .

discover:
	python scripts/01_discover_people.py

download:
	python scripts/02_download_anncsu.py

match:
	python scripts/03_match_streets.py

geocode:
	python scripts/04_geocode_matches.py

history:
	python scripts/05_merge_history.py

dashboard:
	streamlit run app/dashboard.py

test:
	pytest -q

all: download match geocode history
