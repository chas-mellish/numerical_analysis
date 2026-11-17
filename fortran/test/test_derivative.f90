!> test-drive suite for `derivative_mod` (Gerald Ch. 4, Program 1, central differences).
!>
!> Covers the book data card (0.0 0.1) in both precisions -- the ten rows, the accumulated H,
!> the RESULT extras and the printed book rows --, the analytic values at X = 0 (H*SINH(H) and
!> 2*COSH(H)), exact derivatives of a quadratic, the book's order of operations, the optional row
!> count, presets 2 and 3 against the practice answers, and every error branch: H <= 0, X or H
!> not finite, no rows, F(X) / F(X+H) / F(X-H) not finite (at the start and in the middle of a
!> run), DX and DDX overflowing and H*H underflowing to zero.
module test_derivative_suite
   use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_quiet_nan, ieee_positive_inf, &
      ieee_is_finite
   use precision, only: wp, single_precision
   use functions_mod, only: f_book_derivative, f_sin, f_one_plus_log10
   use derivative_mod, only: central_difference, derivative_result, book_rows, h_factor, &
      status_name, status_ok, status_invalid_input, status_invalid_value, &
      status_invalid_estimate, which_none, which_fo, which_fr, which_fl
   use book_format_mod, only: book_e
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_derivative

   !> Book rows (scan, p. 90): DX and DDX as printed.
   real(wp), parameter :: book_dx(10) = [1.0016675e-2_wp, 1.0000150e-4_wp, 9.9995000e-7_wp, &
      1.0000000e-8_wp, 9.9500000e-11_wp, 9.5000000e-13_wp, 5.0000000e-15_wp, 0.0_wp, 0.0_wp, 0.0_wp]
   real(wp), parameter :: book_ddx(10) = [2.0100083_wp, 2.0000999_wp, 2.0000009_wp, 2.0_wp, &
      1.9999999_wp, 1.9999999_wp, 1.9999999_wp, 2.0_wp, 2.0_wp, 2.0_wp]

