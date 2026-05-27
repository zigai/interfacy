@_:
  just --list

_require-uv:
  @uv --version > /dev/null || (echo "Please install uv: https://docs.astral.sh/uv/" && exit 1)

_require-hatch: _require-uv
  @command -v hatch > /dev/null || uv tool list | grep -q '^hatch ' || uv tool install hatch

# check code style and potential issues
lint: _require-uv
  uv run ruff check .

# format code
format: _require-uv
  uv run ruff format .

# fix automatically fixable linting issues
fix: _require-uv
  uv run ruff check --fix .

# run tests across all supported Python versions
test: _require-hatch
  @if command -v hatch > /dev/null; then hatch run test:test; else uv tool run hatch run test:test; fi


# build the package
build: _require-uv
  uv build

# build the documentation site locally
docs: _require-uv
  uv run --extra docs sphinx-build -W --keep-going -b html docs docs/_build/html

# setup or update local dev environment, keeps previously installed extras
sync: _require-uv
  uv sync --inexact --extra dev
  uv run pre-commit install

# run tests with coverage and show a coverage report
coverage: _require-uv
  uv run coverage run -m pytest
  uv run coverage report

# clean build artifacts and caches
clean:
  rm -rf .venv .pytest_cache .pyrefly .ruff_cache
  find . -type d -name "__pycache__" -exec rm -r {} +

# static type check with pyrefly
typecheck: _require-uv
    uv run pyrefly check

# check code for common misspellings
spell: _require-uv
    uv run codespell

# run all quality checks
check: format lint coverage typecheck spell

# list available recipes
help:
    just --list

alias fmt := format
alias cov := coverage
alias pyrefly := typecheck

alias dev := sync
