# Lifecycle targets for the numerical_analysis monorepo. Run from the repository root.
#
#   make build-fortran         compile the Fortran drivers and install them into build/bin/
#   make build-fortran-single  same with -DSINGLE (real32) into build/single/bin/
#   make test-fortran          fpm test (test-drive) with the debug profile flags
#   make build-fortran-flang   compile with LLVM flang (strict, warnings are errors)
#   make test-fortran-flang    fpm test with LLVM flang
#   make sync                  uv sync (Python package + dev tools into python/.venv)
#   make test                  pytest (no browser tests) with coverage on algorithms + expr
#   make test-parity           build the Fortran drivers, then run the cross-engine parity tests
#   make test-golden           build both driver precisions, then run the golden (book) tests
#   make lint                  ruff check, ruff format --check, mypy --strict
#   make format                ruff format + ruff check --fix
#   make e2e                   Playwright browser tests (installs Chromium if needed)
#   make serve                 run the web learning tool (gerald-na serve)
#   make readme-index          regenerate the README program index + study-page errata tables
#   make clean                 remove build output and tool caches (keeps python/.venv)
#
# Compiler selection: FC=gfortran (default) or FC=flang. FFLAGS / FFLAGS_TEST override the flag
# sets below; FPMFLAGS adds extra fpm options (for example FPMFLAGS=--verbose).
#
# fpm only shows compiler output when a compilation fails, so every flag set includes -Werror:
# that is what makes "warning-free" an enforced property rather than a convention.

SHELL := /bin/sh

# GNU make predefines FC=f77; treat that default as "not set".
ifeq ($(origin FC),default)
FC := gfortran
endif
FLANG ?= flang

GFORTRAN_STRICT := -std=f2018 -fimplicit-none -Wall -Wextra -pedantic -Werror
GFORTRAN_RELEASE := $(GFORTRAN_STRICT) -O2
GFORTRAN_DEBUG := $(GFORTRAN_STRICT) -Og -g -fcheck=all -fbacktrace

# LLVM flang: -pedantic is used for the package build. The test build drops it because
# test-drive v0.5.0 itself triggers flang portability warnings under -pedantic.
FLANG_RELEASE := -std=f2018 -pedantic -Werror -O2
FLANG_TEST := -std=f2018 -Werror -O2

ifneq ($(findstring flang,$(FC)),)
FFLAGS ?= $(FLANG_RELEASE)
FFLAGS_TEST ?= $(FLANG_TEST)
else
FFLAGS ?= $(GFORTRAN_RELEASE)
FFLAGS_TEST ?= $(GFORTRAN_DEBUG)
endif

FPMFLAGS ?=
FPM ?= fpm
UV ?= uv
UV_PY := $(UV) --directory python
PLAYWRIGHT_INSTALL_FLAGS ?=

# Paths relative to fortran/ (fpm runs there).
INSTALL_PREFIX := ../build
SINGLE_PREFIX := ../build/single

.PHONY: help build-fortran build-fortran-single build-fortran-flang test-fortran \
	test-fortran-flang sync test test-parity test-golden lint format e2e serve readme-index clean

help:
	@sed -n '3,17p' Makefile

build-fortran:
	cd fortran && $(FPM) build --compiler $(FC) --flag "$(FFLAGS)" $(FPMFLAGS)
	cd fortran && $(FPM) install --compiler $(FC) --flag "$(FFLAGS)" $(FPMFLAGS) \
		--prefix $(INSTALL_PREFIX)

build-fortran-single:
	cd fortran && $(FPM) build --compiler $(FC) --flag "$(FFLAGS) -DSINGLE" $(FPMFLAGS)
	cd fortran && $(FPM) install --compiler $(FC) --flag "$(FFLAGS) -DSINGLE" $(FPMFLAGS) \
		--prefix $(SINGLE_PREFIX)

build-fortran-flang:
	cd fortran && $(FPM) build --compiler $(FLANG) --flag "$(FLANG_RELEASE)" $(FPMFLAGS)

test-fortran:
	cd fortran && $(FPM) test --compiler $(FC) --flag "$(FFLAGS_TEST)" $(FPMFLAGS)

test-fortran-flang:
	cd fortran && $(FPM) test --compiler $(FLANG) --flag "$(FLANG_TEST)" $(FPMFLAGS)

sync:
	$(UV_PY) sync

test:
	$(UV_PY) run pytest --cov --cov-report=term-missing --cov-report=xml

test-parity: build-fortran
	$(UV_PY) run pytest tests/parity

test-golden: build-fortran build-fortran-single
	$(UV_PY) run pytest tests/golden

lint:
	$(UV_PY) run ruff check
	$(UV_PY) run ruff format --check
	$(UV_PY) run mypy --strict src tests

format:
	$(UV_PY) run ruff format
	$(UV_PY) run ruff check --fix

e2e:
	$(UV_PY) run playwright install $(PLAYWRIGHT_INSTALL_FLAGS) chromium
	$(UV_PY) run pytest -m e2e tests/e2e

serve:
	$(UV_PY) run gerald-na serve

# Markdown generated from catalog/*.toml (README.md program index, content/*.md errata tables).
# `make test` fails while these blocks are stale (python/tests/unit/test_generated_docs.py).
readme-index:
	$(UV_PY) run gerald-na catalog index --write

clean:
	rm -rf build fortran/build
	rm -rf python/.pytest_cache python/.mypy_cache python/.ruff_cache python/.hypothesis
	rm -rf python/htmlcov python/coverage.xml python/.coverage python/.coverage.*
	rm -rf python/test-results python/playwright-report
	find python -name __pycache__ -type d -prune -exec rm -rf {} +
