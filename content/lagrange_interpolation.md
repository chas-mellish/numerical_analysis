# Lagrangian interpolation

*Book reference unconfirmed (chapter, program number and page unknown); no scan available.
Catalog entry: `catalog/lagrange_interpolation.toml`. Source: the OCR text
`legacy_code/fortran/chapter_2/polynomial.F90`.*

> **About the source.** Unlike the other programs, this one has no scanned page. Its listing, data
> card and printed result are known only from an OCR text, which contains several slips. Every
> correction below is justified by FORTRAN syntax, the FORMAT Hollerith counts, or the printed
> result 2.3119, which the corrected program reproduces to every digit. The remaining doubts are
> listed in the errata table.

## The method

Given N data pairs (X(I), Y(I)) with distinct X values, there is exactly one polynomial P of
degree at most N − 1 that passes through all of them. Lagrange wrote it as a weighted sum of the
data:

  P(XIN) = Σ Y(I) · L_I(XIN),  L_I(XIN) = ∏ over J ≠ I of (XIN − X(J)) / (X(I) − X(J)).

Each basis polynomial L_I equals 1 at its own node X(I) and 0 at every other node, so P
reproduces the data exactly. The program evaluates P at a single point XIN:

```
      YOUT = 0.0
      DO 20 I = 1,N
      TERM = Y(I)
      DO 10 J = 1,N
      IF (I-J) 9,10,9
    9 TERM = TERM*(XIN - X(J))/(X(I) - X(J))
   10 CONTINUE
   20 YOUT = YOUT + TERM
```

The iteration table shows one row per I: the pair X(I), Y(I), the term Y(I)·L_I(XIN), and the
running sum YOUT. Some points to notice:

* **Nothing iterates to convergence.** The method is direct: N terms, each needing N − 1 factors,
  about N² operations in all. Adding a point means recomputing every term. Newton's divided
  differences avoid this, which is why textbooks usually prefer them for tables of data.
* **The terms can be much larger than the answer and partly cancel** (for the book's card:
  +0.127, −0.624, +2.276, +0.565, −0.032). With nearly equal X values the basis polynomials
  become huge and the cancellation costs digits.
* **Interpolation error** is f⁽ᴺ⁾(ξ)/N! · (XIN − X(1))···(XIN − X(N)). It is smallest when XIN
  lies in the middle of the nodes and grows quickly outside them (extrapolation).
* **The program holds at most 10 points** (`DIMENSION X(10), Y(10)`).

## The book's data card

`READ 100, N, (X(I), Y(I), I = 1,N)` with `100 FORMAT (I2/(2F10.0))` reads N from the first card
and then one pair per card. `READ 101, XIN` with `101 FORMAT (F10.0)` reads the point from the
last card:

```
05
2.3756  1.6
3.2682  1.9
4.4571  2.2
6.0502  2.5
8.1919  2.8
5.0
```

The first number of each pair is X. That is the order of the READ list, and the numbers confirm
it: X = 2.3756 … 8.1919 is SINH(1.6) … SINH(2.8) rounded to four decimals. The book is therefore
doing **inverse interpolation**: it estimates the Y with SINH(Y) = 5, i.e. ASINH(5) = 2.3124383.
Reading the pairs the other way round gives 63.35 instead of 2.3119.

The output, laid out by `FORMAT 200` (the drivers print exactly this, carriage-control blank
consumed):

```
USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG   5 VALUES,
AT X =      5.000 THE FUNCTION HAS VALUE OF     2.3119
```

The terms of the book run (real64):

| I | X(I) | Y(I) | TERM | YOUT |
|---|---|---|---|---|
| 1 | 2.3756 | 1.6 | 0.1269898 | 0.1269898 |
| 2 | 3.2682 | 1.9 | −0.6242720 | −0.4972822 |
| 3 | 4.4571 | 2.2 | 2.2763530 | 1.7790708 |
| 4 | 6.0502 | 2.5 | 0.5645053 | 2.3435760 |
| 5 | 8.1919 | 2.8 | −0.0316748 | 2.3119013 |

The error against ASINH(5) is 5.4 × 10⁻⁴. That is interpolation error, not rounding error.

