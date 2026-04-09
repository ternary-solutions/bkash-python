PYTHON ?= python3
PIP := $(PYTHON) -m pip

.PHONY: install-dev lint typecheck test build check

install-dev:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

lint:
	pre-commit run --all-files

typecheck:
	mypy bkash_pgw_tokenized

test:
	pytest --cov=bkash_pgw_tokenized --cov-report=term-missing --cov-fail-under=90

build:
	rm -rf build dist *.egg-info
	$(PYTHON) -m build
	twine check dist/*

check: lint typecheck test build
