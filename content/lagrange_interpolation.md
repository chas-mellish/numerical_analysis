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

## Other outcomes

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

There is no scan, so the "corrected" column comes from syntax, the Hollerith counts and the
printed result, not from a page image. Every row is also in the catalog `errata` list and the
ERRATA header of `fortran/app/lagrange_interpolation.f90`.

| Id | Kind | OCR text / original | Corrected | Note |
|---|---|---|---|---|
| arithmetic-if-operator | OCR slip | `IF (I=J) 9,10,9` | `IF (I-J) 9,10,9` | an arithmetic IF takes an expression; J = I is skipped |
| product-term-parentheses | OCR slip | `TERM*(XIN - X(J)/X(I) - X(J))` | `TERM*(XIN - X(J))/(X(I) - X(J))` | only this is the basis polynomial and gives 2.3119 |
| format-i2 | OCR slip | `FORMAT (12/(2F10.0))` | `FORMAT (I2/(2F10.0))` | "I" read as "1"; N is read with I2 (`05`) |
| pair-column-order | OCR slip | `2.3756  1.6` (spacing collapsed) | X in columns 1–10, Y in 11–20 | X(I), Y(I) order verified: 2.3119 vs 63.35 swapped |
| output-spacing | OCR slip | `AMONG     5 VALUES,` / `AT X=   5.0000 …    2.3119` | `AMONG   5 VALUES,` / `AT X =      5.000 …     2.3119` | Hollerith counts 49, 8, 8, 27 fix the layout; F10.3 cannot print 5.0000 |
| trailing-05-card | OCR slip | a second `05` card after `5.0` | not part of the data | never read by the program; uncertain without a scan |
| file-extension-and-columns | OCR slip | `polynomial.F90`, ragged columns | fixed-form card layout; free-form modern source | `.F90` means free form + preprocessor, wrong for this listing |
| deck-control-cards | original quirk | `ZZJOB`, `ZZFORX5`, `*LIST PRINTER`, `ZZZZ` | dropped | job control, not FORTRAN |
| dimension-limit | modernization | `DIMENSION X(10), Y(10)`, no check | N must be 1–10 (`DEGREE`) | N > 10 overran the arrays |
| duplicate-x | modernization | division by zero for equal X | `INPUT` error naming the pair | −0.0 and +0.0 count as equal |
| non-finite-values | modernization | no check | overflow is an `INPUT` error | only with extreme data |
| list-directed-input | modernization | fixed card columns | list-directed read in the same order | printed cards work unchanged; N must match the pairs |
| structured-control-flow | modernization | arithmetic IF, `CONTINUE`, `CALL EXIT` | `IF (I /= J)` in `DO … END DO`; exit status | both nonzero branches went to label 9 |
| truncated-digits | original quirk | printer chops digits, no leading zero | book text uses RZ and no leading zero | same machine as the bisection deck; no effect on the book card |
| unconfirmed-book-reference | original quirk | file in `chapter_2/`, no scan | id `lagrange_interpolation`, `book_ref_confirmed = false` | can be confirmed later without renaming |

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
