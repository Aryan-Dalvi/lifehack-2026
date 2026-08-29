.PHONY: dev api web reset keys test build

dev:
	python scripts/dev.py

api:
	python -m uvicorn app.main:app --reload --port 8000

web:
	npm --prefix web run dev

reset:
	python -m seed.reset

keys:
	python -m scripts.generate_keys

test:
	python -m pytest -q

build:
	npm --prefix web run build
