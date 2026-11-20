!> test-drive suite for `bisection_mod` (Gerald Ch. 1, Program 1).
!>
!> Covers the book data card (golden 15-row table), every branch of the scan's three
!> arithmetic IFs including the exact-zero and underflow cases, non-convergence and
!> the optional iteration limit.
module test_bisection_suite
   use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_quiet_nan, ieee_positive_inf
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, f_book_bisection, get_bisection_preset, &
      preset_expr_len
   use bisection_mod, only: bisection, bisection_result, book_max_iter, arith_if, &
      status_name, status_ok, status_root_at_endpoint, status_bracket_error, &
      status_zero_product_error, status_non_convergent, status_invalid_value
   use book_format_mod, only: book_fixed
   use testdrive, only: new_unittest, unittest_type, error_type, check, test_failed
   implicit none
   private

   public :: collect_bisection

   !> The book's printed iteration table (scan, p. 24): X with F10.7, F(X) with F10.6.
   character(len=10), parameter :: book_x(15) = [character(len=10) :: &
      "  .5000000", "  .2500000", "  .3750000", "  .4375000", "  .4687500", &
      "  .4531250", "  .4453125", "  .4414062", "  .4433593", "  .4443359", &
      "  .4438476", "  .4436035", "  .4434814", "  .4435424", "  .4435729"]
   character(len=10), parameter :: book_fx(15) = [character(len=10) :: &
      "  -.100576", "   .396117", "   .131719", "   .011255", "  -.045774", &
      "  -.017534", "  -.003207", "   .004006", "   .000395", "  -.001407", &
      "  -.000506", "  -.000055", "   .000170", "   .000057", "   .000001"]
   real(wp), parameter :: book_fx_value(15) = [ &
      -0.100576_wp, 0.396117_wp, 0.131719_wp, 0.011255_wp, -0.045774_wp, &
      -0.017534_wp, -0.003207_wp, 0.004006_wp, 0.000395_wp, -0.001407_wp, &
      -0.000506_wp, -0.000055_wp, 0.000170_wp, 0.000057_wp, 0.000001_wp]

