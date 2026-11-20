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

## Getting started

### What you need

Choose one of two paths:

* **Docker only** (simplest). The image contains the whole toolchain, builds the Fortran drivers
  and serves the web tool on port 8000:

  ```sh
  docker build -t gerald-na .
  docker run --rm -p 8000:8000 gerald-na
  ```

  Then open <http://127.0.0.1:8000>. The image has a `HEALTHCHECK` on `/healthz`; see
  [Docker](#docker) for what is inside it.
* **Local**. You need GNU make, [uv](https://docs.astral.sh/uv/) (it installs Python 3.15 itself)
  and, for the Fortran engine, gfortran 16 and fpm 0.13. LLVM flang is optional (a second
  compiler check). Exact versions are in [Prerequisites](#prerequisites); a ready-made editor
  environment is in [Devcontainer](#devcontainer).

  **Without gfortran the Python engine, the CLI and the web UI still work.** The Fortran engine
  then shows as unavailable: `/healthz` reports `"fortran":false`, and on a program page the
  "Fortran (compiled book driver)" and "Compare Python and Fortran" choices are disabled with a
  note such as
  ``Unavailable: Fortran driver ch01_p01_bisection is not built in <dir> (run `make build-fortran`)``. `gerald-na run --engine fortran` prints the same message as an error
  (exit status 2).

### Quick start (local)

1. **Get the code** and change into it:

   ```sh
   git clone <repository-url> numerical_analysis
   cd numerical_analysis
   ```

2. **Install the Python environment**: `make sync` (runs `uv sync` in `python/` and creates
   `python/.venv`). To check it, run `uv --directory python run gerald-na --version`, which prints
   `gerald-na 0.1.0`.

3. **Build the Fortran drivers**: `make build-fortran` (needs gfortran and fpm; skip it to use the
   Python engine only). fpm builds with warnings treated as errors and installs the six
   executables. To check it, run `ls build/bin`, which lists:

   ```
   ch01_p01_bisection  ch01_p02_bairstow  ch03_p01_simpson  ch03_p02_romberg
   ch04_p01_central_difference  lagrange_interpolation
   ```

4. **Start the web tool**: `make serve`. Uvicorn reports

   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   ```

5. **Open <http://127.0.0.1:8000>**. The home page, titled "Programs", lists the programs by
   chapter. To check the server from another terminal:

   ```sh
   curl http://127.0.0.1:8000/healthz
   # {"status":"ok","version":"0.1.0","engines":{"python":true,"fortran":true}}
   ```

   `"fortran":false` means step 3 was skipped or failed.

Next: [Running the programs](#running-the-programs) shows how to run each book program from the
command line. [Setup](#setup) and [Lifecycle targets](#lifecycle-targets) cover tests, the
single-precision build and the remaining make targets.

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

## Running the programs

Every program can be run in two ways: as the compiled Fortran driver (the modernized original
program) or through the Python port. A copy-paste command for each program, and the values it
should print, are in [the generated list](#commands-and-expected-results-for-every-program) at the
end of this section.

### Compiled Fortran drivers

After `make build-fortran`, each driver in `build/bin/` reads the book's data card from standard
input, in the book's original card order, and prints the book's line-printer output. The input is
read list-directed, so the card as printed in the book works unchanged; any spacing will do. Run
the drivers from the repository root:

```sh
$ printf '0. 1. 1.E-5\n' | build/bin/ch01_p01_bisection
 AT X =   .5000000 F(X) =   -.100576
 AT X =   .2500000 F(X) =    .396117
 ...
 AT X =   .4435729 F(X) =    .000000
 THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.
```

`sample_input.txt` in the repository root holds Bairstow's two data cards (the coefficients, then
`R1 S1 TEST LIM N`):

```sh
$ build/bin/ch01_p02_bairstow < sample_input.txt
 ...
 THE QUADRATIC FACTORS ARE-

 X**2 +    4.19999 X +   -2.09999
 X**2 +    3.30000 X +   -6.20000
    1.00000X +  -10.30000
```

What to look for with the book's data cards (default real64 build):

* **ch01_p01, bisection**: root `.4435729` after 15 iterations, as in the book. The last F(X) row
  prints `.000000`, while the scan prints `.000001`.
* **ch01_p02, Bairstow**: the factors x² + 4.2x − 2.1, x² + 3.3x − 6.2 and x − 10.3, printed with
  chopped digits. The real64 build prints `3.30000` for the second factor where the book prints
  `3.29999`. The other digits match the book.
* **ch03_p01, Simpson**: Si(5) = `1.5499312` with 100 panels; the book prints `1.5499307`.
* **ch03_p02, Romberg**: Si(15) = `1.6181944` with 80 subintervals; the book prints `1.6181936`.
* **ch04_p01, central differences**: the first row (`1.0016675E-02`, `2.0100083E+00`) matches the
  book. For small H the real64 DX keeps its digits (`1.0000000E-20` in the last row), while the
  book prints `0.0000000E-99`.
* **lagrange_interpolation**: `2.3119` at X = 5.000, as in the book.

These differences come from the arithmetic of the book's machine, not from errors in the programs.
Each study page explains them in its "Precision" section (for example
[content/ch03_p01.md](content/ch03_p01.md#precision)).

### Driver options

| Flag | Effect | Accepted by |
|---|---|---|
| `--trace` | machine-readable records only, no book text: `STEP` records, then `RESULT` or `ERROR` (Bairstow adds `FACTOR` and Romberg `TABLE` records); exit status 2 on `ERROR` | all six drivers |
| `--verbose` | extras after the book text, under the heading `VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)`: the working precision, the data card at full precision and program details (e.g. Bairstow's true factors and roots, Lagrange's terms) | all six drivers |
| `--preset N` | the function to use, from the book's function presets (default 1 = the book's function); the list is in each driver's `--help` | bisection, Simpson, Romberg, central differences (not Bairstow or Lagrange, which take data rather than a function) |
| `--help` | usage text, including the preset list | all six drivers |

Without flags the exit status is 0 on success and 1 when the program stops on one of the book's
error paths (the book's message is printed) or the input is invalid. The record format is
specified in [docs/architecture.md, "DD2: Trace protocol"](docs/architecture.md#dd2-trace-protocol---trace).

```sh
$ printf '0. 1. 1.E-5\n' | build/bin/ch01_p01_bisection --trace
STEP,k=1,x1=0.00000000000000000E+000,x2=1.00000000000000000E+000,x=5.00000000000000000E-001,fx=-1.00576112000487550E-001
...
RESULT,value=4.43572998046875000E-001,converged=T,iterations=15,root_at_endpoint=F,fx1=1.00000000000000000E+000,fx2=-6.32120558828557333E-001

$ printf '0.5 1. 1.E-5\n' | build/bin/ch01_p01_bisection --trace     # no sign change: exit status 2
ERROR,code=BRACKET,message=FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS.

$ printf '1. 2. 1.E-5\n' | build/bin/ch01_p01_bisection --preset 2   # X**3 - X - 1
 ...
 THE VALUE, X =  1.3247184 IS A ROOT.  18 ITERATIONS WERE REQUIRED.

$ printf '1.0 10\n' | build/bin/ch03_p01_simpson --preset 3          # 1/(1+X**2) on [0, 1]
 VALUE OF SINE INTEGRAL FROM X = 0 TO X =  1.00 IS  .7853981 WITH  10 PANELS
```

The book's heading is printed unchanged for every preset, so the Simpson line still says "SINE
INTEGRAL" for 1/(1+x²) (π/4 = 0.78539816…).

### Single-precision build

`make build-fortran-single` builds the same drivers in real32 (`-DSINGLE`), which is closer to the
book's single-precision machine, and installs them into `build/single/bin/`. Some of the book's
digits then reappear. For central differences, the last three DX values become exactly zero, as in
the book:

```sh
$ printf '0.0 0.1\n' | build/single/bin/ch04_p01_central_difference
 ...
  1.0E-07      8.4703277E-15      2.0000000E+00
  1.0E-08      0.0000000E-99      2.0000000E+00
  1.0E-09      0.0000000E-99      2.0000000E+00
  1.0E-10      0.0000000E-99      2.0000000E+00
```

The real32 bisection run also prints the scan's `.000001` in its last row. Single precision does
not reproduce every book digit, though. Simpson prints `1.5499314` in real32 and Romberg
`1.6181944`, against the book's `1.5499307` and `1.6181936`. The book's machine chopped its results
instead of rounding them, so its errors accumulate in one direction, while IEEE arithmetic (real32
or real64) rounds to nearest. The study pages' "Precision" sections
([ch03_p01](content/ch03_p01.md#precision), [ch03_p02](content/ch03_p02.md#precision),
[ch04_p01](content/ch04_p01.md#precision)) compare the builds with emulations of the book's
machine.

### Python port

From `python/`, `uv run gerald-na run <id>` runs a program on the Python engine with the book's data
card and prints the same book text. Add `--engine fortran` to run the compiled driver instead, or
`--engine compare` to run both and compare their traces:

```sh
$ uv run gerald-na run ch03_p01 --engine compare     # timings vary
=== python: OK (0.4 ms)
VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499312 WITH 100 PANELS
=== fortran: OK (8.9 ms)
VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499312 WITH 100 PANELS
=== differences
same outcome: True  same iterations: True
       K: max abs 0.000e+00  max rel 0.000e+00  first differing row -
...
```

`--expr` replaces the program's function with your own. It runs on the Python engine only;
`--engine fortran` with `--expr` is refused with exit status 2. Old FORTRAN names such as `EXPF` and
`SINF` are accepted, in either case.

```sh
$ uv run gerald-na run ch01_p01 --expr 'x**3 - 2' --input x1=1 --input x2=2
...
THE VALUE, X =  1.2599220 IS A ROOT.  18 ITERATIONS WERE REQUIRED.
```

`--input name=value`, `--preset N`, `--verbose`, `--trace-json` and the other options are listed in
[Command line](#command-line).

### Commands and expected results for every program

The block below is generated from the catalog by `make readme-index`; do not edit it by hand.

<!-- RUN_COMMANDS_START -->
Compiled Fortran drivers, from the repository root (each command feeds the catalog's data card on standard input; use `build/single/bin/` for the single-precision build):

```sh
# ch01_p01: Interval halving (bisection)
printf '0.        1.        1.E-5\n' | build/bin/ch01_p01_bisection
# ch01_p02: Bairstow quadratic factors
printf '0.        1.        -17.8     99.41     -261.218  352.611   -134.106\n0.        0.        1.E-5     20  5\n' | build/bin/ch01_p02_bairstow
# ch03_p01: Simpson's 1/3 rule, Si(B)
printf '5.0           100\n' | build/bin/ch03_p01_simpson
# ch03_p02: Romberg integration, Si(B)
printf '15.0           2.E-7\n' | build/bin/ch03_p02_romberg
# ch04_p01: Derivatives by central differences
printf '0.0       0.1\n' | build/bin/ch04_p01_central_difference
# lagrange_interpolation: Lagrangian interpolation
printf '05\n2.3756  1.6\n3.2682  1.9\n4.4571  2.2\n6.0502  2.5\n8.1919  2.8\n5.0\n' | build/bin/lagrange_interpolation
```

Python port, from `python/` (the same data card is the default input):

```sh
# ch01_p01: Interval halving (bisection)
uv run gerald-na run ch01_p01
# ch01_p02: Bairstow quadratic factors
uv run gerald-na run ch01_p02
# ch03_p01: Simpson's 1/3 rule, Si(B)
uv run gerald-na run ch03_p01
# ch03_p02: Romberg integration, Si(B)
uv run gerald-na run ch03_p02
# ch04_p01: Derivatives by central differences
uv run gerald-na run ch04_p01
# lagrange_interpolation: Lagrangian interpolation
uv run gerald-na run lagrange_interpolation
```

Expected results from the catalog's `[[expected]]` entries. *Book* is the value transcribed from the scan, *real64* the value of the default (double-precision) build; the drivers print it truncated to the book's FORMAT, so their significant digits are the leading digits of the value shown. Rows and tables are described in the last column.

| Program id | Quantity | Book | real64 | What the book prints |
|---|---|---|---|---|
| `ch01_p01` | `root` | `0.4435729` | `0.443572998046875` | THE VALUE, X = .4435729 IS A ROOT. |
| `ch01_p01` | `iterations` | `15` | `15` | 15 ITERATIONS WERE REQUIRED. (identical in real32 and real64) |
| `ch01_p01` | `steps` | - | - | The 15 printed AT X = ... F(X) = ... rows (book digits are truncated, not rounded). |
| `ch01_p02` | `factors` | - | - | X\*\*2 + 4.19999 X + -2.09999 / X\*\*2 + 3.29999 X + -6.20000 / 1.00000X + -10.30000 (chopped digits); exact 4.2, -2.1, 3.3, -6.2, 1.0, -10.3. |
| `ch01_p02` | `factor_count` | `3` | `3` | Three factors are printed: two quadratics and the final linear factor (N = 5 is odd). |
| `ch03_p01` | `value` | `1.5499307` | `1.5499312397703537` | VALUE OF SINE INTEGRAL FROM X = 0 TO X = 5.00 IS 1.5499307 WITH 100 PANELS |
| `ch03_p01` | `panels` | `100` | `100` | WITH 100 PANELS |
| `ch03_p02` | `value` | `1.6181936` | `1.6181944440409433` | VALUE IS 1.6181936, (real64: Si(15) = 1.6181944) |
| `ch03_p02` | `subintervals` | `80` | `80` | 80 SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF 2.0000000E-07 (identical in real32 and real64) |
| `ch03_p02` | `iterations` | `3` | `3` | 3 halvings: the 4 printed lines of the table (identical in real32 and real64) |
| `ch03_p02` | `table` | - | - | The printed triangular table; line L is TRAP(1..L, L). |
| `ch04_p01` | `steps` | - | - | The 10 printed rows H, DX, DDX (book digits are those of its 8-digit machine; see precision\_notes). |
| `ch04_p01` | `first_dx` | `0.010016675` | `0.010016675001984412` | Row 1: DX = 1.0016675E-02 for H = .1 (H\*SINH(H) = 0.0100166750020; well conditioned). |
| `ch04_p01` | `first_ddx` | `2.0100083` | `2.010008336111607` | Row 1: DDX = 2.0100083E+00 for H = .1 (2\*COSH(H) = 2.0100083361). |
| `ch04_p01` | `value` | `0.0` | `1.0000000031710762e-20` | DX of the last row (H = 1.E-10): the book prints 0.0000000E-99 (its F(X+H) and F(X-H) are equal); real64 keeps H\*SINH(H) = 1.0E-20. |
| `ch04_p01` | `last_ddx` | `2.0` | `2.0` | DDX of the last row: 2.0000000E+00. |
| `ch04_p01` | `iterations` | `10` | `10` | DO 10 I = 1,10: ten printed rows. |
| `lagrange_interpolation` | `value` | `2.3119` | `2.3119012901784366` | THE FUNCTION HAS VALUE OF 2.3119 (F10.4; one unit of the last printed digit). |
| `lagrange_interpolation` | `n` | `5` | `5` | INTERPOLATION AMONG 5 VALUES (I3). |
| `lagrange_interpolation` | `iterations` | `5` | `5` | Terms summed by the DO 20 loop (one per data pair). |
| `lagrange_interpolation` | `xin` | `5.0` | `5.0` | AT X = 5.000 (F10.3; the OCR text shows 5.0000, which F10.3 cannot print). |
<!-- RUN_COMMANDS_END -->

## Using the web interface

Start the server with `make serve` (or the Docker image, see [Getting started](#getting-started))
and open <http://127.0.0.1:8000>. Every program has the same layout: a run form and the results
side by side, tabs with the original and modern sources, and practice questions. Everything on a
page is generated from the program's catalog entry. How the pages are built, and the test ids of
every element, are in [`docs/architecture.md`](docs/architecture.md) ("Web UI and JSON API",
"Results fragment", "Program page testids").

### 1. Choose a program

The home page, **Programs**, groups the programs by chapter: "Chapter 1: Solution of Nonlinear
Equations", "Chapter 3: Numerical Integration" and "Chapter 4: Numerical Differentiation".
Programs whose place in the book is not confirmed come last under **Book reference
unconfirmed**; today that is only Lagrangian interpolation, whose card carries an "unconfirmed"
badge (see [Missing scans](#missing-scans-and-programs-not-yet-migrated)). Each card shows the
book reference, the method, a "Scan available" or "No scan" badge and the engines that can run it
(for example "Engines: python, fortran, compare").

Click a program's title to open its page at `/programs/<id>` (for example
<http://127.0.0.1:8000/programs/ch01_p01>). The **All programs** link above the title, or the
"Gerald · *Applied Numerical Analysis*" banner, leads back. The footer links the **JSON API**
and its interactive **API docs** (see [Web routes and JSON API](#web-routes-and-json-api)).

### 2. Fill in the run form

The **Run** panel opens with the book's data card already filled in, so **Run** reproduces the
book's printed result straight away.

* **Data card.** One field per value on the card, in card order, labelled as in the listing
  (`X1`, `X2`, `TOL`, ...) with its type (`real` or `int`). Below each field is a short
  explanation and its allowed range, for example "Left end of the starting interval. F(X1) and
  F(X2) must have opposite signs. (min -1000.0, max 1000.0)". Numbers may be typed the way the
  data card spells them: `0.`, `.5`, `1.E-5`, `1.D-5` (the pre-filled values are shown in Python
  notation, so the book's `1.E-5` appears as `1e-05`).
* **Book data card.** Click this line at the end of the fieldset to show the card exactly as
  printed in the book (for bisection `0. 1. 1.E-5`), with the catalog's note on it.
* **Lists.** A list of reals with a fixed length, such as Bairstow's seven coefficients
  "A (X\*\*6 ... X\*\*0)" ("list of reals, 7 entries"), has one field per entry and no buttons.
  A list that can grow, such as Lagrange's "Data pairs X(I), Y(I)" ("list of (x, y) points"),
  has a **Remove** button on each row and an **Add point** button below the rows (**Add entry**
  for a list of reals). Lagrange's `N` follows the number of rows by itself ("Updated
  automatically when you add or remove a row of Data pairs X(I), Y(I).").
* **Function F(X).** Programs that take a function (bisection, Simpson, Romberg and central
  differences) have a **Function** list. Option 1 is the book's function (for bisection "1: Book:
  exp(-x) - sin(pi x / 2)"); the other numbered options are extra functions from the catalog
  ("2: x^3 - x - 1", "3: cos(x) - x"). The line "Preset F(x) = ..." under the list shows the
  formula being used. The last option, "Custom expression (Python engine only)", is described in
  the next step. Bairstow and Lagrange work on data only and have no function.
* **Reset to book data card.** This button, next to **Run**, puts back every field, the
  function and the engine as they were when the page opened, and clears the results panel.

Click **Run** ("Running..." shows while it works). If a value is rejected, the results panel
shows **INPUT** "Please correct the highlighted values." with one line per field, for example
"X1: 'abc' is not a number (examples: 0.5, 1.E-5)" and "TOL: 5.0 is above the maximum 1.0", and
the offending fields are outlined in red until the next successful run or reset.

### 3. Try your own function

Type a formula in the **Custom expression** field (placeholder "for example x\*\*3 - 2\*x - 5").
Typing there selects "Custom expression (Python engine only)" in the **Function** list by
itself. The accepted syntax, listed under the field:

* the variable `x`, numbers (data-card spellings too: `2.`, `.5`, `1.E-5`), the operators
  `+ - * / **` and parentheses;
* the constants `e` and `pi`;
* the functions `abs`, `acos`, `asin`, `atan`, `atan2(y, x)`, `ceil`, `cos`, `cosh`, `exp`,
  `floor`, `log`, `log10`, `sin`, `sinh`, `sqrt`, `tan`, `tanh`;
* the FORTRAN names of the book's listings: `EXPF`, `SINF`, `COSF`, `ATANF`, `TANHF`, `LOGF`,
  `SQRTF`, `ABSF`, `ALOG`, `ALOG10` and the double-precision `D...` names (`DSIN`, `DEXP`,
  `DSQRT`, ...), plus `ln`, `arcsin`, `arccos` and `arctan`.

Names are case-insensitive, so the book's own `EXPF(-X) - SINF(3.1415926*X/2.)` is accepted as
written. As in Fortran, an integer exponent (`x**3`) is computed by repeated multiplication,
which matches the Fortran presets bit for bit; a real exponent (`x**3.`) uses `pow`.

**A custom function runs on the Python engine only.** The compiled Fortran drivers evaluate the
catalog's preset functions (`--preset N`), so as soon as the custom expression is selected the
Fortran and compare choices are disabled and the note "A custom expression runs on the Python
engine only: the Fortran drivers evaluate the catalog presets (--preset N), so Fortran and
compare are disabled." appears. Choose a numbered function again to re-enable them.

An expression that cannot be compiled is rejected before anything runs. The results panel shows
**EXPRESSION**, the message with its column, and the expression with a caret under the problem:

```
EXPRESSION syntax error: invalid syntax (at column 3)
Problem at column 3:
x**
  ^
```

`sin(x` gives "syntax error: '(' was never closed (at column 4)", `foo(x)` gives "unknown
function 'foo' (at column 1)" and `x + y` gives "unknown name 'y'; use the variable x, the
constants pi and e, or a supported function (at column 5)". A formula that compiles but fails
while the program runs, such as `log(x - 2)` on bisection's interval [0, 1], is reported like a
program error (step 5): "EXPRESSION log(-2.0) is outside the function's domain (at x = 0.0)".

### 4. Pick an engine

The **Engine** choices are:

* **Python**: the Python port (the default);
* **Fortran (compiled book driver)**: the modern Fortran driver, run as a separate program
  (needs `make build-fortran`; see [Troubleshooting](#troubleshooting-the-web-interface));
* **Compare Python and Fortran**: both, with their traces compared row by row.

Compare mode shows a summary first: the verdict **The engines agree bit for bit** or **The
engines differ**, then "Iterations: python 15, fortran 15", "Outcome: python OK, fortran OK",
"Largest cell difference: abs ..., rel ... (N differing cells, first in row R)", "Final value
difference: ..." and a **Per column** table of the largest differences per column. Below it are
the Python charts and the two traces, headed **Python** and **Fortran**, each with its summary,
iteration table and book-format output. They sit side by side when the window is wide enough
and stack otherwise. Every cell where the engines differ is highlighted (orange background), and
hovering over it shows both the value and the difference ("abs diff 9.267e-09, rel diff
9.214e-08").

Why the engines can differ: Python computes in double precision (real64), and the standard
Fortran build (`build/bin`) uses the same precision and the same formulas, so with it compare
normally reports "The engines agree bit for bit". The book's own machine worked in about eight
significant digits; to see that effect, build the
[single-precision drivers](#single-precision-build) (`make build-fortran-single`) and start the
server with `GERALD_NA_FORTRAN_BIN_DIR=build/single/bin make serve`. Compare then reports "The
engines differ", for bisection with 15 differing F(X) cells (largest difference abs 6.778e-08),
while the iteration count and the root agree. Each program's study page has a "Precision"
section explaining which digits are expected to change.

### 5. Read the results

A successful run fills the **Results** panel with:

* **the summary**: **Result** (the final value), **Converged** (yes or no), **Iterations** and
  **Engine** (with the run time, for example "python (0.2 ms)");
* **the charts** (Plotly), chosen per program: for bisection "Bracket shrinkage per iteration"
  and "|F(X)| per iteration (log scale)", for Romberg the table coloured by its distance from the
  result, for Bairstow R and S per iteration and the roots on the complex plane, for Lagrange the
  interpolating polynomial through the data points. Hover over a point to read its values; drag
  over an area to zoom in. The toolbar at the top right of each chart has **Zoom**, **Pan**,
  **Zoom in**, **Zoom out**, **Autoscale**, **Reset axes** and **Download plot as a PNG**;
* **the iteration table**, captioned for example "Iterations (15 rows, python engine)", with
  the columns of the book's printout (bisection: I, X1, X2, X, F(X)). Values are rounded for
  display; hover over a cell to see the full value;
* **Result details** (open by default): every other field of the result, for example the input
  values used, Romberg's triangular `table`, Bairstow's `factors` (one group per factor with its
  coefficients) or Lagrange's `xs` and `ys`;
* **Book-format output (python)** (or `fortran`): the lines the original program printed, in
  its line-printer format, for example `AT X =   .5000000 F(X) =   -.100576`.

When the program stops on one of its own error paths, the panel shows a red box with the code
and the program's message instead of the summary, plus the rows computed before the stop:

* Bisection with `X1` = 0.5 (and `X2` = 1, the book function): **BRACKET** "FUNCTION VALUES
  WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS." and "python engine.", with
  "No iteration rows." below.
* Bairstow with `LIM` = 4: **NON_CONVERGENT** "DOES NOT CONVERGE AFTER 4 ITERATIONS" and
  "python engine; the 4 iteration rows computed before the error are shown below."; the partial
  table and the book text, ending in `DOES NOT CONVERGE AFTER    4 ITERATIONS`, follow.

These are results, not failures of the tool: the study page of each program lists the outcomes
it handles ("Other outcomes the program handles").

### 6. Read the sources

Below the form, five tabs show where the program comes from (switch with a click or the left
and right arrow keys):

| Tab | Shows | Links |
|---|---|---|
| **Original scan** | the scanned book listing, inline | "Open the scan (PDF) in a new tab" (or "Download the scan" when the browser cannot show PDFs) |
| **Legacy OCR text** | the OCR transcription in `legacy_code/`, as is (with the slips listed in the errata) | "raw file"; a page kept only as a scan is shown as "A scanned page (PDF); no OCR text of it exists. Open the PDF." |
| **Modern Fortran** | the **Module** (`fortran/src/...`) and the **Driver** (`fortran/app/...`) | "raw file" for each |
| **Python** | the Python function (its callable is named above the code) | "raw file" |
| **Study page** | the study notes: the method, the data card, other outcomes, errata, precision and the practice questions | "Markdown source" |

Every "raw file" link opens the file as plain text from `/files/<id>/<kind>`, the only files
the server hands out. For Lagrangian interpolation the **Original scan** tab says "No scan
available for this program" and explains that the page has not been scanned and its place in
the book is unconfirmed.

### 7. Answer the practice questions

At the bottom of the page, **Practice questions** lists the program's questions. Type your answer
in **Your answer** (**Your answer (yes or no)** for questions about convergence) and click
**Check**. The answer is not looked up: the engines are run with the inputs the question states
(independently of what is in the run form), and your answer is compared with their result
within the question's tolerance (shown in the feedback when it is not zero). The feedback reads, for example:

* **Correct** · "Your answer matches the computed 15.";
* **Incorrect** · "The engine computes 0.443359375 (within 5e-06).";

followed by what each engine computed ("Python engine: 15", and "Fortran engine: 15" when the
driver is built) and an explanation. An answer that cannot be read is answered with a message
and nothing is run, for example "'abc' is not a number (examples: 0.5, 1.E-5)" or "answer yes or
no (true/false)". When no engine can compute the answer, the verdict is **Not checked** with "the
answer could not be computed (...)".

### Troubleshooting the web interface

Settings are listed in [Configuration](#configuration); every one can be set as a `GERALD_NA_*`
environment variable for a single run.

* **"Unavailable: Fortran driver ... is not built in <dir> (run `make build-fortran`)"** next to
  the Fortran and compare choices (and "Engines: python" on the home page card) means the
  server found no compiled drivers, as described in [What you need](#what-you-need). Run
  `make build-fortran` and reload the page (no restart needed), or, if the drivers are elsewhere
  (for example the single-precision build), restart with
  `GERALD_NA_FORTRAN_BIN_DIR=<dir> make serve`. A run started with an unavailable engine is
  refused with **ENGINE_UNAVAILABLE** "fortran engine unavailable: ...". The Python engine,
  the practice questions and every tab keep working.
* **Port 8000 is taken**: `GERALD_NA_PORT=9000 make serve` (or
  `uv --directory python run gerald-na serve --port 9000`), then open <http://127.0.0.1:9000>.
* **A Fortran run times out**: each driver run is stopped after `run_timeout_s` (5 seconds by
  default) and reported as **FORTRAN_RUN** "Fortran driver ch01_p01_bisection did not finish
  within 5 s and was stopped". On a slow machine raise it, for example
  `GERALD_NA_RUN_TIMEOUT_S=20 make serve`.

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

## Web routes and JSON API

How to use the pages is in [Using the web interface](#using-the-web-interface); this section lists
the routes behind them and the JSON API (every interactive element has a `data-testid` for Playwright).

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
