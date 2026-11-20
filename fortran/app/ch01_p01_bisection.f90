!===============================================================================
! ch01_p01_bisection.f90
!
! Solution of F(X) = 0 by the interval halving (bisection) method.
! C. F. Gerald, "Applied Numerical Analysis", Chapter 1, Program 1 (book p. 24).
! Authoritative source: docs/chapter_01_program_01_listing.pdf (image-only scan of
! the card listing and its line-printer output). The previous modern rewrite,
! legacy_code/fortran/chapter_1/bisection.f90, was a reference only; this program
! was re-transcribed from the scan.
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/bisection_mod.f90 (module bisection_mod), the functions and presets
! in fortran/src/functions_mod.f90, the book-style number formatting and trace
! helpers in fortran/src/book_format_mod.f90, and the command-line parsing in
! fortran/src/cli_mod.f90.
!
! USAGE
! -----
!   ch01_p01_bisection [--trace] [--verbose] [--preset N] [--help]  < data card
!
!   stdin    the book's data card, list-directed, in the original order
!            X1 X2 TOL   (the book card "0. 1. 1.E-5" works unchanged)
!   --preset N   function to solve (default 1 = the book's function):
!                1 EXP(-X) - SIN(3.1415926*X/2.)   2 X**3 - X - 1   3 COS(X) - X
!   --trace      machine-readable records only (STEP / RESULT / ERROR, see below)
!   --verbose    extras after the book text (final bracket, |F(root)|, precision)
!   --help       usage text
!
!   Without --trace, stdout is the book's line-printer text. Exit status 0 on
!   success; a book error path prints the book's message and exits 1; bad input
!   (non-numeric card, unknown flag, unknown preset) prints a message on stderr
!   and exits 1. With --trace (protocol DD2, docs/architecture.md):
!     STEP,k=<I0>,x1=<r>,x2=<r>,x=<r>,fx=<r>      one per iteration row
!     RESULT,value=<r>,converged=T,iterations=<I0>,root_at_endpoint=<T|F>,
!            fx1=<r>,fx2=<r>                      F(X1), F(X2) of the data card
!     ERROR,code=<BRACKET|ZERO_PRODUCT|NON_CONVERGENT|INPUT>,message=<text>
!   reals as ES25.17E3 without leading blanks; on ERROR the exit status is 2.
!   ZERO_PRODUCT carries the book's message (202 before the loop, "ERROR." for
!   label 11); INPUT also covers a NaN or infinite function value.
!
! TRANSCRIPTION OF THE SCAN
! -------------------------
! The scan, re-read at 300 dpi, is (comment cards abbreviated):
!
!       F(X) = EXPF(-X) - SINF(3.1415926*X/2.)
!       READ 100, X1, X2, TOL
!   100 FORMAT (2F10.0, E10.0)
!       FX1 = F(X1)
!       FX2 = F(X2)
!       IF (FX1*FX2) 1, 2, 3
!     3 TYPE 200
!   200 FORMAT (80H FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOS
!      1ITE SIGNS. CHANGE INPUTS. )
!       CALL EXIT
!     2 IF (FX1) 4, 5, 4
!     5 PRINT 201, X1
!   201 FORMAT (22H THE INPUT VALUE, X = ,F6.3, 27H IS A ROOT OF THE EQUAT
!      1ION. )
!     4 IF (FX2) 6, 7, 6
!     7 PRINT 201, X2
!       CALL EXIT
!     6 PRINT 202
!   202 FORMAT (55H ERROR. FX1 AND FX2 NOT ZERO THOUGH PRODUCT TESTS ZERO.
!      1 )
!       CALL EXIT
!     1 DO 30 I = 1, 25
!       X = (X1 + X2)/2.
!       FX = F(X)
!       PRINT 206, X, FX
!   206 FORMAT (8H AT X = , F10.7, 8H F(X) = ,F10.6)
!       IF (ABSF(FX) - TOL) 8, 8, 9
!     9 IF (FX*FX1) 10, 11, 12
!    10 X2 = X
!       GO TO 30
!    12 X1 = X
!       FX1 = FX
!    30 CONTINUE
!       PRINT 204
!   204 FORMAT (33H NON-CONVERGENT IN 25 ITERATIONS. )
!       CALL EXIT
!    11 PRINT 205
!   205 FORMAT (7H ERROR. )
!       CALL EXIT
!     8 PRINT 203, X, I
!   203 FORMAT (16H THE VALUE, X = ,F10.7, 12H IS A ROOT. , I3, 26H ITERAT
!      1IONS WERE REQUIRED. )
!       CALL EXIT
!       END
!   data card:  0.        1.        1.E-5
!
!   * Every Hollerith count was checked against its text (80, 22, 27, 55, 8, 8,
!     33, 7, 16, 12, 26 characters, leading blank included) and the messages
!     below are emitted character for character.
!   * The listing's print chain renders comma and period with the same raised
!     dot. Commas are required by syntax in "READ 100, X1, X2, TOL" and look
!     identical to the dot in "THE VALUE, X =" and "THE INPUT VALUE, X =", which
!     are therefore transcribed with commas (they are not Hollerith-count
!     sensitive either way).
!   * The deck-control cards (ZZJOB 5, ZZFORX5, *LIST PRINTER, ZZZZ) are job
!     control, not Fortran, and are dropped. The data card and ZZZZ appear in
!     the book's printout only because the deck was listed; they are not program
!     output and are not echoed.
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. Drift of the earlier rewrite (legacy_code/fortran/chapter_1/bisection.f90)
!    from the scan, restored here:
!   * The rewrite had no equivalent of label 11: when FX*FX1 is exactly zero
!     inside the loop (IF (FX*FX1) 10, 11, 12) the scan prints "ERROR." and
!     stops; the rewrite silently moved X1. Restored (status ZERO_PRODUCT).
!   * The rewrite printed "Error: maximum iterations exceeded without
!     convergence."; the scan prints "NON-CONVERGENT IN 25 ITERATIONS.".
!   * The rewrite printed an input root with F10.7; the scan's FORMAT 201 uses
!     F6.3. The rewrite also reworded every message (mixed case, "Error:",
!     "THE VALUE X =" without the comma) and changed the iteration line
!     ("AT X = ...  F(X) = ..."): all messages and formats are the scan's again.
!   * The rewrite tested F(X1)*F(X2) > 0 with a comparison, not the product's
!     sign as an arithmetic IF; that is equivalent except for the exact-zero
!     product, now handled as in the scan (labels 2, 4, 5, 6, 7).
!   * The rewrite's convergence test |FX| <= TOL is kept in the scan's form
!     ABSF(FX) - TOL <= 0 (same result in IEEE arithmetic).
! B. Hard-coded inputs removed: the rewrite assigned X1 = 0, X2 = 1,
!    TOL = 1E-5 in the source. The data card is read from stdin again, in the
!    book's order X1 X2 TOL.
! C. Bug in the original, corrected: label 5 (PRINT 201, X1) has no CALL EXIT
!    and falls through to label 4. With F(X1) = 0 and F(X2) /= 0 the original
!    printed "THE INPUT VALUE, X = ... IS A ROOT OF THE EQUATION." and then
!    "ERROR. FX1 AND FX2 NOT ZERO THOUGH PRODUCT TESTS ZERO.". The listing's own
!    comment ("WHEN PRODUCT OF FX1*FX2 IS ZERO, X1 OR X2 IS A ROOT") states the
!    intent, so the 202 message is no longer printed after an endpoint root and
!    the run succeeds (RESULT with root_at_endpoint=T, iterations=0). When both
!    F(X1) and F(X2) are zero the original's output -- both input values
!    reported as roots, X1 first -- is kept; the trace value is X1.
! D. Modernization (behavior-preserving):
!   * Arithmetic IFs and GO TOs became SELECT CASE on a three-way sign helper
!     (bisection_mod: arith_if) that keeps every exact-zero destination; the
!     products FX1*FX2 and FX*FX1 are still formed, so an underflow to zero
!     takes the zero branch (message 202 before the loop, 205 inside it).
!   * The arithmetic statement function F(X) became a procedure argument
!     (abstract interface real_function); --preset N selects it. EXPF/SINF/ABSF
!     are the generic EXP/SIN/ABS. The book's PI literal 3.1415926 is kept.
!   * READ 100 with FORMAT (2F10.0, E10.0) (fixed card columns 1-10, 11-20,
!     21-30) became a list-directed read, so the card may be typed with any
!     spacing; values must be finite.
!   * TYPE 200 wrote to the console typewriter; message 200 now goes to stdout
!     with the rest of the output.
!   * CALL EXIT became a return with exit status 0 (success) or 1 (book error
!     path), or 2 for an ERROR record in --trace mode.
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! E. Number formatting and precision notes:
!   * The book's machine printed Fw.d fields chopped (rounded toward zero) and
!     without a leading zero: the exact midpoints 0.44140625, 0.443359375,
!     0.44384765625, 0.44354248046875 and 0.443572998046875 print as .4414062,
!     .4433593, .4438476, .4435424 and .4435729. Fortran's default output
!     rounds to nearest (.4414063, ..., .4435730) and prints "0.". The book
!     text therefore uses the standard RZ (round toward zero) edit mode and
!     drops the leading zero (book_format_mod: book_fixed); widths and decimals
!     are the scan's. --trace and --verbose print full precision instead.
!   * With these conventions both builds reproduce, character for character,
!     the X column of all 15 rows, the final line "THE VALUE, X =   .4435729
!     IS A ROOT.  15 ITERATIONS WERE REQUIRED." and the iteration count. (With
!     round-to-nearest, five X values and the root would print one digit
!     higher, e.g. .4435730.)
!   * One last-digit difference remains in the F(X) column of each build. It is
!     documented, not patched: F(X) = EXP(-X) - SIN(...) cancels to about 1E-6
!     near the root, so its sixth decimal depends on the arithmetic.
!     The book's computer is not identified (docs/architecture.md, "The
!     book's computer"). The deck-control cards (ZZJOB, ZZFORX) look like
!     IBM 1620 Monitor cards (8-digit decimal floating point, chopped), and
!     the Bairstow echo (ch01_p02) also suggests a decimal machine, while the
!     chapter 3 sums (ch03_p01, ch03_p02) fit 27-bit chopped binary (IBM 7090
!     class) better. This program does not discriminate: both an 8-digit
!     decimal and a 27-bit binary chopped emulation reproduce the two book
!     digits below, which each IEEE build misses.
!       row 15, real64:  F(.443572998...) =  9.989E-7 -> .000000  (book .000001)
!       row 11, real32:  F(.443847656...) = -5.0598E-4 -> -.000505 (book -.000506)
!     All other F(X) entries agree with the book in both builds, and every
!     F(X) agrees with the book value within 1E-6
!     (fortran/test/test_bisection.f90 checks every row and these exceptions).
! F. Index of the catalog errata (catalog/ch01_p01_bisection.toml [[errata]],
!    also on content/ch01_p01.md), one line per id, in catalog order:
!   1 zero-product-branch (rewrite_drift): label 11 restored; FX*FX1 exactly
!     zero prints " ERROR." and stops. Trace: ERROR,code=ZERO_PRODUCT,
!     message=ERROR. (exit 2). See A.
!   2 non-convergence-message (rewrite_drift): " NON-CONVERGENT IN 25
!     ITERATIONS." after the DO 30 loop; trace code NON_CONVERGENT. See A.
!   3 endpoint-root-format (rewrite_drift): FORMAT 201 with F6.3 (rewrite:
!     F10.7); trace RESULT with root_at_endpoint=T, iterations=0. See A, C.
!   4 product-zero-test-order (rewrite_drift): the rewrite printed the 202
!     message when both values were zero, the opposite of its wording; the
!     order X1-root, X2-root, error (labels 2, 5, 4, 7, 6) is restored and 202
!     is reached only when FX1*FX2 underflows to zero. Trace code ZERO_PRODUCT.
!   5 hard-coded-inputs (rewrite_drift): the data card X1 X2 TOL is read from
!     stdin again, list-directed, in the book's order. See B, D.
!   6 line-layout (rewrite_drift): FORMATs 206 and 203 restored with their
!     Hollerith widths, the comma in "THE VALUE, X =" and the leading blank
!     (carriage-control column, kept on stdout). See A.
!   7 bracket-message-unit (original_quirk): TYPE 200 went to the console
!     typewriter; it is written to stdout with the rest of the run. See D.
!   8 truncated-digits (original_quirk): the book printed chopped digits
!     without a leading zero (.4414062 ... .4435729). The golden tests compare
!     numbers; in addition this driver's book text uses RZ and drops the
!     leading zero so the text matches the scan. See E.
!   9 label-5-fall-through (original_bug): label 5 (PRINT 201, X1) had no CALL
!     EXIT and fell through to message 202 after an endpoint root; corrected,
!     the run ends successfully with root_at_endpoint=T. See C.
!  10 structured-control-flow (modernization): arithmetic IF / GO TO / CALL
!     EXIT became SELECT CASE, a DO loop and STOP with an exit status; F is a
!     procedure argument (--preset N); EXPF/SINF/ABSF became EXP/SIN/ABS;
!     every zero branch is kept. See D.
!  11 non-finite-values (modernization): F returning NaN or +-Inf (for example
!     EXP(-X) overflowing for X < -709 in real64, X < -88 in real32; impossible
!     as IEEE specials on the original machine) stops the run as an INPUT error
!     (ERROR,code=INPUT in trace mode, a message on stderr and exit 1
!     otherwise), matching InputError on the Python engine. See D.
!  12 precision-last-digit (original_quirk): real64 row 15 prints .000000
!     (scan .000001) and real32 row 11 prints -.000505 (scan -.000506); the
!     F(X) values agree with the book within 1E-6. See E.
!===============================================================================
program ch01_p01_bisection
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, get_bisection_preset, preset_expr_len
   use bisection_mod, only: bisection, bisection_result, book_max_iter, status_ok, &
      status_root_at_endpoint, status_bracket_error, status_zero_product_error, &
      status_non_convergent, status_invalid_value
   use book_format_mod, only: book_fixed, book_int, trace_real, trace_int, trace_logical, no_commas
   use cli_mod, only: parse_arguments
   implicit none

   ! Book messages (Hollerith text of FORMATs 200, 202, 204, 205, leading blank included).
   character(len=*), parameter :: msg_200 = &
      " FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS."
   character(len=*), parameter :: msg_202 = &
      " ERROR. FX1 AND FX2 NOT ZERO THOUGH PRODUCT TESTS ZERO."
   character(len=*), parameter :: msg_204 = " NON-CONVERGENT IN 25 ITERATIONS."
   character(len=*), parameter :: msg_205 = " ERROR."

   logical :: trace, verbose, help
   integer :: preset
   character(len=:), allocatable :: arg_error
   procedure(real_function), pointer :: f
   character(len=preset_expr_len) :: expr
   logical :: found
   real(wp) :: x1, x2, tol
   integer :: ios
   type(bisection_result) :: res

   call parse_arguments(trace, verbose, help, preset, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   call get_bisection_preset(preset, f, expr, found)
   if (.not. found) call input_error("unknown preset " // trace_int(preset) // &
      " (valid presets are 1 2 3)")

   ! READ 100, X1, X2, TOL
   read (input_unit, *, iostat=ios) x1, x2, tol
   if (ios /= 0) call input_error( &
      "could not read the data card X1 X2 TOL (three numbers expected on stdin)")
   if (.not. (ieee_is_finite(x1) .and. ieee_is_finite(x2) .and. ieee_is_finite(tol))) &
      call input_error("data card values X1 X2 TOL must be finite numbers")

   res = bisection(f, x1, x2, tol, book_max_iter)

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose) call write_verbose(res)
   end if

   ! Success ends normally (exit status 0); a book error path exits 1, an ERROR record 2.
   if (res%status /= status_ok .and. res%status /= status_root_at_endpoint) then
      if (trace) then
         stop 2, quiet=.true.
      else
         stop 1, quiet=.true.
      end if
   end if