contains

   !> Collect all exported unit tests.
   subroutine collect_bisection(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_result", test_book_card_result), &
         new_unittest("book_card_x_column", test_book_card_x_column), &
         new_unittest("book_card_fx_column", test_book_card_fx_column), &
         new_unittest("step_records", test_step_records), &
         new_unittest("default_max_iter_is_25", test_default_max_iter), &
         new_unittest("bracket_error_positive", test_bracket_error_positive), &
         new_unittest("bracket_error_negative", test_bracket_error_negative), &
         new_unittest("root_at_left_endpoint", test_root_at_left_endpoint), &
         new_unittest("root_at_right_endpoint", test_root_at_right_endpoint), &
         new_unittest("root_at_both_endpoints", test_root_at_both_endpoints), &
         new_unittest("zero_product_underflow_at_start", test_zero_product_start), &
         new_unittest("zero_product_underflow_in_loop", test_zero_product_loop), &
         new_unittest("exact_zero_midpoint_converges", test_exact_zero_midpoint), &
         new_unittest("exact_zero_midpoint_negative_tol", test_exact_zero_negative_tol), &
         new_unittest("non_convergent_25", test_non_convergent_25), &
         new_unittest("non_convergent_max_iter", test_non_convergent_max_iter), &
         new_unittest("nan_at_endpoint_is_invalid", test_nan_endpoint), &
         new_unittest("nan_at_midpoint_is_invalid", test_nan_midpoint), &
         new_unittest("infinity_is_invalid", test_infinite_values), &
         new_unittest("arith_if_branches", test_arith_if), &
         new_unittest("status_names", test_status_names), &
         new_unittest("preset_2_and_3", test_presets) &
      ]
   end subroutine collect_bisection

   ! ---------------------------------------------------------------------------------------
   ! Test functions
   ! ---------------------------------------------------------------------------------------

   !> A scale s with s*s underflowing to zero (1E-200 in real64, about 2E-25 in real32).
   pure real(wp) function tiny_scale()
      tiny_scale = tiny(1.0_wp)**0.65_wp
   end function tiny_scale

   pure function f_identity(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x
   end function f_identity

   pure function f_x_minus_1(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x - 1.0_wp
   end function f_x_minus_1

   pure function f_x_times_x_minus_1(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x*(x - 1.0_wp)
   end function f_x_times_x_minus_1

   pure function f_x_squared_plus_1(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x*x + 1.0_wp
   end function f_x_squared_plus_1

   pure function f_minus_x_squared_minus_1(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = -x*x - 1.0_wp
   end function f_minus_x_squared_minus_1

   pure function f_x_minus_half(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x - 0.5_wp
   end function f_x_minus_half

   pure function f_x_minus_tenth(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x - 0.1_wp
   end function f_x_minus_tenth

   !> Tiny linear function: F(0)*F(1) underflows to zero although neither factor is zero.
   pure function f_tiny_linear(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = tiny_scale()*(x - 0.3_wp)
   end function f_tiny_linear

   !> F(0) = -s, F(1) = 1, F(0.5) = s: the bracket product is -s (nonzero) but
   !> F(X)*F(X1) at the first midpoint is -s*s, which underflows to zero.
   pure function f_tiny_step(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x < 0.25_wp) then
         y = -tiny_scale()
      else if (x > 0.75_wp) then
         y = 1.0_wp
      else
         y = tiny_scale()
      end if
   end function f_tiny_step

   !> NaN at X = 0, -1 at X = 1.
   pure function f_nan_at_zero(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x < 0.5_wp) then
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      else
         y = -1.0_wp
      end if
   end function f_nan_at_zero

   !> +Inf for X < 0, else X - 0.3.
   pure function f_inf_below_zero(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x < 0.0_wp) then
         y = ieee_value(1.0_wp, ieee_positive_inf)
      else
         y = x - 0.3_wp
      end if
   end function f_inf_below_zero

   !> -1 for X <= 0.25, +Inf on (0.25, 0.75), 1 above: brackets [-1,1], Inf at the midpoint 0.5.
   pure function f_inf_above_quarter(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x <= 0.25_wp) then
         y = -1.0_wp
      else if (x < 0.75_wp) then
         y = ieee_value(1.0_wp, ieee_positive_inf)
      else
         y = 1.0_wp
      end if
   end function f_inf_above_quarter

   !> Brackets [0,1] (F(0) = -1, F(1) = 1) but is NaN on [0.3,0.4], hit at the 3rd midpoint.
   pure function f_nan_inside(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x >= 0.3_wp .and. x <= 0.4_wp) then
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      else if (x < 0.35_wp) then
         y = -1.0_wp
      else
         y = 1.0_wp
      end if
   end function f_nan_inside

   ! ---------------------------------------------------------------------------------------
   ! Helpers
   ! ---------------------------------------------------------------------------------------

   pure logical function is_zero(v)
      real(wp), intent(in) :: v
      is_zero = v >= 0.0_wp .and. v <= 0.0_wp
   end function is_zero

   pure logical function same(a, b)
      real(wp), intent(in) :: a, b
      same = a >= b .and. a <= b
   end function same

   !> Common checks on status / converged / iterations / number of steps.
   subroutine check_outcome(error, res, status, converged, iterations)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result), intent(in) :: res
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
      call check(error, size(res%steps), iterations, "number of step records")
   end subroutine check_outcome

   ! ---------------------------------------------------------------------------------------
   ! Book data card 0. 1. 1.E-5
   ! ---------------------------------------------------------------------------------------

   !> Root .4435729 after 15 iterations.
   subroutine test_book_card_result(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_ok, .true., 15)
      if (allocated(error)) return
      call check(error, res%value, 0.4435729_wp, thr=1.0e-6_wp, &
         message="root must be the book's .4435729 within 1E-6")
      if (allocated(error)) return
      ! Midpoints of [0,1] are exact dyadic fractions in both precisions, so the root is
      ! exactly 14535/32768 = 0.443572998046875 in the real64 and the real32 build.
      call check(error, same(res%value, 14535.0_wp/32768.0_wp), &
         "root must be exactly 14535/32768")
      if (allocated(error)) return
      call check(error, book_fixed(res%value, 10, 7), "  .4435729", &
         "root must print as the book's .4435729")
   end subroutine test_book_card_result

   !> The X column of the 15-row table, character for character (both precisions).
   subroutine test_book_card_x_column(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res
      integer :: i
      character(len=8) :: row

      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check(error, size(res%steps), 15)
      if (allocated(error)) return
      do i = 1, 15
         write (row, '(I0)') i
         call check(error, book_fixed(res%steps(i)%x, 10, 7), book_x(i), &
            "X column, row " // trim(row))
         if (allocated(error)) return
      end do
   end subroutine test_book_card_x_column

   !> The F(X) column: every row within 1E-6 of the book; printed digits identical except
   !> the one documented last-digit difference per precision (see the driver's ERRATA E).
   subroutine test_book_card_fx_column(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res
      integer :: i, exception_row
      character(len=10) :: exception_text
      character(len=8) :: row

      if (single_precision) then
         exception_row = 11
         exception_text = "  -.000505"
      else
         exception_row = 15
         exception_text = "   .000000"
      end if

      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check(error, size(res%steps), 15)
      if (allocated(error)) return
      do i = 1, 15
         write (row, '(I0)') i
         call check(error, res%steps(i)%fx, book_fx_value(i), thr=1.0e-6_wp, &
            message="F(X) value, row " // trim(row))
         if (allocated(error)) return
         if (i == exception_row) then
            call check(error, book_fixed(res%steps(i)%fx, 10, 6), exception_text, &
               "documented precision exception, row " // trim(row))
         else
            call check(error, book_fixed(res%steps(i)%fx, 10, 6), book_fx(i), &
               "F(X) column, row " // trim(row))
         end if
         if (allocated(error)) return
      end do
   end subroutine test_book_card_fx_column

   !> STEP records hold the bracket at the start of the iteration and its midpoint.
   subroutine test_step_records(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res
      integer :: i

      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check(error, size(res%steps), 15)
      if (allocated(error)) return
      call check(error, same(res%steps(1)%x1, 0.0_wp) .and. same(res%steps(1)%x2, 1.0_wp) &
         .and. same(res%steps(1)%x, 0.5_wp), "first step must be [0,1] with midpoint 0.5")
      if (allocated(error)) return
      ! F(.5) < 0 = sign of F(1): label 10, X2 = X.
      call check(error, same(res%steps(2)%x1, 0.0_wp) .and. same(res%steps(2)%x2, 0.5_wp), &
         "second step must be [0,0.5]")
      if (allocated(error)) return
      ! F(.25) > 0 = sign of F(0): label 12, X1 = X.
      call check(error, same(res%steps(3)%x1, 0.25_wp) .and. same(res%steps(3)%x2, 0.5_wp), &
         "third step must be [0.25,0.5]")
      if (allocated(error)) return
      do i = 1, size(res%steps)
         call check(error, res%steps(i)%k, i, "step index k")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%x, (res%steps(i)%x1 + res%steps(i)%x2)/2.0_wp), &
            "x must be the midpoint of the step bracket")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%fx, f_book_bisection(res%steps(i)%x)), &
            "fx must be F(x)")
         if (allocated(error)) return
      end do
      call check(error, same(res%fx1, f_book_bisection(0.0_wp)) .and. &
         same(res%fx2, f_book_bisection(1.0_wp)), "fx1/fx2 must be F at the input endpoints")
   end subroutine test_step_records

   !> Omitting max_iter means the book's 25.
   subroutine test_default_max_iter(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      call check(error, book_max_iter, 25)
      if (allocated(error)) return
      res = bisection(f_x_minus_tenth, 0.0_wp, 1.0_wp, 0.0_wp)
      call check_outcome(error, res, status_non_convergent, .false., 25)
   end subroutine test_default_max_iter

   ! ---------------------------------------------------------------------------------------
   ! IF (FX1*FX2) 1, 2, 3
   ! ---------------------------------------------------------------------------------------

   !> Label 3: both endpoint values positive -> message 200.
   subroutine test_bracket_error_positive(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_squared_plus_1, -1.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_bracket_error, .false., 0)
   end subroutine test_bracket_error_positive

   !> Label 3: both endpoint values negative (positive product) -> message 200.
   subroutine test_bracket_error_negative(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_minus_x_squared_minus_1, -1.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_bracket_error, .false., 0)
      if (allocated(error)) return
      ! The book card's bracket reversed is still a valid bracket (no error).
      res = bisection(f_book_bisection, 1.0_wp, 0.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_ok, .true., 15)
   end subroutine test_bracket_error_negative

   !> Labels 2 -> 5: F(X1) = 0 is a root (the original's fall-through to message 202 is
   !> the corrected bug, see ERRATA C).
   subroutine test_root_at_left_endpoint(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_identity, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_root_at_endpoint, .true., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "value must be X1 = 0")
      if (allocated(error)) return
      call check(error, is_zero(res%fx1) .and. .not. is_zero(res%fx2), "fx1 = 0, fx2 /= 0")
      if (allocated(error)) return
      call check(error, book_fixed(res%value, 6, 3), "  .000", "F6.3 of the input root")
   end subroutine test_root_at_left_endpoint

   !> Labels 2 -> 4 -> 7: F(X2) = 0 is a root.
   subroutine test_root_at_right_endpoint(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_minus_1, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_root_at_endpoint, .true., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 1.0_wp), "value must be X2 = 1")
      if (allocated(error)) return
      call check(error, book_fixed(res%value, 6, 3), " 1.000", "F6.3 of the input root")
   end subroutine test_root_at_right_endpoint

   !> Both endpoint values zero: the value is X1 and both fx1 and fx2 are reported zero.
   subroutine test_root_at_both_endpoints(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_times_x_minus_1, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_root_at_endpoint, .true., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "value must be X1")
      if (allocated(error)) return
      call check(error, is_zero(res%fx1) .and. is_zero(res%fx2), "fx1 and fx2 must be zero")
   end subroutine test_root_at_both_endpoints

   !> Labels 2 -> 4 -> 6: FX1*FX2 underflows to zero although FX1 and FX2 are not zero
   !> -> message 202 (ZERO_PRODUCT before the loop, iterations = 0).
   subroutine test_zero_product_start(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_tiny_linear, 0.0_wp, 1.0_wp, 0.0_wp)
      ! Precondition: the product really underflows in this precision.
      call check(error, .not. is_zero(res%fx1) .and. .not. is_zero(res%fx2), &
         "precondition: F(X1) and F(X2) must be nonzero")
      if (allocated(error)) return
      call check(error, res%fx1 < 0.0_wp .and. res%fx2 > 0.0_wp, &
         "precondition: F(X1) and F(X2) must have opposite signs")
      if (allocated(error)) return
      call check(error, arith_if(res%fx1*res%fx2) == 0, &
         "precondition: F(X1)*F(X2) must underflow to zero")
      if (allocated(error)) return
      call check_outcome(error, res, status_zero_product_error, .false., 0)
   end subroutine test_zero_product_start

   ! ---------------------------------------------------------------------------------------
   ! IF (FX*FX1) 10, 11, 12
   ! ---------------------------------------------------------------------------------------

   !> Label 11: F(X)*F(X1) underflows to zero inside the loop -> message 205 "ERROR.".
   subroutine test_zero_product_loop(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_tiny_step, 0.0_wp, 1.0_wp, 0.0_wp)
      call check(error, arith_if(res%fx1*res%fx2) == -1, &
         "precondition: the bracket product must be negative")
      if (allocated(error)) return
      call check_outcome(error, res, status_zero_product_error, .false., 1)
      if (allocated(error)) return
      call check(error, .not. is_zero(res%steps(1)%fx), "precondition: F(0.5) must be nonzero")
      if (allocated(error)) return
      call check(error, arith_if(res%steps(1)%fx*res%fx1) == 0, &
         "precondition: F(X)*F(X1) must underflow to zero")
      if (allocated(error)) return
      call check(error, same(res%value, 0.5_wp), "value must be the midpoint")
   end subroutine test_zero_product_loop

   !> Exact-zero midpoint with TOL >= 0: ABSF(FX) - TOL <= 0 takes label 8 (converged).
   subroutine test_exact_zero_midpoint(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_minus_half, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_ok, .true., 1)
      if (allocated(error)) return
      call check(error, same(res%value, 0.5_wp) .and. is_zero(res%steps(1)%fx), &
         "the exact midpoint root must be found in one iteration")
      if (allocated(error)) return
      ! TOL = 0 still converges on an exact zero (|0| - 0 = 0 -> label 8).
      res = bisection(f_x_minus_half, 0.0_wp, 1.0_wp, 0.0_wp)
      call check_outcome(error, res, status_ok, .true., 1)
   end subroutine test_exact_zero_midpoint

   !> Exact-zero midpoint with a negative TOL: |0| - TOL > 0 goes on to label 9, where
   !> FX*FX1 = 0 takes label 11 ("ERROR.").
   subroutine test_exact_zero_negative_tol(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_minus_half, 0.0_wp, 1.0_wp, -1.0_wp)
      call check_outcome(error, res, status_zero_product_error, .false., 1)
      if (allocated(error)) return
      call check(error, same(res%value, 0.5_wp), "value must be the midpoint")
   end subroutine test_exact_zero_negative_tol

   ! ---------------------------------------------------------------------------------------
   ! DO 30 I = 1, 25 exhausted
   ! ---------------------------------------------------------------------------------------

   !> X - 0.1 with TOL = 0: 0.1 is not a 25-bit dyadic fraction in either precision, so no
   !> midpoint is an exact root -> NON-CONVERGENT IN 25 ITERATIONS.
   subroutine test_non_convergent_25(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_x_minus_tenth, 0.0_wp, 1.0_wp, 0.0_wp, book_max_iter)
      call check_outcome(error, res, status_non_convergent, .false., 25)
      if (allocated(error)) return
      call check(error, same(res%value, res%steps(25)%x), "value must be the last midpoint")
      if (allocated(error)) return
      call check(error, res%value, 0.1_wp, thr=1.0e-7_wp, &
         message="the last midpoint must be within 2**-25 of the root")
   end subroutine test_non_convergent_25

   !> An explicit smaller limit stops earlier (the book card fails after 5 halvings).
   subroutine test_non_convergent_max_iter(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp, max_iter=5)
      call check_outcome(error, res, status_non_convergent, .false., 5)
      if (allocated(error)) return
      call check(error, same(res%value, 0.46875_wp), "value must be the 5th midpoint")
      if (allocated(error)) return
      res = bisection(f_book_bisection, 0.0_wp, 1.0_wp, 1.0e-5_wp, max_iter=0)
      call check_outcome(error, res, status_non_convergent, .false., 0)
   end subroutine test_non_convergent_max_iter

   ! ---------------------------------------------------------------------------------------
   ! NaN function values (INPUT error, no book equivalent)
   ! ---------------------------------------------------------------------------------------

   !> F(X1) is NaN: invalid before the bracket test.
   subroutine test_nan_endpoint(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_nan_at_zero, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "value must be the offending X")
      if (allocated(error)) return
      res = bisection(f_nan_at_zero, 1.0_wp, 0.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
   end subroutine test_nan_endpoint

   !> F(X) is NaN at the third midpoint 0.375: two completed rows, then invalid.
   subroutine test_nan_midpoint(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_nan_inside, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_invalid_value, .false., 2)
      if (allocated(error)) return
      call check(error, same(res%value, 0.375_wp), "value must be the NaN midpoint")
   end subroutine test_nan_midpoint

   !> +Inf at X1 (like EXP(-X) overflowing for X < -709) and at the 2nd midpoint: INPUT error.
   subroutine test_infinite_values(error)
      type(error_type), allocatable, intent(out) :: error
      type(bisection_result) :: res

      res = bisection(f_inf_below_zero, -1.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, same(res%value, -1.0_wp), "value must be the offending X")
      if (allocated(error)) return
      ! midpoints 0 (F = -1, so X1 = 0) then 0.5: F(0.5) = +Inf after one completed row
      res = bisection(f_inf_above_quarter, -1.0_wp, 1.0_wp, 1.0e-5_wp)
      call check_outcome(error, res, status_invalid_value, .false., 1)
      if (allocated(error)) return
      call check(error, same(res%value, 0.5_wp), "value must be the infinite midpoint")
   end subroutine test_infinite_values

   ! ---------------------------------------------------------------------------------------
   ! Helpers of the module
   ! ---------------------------------------------------------------------------------------

   !> Three-way branch: negative, both signed zeros, positive, NaN (positive branch).
   subroutine test_arith_if(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: nan

      call check(error, arith_if(-2.0_wp), -1)
      if (allocated(error)) return
      call check(error, arith_if(0.0_wp), 0)
      if (allocated(error)) return
      call check(error, arith_if(-0.0_wp), 0)
      if (allocated(error)) return
      call check(error, arith_if(tiny(1.0_wp)), 1)
      if (allocated(error)) return
      call check(error, arith_if(-tiny(1.0_wp)), -1)
      if (allocated(error)) return
      nan = ieee_value(1.0_wp, ieee_quiet_nan)
      call check(error, arith_if(nan), 1)
   end subroutine test_arith_if

   !> Status names used in diagnostics.
   subroutine test_status_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_root_at_endpoint), "root_at_endpoint")
      if (allocated(error)) return
      call check(error, status_name(status_bracket_error), "bracket_error")
      if (allocated(error)) return
      call check(error, status_name(status_zero_product_error), "zero_product_error")
      if (allocated(error)) return
      call check(error, status_name(status_non_convergent), "non_convergent")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_value), "invalid_value")
      if (allocated(error)) return
      call check(error, status_name(99), "unknown")
   end subroutine test_status_names

   !> Bisection through the preset table: preset 2 on [1,2], preset 3 on [0,1].
   subroutine test_presets(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(bisection_result) :: res

      call get_bisection_preset(2, f, expr, found)
      if (.not. found) then
         call test_failed(error, "preset 2 missing")
         return
      end if
      res = bisection(f, 1.0_wp, 2.0_wp, 1.0e-5_wp)
      call check(error, res%converged .and. res%status == status_ok, "preset 2 must converge")
      if (allocated(error)) return
      call check(error, abs(f(res%value)) <= 1.0e-5_wp, "|F(root)| <= TOL for preset 2")
      if (allocated(error)) return
      call check(error, res%value, 1.3247179572447460_wp, thr=1.0e-5_wp)
      if (allocated(error)) return

      call get_bisection_preset(3, f, expr, found)
      if (.not. found) then
         call test_failed(error, "preset 3 missing")
         return
      end if
      res = bisection(f, 0.0_wp, 1.0_wp, 1.0e-5_wp)
      call check(error, res%converged .and. res%status == status_ok, "preset 3 must converge")
      if (allocated(error)) return
      call check(error, abs(f(res%value)) <= 1.0e-5_wp, "|F(root)| <= TOL for preset 3")
      if (allocated(error)) return
      call check(error, res%value, 0.7390851332151607_wp, thr=1.0e-5_wp)
   end subroutine test_presets

end module test_bisection_suite
