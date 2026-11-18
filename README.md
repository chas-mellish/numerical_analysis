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

Each program is described once in a shared catalog (`catalog/*.toml`); the UI, the tests, both
engines and the program index below read it. The original OCR transcriptions in `legacy_code/` and
the scans in `docs/*.pdf` are kept unchanged as the reference.

## Programs

The index is generated from the catalog by `make readme-index` (`gerald-na catalog index --write`);
do not edit the text between the markers by hand. `make test` fails while it is out of date.
Every program runs on the Python engine, the Fortran engine and in compare mode, and has a web page
at `/programs/<id>`.

<!-- PROGRAM_INDEX_START -->
| Program id | Book reference | Method | Scan available? | Fortran executable | Python function | Study page |
|---|---|---|---|---|---|---|
| `ch01_p01` | Ch. 1, Prog. 1, p. 24 | Interval halving (bisection) | [yes](docs/chapter_01_program_01_listing.pdf) | [`ch01_p01_bisection`](fortran/app/ch01_p01_bisection.f90) | `gerald_na.algorithms.bisection:bisection` | [content/ch01_p01.md](content/ch01_p01.md) |
| `ch01_p02` | Ch. 1, Prog. 2, p. 25 | Bairstow quadratic factors | [yes](docs/chapter_01_program_02_listing.pdf) | [`ch01_p02_bairstow`](fortran/app/ch01_p02_bairstow.f90) | `gerald_na.algorithms.bairstow:bairstow` | [content/ch01_p02.md](content/ch01_p02.md) |
| `ch03_p01` | Ch. 3, Prog. 1, p. 73 | Simpson's 1/3 rule, Si(B) | [yes](docs/chapter_03_program_01_listing.pdf) | [`ch03_p01_simpson`](fortran/app/ch03_p01_simpson.f90) | `gerald_na.algorithms.simpson:simpson` | [content/ch03_p01.md](content/ch03_p01.md) |
| `ch03_p02` | Ch. 3, Prog. 2, p. 74 | Romberg integration, Si(B) | [yes](docs/chapter_03_program_02_listing.pdf) | [`ch03_p02_romberg`](fortran/app/ch03_p02_romberg.f90) | `gerald_na.algorithms.romberg:romberg` | [content/ch03_p02.md](content/ch03_p02.md) |
| `ch04_p01` | Ch. 4, Prog. 1, p. 90 | Derivatives by central differences | [yes](legacy_code/fortran/chapter_4/derivatives.pdf) | [`ch04_p01_central_difference`](fortran/app/ch04_p01_central_difference.f90) | `gerald_na.algorithms.central_difference:central_difference` | [content/ch04_p01.md](content/ch04_p01.md) |
| `lagrange_interpolation` | unconfirmed | Lagrangian interpolation | **no** | [`lagrange_interpolation`](fortran/app/lagrange_interpolation.f90) | `gerald_na.algorithms.lagrange:lagrange` | [content/lagrange_interpolation.md](content/lagrange_interpolation.md) |

6 programs. Without a scan: `lagrange_interpolation`. Book reference unconfirmed: `lagrange_interpolation`.
<!-- PROGRAM_INDEX_END -->

### Missing scans and programs not yet migrated

* **Lagrangian interpolation has no scan and an unconfirmed book reference.** Its only source is
  the OCR text `legacy_code/fortran/chapter_2/polynomial.F90` (the folder name does not establish
  the chapter). It is catalogued under the non-book id `lagrange_interpolation` with
  `book_ref_confirmed = false` and no `scan_pdf`; the web page shows "no scan available", and its
  corrections are justified by syntax, FORMAT Hollerith counts and the printed result 2.3119. When
  a scan turns up, the reference can be confirmed in the catalog without renaming any file.
* **Scanned listings.** Chapters 1 and 3 are the four listing PDFs in `docs/`
  (`chapter_01_program_01/02`, `chapter_03_program_01/02`). Chapter 4, Program 1 (central
  differences, book p. 90) is scanned in `legacy_code/fortran/chapter_4/derivatives.pdf` and
  catalogued as `ch04_p01`; it has no OCR text, so its listing was transcribed from the scan.
* **Scanned pages without a program listing.** Two scans hold no program: Chapter 4 p. 91
  (`legacy_code/fortran/chapter_4/derivatives_log_example.pdf`, problems 2-7 of chapter 4; its
  problem 2 is used by the `ch04_p01` practice questions and preset 3) and Chapter 5 p. 106
  (`legacy_code/fortran/chapter_5/integration_methods.pdf`, a summary of the trapezoidal,
  Simpson, Milne and Adams formulas with their error terms, cited on the `ch04_p01` study page).
  Neither is a program to migrate; Chapter 5's programs are not scanned yet.
