!===============================================================================
! ch04_p01_central_difference.f90
!
! First and second derivatives by central-difference formulas. C. F. Gerald,
! "Applied Numerical Analysis", Chapter 4, Program 1 (book p. 90).
! Authoritative source: legacy_code/fortran/chapter_4/derivatives.pdf (image-only
! scan of the card listing and its line-printer output; no OCR text exists).
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/derivative_mod.f90 (module derivative_mod), the functions and
! presets in fortran/src/functions_mod.f90, the book-style number formatting and
! trace helpers in fortran/src/book_format_mod.f90, and the command-line parsing
! in fortran/src/cli_mod.f90.
!
! USAGE
! -----
!   ch04_p01_central_difference [--trace] [--verbose] [--preset N] [--help]
!                               < data card
!
!   stdin    the book's data card, list-directed, in the original order
!            X H   (the book card "0.0       0.1" works unchanged)
!   --preset N   function (default 1 = the book's function):
!                1 X**2*EXP(X)   2 SIN(X)   3 1 + LOG10(X)
!   --trace      machine-readable records only (STEP / RESULT / ERROR, see below)
!   --verbose    extras after the book text (F(X), every row at full precision
!                with the change from the row before, the final value)
!   --help       usage text
!
!   Without --trace, stdout is the book's line-printer text. Exit status 0 on
!   success; bad input (non-numeric card, X or H not finite, H <= 0, unknown
!   flag or preset) prints a message on stderr and exits 1 before the heading;
!   a non-finite F(X), F(X+H), F(X-H), DX or DDX prints the heading and the rows
!   computed so far, then a message on stderr, and exits 1. With --trace
!   (protocol DD2, docs/architecture.md):
!     STEP,k=<I0>,h=<r>,dx=<r>,ddx=<r>          one per printed row, k = 1..10
!     RESULT,value=<r>,converged=T,iterations=10,fo=<r>,first_dx=<r>,
!            first_ddx=<r>,last_ddx=<r>
!     ERROR,code=INPUT,message=<text>
!   reals as ES25.17E3 without leading blanks; on ERROR the exit status is 2
!   (the STEP records of the rows computed before the error come first).
!   value is DX of the last row (the smallest H): the program has no stopping
!   test, so converged is always T.
!
! TRANSCRIPTION OF THE SCAN
! -------------------------
! The scan (book p. 90, re-read at 150 and 220 dpi) is (comment cards kept):
!
!   ZZJOB 5                                   CSC 001      GERALD, C. F.
!   ZZFORX5
!   *LIST PRINTER
!   C  PROGRAM TO COMPUTE DERIVATIVES BY FINITE DIFFERENCE FORMULAS
!   C  DEFINE THE FUNCTION BY AN ARITHMETIC STATEMENT FUNCTION
!         F(X) = X**2*EXPF(X)
!   C  READ IN X VALUE AND INITIAL VALUE OF DELTA X
!         READ 100, X, H
!   C  PRINT HEADING
!         PRINT 200, X
!   C  COMPUTE DERIVATIVES AND PRINT.  DECREASE H AND REPEAT
!         FO = F(X)
!         DO 10 I = 1,10
!         FR = F(X + H)
!         FL = F(X - H)
!         DX = (FR - FL)/(2.*H)
!         DDX = (FR - 2.*FO + FL)/H**2
!         PRINT 201, H, DX, DDX
!      10 H = 0.1*H
!         CALL EXIT
!     100 FORMAT (2F10.0)
!     200 FORMAT (52H DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS /
!        1 8H AT X = , F5.2 // 4X, 1HH, 13X, 2HDX, 17X, 3HDDX /)
!     201 FORMAT (1H , E8.1, 5X, E14.7, 5X, E14.7)
!         END
!   0.0       0.1
!   ZZZZ
!
!   data card:  0.0       0.1     (X in columns 1-10, H in columns 11-20)
!   printed (carriage-control column dropped, as in the scan):
!     DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS
!     AT X =  0.00
!
!        H             DX                 DDX
!
!     1.0E-01      1.0016675E-02      2.0100083E+00
!     1.0E-02      1.0000150E-04      2.0000999E+00
!     1.0E-03      9.9995000E-07      2.0000009E+00
!     1.0E-04      1.0000000E-08      2.0000000E+00
!     1.0E-05      9.9500000E-11      1.9999999E+00
!     1.0E-06      9.5000000E-13      1.9999999E+00
!     1.0E-07      5.0000000E-15      1.9999999E+00
!     1.0E-08      0.0000000E-99      2.0000000E+00
!     1.0E-09      0.0000000E-99      2.0000000E+00
!     1.0E-10      0.0000000E-99      2.0000000E+00
!
!   * Hollerith counts checked against their text, leading blank included:
!     52 " DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS", 8 " AT X = "
!     (the trailing blank precedes F5.2, which prints " 0.00": two blanks
!     before the 0 in "AT X =  0.00"), 1 "H", 2 "DX", 3 "DDX", 1 " " (the
!     carriage control of FORMAT 201). 4X supplies the carriage-control blank
!     and three more columns before H.
!   * The slash after the 52H field ends the first record; "//" ends the
!     "AT X =" record and writes an empty record; the closing "/)" writes the
!     empty record after the column headings.
!   * The print chain renders comma and period with the same raised dot; the
!     syntax fixes the commas ("READ 100, X, H", "1,10", the FORMAT lists) and
!     the decimal points ("2.*H", "2.*FO", "0.1*H", "2F10.0", "E14.7").
!   * FO is the letter O ("F at the origin of the stencil", next to FR and FL),
!     not F-zero.
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. Original quirks (kept and documented):
!   * The deck-control cards ZZJOB 5, ZZFORX5, *LIST PRINTER and ZZZZ are job
!     control of the book's monitor system, not Fortran; they are dropped and
!     the driver reads only the data card from stdin.
!   * FO is the letter O; the Fortran variable keeps the name and the trace
!     RESULT key is fo. FO is evaluated once, before the DO loop.
!   * 10 H = 0.1*H accumulates H: on a binary machine row k uses H slightly
!     different from 10**(1-k) times the card's H (real64 row 10: H =
!     1.0000000000000006E-10). Kept; the literal is 0.1_wp, so both engines
!     multiply by the same double.
!   * The book's E editing printed one digit before the point (1.0E-01,
!     1.0016675E-02): modern ES editing (book_e in book_format_mod), with DX
!     and DDX chopped (RZ) like the other book printouts and the echoes X and H
!     rounded to nearest (RN: chopping the binary value of X = .29 would print
!     0.28, of H = 1.E-6 9.9E-07). F5.2 keeps its leading zero ("0.00"), unlike
!     the Chapter 1 and 3 printouts (fixed_leading_zero).
!   * An exact zero prints as 0.0000000E-99 (the floating-point zero of the
!     book's machine, smallest exponent -99); a negative zero keeps its sign.
!     The trace and the result carry the number 0.
!   * The digits of the book's small-H rows (DX 1.0000150E-04 ... 5.0000000E-15
!     then 0; DDX 2.0000999, 2.0000009, 1.9999999) are round-off of its 8-digit
!     machine, which is what the program demonstrates. See C.
! B. Modernization (behavior-preserving):
!   * EXPF is the FORTRAN II name of EXP: preset 1 is X**2*EXP(X).
!   * The arithmetic statement function F(X) became a procedure argument
!     (abstract interface real_function); --preset N selects it.
!   * READ 100 with FORMAT (2F10.0) became a list-directed read, so the card
!     may be typed with any spacing; Hollerith fields became character
!     constants; CALL EXIT became a normal end (exit status 0).
!   * The order and grouping of every operation are kept: FO before the loop,
!     then FR = F(X + H), FL = F(X - H), DX = (FR - FL)/(2*H), DDX = ((FR -
!     2*FO) + FL)/(H*H) (H**2 is a multiplication), H = 0.1*H.
!   * H <= 0 (the book divides by zero for H = 0; a negative H mirrors the
!     rows) and a non-finite X or H are INPUT errors, reported before the
!     heading is printed.
!   * F(X), F(X+H) or F(X-H) returning NaN or +-Inf (EXP overflows for X > 709
!     in real64, X > 88 in real32; LOG10 of X - H <= 0 for preset 3), or DX or
!     DDX overflowing (or H*H underflowing to 0), is an INPUT error: the book
!     text keeps the heading and the rows computed so far, then a message on
!     stderr and exit status 1; in trace mode the STEP records so far, then
!     ERROR,code=INPUT and exit status 2.
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! C. Precision notes (catalog precision_notes has the details):
!   * At X = 0 the book function gives DX = H*SINH(H) and DDX = 2*COSH(H)
!     exactly. Real64 keeps about 16 digits: row 2 prints DX = 1.0000166E-04,
!     the last row 1.0000000E-20 and DDX = 2.0000000E+00 from H = 1E-4 on.
!   * The real32 build (IEEE binary32) behaves like the book: EXP(H) rounds to
!     1 for H below 6E-8, so DX is exactly 0 for the last three rows, printed
!     0.0000000E-99. The golden tests compare per column in absolute terms.
!   * The book's computer is not identified (docs/architecture.md, "The
!     book's computer").
! D. Index of the catalog errata (catalog/ch04_p01_central_difference.toml
!    [[errata]], also on content/ch04_p01.md), one line per id, in catalog
!    order:
!   1 job-control-cards (original_quirk): ZZJOB / ZZFORX5 / *LIST PRINTER /
!     ZZZZ omitted. See A.
!   2 expf-is-exp (modernization): EXPF -> EXP (preset 1). See B.
!   3 fo-letter-o (original_quirk): FO is F-letter-O, RESULT key fo. See A.
!   4 accumulated-h (original_quirk): H = 0.1*H accumulated, 0.1_wp. See A.
!   5 book-number-format (original_quirk): ES-style E8.1 / E14.7, DX and DDX
!     chopped, X and H rounded to nearest, F5.2 with its leading zero. See A.
!   6 zero-exponent-99 (original_quirk): an exact zero prints 0.0000000E-99.
!     See A.
!   7 small-h-round-off (original_quirk): the book's small-H digits are its
!     machine's round-off; real64 prints other digits. See A and C.
!   8 structured-control-flow (modernization): statement function, READ 100,
!     Hollerith FORMAT 200 and CALL EXIT modernized; operation order kept.
!     See B.
!   9 h-positive (modernization): H <= 0 and non-finite X or H are INPUT
!     errors before the heading. See B.
!  10 non-finite-values (modernization): non-finite F, DX or DDX is an INPUT
!     error keeping the rows computed so far. See B.
!===============================================================================
program ch04_p01_central_difference
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, get_derivative_preset, preset_expr_len
   use derivative_mod, only: central_difference, derivative_result, book_rows, status_ok, &
      status_invalid_input, status_invalid_value, status_invalid_estimate, which_fo, which_fr, &
      which_fl
   use book_format_mod, only: book_e, fixed_leading_zero, trace_real, trace_int, &
      trace_logical, no_commas
   use cli_mod, only: parse_arguments
   implicit none

   !> The 52H field of FORMAT 200, carriage-control blank included.
   character(len=*), parameter :: heading = &
      " DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS"
   !> 4X, 1HH, 13X, 2HDX, 17X, 3HDDX (the first blank of 4X is the carriage control).
   character(len=*), parameter :: column_headings = &
      "    H" // repeat(" ", 13) // "DX" // repeat(" ", 17) // "DDX"

   logical :: trace, verbose, help
   integer :: preset
   character(len=:), allocatable :: arg_error
   procedure(real_function), pointer :: f
   character(len=preset_expr_len) :: expr
   logical :: found
   real(wp) :: x, h
   integer :: ios
   type(derivative_result) :: res

   call parse_arguments(trace, verbose, help, preset, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   call get_derivative_preset(preset, f, expr, found)
   if (.not. found) call input_error("unknown preset " // trace_int(preset) // &
      " (valid presets are 1 2 3)")

   ! READ 100, X, H
   read (input_unit, *, iostat=ios) x, h
   if (ios /= 0) call input_error( &
      "could not read the data card X H (two numbers expected on stdin)")
   if (.not. ieee_is_finite(x)) call input_error("data card value X must be a finite number")
   if (.not. (ieee_is_finite(h) .and. h > 0.0_wp)) call input_error( &
      "the initial step H must be a positive finite number (got " // trace_real(h) // ")")

   res = central_difference(f, x, h, book_rows)
   if (res%status == status_invalid_input) call input_error(input_message(res))

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose .and. res%status == status_ok) call write_verbose(res)
   end if

   ! Success ends normally (exit status 0); an error after the heading exits 1, an ERROR record 2.
   if (res%status /= status_ok) then
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
         write (error_unit, '(a)') "ch04_p01_central_difference: " // message
         stop 1, quiet=.true.
      end if
   end subroutine input_error

   !> Message of the INPUT errors detected by the module.
   function input_message(res) result(message)
      type(derivative_result), intent(in) :: res
      character(len=:), allocatable :: message

      select case (res%status)
      case (status_invalid_value)
         select case (res%failed_which)
         case (which_fo)
            message = "F(X)"
         case (which_fr)
            message = "F(X+H)"
         case (which_fl)
            message = "F(X-H)"
         case default
            message = "F"
         end select
         message = message // " is not a finite number at X = " // trace_real(res%failed_at)
      case (status_invalid_estimate)
         message = "DX or DDX is not a finite number at H = " // trace_real(res%failed_at) // &
            " (row " // trace_int(res%failed_row) // ")"
      case default
         message = "X and H must be finite and H positive (got X = " // trace_real(x) // &
            " and H = " // trace_real(h) // ")"
      end select
   end function input_message

   !> The book's line-printer output: FORMAT 200 (heading), then FORMAT 201 per row.
   subroutine write_book_text(res)
      type(derivative_result), intent(in) :: res
      integer :: i

      ! PRINT 200, X
      write (output_unit, '(a)') heading
      write (output_unit, '(a)') " AT X = " // fixed_leading_zero(x, 5, 2, "RN")
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') column_headings
      write (output_unit, '(a)') ""
      ! PRINT 201, H, DX, DDX
      do i = 1, size(res%steps)
         write (output_unit, '(a)') " " // book_e(res%steps(i)%h, 8, 1, "RN") // &
            repeat(" ", 5) // book_e(res%steps(i)%dx, 14, 7, "RZ") // &
            repeat(" ", 5) // book_e(res%steps(i)%ddx, 14, 7, "RZ")
      end do
      if (res%status /= status_ok) then
         ! No book message exists: report on stderr like the other input errors.
         write (error_unit, '(a)') "ch04_p01_central_difference: " // input_message(res)
      end if
   end subroutine write_book_text

   !> --trace: STEP records, then exactly one RESULT or ERROR record.
   subroutine write_trace(res)
      type(derivative_result), intent(in) :: res
      integer :: i

      do i = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,k=" // trace_int(res%steps(i)%k) // &
            ",h=" // trace_real(res%steps(i)%h) // &
            ",dx=" // trace_real(res%steps(i)%dx) // &
            ",ddx=" // trace_real(res%steps(i)%ddx)
      end do

      if (res%status == status_ok) then
         write (output_unit, '(a)') "RESULT,value=" // trace_real(res%value) // &
            ",converged=" // trace_logical(res%converged) // &
            ",iterations=" // trace_int(res%iterations) // &
            ",fo=" // trace_real(res%fo) // &
            ",first_dx=" // trace_real(res%first_dx) // &
            ",first_ddx=" // trace_real(res%first_ddx) // &
            ",last_ddx=" // trace_real(res%last_ddx)
      else
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // &
            no_commas(input_message(res))
      end if
   end subroutine write_trace

   !> --verbose: extras after the book text (CentralDifferenceAdapter.verbose_text).
   subroutine write_verbose(res)
      type(derivative_result), intent(in) :: res
      character(len=:), allocatable :: line
      integer :: i

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      write (output_unit, '(a)') " PRESET " // trace_int(preset) // ": F(X) = " // trim(expr)
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " DATA CARD: X = " // trace_real(x) // "  H = " // trace_real(h)
      write (output_unit, '(a)') " FO = F(X) = " // trace_real(res%fo)
      do i = 1, size(res%steps)
         line = "   ROW " // trace_int(res%steps(i)%k) // ": H = " // &
            trace_real(res%steps(i)%h) // "  DX = " // trace_real(res%steps(i)%dx) // &
            "  DDX = " // trace_real(res%steps(i)%ddx)
         if (i > 1) then
            line = line // "  |DX CHANGE| = " // &
               trace_real(abs(res%steps(i)%dx - res%steps(i - 1)%dx)) // &
               "  |DDX CHANGE| = " // trace_real(abs(res%steps(i)%ddx - res%steps(i - 1)%ddx))
         end if
         write (output_unit, '(a)') line
      end do
      write (output_unit, '(a)') " VALUE = DX OF THE LAST ROW = " // trace_real(res%value)
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: ch04_p01_central_difference [--trace] [--verbose] " // &
         "[--preset N] [--help] < data-card"
      write (unit, '(a)') ""
      write (unit, '(a)') "F'(X) and F''(X) by central differences for ten values of H " // &
         "(H = 0.1*H after each row),"
      write (unit, '(a)') "Gerald Ch. 4 Program 1."
      write (unit, '(a)') "stdin: the book's data card X H, list-directed " // &
         "(book card: 0.0 0.1); H must be positive."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --preset N  function (default 1):"
      write (unit, '(a)') "                1  X**2*EXP(X)  (book)"
      write (unit, '(a)') "                2  SIN(X)"
      write (unit, '(a)') "                3  1 + LOG10(X)  (p. 91 problem 2)"
      write (unit, '(a)') "  --trace     machine-readable STEP/RESULT/ERROR records only " // &
         "(exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (F(X); full-precision " // &
         "rows and their changes)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text; " // &
         "errors exit 1."
   end subroutine print_usage

end program ch04_p01_central_difference
