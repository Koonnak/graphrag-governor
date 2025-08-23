# Developer experience shortcuts (lint, test, build)
.PHONY: install format lint type test cov up down

install:
	python -m pip install -r requirements.txt

format:
	black .
	ruff check --fix .
	ruff format .

lint:
	ruff check .
	ruff format --check .
	black --check .

type:
	mypy src

test:
	pytest -q

cov:
	pytest --maxfail=1 --disable-warnings --cov=src --cov-report=term-missing

up:
	docker compose up -d --build

down:
	docker compose down -v

