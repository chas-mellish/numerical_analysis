# Architecture

This repository modernizes the card-image FORTRAN listings of C. F. Gerald's *Applied Numerical
Analysis* into three tracks that share one program catalog:

* a **Fortran 2018** fpm package (`fortran/`) that reproduces each book program,
* a **Python 3.15** port (`python/`, package `gerald_na`) with the same algorithms,
* a **web learning tool** (`gerald_na.web`, FastAPI + Jinja2 + HTMX + Plotly.js) that runs either
  engine and shows the original scan beside the modern code.

## Repository layout

```
numerical_analysis/
  legacy_code/fortran/...      untouched OCR transcriptions (reference only, never built)
  docs/*.pdf                   scanned book listings (source of truth for transcription)
  docs/architecture.md         this document
  catalog/<id>_<name>.toml     program metadata, inputs, presets, data card, golden outputs
  content/<id>.md              study pages
  config/settings.toml         runtime settings
  fortran/fpm.toml             Fortran package (gerald_na_fortran)
  fortran/src/                 precision.F90 and one module per method
  fortran/app/                 thin I/O drivers, one executable per program
  fortran/test/                test-drive suites
  python/pyproject.toml        Python package gerald-na (hatchling, uv)
  python/src/gerald_na/
    algorithms/                standard-library-only algorithms returning frozen result dataclasses
    expr/                      safe expression compiler for learner functions (ast whitelist)
    engines/                   Python engine, trace parser and FortranRunner
    registry/                  catalog loader and integrity checks
    web/                       FastAPI app factory (create_app), templates, static files
    errors.py                  typed errors with stable codes
    settings.py                pydantic-settings Settings
    cli.py                     gerald-na command line
  python/tests/{unit,golden,parity,web,e2e}
  build/bin/                   installed Fortran drivers (generated, not versioned)
  build/single/bin/            SINGLE-precision drivers (generated, not versioned)
  Makefile, Dockerfile, .devcontainer/, .github/workflows/ci.yml
```

### Toolchain

* **Fortran:** free-form Fortran 2018, built by fpm. gfortran builds use
  `-std=f2018 -fimplicit-none -Wall -Wextra -pedantic -Werror` (`-O2` for the installed drivers,
  `-Og -g -fcheck=all -fbacktrace` for `fpm test`). LLVM flang builds the same package with
  `-std=f2018 -pedantic -Werror` and runs `fpm test` with `-std=f2018 -Werror` (test-drive itself
  raises flang portability warnings under `-pedantic`). Flags are passed by the Makefile through
  `fpm --flag`, so `fpm.toml` stays compiler-neutral. fpm prints compiler output only when a
  compilation fails, so `-Werror` is what enforces warning-free code.
* **Working precision:** `fortran/src/precision.F90` exports `wp`, which is `real64` by default
  and `real32` when built with `-DSINGLE` (`make build-fortran-single`) to reproduce the book's
  single-precision digits.
* **Python:** `requires-python >= 3.14`, developed on 3.15 with uv. The algorithm modules use only
  the standard library; NumPy and SciPy are test-only references.
* **Settings:** `config/settings.toml`, overridden by `GERALD_NA_*` environment variables and read
  by `gerald_na.settings.Settings`. Relative paths are resolved against the repository root, which
  is auto-detected (nearest ancestor of the package containing `config/settings.toml` or
  `catalog/`) or set with `GERALD_NA_REPO_ROOT`.

## Program identities

| Catalog ID | Catalog file | Fortran executable | Study page | Program |
|---|---|---|---|---|
| `ch01_p01` | `catalog/ch01_p01_bisection.toml` | `ch01_p01_bisection` | `content/ch01_p01.md` | Interval halving (bisection) |
| `ch01_p02` | `catalog/ch01_p02_bairstow.toml` | `ch01_p02_bairstow` | `content/ch01_p02.md` | Bairstow quadratic factors |
| `ch03_p01` | `catalog/ch03_p01_simpson.toml` | `ch03_p01_simpson` | `content/ch03_p01.md` | Simpson's 1/3 rule, Si(B) |
| `ch03_p02` | `catalog/ch03_p02_romberg.toml` | `ch03_p02_romberg` | `content/ch03_p02.md` | Romberg integration, Si(B) |
| `lagrange_interpolation` | `catalog/lagrange_interpolation.toml` | `lagrange_interpolation` | `content/lagrange_interpolation.md` | Lagrangian interpolation |

Program pages are served at `/programs/<catalog id>`.

## Design decisions

### DD1: Identity of the Lagrange program