contains

   !> Collect all exported unit tests.
   subroutine collect_derivative(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_result", test_book_card_result), &
         new_unittest("book_card_rows_vs_scan", test_book_card_rows), &
         new_unittest("book_card_exact_rows", test_book_card_exact_rows), &
         new_unittest("book_card_printed_rows", test_book_card_printed), &
         new_unittest("accumulated_h", test_accumulated_h), &
         new_unittest("analytic_at_zero", test_analytic_at_zero), &
         new_unittest("exact_for_quadratic", test_exact_quadratic), &
         new_unittest("book_order_of_operations", test_order_of_operations), &
         new_unittest("optional_row_count", test_row_count), &
         new_unittest("preset_2_sin", test_preset_sin), &
         new_unittest("preset_3_log_table", test_preset_log), &
         new_unittest("h_zero_is_input_error", test_h_zero), &
         new_unittest("h_negative_is_input_error", test_h_negative), &
         new_unittest("non_finite_x_h_are_input_errors", test_non_finite_inputs), &
         new_unittest("no_rows_is_input_error", test_no_rows), &
         new_unittest("non_finite_fo", test_non_finite_fo), &
         new_unittest("non_finite_fl_first_row", test_non_finite_fl), &
         new_unittest("non_finite_fr_mid_run", test_non_finite_fr_mid_run), &
         new_unittest("dx_overflow", test_dx_overflow), &
         new_unittest("ddx_overflow", test_ddx_overflow), &
         new_unittest("h_squared_underflow", test_h_squared_underflow), &
         new_unittest("status_names", test_status_names) &
      ]
   end subroutine collect_derivative

   ! ---------------------------------------------------------------------------------------
   ! Test functions
   ! ---------------------------------------------------------------------------------------

   !> 3x**2 - 2x + 1: F' = 6x - 2, F'' = 6.
   pure function f_quadratic(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = (3.0_wp*x - 2.0_wp)*x + 1.0_wp
   end function f_quadratic

   !> NaN within 5E-3 of X = 1 (but not at 1): F(X+H) fails in row 3 for X = 1, H = 0.1.
   pure function f_nan_near_one(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (abs(x - 1.0_wp) < 5.0e-3_wp .and. (x > 1.0_wp .or. x < 1.0_wp)) then
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      else
         y = x
      end if
   end function f_nan_near_one

   !> +-HUGE for x of either sign, 0 at 0: FR - FL overflows.
   pure function f_step_huge(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 0.0_wp) then
         y = huge(1.0_wp)
      else if (x < 0.0_wp) then
         y = -huge(1.0_wp)
      else
         y = 0.0_wp
      end if
   end function f_step_huge

   !> HUGE/4 away from 0, 0 at 0: DX = 0, but FR - 2*FO + FL = HUGE/2 overflows over H*H < 1.
   pure function f_spike(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 0.0_wp .or. x < 0.0_wp) then
         y = huge(1.0_wp)/4.0_wp
      else
         y = 0.0_wp
      end if
   end function f_spike

   !> cos(x), a smooth function for the H*H underflow test.
   pure function f_cos(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = cos(x)
   end function f_cos

   ! ---------------------------------------------------------------------------------------
   ! Helpers
   ! ---------------------------------------------------------------------------------------

   pure logical function same(a, b)
      real(wp), intent(in) :: a, b
      same = a >= b .and. a <= b
   end function same

   pure real(wp) function tol(real64_tol, real32_tol)
      real(wp), intent(in) :: real64_tol, real32_tol
      if (single_precision) then
         tol = real32_tol
      else
         tol = real64_tol
      end if
   end function tol

   !> Common checks on status / converged / iterations / number of rows.
   subroutine check_outcome(error, res, status, converged, iterations)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result), intent(in) :: res
      integer, intent(in) :: status, iterations
      logical, intent(in) :: converged

      call check(error, status_name(res%status), status_name(status), "status")
      if (allocated(error)) return
      call check(error, res%converged .eqv. converged, "converged flag")
      if (allocated(error)) return
      call check(error, res%iterations, iterations, "iterations")
      if (allocated(error)) return
      call check(error, allocated(res%steps), "steps must be allocated")
      if (allocated(error)) return
      call check(error, size(res%steps), iterations, "number of rows")
   end subroutine check_outcome

   !> An INPUT error rejected before anything is evaluated.
   subroutine check_rejected(error, res)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result), intent(in) :: res

      call check_outcome(error, res, status_invalid_input, .false., 0)
   end subroutine check_rejected

   ! ---------------------------------------------------------------------------------------
   ! Book data card 0.0 0.1
   ! ---------------------------------------------------------------------------------------

   !> Ten rows; value = DX of the last row; FO = F(0) = 0; the first / last row extras.
   subroutine test_book_card_result(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      integer :: k

      res = central_difference(f_book_derivative, 0.0_wp, 0.1_wp)
      call check_outcome(error, res, status_ok, .true., book_rows)
      if (allocated(error)) return
      call check(error, book_rows, 10, "DO 10 I = 1,10")
      if (allocated(error)) return
      do k = 1, book_rows
         call check(error, res%steps(k)%k, k, "row number")
         if (allocated(error)) return
      end do
      call check(error, same(res%fo, 0.0_wp), "FO = F(0) = 0")
      if (allocated(error)) return
      call check(error, same(res%value, res%steps(10)%dx), "value is DX of the last row")
      if (allocated(error)) return
      call check(error, same(res%first_dx, res%steps(1)%dx), "first_dx")
      if (allocated(error)) return
      call check(error, same(res%first_ddx, res%steps(1)%ddx), "first_ddx")
      if (allocated(error)) return
      call check(error, same(res%last_ddx, res%steps(10)%ddx), "last_ddx")
      if (allocated(error)) return
      call check(error, res%failed_which, which_none, "no failed evaluation")
      if (allocated(error)) return
      ! Catalog [[expected]] first_dx / first_ddx (book digits, real64 and real32 tolerances).
      call check(error, res%first_dx, 1.0016675e-2_wp, thr=tol(1.0e-9_wp, 1.0e-8_wp), &
         message="first DX vs the book's 1.0016675E-02")
      if (allocated(error)) return
      call check(error, res%first_ddx, 2.0100083_wp, thr=tol(1.0e-7_wp, 1.0e-6_wp), &
         message="first DDX vs the book's 2.0100083E+00")
      if (allocated(error)) return
      call check(error, res%last_ddx, 2.0_wp, thr=tol(1.0e-7_wp, 1.0e-6_wp), &
         message="last DDX vs the book's 2.0000000E+00")
   end subroutine test_book_card_result

   !> Every row against the scan within the catalog's per-column tolerances.
   subroutine test_book_card_rows(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      character(len=8) :: row
      integer :: k

      res = central_difference(f_book_derivative, 0.0_wp, 0.1_wp)
      call check(error, size(res%steps), 10)
      if (allocated(error)) return
      do k = 1, 10
         write (row, '(I0)') k
         call check(error, res%steps(k)%h, 0.1_wp**k, thr=tol(1.0e-12_wp, 1.0e-8_wp), &
            message="H of row " // trim(row))
         if (allocated(error)) return
         call check(error, res%steps(k)%dx, book_dx(k), thr=tol(2.0e-9_wp, 1.0e-8_wp), &
            message="DX of row " // trim(row))
         if (allocated(error)) return
         call check(error, res%steps(k)%ddx, book_ddx(k), thr=tol(2.0e-7_wp, 1.0e-6_wp), &
            message="DDX of row " // trim(row))
         if (allocated(error)) return
      end do
   end subroutine test_book_card_rows

   !> The exact values of each build: real64 (catalog real64_value) and real32 (DX exactly 0 in
   !> the last three rows, as on the book's machine).
   subroutine test_book_card_exact_rows(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      real(wp), parameter :: real64_dx(10) = [0.010016675001984412_wp, &
         0.00010000166667499881_wp, 1.0000001666666187e-06_wp, 1.0000000016670753e-08_wp, &
         1.0000000000085782e-10_wp, 9.999999999714196e-13_wp, 9.999999990310974e-15_wp, &
         9.999999948895776e-17_wp, 1.0000000272452008e-18_wp, 1.0000000031710762e-20_wp]
      real(wp), parameter :: real64_ddx(10) = [2.010008336111607_wp, 2.0001000008333363_wp, &
         2.0000010000000836_wp, 2.0000000100000004_wp, 2.0000000001_wp, 2.000000000001_wp, &
         2.0000000000000098_wp, 2.0_wp, 2.0_wp, 2.0_wp]
      character(len=8) :: row
      integer :: k

      res = central_difference(f_book_derivative, 0.0_wp, 0.1_wp)
      if (single_precision) then
         do k = 8, 10
            write (row, '(I0)') k
            call check(error, same(res%steps(k)%dx, 0.0_wp), &
               "real32 DX of row " // trim(row) // " must be exactly 0 (EXP(H) rounds to 1)")
            if (allocated(error)) return
         end do
         call check(error, same(res%value, 0.0_wp), "real32 value (DX of row 10) is 0")
         if (allocated(error)) return
         call check(error, res%steps(1)%dx, 1.00166769698262215e-2_wp, thr=0.0_wp, &
            message="real32 DX of row 1")
         if (allocated(error)) return
         call check(error, res%steps(1)%ddx, 2.01000857353210449_wp, thr=0.0_wp, &
            message="real32 DDX of row 1")
      else
         do k = 1, 10
            write (row, '(I0)') k
            call check(error, res%steps(k)%dx, real64_dx(k), rel=.true., thr=1.0e-15_wp, &
               message="real64 DX of row " // trim(row))
            if (allocated(error)) return
            call check(error, res%steps(k)%ddx, real64_ddx(k), thr=1.0e-15_wp, &
               message="real64 DDX of row " // trim(row))
            if (allocated(error)) return
         end do
         call check(error, res%steps(10)%h, 1.0000000000000006e-10_wp, thr=0.0_wp, &
            message="real64 H of row 10 (accumulated)")
      end if
   end subroutine test_book_card_exact_rows

   !> FORMAT 201 as the book printed it: ES editing, H rounded, DX and DDX chopped, zero E-99.
   subroutine test_book_card_printed(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      character(len=:), allocatable :: line
      character(len=47) :: expected(10)
      character(len=8) :: row
      integer :: k

      if (single_precision) then
         expected = [character(len=47) :: &
            "  1.0E-01      1.0016676E-02      2.0100085E+00", &
            "  1.0E-02      1.0000184E-04      2.0000998E+00", &
            "  1.0E-03      1.0000462E-06      2.0000009E+00", &
            "  1.0E-04      1.0000888E-08      2.0000000E+00", &
            "  1.0E-05      9.9920065E-11      2.0000000E+00", &
            "  1.0E-06      9.7578184E-13      2.0000000E+00", &
            "  1.0E-07      8.4703277E-15      2.0000000E+00", &
            "  1.0E-08      0.0000000E-99      2.0000000E+00", &
            "  1.0E-09      0.0000000E-99      2.0000000E+00", &
            "  1.0E-10      0.0000000E-99      2.0000000E+00"]
      else
         expected = [character(len=47) :: &
            "  1.0E-01      1.0016675E-02      2.0100083E+00", &
            "  1.0E-02      1.0000166E-04      2.0001000E+00", &
            "  1.0E-03      1.0000001E-06      2.0000010E+00", &
            "  1.0E-04      1.0000000E-08      2.0000000E+00", &
            "  1.0E-05      1.0000000E-10      2.0000000E+00", &
            "  1.0E-06      9.9999999E-13      2.0000000E+00", &
            "  1.0E-07      9.9999999E-15      2.0000000E+00", &
            "  1.0E-08      9.9999999E-17      2.0000000E+00", &
            "  1.0E-09      1.0000000E-18      2.0000000E+00", &
            "  1.0E-10      1.0000000E-20      2.0000000E+00"]
      end if
      res = central_difference(f_book_derivative, 0.0_wp, 0.1_wp)
      do k = 1, 10
         write (row, '(I0)') k
         line = " " // book_e(res%steps(k)%h, 8, 1, "RN") // repeat(" ", 5) // &
            book_e(res%steps(k)%dx, 14, 7, "RZ") // repeat(" ", 5) // &
            book_e(res%steps(k)%ddx, 14, 7, "RZ")
         call check(error, line, trim(expected(k)), "printed row " // trim(row))
         if (allocated(error)) return
      end do
   end subroutine test_book_card_printed

   !> 10 H = 0.1*H: every H is exactly h_factor times the one before (accumulated).
   subroutine test_accumulated_h(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      integer :: k

      call check(error, same(h_factor, 0.1_wp), "h_factor is the literal 0.1 of kind wp")
      if (allocated(error)) return
      res = central_difference(f_sin, 0.3_wp, 0.7_wp)
      call check(error, same(res%steps(1)%h, 0.7_wp), "row 1 uses the card's H")
      if (allocated(error)) return
      do k = 2, size(res%steps)
         call check(error, same(res%steps(k)%h, h_factor*res%steps(k - 1)%h), &
            "H = 0.1*H accumulated")
         if (allocated(error)) return
      end do
   end subroutine test_accumulated_h

   !> At X = 0 the book function gives DX = H*SINH(H) and DDX = 2*COSH(H) (rows 1-3, where the
   !> truncation error dominates the round-off).
   subroutine test_analytic_at_zero(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      real(wp) :: h
      integer :: k

      res = central_difference(f_book_derivative, 0.0_wp, 0.1_wp)
      do k = 1, 3
         h = res%steps(k)%h
         call check(error, res%steps(k)%dx, h*sinh(h), rel=.true., &
            thr=tol(1.0e-9_wp, 1.0e-3_wp), message="DX = H*SINH(H)")
         if (allocated(error)) return
         call check(error, res%steps(k)%ddx, 2.0_wp*cosh(h), thr=tol(1.0e-12_wp, 1.0e-6_wp), &
            message="DDX = 2*COSH(H)")
         if (allocated(error)) return
      end do
   end subroutine test_analytic_at_zero

   !> Central differences are exact for a quadratic: F'(0.5) = 1 and F'' = 6. With X = 0.5,
   !> H = 0.5 every operand of row 1 is exact; rows 2 and 3 agree to round-off
   !> (which grows like eps/H**2 for DDX).
   subroutine test_exact_quadratic(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      integer :: k

      res = central_difference(f_quadratic, 0.5_wp, 0.5_wp)
      call check_outcome(error, res, status_ok, .true., 10)
      if (allocated(error)) return
      call check(error, same(res%fo, 0.75_wp), "FO = F(0.5) = 0.75")
      if (allocated(error)) return
      call check(error, same(res%first_dx, 1.0_wp), "row 1 DX exactly F'(0.5) = 1")
      if (allocated(error)) return
      call check(error, same(res%first_ddx, 6.0_wp), "row 1 DDX exactly F'' = 6")
      if (allocated(error)) return
      do k = 2, 3
         call check(error, res%steps(k)%dx, 1.0_wp, thr=tol(1.0e-12_wp, 1.0e-4_wp), &
            message="DX of a quadratic has no truncation error")
         if (allocated(error)) return
         call check(error, res%steps(k)%ddx, 6.0_wp, thr=tol(1.0e-9_wp, 1.0e-2_wp), &
            message="DDX of a quadratic has no truncation error")
         if (allocated(error)) return
      end do
   end subroutine test_exact_quadratic

   !> The book's grouping: DX = (FR - FL)/(2*H), DDX = ((FR - 2*FO) + FL)/(H*H), bit for bit.
   subroutine test_order_of_operations(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      real(wp) :: x, h, fo, fr, fl
      integer :: k

      x = 1.3_wp
      res = central_difference(f_sin, x, 0.25_wp)
      fo = sin(x)
      call check(error, same(res%fo, fo), "FO = F(X)")
      if (allocated(error)) return
      do k = 1, size(res%steps)
         h = res%steps(k)%h
         fr = sin(x + h)
         fl = sin(x - h)
         call check(error, same(res%steps(k)%dx, (fr - fl)/(2.0_wp*h)), "DX grouping")
         if (allocated(error)) return
         call check(error, same(res%steps(k)%ddx, ((fr - 2.0_wp*fo) + fl)/(h*h)), &
            "DDX grouping")
         if (allocated(error)) return
      end do
   end subroutine test_order_of_operations

   !> n_rows is optional (default book_rows = 10).
   subroutine test_row_count(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res, full

      res = central_difference(f_sin, 1.0_wp, 0.1_wp, 3)
      call check_outcome(error, res, status_ok, .true., 3)
      if (allocated(error)) return
      full = central_difference(f_sin, 1.0_wp, 0.1_wp)
      call check(error, same(res%value, full%steps(3)%dx), "value is DX of row 3")
      if (allocated(error)) return
      call check(error, same(res%last_ddx, full%steps(3)%ddx), "last_ddx is DDX of row 3")
      if (allocated(error)) return
      res = central_difference(f_sin, 1.0_wp, 0.1_wp, 1)
      call check_outcome(error, res, status_ok, .true., 1)
      if (allocated(error)) return
      call check(error, same(res%first_dx, res%value), "one row: first and last DX agree")
   end subroutine test_row_count

   !> Preset 2, sin at X = 1, H = 0.1: practice answer first_ddx = -0.8407699926874178.
   subroutine test_preset_sin(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_sin, 1.0_wp, 0.1_wp)
      call check_outcome(error, res, status_ok, .true., 10)
      if (allocated(error)) return
      call check(error, res%first_ddx, -0.8407699926874178_wp, thr=tol(1.0e-12_wp, 5.0e-5_wp), &
         message="first DDX = 2(cos(H) - 1)/H**2 * sin(1)")
      if (allocated(error)) return
      call check(error, res%first_dx, sin(0.1_wp)/0.1_wp*cos(1.0_wp), &
         thr=tol(1.0e-12_wp, 1.0e-5_wp), message="first DX = sin(H)/H * cos(1)")
      if (allocated(error)) return
      call check(error, res%steps(4)%dx, cos(1.0_wp), thr=tol(1.0e-8_wp, 1.0e-2_wp), &
         message="DX tends to cos(1)")
   end subroutine test_preset_sin

   !> Preset 3, 1 + log10(x) at X = 0.19, H = 0.02 (p. 91 problem 2): practice answers.
   subroutine test_preset_log(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_one_plus_log10, 0.19_wp, 0.02_wp)
      call check_outcome(error, res, status_ok, .true., 10)
      if (allocated(error)) return
      call check(error, res%first_dx, 2.2942593338911355_wp, thr=tol(1.0e-12_wp, 1.0e-5_wp), &
         message="(F(0.21) - F(0.17))/0.04")
      if (allocated(error)) return
      if (.not. single_precision) then
         call check(error, res%value, 2.2857604697890097_wp, thr=1.0e-12_wp, &
            message="DX of the last row (H = 2E-11)")
      end if
   end subroutine test_preset_log

   ! ---------------------------------------------------------------------------------------
   ! Error branches
   ! ---------------------------------------------------------------------------------------

   !> H = 0 (the book divides by zero) is rejected before F is evaluated.
   subroutine test_h_zero(error)
      type(error_type), allocatable, intent(out) :: error

      call check_rejected(error, central_difference(f_book_derivative, 0.0_wp, 0.0_wp))
   end subroutine test_h_zero

   !> A negative H is rejected (it would mirror the rows).
   subroutine test_h_negative(error)
      type(error_type), allocatable, intent(out) :: error

      call check_rejected(error, central_difference(f_book_derivative, 0.0_wp, -0.1_wp))
   end subroutine test_h_negative

   !> X or H NaN or infinite.
   subroutine test_non_finite_inputs(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: nan, inf

      nan = ieee_value(1.0_wp, ieee_quiet_nan)
      inf = ieee_value(1.0_wp, ieee_positive_inf)
      call check_rejected(error, central_difference(f_sin, nan, 0.1_wp))
      if (allocated(error)) return
      call check_rejected(error, central_difference(f_sin, inf, 0.1_wp))
      if (allocated(error)) return
      call check_rejected(error, central_difference(f_sin, 0.0_wp, nan))
      if (allocated(error)) return
      call check_rejected(error, central_difference(f_sin, 0.0_wp, inf))
   end subroutine test_non_finite_inputs

   !> n_rows < 1.
   subroutine test_no_rows(error)
      type(error_type), allocatable, intent(out) :: error

      call check_rejected(error, central_difference(f_sin, 0.0_wp, 0.1_wp, 0))
   end subroutine test_no_rows

   !> FO = F(X) not finite: 1 + LOG10(0) = -Inf (preset 3 with the book card). No rows.
   subroutine test_non_finite_fo(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_one_plus_log10, 0.0_wp, 0.1_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, res%failed_which, which_fo, "FO failed")
      if (allocated(error)) return
      call check(error, same(res%failed_at, 0.0_wp), "at X")
   end subroutine test_non_finite_fo

   !> F(X - H) not finite in row 1: LOG10(0.05 - 0.1) is NaN.
   subroutine test_non_finite_fl(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_one_plus_log10, 0.05_wp, 0.1_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, res%failed_which, which_fl, "F(X-H) failed")
      if (allocated(error)) return
      call check(error, same(res%failed_at, 0.05_wp - 0.1_wp), "at X - H")
   end subroutine test_non_finite_fl

   !> F(X + H) not finite in row 3: the two rows before are kept.
   subroutine test_non_finite_fr_mid_run(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_nan_near_one, 1.0_wp, 0.1_wp)
      call check_outcome(error, res, status_invalid_value, .false., 2)
      if (allocated(error)) return
      call check(error, res%failed_which, which_fr, "F(X+H) failed")
      if (allocated(error)) return
      call check(error, res%steps(2)%k, 2, "rows 1 and 2 kept")
      if (allocated(error)) return
      call check(error, same(res%failed_at, 1.0_wp + res%steps(2)%h*h_factor), "at X + H")
      if (allocated(error)) return
      call check(error, res%steps(1)%dx, 1.0_wp, thr=tol(1.0e-14_wp, 1.0e-6_wp), &
         message="DX of F(X) = X in row 1")
   end subroutine test_non_finite_fr_mid_run

   !> FR - FL = 2*HUGE overflows: DX is not finite in row 1.
   subroutine test_dx_overflow(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_step_huge, 0.0_wp, 1.0_wp)
      call check_outcome(error, res, status_invalid_estimate, .false., 0)
      if (allocated(error)) return
      call check(error, res%failed_row, 1, "row 1")
      if (allocated(error)) return
      call check(error, same(res%failed_at, 1.0_wp), "at H of row 1")
   end subroutine test_dx_overflow

   !> DX = 0 is finite but DDX = (HUGE/2)/H**2 overflows as soon as H < 1.
   subroutine test_ddx_overflow(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res

      res = central_difference(f_spike, 0.0_wp, 2.0_wp)
      call check_outcome(error, res, status_invalid_estimate, .false., 1)
      if (allocated(error)) return
      call check(error, ieee_is_finite(res%steps(1)%ddx), "row 1 (H = 2) is finite")
      if (allocated(error)) return
      call check(error, same(res%steps(1)%dx, 0.0_wp), "DX of the symmetric spike is 0")
      if (allocated(error)) return
      call check(error, res%failed_row, 2, "row 2 (H = 0.2) overflows")
   end subroutine test_ddx_overflow

   !> H*H underflows to 0 (tested before the division): the rows with a subnormal H*H are kept.
   !> real64: H = 2**-532 (1.1E-160), then 1.1E-161 give H*H ~ 1.2E-320, 1.2E-322 (subnormal);
   !> row 3 (1.2E-324, below half the smallest subnormal) is 0.
   !> real32: H = 2**-66 (1.4E-20) .. 1.4E-22 give H*H down to 1.8E-44; row 4 (1.8E-46) is 0.
   !> (scale() with a variable exponent avoids a constant that underflows in the other precision.)
   subroutine test_h_squared_underflow(error)
      type(error_type), allocatable, intent(out) :: error
      type(derivative_result) :: res
      integer :: failed_row, exponent
      real(wp) :: h

      if (single_precision) then
         exponent = -66
         failed_row = 4
      else
         exponent = -532
         failed_row = 3
      end if
      h = scale(1.0_wp, exponent)
      res = central_difference(f_cos, 0.0_wp, h)
      call check_outcome(error, res, status_invalid_estimate, .false., failed_row - 1)
      if (allocated(error)) return
      call check(error, res%failed_row, failed_row, "row whose H*H underflows")
      if (allocated(error)) return
      call check(error, res%failed_at*res%failed_at <= 0.0_wp, "H*H of the failed row is 0")
      if (allocated(error)) return
      call check(error, res%steps(failed_row - 1)%h**2 > 0.0_wp, "H*H of the last row kept > 0")
   end subroutine test_h_squared_underflow

   !> status_name covers every code.
   subroutine test_status_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_input), "invalid_input")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_value), "invalid_value")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_estimate), "invalid_estimate")
      if (allocated(error)) return
      call check(error, status_name(99), "unknown")
   end subroutine test_status_names

end module test_derivative_suite
