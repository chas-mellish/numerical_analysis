!===============================================================================
! ch03_p01_simpson.f90
!
! Sine integral Si(B) = integral from 0 to B of SIN(X)/X dX by Simpson's 1/3
! rule. C. F. Gerald, "Applied Numerical Analysis", Chapter 3, Program 1
! (book p. 73). Authoritative source: docs/chapter_03_program_01_listing.pdf
! (image-only scan of the card listing and its line-printer output). The
! earlier modern rewrite, legacy_code/fortran/chapter_3/sine_integral.f90, was
! a reference only; this program was re-transcribed from the scan.
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/simpson_mod.f90 (module simpson_mod), the integrands and presets
! in fortran/src/functions_mod.f90, and the book-style number formatting in
! fortran/src/book_format_mod.f90.
!
! USAGE
! -----
!   ch03_p01_simpson [--trace] [--verbose] [--preset N] [--help]  < data card
!
!   stdin    the book's data card, list-directed, in the original order
!            B N   (the book card "5.0           100" works unchanged)
!   --preset N   integrand on [0, B] (default 1 = the book's function):
!                1 SIN(X)/X (limit 1 at X = 0)   2 EXP(-X**2)   3 1/(1+X**2)
!   --trace      machine-readable records only (STEP / RESULT / ERROR, see below)
!   --verbose    extras after the book text (DELX, SUM, full-precision value)
!   --help       usage text
!
!   Without --trace, stdout is the book's line-printer text. Exit status 0 on
!   success; the book's odd-N path prints message 200 and exits 1; bad input
!   (non-numeric card, N < 2, unknown flag or preset) prints a message on
!   stderr and exits 1. With --trace (protocol DD2, docs/architecture.md):
!     STEP,k=<I0>,x=<r>,fx=<r>,weight=<r>       one per ordinate, k = 0..N
!     RESULT,value=<r>,converged=T,iterations=<I0>,delx=<r>,sum=<r>
!     ERROR,code=<ODD_PANELS|INPUT>,message=<text>
!   reals as ES25.17E3 without leading blanks; on ERROR the exit status is 2.
!   iterations = N + 1 (ordinates evaluated). ODD_PANELS carries message 200
!   with its comma written as a semicolon (trace messages contain no commas);
!   INPUT also covers a NaN or infinite function value.
!
! TRANSCRIPTION OF THE SCAN
! -------------------------
! The scan, re-read at 400 dpi, is (comment cards kept, they are short):
!
!   C  PROGRAM FOR SIMPSONS RULE EVALUATION OF SINE INTEGRAL BETWEEN X = 0 AND X = B
!       F(X) = SINF(X)/X
!   C  READ UPPER LIMIT OF INTEGRATION AND NUMBER OF PANELS. N GREATER THAN 2
!       READ 100, B, N
!   C  CHECK THAT NUMBER OF PANELS IS EVEN
!       NHALF = N/2
!       IF (N - 2*NHALF) 99,1,99
!    99 PRINT 200
!       CALL EXIT
!   C  COMPUTE DELTA X.  ADD FIRST, SECOND, AND LAST VALUES TO SUM
!     1 XN = N
!       DELX = B/XN
!       SUM = 1.0 + 4.*F(DELX) + F(B)
!   C  ADD REST OF VALUES TO SUM
!       X = 2.*DELX
!       DO 10 I = 2,NHALF
!       SUM = SUM + 2.*F(X) + 4.*F(X+DELX)
!    10 X = X + 2.*DELX
!   C  COMPUTE INTEGRAL AND OUTPUT THE VALUE
!       SININT = DELX/3.*SUM
!       PRINT 201, B, SININT, N
!       CALL EXIT
!   100 FORMAT (F10.0, I10)
!   200 FORMAT (60H WITH ODD NUMBER OF PANELS, SIMPSONS 1/3 RULE DOES NOT
!      1APPLY )
!   201 FORMAT (41H VALUE OF SINE INTEGRAL FROM X = 0 TO X = , F6.2,
!      1 3H IS , F10.7, 5H WITH , I4, 7H PANELS )
!       END
!   data card:  5.0           100          (B in columns 1-10, N in 11-20)
!   printed:    VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499307 WITH 100 PANELS
!
!   * Hollerith counts checked against their text, leading blank included:
!     41 " VALUE OF SINE INTEGRAL FROM X = 0 TO X =" (the blank before the
!     comma lies outside the field), 3 " IS", 5 " WITH", 7 " PANELS".
!     60H of FORMAT 200 continues onto the next card: card 1 holds 54
!     characters from column 18 to column 71 (" WITH ... DOES NOT"), column 72
!     is a blank, and the continuation card (continuation mark "1" in column
!     6) supplies "APPLY": 54 + 1 + 5 = 60, giving the single blank in
!     "DOES NOT APPLY".
!   * The print chain renders comma and period with the same raised dot. The
!     syntax fixes the commas in "READ 100, B, N", "99,1,99", "2,NHALF" and
!     the FORMAT lists; the dot in "PANELS, SIMPSONS" is read as a comma (as
!     in the rewrite), the one in "DELTA X." as a period. "1.0", "4.", "2.",
!     "3." and "5.0" are decimal points.
!   * The deck-control cards (ZZJOB 5, ZZFORX5, *LIST PRINTER, ZZZZ) are job
!     control, not Fortran, and are dropped; the data card appears in the
!     printout only because the deck was listed, and is not echoed.
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. Text-transcription (OCR) slips recorded in the rewrite's notes, checked
!    against the scan, which reads correctly in every case:
!   * "IF (N = 2*NHALF) 99,1,99" is "IF (N - 2*NHALF) 99,1,99" (an
!     arithmetic IF branches on the sign of N - 2*(N/2): zero for even N).
!   * "DO 10 I = 2.NHALF" is "DO 10 I = 2,NHALF".
!   * "SININT = DELX/3.*5UM" is "SININT = DELX/3.*SUM".
!   * "Fl0.7" in FORMAT 201 is "F10.7".
! B. Drift of the earlier rewrite (sine_integral.f90) from the scan, restored:
!   * The rewrite moved the X = 0 special case into F (F(0) = 1) and summed
!     F(0) + 4F(DELX) + F(B); the scan seeds the sum with the literal 1.0.
!     Here the module takes the seed as an optional argument F0 and uses F(0)
!     otherwise; preset 1 (SIN(X)/X with its limit 1 at X = 0) returns
!     exactly 1, the book's literal, so the sum is bit for bit the book's.
!     For another integrand the seed generalizes to its ordinate F(0).
!   * The rewrite printed a prompt ("Upper limit of integration B, and number
!     of panels N ...") and a blank line before each message ('(/,A)'); the
!     book has neither: FORMATs 200 and 201 contain no slash. Removed.
!   * The rewrite's comment asked for "N (even, > 2)" but accepted N = 2 with
!     a zero-trip loop; see D for the book's reason for "N GREATER THAN 2".
! C. Original quirks (kept and documented):
!   * The seed 1.0 is the limit of SIN(X)/X at X = 0, written as a literal
!     because the statement function cannot be evaluated there.
!   * The book's printer chopped (rounded toward zero) and printed no leading
!     zero, as in Program 1 of Chapter 1; book_fixed applies RZ and drops the
!     leading zero so values below 1 print as the book would (".9460830").
!     The book's own line shows no such value; F6.2 of B and F10.7 of SININT
!     are the scan's.
! D. Modernization (behavior-preserving):
!   * The arithmetic IF (N - 2*NHALF) 99,1,99 became an IF on N - 2*NHALF /= 0
!     with Fortran's truncating integer division, as in the book (a negative
!     odd N is odd as well). The odd check comes first, as in the scan.
!   * DO-loop trip count: FORTRAN II/IV executed a DO body at least once, so
!     with N = 2 (NHALF = 1) the original would have added F(2*DELX) and
!     F(3*DELX) -- ordinates beyond B -- hence the listing's "N GREATER THAN
!     2". The F2018 loop is zero-trip: N = 2 gives the correct three-ordinate
!     rule. N = 0 (division by zero in DELX = B/XN) and negative even N are
!     rejected as INPUT errors; so is N > 1000000 (memory bound of the trace).
!   * The arithmetic statement function F(X) = SINF(X)/X became a procedure
!     argument (abstract interface real_function); --preset N selects it.
!   * READ 100 with FORMAT (F10.0, I10) became a list-directed read, so the
!     card may be typed with any spacing; B must be finite.
!   * CALL EXIT became a return with exit status 0 (success) or 1 (book error
!     path), or 2 for an ERROR record in --trace mode.
!   * The trace message of ODD_PANELS writes the comma of message 200 as a
!     semicolon (DD2: trace messages contain no commas); the book text keeps
!     the comma.
!   * Every summation keeps the scan's order and grouping: SUM = (1.0 +
!     4.*F(DELX)) + F(B), then SUM = (SUM + 2.*F(X)) + 4.*F(X+DELX) with X
!     accumulated by X = X + 2.*DELX, then (DELX/3.)*SUM.
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! E. Precision notes:
!   * Book card 5.0 100: the book printed 1.5499307. The real64 build prints
!     1.5499312 (1.54993123977035374), which agrees with the true Si(5) =
!     1.5499312449... to 8 figures: Simpson's truncation error with N = 100
!     is about 5E-9. The book's 5E-7 deficit is the arithmetic of its
!     machine, not a bug.
!   * The real32 build (-DSINGLE, IEEE binary32, round to nearest) prints
!     1.5499314 (1.54993140697479248), NOT the book's 1.5499307. Arithmetic
!     with a 27-bit binary mantissa and chopped results (IBM 7090/7094 single
!     precision) comes closest: 1.549930662, the book's 1.5499307 when
!     rounded (1.5499306 when chopped); 8-digit decimal chopped (IBM 1620
!     class) gives 1.5499262. The book's computer is not identified (its SIN
!     routine is unknown; see docs/architecture.md, "The book's computer").
!     The order of summation matters in real32: summing the ordinates in k order
!     gives 1.5499310 instead of 1.5499314, so the scan's order is kept
!     exactly. Golden tests compare the SINGLE build with the book value
!     within 1E-6 (fortran/test/test_simpson.f90 pins the exact real32 value).
! F. Index of the catalog errata (catalog/ch03_p01_simpson.toml [[errata]],
!    also on content/ch03_p01.md), one line per id, in catalog order:
!   1 ocr-arithmetic-if (ocr_slip): IF (N = 2*NHALF) -> IF (N - 2*NHALF). A.
!   2 ocr-do-comma (ocr_slip): DO 10 I = 2.NHALF -> 2,NHALF. See A.
!   3 ocr-sum (ocr_slip): DELX/3.*5UM -> DELX/3.*SUM. See A.
!   4 ocr-f10-7 (ocr_slip): Fl0.7 -> F10.7 in FORMAT 201. See A.
!   5 seed-is-f0 (rewrite_drift): SUM seeded with the book's 1.0 = F(0) of
!     SIN(X)/X; the module's optional F0 argument / F(0) generalize it. B.
!   6 prompt-and-blank-lines (rewrite_drift): the rewrite's prompt and '(/,A)'
!     blank lines removed; FORMATs 200 and 201 restored. See B.
!   7 one-trip-do (original_quirk): "N GREATER THAN 2" comes from the one-trip
!     DO loop; N = 2 is the correct three-ordinate rule here. See D.
!   8 truncated-digits (original_quirk): chopped digits, no leading zero. C.
!   9 odd-message-trace-comma (modernization): ODD_PANELS trace message uses
!     a semicolon for the comma of message 200. See D.
!  10 n-below-two (modernization): N = 0 and negative even N are INPUT errors
!     (the book divides by zero). See D.
!  11 structured-control-flow (modernization): arithmetic IF / CALL EXIT /
!     statement function / formatted READ modernized; order of summation
!     kept. See D.
!   Not a catalog id: non-finite function values. F returning NaN or +-Inf
!   (for example 1/(1+X**2) never does, but a learner's function may) stops
!   the run as an INPUT error (ERROR,code=INPUT in trace mode, a message on
!   stderr and exit 1 otherwise), matching InputError on the Python engine.
!===============================================================================
program ch03_p01_simpson
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, get_quadrature_preset, preset_expr_len
   use simpson_mod, only: simpson, simpson_result, max_panels, status_ok, &
      status_odd_panels, status_invalid_input, status_invalid_value
   use book_format_mod, only: book_fixed, book_int, trace_real, trace_int, trace_logical
   implicit none

   !> Fixed-length buffer for command-line arguments.
   integer, parameter :: arg_len = 256

   !> Book message 200 (Hollerith text, leading blank included).
   character(len=*), parameter :: msg_200 = &
      " WITH ODD NUMBER OF PANELS, SIMPSONS 1/3 RULE DOES NOT APPLY"

   logical :: trace, verbose, help
   integer :: preset
   character(len=:), allocatable :: arg_error
   procedure(real_function), pointer :: f
   character(len=preset_expr_len) :: expr
   logical :: found
   real(wp) :: b
   integer :: n, ios
   type(simpson_result) :: res

   call parse_arguments(trace, verbose, help, preset, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   call get_quadrature_preset(preset, f, expr, found)
   if (.not. found) call input_error("unknown preset " // trace_int(preset) // &
      " (valid presets are 1 2 3)")

   ! READ 100, B, N
   read (input_unit, *, iostat=ios) b, n
   if (ios /= 0) call input_error( &
      "could not read the data card B N (a number and an integer expected on stdin)")
   if (.not. ieee_is_finite(b)) call input_error("data card value B must be a finite number")

   res = simpson(f, b, n)

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose .and. res%status == status_ok) call write_verbose(res)
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
   subroutine parse_arguments(trace, verbose, help, preset, arg_error)
      logical, intent(out) :: trace, verbose, help
      integer, intent(out) :: preset
      character(len=:), allocatable, intent(out) :: arg_error
      character(len=arg_len) :: arg
      integer :: i, n, length, stat

      trace = .false.
      verbose = .false.
      help = .false.
      preset = 1
      n = command_argument_count()
      i = 1
      do while (i <= n)
         call get_command_argument(i, arg, length, stat)
         if (stat /= 0 .or. length > arg_len) then
            if (.not. allocated(arg_error)) arg_error = "command-line argument " // &
               trace_int(i) // " is too long"
            i = i + 1
            cycle
         end if
         select case (trim(arg))
         case ("--trace")
            trace = .true.
         case ("--verbose")
            verbose = .true.
         case ("--help", "-h")
            help = .true.
         case ("--preset")
            if (i == n) then
               if (.not. allocated(arg_error)) arg_error = "--preset needs a number"
            else
               i = i + 1
               call get_command_argument(i, arg, length, stat)
               call parse_preset(arg, stat == 0 .and. length <= arg_len, preset, arg_error)
            end if
         case default
            if (index(arg, "--preset=") == 1) then
               call parse_preset(arg(len("--preset=") + 1:), .true., preset, arg_error)
            else if (.not. allocated(arg_error)) then
               arg_error = "unknown argument " // trim(arg) // " (try --help)"
            end if
         end select
         i = i + 1
      end do
   end subroutine parse_arguments

   !> Parse the value of --preset.
   subroutine parse_preset(text, ok, preset, arg_error)
      character(len=*), intent(in) :: text
      logical, intent(in) :: ok
      integer, intent(inout) :: preset
      character(len=:), allocatable, intent(inout) :: arg_error
      integer :: ios, value

      value = 0
      ios = 1
      if (ok .and. len_trim(text) > 0 .and. verify(trim(text), "0123456789") == 0) then
         read (text, *, iostat=ios) value
      end if
      if (ios == 0) then
         preset = value
      else if (.not. allocated(arg_error)) then
         arg_error = "--preset needs a positive integer (got " // trim(text) // ")"
      end if
   end subroutine parse_preset

   !> Report bad input and stop: ERROR,code=INPUT (exit 2) in trace mode, else stderr (exit 1).
   subroutine input_error(message)
      character(len=*), intent(in) :: message

      if (trace) then
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // no_commas(message)
         stop 2, quiet=.true.
      else
         write (error_unit, '(a)') "ch03_p01_simpson: " // message
         stop 1, quiet=.true.
      end if
   end subroutine input_error

   !> Message text for a trace record: commas are field separators, so replace them.
   pure function no_commas(text) result(s)
      character(len=*), intent(in) :: text
      character(len=len(text)) :: s
      integer :: i

      s = text
      do i = 1, len(s)
         if (s(i:i) == ",") s(i:i) = ";"
      end do
   end function no_commas

   !> Message of the INPUT errors detected by the module.
   function input_message(res) result(message)
      type(simpson_result), intent(in) :: res
      character(len=:), allocatable :: message

      if (res%status == status_invalid_value) then
         message = "F(X) is not a finite number at X = " // trace_real(res%value)
      else
         message = "the number of panels N must be an even number from 2 to " // &
            trace_int(max_panels) // " (got " // trace_int(n) // ")"
      end if
   end function input_message

   !> The book's line-printer output.
   subroutine write_book_text(res)
      type(simpson_result), intent(in) :: res

      select case (res%status)
      case (status_ok)
         ! 201 FORMAT (41H VALUE OF SINE INTEGRAL FROM X = 0 TO X = , F6.2,
         !    1 3H IS , F10.7, 5H WITH , I4, 7H PANELS )
         write (output_unit, '(a)') " VALUE OF SINE INTEGRAL FROM X = 0 TO X =" // &
            book_fixed(b, 6, 2) // " IS" // book_fixed(res%value, 10, 7) // &
            " WITH" // book_int(n, 4) // " PANELS"
      case (status_odd_panels)
         ! 99 PRINT 200
         write (output_unit, '(a)') msg_200
      case (status_invalid_input, status_invalid_value)
         ! No book message exists: report on stderr like the other input errors.
         write (error_unit, '(a)') "ch03_p01_simpson: " // input_message(res)
      end select
   end subroutine write_book_text

   !> --trace: STEP records, then exactly one RESULT or ERROR record.
   subroutine write_trace(res)
      type(simpson_result), intent(in) :: res
      integer :: i

      do i = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,k=" // trace_int(res%steps(i)%k) // &
            ",x=" // trace_real(res%steps(i)%x) // &
            ",fx=" // trace_real(res%steps(i)%fx) // &
            ",weight=" // trace_real(res%steps(i)%weight)
      end do

      select case (res%status)
      case (status_ok)
         write (output_unit, '(a)') "RESULT,value=" // trace_real(res%value) // &
            ",converged=" // trace_logical(res%converged) // &
            ",iterations=" // trace_int(res%iterations) // &
            ",delx=" // trace_real(res%delx) // ",sum=" // trace_real(res%sum)
      case (status_odd_panels)
         write (output_unit, '(a)') "ERROR,code=ODD_PANELS,message=" // &
            trim(adjustl(no_commas(msg_200)))
      case (status_invalid_input, status_invalid_value)
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // &
            no_commas(input_message(res))
      end select
   end subroutine write_trace

   !> --verbose: extras after the book text.
   subroutine write_verbose(res)
      type(simpson_result), intent(in) :: res

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      write (output_unit, '(a)') " PRESET " // trace_int(preset) // ": F(X) = " // trim(expr)
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " DATA CARD: B = " // trace_real(b) // "  N = " // trace_int(n)
      write (output_unit, '(a)') " DELX = B/N = " // trace_real(res%delx)
      write (output_unit, '(a)') " SUM OF WEIGHTED ORDINATES = " // trace_real(res%sum)
      write (output_unit, '(a)') " INTEGRAL = DELX/3*SUM = " // trace_real(res%value)
      write (output_unit, '(a)') " ORDINATES EVALUATED = " // trace_int(res%iterations)
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: ch03_p01_simpson [--trace] [--verbose] [--preset N] " // &
         "[--help] < data-card"
      write (unit, '(a)') ""
      write (unit, '(a)') "Simpson's 1/3 rule from X = 0 to X = B, Gerald Ch. 3 Program 1."
      write (unit, '(a)') "stdin: the book's data card B N, list-directed " // &
         "(book card: 5.0 100); N must be even."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --preset N  integrand (default 1):"
      write (unit, '(a)') "                1  SIN(X)/X, limit 1 at X = 0  (book)"
      write (unit, '(a)') "                2  EXP(-X**2)"
      write (unit, '(a)') "                3  1/(1+X**2)"
      write (unit, '(a)') "  --trace     machine-readable STEP/RESULT/ERROR records only " // &
         "(exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (DELX; SUM; full value)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text; " // &
         "book error paths exit 1."
   end subroutine print_usage

end program ch03_p01_simpson