The Lagrangian interpolation listing has no scan, and its chapter and program number in the book
are unconfirmed. It therefore uses a non-book slug instead of a `chNN_pNN` identifier:

* Catalog ID `lagrange_interpolation`, file `catalog/lagrange_interpolation.toml`, Fortran
  executable `lagrange_interpolation`, module `lagrange_mod`, Python function
  `gerald_na.algorithms.lagrange.lagrange`, study page `content/lagrange_interpolation.md`,
  URL `/programs/lagrange_interpolation`.
* The catalog schema makes `book_ref` optional (its `chapter`, `program` and `page` are each
  optional) and adds `book_ref_confirmed: bool` (false for Lagrange, true for the others).
  `scan_pdf` is optional and absent for Lagrange.
* The scan tab of the UI shows a "no scan available" empty state (`data-testid="scan-missing"`).
* A confirmed book reference can be added later without renaming any file.

### DD2: Trace protocol (`--trace`)

Every driver run with `--trace` prints only machine-readable lines to stdout, one record per line.
Fields are comma-separated; the first field is the record type and the others are `key=value`:

* `STEP,k=<int>,<key>=<real>,...`: one record per iteration row. The keys of each program are
  declared in its catalog entry (`[trace] step_columns = [{key = "x", label = "X"}, ...]`), so the
  parser is generic and the UI table headers come from the catalog.
* `TABLE,row=<i>,col=<j>,value=<real>`: table cells. For Romberg, `row` is the extrapolation-order
  index and `col` the halving index, matching `TRAP(row,col)`.
* `FACTOR,kind=<quadratic|linear|final_quadratic>,<coefficient keys>=<real>...`: Bairstow factors.
  Other program-specific record types are allowed when documented in the catalog `[trace] records`.
* `RESULT,value=<real>,converged=<T|F>,iterations=<int>[,<extra key>=<value>...]`: exactly one
  on success.
* `ERROR,code=<CODE>,message=<text without commas>`: printed instead of `RESULT` on error paths.

Formatting: reals use `ES25.17E3` (full real64 precision), integers `I0`, logicals `T`/`F`.

Error codes map one-to-one to the Python error classes in `gerald_na.errors`:

| Trace code | Python class |
|---|---|
| `INPUT` | `InputError` |
| `BRACKET` | `BracketError` |
| `ZERO_PRODUCT` | `ZeroProductError` (subclass of `BracketError`; the bisection `ERROR.` branch) |
| `ODD_PANELS` | `OddPanelsError` |
| `NON_CONVERGENT` | `NonConvergenceError` |
| `DEGREE` | `DegreeError` |

A root found at an interval endpoint is not an error: it is a `RESULT` with `root_at_endpoint=T`.
Engine-level failures use `EngineError` (`ENGINE`), `EngineUnavailableError`
(`ENGINE_UNAVAILABLE`) and `FortranRunError` (`FORTRAN_RUN`, also used for unknown trace codes).

Command-line behaviour of every driver:

* Without `--trace`, stdout is the book's line-printer text, reproducing the layout of the scan.
* `--verbose` adds extras after the book text (for example Bairstow's true factors and roots).
* `--preset N` selects the book function (DD3).
* Flags may appear in any order. stdin is always the pure book data card, read list-directed.
* Exit status 0 on success. On an error path, book-text mode prints the book's message and exits
  with 1; trace mode prints the `ERROR` record and exits with 2.

On the Python side, `gerald_na.engines.trace` holds the generic parser and `FortranRunner` maps
the records into the same result dataclasses that the Python engine returns.

### DD3: Functions on the Fortran engine

* The function is chosen with the `--preset N` flag; stdin stays the book data card, so the
  printed data cards work unchanged. The default preset is the book's function (1).
* The preset table lives in the catalog (`[[presets]] id = 1, expr = "EXP(-X) - SIN(3.1415926*X/2.)",
  label = ...`) and in a matching `select case` in the Fortran code. The Python engine evaluates
  the same expression through `gerald_na.expr`.
* Bisection presets: 1 `exp(-x) - sin(pi*x/2)` (the book's, with pi = 3.1415926), 2 `x**3 - x - 1`,
  3 `cos(x) - x`.
* Simpson and Romberg presets: 1 `sin(x)/x` with the limit 1 at x = 0 (the book's),
  2 `exp(-x**2)`, 3 `1/(1+x**2)`.
* Bairstow and Lagrange take data, not functions, and have no presets.
* When the learner enters a custom expression instead of a preset, the UI disables the Fortran and
  compare engines, and the API answers 422 if they are requested.

### DD4: Golden tolerance policy

Each catalog `[[expected]]` entry has a `name`, the `book_value` transcribed from the scan,
`tol_real64`, `tol_real32`, and optionally a `real64_value` with a tighter `tol_real64_value`.
Exact-integer expectations (`iterations`, `subintervals`, row counts) are compared exactly.

* Default (real64) Fortran builds and the Python engine are compared against `real64_value`
  (tight), when present, and against `book_value` within `tol_real64`.
* A `SINGLE` Fortran build is compared against `book_value` within `tol_real32`.
* Iteration counts are compared exactly; any exception caused by precision is documented in the
  program's errata.

### DD5: Serving scans and sources

The UI shows the scan, the legacy OCR text, the modern Fortran and the Python source through one
whitelisted route, `GET /files/{program_id}/{kind}`, with `kind` one of `scan`, `legacy`,
`fortran_module`, `fortran_app`, `python` and `study`. The file path comes only from the catalog
entry and is resolved under the repository root (`repo_root` from settings). No user-supplied
paths are accepted, which rules out path traversal and keeps the files in one place. The container
image therefore includes `docs/`, `legacy_code/`, `fortran/`, `catalog/`, `content/` and `python/`.

## Catalog schema

Each book program is described once in `catalog/<id>[_<name>].toml`. The file name must be the id
or start with `<id>_`. `gerald_na.registry` loads every file with `tomllib` into frozen pydantic v2
models that reject unknown keys (`gerald_na.registry.models.CatalogEntry`), so a misspelt key is an
error. The catalog drives the UI forms, the golden tests, the Fortran test fixtures and the README
index. **Adding a future chapter's program means adding one catalog file plus the two
implementations**, then running `gerald-na catalog check`. `catalog/ch01_p01_bisection.toml` is
the reference example.

### Top-level keys

| Key | Type | Meaning |
|---|---|---|
| `id` | string | Catalog id: `chNN_pNN` for confirmed book programs (it must match `book_ref`), otherwise a slug such as `lagrange_interpolation` |
| `title`, `method`, `summary` | string | Display title, method name, and a paragraph describing the method and the book's run |
| `book_ref_confirmed` | bool | `true` requires `book_ref.chapter`, `program` and `page` |
| `precision_notes` | string | Real32 versus real64 versus book digits; shown on the study page |
| `book_output` | string | The line-printer output exactly as printed in the scan (carriage-control column dropped, leading zeros suppressed as printed) |

### Tables

* **`[book_ref]`** (optional): `chapter`, `program`, `page`, `title` (the chapter title as
  printed), each optional (DD1).
* **`[[inputs]]`** (at least one), in data-card order:
  * `name`: lower-case identifier, the Python keyword argument.
  * `type`: `real`, `int`, `real_list` or `point_list` (a list of `[x, y]` pairs).
  * `label`, `help`: UI text.
  * `default`: the book data card's value.
  * `min`, `max` (optional): inclusive bounds, applied to every number of a list.
  * `card`: 1-based data card number. Cards must run from 1 without gaps; inputs are read card
    by card in declaration order.
  * `length` (optional, lists only): fixed list length.
* **`[data_card]`**:
  * `text`: the card(s) exactly as printed, possibly multi-line.
  * `values`: one entry per input.
  * `note` (optional).

  Validation checks that `values` equal the input defaults and that the list-directed fields of
  `text` (separated by blanks or commas; Fortran reals like `0.`, `1.E-5`, `1.D-3` are accepted)
  are, in order, the flattened defaults. Integer inputs need integer fields.
* **`[function]`**:
  * `takes_function`: bool.
  * `variable`: default `"x"`.
  * `default_preset`: required when the program takes a function.
  * `[[function.presets]]`: `id`, `label`, `expr` (compiled by `gerald_na.expr`), `fortran_preset`
    (must equal `id`; the value passed to `--preset`), and an optional `note`.

  Programs that take data instead of a function (Bairstow, Lagrange) declare
  `takes_function = false` and no presets (DD3).
* **`[trace]`** (DD2):
  * `step_columns`: list of `{key, label, format}`. The `key` is the `STEP` record key and the
    Python step attribute; the `format` is a Fortran edit descriptor (`I3`, `F10.7`, `E15.7`,
    `ES25.17`, `G0`, `Ln`, `A`). `I` columns are integers and are compared exactly.
  * `records`: extra record types, each `{type, fields, description}`, for example Bairstow's
    `FACTOR`.
  * `result_extras`: extra `RESULT` keys, each `{key, type = real|int|bool|text, description}`.
    They may not redefine `value`, `converged` or `iterations`.
* **`[[expected]]`** (DD4, at least one):
  * `name`: unique identifier.
  * `field` (optional, default `name`): the result attribute compared.
  * `description` (optional).
  * `kind` and `book_value`, the value transcribed from the scan:
    * `real`: a number.
    * `int`: an exact integer.
    * `text`: an exact string.
    * `table`: a ragged list of rows, for example Romberg's triangle.
    * `rows`: a list of rows whose cells correspond to `columns`, a list of step keys.
  * `tol_real64`, `tol_real32`: absolute tolerances. They are required for `real`, `table` and
    `rows`, and forbidden for `int` and `text`. For `rows` they may be a per-column table such as
    `{ x = 1e-7, fx = 1e-6 }`; columns without an entry are compared exactly.
  * `real64_value` with `tol_real64_value` (optional, together): the tighter real64 reference, in
    the same shape as `book_value`.
* **`[files]`**: paths are relative POSIX paths under the repository root. Absolute paths, `..`,
  `.`, empty segments and backslashes are rejected.
  * `legacy`: list of at least one path.
  * `scan_pdf`: optional; absent means "no scan available".
  * `fortran_module`, `fortran_app`.
  * `fortran_executable`: the name in `build/bin`; it must be the id or start with `<id>_`.
  * `python_callable`: `module.path:function`.
  * `study_page`.
* **`[chart]`**:
  * `kind`: one of `bracket`, `abs_residual`, `romberg_heatmap`, `integrand_panels`, `factors`,
    `interpolant`.
  * `options`: a free-form table of scalars or lists.
* **`[[practice]]`**:
  * `id`: slug, cited as `[id]` on the study page.
  * `prompt`.
  * `inputs`: overrides of the defaults, validated against the inputs' types and bounds.
  * `preset` (optional): a preset id.
  * `answer_field`: `value`, `iterations`, `converged` or a result extra.
  * `answer` (optional): reference answer, as computed by the engines.
  * `tolerance`.
  * `explanation`.

  The web layer checks a learner's answer by running an engine with the overrides
  (`CatalogEntry.practice_inputs`).
* **`[[errata]]`**:
  * `id`.
  * `kind`, one of:
    * `ocr_slip`: an error in the text transcription.
    * `original_bug`: a genuine bug in the book's program.
    * `original_quirk`: odd but intended behaviour of the original.
    * `rewrite_drift`: where an earlier partial rewrite in `legacy_code/` departed from the scan.
    * `modernization`: a deliberate change made by the modern code.
  * `original`, `corrected`, `note`.

  Every erratum is mirrored in the Fortran ERRATA header and the study-page errata table.

### Registry API

* `Registry.load(repo_root)` validates every file. It raises `CatalogError` naming the file on
  invalid TOML or schema errors.
* `.programs` lists programs ordered by (chapter, program). Unconfirmed references come last,
  sorted by id.
* `.get(id)` returns one program.
* `.by_chapter()` groups programs by confirmed chapter; the key `None` holds the unconfirmed
  ones.
* `get_registry()` is the cached registry for `get_settings().repo_root`.
* `resolve_path(entry, kind)` is the whitelist used by `GET /files/{program_id}/{kind}` (DD5):
  * `kind` is one of `scan`, `legacy`, `fortran_module`, `fortran_app`, `python`, `study` or
    `catalog`.
  * Only paths named by a catalogued entry can be produced.
  * The resolved path, after following symlinks, must stay under the repository root; otherwise
    it raises `CatalogPathError`. `python` maps the callable's module to its file under
    `python/src/`.
* `check_integrity()` returns the list of problems:
  * duplicate ids, file names that do not match the id, and shared executables;
  * missing referenced files: legacy, the scan when one is named, Fortran module and app, and
    study page;
  * a Python callable that cannot be imported or is not callable;
  * blank preset expressions, or ones that do not compile;
  * defaults or practice overrides out of bounds.

  Files that no entry references, such as the un-migrated Chapter 4/5 PDFs, are never inspected.
  `gerald-na catalog check` prints the problems and exits with status 1. `gerald-na catalog list`
  prints the index. The test `python/tests/unit/test_catalog_integrity.py` requires an empty
  list.

## Conventions

* Python results are frozen dataclasses with `value`, `converged`, `iterations`, `steps` and a
  `book_text()` method that renders the line-printer output.
* Every interactive HTML element carries a `data-testid` attribute.
* Fortran-dependent tests are marked `fortran` and locate the drivers through the
  `fortran_bin_dir` setting; they are skipped with an explicit reason when the drivers are absent.
* No absolute paths in code, configuration or tests.
