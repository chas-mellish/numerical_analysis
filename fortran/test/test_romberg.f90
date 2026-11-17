!> test-drive suite for `romberg_mod` (Gerald Ch. 3, Program 2).
!>
!> Covers the book data card (golden 4-row table, value and 80 subintervals), the scan's
!> tolerance test including its zero branch, the extrapolation formula, the STEP records,
!> non-convergence after 8 extrapolations (a result, not an error), the F(0) + F(B) seed,
!> the presets, exactness for low-degree polynomials and non-finite function values.
module test_romberg_suite
   use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_quiet_nan
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, f_sinc, f_gauss, f_runge, get_quadrature_preset, &
      preset_expr_len
   use romberg_mod, only: romberg, romberg_result, status_name, book_max_halvings, &
      book_first_panels, table_size, status_ok, status_not_converged, status_invalid_value
   use book_format_mod, only: book_fixed
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_romberg

   !> The book's printed table (scan, p. 74): printed row L holds TRAP(1..L, L).
   real(wp), parameter :: book_table(4, 4) = reshape([ &
      1.6077255_wp, 0.0_wp, 0.0_wp, 0.0_wp, &
      1.6156591_wp, 1.6183036_wp, 0.0_wp, 0.0_wp, &
      1.6175654_wp, 1.6182008_wp, 1.6181940_wp, 0.0_wp, &
      1.6180369_wp, 1.6181940_wp, 1.6181936_wp, 1.6181936_wp], [4, 4])
   !> Book value 1.6181936 and the true Si(15) = 1.6181944437083...
   real(wp), parameter :: book_value = 1.6181936_wp
   real(wp), parameter :: si_15 = 1.61819444370837_wp
   !> Golden tolerance against the book digits (DD4): the book's decimal machine differs
   !> from IEEE arithmetic by up to 8.6E-7 in row 4, in real64 and in real32 alike.
   real(wp), parameter :: tol_book = 1.0e-6_wp
   real(wp), parameter :: pi = 3.14159265358979323846_wp

