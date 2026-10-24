# ---------------------------------------------------------------------------
# invoice-diff — developer convenience targets
# ---------------------------------------------------------------------------
.PHONY: help install dev test lint format sample clean all

.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "invoice-diff — developer targets"
	@echo ""
	@echo "  install        Install in editable mode with dev deps"
	@echo "  dev            Create a fresh virtualenv and install"
	@echo "  test           Run the full pytest suite"
	@echo "  test-cov       Run pytest with coverage"
	@echo "  lint           Run ruff linter"
	@echo "  format         Run ruff formatter"
	@echo "  sample         Generate sample Flipkart/Meesho/Amazon CSVs"
	@echo "  clean          Remove build artifacts, caches, and reports"
	@echo "  all            lint + test"
	@echo ""

install:
	pip install -e ".[dev]"

dev:
	python -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

test:
	pytest

test-cov:
	pytest --cov=invoice_diff --cov-report=term-missing --cov-report=html

lint:
	ruff check .

format:
	ruff format .

sample:
	python generate_sample_data.py

test-cov:
	pytest --cov=invoice_diff --cov-report=term-missing --cov-report=html

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf reports/

all: lint test