## Other outcomes the program handles

The original program had no checks. The modern programs add them, and both engines report the
same errors:

| Situation | Original | Modern behaviour |
|---|---|---|
| N < 1 or N > 10 | arrays overrun | `DegreeError` (trace code `DEGREE`): `N = 11 IS NOT BETWEEN 1 AND 10 (DIMENSION X(10) Y(10))` |
| two equal X values | division by zero at label 9 | `InputError` (`INPUT`): `X(2) AND X(4) ARE EQUAL: LAGRANGIAN INTERPOLATION NEEDS DISTINCT X VALUES` |
| N differs from the number of pairs given | (not possible with cards) | `InputError` before anything runs |
| a term or the sum overflows | (no IEEE infinities) | `InputError` after the completed rows |
| N = 1 | the constant Y(1) | the same: the inner loop multiplies nothing |

## Errata

There is no scan, so the "corrected" column comes from syntax, the Hollerith counts and the printed
result, not from a page image. The table below is generated from the catalog `errata` list (`make
readme-index`), so it carries every erratum with the catalog's id, kind and wording; the Fortran
ERRATA header of `fortran/app/lagrange_interpolation.f90` lists the same ids.

<!-- ERRATA_TABLE_START -->
| Id | Kind | Original | Corrected | Note |
|---|---|---|---|---|
| `arithmetic-if-operator` | OCR slip | IF (I=J) 9,10,9 | IF (I-J) 9,10,9 | An arithmetic IF takes an expression; I-J is zero exactly when J = I, whose factor is skipped. The modern code writes IF (I /= J). |
| `product-term-parentheses` | OCR slip | 9 TERM = TERM\*(XIN - X(J)/X(I) - X(J)) | 9 TERM = TERM\*(XIN - X(J))/(X(I) - X(J)) | The OCR lost the parentheses around the division. Only the corrected factor is the Lagrange basis polynomial, and only it reproduces the printed 2.3119. Evaluated left to right, (TERM\*(XIN - X(J)))/(X(I) - X(J)), in both engines. |
| `format-i2` | OCR slip | 100 FORMAT (12/(2F10.0)) | 100 FORMAT (I2/(2F10.0)) | "I" was read as "1". N is read with I2 from the first card (05); format reversion then reads one X, Y pair per card with 2F10.0. |
| `pair-column-order` | OCR slip | data cards printed as "2.3756 1.6" with the column spacing collapsed | X(I) in columns 1-10, Y(I) in columns 11-20: X = 2.3756 ... 8.1919, Y = 1.6 ... 2.8 | The READ list is X(I), Y(I). Verified numerically: this order gives 2.3119013 at XIN = 5.0 (the book's 2.3119); the swapped order gives 63.35. The X column is SINH(Y) to four decimals, so the book interpolates the inverse function ASINH. |
| `output-spacing` | OCR slip | USING ... AMONG 5 VALUES, / AT X= 5.0000 THE FUNCTION HAS VALUE OF 2.3119 | USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG 5 VALUES, / AT X = 5.000 THE FUNCTION HAS VALUE OF 2.3119 | The Hollerith counts 49, 8, 8 and 27 are all consistent with their texts, so FORMAT 200 fixes the layout: I3 gives two blanks before 5, F10.3 prints 5.000 (the OCR's 5.0000 is impossible) and F10.4 prints 2.3119. The OCR's blank runs are artifacts; the drivers follow the FORMAT. |
| `trailing-05-card` | OCR slip | a second card "05" after XIN = 5.0, before ZZZZ | not part of the data card | The program reads N, the N pairs and XIN, prints and calls EXIT, so a further card is never read. It is probably a listing/OCR duplicate or the start of an unrun second data set; uncertain without a scan. The drivers ignore anything after XIN. |
| `file-extension-and-columns` | OCR slip | polynomial.F90 with ragged label and continuation columns | fixed-form card layout (labels in columns 1-5, continuation marks 1 and 2 in column 6); modern free-form source in lagrange\_interpolation.f90 | The .F90 suffix tells compilers the file is free-form source to be preprocessed, but the listing is fixed-form FORTRAN with C comment cards and job-control cards, so it could not compile under that name. Layout only. |
| `deck-control-cards` | original quirk | ZZJOB 5 / CSC 001 GERALD, C, F / ZZFORX5 / \*LIST PRINTER / ZZZZ | dropped | Job-control cards of the same monitor as the bisection deck, not FORTRAN; they appear in the printout only because the deck was listed and are not echoed. |
| `dimension-limit` | modernization | DIMENSION X(10), Y(10) with no check on N | N must be 1 to 10: DEGREE error (DegreeError) before the pairs are read | N above 10 overran the arrays in the original. The catalog form bounds N to 1..10; a card fed directly to the driver gets ERROR,code=DEGREE. |
| `duplicate-x` | modernization | X(I) = X(J) for I /= J divides by zero at label 9 | INPUT error naming the first equal pair, before any term: X(i) AND X(j) ARE EQUAL | Interpolation needs distinct nodes. The original would divide by zero (a machine stop or garbage); both engines now reject the data with the same message. -0.0 and +0.0 count as equal. |
| `non-finite-values` | modernization | no check (the original machine had no IEEE infinities or NaN) | a term or the running sum that overflows is an INPUT error after the completed rows | Only possible with extreme or nearly equal X values; the same rule as the other programs' non-finite function values. |
| `list-directed-input` | modernization | READ 100 / READ 101 with fixed card columns (I2, 2F10.0, F10.0) | list-directed read of N, the N pairs and XIN, in the same order | The printed cards work unchanged and may be typed with any spacing; the engines also check that N equals the number of pairs supplied. |
| `structured-control-flow` | modernization | IF (I-J) 9,10,9 / 10 CONTINUE / 20 YOUT = YOUT + TERM / CALL EXIT | IF (I /= J) inside DO ... END DO loops; normal termination or STOP with an exit status | The arithmetic IF's two nonzero branches both go to label 9, so a single test is exact. |
| `truncated-digits` | original quirk | line printer that chops Fw.d digits and prints no leading zero (as in the bisection listing) | book text rendered with RZ rounding and no leading zero | Same deck-control cards as the bisection program, so the same output conventions are assumed. For the book card it makes no difference (5.000 and 2.3119 either way). |
| `unconfirmed-book-reference` | original quirk | legacy file in chapter\_2/, no scan, no page number | catalog id lagrange\_interpolation with book\_ref\_confirmed = false and no scan\_pdf | The chapter, program number and page in the book are unknown; a confirmed reference can be added later without renaming files (DD1). |
<!-- ERRATA_TABLE_END -->

## Precision

The book printed 2.3119 (F10.4). The real64 value is 2.3119012901784366 and real32 gives 2.3119011.
Both print `2.3119`, whether the digits are chopped (as the book's printer did) or rounded, so the
default and the `SINGLE` Fortran builds reproduce the book text exactly. The golden test allows
one unit of the last printed digit (10⁻⁴) and checks real64 against 2.3119012901784366 to 10⁻¹².

Precision is not what limits the answer here. The interpolation error (5.4 × 10⁻⁴) is about a
thousand times larger than the real32 rounding error. The rounding of the X column to four
decimals adds about 10⁻⁵ more. Precision only matters when X values are nearly equal: then the
basis polynomials become large and cancel, and duplicates make the program stop.

## Practice questions

The answers are checked by running an engine with the stated inputs (catalog `practice` ids in
brackets).

1. **[book-value]** Run the book's data card. What value does the interpolating polynomial give
   at X = 5.0 (5 decimals)?
2. **[node-reproduction]** Keep the five pairs but set XIN = 6.0502, the fourth X value. What is
   printed, and why?
3. **[three-point-extrapolation]** Use only the first three pairs (N = 3) with XIN = 5.0. Is the
   result better or worse than the five-point value? Why?
4. **[inverse-at-3]** Interpolate at XIN = 3.0 and compare with ASINH(3) = 1.8184465.
5. **[quadratic-exact]** Enter N = 3 with the points (1, 1), (2, 4), (4, 16) of Y = X² and
   XIN = 2.5. What value is printed?
6. **[terms-summed]** How many terms does the DO 20 loop add for the book's card?
