# Thin wrappers around the CLI. On Windows without make, run the commands directly.
.PHONY: check test reproduce audit

check:
	uv run ruff check src tests
	uv run mypy
	uv run lint-imports
	uv run pytest --cov=rbrs --cov-report=term-missing

test:
	uv run pytest

reproduce:
	uv run rbrs reproduce

audit:
	uv run rbrs audit
