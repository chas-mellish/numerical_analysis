!===============================================================================
! ch03_p02_romberg.f90
!
! Value of the sine integral Si(B) = integral of SIN(X)/X from 0 to B by Romberg
! integration. C. F. Gerald, "Applied Numerical Analysis", Chapter 3, Program 2
! (book p. 74). Authoritative source: docs/chapter_03_program_02_listing.pdf
! (image-only scan of the card listing and its line-printer output). The text
! transcription legacy_code/fortran/chapter_3/integration.f90 is raw OCR and was
! a reference only; this program was re-transcribed from the scan.
!
! This file is the thin I/O driver. The algorithm lives in
! fortran/src/romberg_mod.f90 (module romberg_mod), the integrands and presets in
! fortran/src/functions_mod.f90, and the book-style number formatting in
! fortran/src/book_format_mod.f90.
!
! USAGE
! -----
!   ch03_p02_romberg [--trace] [--verbose] [--preset N] [--help]  < data card
!
!   stdin    the book's data card, list-directed, in the original order
!            B TOL   (the book card "15.0 2.E-7" works unchanged)
!   --preset N   integrand on [0, B] (default 1 = the book's):
!                1 SIN(X)/X (limit 1 at X = 0)   2 EXP(-X**2)   3 1/(1+X**2)
!   --trace      machine-readable records only (STEP / TABLE / RESULT / ERROR)
!   --verbose    extras after the book text (full-precision table, estimates)
!   --help       usage text
!
!   Without --trace, stdout is the book's line-printer text. Exit status 0 on
!   success, including a run that did not meet the tolerance after 8
!   extrapolations (the book prints the 9x9 table and FORMAT 201: a result, not
!   an error); bad input (non-numeric card, unknown flag, unknown preset, a NaN or
!   infinite function value) prints a message on stderr and exits 1. With
!   --trace (protocol DD2, docs/architecture.md):
!     STEP,k=<I0>,panels=<I0>,h=<r>,trap=<r>,best=<r>,diff=<r>  one per halving
!     TABLE,row=<I0>,col=<I0>,value=<r>     every computed TRAP(row,col), in the
!                                           book's printing order (col, then row)
!     RESULT,value=<r>,converged=<T|F>,iterations=<I0>,subintervals=<I0>
!     ERROR,code=INPUT,message=<text>       (exit status 2)
!   reals as ES25.17E3 without leading blanks.
!
! TRANSCRIPTION OF THE SCAN
! -------------------------
! The scan, re-read at 400-600 dpi, is (job cards and comment cards abbreviated):
!
!       FCN(X) = SINF(X)/X
!       DIMENSION TRAP(9,9)
!       READ 100, B, TOL
!       H = B/10.
!       SUM = 1. + FCN(B)
!       X = 0.0
!       DO 10 I = 2,10
!       X = X + H
!    10 SUM = SUM + FCN(X)*2.
!       TRAP(1,1) = H/2.*SUM
!       DO 20 I = 1,8
!       H = H/2.
!       X = H
!       K = 10.*2.**I
!       DO 30 J = 2,K,2
!       SUM = SUM + FCN(X)*2.
!    30 X = X + H + H
!       TRAP(1,I+1) = H/2.*SUM
!       DO 40 II = 1,I
!    40 TRAP(II+1,I+1) = TRAP(II,I+1) + 1./(4.**II - 1.)*(TRAP(II,I+1) -
!      1 TRAP(II,I))
!       IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1))- TOL) 50,50,20
!    20 CONTINUE
!       PRINT 200, B
!       DO 60 K = 1,9
!    60 PRINT 203, (TRAP(J,K), J = 1,K)
!       PRINT 201, TRAP(9,9), TOL
!       CALL EXIT
!    50 PRINT 200, B
!       I = I + 1
!       DO 70 L = 1,I
!    70 PRINT 203, (TRAP(J,L), J = 1,L)
!       PRINT 202, TRAP(I,I), K, TOL
!       CALL EXIT
!   100 FORMAT (F10.0, E10.0)
!   200 FORMAT (// 38H VALUE OF SINE INTEGRAL BETWEEN 0 AND , F6.2,
!      1 24H BY ROMBERG INTEGRATION / )
!   201 FORMAT (/ 10H VALUE IS , F10.7, 31H BUT DID NOT MEET TOLERANCE OF
!      1 E14.7)
!   202 FORMAT (/ 10H VALUE IS , F10.7, 2H, / I5,
!      1 49H SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF , E14.7)
!   203 FORMAT (1H ,8F10.7)
!       END
!   data card:  15.0            2.E-7
!
!   * Every Hollerith count was checked against its text, leading blank
!     included: 38 (" VALUE OF SINE INTEGRAL BETWEEN 0 AND "), 24 (" BY ROMBERG
!     INTEGRATION ", with its trailing blank), 10 (" VALUE IS "), 2 (", "), 49
!     (" SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF ") and 31 (" BUT DID NOT
!     MEET TOLERANCE OF" is 30 characters; the 31st is the blank that follows on
!     the card before the continuation, so the text ends with a blank). The
!     emitted records keep these blanks, trailing ones included.
!   * The print chain shows comma and period as the same raised dot; commas are
!     required by syntax in the READ/PRINT lists, the DO statements and between
!     FORMAT items, and the Hollerith 2H, is a comma (the scan's output line
!     reads "VALUE IS  1.6181936,").
!   * "BETWEEN 0 AND": the scan's printer shows digit zero and letter O alike;
!     it is the lower limit of integration, a zero.
!   * The deck-control cards (ZZJOB 5, ZZFORX5, *LIST PRINTER, ZZZZ) are job
!     control, not Fortran, and are dropped; the data card is not echoed.
!   * The tolerance test was checked against the book's table (MILESTONE risk):
!     after halving I = 3 the last two entries of printed row 4 are 1.6181936
!     and 1.6181936, |TRAP(4,4) - TRAP(3,4)| <= 2.E-7, so the run stops with
!     4 rows and K = 10*2**3 = 80 subintervals, as printed. Row 3 (1.6182008,
!     1.6181940) differs by 6.8E-6 and does not stop. Real64, real32, a
!     27-bit chopped binary emulation of the original machine (and 8- or
!     9-digit decimal arithmetic) all stop at row 4 with K = 80.
!
! ERRATA AND CORRECTIONS
! ----------------------
! A. Slips of the OCR text (legacy_code/fortran/chapter_3/integration.f90),
!    corrected from the scan:
!   * SUM = 1. + FCNI(B)          -> SUM = 1. + FCN(B)
!   * DO 20 1 = 1, 8              -> DO 20 I = 1,8
!   * 40 TRAP(II+1, I+1) = TRAP(II+1, I+1) + 1./(4.**II - 1.)*(TRAP(II+1,
!     I+1)) - TRAP(II, 1))        -> 40 TRAP(II+1,I+1) = TRAP(II,I+1) +
!     1./(4.**II - 1.)*(TRAP(II,I+1) - TRAP(II,I))   (continuation card 1)
!   * IF (ABSF(TRAP(II+1, I+1)) - TRAP(II+1, I+1)) - TOL) 50, 50, 20
!                                 -> IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1))- TOL)
!                                    50,50,20
!   * 202 FORMAT (... F10.7s, ...) -> F10.7
!   * 201 FORMAT (/ 10H VALUE IS , F10.7, I5, 31H ...): the scan has NO I5.
!     FORMAT 201 is (/ 10H VALUE IS , F10.7, 31H BUT DID NOT MEET TOLERANCE OF
!     E14.7), which matches its list PRINT 201, TRAP(9,9), TOL exactly. K is not
!     printed on this path (it would hold 10 after DO 60 K = 1,9 anyway, not the
!     2560 subintervals of the last sum); nothing to reproduce.
!   * Minor: ZZJ0B S -> ZZJOB 5, #LIST -> *LIST, x = H -> X = H, BETWEEN O ->
!     BETWEEN 0, (lH ,8F10.7) -> (1H ,8F10.7), and in the output 16077255 ->
!     1.6077255.
! B. Original quirks, kept:
!   * SUM = 1. + FCN(B): the literal 1. is FCN(0), the limit of SIN(X)/X at
!     X = 0, which the statement function cannot evaluate (0/0). The modern code
!     seeds with F0 + F(B): romberg_mod takes the ordinate at 0 as an optional
!     argument f0 and evaluates F(0) without it (the convention of ch03_p01).
!     This driver relies on F(0): preset 1 (functions_mod: f_sinc) returns the
!     limit 1 at X = 0, so the book's seed is reproduced exactly, and presets 2
!     and 3 get their true F(0). The Python adapter passes the book's 1.0 as f0
!     for SIN(X)/X, whose compiled expression cannot be evaluated at 0.
!   * The heading says "VALUE OF SINE INTEGRAL" whatever the integrand: it is
!     book text and is printed for every preset (--verbose names the preset).
!   * E14.7 on the book's machine printed one digit before the decimal point,
!     "2.0000000E-07" (8 significant digits, like a modern ES14.7 or 1PE14.7);
!     a modern E14.7 would print "0.2000000E-06". The driver writes ES14.7.
!   * Table layout: FORMAT 203 (1H ,8F10.7) writes a blank carriage-control
!     character and then F10.7 fields, each with its own leading blank, so a
!     table line starts one column to the right of "VALUE IS". In the scan the
!     table lines start in the same column as "VALUE" (measured on the scan;
!     the "VALUE IS" and "80 SUBINTERVALS" lines match their FORMATs exactly).
!     The driver follows the FORMAT; the catalog's book_output transcribes the
!     scan as printed. Row 9 of the non-convergence table has 9 values: format
!     reversion prints the 9th on a line of its own, as the original did.
!   * Printed digits: the book's table drifts low against IEEE arithmetic by
!     up to 8.6E-7 in line 4 (book 1.6181936; real64 1.6181944 = Si(15);
!     real32 1.6181945). The book's machine chopped its results to a 27-bit
!     binary mantissa (IBM 7090/7094 class, whose FORTRAN II named SINF and
!     ABSF; the same model reproduces ch03_p01's digit): emulating that brings
!     every entry within 3E-7 of the book (1.6181938), not digit for digit,
!     since the machine's SINF is unknown. Computed values are printed like the
!     book's printer did, chopped (RZ) and without a leading zero
!     (book_format_mod: book_fixed). The two input echoes, B (F6.2) and TOL
!     (E14.7), are rounded to nearest instead: they were exact card values in
!     the book, whereas chopping the nearest binary value prints 2.E-7 as
!     1.9999999E-07 and 2.3 as 2.29.
! C. Modernization (behavior-preserving):
!   * The arithmetic IF became an IF block; the branch to 20 CONTINUE continues
!     the DO loop, the branch to 50 leaves it. Every expression keeps the
!     listing's operation order, with explicit parentheses ((X + H) + H,
!     (H/2.)*SUM, (1./(4.**II - 1.))*(...)), so the compiler cannot reassociate
!     it. K = 10.*2.**I is computed in integer arithmetic (exact).
!   * The arithmetic statement function FCN(X) became a procedure argument
!     (abstract interface real_function); --preset N selects it. SINF/ABSF are
!     the generic SIN/ABS.
!   * READ 100 with FORMAT (F10.0, E10.0) (card columns 1-10, 11-20) became a
!     list-directed read, so the card may be typed with any spacing; values
!     must be finite.
!   * After 8 extrapolations without meeting TOL the original printed the 9x9
!     table and FORMAT 201, then CALL EXIT. This is a RESULT with converged=F
!     and exit status 0 (it is the book's documented outcome, not an error).
!   * CALL EXIT became a normal end (exit status 0); input errors stop with 1,
!     or 2 for an ERROR record in --trace mode.
!   * A NaN or infinite function value (impossible as an IEEE special on the
!     original machine) stops the run as an INPUT error, matching InputError on
!     the Python engine.
!   * Real arithmetic is real64 by default; build with -DSINGLE
!     (make build-fortran-single) for real32.
! D. Index of the catalog errata (catalog/ch03_p02_romberg.toml [[errata]],
!    also on content/ch03_p02.md), one line per id, in catalog order:
!   1 fcn-call-slip (ocr_slip): FCNI(B) -> FCN(B). See A.
!   2 do-20-slip (ocr_slip): DO 20 1 = 1, 8 -> DO 20 I = 1,8. See A.
!   3 extrapolation-line (ocr_slip): label 40 reads TRAP(II,I+1) + 1./(4.**II
!     - 1.)*(TRAP(II,I+1) - TRAP(II,I)). See A.
!   4 tolerance-test (ocr_slip): IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1))- TOL)
!     50,50,20, verified against the book table. See A and TRANSCRIPTION.
!   5 format-202-slip (ocr_slip): F10.7s -> F10.7. See A.
!   6 format-201-no-i5 (ocr_slip): the OCR's I5 in FORMAT 201 is not in the
!     scan. See A.
!   7 minor-ocr-slips (ocr_slip): job cards, X, BETWEEN 0, 1H, 1.6077255.
!   8 sinc-seed (original_quirk): SUM = 1. + FCN(B) generalized to
!     F(0) + F(B). See B.
!   9 e-format-digits (original_quirk): E14.7 printed as ES14.7. See B.
!  10 table-row-alignment (original_quirk): FORMAT 203 followed; the scan
!     shows the table one column to the left. See B.
!  11 machine-digits (original_quirk): 27-bit chopped arithmetic of the book's
!     machine; RZ without leading zero for computed values, inputs rounded.
!     See B.
!  12 non-convergence-result (modernization): the 9x9 table and FORMAT 201 are
!     a RESULT with converged=F, exit status 0. See C.
!  13 structured-control-flow (modernization): arithmetic IF, statement
!     function, CALL EXIT, fixed-column READ. See C.
!   Not a catalog id: non-finite function values (INPUT error), see C.
!===============================================================================
program ch03_p02_romberg
   use, intrinsic :: iso_fortran_env, only: input_unit, output_unit, error_unit
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, get_quadrature_preset, preset_expr_len
   use romberg_mod, only: romberg, romberg_result, book_max_halvings, table_size, &
      status_ok, status_not_converged, status_invalid_value
   use book_format_mod, only: book_fixed, book_int, trace_real, trace_int, trace_logical
   implicit none

   !> Fixed-length buffer for command-line arguments.
   integer, parameter :: arg_len = 256
   !> FORMAT 203 prints at most 8 values per line (format reversion for the 9th).
   integer, parameter :: values_per_line = 8

   logical :: trace, verbose, help
   integer :: preset
   character(len=:), allocatable :: arg_error
   procedure(real_function), pointer :: f
   character(len=preset_expr_len) :: expr
   logical :: found
   real(wp) :: b, tol
   integer :: ios
   type(romberg_result) :: res

   call parse_arguments(trace, verbose, help, preset, arg_error)
   if (help) then
      call print_usage(output_unit)
      stop 0, quiet=.true.
   end if
   if (allocated(arg_error)) call input_error(arg_error)

   call get_quadrature_preset(preset, f, expr, found)
   if (.not. found) call input_error("unknown preset " // trace_int(preset) // &
      " (valid presets are 1 2 3)")

   ! READ 100, B, TOL
   read (input_unit, *, iostat=ios) b, tol
   if (ios /= 0) call input_error( &
      "could not read the data card B TOL (two numbers expected on stdin)")
   if (.not. (ieee_is_finite(b) .and. ieee_is_finite(tol))) &
      call input_error("data card values B TOL must be finite numbers")

   res = romberg(f, b, tol)

   if (trace) then
      call write_trace(res)
   else
      call write_book_text(res)
      if (verbose .and. res%status /= status_invalid_value) call write_verbose(res)
   end if

   ! Success (converged or not) ends normally with exit status 0; an invalid function value
   ! is an input error: exit 1 in book mode, 2 with an ERROR record.
   if (res%status == status_invalid_value) then
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
         write (error_unit, '(a)') "ch03_p02_romberg: " // message
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

   !> Input echo `Fw.d` (B in FORMAT 200): rounded to nearest, book style without the
   !> leading zero of a value below one (see ERRATA B, printed digits).
   function input_fixed(x, w, d) result(s)
      real(wp), intent(in) :: x
      integer, intent(in) :: w, d
      character(len=w) :: s
      character(len=32) :: fmt
      integer :: p

      write (fmt, '("(RN,F", I0, ".", I0, ")")') w, d
      write (s, fmt) x
      p = index(s, "0.")
      if (p >= 1) then
         if (p == 1) then
            s = " "//s(2:)
         else if (s(p - 1:p - 1) == " " .or. s(p - 1:p - 1) == "-") then
            s = " "//s(1:p - 1)//s(p + 1:)
         end if
      end if
   end function input_fixed

   !> Input echo `Ew.d` (TOL in FORMATs 201 and 202) as the book printed it: one digit
   !> before the decimal point (`ESw.d`), rounded to nearest (see ERRATA B).
   function input_exp(x, w, d) result(s)
      real(wp), intent(in) :: x
      integer, intent(in) :: w, d
      character(len=w) :: s
      character(len=32) :: fmt

      write (fmt, '("(RN,ES", I0, ".", I0, ")")') w, d
      write (s, fmt) x
   end function input_exp

   !> Message for a NaN or infinite function value (INPUT error; InputError on the Python engine).
   function nan_message(res) result(message)
      type(romberg_result), intent(in) :: res
      character(len=:), allocatable :: message

      message = "F(X) is not a finite number at X = " // trace_real(res%value)
   end function nan_message

   !> The book's line-printer output (records keep their carriage-control blank).
   subroutine write_book_text(res)
      type(romberg_result), intent(in) :: res
      integer :: l, j, first

      if (res%status == status_invalid_value) then
         ! No book message exists: report on stderr like the other input errors.
         write (error_unit, '(a)') "ch03_p02_romberg: " // nan_message(res)
         return
      end if

      ! 200 FORMAT (// 38H VALUE OF SINE INTEGRAL BETWEEN 0 AND , F6.2,
      !    1 24H BY ROMBERG INTEGRATION / )
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VALUE OF SINE INTEGRAL BETWEEN 0 AND " // &
         input_fixed(b, 6, 2) // " BY ROMBERG INTEGRATION "
      write (output_unit, '(a)') ""

      ! 203 FORMAT (1H ,8F10.7): row L = TRAP(1..L, L); 8 values per record.
      do l = 1, res%rows
         first = 1
         do while (first <= l)
            write (output_unit, '(a)', advance="no") " "
            do j = first, min(l, first + values_per_line - 1)
               write (output_unit, '(a)', advance="no") book_fixed(res%trap(j, l), 10, 7)
            end do
            write (output_unit, '(a)') ""
            first = first + values_per_line
         end do
      end do

      write (output_unit, '(a)') ""
      if (res%status == status_ok) then
         ! 202 FORMAT (/ 10H VALUE IS , F10.7, 2H, / I5,
         !    1 49H SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF , E14.7)
         write (output_unit, '(a)') " VALUE IS " // book_fixed(res%value, 10, 7) // ", "
         write (output_unit, '(a)') book_int(res%subintervals, 5) // &
            " SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF " // input_exp(tol, 14, 7)
      else
         ! 201 FORMAT (/ 10H VALUE IS , F10.7, 31H BUT DID NOT MEET TOLERANCE OF
         !    1 E14.7)
         write (output_unit, '(a)') " VALUE IS " // book_fixed(res%value, 10, 7) // &
            " BUT DID NOT MEET TOLERANCE OF " // input_exp(tol, 14, 7)
      end if
   end subroutine write_book_text

   !> --trace: STEP records, TABLE records, then exactly one RESULT or ERROR record.
   subroutine write_trace(res)
      type(romberg_result), intent(in) :: res
      integer :: i, l, j

      do i = 1, size(res%steps)
         write (output_unit, '(a)') "STEP,k=" // trace_int(res%steps(i)%k) // &
            ",panels=" // trace_int(res%steps(i)%panels) // &
            ",h=" // trace_real(res%steps(i)%h) // &
            ",trap=" // trace_real(res%steps(i)%trap) // &
            ",best=" // trace_real(res%steps(i)%best) // &
            ",diff=" // trace_real(res%steps(i)%diff)
      end do

      if (res%status == status_invalid_value) then
         write (output_unit, '(a)') "ERROR,code=INPUT,message=" // nan_message(res)
         return
      end if

      do l = 1, res%rows
         do j = 1, l
            write (output_unit, '(a)') "TABLE,row=" // trace_int(j) // ",col=" // &
               trace_int(l) // ",value=" // trace_real(res%trap(j, l))
         end do
      end do
      write (output_unit, '(a)') "RESULT,value=" // trace_real(res%value) // &
         ",converged=" // trace_logical(res%converged) // &
         ",iterations=" // trace_int(res%iterations) // &
         ",subintervals=" // trace_int(res%subintervals)
   end subroutine write_trace

   !> --verbose: extras after the book text.
   subroutine write_verbose(res)
      type(romberg_result), intent(in) :: res
      integer :: l, j, last

      write (output_unit, '(a)') ""
      write (output_unit, '(a)') " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
      write (output_unit, '(a)') " PRESET " // trace_int(preset) // ": F(X) = " // trim(expr) &
         // " ON [0, B]"
      if (single_precision) then
         write (output_unit, '(a)') " WORKING PRECISION: REAL32 (-DSINGLE BUILD)"
      else
         write (output_unit, '(a)') " WORKING PRECISION: REAL64"
      end if
      write (output_unit, '(a)') " DATA CARD: B = " // trace_real(b) // "  TOL = " // &
         trace_real(tol)
      write (output_unit, '(a)') " SEED F(0) + F(B) = " // trace_real(f(0.0_wp)) // " + " // &
         trace_real(f(b)) // "  (THE BOOK USES 1. + FCN(B))"
      write (output_unit, '(a)') " TABLE TRAP(ROW, COL), ROW = EXTRAPOLATION ORDER, " // &
         "COL = 10*2**(COL-1) SUBINTERVALS:"
      do l = 1, res%rows
         do j = 1, l
            write (output_unit, '(a)') "   TRAP(" // trace_int(j) // "," // trace_int(l) // &
               ") = " // trace_real(res%trap(j, l))
         end do
      end do
      last = size(res%steps)
      if (last > 0) then
         write (output_unit, '(a)') " LAST TEST |TRAP(I+1,I+1) - TRAP(I,I+1)| = " // &
            trace_real(res%steps(last)%diff) // "  WITH I = " // trace_int(res%steps(last)%k)
      end if
      write (output_unit, '(a)') " VALUE = " // trace_real(res%value) // "  CONVERGED = " // &
         trace_logical(res%converged)
      write (output_unit, '(a)') " HALVINGS = " // trace_int(res%iterations) // " OF " // &
         trace_int(book_max_halvings) // "  SUBINTERVALS = " // trace_int(res%subintervals) // &
         "  FUNCTION EVALUATIONS = " // trace_int(res%subintervals + 1)
      if (res%status == status_not_converged) then
         write (output_unit, '(a)') " THE TABLE IS FULL (" // trace_int(table_size) // "x" // &
            trace_int(table_size) // "): TOL WAS NOT MET AFTER 8 EXTRAPOLATIONS"
      end if
   end subroutine write_verbose

   !> --help text.
   subroutine print_usage(unit)
      integer, intent(in) :: unit

      write (unit, '(a)') "usage: ch03_p02_romberg [--trace] [--verbose] [--preset N] " // &
         "[--help] < data-card"
      write (unit, '(a)') ""
      write (unit, '(a)') "Romberg integration of F on [0, B], Gerald Ch. 3 Program 2."
      write (unit, '(a)') "stdin: the book's data card B TOL, list-directed " // &
         "(book card: 15.0 2.E-7)."
      write (unit, '(a)') ""
      write (unit, '(a)') "  --preset N  integrand (default 1):"
      write (unit, '(a)') "                1  SIN(X)/X, limit 1 at X = 0  (book: Si(B))"
      write (unit, '(a)') "                2  EXP(-X**2)"
      write (unit, '(a)') "                3  1/(1+X**2)"
      write (unit, '(a)') "  --trace     machine-readable STEP/TABLE/RESULT/ERROR records " // &
         "only (exit 2 on ERROR)"
      write (unit, '(a)') "  --verbose   extras after the book text (full-precision table)"
      write (unit, '(a)') "  --help      show this text"
      write (unit, '(a)') ""
      write (unit, '(a)') "Without --trace, stdout is the book's line-printer text. A run " // &
         "that does not meet TOL"
      write (unit, '(a)') "after 8 extrapolations prints the 9x9 table and the book's note " // &
         "(exit status 0)."
   end subroutine print_usage

end program ch03_p02_romberg
