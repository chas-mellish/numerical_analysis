!===============================================================================
! ch01_p02_bairstow.f90
!
! Quadratic factors of polynomials to sixth degree, Bairstow method.
! C. F. Gerald, "Applied Numerical Analysis", Chapter 1, Program 2 (book p. 25,
! output and discussion p. 26).
! Authoritative source: docs/chapter_01_program_02_listing.pdf (image-only scan
! of the card listing and its line-printer output). The raw OCR text
! legacy_code/fortran/chapter_1/fortran_program_02.f90 and the earlier modern
! rewrite legacy_code/fortran/chapter_2/bairstow.f90 (misfiled in chapter_2,
! degree-first interactive input) were references only; this program was
! re-transcribed from the scan.
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/bairstow_mod.f90 (module bairstow_mod) and the book-style number
! formatting and trace helpers in fortran/src/book_format_mod.f90. Its flag
! parser stays here (it rejects --preset); arg_len comes from cli_mod.
!
! USAGE
! -----
!   ch01_p02_bairstow [--trace] [--verbose] [--help]  < data cards
!
!   stdin    the book's two data cards, list-directed, in the original order
!              card 1: the seven coefficients of X**6, X**5, ..., X**0
!              card 2: R1 S1 TEST LIM N
!            (book cards "0. 1. -17.8 99.41 -261.218 352.611 -134.106" and
!            "0. 0. 1.E-5 20 5" work unchanged)
!   --trace      machine-readable records only (STEP / FACTOR / RESULT / ERROR)
!   --verbose    extras after the book text: the true factors X**2 - R X - S
!                and their roots (complex where needed), iterations per factor
!   --help       usage text
!   --preset N   not accepted: Bairstow takes data, not a function (DD3)
!
!   Without --trace, stdout is the book's line-printer text. Exit status 0 on
!   success; a book error path prints its message and exits 1; bad input
!   (non-numeric card, unknown flag) prints a message on stderr and exits 1.
!   With --trace (protocol DD2, docs/architecture.md):
!     STEP,factor=<I0>,k=<I0>,r=<r>,s=<r>,delr=<r>,dels=<r>   per correction
!     FACTOR,kind=quadratic,r=<r>,s=<r>                         after each factor
!     FACTOR,kind=final_quadratic,a2=<r>,a1=<r>,a0=<r>   or
!     FACTOR,kind=linear,a1=<r>,a0=<r>                          the last factor
!     RESULT,value=<number of factors>,converged=T,iterations=<I0>,nudges=<I0>
!     ERROR,code=<NON_CONVERGENT|DEGREE|INPUT>,message=<text>
!   reals as ES25.17E3 without leading blanks; on ERROR the exit status is 2.
!   STEP r and s are the values after the correction (R = DELR + R).
!
! TRANSCRIPTION OF THE SCAN
! -------------------------
! The scan, re-read at 200 and 400 dpi, is (comment cards abbreviated):
!
!       DIMENSION A(9), B(9), C(9)
!       PRINT 1000
!  1000 FORMAT (1H1,29H DEMONSTRATION PROGRAM OUTPUT)
!       READ 1, (A(I), I = 3,9)
!     1 FORMAT (7F10.0)
!       READ 2, R1, S1, TEST, LIM, N
!     2 FORMAT (2F10.0, E10.0, 2I3)
!       PRINT 3
!     3 FORMAT (//25H THE ORIGINAL POLYNOMIAL- /)
!       PRINT 4
!     4 FORMAT (5X, 10HPOWER OF X , 5X, 11HCOEFFICIENT /)
!       J = 9 - N
!       DO 5 I = J,9
!       M = 9 - I
!     5 PRINT 6, M, A(I)
!     6 FORMAT (10X, I2, 8X, F10.5)
!       PRINT 7
!     7 FORMAT (//27H THE QUADRATIC FACTORS ARE- /)
!       B(1) = 0.
!       B(2) = 0.
!       C(1) = 0.
!       C(2) = 0.
!       R = R1
!       S = S1
!    11 KOUNT = 1
!    16 DO 8 J = 3,9
!       B(J) = A(J) + R*B(J - 1) + S*B(J - 2)
!     8 C(J) = B(J) + R*C(J - 1) + S*C(J - 2)
!       DENOM = C(7)*C(7) - C(8)*C(6)
!       IF ( DENOM) 9, 10, 9
!    10 R1 = R1 + 1.
!       S1 = S1 + 1.
!       GO TO 11
!     9 DELR = (-B(8)*C(7) + C(6)*B(9))/DENOM
!       DELS = (-C(7)*B(9) + B(8)*C(8))/DENOM
!       R = DELR + R
!       S = DELS + S
!       IF ( ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13
!    13 IF (KOUNT - LIM) 14, 15, 15
!    15 PRINT 24, LIM
!    24 FORMAT (25H DOES NOT CONVERGE AFTER , I4, 11H ITERATIONS    )
!       CALL EXIT
!    14 KOUNT = KOUNT + 1
!       GO TO 16
!    12 PRINT 17, R, S
!    17 FORMAT ( 8H X**2 + , F10.5, 5H X + , F10.5)
!       N = N - 2
!       IF (N - 2) 18, 19, 20
!    20 DO 21 K = 3,9
!    21 A(K) = B(K - 2)
!       GO TO 11
!    19 PRINT 22, B(5), B(6), B(7)
!    22 FORMAT (1H ,F10.5, 7HX**2 + , F10.5, 4HX + , F10.5)
!       CALL EXIT
!    18 PRINT 23, B(6), B(7)
!    23 FORMAT (1H ,F10.5, 4HX + , F10.5)
!       CALL EXIT
!       END
!   data cards:  0.  1.  -17.8  99.41  -261.218  352.611  -134.106
!                0.  0.  1.E-5 20  5
!
!   * Every Hollerith count was checked against its text, leading and trailing
!     blanks included: 29 " DEMONSTRATION PROGRAM OUTPUT", 25 " THE ORIGINAL
!     POLYNOMIAL-", 10 "POWER OF X", 11 "COEFFICIENT", 27 " THE QUADRATIC
!     FACTORS ARE-", 25 " DOES NOT CONVERGE AFTER " (the trailing blank
!     belongs to the Hollerith; the blanks before ")" in FORMAT 24 are card
!     columns, not text), 11 " ITERATIONS", 8 " X**2 + ", 5 " X + ",
!     7 "X**2 + ", 4 "X + ". The records below are emitted character for
!     character, including the empty records of the "/" edit descriptors.
!   * The deck-control cards (ZZJOB 5 / CSC 001 / GERALD, C. F., ZZFORX5,
!     *LIST PRINTER, ZZZZ) are job control, not Fortran, and are dropped. The
!     data cards appear in the printout only because the deck was listed.
!   * The scan's printout starts at THE ORIGINAL POLYNOMIAL-: the heading of
!     FORMAT 1000 went to the top of a new page (carriage control 1H1).
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. OCR slips in legacy_code/fortran/chapter_1/fortran_program_02.f90
!    (the scan is right; nothing to change in the program):
!   * DIMENSION ... C(I) is C(9) (an "I" misread for "9").
!   * The data card's -126.218 is -261.218 (scan card; the printed polynomial
!     shows -261.21800 and the book text gives -261.218x**2).
!   * QUTPUT -> OUTPUT; READ 1+ (A(I), I = 3.9) -> READ 1, (A(I), I = 3,9);
!     Sl -> S1; E10,0 -> E10.0; BX -> 8X; O. -> 0. (B(2), C(1)); "~" and an
!     em dash -> "-" (J = 9 - N, -B(8), C(7)*C(7) - C(8)*C(6)); j -> J;
!     IF ( DENOM) = 9, 10, 9 -> IF ( DENOM) 9, 10, 9; R1 + l. -> R1 + 1.;
!     l4 -> I4 and the lost blank of 25H DOES NOT CONVERGE AFTER ;
!     SH X , -> 5H X + , (the "+" was lost); F1l0.5 -> F10.5;
!     DO 21 K = 3.9 -> 3,9; the job cards ZZJ0B / csC / ZZFORXS / *L 1ST were
!     garbled and the page heading "1-9 PROGRAMMING OF METHODS TO SOLVE
!     EQUATIONS" / "Program 2" was inserted as comment cards.
!   * The OCR'd printout lost the "+" signs and the blanks of FORMAT 17 and 23
!     ("X**2 4.19999 X + -2.09999", "1.00000X + - 10.30000"); the scan prints
!     "X**2 +    4.19999 X +   -2.09999" and "  1.00000X +  -10.30000".
! B. Bug in the original, corrected: label 10 increments R1 and S1 and jumps
!    to label 11, which never reloads R and S from them (R = R1 and S = S1 are
!    executed once, before label 11). An exactly zero DENOM therefore repeated
!    the same computation forever. The book's text says the intent: "If a zero
!    denominator should occur, the r and s values are arbitrarily incremented
!    by one". The working R and S are incremented, and KOUNT restarts at 1 as
!    GO TO 11 does. Termination guard (modernization, no book equivalent): more
!    than LIM nudges while searching for one factor (DENOM staying zero, e.g.
!    an all-zero polynomial) ends the run with message 24.
! C. Quirks of the original, kept:
!   * FORMAT 17 labels each factor "X**2 + R X + S", but the recurrence
!     B(J) = A(J) + R*B(J-1) + S*B(J-2) divides by X**2 - R*X - S. The book's
!     text confirms it: the printed 4.19999/-2.09999, 3.29999/-6.20000 and
!     1.00000X + -10.30000 are the exact factors x**2 - 4.2x + 2.1,
!     x**2 - 3.3x + 6.2 and x - 10.3. --verbose prints the true factors.
!   * DENOM is tested for an exact zero (IF ( DENOM) 9, 10, 9), not against
!     a small epsilon as the earlier rewrite did; a NaN DENOM is nonzero.
!   * After a factor, R and S are not reset: the next factor starts from the
!     previous factor's R and S (the book: "the r and s coefficients of that
!     factor are used as starting values for the next factor").
!   * For N = 2 the quadratic factor is the polynomial itself and label 18
!     prints the constant quotient as a "linear" factor .00000X + A, A being
!     the leading coefficient. N = 4 and 6 end with FORMAT 22 (B(5) X**2 ...),
!     N = 3 and 5 with FORMAT 23.
!   * KOUNT counts the corrections of the current factor and LIM bounds it, so
!     the limit applies per factor, not to the whole run. LIM <= 0 behaves as 1
!     (IF (KOUNT - LIM) after the first correction).
!   * The book's machine chopped printed digits (4.19999, -2.09999, 3.29999)
!     and printed no leading zero. The factor lines use the RZ edit mode and
!     drop the leading zero (book_fixed). The echoed coefficients are printed
!     rounded to nearest, also without a leading zero: the book shows 99.41000,
!     -17.80000 and -261.21800, exact as on a decimal machine, whereas binary
!     99.41 is 99.409999... and would chop to 99.40999. This echo is one of
!     the hints that chapter 1 ran on a decimal machine; the book's computer
!     is not identified (docs/architecture.md, "The book's computer").
! D. Drift of the earlier rewrite (legacy_code/fortran/chapter_2/bairstow.f90),
!    restored to the scan:
!   * It read the degree first, with prompts; the cards are read again in the
!     book's order (coefficients of X**6 ... X**0, then R1 S1 TEST LIM N). The
!     root-level sample_input.txt was rewritten into this order.
!   * It tested |DENOM| < EPSILON; the scan tests DENOM = 0 exactly.
!   * It tested |DELR| + |DELS| < TEST; the scan's IF (... - TEST) 12, 12, 13
!     accepts equality (<= TEST).
!   * It reworded every heading and line ("THE QUADRATIC FACTORS ARE:",
!     "DOES NOT CONVERGE AFTER 20 ITERATIONS") and printed the true factors and
!     roots inline. The scan's FORMATs are restored; the extras moved behind
!     --verbose.
! E. Modernization (behavior-preserving):
!   * Arithmetic IFs and GO TOs became IF blocks and named DO loops that keep
!     every zero branch; CALL EXIT became a return with an exit status.
!   * READ 1 / READ 2 with FORMATs 7F10.0 and 2F10.0, E10.0, 2I3 (fixed card
!     columns) became list-directed reads, so the cards may be typed with any
!     spacing; reals must be finite and LIM, N integers.
!   * Degree check (no book equivalent): N outside 2..6 (the book would index
!     A(9-N) outside the array) and a nonzero coefficient of a power above N
!     (the book would print one polynomial and factor another) stop the run
!     with a DEGREE error after the heading.
!   * Carriage control: stdout has no line printer, so the page eject 1H1 of
!     FORMAT 1000 is written as a blank carriage-control column; every other
!     record keeps its blank first column (1H or the leading blank of the
!     Hollerith) as in the other drivers.
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! F. Precision notes (book data cards):
!   * Both builds need 8 corrections for the first factor and 5 for the second
!     (13 in total) and find the factors 4.2/-2.1, 3.3/-6.2 and 1.0X - 10.3.
!   * real64 prints 4.19999 -2.09999 / 3.30000 -6.20000 / 1.00000 -10.30000
!     (book: 3.29999); real32 prints the last digit of several values
!     differently again. Every value is within 2E-5 of the book's digits; the
!     golden tests compare numbers, not text (catalog tolerances, DD4).
! G. Index of the catalog errata (catalog/ch01_p02_bairstow.toml [[errata]],
!    also on content/ch01_p02.md), one line per id, in catalog order:
!   1 dimension-c9 (ocr_slip): C(I) -> C(9). See A.
!   2 data-card-coefficient (ocr_slip): -126.218 -> -261.218. See A.
!   3 ocr-character-slips (ocr_slip): QUTPUT, Sl, O., ~, em dash, j, l., BX,
!     E10,0, 3.9, "=" in the arithmetic IF, F1l0.5. See A.
!   4 format-24-hollerith (ocr_slip): l4 -> I4, trailing blank of the 25H
!     field. See A.
!   5 format-17-hollerith (ocr_slip): SH X , -> 5H X + ,. See A.
!   6 job-cards-and-page-headings (ocr_slip): garbled job cards, page heading
!     inserted as comments. See A.
!   7 printed-output-transcription (ocr_slip): lost "+" and blanks. See A.
!   8 nudge-never-reloads-r-s (original_bug): working R and S are bumped. B.
!   9 factor-sign-label (original_quirk): X**2 + R X + S printed, X**2 - R X
!     - S divided out. See C.
!  10 exact-zero-denominator (rewrite_drift): DENOM = 0 exactly. See C, D.
!  11 convergence-test-equality (rewrite_drift): <= TEST. See D.
!  12 rewrite-input-order (rewrite_drift): book card order, sample_input.txt.
!  13 rewrite-output-layout (rewrite_drift): scan FORMATs, --verbose. See D.
!  14 degree-two-constant-quotient (original_quirk): N = 2 prints
!     .00000X + A. See C.
!  15 truncated-digits (original_quirk): chopped factor digits, RN for the
!     echoed card values. See C, F.
!  16 nudge-limit (modernization): at most LIM nudges per factor. See B.
!  17 degree-check (modernization): DEGREE error. See E.
!  18 page-eject (modernization): 1H1 written as a blank. See E.
!  19 structured-control-flow (modernization): IF blocks, loops, list-
!     directed reads, exit status. See E.
!===============================================================================
program ch01_p02_bairstow
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp, single_precision
   use bairstow_mod, only: bairstow, bairstow_result, bairstow_factor, factor_roots, &
      factor_kind_name, is_exact_zero, n_coeffs, min_degree, max_degree, status_ok, &
      status_non_convergent, status_degree_error, degree_out_of_range, factor_quadratic, &
      factor_final_quadratic
   use book_format_mod, only: book_fixed, book_fixed_nearest, book_int, &
      trace_real, trace_int, trace_logical, no_commas
   use cli_mod, only: arg_len
   implicit none

   ! Book text of FORMAT 1000 (page eject written as a blank), 3, 4, 7 and 24.
   character(len=*), parameter :: msg_1000 = "  DEMONSTRATION PROGRAM OUTPUT"
   character(len=*), parameter :: msg_3 = " THE ORIGINAL POLYNOMIAL-"
   character(len=*), parameter :: msg_4 = "     POWER OF X     COEFFICIENT"
   character(len=*), parameter :: msg_7 = " THE QUADRATIC FACTORS ARE-"

   logical :: trace, verbose, help
   character(len=:), allocatable :: arg_error
   real(wp) :: coeffs(n_coeffs), r1, s1, test
   integer :: lim, n, ios
   type(bairstow_result) :: res

   call parse_arguments(trace, verbose, help, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   ! READ 1, (A(I), I = 3,9)
   read (input_unit, *, iostat=ios) coeffs
   if (ios /= 0) call input_error( &
      "could not read data card 1 (seven coefficients of X**6 ... X**0 expected on stdin)")
   ! READ 2, R1, S1, TEST, LIM, N
   read (input_unit, *, iostat=ios) r1, s1, test, lim, n
   if (ios /= 0) call input_error( &
      "could not read data card 2 (R1 S1 TEST LIM N expected; LIM and N are integers)")
   if (.not. (all(ieee_is_finite(coeffs)) .and. ieee_is_finite(r1) .and. &
      ieee_is_finite(s1) .and. ieee_is_finite(test))) &
      call input_error("data card values must be finite numbers")

   res = bairstow(coeffs, r1, s1, test, lim, n)

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose .and. res%status /= status_degree_error) call write_verbose(res)
   end if

   ! Success ends normally (exit status 0); a book error path exits 1, an ERROR record 2.
   if (res%status /= status_ok) then
      if (trace) then
         stop 2, quiet=.true.
      else
         stop 1, quiet=.true.
      end if
   end if

contains

   !> Read all command-line flags (any order). Sets `arg_error` on the first bad argument.
   subroutine parse_arguments(trace, verbose, help, arg_error)
      logical, intent(out) :: trace, verbose, help
      character(len=:), allocatable, intent(out) :: arg_error
      character(len=arg_len) :: arg
      integer :: i, nargs, length, stat

      trace = .false.
      verbose = .false.
      help = .false.
      nargs = command_argument_count()
      do i = 1, nargs
         call get_command_argument(i, arg, length, stat)
         if (stat /= 0 .or. length > arg_len) then
            if (.not. allocated(arg_error)) arg_error = "command-line argument " // &
               trace_int(i) // " is too long"
            cycle
         end if
         select case (trim(arg))
         case ("--trace")
            trace = .true.
         case ("--verbose")
            verbose = .true.
         case ("--help", "-h")
            help = .true.
         case default
            if (.not. allocated(arg_error)) then
               if (trim(arg) == "--preset" .or. index(arg, "--preset=") == 1) then
                  arg_error = "--preset is not available: Bairstow takes data cards, " // &
                     "not a function"
               else
                  arg_error = "unknown argument " // trim(arg) // " (try --help)"
               end if
            end if
         end select
      end do
   end subroutine parse_arguments

   !> Report bad input and stop: ERROR,code=INPUT (exit 2) in trace mode, else stderr (exit 1).
   subroutine input_error(message)
      character(len=*), intent(in) :: message

      if (trace) then
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // no_commas(message)
         stop 2, quiet=.true.
      else
         write (error_unit, '(a)') "ch01_p02_bairstow: " // message
         stop 1, quiet=.true.
      end if
   end subroutine input_error

   !> FORMAT 24 text (leading blank = carriage control).
   function msg_24() result(s)
      character(len=:), allocatable :: s

      s = " DOES NOT CONVERGE AFTER " // book_int(lim, 4) // " ITERATIONS"
   end function msg_24

   !> Message of the DEGREE error (no book equivalent; leading blank = carriage control).
   function degree_message(res) result(s)
      type(bairstow_result), intent(in) :: res
      character(len=:), allocatable :: s

      if (res%degree_problem == degree_out_of_range) then
         s = " DEGREE N = " // trace_int(n) // " IS OUTSIDE " // trace_int(min_degree) // &
            " TO " // trace_int(max_degree) // "."
      else
         s = " COEFFICIENT OF X**" // trace_int(res%bad_power) // " IS NOT ZERO BUT N = " // &
            trace_int(n) // "."
      end if
   end function degree_message

   !> One printed factor (FORMAT 17, 22 or 23).
   function factor_line(f) result(s)
      type(bairstow_factor), intent(in) :: f
      character(len=:), allocatable :: s

      select case (f%kind)
      case (factor_quadratic)
         ! 17 FORMAT ( 8H X**2 + , F10.5, 5H X + , F10.5)
         s = " X**2 + " // book_fixed(f%coef(1), 10, 5) // " X + " // book_fixed(f%coef(2), 10, 5)
      case (factor_final_quadratic)
         ! 22 FORMAT (1H ,F10.5, 7HX**2 + , F10.5, 4HX + , F10.5)
         s = " " // book_fixed(f%coef(1), 10, 5) // "X**2 + " // book_fixed(f%coef(2), 10, 5) &
            // "X + " // book_fixed(f%coef(3), 10, 5)
      case default
         ! 23 FORMAT (1H ,F10.5, 4HX + , F10.5)
         s = " " // book_fixed(f%coef(1), 10, 5) // "X + " // book_fixed(f%coef(2), 10, 5)
      end select
   end function factor_line

   !> The book's line-printer output.
   subroutine write_book_text(res)
      type(bairstow_result), intent(in) :: res
      integer :: i

      ! PRINT 1000
      write (output_unit, '(a)') msg_1000
      if (res%status == status_degree_error) then
         write (output_unit, '(a)') degree_message(res)
         return
      end if
      ! PRINT 3: (//25H THE ORIGINAL POLYNOMIAL- /)
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') msg_3
      write (output_unit, '(a)') ""
      ! PRINT 4: (5X, 10HPOWER OF X , 5X, 11HCOEFFICIENT /)
      write (output_unit, '(a)') msg_4
      write (output_unit, '(a)') ""
      ! DO 5 I = J,9 ... 5 PRINT 6, M, A(I): (10X, I2, 8X, F10.5)
      do i = 9 - n, 9
         write (output_unit, '(a)') repeat(" ", 10) // book_int(9 - i, 2) // repeat(" ", 8) // &
            book_fixed_nearest(coeffs(i - 2), 10, 5)
      end do
      ! PRINT 7: (//27H THE QUADRATIC FACTORS ARE- /)
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') msg_7
      write (output_unit, '(a)') ""
      do i = 1, size(res%factors)
         write (output_unit, '(a)') factor_line(res%factors(i))
      end do
      if (res%status == status_non_convergent) write (output_unit, '(a)') msg_24()
   end subroutine write_book_text

   !> --trace: STEP records with a FACTOR record after each factor, then RESULT or ERROR.
   subroutine write_trace(res)
      type(bairstow_result), intent(in) :: res
      integer :: i, next_factor

      next_factor = 1
      do i = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,factor=" // trace_int(res%steps(i)%factor) // &
            ",k=" // trace_int(res%steps(i)%k) // &
            ",r=" // trace_real(res%steps(i)%r) // &
            ",s=" // trace_real(res%steps(i)%s) // &
            ",delr=" // trace_real(res%steps(i)%delr) // &
            ",dels=" // trace_real(res%steps(i)%dels)
         ! The quadratic factor is printed after the last correction of its search.
         if (next_factor <= size(res%factors)) then
            if (i == size(res%steps) .or. res%steps(min(i + 1, size(res%steps)))%factor /= &
               res%steps(i)%factor) then
               call write_factor(res%factors(next_factor))
               next_factor = next_factor + 1
            end if
         end if
      end do
      do i = next_factor, size(res%factors)
         call write_factor(res%factors(i))
      end do

      select case (res%status)
      case (status_ok)
         write (output_unit, '(a)') "RESULT,value=" // trace_int(res%value) // &
            ",converged=" // trace_logical(res%converged) // &
            ",iterations=" // trace_int(res%iterations) // &
            ",nudges=" // trace_int(res%nudges)
      case (status_non_convergent)
         write (output_unit, '(a)') "ERROR,code=NON_CONVERGENT,message=" // &
            trim(adjustl(msg_24()))
      case (status_degree_error)
         write (output_unit, '(a)') "ERROR,code=DEGREE,message=" // &
            trim(adjustl(degree_message(res)))
      end select
   end subroutine write_trace

   !> One FACTOR record.
   subroutine write_factor(f)
      type(bairstow_factor), intent(in) :: f

      select case (f%kind)
      case (factor_quadratic)
         write (output_unit, '(a)') "FACTOR,kind=" // factor_kind_name(f%kind) // &
            ",r=" // trace_real(f%coef(1)) // ",s=" // trace_real(f%coef(2))
      case (factor_final_quadratic)
         write (output_unit, '(a)') "FACTOR,kind=" // factor_kind_name(f%kind) // &
            ",a2=" // trace_real(f%coef(1)) // ",a1=" // trace_real(f%coef(2)) // &
            ",a0=" // trace_real(f%coef(3))
      case default
         write (output_unit, '(a)') "FACTOR,kind=" // factor_kind_name(f%kind) // &
            ",a1=" // trace_real(f%coef(1)) // ",a0=" // trace_real(f%coef(2))
      end select
   end subroutine write_factor

   !> `F14.6`, rounded to nearest, leading zero kept (the --verbose number format).
   function f14(x) result(s)
      real(wp), intent(in) :: x
      character(len=14) :: s

      write (s, '(RN,F14.6)') x
   end function f14

   !> A root for --verbose: `F14.6`, plus `SP,F14.6,"i"` for a nonzero imaginary part.
   function root_text(z) result(s)
      complex(wp), intent(in) :: z
      character(len=:), allocatable :: s
      character(len=14) :: im

      if (is_exact_zero(aimag(z))) then
         s = f14(real(z, wp))
      else
         write (im, '(RN,SP,F14.6)') aimag(z)
         s = f14(real(z, wp)) // im // "i"
      end if
   end function root_text

   !> --verbose: the true factors and their roots, after the book text.
   subroutine write_verbose(res)
      type(bairstow_result), intent(in) :: res
      type(bairstow_factor) :: f
      complex(wp) :: roots(2)
      integer :: i, j, nroots

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " FORMAT 17 PRINTS X**2 + R X + S; THE FACTOR DIVIDED OUT " // &
         "IS X**2 - R X - S."
      do i = 1, size(res%factors)
         f = res%factors(i)
         select case (f%kind)
         case (factor_quadratic)
            write (output_unit, '(a)') " FACTOR " // trace_int(i) // ": R =" // &
               f14(f%coef(1)) // "  S =" // f14(f%coef(2)) // "  ITERATIONS = " // &
               trace_int(count(res%steps%factor == i))
            write (output_unit, '(a)') "   TRUE FACTOR X**2 - R X - S = X**2 +" // &
               f14(-f%coef(1)) // " X +" // f14(-f%coef(2))
         case (factor_final_quadratic)
            write (output_unit, '(a)') " FACTOR " // trace_int(i) // &
               ": FINAL QUADRATIC A2 X**2 + A1 X + A0  A2 =" // f14(f%coef(1)) // &
               "  A1 =" // f14(f%coef(2)) // "  A0 =" // f14(f%coef(3))
         case default
            write (output_unit, '(a)') " FACTOR " // trace_int(i) // ": FINAL LINEAR A1 X + A0  A1 =" // &
               f14(f%coef(1)) // "  A0 =" // f14(f%coef(2))
         end select
         call factor_roots(f, roots, nroots)
         if (nroots == 0) then
            write (output_unit, '(a)') "   NO ROOT (CONSTANT FACTOR)"
         end if
         do j = 1, nroots
            write (output_unit, '(a)') "   ROOT " // root_text(roots(j))
         end do
      end do
      write (output_unit, '(a)') " ZERO-DENOMINATOR NUDGES = " // trace_int(res%nudges)
      write (output_unit, '(a)') " TOTAL ITERATIONS = " // trace_int(res%iterations)
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: ch01_p02_bairstow [--trace] [--verbose] [--help] < data-cards"
      write (unit, '(a)') ""
      write (unit, '(a)') "Quadratic factors of polynomials to sixth degree, Bairstow method,"
      write (unit, '(a)') "Gerald Ch. 1 Program 2."
      write (unit, '(a)') "stdin: card 1 = the 7 coefficients of X**6 ... X**0; card 2 = R1 S1 " // &
         "TEST LIM N"
      write (unit, '(a)') "(book cards: 0. 1. -17.8 99.41 -261.218 352.611 -134.106 / " // &
         "0. 0. 1.E-5 20 5)."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --trace     machine-readable STEP/FACTOR/RESULT/ERROR records only " // &
         "(exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (true factors X**2 - R X - S " // &
         "and roots)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text; " // &
         "book error paths exit 1."
   end subroutine print_usage

end program ch01_p02_bairstow
