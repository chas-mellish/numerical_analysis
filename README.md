# Gerald *Applied Numerical Analysis*: modern Fortran, Python and a web learning tool

This repository turns the 1970s card-image FORTRAN listings from C. F. Gerald's
*Applied Numerical Analysis* into a learning tool with three parts:

1. **Modern Fortran 2018** (`fortran/`): an [fpm](https://fpm.fortran-lang.org) package built
   with gfortran 16 (strict flags, warnings are errors) and checked with LLVM flang. One thin
   driver per book program reproduces the book's line-printer output.
2. **A Python 3.15 port** (`python/`, package `gerald_na`): standard-library-only algorithms that
   return trace dataclasses, a safe expression compiler for learner functions, and engines that run
   either the Python code or the compiled Fortran drivers.
3. **A web learning tool** (FastAPI + Jinja2 + HTMX + Plotly.js) that shows, for each method, the
   original scan, the modern sources, the iteration trace, charts and practice questions.

Each program is described once in a shared catalog (`catalog/*.toml`); the UI, the tests and both
engines read it. The original OCR transcriptions in `legacy_code/` and the scans in `docs/*.pdf`
are kept unchanged as the reference.

## Repository layout

```
legacy_code/fortran/...   original OCR transcriptions (reference only, never built)
docs/*.pdf                scanned book listings (source of truth for transcription)
docs/architecture.md      layout and design decisions
catalog/                  one TOML file per program: metadata, inputs, presets, golden outputs
content/                  study pages (Markdown)
config/settings.toml      runtime settings (overridable with GERALD_NA_* variables)
fortran/fpm.toml          Fortran 2018 package
fortran/src/              modules (precision.F90 exports the working precision `wp`)
fortran/app/              thin drivers, one executable per program
fortran/test/             test-drive suites (`fpm test`)
python/pyproject.toml     Python package `gerald-na` (uv, hatchling)
python/src/gerald_na/     algorithms, expr, engines, registry, web, errors.py, settings.py, cli.py
python/tests/             unit, golden, parity, web, e2e
Makefile                  lifecycle targets
Dockerfile, .devcontainer/  reference environment
```

`catalog/`, `content/`, `fortran/app/` and the algorithm modules are filled in program by program.

## Quick start

Requirements: gfortran 16 (or LLVM flang), fpm 0.13, GNU make and
[uv](https://docs.astral.sh/uv/) (uv installs Python 3.15 automatically from
`python/.python-version`). The `Dockerfile` / `.devcontainer/` provide all of them.

```sh
make sync            # uv sync: creates python/.venv with the package and dev tools
make build-fortran   # fpm build + fpm install: executables land in build/bin/
make test            # pytest with coverage (Fortran-dependent tests skip if build/bin is empty)
make serve           # http://127.0.0.1:8000  (health check: GET /healthz)
```

The CLI is available inside the uv environment:

```sh
cd python
uv run gerald-na --version
uv run gerald-na --help
uv run gerald-na serve --host 0.0.0.0 --port 8000 [--reload]
```

## Lifecycle targets

| Target | What it does |
|---|---|
| `make build-fortran` | `fpm build` + `fpm install --prefix ../build` with `-std=f2018 -fimplicit-none -Wall -Wextra -pedantic -Werror -O2`; drivers in `build/bin/` |
| `make build-fortran-single` | same with `-DSINGLE` (real32, the book's precision); drivers in `build/single/bin/` |
| `make test-fortran` | `fpm test` with the debug flags (`-Og -g -fcheck=all -fbacktrace` plus the strict set) |
| `make build-fortran-flang` / `make test-fortran-flang` | the same with LLVM flang (`fpm --compiler flang`) |
| `make sync` | `uv sync` in `python/` |
| `make test` | pytest without browser tests; coverage of `gerald_na.algorithms` and `gerald_na.expr` must be at least 90% |
| `make test-parity` | builds the Fortran drivers, then runs the cross-engine parity tests |
| `make lint` | `ruff check`, `ruff format --check`, `mypy --strict` |
| `make format` | `ruff format` and `ruff check --fix` |
| `make e2e` | installs Playwright Chromium if needed and runs `pytest -m e2e` |
| `make serve` | `uv run gerald-na serve` |
| `make clean` | removes `build/`, `fortran/build/` and tool caches (keeps `python/.venv`) |

Variables: `FC=flang` switches the compiler for every Fortran target, `FFLAGS` / `FFLAGS_TEST`
replace the flag sets, and `FPMFLAGS` passes extra options to fpm (for example `--verbose`).
fpm only prints compiler output when a compilation fails, which is why every flag set includes
`-Werror`.

### Tests

pytest markers (`python/pyproject.toml`):

* `fortran`: needs the compiled drivers. These tests are skipped with the reason
  "Fortran binaries not built: run `make build-fortran`" when `fortran_bin_dir` holds no executables.
* `e2e`: Playwright browser tests. They are excluded by default; run them with `make e2e` or
  `uv run pytest -m e2e`.
* `slow`: long-running tests.

## Configuration

Settings are read from `config/settings.toml` and can be overridden by environment variables with
the prefix `GERALD_NA_`:

| Key | Default | Meaning |
|---|---|---|
| `fortran_bin_dir` | `build/bin` | directory of the compiled drivers, relative to the repository root |
| `run_timeout_s` | `5.0` | timeout for one Fortran driver run, in seconds |
| `engines_enabled` | `["python", "fortran"]` | engines offered by the UI and API |
| `host` | `127.0.0.1` | bind address of `gerald-na serve` |
| `port` | `8000` | port of `gerald-na serve` |
| `repo_root` | auto-detected | repository root (nearest ancestor of the package holding `config/settings.toml` or `catalog/`) |

Examples: `GERALD_NA_PORT=9000 make serve`, or
`GERALD_NA_FORTRAN_BIN_DIR=build/single/bin make test` to run against the single-precision build.
Lists are given as JSON (`GERALD_NA_ENGINES_ENABLED='["python"]'`). There are no secrets and no
external services.

## Container

```sh
docker build -t gerald-na .
docker run --rm -p 8000:8000 gerald-na
```

The image (Ubuntu 24.04, gfortran 16 from the ubuntu-toolchain-r/test PPA, LLVM flang 22,
fpm 0.13.0, uv with Python 3.15) builds the Fortran drivers and serves the web tool on port 8000.
The devcontainer uses the same Dockerfile.

## Program index

The index below is generated from the catalog (`catalog/*.toml`). It is empty until catalog
entries exist; do not edit the text between the markers by hand.

<!-- PROGRAM_INDEX_START -->
<!-- PROGRAM_INDEX_END -->

## Further reading

* [`docs/architecture.md`](docs/architecture.md): repository layout and design decisions
  (program identities, trace protocol, Fortran presets, golden tolerances, file serving).
