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
  fortran/src/                 precision.F90, one module per method, and the driver helpers
                               book_format_mod (book/trace formatting) and cli_mod (flags)
  fortran/app/                 thin I/O drivers, one executable per program
  fortran/test/                test-drive suites
  python/pyproject.toml        Python package gerald-na (hatchling, uv)
  python/src/gerald_na/
    algorithms/                standard-library-only algorithms returning frozen result dataclasses
    expr/                      safe expression compiler for learner functions (ast whitelist)
    engines/                   Python engine, trace parser and FortranRunner
    registry/                  catalog loader, integrity checks, generated Markdown (README index, errata tables)
    tools/                     developer tools (book_machine: chopped-arithmetic emulation)
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
| `ch04_p01` | `catalog/ch04_p01_central_difference.toml` | `ch04_p01_central_difference` | `content/ch04_p01.md` | Derivatives by central differences |
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
the records into the same result dataclasses that the Python engine returns (see "Engines"
below). A `RESULT` record carries every result field that does not come from the request, so the
dataclass can be rebuilt from the trace alone; for bisection these are the extras
`root_at_endpoint`, `fx1` and `fx2` (F at the data card's X1 and X2).

A function value that is not finite (NaN or an infinity, for example `EXP(-X)` overflowing for
X < -709 in real64) is an `INPUT` error on both engines, reported after the rows completed
before it.

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
* Central-difference presets (ch04_p01): 1 `x**2*exp(x)` (the book's), 2 `sin(x)`,
  3 `1 + log10(x)` (the p. 91 problem 2 table).
* Preset ids are scoped per program family: `functions_mod` has one `get_<family>_preset`
  routine and `<family>_preset_count` per family (`bisection`, `quadrature`, `derivative`), and a
  driver calls only its own family's routine, so every family numbers its presets from 1.
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
paths are accepted, which rules out path traversal and keeps the files in one place. A `legacy`
file may be a PDF (a page kept only as a scan, such as `ch04_p01`'s, which has no OCR text): it is
served as `application/pdf` and the Legacy tab links it (`legacy-source-<i>-pdf`) instead of
showing it as text. The container
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
  * `legacy`: list of at least one path: the OCR text, or, when none exists, the scanned pages
    (`.pdf`, linked rather than shown in the Legacy tab).
  * `scan_pdf`: optional; absent means "no scan available".
  * `fortran_module`, `fortran_app`.
  * `fortran_executable`: the name in `build/bin`; it must be the id or start with `<id>_`.
  * `python_callable`: `module.path:function`.
  * `study_page`.
* **`[chart]`**:
  * `kind`: one of `bracket`, `abs_residual`, `romberg_heatmap`, `integrand_panels`, `factors`,
    `interpolant`, `convergence`.
  * `options`: a free-form table of scalars or lists; what each kind reads is listed under
    "Web UI and JSON API", "Chart kinds".
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

  Files that no entry references are never inspected, so scans that are not catalogued (such as
  the Chapter 5 formula summary `legacy_code/fortran/chapter_5/integration_methods.pdf`, which
  holds no program) cannot make the check fail.
  `gerald-na catalog check` prints the problems and exits with status 1. `gerald-na catalog list`
  prints the index. The test `python/tests/unit/test_catalog_integrity.py` requires an empty
  list.

### The book's computer (not identified)

The scans do not name the computer the listings ran on, and the evidence points two ways, so
every catalog entry, study page and driver header treats the identification as open:

* **Deck-control cards (ch01_p01).** The bisection page shows `ZZJOB` and `ZZFORX` cards, which
  look like IBM 1620 Monitor control cards. The 1620 (FORTRAN II-D) used decimal floating point,
  8 digits by default, with chopped results.
* **Coefficient echo (ch01_p02).** Bairstow prints 99.41000, -17.80000 and -261.21800. A decimal
  machine holds these exactly. A binary machine whose output conversion chops (the X column of
  ch01_p01 shows that the printer chopped) would print 99.40999, -17.79999 and -261.21799.
* **Accumulated sums (ch03_p01, ch03_p02).** Emulating 27-bit binary chopped arithmetic (the
  single precision of the IBM 704/709/7090/7094) gives Si(5) = 1.54993066 for Simpson (book
  1.5499307: that is the value rounded; chopped it prints 1.5499306) and a last Romberg line
  within 3e-7 of the book (1.6181938 against 1.6181936). An 8-digit decimal chopped emulation is
  further off: 1.5499262 and 1.6181909 (9 digits: 1.5499308 and 1.6181941). The machine's SIN
  routine is unknown (the emulations chop a correctly rounded sine), so these are indications,
  not proof.
* **Not discriminating.** Bisection's printed digits, including the F(X) entries `.000001`
  (row 15) and `-.000506` (row 11) that the real64 and real32 builds each miss by one unit, are
  reproduced by both the 8-digit decimal and the 27-bit binary model. The names SINF, EXPF and
  ABSF are the FORTRAN II convention on the 1620 and on the 7090 family alike.

A plausible reading is that the listings did not all run on the same machine: chapter 1 on a
decimal one (IBM 1620 class) and chapter 3 on a 27-bit binary one (IBM 7090 class). Neither is
confirmed. Nothing in the modern code depends on the answer: the engines compute in IEEE real64
(real32 with `SINGLE`), the book text imitates the printer (chopped digits, no leading zero), and
the golden tests compare numbers within the DD4 tolerances.

**Re-running the evidence.** Every number above comes from
`python/src/gerald_na/tools/book_machine.py` (standard library only). It models a machine as a
mantissa of N binary or decimal digits whose every result is chopped (exact `Fraction`
arithmetic, then truncation toward zero), and replays the Simpson, Romberg and bisection cards
in the listings' operation order, plus the Bairstow coefficient echo:

```sh
cd python
uv run python -m gerald_na.tools.book_machine                 # 27-bit binary, 8- and 9-digit decimal
uv run python -m gerald_na.tools.book_machine --bits 24 --digits 7   # other models
```

`python/tests/unit/test_book_machine.py` pins the quoted values, so this section and the tool
cannot drift apart.

## Engines

`gerald_na.engines` runs a catalog program on either engine and returns the same result
dataclass from both (for example `BisectionResult`), so the UI, the golden tests and compare mode
never depend on the engine.

### API

```python
from gerald_na.engines import RunRequest, run_program, compare, get_engine, available_engines

request = RunRequest.for_entry(entry, {"tol": 1e-3}, preset=2)   # book card + overrides
outcome = run_program("ch01_p01", request, "fortran")            # or "python", or an Engine
report = compare("ch01_p01", request)                            # python vs fortran diff
```

* `RunRequest(inputs, preset=None, expression=None, verbose=False)`: inputs keyed by catalog
  input name; `preset` (default: the catalog `default_preset`) and `expression` (a learner
  function, Python engine only) are mutually exclusive. `RunRequest.for_entry(entry, overrides)`
  starts from the book data card.
* `Engine.run(entry, request) -> RunOutcome`; engines: `PythonEngine` (`name = "python"`) and
  `FortranRunner` (`name = "fortran"`). `get_engine(name, settings)` builds one (respecting
  `engines_enabled`); `available_engines(settings, entry=None)` lists the enabled engines that
  can run now (Fortran only when the driver is built).
* `RunOutcome`: `engine`, `program_id`, `inputs` (validated), `preset`, `expression`, exactly
  one of `result` (the program's result dataclass) and `error` (a typed `GeraldNAError` with
  `code`, `message` and the partial `steps`), `book_text`, `elapsed_ms`, `verbose_text`, and for
  Fortran `raw_stdout` (book-mode stdout, carriage-control blanks kept) and `trace_text`.
  Properties `ok`, `status` (`OK` or the error code), `steps`; `to_dict()` gives JSON.
* `book_text` is the line-printer text with the carriage-control column consumed, as in the
  scan, on both engines: Python's `result.book_text()` (or the error's `book_output`), Fortran's
  own book-mode stdout. Python's `book_text(carriage_control=True)` equals the driver's stdout
  character for character (checked by the parity tests).
* `compare(program_id, request, engines=("python", "fortran"), rel_tol=0, abs_tol=0)` runs both
  engines and returns a `CompareReport`: per step column the largest absolute and relative
  difference and the first differing row, the differing cells, mismatched iteration and row
  counts, both outcomes' statuses, the difference of the final values, and `matches`.
  `diff_outcomes(entry, left, right)` diffs two existing outcomes.
* Command line: `gerald-na run <program_id> [--engine python|fortran|compare] [--preset N]
  [--expr "..."] [--input name=value ...] [--verbose] [--trace-json] [--bin-dir DIR]` prints the
  book text (or JSON); exit status 0 success, 1 a book error path or engine failure, 2 an invalid
  request. Lists are given comma-separated, point lists as `x1,y1,x2,y2,...`.

Error contract of `Engine.run`: problems with the request are raised before anything runs --
`InputError` (unknown or missing input, wrong type, strings or booleans, NaN or infinity, outside
the catalog `min`/`max`, wrong list length, integers that do not fit a Fortran integer, unknown
preset; `ExpressionError` for a bad learner function; a learner function sent to the Fortran
engine) and `EngineUnavailableError` (engine disabled, program without an adapter, driver not
built). Everything that happens while the program runs is returned in `outcome.error`: the book
errors (`BracketError`, `ZeroProductError`, `NonConvergenceError`, ...), `InputError` for a
function value that is not finite, and `FortranRunError` for a timeout, a crash or a protocol
violation. When a *preset* cannot be evaluated the Python engine reports `INPUT` like the
Fortran driver; `EXPRESSION` is reserved for the learner's own function.

### Python engine

`PythonEngine` compiles the preset's catalog expression (the same text as the Fortran
`select case`) or the learner's expression with `gerald_na.expr` and calls the algorithm through
the program's adapter. As in Fortran, an integer literal exponent (`X**3`) is an integer power
evaluated by multiplication (square-and-multiply in libgcc's `__powidf2` order) and a real
exponent (`X**3.`) uses `pow`; this keeps the presets bit-identical to the compiled drivers (for
`x**3 - x - 1` near its root, `pow` would differ by an ulp of x**3, 5e-11 relative after the
cancellation).

### Fortran runner and its safety rules

`FortranRunner(settings=None, *, bin_dir=None, registry=None, timeout_s=None,
max_output_bytes=1_000_000, label=None)`; `bin_dir` defaults to `settings.fortran_bin_dir`
(`build/bin`) and may name another build, for example `settings.fortran_single_bin_dir`
(`build/single/bin`, `make build-fortran-single`). Relative directories resolve under the
repository root.

* **Executable whitelist.** Only the `files.fortran_executable` names of the loaded catalog can
  run, only from `bin_dir`, and the entry passed in must equal the catalog's entry for its id, so
  a forged entry cannot name another file. A missing or non-executable driver is
  `EngineUnavailableError`.
* **No shell, numeric stdin.** `subprocess.run([driver, flags...], input=card,
  capture_output=True, timeout=settings.run_timeout_s, shell=False)` with the fixed flags
  `--trace`, `--verbose` and `--preset <int>` (the preset's `fortran_preset`). The card is written
  by the adapter from inputs already validated against the catalog. The environment is reduced to
  `PATH`, `LC_ALL=C`, `LANG=C` and the shared-library path, so `GFORTRAN_*` settings of the server
  cannot change the drivers' behaviour.
* **Bounded runs.** The timeout (`run_timeout_s`, default 5 s) kills a hung driver and becomes a
  `FortranRunError`; stdout plus stderr above `max_output_bytes` is a `FortranRunError` (the
  timeout bounds what can be produced before the check).
* **Learner functions are refused** (`InputError`, DD3); the web layer answers 422.
* **Exit status mapping.** Trace mode: 0 with a `RESULT` record is success; 2 with an `ERROR`
  record becomes the typed error of its code (`errors.TRACE_ERROR_CODES`), carrying the `STEP`
  rows printed before it; an unknown code, a missing or misplaced terminal record, any malformed
  line, any other status or a signal is a `FortranRunError` quoting the end of stderr. Book mode
  accepts 0 and 1 (a book error path).
* **Two runs per request.** One `--trace` run is parsed into the result; one book-mode run
  captures the driver's own line-printer text for the UI (`raw_stdout`, `book_text`); a `verbose`
  request adds a `--verbose` run whose extras go to `verbose_text`. Each takes a few
  milliseconds. `FortranRunner.execute(entry, card, preset=, trace=, verbose=)` is the
  single-run primitive (used by the golden test that feeds the card exactly as printed).

### Trace parser

`gerald_na.engines.trace.parse_trace(text) -> Trace` is program-independent. Each line becomes a
`Record(type, fields, line)`; values are typed by spelling (`T`/`F` -> bool, integer literal ->
int, anything `float()` accepts -> float, otherwise text) and read with `record.real(key)`,
`.integer(key)`, `.logical(key)` and `.text(key)`. The `message` of an `ERROR` record runs to the
end of the line. `Trace.steps`, `.of_type("TABLE")`, `.result` and `.error` give access by record
type. Blank lines and trailing padding are ignored; a lower-case or missing record type, a field
that is not `key=value`, a duplicate or empty field, a line over 4096 characters, no terminal
record, more than one, or one that is not last, and a `RESULT` without `value`, `converged` and
`iterations` (or an `ERROR` without `code` and `message`) raise `FortranRunError`.

### Adding a program to the engines

Program-specific code lives only in adapters (`gerald_na.engines.programs.ProgramAdapter`). To
add a program (Bairstow, Simpson, Romberg, Lagrange or a future chapter):

1. Write the catalog file, the Fortran module and driver (with `--trace` per DD2: `STEP` keys =
   catalog `step_columns`, every result field not taken from the inputs in `RESULT` extras listed
   in `result_extras`, program-specific records listed in `[trace] records`), and the Python
   algorithm whose step dataclass fields equal the `step_columns` keys. Drivers format output
   with `book_format_mod` (`book_fixed`, `book_fixed_nearest`, the Chapter 4 `book_e` and
   `fixed_leading_zero`, the `trace_*` helpers and
   `no_commas` for `ERROR` messages) and, when they take a function preset, parse their flags
   with `cli_mod`'s `parse_arguments`; they do not keep private copies of these helpers.
2. Create `python/src/gerald_na/engines/adapters/<name>.py` with a `ProgramAdapter` subclass:
   * `program_id`, `result_type` (the result dataclass) and `step_type` (the step dataclass);
   * `run_python(entry, inputs, function)`: call the algorithm with the validated inputs (keyed by
     catalog input name) and the compiled function (`None` for data-only programs such as
     Bairstow and Lagrange);
   * `result_from_trace(entry, inputs, trace)`: build `result_type` from `trace.result`, the
     steps from `self.steps_from_trace(entry, trace)` and other records (for example
     `trace.of_type("TABLE")` for the Romberg table, `trace.of_type("FACTOR")` for Bairstow), and
     raise `FortranRunError` on inconsistent records;
   * optionally override `input_problems(entry, inputs) -> {input name: message}` for
     constraints between inputs that the per-input bounds cannot express (Lagrange: `n` must
     equal the number of points). Both engines call `check_inputs` (which raises `InputError`
     with those messages) after request validation and before anything runs; the web layer
     reports them per field (422 `INPUT` with `fields`);
   * optionally set `count_inputs = {count input: list input}` when an integer input counts the
     rows of a list input (Lagrange: `{"n": "points"}`). The web form marks that field with
     `data-count-of` and `static/app.js` keeps it equal to the number of rows as the learner
     adds or removes rows; `input_problems` still enforces the rule on every request;
   * optionally override `substituted_ordinates(entry, function) -> {x: value}` when the program
     uses a fixed value instead of F(x) somewhere (Simpson and Romberg: F(0) = 1 for the book's
     SIN(X)/X); the charts draw F the same way. Shared input accessors (`real_input`,
     `int_input`) and the book-function test (`is_book_function`, `book_seed_for`) are in
     `gerald_na.engines.adapters._common`;
   * optionally override `data_card(entry, inputs)` when the driver's `READ` statements need a
     layout other than the generic one (one line per catalog `card`, numbers with `repr`
     precision, every `point_list` pair on its own line), `steps_from_trace` when the `STEP`
     records are not one flat list, and `verbose_text(entry, inputs, result, *, preset,
     function)` when the driver prints `--verbose` extras: it must return the same text as the
     driver (real64 build; `trace_real`, `trace_logical` and `verbose_header` in `_common`
     reproduce `book_format_mod` and the common first records). Bisection, Bairstow, Simpson,
     Romberg and Lagrange all do.
3. Import it in `gerald_na/engines/adapters/__init__.py` and add an instance to `_BUILTIN`.
4. Run the tests: the golden tests, the parity tests and `test_every_catalog_entry_has_an_adapter`
   pick the new catalog entry up automatically. If the program's inputs constrain each other
   (Lagrange's `n` and its number of points), override `ProgramAdapter.random_inputs` and set
   `parity_outcomes` (the statuses the generated sets must reach; and optionally `parity_cases`,
   labelled hand-built input sets) on the adapter. The parity tests never name a program id.

### Program-specific notes

* **ch01_p02 (Bairstow).** Data-only program (`takes_function = false`): the driver rejects `--preset`. Card 1 is the
  `real_list` input `a` (seven coefficients, X**6 first), card 2 is `r1 s1 test lim n`; the generic
  `serialize_card` writes one line per card.
* Trace: `STEP` rows carry `factor` and `k` (KOUNT restarts at 1 per factor and after a
  zero-denominator nudge); a `FACTOR` record follows the last `STEP` of each factor; `RESULT`
  `value` is the number of factors (an integer) with the extra `nudges`. Errors: `NON_CONVERGENT`
  (book FORMAT 24) and `DEGREE` (N outside 2..6 or a nonzero coefficient above X**N).
* `--verbose` text (true factors X**2 - R X - S and roots) is identical on both engines
  (`BairstowResult.verbose_text`), checked by the generic `test_verbose_text_agrees` in
  `python/tests/parity/test_parity.py` (it covers every adapter that overrides `verbose_text`).
  `BairstowAdapter.random_inputs` draws the coefficients with N, and its `parity_cases` add the
  `singular` card (x**4 - 16 from R = S = 0: a zero denominator, one nudge).
* Book text: factor lines use RZ (the book's chopped digits); the echoed coefficients use RN,
  because binary 99.41 would chop to 99.40999.
* **ch03_p01 (Simpson), the X = 0 seed.** The listing starts its sum with the literal `1.0`, the
  limit of SIN(X)/X at 0. The catalog expression `SIN(X)/X` divides by zero there on the Python
  engine, while the Fortran preset `f_sinc` returns 1. Both algorithms therefore take the first
  ordinate as an optional `f0` argument (default: evaluate `f(0)`). The adapter passes the
  book's `1.0` only when the function normalizes to the book's integrand (preset 1, or a learner's
  `SINF(X)/X`); the test is the shared `book_seed_for` of `gerald_na.engines.adapters._common`,
  and both adapters derive from its `BookSeededIntegrandAdapter`, which also reports the seed as
  `substituted_ordinates` so the `integrand_panels` chart draws F(0) = 1 instead of a gap. Any other function supplies its own F(0); a learner function undefined at 0 is an
  `EXPRESSION` error. The `ODD_PANELS` trace message writes the comma of the book message as `;`.
* **ch03_p02 (Romberg), table and seed.** The `TABLE,row=..,col=..,value=..` records carry every
  computed `TRAP(row, col)` (row = extrapolation order, col = halving index + 1) in the book's
  printing order; the adapter rebuilds `RombergResult.table`, whose line `L` is
  `TRAP(1..L, L)` as printed, and rejects missing, repeated or out-of-triangle cells. `STEP` is
  one record per halving (`k` = 1..8), so `iterations` is the number of halvings and the table
  has `iterations + 1` lines. Not meeting TOL after 8 extrapolations is a `RESULT` with
  `converged=F` (exit status 0), as the book prints the table and a note. The seed
  `SUM = 1. + FCN(B)` follows the Simpson convention through the same shared base class.
* **ch04_p01 (central differences).** Scan only (`legacy_code/fortran/chapter_4/derivatives.pdf`,
  book p. 90; no OCR text, so `files.legacy` lists the p. 90 and p. 91 scans, which the Legacy tab
  links). `STEP,k,h,dx,ddx` per printed row (always 10); `RESULT` `value` is DX of the last row
  (the smallest H; there is no stopping test, `converged=T`), extras `fo`, `first_dx`,
  `first_ddx`, `last_ddx`, which the adapter checks against the first and last `STEP`. H is
  accumulated (`H = 0.1*H`, with a `wp` literal on the Fortran side). Book text: the scan prints
  `E` fields with one digit before the point (`ES` editing) and a zero as `0.0000000E-99`; DX
  and DDX are chopped, the echoed X (`F5.2` with its leading zero) and H rounded to nearest. A
  non-finite F, DX or DDX is `INPUT` with the rows so far; the heading is printed before
  `FO = F(X)`, so the book text of such a run holds the heading. Preset 3 (`1 + LOG10(X)`, the
  p. 91 problem 2 table) is undefined at the book card, so `parity_outcomes` includes `INPUT`.
* **lagrange_interpolation.** No scan exists; the listing was transcribed from the OCR text only, and the corrections are
  justified by syntax, the FORMAT Hollerith counts and the printed 2.3119 (see the catalog
  errata). The pairs are X(I), Y(I) in READ order (verified numerically).
* The driver reads the whole of stdin and parses it list-directed, so N is checked against
  `DIMENSION X(10), Y(10)` (`DEGREE`) before the pairs are read and any card layout works.
  Equal X values (a division by zero in the original) are an `INPUT` error on both engines.
* The adapter writes the book's card layout (`05`, one pair per line, XIN) and reports
  `n != len(points)` from `input_problems` (keyed by `n`: the web form marks that field and the
  API lists it in `fields`); its `random_inputs` draws consistent, well-spaced parity data.
* The `interpolant` chart (nodes, curve, and the evaluated point) is sampled by the generic
  chart builder in `gerald_na.web.charts` from the result's nodes.

### Golden and parity tests

* `python/tests/golden/test_golden.py` runs every catalog entry's data card on the Python engine,
  the default Fortran build (`build/bin`) and the `SINGLE` build (`build/single/bin`) and checks
  every `[[expected]]` entry with the DD4 policy (real64 engines against `real64_value` and
  `tol_real64`, the `SINGLE` build against `tol_real32`, integers and `I` columns exactly). It
  also feeds each driver the data card exactly as printed in the scan and requires the same trace
  as the generated card. Fortran cases are marked `fortran` and skipped with the build command
  when the driver is absent.
* `python/tests/parity/test_parity.py` (all marked `fortran`; `make test-parity` builds the
  drivers first) runs, for every entry and preset, the data card and 24 reproducible random input
  sets within the catalog bounds through both engines and requires the same status (and the same
  book message), the same rows and iterations, every real within 1e-12 relative, the same book
  text, and for the data card Python's `book_text(carriage_control=True)` equal to the driver's
  stdout. In practice the two engines agree bit for bit.

## Web UI and JSON API

`gerald_na.web.app.create_app(settings=None, *, registry=None)` builds the FastAPI app (`gerald-na
serve` / `make serve`). Everything is generated from the catalog: a new catalog file plus its engine
adapter appears on the home page, gets a program page, a form, charts, tabs and practice questions
without web-layer changes. The catalog is loaded lazily, so `/healthz` works without one.

Modules: `services.py` (`WebState`: lazy registry, engine availability per program, shared request
validation and running for HTML and API), `forms.py` (form field names and number parsing),
`presenters.py` (iteration table, result extras, compare highlighting), `charts.py` (Plotly figure
specs per chart kind), `practice.py` (answer checking), `pages.py`, `api.py`, `files.py`
(routers), `markdown.py` (study pages), `middleware.py` (body limit, security headers),
`templates/` (Jinja2, autoescaping on everywhere) and `static/` (app JS/CSS and the vendored
HTMX 2.0.11 and Plotly.js 3.7.0 cartesian bundle with their licences, `static/vendor/README.md`;
no CDN at runtime).

### Routes

| Route | Response |
|---|---|
| `GET /healthz` | liveness and engines |
| `GET /` | programs grouped by confirmed chapter, then "Book reference unconfirmed" |
| `GET /programs/{id}` | header, run form, results area, tabs, practice questions |
| `GET /programs/{id}/form` | the run form reset to the book data card (HTMX fragment), plus an out-of-band `<div id="results" hx-swap-oob="innerHTML">` holding `results-placeholder`, so a reset also clears stale results and errors |
| `POST /programs/{id}/run` | results fragment (full page without the `HX-Request` header); 422 invalid input, 503 engine unavailable, 200 for every completed run including book error paths |
| `POST /programs/{id}/practice/{question_id}` | feedback fragment; 422 when the answer cannot be read |
| `GET /api/programs` | list: `id`, `title`, `method`, `book_ref`, `confirmed`, `book_ref_text`, `chapter`, `inputs` (catalog schema), `takes_function`, `default_preset`, `presets`, `engines` (available now, including `compare`), `scan_available`, `chart_kind`, `url`, `api_url` |
| `GET /api/programs/{id}` | the full catalog entry; `files` holds `/files/...` URLs instead of paths (plus `fortran_executable`, `python_callable`); `engines` maps `python`/`fortran`/`compare` to `{available, reason}` |
| `POST /api/programs/{id}/run` | see below |
| `GET /files/{id}/{kind}[?index=N]` | DD5 whitelist: `scan` (`application/pdf`), `legacy` (`index` picks one of several; a `.pdf` legacy file is `application/pdf`), `fortran_module`, `fortran_app`, `python`, `study` (all `text/plain; charset=utf-8`), served inline with `nosniff`. Unknown program or kind, a missing file or scan, a bad index, `catalog` and any traversal attempt are 404; paths come only from `Registry.resolve_path` |

Run form fields: `in_<name>` for `real`/`int`; `in_<name>` repeated per element for `real_list`
(editable rows; add/remove buttons unless the input has a fixed `length`); `in_<name>.x` and
`in_<name>.y` repeated per point for `point_list`; `engine` (`python`, `fortran`, `compare`),
`function` (a preset id or `custom`) and `expression`. Numbers accept the data-card spellings
(`0.`, `.5`, `1.E-5`, `1.D-3`); NaN and infinities are rejected. A list takes at most 100
entries; request bodies over 64 KiB are refused with 413 (a JSON
`TOO_LARGE` error on `/api` paths). A list with a fixed `length` (Bairstow's
seven coefficients) has no add/remove buttons and any other count is a field error. Constraints
between inputs come from the adapter's `input_problems`: for Lagrange, `n` must equal the number
of point rows. The adapter declares `n` as the count of `points` (`count_inputs`), so the form
updates N by itself whenever a point row is added or removed (`field-sync-note-n` says so); an N
typed by hand that disagrees with the rows is still answered with 422 and the message on the `n`
field (`field-error-n`).

### `POST /api/programs/{id}/run`

Body `{"engine": "python"|"fortran"|"compare", "inputs": {...}, "preset": N, "expression": "...",
"verbose": false}`, unknown keys rejected. Inputs left out take the book data card's value. The
checks run in this order, and HTML and API share them (`WebState.build_request`, `WebState.run`):

| HTTP | `error.code` | When |
|---|---|---|
| 404 | `NOT_FOUND` | unknown program (also any unknown `/api` path) |
| 405 | `METHOD_NOT_ALLOWED` | wrong method on an `/api` path (e.g. `GET /api/programs/{id}/run`) |
| 413 | `TOO_LARGE` | the request body is over 64 KiB (checked on the declared Content-Length and while streaming) |
| 422 | `VALIDATION` | the body does not match the schema (unknown engine, wrong JSON type, unknown key, `preset < 1`); `details` lists pydantic's errors |
| 422 | `CUSTOM_FUNCTION_ENGINE` | an `expression` with the `fortran` or `compare` engine (DD3) |
| 422 | `INPUT` | input values invalid; `fields` maps input name to message (`_unknown` for undeclared inputs; cross-input rules such as Lagrange's `n` against its points are reported on the input named by the adapter); also an unknown preset, preset plus expression, or a function for a data-only program |
| 422 | `EXPRESSION` | the expression does not parse or is not allowed; `position` is the 1-based column |
| 503 | `ENGINE_UNAVAILABLE` | the engine is disabled in the settings, the Fortran driver is not built, or the program has no engine adapter |
| 4xx | `HTTP_ERROR` | any other HTTP error raised by the framework on an `/api` path; `message` carries its detail |
| 200 | (none) | the run executed |

Every error body is `{"error": {"code", "message", ...}}`. A 200 body is `RunOutcome.to_dict()`
plus `mode` (the engine) and `ok`. `ok: false` means the program stopped on one of its own error
paths, and `status` and `error.code` give the reason (`BRACKET`, `ZERO_PRODUCT`, `NON_CONVERGENT`,
`ODD_PANELS`, `DEGREE`, `INPUT` for a non-finite F(x), `FORTRAN_RUN` for a driver timeout or crash);
`steps` then holds the partial rows. In compare mode the body is `CompareReport.to_dict()` (with
`outcomes`, `cells`, `columns`, `matches`, ...) plus `mode: "compare"` and `ok` (both engines
succeeded). Non-finite floats become `null` and complex numbers become `{"re", "im"}`.

### Results fragment

Single engine: status (`result-value`, `result-converged`, `result-iterations`, `result-engine`) or
`result-error` (`data-code`, `result-error-code`, `result-error-message`) with the partial rows;
the charts; the iteration table (`results-table`, one `step-row` per step, columns and edit
descriptors from `trace.step_columns`, the full value as tooltip); "Result details"
(`result-extras`) made of every result dataclass field except `value`, `converged`, `iterations`
and `steps`, rendered by shape: scalars (`extra-<field>`), number lists, ragged tables such as the
Romberg triangle (`extra-table-<field>`), lists of dataclasses or dicts (a table with one column
per key), and lists of records with named coefficients such as Bairstow's factors
(`extra-table-factors`: one row group `extra-factors-<i>` with `data-kind` per factor, headed by
its kind and printed form, and one named row `extra-factors-<i>-<name>` per coefficient: `r`, `s`
for a quadratic, `a2`, `a1`, `a0` for the final quadratic, `a1`, `a0` for the linear factor); the book text (`book-text`) and the verbose extras
(`verbose-text`).

Field errors: each `field-error-<name>` item also has `id="field-error-<name>"` and
`data-field-error="<name>"`. The offending control (`#in-<name>`, every input of a list fieldset
plus the fieldset's style, `#custom-expr` for `expression`, `#function-select` for `function`)
gets `aria-invalid="true"`, `class="invalid"` and `field-error-<name>` appended to its
`aria-describedby`: rendered by the server on the full-page (no-JS) POST, and applied by `app.js`
after each HTMX swap into `#results`, which first clears the previous marks (so a successful run
or a reset clears them).

Compare mode: `compare-summary` (`data-matches`, `compare-verdict`, `compare-iterations` with
`data-same`, `compare-status`, `compare-max-diff`, `compare-value-diff`, `compare-note`,
`compare-columns`), the Python charts, and the two traces side by side (`compare-python`,
`compare-fortran`, each with `book-text-python` / `book-text-fortran`). Differing cells carry
`class="diff-cell"` and `data-testid="diff-cell"`, with the absolute and relative difference in
the tooltip and `data-diff`. The two sides sit next to each other only when each column gets at least
36rem (`.compare-grid`, `minmax(min(100%, 36rem), 1fr)`); in the results panel of a 1280px window
they stack, so iteration tables and book lines are shown whole (each `.table-wrap` and `<pre>`
still scrolls on its own when wider; e2e `expect_compare_fully_visible` checks no overflow).

### Chart kinds (`[chart] kind` and `options`)

Builders in `gerald_na.web.charts` read only plain data: the step rows (dicts keyed by
`step_columns`), the result dataclass's fields, the validated inputs, the chart options and, for
programs that take a function, the compiled preset or custom function. Option defaults are in
brackets. Each figure is a `<div data-testid="chart-<figure id>">` inside `result-chart`; the
specs travel as JSON in `<script type="application/json" data-testid="result-chart-data">`.

| Kind | Figures (ids) | Reads |
|---|---|---|
| `bracket` | `bracket`, plus `abs_residual` when `residual_key` is set | steps `lower_key` [x1], `upper_key` [x2], `point_key` [x] against `index_key` [k] (row number if absent); `log_residual` [true] |
| `abs_residual` | `abs_residual` | \|steps[`residual_key` [fx]]\| against `index_key` [k]; log scale unless `log_residual = false` (exact zeros are left out on a log scale) |
| `romberg_heatmap` | `romberg_heatmap` | result field `table_field` [table]: list of rows, as printed and possibly ragged (row i, column j, 1-based in the hover; axis titles `row_label` ["row i"] and `column_label` ["column j"]). Colour is log10 \|T - result value\| (`color = "error"`, the default), or the value itself with `color = "value"`; each cell's text is its value |
| `integrand_panels` | `integrand_panels` | F sampled at 400 points over [`a` (number), or input `lower_input`, or 0; input `upper_input` [b]], widened to cover the ordinates; ordinates from steps `x_key` [x], `y_key` [fx]; `weight_key` [weight] shown in the hover. F is evaluated the way the program does: the adapter's `substituted_ordinates` (Simpson/Romberg: F(0) = 1 for the book's SIN(X)/X) replace the expression there; other points where F fails (a learner's 1/x at 0) are gaps |
| `factors` | `factors_r`, `factors_s`, `factors_roots`, plus `factors_delta` with `delta_keys` and `factors_polynomial` with `show_polynomial` | steps grouped by `group_key` [factor], with `index_key` [k], `r_key` [r], `s_key` [s]. Roots come from result `roots_field` [roots] (complex numbers, `[re, im]` or `{re, im}`), otherwise from result `factors_field` [factors]: dicts or dataclasses with `kind = quadratic` (`r`, `s`; `quadratic_form` ["x^2 - r x - s", Gerald's convention, whose sum of roots is 17.8 for the book polynomial; or "x^2 + r x + s"]), `final_quadratic` (`a2`, `a1`, `a0`) or `linear` (`a1`, `a0`), the coefficients either as named keys or as one `coefficients` list in that order (`BairstowFactor`). With `poly_input` (a real_list input, highest power first) the polynomial's own roots (Durand-Kerner) are added as a reference, and `show_polynomial = true` draws P(x) with the real roots marked. `delta_keys` (e.g. `["delr", "dels"]`) plots the sum of their absolute values per iteration and factor (log scale unless `log_delta = false`) |
| `interpolant` | `interpolant` | nodes from input `points_input` [points], only the first `count_input` [n] when that input exists; the Lagrange polynomial through them (`samples` [400] points); the point (input `x_input` [xin], result `value`); axis titles `x_label` [x], `y_label` [y] |
| `convergence` | `convergence_<key>` per key of `y_keys`, plus `convergence_changes` unless `changes = false` | steps `y_keys` (list) against step `x_key` [h] (the row number if the column is absent), log x axis unless `log_x = false`; keys in `log_y_keys` are drawn as \|y\| on a log scale. `convergence_changes` draws \|y(row i+1) - y(row i)\| at the x of row i on log-log axes, an error estimate that shows where round-off takes over (ch04_p01: DX and DDX against H). Zeros and negatives are left out on log axes |

### Program page testids

Navigation: `nav-brand`, `nav-home`, `nav-api`, `nav-api-docs`. Home: `program-list`, `chapter-<n>` /
`chapter-unconfirmed`, `program-card-<id>`, `program-link-<id>`, `program-bookref-<id>`,
`unconfirmed-badge-<id>`, `scan-status-<id>` (`data-scan` available or missing), `engines-<id>`.
Header: `program-title`, `book-ref`, `book-ref-unconfirmed`, `program-id`, `program-summary`. Form:
`run-form`, `input-<name>` (the input itself; for lists, the fieldset), `input-<name>-<i>` (list
element), `input-<name>-<i>-x` / `-y` (point), `add-row-<name>`, `remove-row-<name>-<i>`,
`field-help-<name>`, `field-bounds-<name>`, `field-sync-note-<name>` (a count input), `data-card-toggle`, `data-card`, `preset-select`,
`preset-expr`, `custom-expr`, `engine-selector`, `engine-python`, `engine-fortran`,
`engine-compare`, `engine-note-<engine>` (why it is unavailable), `engine-custom-note`,
`run-button`, `reset-button`, `run-indicator`. Results: `results`, `results-placeholder`,
`results-body`, `validation-error` (`data-code`), `field-error-<name>` (also `expression`,
`function`), `expr-error-column`, `expr-error-position`, `engine-unavailable`, plus the result
and compare ids above. Tabs: `tab-scan`, `tab-legacy`, `tab-fortran`, `tab-python`, `tab-study`;
panels `panel-*`; `scan-viewer` (an `<object type="application/pdf">`), `scan-download`,
`scan-download-fallback`, `scan-missing` ("No scan available for this program"),
`legacy-source-<i>` (`legacy-source-<i>-pdf` for a scanned legacy page), `fortran-module-source`, `fortran-app-source`, `python-source` (each
`*-missing` when the file is absent, `download-<same id>` for the raw file), `study-content`,
`download-study`, `study-missing`. Practice: `practice-section`, `practice-empty`, `practice-<qid>`,
`practice-prompt-<qid>`, `practice-answer-<qid>`, `practice-submit-<qid>`, `practice-feedback-<qid>`,
and in the feedback `practice-verdict` (`data-correct` true, false or unknown),
`practice-computed-python`, `practice-computed-fortran`, `practice-explanation`,
`practice-invalid`.

The Fortran and compare radios are disabled server-side when unavailable (with the reason) and
client-side while the custom function is selected; the server enforces both. Practice answers
are checked against `answer_field` of a fresh Python run of the question's inputs and preset,
within `tolerance`; Fortran runs too when its driver is built and its answer is shown beside
Python's.

### Security

Jinja2 autoescaping is on for every template, and nothing user-supplied or read from files is
marked safe. The only `Markup` is the study page rendered by markdown-it-py with raw HTML disabled.
Numbers are validated against the catalog before any engine runs. Bodies are capped at 64 KiB.
Every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
`X-Frame-Options: SAMEORIGIN` and a CSP with `script-src 'self'`: no inline scripts, and HTMX
runs with `allowEval: false`. Because of this CSP, browser tests must use locator assertions
rather than Playwright's string `wait_for_function`, which needs `eval`.

## Conventions

* Python results are frozen dataclasses with `value`, `converged`, `iterations`, `steps` and a
  `book_text()` method that renders the line-printer output.
* Every interactive HTML element carries a `data-testid` attribute.
* Fortran-dependent tests are marked `fortran` and locate the drivers through the
  `fortran_bin_dir` (and `fortran_single_bin_dir`) settings; they are skipped with an explicit
  reason when the drivers are absent.
* No absolute paths in code, configuration or tests.