* **Chapters 6 to 8 are not scanned yet** (the repository history says the code for the later
  chapters will be uploaded once scanned).

New programs follow the checklist in [Adding a program](#adding-a-program).

## Repository layout

```
legacy_code/fortran/...   original OCR transcriptions (reference only, never built)
docs/*.pdf                scanned book listings (source of truth for transcription)
docs/architecture.md      layout, design decisions, catalog schema, engines, web UI
catalog/                  one TOML file per program: metadata, inputs, presets, golden outputs
content/                  study pages (Markdown; errata tables generated from the catalog)
config/settings.toml      runtime settings (overridable with GERALD_NA_* variables)
fortran/fpm.toml          Fortran 2018 package
fortran/src/              modules (precision.F90 exports the working precision `wp`)
fortran/app/              thin drivers, one executable per program
fortran/test/             test-drive suites (`fpm test`)
python/pyproject.toml     Python package `gerald-na` (uv, hatchling)
python/src/gerald_na/     algorithms, expr, engines, registry, web, tools, errors.py, settings.py, cli.py
python/tests/             unit, golden, parity, web, e2e
Makefile                  lifecycle targets
Dockerfile, .devcontainer/  reference environment
```

## Setup

### Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| GNU make | any | the lifecycle targets below |
| [uv](https://docs.astral.sh/uv/) | recent | Python environment; installs Python 3.15 itself from `python/.python-version` (`requires-python >= 3.14`) |
| gfortran | 16 | `make build-fortran`, `make test-fortran` (the Fortran engine, parity tests) |
| fpm | 0.13 | building and testing the Fortran package |
| LLVM flang | 22 (optional) | `make build-fortran-flang`, `make test-fortran-flang` |
| Chromium for Playwright | installed by `make e2e` | browser tests only |

Without a Fortran compiler the Python side still installs and its unit, golden, web and CLI tests
run: tests that need the drivers are marked `fortran` and skip with the reason "Fortran binaries
not built: run `make build-fortran`", and the web UI offers only the Python engine.

### Local setup

```sh
make sync            # uv sync: python/.venv with the package and dev tools
make build-fortran   # fpm build + fpm install: executables land in build/bin/
make test            # pytest with coverage (Fortran-dependent tests skip if build/bin is empty)
make serve           # http://127.0.0.1:8000  (health check: GET /healthz)
```

### Docker

```sh
docker build -t gerald-na .
docker run --rm -p 8000:8000 gerald-na                       # serves on http://127.0.0.1:8000
docker run --rm -it gerald-na make test test-fortran lint    # run the gates in the image
```

The image (Ubuntu 24.04, gfortran 16 from the ubuntu-toolchain-r/test PPA, LLVM flang 22,
fpm 0.13.0, uv with Python 3.15) builds the Fortran drivers and the Python environment, serves
the web tool on port 8000 (`gerald-na serve --host 0.0.0.0`) and has a `HEALTHCHECK` on
`/healthz`. It is the reference environment: compiler versions are pinned there, so golden and
parity results are reproducible.

### Devcontainer

Open the repository in VS Code (or any devcontainer client) and choose "Reopen in Container".
`.devcontainer/devcontainer.json` builds the same `Dockerfile`, mounts the checkout at
`/workspace`, runs `make sync build-fortran` after creation, forwards port 8000 and installs the
Fortran, Ruff, Python, mypy and TOML extensions. Then use the make targets as above.

## Lifecycle targets

| Target | What it does |
|---|---|
| `make sync` | `uv sync` in `python/` |
| `make build-fortran` | `fpm build` + `fpm install --prefix ../build` with `-std=f2018 -fimplicit-none -Wall -Wextra -pedantic -Werror -O2`; drivers in `build/bin/` |
| `make build-fortran-single` | same with `-DSINGLE` (real32, the book's precision); drivers in `build/single/bin/` |
| `make test-fortran` | `fpm test` (test-drive) with the debug flags (`-Og -g -fcheck=all -fbacktrace` plus the strict set) |
| `make build-fortran-flang` / `make test-fortran-flang` | the same with LLVM flang (`fpm --compiler flang`) |
| `make test` | pytest without browser tests (unit, golden, web, CLI, generated docs; parity when the drivers exist); coverage of `gerald_na.algorithms` and `gerald_na.expr` must be at least 90% |
| `make test-parity` | builds the Fortran drivers, then runs the cross-engine parity tests |
| `make lint` | `ruff check`, `ruff format --check`, `mypy --strict` |
| `make format` | `ruff format` and `ruff check --fix` |
| `make e2e` | installs Playwright Chromium if needed and runs `pytest -m e2e` (one browser test per program) |
| `make serve` | `uv run gerald-na serve` |
| `make readme-index` | regenerates the program index above and the errata table of every study page from the catalog |
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

`GERALD_NA_FORTRAN_BIN_DIR=build/single/bin make test` runs the golden tests against the
single-precision build, where they compare more tightly with the book's digits.

## Configuration

Settings are read from `config/settings.toml` and can be overridden by environment variables with
the prefix `GERALD_NA_`:

| Key | Default | Meaning |
|---|---|---|
| `fortran_bin_dir` | `build/bin` | directory of the compiled drivers, relative to the repository root |
| `fortran_single_bin_dir` | `build/single/bin` | SINGLE-precision drivers, used by the golden tests to compare with the book's digits |
| `run_timeout_s` | `5.0` | timeout for one Fortran driver run, in seconds |
| `engines_enabled` | `["python", "fortran"]` | engines offered by the UI and API |
| `host` | `127.0.0.1` | bind address of `gerald-na serve` |
| `port` | `8000` | port of `gerald-na serve` |
| `repo_root` | auto-detected | repository root (nearest ancestor of the package holding `config/settings.toml` or `catalog/`) |

Examples: `GERALD_NA_PORT=9000 make serve`, or
`GERALD_NA_FORTRAN_BIN_DIR=build/single/bin make test` to run against the single-precision build.
Lists are given as JSON (`GERALD_NA_ENGINES_ENABLED='["python"]'`). There are no secrets, no
database and no external services.

## Command line

The `gerald-na` command is available inside the uv environment (`cd python`, then `uv run ...`):

```sh
uv run gerald-na --version
uv run gerald-na --help
uv run gerald-na serve [--host 0.0.0.0] [--port 8000] [--reload]
```

**Run a program** with the book data card, optionally overriding inputs, and print the book text
(exit status 0 success, 1 the program stopped on one of its error paths, 2 invalid request):

```sh
uv run gerald-na run ch03_p01                       # VALUE OF SINE INTEGRAL ... IS 1.5499312 WITH 100 PANELS
uv run gerald-na run ch01_p01 --input tol=1.E-3     # override one data-card field
uv run gerald-na run ch01_p01 --preset 2 --input x1=1 --input x2=2   # another catalog function
uv run gerald-na run ch01_p01 --expr 'x**3 - 2' --input x1=1 --input x2=2   # custom F(x), Python only
uv run gerald-na run lagrange_interpolation --input n=3 --input points=1,1,2,4,4,16 --input xin=2.5
uv run gerald-na run ch01_p02 --engine fortran --verbose          # the compiled driver, with extras
uv run gerald-na run ch03_p02 --engine compare                    # both engines, traces diffed
uv run gerald-na run ch03_p02 --engine fortran --bin-dir build/single/bin   # SINGLE build
uv run gerald-na run ch01_p01 --trace-json                        # full outcome as JSON
```

Lists are comma-separated (`--input a=0,1,-17.8,99.41,-261.218,352.611,-134.106`), point lists
are flat `x1,y1,x2,y2,...`, and reals accept the data-card spellings (`1.E-5`, `1.D-5`, `.5`).

**Inspect the catalog:**

```sh
uv run gerald-na catalog list            # id, book reference, scan, title
uv run gerald-na catalog check           # every entry valid and every referenced file present (exit 1 otherwise)
uv run gerald-na catalog index           # print the README program index
uv run gerald-na catalog index --check   # exit 1 if README.md or a study page's errata table is stale
uv run gerald-na catalog index --write   # regenerate them (make readme-index)
```

**Re-run the book-machine evidence** (`docs/architecture.md`, "The book's computer"): the
chopped-arithmetic emulation of the book's data cards on 27-bit binary and 8/9-digit decimal
machines.

```sh
uv run python -m gerald_na.tools.book_machine [--bits N] [--digits N]
```

## Web UI and JSON API

`make serve` starts the web tool. The home page lists the programs by chapter (unconfirmed
references last). Each program page has a form generated from the catalog and pre-filled with the
book's data card, an engine selector (Python, Fortran, compare), the iteration table, a Plotly
chart, the book-format text, "Result details", tabs for the original scan, the legacy OCR text,
the modern Fortran, the Python source and the study page, and practice questions whose answers
are checked by running the engines. Every interactive element has a `data-testid` for Playwright.

| Route | Response |
|---|---|
| `GET /healthz` | liveness and engine availability |
| `GET /` | home page |
| `GET /programs/{id}` | program page; `POST /programs/{id}/run` returns the results fragment (HTMX) |
| `POST /programs/{id}/practice/{question_id}` | practice-answer feedback fragment |
| `GET /api/programs` | JSON list of programs (inputs, presets, engines available, scan available, ...) |
| `GET /api/programs/{id}` | the full catalog entry with `/files/...` URLs |
| `POST /api/programs/{id}/run` | run: body `{"engine": "python"\|"fortran"\|"compare", "inputs": {...}, "preset": N, "expression": "...", "verbose": false}` |
| `GET /files/{id}/{kind}` | whitelisted catalog files only: `scan`, `legacy`, `fortran_module`, `fortran_app`, `python`, `study` |

```sh
curl -s localhost:8000/api/programs | jq '.[].id'
curl -s -X POST localhost:8000/api/programs/ch01_p01/run \
     -H 'content-type: application/json' -d '{"engine": "python", "inputs": {"tol": 0.001}}'
```

Errors are `{"error": {"code", "message", ...}}` with 404 (unknown program), 422 (`VALIDATION`,
`INPUT` with per-field messages, `EXPRESSION`, `CUSTOM_FUNCTION_ENGINE`) or 503
(`ENGINE_UNAVAILABLE`). A completed run is 200 even when the program stops on one of its own error
paths (`ok: false`, with `error.code` such as `BRACKET` or `NON_CONVERGENT`). The full contract is
in `docs/architecture.md`, "Web UI and JSON API".

## Adding a program

A program counts as migrated when all of these exist (the catalog schema and the trace protocol
are the extension contract; details in `docs/architecture.md`):

1. **Catalog entry** `catalog/chNN_pNN_<name>.toml` (id `chNN_pNN` for a confirmed book reference;
   otherwise a non-book id with `book_ref_confirmed = false`): book reference, summary, precision
   notes, inputs in data-card order, the data card as printed, function presets, trace columns,
   golden `expected` values with `tol_real64` / `tol_real32`, files (legacy, `scan_pdf` if there
   is one, Fortran module and app, executable, Python callable, study page), chart, `[[practice]]`
   questions and every `[[errata]]` item.
2. **Fortran**: a module in `fortran/src/` (procedure argument through an abstract interface,
   derived-type result with value, convergence flag and trace) and a thin driver in
   `fortran/app/` that reads the book's data card from stdin, prints the book's text, supports
   `--trace` (`STEP`/`RESULT`/`ERROR` records), `--verbose` and `--preset N`, and carries an
   ERRATA header with every catalog erratum id; test-drive cases in `fortran/test/` for every
   original branch.
3. **Python**: a standard-library-only function in `python/src/gerald_na/algorithms/` returning a
   frozen result dataclass (`value`, `converged`, `iterations`, `steps`, `book_text()`), typed
   errors from `gerald_na.errors`, and an engine adapter in
   `python/src/gerald_na/engines/adapters/` registered in `_BUILTIN`.
4. **Study page** `content/<id>.md` with the sections of the existing pages (method, data card,
   other outcomes, errata, precision, practice questions with `[practice-id]` markers) and an
   empty `<!-- ERRATA_TABLE_START -->` / `<!-- ERRATA_TABLE_END -->` block; then run
   `make readme-index` to fill the errata table and the program index.
5. **Tests**: unit and property tests for the algorithm; the golden, parity, catalog-integrity
   and generated-docs tests pick the entry up automatically; add one Playwright e2e test in
   `python/tests/e2e/`.
6. **Gates**: `make lint`, `make test`, `make test-fortran`, `make test-parity`, `make e2e` and
   `uv run gerald-na catalog check`.

## Further reading

* [`docs/architecture.md`](docs/architecture.md): repository layout and design decisions
  (program identities, trace protocol, Fortran presets, golden tolerances, file serving), the
  catalog schema, the engines, the web UI and JSON API, and the evidence about the book's computer.
* `content/*.md`: one study page per program (linked from the index above and from each program
  page in the web tool).
