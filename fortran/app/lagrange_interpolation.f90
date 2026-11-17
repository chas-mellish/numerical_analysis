!===============================================================================
! lagrange_interpolation.f90
!
! Lagrangian polynomial interpolation among N data pairs.
! C. F. Gerald, "Applied Numerical Analysis" -- chapter and program number
! UNCONFIRMED (catalog id lagrange_interpolation, book_ref_confirmed = false).
! Source: legacy_code/fortran/chapter_2/polynomial.F90, a raw OCR text of the
! card listing with the data card and the book's output appended. NO SCAN of
! this program exists (docs/ has no PDF for it), so unlike the other programs
! it could not be re-read from a page image: every correction below is derived
! from FORTRAN syntax, the Hollerith counts and the book's printed result
! 2.3119 at X = 5.0, and the remaining uncertainty is stated explicitly.
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/lagrange_mod.f90 (module lagrange_mod) and the book-style number
! formatting in fortran/src/book_format_mod.f90.
!
! USAGE
! -----
!   lagrange_interpolation [--trace] [--verbose] [--help]  < data card
!
!   stdin    the book's data card, list-directed, in the original order
!            N, then N pairs X(I) Y(I), then XIN   (the book card
!            "05 / 2.3756 1.6 / ... / 8.1919 2.8 / 5.0" works unchanged).
!            1 <= N <= 10 (DIMENSION X(10), Y(10)); X values must be distinct.
!   --trace      machine-readable records only (STEP / RESULT / ERROR, below)
!   --verbose    extras after the book text (the terms, full precision)
!   --preset N   not accepted: the program takes data, not a function (DD3)
!   --help       usage text
!
!   Without --trace, stdout is the book's line-printer text (FORMAT 200). Exit
!   status 0 on success; bad input (non-numeric card, N out of range, equal X
!   values, overflow, unknown flag) prints a message on stderr and exits 1.
!   With --trace (protocol DD2, docs/architecture.md):
!     STEP,i=<I0>,x=<r>,y=<r>,term=<r>,partial=<r>    one per term (DO 20)
!     RESULT,value=<r>,converged=T,iterations=<N>
!     ERROR,code=<DEGREE|INPUT>,message=<text>
!   reals as ES25.17E3 without leading blanks; on ERROR the exit status is 2.
!
! TRANSCRIPTION (from the OCR text; no page image available)
! -------------------------------------------------------------
! The corrected listing is (deck-control cards dropped, see below):
!
!   C       PROGRAM FOR LAGRANGIAN INTERPOLATION
!           DIMENSION X(10), Y(10)
!   C   READ IN NUMBER OF PAIRS OF DATA, THEN READ DATA PAIRS
!           READ 100, N, (X(I), Y(I), I = 1,N)
!   C   READ IN X VALUE FOR WHICH Y IS DESIRED
!           READ 101, XIN
!   C   COMPUTE
!           YOUT = 0.0
!           DO 20 I = 1,N
!           TERM = Y(I)
!           DO 10 J = 1,N
!           IF (I-J) 9,10,9
!       9   TERM = TERM*(XIN - X(J))/(X(I) - X(J))
!      10   CONTINUE
!      20   YOUT = YOUT + TERM
!   C   PRINT OUTPUT
!           PRINT 200, N, XIN, YOUT
!     100   FORMAT (I2/(2F10.0))
!     101   FORMAT (F10.0)
!     200   FORMAT (49H USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG ,I3,
!          1   8H VALUES, / 8H AT X = ,F10.3, 27H THE FUNCTION HAS VALUE OF ,
!          2   F10.4)
!           CALL EXIT
!           END
!   data cards:  05 / 2.3756 1.6 / 3.2682 1.9 / 4.4571 2.2 / 6.0502 2.5 /
!                8.1919 2.8 / 5.0
!
!   * Hollerith counts verified against their text, blanks included:
!     49 = " USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG " (leading AND
!     trailing blank), 8 = " VALUES,", 8 = " AT X = ", 27 = " THE FUNCTION HAS
!     VALUE OF " (leading and trailing blank). All four counts are consistent,
!     which also confirms the comma after VALUES and the blank after "=".
!   * FORMAT 200 therefore prints exactly two records:
!       " USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG   5 VALUES,"
!       " AT X =      5.000 THE FUNCTION HAS VALUE OF     2.3119"
!     The output appended to the OCR text ("AMONG     5 VALUES," and
!     "AT X=   5.0000 THE FUNCTION ...    2.3119") has collapsed/expanded
!     blanks and shows XIN with four decimals, which F10.3 cannot produce:
!     its spacing is an OCR artifact and the FORMAT is followed. Only the
!     digits 5 and 2.3119 are taken from it.
!   * Column order of the pairs: the READ list is X(I), Y(I), so the first
!     number of each pair card is X. Checked numerically: X = 2.3756 ... 8.1919,
!     Y = 1.6 ... 2.8 gives YOUT = 2.3119013 at XIN = 5.0, the book's 2.3119;
!     the swapped reading gives 63.35. The X column is SINH(Y) rounded to four
!     decimals, i.e. the book interpolates the inverse function: the exact
!     value is ASINH(5) = 2.3124383, so 2.3119 carries an interpolation error
!     of about 5.4E-4.
!   * The OCR places "1.6" two blanks after "2.3756", which on a fixed-column
!     2F10.0 card would put both numbers into columns 1-10; the real card had
!     X in columns 1-10 and Y in 11-20. The list-directed read makes the
!     spacing irrelevant.
!   * A second "05" card follows "5.0" in the OCR text, before ZZZZ. The
!     program reads exactly N, N pairs and XIN, then stops; a further card
!     would never be read. It is taken to be an OCR/listing artifact (or the
!     start of an unrun second data set) and is not part of the catalog card.
!     This driver also ignores anything after XIN.
!   * The deck-control cards (ZZJOB 5 / CSC 001 GERALD, C, F, ZZFORX5,
!     *LIST PRINTER, ZZZZ) are job control of the same monitor as the
!     bisection deck, not FORTRAN; they are dropped and not echoed.
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. Slips of the OCR text, corrected (each is required to compile or to
!    reproduce 2.3119):
!   * IF (I=J) 9,10,9 -> IF (I-J) 9,10,9. "=" is not an operator; the
!     arithmetic IF takes the integer I-J: zero (J = I) skips the factor.
!   * TERM = TERM*(XIN - X(J)/X(I) - X(J)) ->
!     TERM = TERM*(XIN - X(J))/(X(I) - X(J)). The OCR lost the closing and
!     opening parentheses around the division; as printed the factor would be
!     XIN - X(J)/X(I) - X(J), which is not the Lagrange basis polynomial and
!     does not give 2.3119.
!   * 100 FORMAT (12/(2F10.0)) -> 100 FORMAT (I2/(2F10.0)): "I" read as "1".
!     N is read with I2 (the card "05"), then one pair per card (2F10.0, the
!     group repeated by format reversion).
!   * Indentation and statement-label columns are ragged in the OCR (labels 9,
!     10, 20 and the PRINT/FORMAT lines drift by a column); in fixed form the
!     labels belong in columns 1-5 and the continuation marks "1", "2" of
!     FORMAT 200 in column 6. Layout only, no semantic change.
!   * File name polynomial.F90: the ".F90" suffix makes compilers treat the
!     file as FREE-form source run through the C preprocessor, but the
!     listing is fixed-form FORTRAN II/IV with comment cards in column 1 ("C")
!     and job-control cards. It could never have compiled under that name; the
!     modern program is free-form Fortran 2018 in a ".f90" file.
! B. Modernization (behavior-preserving on valid data):
!   * READ 100 / READ 101 with fixed card columns became list-directed reads
!     of the whole of stdin in the same order (N, the N pairs, XIN), so the
!     card may be typed with any spacing and line layout; values must be
!     finite.
!   * DIMENSION X(10), Y(10) is enforced: N outside 1..10 overran the arrays
!     in the original; it is now a DEGREE error (DegreeError), reported before
!     the pairs are read.
!   * Equal X values divided by zero in label 9 (X(I) - X(J) = 0) and printed
!     garbage or stopped the machine; they are now an INPUT error naming the
!     first equal pair, before any term is computed.
!   * A term or the running sum that overflows to +-Inf or NaN (no IEEE
!     specials on the original machine) is an INPUT error, reported after the
!     rows completed before it, matching InputError on the Python engine.
!   * The integer arithmetic IF became IF (I /= J); the DO/CONTINUE loops became
!     DO/END DO; CALL EXIT became normal termination (exit status 0) or STOP
!     with status 1 (2 for an ERROR record in --trace mode).
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! C. Number formatting and precision notes:
!   * The book's machine printed Fw.d fields chopped (round toward zero)
!     without a leading zero (see ch01_p01_bisection.f90, same deck-control
!     cards). The book text uses the same convention (book_format_mod:
!     book_fixed with RZ), so e.g. XIN = 0.5 prints "      .500". For the
!     book card it makes no difference: 5.000 and 2.3119 (YOUT = 2.31190129)
!     are the same chopped or rounded.
!   * real64 YOUT = 2.3119012901784366; real32 YOUT = 2.311901 (to about 1E-6).
!     Both print 2.3119, the book's digits, character for character.
! D. Index of the catalog errata (catalog/lagrange_interpolation.toml
!    [[errata]], also on content/lagrange_interpolation.md), in catalog order:
!   1 arithmetic-if-operator (ocr_slip): IF (I=J) -> IF (I-J). See A.
!   2 product-term-parentheses (ocr_slip): (XIN-X(J))/(X(I)-X(J)). See A.
!   3 format-i2 (ocr_slip): FORMAT (12/...) -> (I2/(2F10.0)). See A.
!   4 pair-column-order (ocr_slip): pairs are X(I), Y(I); verified by 2.3119.
!   5 output-spacing (ocr_slip): book output spacing follows FORMAT 200, not
!     the OCR text ("5.0000" cannot come from F10.3). See TRANSCRIPTION.
!   6 trailing-05-card (ocr_slip): the second "05" after XIN is not read.
!   7 file-extension-and-columns (ocr_slip): ".F90" (free form + cpp) for fixed-form
!     source; label/continuation columns. See A.
!   8 deck-control-cards (original_quirk): ZZJOB, ZZFORX, *LIST PRINTER and ZZZZ dropped.
!   9 dimension-limit (modernization): N must be 1..10; DEGREE error. See B.
!  10 duplicate-x (modernization): equal X values are an INPUT error instead
!     of a division by zero. See B.
!  11 non-finite-values (modernization): overflow is an INPUT error. See B.
!  12 list-directed-input (modernization): stdin read list-directed. See B.
!  13 structured-control-flow (modernization): IF (I /= J), DO loops, exit
!     statuses. See B.
!  14 truncated-digits (original_quirk): RZ output without a leading zero.
!     See C.
!  15 unconfirmed-book-reference (original_quirk): chapter/program/page of
!     the book unknown; no scan.
!===============================================================================
program lagrange_interpolation
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite, ieee_value, ieee_quiet_nan
   use precision, only: wp, single_precision
   use lagrange_mod, only: lagrange, lagrange_result, max_points, status_ok, &
      status_degree_error, status_size_mismatch, status_duplicate_x, status_invalid_value
   use book_format_mod, only: book_fixed, book_int, trace_real, trace_int, trace_logical
   implicit none

   !> Fixed-length buffer for command-line arguments.
   integer, parameter :: arg_len = 256
   !> Upper bound on the size of the data card text read from stdin.
   integer, parameter :: max_card_chars = 1000000

   logical :: trace, verbose, help
   character(len=:), allocatable :: arg_error, card
   real(wp) :: xv(max_points), yv(max_points), xin
   integer :: n, i, ios
   type(lagrange_result) :: res

   call parse_arguments(trace, verbose, help, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   call read_stdin(card, ios)
   if (ios /= 0) call input_error("could not read the data card from stdin")

   ! READ 100, N, (X(I), Y(I), I = 1,N)  -- N first, so the DIMENSION can be checked.
   read (card, *, iostat=ios) n
   if (ios /= 0) call input_error( &
      "could not read N (an integer) at the start of the data card")
   if (n < 1 .or. n > max_points) call fail("DEGREE", degree_message(n))

   xv = ieee_value(1.0_wp, ieee_quiet_nan)
   yv = xv
   xin = xv(1)
   ! READ 100 (the pairs) and READ 101, XIN: list-directed, any layout.
   read (card, *, iostat=ios) n, (xv(i), yv(i), i = 1, n), xin
   if (ios /= 0) call input_error("could not read the data card: N then " // &
      trace_int(n) // " pairs X Y then XIN (" // trace_int(2*n + 2) // " numbers expected)")
   if (.not. (all(ieee_is_finite(xv(1:n))) .and. all(ieee_is_finite(yv(1:n))) .and. &
      ieee_is_finite(xin))) call input_error("data card values must be finite numbers")

   res = lagrange(xv(1:n), yv(1:n), xin)

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose .and. res%status == status_ok) call write_verbose(res)
   end if

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
      integer :: i, n, length, stat

      trace = .false.
      verbose = .false.
      help = .false.
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
            if (.not. allocated(arg_error)) arg_error = &
               "lagrange_interpolation takes data and not a function: there are no presets"
            i = i + 1
         case default
            if (index(arg, "--preset=") == 1) then
               if (.not. allocated(arg_error)) arg_error = &
                  "lagrange_interpolation takes data and not a function: there are no presets"
            else if (.not. allocated(arg_error)) then
               arg_error = "unknown argument " // trim(arg) // " (try --help)"
            end if
         end select
         i = i + 1
      end do
   end subroutine parse_arguments

   !> The whole of stdin as one string, lines joined by blanks (one list-directed record).
   subroutine read_stdin(text, ios)
      character(len=:), allocatable, intent(out) :: text
      integer, intent(out) :: ios
      character(len=4096) :: chunk
      integer :: got

      text = ""
      do
         read (input_unit, '(a)', advance='no', iostat=ios, size=got) chunk
         if (is_iostat_end(ios)) exit
         if (is_iostat_eor(ios)) then
            text = text // chunk(1:got) // " "
         else if (ios == 0) then
            text = text // chunk(1:got)
         else
            return
         end if
         if (len(text) > max_card_chars) then
            ios = 1
            return
         end if
      end do
      ios = 0
   end subroutine read_stdin

   !> Message of the DEGREE error (identical to gerald_na.algorithms.lagrange.msg_degree).
   function degree_message(n) result(message)
      integer, intent(in) :: n
      character(len=:), allocatable :: message

      message = "N = " // trace_int(n) // " IS NOT BETWEEN 1 AND " // trace_int(max_points) // &
         " (DIMENSION X(" // trace_int(max_points) // ") Y(" // trace_int(max_points) // "))"
   end function degree_message

   !> Message of a failed run (identical to the Python engine's messages).
   function failure_message(res) result(message)
      type(lagrange_result), intent(in) :: res
      character(len=:), allocatable :: message

      select case (res%status)
      case (status_degree_error)
         message = degree_message(res%n)
      case (status_duplicate_x)
         message = "X(" // trace_int(res%dup_i) // ") AND X(" // trace_int(res%dup_j) // &
            ") ARE EQUAL: LAGRANGIAN INTERPOLATION NEEDS DISTINCT X VALUES"
      case (status_invalid_value)
         message = "THE INTERPOLATED VALUE IS NOT A FINITE NUMBER AFTER TERM " // &
            trace_int(res%iterations + 1)
      case (status_size_mismatch)
         message = "the numbers of X and Y values differ"
      case default
         message = "unexpected status"
      end select
   end function failure_message

   !> Trace error code of a failed run.
   pure function failure_code(status) result(code)
      integer, intent(in) :: status
      character(len=:), allocatable :: code

      if (status == status_degree_error) then
         code = "DEGREE"
      else
         code = "INPUT"
      end if
   end function failure_code

   !> Report an error before the computation and stop (exit 2 in trace mode, else 1).
   subroutine fail(code, message)
      character(len=*), intent(in) :: code, message

      if (trace) then
         write (output_unit, '(a)') "ERROR,code=" // code // ",message=" // no_commas(message)
         stop 2, quiet=.true.
      else
         write (error_unit, '(a)') "lagrange_interpolation: " // message
         stop 1, quiet=.true.
      end if
   end subroutine fail

   !> Bad input: ERROR,code=INPUT (exit 2) in trace mode, else a message on stderr (exit 1).
   subroutine input_error(message)
      character(len=*), intent(in) :: message

      call fail("INPUT", message)
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

   !> The book's line-printer output: FORMAT 200 (two records). Errors go to stderr.
   subroutine write_book_text(res)
      type(lagrange_result), intent(in) :: res

      if (res%status /= status_ok) then
         write (error_unit, '(a)') "lagrange_interpolation: " // failure_message(res)
         return
      end if
      ! 200 FORMAT (49H USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG ,I3,
      !    1   8H VALUES, / 8H AT X = ,F10.3, 27H THE FUNCTION HAS VALUE OF ,F10.4)
      write (output_unit, '(a)') " USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG " // &
         book_int(res%n, 3) // " VALUES,"
      write (output_unit, '(a)') " AT X = " // book_fixed(xin, 10, 3) // &
         " THE FUNCTION HAS VALUE OF " // book_fixed(res%value, 10, 4)
   end subroutine write_book_text

   !> --trace: STEP records, then exactly one RESULT or ERROR record.
   subroutine write_trace(res)
      type(lagrange_result), intent(in) :: res
      integer :: k

      do k = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,i=" // trace_int(res%steps(k)%i) // &
            ",x=" // trace_real(res%steps(k)%x) // &
            ",y=" // trace_real(res%steps(k)%y) // &
            ",term=" // trace_real(res%steps(k)%term) // &
            ",partial=" // trace_real(res%steps(k)%partial)
      end do
      if (res%status == status_ok) then
         write (output_unit, '(a)') "RESULT,value=" // trace_real(res%value) // &
            ",converged=" // trace_logical(res%converged) // &
            ",iterations=" // trace_int(res%iterations)
      else
         write (output_unit, '(a)') "ERROR,code=" // failure_code(res%status) // &
            ",message=" // no_commas(failure_message(res))
      end if
   end subroutine write_trace

   !> --verbose: extras after the book text.
   subroutine write_verbose(res)
      type(lagrange_result), intent(in) :: res
      integer :: k

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " DATA CARD: N = " // trace_int(res%n) // "  XIN = " // &
         trace_real(xin)
      write (output_unit, '(a)') " TERM(I) = Y(I) * PRODUCT OVER J /= I OF " // &
         "(XIN - X(J))/(X(I) - X(J));  YOUT = RUNNING SUM"
      do k = 1, size(res%steps)
         write (output_unit, '(a)') " I = " // book_int(res%steps(k)%i, 2) // &
            "  X = " // trace_real(res%steps(k)%x) // &
            "  Y = " // trace_real(res%steps(k)%y) // &
            "  TERM = " // trace_real(res%steps(k)%term) // &
            "  YOUT = " // trace_real(res%steps(k)%partial)
      end do
      write (output_unit, '(a)') " VALUE = " // trace_real(res%value) // "  (" // &
         trace_int(res%iterations) // " TERMS)"
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: lagrange_interpolation [--trace] [--verbose] [--help] " // &
         "< data-card"
      write (unit, '(a)') ""
      write (unit, '(a)') "Lagrangian polynomial interpolation (Gerald; book reference " // &
         "unconfirmed)."
      write (unit, '(a)') "stdin: the book's data card, list-directed: N (1 to 10), then " // &
         "N pairs X Y, then XIN"
      write (unit, '(a)') "       (book card: 05 / 2.3756 1.6 / 3.2682 1.9 / 4.4571 2.2 / " // &
         "6.0502 2.5 / 8.1919 2.8 / 5.0)."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --trace     machine-readable STEP/RESULT/ERROR records only " // &
         "(exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (every term; full precision)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text; " // &
         "input errors exit 1."
   end subroutine print_usage

end program lagrange_interpolation