contains

   !> Collect all exported unit tests.
   subroutine collect_romberg(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_result", test_book_card_result), &
         new_unittest("book_card_table", test_book_card_table), &
         new_unittest("book_card_printed_value", test_book_card_printed_value), &
         new_unittest("book_card_tolerance_test", test_book_card_tolerance_test), &
         new_unittest("step_records", test_step_records), &
         new_unittest("extrapolation_formula", test_extrapolation_formula), &
         new_unittest("trapezoid_column", test_trapezoid_column), &
         new_unittest("zero_branch_converges", test_zero_branch), &
         new_unittest("non_convergence_after_8", test_non_convergence), &
         new_unittest("non_convergence_negative_tol", test_negative_tol), &
         new_unittest("non_convergence_preset_3", test_non_convergence_preset), &
         new_unittest("seed_is_f0_plus_fb", test_seed), &
         new_unittest("explicit_f0_book_seed", test_explicit_f0), &
         new_unittest("zero_upper_limit", test_zero_upper_limit), &
         new_unittest("cubic_exact_after_extrapolation", test_cubic_exact), &
         new_unittest("quintic_exact_after_two_extrapolations", test_quintic_exact), &
         new_unittest("preset_1_sinc", test_preset_sinc), &
         new_unittest("preset_2_gauss", test_preset_gauss), &
         new_unittest("preset_3_runge", test_preset_runge), &
         new_unittest("nan_at_zero_is_invalid", test_nan_at_zero), &
         new_unittest("nan_after_halvings_is_invalid", test_nan_inside), &
         new_unittest("status_names", test_status_names) &
      ]
   end subroutine collect_romberg

   ! ---------------------------------------------------------------------------------------
   ! Test integrands
   ! ---------------------------------------------------------------------------------------

   pure function f_one(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = 1.0_wp + 0.0_wp*x
   end function f_one

   pure function f_linear(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = 3.0_wp*x + 1.0_wp
   end function f_linear

   pure function f_cubic(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x**3 - 2.0_wp*x**2 + 0.5_wp*x + 1.0_wp
   end function f_cubic

   pure function f_quintic(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x**5 - x**4 + 2.0_wp*x
   end function f_quintic

   !> sqrt(x): its derivative is singular at 0, so the error expansion that Richardson
   !> extrapolation assumes does not hold and the table converges slowly.
   pure function f_sqrt(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = sqrt(x)
   end function f_sqrt

   !> NaN at X = 0, 1 elsewhere.
   pure function f_nan_at_zero(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 0.0_wp) then
         y = 1.0_wp
      else
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      end if
   end function f_nan_at_zero

   !> NaN on (0.24, 0.26) only. With B = 10 the grid points are multiples of 1/(2**k) and
   !> the first one inside is X = 0.25, reached at halving 2 (H = 0.25).
   pure function f_nan_near_quarter(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 0.24_wp .and. x < 0.26_wp) then
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      else
         y = cos(x)
      end if
   end function f_nan_near_quarter

   ! ---------------------------------------------------------------------------------------
   ! Helpers
   ! ---------------------------------------------------------------------------------------

   pure logical function same(a, b)
      real(wp), intent(in) :: a, b
      same = a >= b .and. a <= b
   end function same

   !> Common checks on status / converged / iterations / rows / subintervals / steps.
   subroutine check_outcome(error, res, status, converged, iterations)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result), intent(in) :: res
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
      call check(error, size(res%steps), iterations, "one step record per halving")
      if (allocated(error)) return
      if (status == status_invalid_value) return
      call check(error, res%rows, iterations + 1, "printed rows")
      if (allocated(error)) return
      call check(error, res%subintervals, book_first_panels*2**iterations, "subintervals")
   end subroutine check_outcome

   ! ---------------------------------------------------------------------------------------
   ! Book data card 15.0 2.E-7
   ! ---------------------------------------------------------------------------------------

   !> 4 rows, 80 subintervals, value 1.6181936 (book) / Si(15) (real64).
   subroutine test_book_card_result(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      call check_outcome(error, res, status_ok, .true., 3)
      if (allocated(error)) return
      call check(error, res%subintervals, 80, "80 SUBINTERVALS WERE REQUIRED")
      if (allocated(error)) return
      call check(error, res%value, book_value, thr=tol_book, &
         message="value must be the book's 1.6181936 within 1E-6")
      if (allocated(error)) return
      call check(error, same(res%value, res%trap(4, 4)), "value must be TRAP(4,4)")
      if (allocated(error)) return
      if (.not. single_precision) then
         call check(error, res%value, si_15, thr=1.0e-9_wp, &
            message="real64 value must be Si(15) = 1.6181944 within 1E-9")
      end if
   end subroutine test_book_card_result

   !> Every printed table entry within 1E-6 of the book; nothing outside the triangle.
   subroutine test_book_card_table(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      integer :: l, j
      character(len=16) :: cell

      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      call check(error, res%rows, 4, "4 printed rows")
      if (allocated(error)) return
      do l = 1, size(book_table, 2)
         do j = 1, l
            write (cell, '("TRAP(", I0, ",", I0, ")")') j, l
            call check(error, res%trap(j, l), book_table(j, l), thr=tol_book, &
               message=trim(cell) // " must match the book within 1E-6")
            if (allocated(error)) return
         end do
      end do
      do l = 1, table_size
         do j = 1, table_size
            if (l <= 4 .and. j <= l) cycle
            write (cell, '("TRAP(", I0, ",", I0, ")")') j, l
            call check(error, same(res%trap(j, l), 0.0_wp), trim(cell) // " must not be computed")
            if (allocated(error)) return
         end do
      end do
   end subroutine test_book_card_table

   !> The final value prints as 1.6181944 in both precisions (book: 1.6181936, see ERRATA B).
   subroutine test_book_card_printed_value(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      call check(error, book_fixed(res%value, 10, 7), " 1.6181944", &
         "value prints as 1.6181944 (chopped)")
   end subroutine test_book_card_printed_value

   !> IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1)) - TOL) 50,50,20: row 3 fails, row 4 passes.
   subroutine test_book_card_tolerance_test(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      call check(error, size(res%steps), 3)
      if (allocated(error)) return
      call check(error, res%steps(1)%diff > 2.0e-7_wp, "halving 1 must not meet TOL")
      if (allocated(error)) return
      ! Book row 3: |1.6181940 - 1.6182008| = 6.8E-6
      call check(error, res%steps(2)%diff, 6.85e-6_wp, thr=1.0e-7_wp, &
         message="halving 2 difference is about 6.8E-6 (book row 3)")
      if (allocated(error)) return
      call check(error, res%steps(2)%diff > 2.0e-7_wp, "halving 2 must not meet TOL")
      if (allocated(error)) return
      ! Book row 4: 1.6181936 and 1.6181936
      call check(error, res%steps(3)%diff <= 2.0e-7_wp, "halving 3 meets TOL (book row 4)")
      if (allocated(error)) return
      call check(error, same(res%steps(3)%diff, abs(res%trap(4, 4) - res%trap(3, 4))), &
         "diff must be |TRAP(I+1,I+1) - TRAP(I,I+1)|")
   end subroutine test_book_card_tolerance_test

   !> STEP records: k, panels = 10*2**k, h = B/10/2**k, trap = TRAP(1,k+1), best = diagonal.
   subroutine test_step_records(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      integer :: i

      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      do i = 1, size(res%steps)
         call check(error, res%steps(i)%k, i, "step index k")
         if (allocated(error)) return
         call check(error, res%steps(i)%panels, 10*2**i, "panels")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%h, 1.5_wp/2.0_wp**i), "h = 1.5/2**k")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%trap, res%trap(1, i + 1)), "trap = TRAP(1,k+1)")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%best, res%trap(i + 1, i + 1)), &
            "best = TRAP(k+1,k+1)")
         if (allocated(error)) return
         call check(error, same(res%steps(i)%diff, &
            abs(res%trap(i + 1, i + 1) - res%trap(i, i + 1))), "diff")
         if (allocated(error)) return
      end do
   end subroutine test_step_records

   !> Label 40 exactly as in the scan: TRAP(II,I+1) + 1./(4.**II-1.)*(TRAP(II,I+1)-TRAP(II,I)).
   subroutine test_extrapolation_formula(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      integer :: l, ii
      real(wp) :: expected
      character(len=16) :: cell

      res = romberg(f_sinc, 15.0_wp, 1.0e-30_wp)
      do l = 2, res%rows
         do ii = 1, l - 1
            expected = res%trap(ii, l) + (1.0_wp/(4.0_wp**ii - 1.0_wp))* &
               (res%trap(ii, l) - res%trap(ii, l - 1))
            write (cell, '("TRAP(", I0, ",", I0, ")")') ii + 1, l
            call check(error, same(res%trap(ii + 1, l), expected), trim(cell))
            if (allocated(error)) return
         end do
      end do
   end subroutine test_extrapolation_formula

   !> Row 1 is the composite trapezoidal rule with 10*2**(L-1) subintervals.
   subroutine test_trapezoid_column(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      real(wp) :: h, s
      integer :: l, n, i

      ! A negative TOL can never be met, so all 9 columns are computed.
      res = romberg(f_gauss, 2.0_wp, -1.0_wp)
      call check(error, res%rows, table_size, "negative TOL fills the table")
      if (allocated(error)) return
      do l = 1, res%rows
         n = 10*2**(l - 1)
         h = 2.0_wp/real(n, wp)
         s = (f_gauss(0.0_wp) + f_gauss(2.0_wp))/2.0_wp
         do i = 1, n - 1
            s = s + f_gauss(real(i, wp)*h)
         end do
         call check(error, res%trap(1, l), h*s, thr=100.0_wp*epsilon(1.0_wp), &
            message="TRAP(1,L) must be the trapezoidal rule")
         if (allocated(error)) return
      end do
   end subroutine test_trapezoid_column

   !> A zero difference with TOL = 0 takes the zero branch (50): converged at halving 1.
   subroutine test_zero_branch(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_one, 4.0_wp, 0.0_wp)
      call check_outcome(error, res, status_ok, .true., 1)
      if (allocated(error)) return
      call check(error, same(res%steps(1)%diff, 0.0_wp), "constant integrand: diff = 0")
      if (allocated(error)) return
      call check(error, same(res%value, 4.0_wp), "integral of 1 on [0,4] is exactly 4")
   end subroutine test_zero_branch

   !> 8 extrapolations without meeting TOL: a result with converged = F, the full 9x9 table,
   !> value TRAP(9,9), 2560 subintervals (book FORMAT 201 path).
   subroutine test_non_convergence(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_sqrt, 1.0_wp, 1.0e-14_wp)
      if (single_precision) then
         ! Precision effect: in real32 the extrapolated values stagnate and the difference
         ! becomes exactly zero (halving 5), which meets any TOL >= 0. The non-convergence
         ! path itself is covered in real32 by non_convergence_negative_tol.
         call check(error, res%converged, "real32 meets TOL on a zero difference")
         if (allocated(error)) return
         call check(error, same(res%steps(res%iterations)%diff, 0.0_wp), "zero difference")
         return
      end if
      call check_outcome(error, res, status_not_converged, .false., book_max_halvings)
      if (allocated(error)) return
      call check(error, res%rows, table_size, "9 printed rows")
      if (allocated(error)) return
      call check(error, res%subintervals, 2560, "MAXIMUM NUMBER OF SUBINTERVALS ... IS 2560")
      if (allocated(error)) return
      call check(error, same(res%value, res%trap(9, 9)), "value must be TRAP(9,9)")
      if (allocated(error)) return
      call check(error, res%steps(book_max_halvings)%diff > 1.0e-14_wp, "TOL not met")
      if (allocated(error)) return
      call check(error, res%value, 2.0_wp/3.0_wp, thr=1.0e-4_wp, &
         message="still a usable estimate of 2/3")
   end subroutine test_non_convergence

   !> A negative TOL can never be met (|diff| - TOL > 0 always).
   subroutine test_negative_tol(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_one, 1.0_wp, -1.0_wp)
      call check_outcome(error, res, status_not_converged, .false., book_max_halvings)
      if (allocated(error)) return
      call check(error, same(res%value, 1.0_wp), "value is still the exact integral")
   end subroutine test_negative_tol

   !> Preset 3 with B = 100, TOL = 1.E-13 does not converge in real64 (the catalog's
   !> practice question); real32 stops earlier on an exactly zero difference.
   subroutine test_non_convergence_preset(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_runge, 100.0_wp, 1.0e-13_wp)
      if (single_precision) then
         call check(error, res%converged, "real32 meets TOL on a zero difference")
         return
      end if
      call check_outcome(error, res, status_not_converged, .false., book_max_halvings)
      if (allocated(error)) return
      call check(error, res%value, atan(100.0_wp), thr=1.0e-6_wp, &
         message="value close to atan(100)")
   end subroutine test_non_convergence_preset

   !> SUM is seeded with F(0) + F(B): exact for linear integrands from the first column.
   subroutine test_seed(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      ! integral of 3x + 1 on [0, 2] = 6 + 2 = 8; F(0) = 1 must be included
      res = romberg(f_linear, 2.0_wp, 1.0e-12_wp)
      call check(error, res%trap(1, 1), 8.0_wp, thr=10.0_wp*epsilon(1.0_wp), &
         message="TRAP(1,1) of a linear integrand is exact")
      if (allocated(error)) return
      call check(error, res%value, 8.0_wp, thr=10.0_wp*epsilon(1.0_wp), &
         message="integral of 3x + 1 on [0,2]")
      if (allocated(error)) return
      ! the book's seed 1. + FCN(B)
      call check(error, same(f_sinc(0.0_wp), 1.0_wp), "preset 1 is 1 at X = 0 (book seed)")
   end subroutine test_seed

   !> The optional f0: the book's seed 1. gives the same run as F(0) of the preset, it lets an
   !> integrand that is undefined at 0 be integrated, and a non-finite f0 is invalid.
   subroutine test_explicit_f0(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res, ref
      integer :: l, j

      ref = romberg(f_sinc, 15.0_wp, 2.0e-7_wp)
      res = romberg(f_sinc, 15.0_wp, 2.0e-7_wp, f0=1.0_wp)
      call check(error, res%rows, ref%rows, "same rows with the book seed 1.")
      if (allocated(error)) return
      do l = 1, res%rows
         do j = 1, l
            call check(error, same(res%trap(j, l), ref%trap(j, l)), "same table, bit for bit")
            if (allocated(error)) return
         end do
      end do
      ! F is NaN at 0 only; with f0 = 1 the integral of 1 on [0, 2] is exact.
      res = romberg(f_nan_at_zero, 2.0_wp, 1.0e-10_wp, f0=1.0_wp)
      call check(error, res%converged, "f0 replaces F(0)")
      if (allocated(error)) return
      call check(error, same(res%value, 2.0_wp), "integral of 1 on [0,2]")
      if (allocated(error)) return
      res = romberg(f_one, 2.0_wp, 1.0e-10_wp, f0=ieee_value(1.0_wp, ieee_quiet_nan))
      call check_outcome(error, res, status_invalid_value, .false., 0)
   end subroutine test_explicit_f0

   !> B = 0: H = 0, every sum is zero; the first test has a zero difference.
   subroutine test_zero_upper_limit(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_sinc, 0.0_wp, 2.0e-7_wp)
      call check_outcome(error, res, status_ok, .true., 1)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "integral over [0,0] is 0")
   end subroutine test_zero_upper_limit

   !> The first extrapolation (Simpson's rule) is exact for cubics.
   subroutine test_cubic_exact(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      real(wp) :: exact

      ! integral on [0, 3]: 81/4 - 2*9 + 0.25*9 + 3 = 7.5
      exact = 7.5_wp
      res = romberg(f_cubic, 3.0_wp, 1.0e-30_wp)
      call check(error, res%trap(2, 2), exact, thr=1.0e3_wp*epsilon(1.0_wp)*exact, &
         message="TRAP(2,2) (Simpson) is exact for a cubic")
      if (allocated(error)) return
      call check(error, abs(res%trap(1, 2) - exact) > 1.0e-3_wp, &
         "the trapezoidal column itself is not exact")
      if (allocated(error)) return
      res = romberg(f_cubic, 3.0_wp, 1.0e-6_wp)
      call check(error, res%converged, "converges")
      if (allocated(error)) return
      call check(error, res%value, exact, thr=1.0e3_wp*epsilon(1.0_wp)*exact, &
         message="value exact for a cubic")
   end subroutine test_cubic_exact

   !> The second extrapolation (Boole's rule) is exact for degree 5.
   subroutine test_quintic_exact(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res
      real(wp) :: exact

      ! integral on [0, 2]: 64/6 - 32/5 + 4
      exact = 64.0_wp/6.0_wp - 32.0_wp/5.0_wp + 4.0_wp
      res = romberg(f_quintic, 2.0_wp, 1.0e-30_wp)
      call check(error, res%trap(3, 3), exact, thr=1.0e3_wp*epsilon(1.0_wp)*exact, &
         message="TRAP(3,3) is exact for degree 5")
      if (allocated(error)) return
      call check(error, abs(res%trap(2, 3) - exact) > 1.0e-9_wp, &
         "Simpson's column is not exact for degree 5")
   end subroutine test_quintic_exact

   !> Preset 1 through get_quadrature_preset: the book integrand.
   subroutine test_preset_sinc(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(romberg_result) :: res

      call get_quadrature_preset(1, f, expr, found)
      call check(error, found, "preset 1 exists")
      if (allocated(error)) return
      call check(error, trim(expr), "SIN(X)/X")
      if (allocated(error)) return
      res = romberg(f, 15.0_wp, 2.0e-7_wp)
      call check(error, res%subintervals, 80, "preset 1 is the book's run")
      if (allocated(error)) return
      ! Si(1) = 0.946083070367183
      res = romberg(f, 1.0_wp, 1.0e-10_wp)
      call check(error, res%converged, "Si(1) converges")
      if (allocated(error)) return
      call check(error, res%value, 0.946083070367183_wp, thr=merge(2.0e-6_wp, 1.0e-12_wp, &
         single_precision), message="Si(1)")
   end subroutine test_preset_sinc

   !> Preset 2, EXP(-X**2) on [0, 3] = sqrt(pi)/2 * erf(3).
   subroutine test_preset_gauss(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(romberg_result) :: res

      call get_quadrature_preset(2, f, expr, found)
      call check(error, found .and. trim(expr) == "EXP(-X**2)", "preset 2")
      if (allocated(error)) return
      res = romberg(f, 3.0_wp, 1.0e-8_wp)
      call check(error, res%converged, "converges")
      if (allocated(error)) return
      call check(error, res%value, sqrt(pi)/2.0_wp*erf(3.0_wp), &
         thr=merge(2.0e-6_wp, 1.0e-8_wp, single_precision), message="sqrt(pi)/2 erf(3)")
   end subroutine test_preset_gauss

   !> Preset 3, 1/(1+X**2) on [0, 1] = pi/4.
   subroutine test_preset_runge(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(romberg_result) :: res

      call get_quadrature_preset(3, f, expr, found)
      call check(error, found .and. trim(expr) == "1/(1+X**2)", "preset 3")
      if (allocated(error)) return
      res = romberg(f, 1.0_wp, 1.0e-10_wp)
      call check(error, res%converged, "converges")
      if (allocated(error)) return
      call check(error, res%value, pi/4.0_wp, thr=merge(2.0e-6_wp, 1.0e-10_wp, &
         single_precision), message="pi/4")
   end subroutine test_preset_runge

   !> F(0) is NaN: invalid before any trapezoid; value = the offending X.
   subroutine test_nan_at_zero(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_nan_at_zero, 1.0_wp, 1.0e-6_wp)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "offending X = 0")
   end subroutine test_nan_at_zero

   !> NaN first met at halving 2 (X = 0.25): one completed step is kept.
   subroutine test_nan_inside(error)
      type(error_type), allocatable, intent(out) :: error
      type(romberg_result) :: res

      res = romberg(f_nan_near_quarter, 10.0_wp, 1.0e-30_wp)
      call check_outcome(error, res, status_invalid_value, .false., 1)
      if (allocated(error)) return
      call check(error, same(res%value, 0.25_wp), "offending X = 0.25")
   end subroutine test_nan_inside

   subroutine test_status_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_not_converged), "not_converged")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_value), "invalid_value")
      if (allocated(error)) return
      call check(error, status_name(99), "unknown")
   end subroutine test_status_names

end module test_romberg_suite