contains

   !> Report bad input and stop: ERROR,code=INPUT (exit 2) in trace mode, else stderr (exit 1).
   subroutine input_error(message)
      character(len=*), intent(in) :: message

      if (trace) then
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // no_commas(message)
         stop 2, quiet=.true.
      else
         write (error_unit, '(a)') "ch01_p01_bisection: " // message
         stop 1, quiet=.true.
      end if
   end subroutine input_error

   !> The book's line-printer output.
   subroutine write_book_text(res)
      type(bisection_result), intent(in) :: res
      integer :: i

      do i = 1, size(res%steps)
         ! 206 FORMAT (8H AT X = , F10.7, 8H F(X) = ,F10.6)
         write (output_unit, '(a)') " AT X = " // book_fixed(res%steps(i)%x, 10, 7) // &
            " F(X) = " // book_fixed(res%steps(i)%fx, 10, 6)
      end do

      select case (res%status)
      case (status_ok)
         ! 203 FORMAT (16H THE VALUE, X = ,F10.7, 12H IS A ROOT. , I3, 26H ITERATIONS WERE ...)
         write (output_unit, '(a)') " THE VALUE, X = " // book_fixed(res%value, 10, 7) // &
            " IS A ROOT. " // book_int(res%iterations, 3) // " ITERATIONS WERE REQUIRED."
      case (status_root_at_endpoint)
         ! 201 FORMAT (22H THE INPUT VALUE, X = ,F6.3, 27H IS A ROOT OF THE EQUATION.)
         if (is_zero(res%fx1)) call write_input_root(x1)
         if (is_zero(res%fx2)) call write_input_root(x2)
      case (status_bracket_error)
         write (output_unit, '(a)') msg_200
      case (status_zero_product_error)
         if (res%iterations == 0) then
            write (output_unit, '(a)') msg_202
         else
            write (output_unit, '(a)') msg_205
         end if
      case (status_non_convergent)
         write (output_unit, '(a)') msg_204
      case (status_invalid_value)
         ! No book message exists: report on stderr like the other input errors.
         write (error_unit, '(a)') "ch01_p01_bisection: " // nan_message(res)
      end select
   end subroutine write_book_text

   !> Message for a NaN or infinite function value (INPUT error; InputError on the Python engine).
   function nan_message(res) result(message)
      type(bisection_result), intent(in) :: res
      character(len=:), allocatable :: message

      message = "F(X) is not a finite number at X = " // trace_real(res%value)
   end function nan_message

   !> FORMAT 201.
   subroutine write_input_root(x)
      real(wp), intent(in) :: x

      write (output_unit, '(a)') " THE INPUT VALUE, X = " // book_fixed(x, 6, 3) // &
         " IS A ROOT OF THE EQUATION."
   end subroutine write_input_root

   !> Exact zero test without a real equality comparison (-Wcompare-reals).
   pure logical function is_zero(v)
      real(wp), intent(in) :: v

      is_zero = v >= 0.0_wp .and. v <= 0.0_wp
   end function is_zero

   !> --trace: STEP records, then exactly one RESULT or ERROR record.
   subroutine write_trace(res)
      type(bisection_result), intent(in) :: res
      integer :: i

      do i = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,k=" // trace_int(res%steps(i)%k) // &
            ",x1=" // trace_real(res%steps(i)%x1) // &
            ",x2=" // trace_real(res%steps(i)%x2) // &
            ",x=" // trace_real(res%steps(i)%x) // &
            ",fx=" // trace_real(res%steps(i)%fx)
      end do

      select case (res%status)
      case (status_ok, status_root_at_endpoint)
         write (output_unit, '(a)') "RESULT,value=" // trace_real(res%value) // &
            ",converged=" // trace_logical(res%converged) // &
            ",iterations=" // trace_int(res%iterations) // &
            ",root_at_endpoint=" // trace_logical(res%status == status_root_at_endpoint) // &
            ",fx1=" // trace_real(res%fx1) // ",fx2=" // trace_real(res%fx2)
      case (status_bracket_error)
         write (output_unit, '(a)') "ERROR,code=BRACKET,message=" // trim(adjustl(msg_200))
      case (status_zero_product_error)
         if (res%iterations == 0) then
            write (output_unit, '(a)') "ERROR,code=ZERO_PRODUCT,message=" // &
               trim(adjustl(msg_202))
         else
            write (output_unit, '(a)') "ERROR,code=ZERO_PRODUCT,message=" // &
               trim(adjustl(msg_205))
         end if
      case (status_non_convergent)
         write (output_unit, '(a)') "ERROR,code=NON_CONVERGENT,message=" // &
            trim(adjustl(msg_204))
      case (status_invalid_value)
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // nan_message(res)
      end select
   end subroutine write_trace

   !> --verbose: extras after the book text.
   subroutine write_verbose(res)
      type(bisection_result), intent(in) :: res
      integer :: last

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      write (output_unit, '(a)') " PRESET " // trace_int(preset) // ": F(X) = " // trim(expr)
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " DATA CARD: X1 = " // trace_real(x1) // "  X2 = " // &
         trace_real(x2) // "  TOL = " // trace_real(tol)
      write (output_unit, '(a)') " F(X1) = " // trace_real(res%fx1) // "  F(X2) = " // &
         trace_real(res%fx2)
      last = size(res%steps)
      if (last > 0) then
         write (output_unit, '(a)') " FINAL BRACKET: X1 = " // trace_real(res%steps(last)%x1) &
            // "  X2 = " // trace_real(res%steps(last)%x2)
         write (output_unit, '(a)') " FINAL BRACKET WIDTH = " // &
            trace_real(abs(res%steps(last)%x2 - res%steps(last)%x1)) // &
            "  (ERROR BOUND |X - ROOT| <= " // &
            trace_real(abs(res%steps(last)%x2 - res%steps(last)%x1)/2.0_wp) // ")"
      end if
      select case (res%status)
      case (status_ok, status_root_at_endpoint)
         write (output_unit, '(a)') " ROOT = " // trace_real(res%value) // &
            "  |F(ROOT)| = " // trace_real(abs(f(res%value)))
      case default
         write (output_unit, '(a)') " LAST X = " // trace_real(res%value) // &
            "  |F(X)| = " // trace_real(abs(f(res%value)))
      end select
      write (output_unit, '(a)') " ITERATIONS = " // trace_int(res%iterations) // &
         " OF " // trace_int(book_max_iter)
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: ch01_p01_bisection [--trace] [--verbose] [--preset N] " // &
         "[--help] < data-card"
      write (unit, '(a)') ""
      write (unit, '(a)') "Interval halving (bisection), Gerald Ch. 1 Program 1."
      write (unit, '(a)') "stdin: the book's data card X1 X2 TOL, list-directed " // &
         "(book card: 0. 1. 1.E-5)."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --preset N  function to solve (default 1):"
      write (unit, '(a)') "                1  EXP(-X) - SIN(3.1415926*X/2.)  (book)"
      write (unit, '(a)') "                2  X**3 - X - 1"
      write (unit, '(a)') "                3  COS(X) - X"
      write (unit, '(a)') "  --trace     machine-readable STEP/RESULT/ERROR records only " // &
         "(exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (final bracket; |F(root)|)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text; " // &
         "book error paths exit 1."
   end subroutine print_usage

end program ch01_p01_bisection
