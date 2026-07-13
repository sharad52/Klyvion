.PHONY: install install-lite install-pip test lint format typecheck check serve docker docker-up clean help

install:            ## one-shot full install into .venv (neural + server + dev) via uv
	uv sync

install-lite:       ## fast install: offline engine + server + dev, NO neural model (via uv)
	uv sync --no-default-groups --extra lite --extra server --group dev

install-pip:        ## fallback if you don't use uv: full install with pip
	python -m pip install -e ".[all,dev]"

test:               ## run test suite
	pytest -q

lint:               ## ruff + black check
	ruff check . && black --check .

format:             ## auto-format
	black . && ruff check --fix .

typecheck:
	mypy klyvion --ignore-missing-imports

check: lint typecheck test   ## everything CI runs

serve:              ## run the HTTP server locally
	python -m uvicorn --factory klyvion.api.server:create_app --reload --port 8000

docker:             ## build production image
	docker compose build

docker-up:
	docker compose up -d

clean:
	rm -rf build dist *.egg-info .pytest_cache .coverage
	find . -name __pycache__ -type d -exec rm -rf {} +

help:               ## show targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ —/'
