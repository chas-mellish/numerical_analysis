!> test-drive suite for `simpson_mod` (Gerald Ch. 3, Program 1).
!>
!> Covers the book data card (Si(5) with 100 panels) in both precisions, the ordinate records,
!> the book's seed 1.0 = F(0), the odd-N branch, N < 2, the smallest legal N = 2 (zero-trip
!> loop), exactness for cubics, presets 2 and 3 against closed forms, a negative upper limit,
!> B = 0 and non-finite function values.
module test_simpson_suite
   use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_quiet_nan, ieee_positive_inf
   use precision, only: wp, single_precision
   use functions_mod, only: real_function, f_sinc, get_quadrature_preset, preset_expr_len
   use simpson_mod, only: simpson, simpson_result, max_panels, status_name, status_ok, &
      status_odd_panels, status_invalid_input, status_invalid_value
   use book_format_mod, only: book_fixed
   use testdrive, only: new_unittest, unittest_type, error_type, check, test_failed
   implicit none
   private

   public :: collect_simpson

   !> The book's printed value (scan, p. 73): Si(5) with 100 panels, single precision.
   real(wp), parameter :: book_value = 1.5499307_wp
   !> Si(5) = 1.5499312449446741 (true value, Abramowitz and Stegun table 5.1).
   real(wp), parameter :: si5 = 1.5499312449446741_wp

contains

   !> Collect all exported unit tests.
   subroutine collect_simpson(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_result", test_book_card_result), &
         new_unittest("book_card_printed_digits", test_book_card_digits), &
         new_unittest("book_card_ordinates", test_book_card_ordinates), &
         new_unittest("seed_is_f_at_zero", test_seed_is_f0), &
         new_unittest("seed_generalizes_to_f0", test_seed_generalizes), &
         new_unittest("odd_panels", test_odd_panels), &
         new_unittest("odd_panels_negative", test_odd_panels_negative), &
         new_unittest("n_below_two_is_input_error", test_n_below_two), &
         new_unittest("n_above_limit_is_input_error", test_n_above_limit), &
         new_unittest("two_panels_zero_trip_loop", test_two_panels), &
         new_unittest("exact_for_cubics", test_exact_cubic), &
         new_unittest("preset_2_gauss", test_preset_gauss), &
         new_unittest("preset_3_runge", test_preset_runge), &
         new_unittest("convergence_order_four", test_convergence), &
         new_unittest("negative_upper_limit", test_negative_b), &
         new_unittest("zero_upper_limit", test_zero_b), &
         new_unittest("nan_ordinate_is_invalid", test_nan_ordinate), &
         new_unittest("infinite_seed_is_invalid", test_infinite_seed), &
         new_unittest("status_names", test_status_names) &
      ]
   end subroutine collect_simpson

   ! ---------------------------------------------------------------------------------------
   ! Test functions
   ! ---------------------------------------------------------------------------------------

   !> A cubic, 2x**3 - 3x**2 + x + 1; integral from 0 to B is B**4/2 - B**3 + B**2/2 + B.
   pure function f_cubic(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = ((2.0_wp*x - 3.0_wp)*x + 1.0_wp)*x + 1.0_wp
   end function f_cubic

   pure function cubic_integral(b) result(v)
      real(wp), intent(in) :: b
      real(wp) :: v
      v = b**4/2.0_wp - b**3 + b**2/2.0_wp + b
   end function cubic_integral

   !> cos(x): F(0) = 1, integral sin(B).
   pure function f_cos(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = cos(x)
   end function f_cos

   !> NaN for x > 2 (an ordinate inside the loop).
   pure function f_nan_beyond_two(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 2.0_wp .and. x < 3.0_wp) then
         y = ieee_value(1.0_wp, ieee_quiet_nan)
      else
         y = 1.0_wp
      end if
   end function f_nan_beyond_two

   !> 1/x without a special case: +Inf at x = 0.
   pure function f_reciprocal(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = 1.0_wp/x
   end function f_reciprocal

   ! ---------------------------------------------------------------------------------------
   ! Helpers
   ! ---------------------------------------------------------------------------------------

   pure logical function same(a, b)
      real(wp), intent(in) :: a, b
      same = a >= b .and. a <= b
   end function same

   !> Tolerance for analytic comparisons: real64 vs real32 rounding.
   pure real(wp) function tol(real64_tol, real32_tol)
      real(wp), intent(in) :: real64_tol, real32_tol
      if (single_precision) then
         tol = real32_tol
      else
         tol = real64_tol
      end if
   end function tol

   !> Common checks on status / converged / iterations / number of steps.
   subroutine check_outcome(error, res, status, converged, iterations)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result), intent(in) :: res
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
   ! Book data card 5.0 100
   ! ---------------------------------------------------------------------------------------

   !> Si(5) with 100 panels: the book's 1.5499307 within 1E-6 in both precisions; the
   !> exact value of each build (the book order of summation fixes the real32 digits).
   subroutine test_book_card_result(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, 100)
      call check_outcome(error, res, status_ok, .true., 101)
      if (allocated(error)) return
      call check(error, res%value, book_value, thr=1.0e-6_wp, &
         message="value must be the book's 1.5499307 within 1E-6")
      if (allocated(error)) return
      if (single_precision) then
         ! IEEE binary32 with the book's order of summation; the book's machine (not
         ! identified; closest model: 27-bit binary mantissa, chopped) printed 1.5499307.
         call check(error, res%value, 1.54993140697479248_wp, thr=0.0_wp, &
            message="real32 value with the book's order of summation")
      else
         call check(error, res%value, 1.54993123977035374_wp, thr=1.0e-15_wp, &
            message="real64 value")
         if (allocated(error)) return
         call check(error, res%value, si5, thr=1.0e-8_wp, &
            message="real64 value must match Si(5) = 1.5499312449 to 8 figures")
      end if
      if (allocated(error)) return
      call check(error, res%delx, 5.0_wp/100.0_wp, thr=0.0_wp, message="DELX = B/XN")
      if (allocated(error)) return
      call check(error, same(res%value, res%delx/3.0_wp*res%sum), "SININT = DELX/3.*SUM")
   end subroutine test_book_card_result

   !> FORMAT 201 fields: F6.2 of B and F10.7 of SININT (book printer conventions).
   subroutine test_book_card_digits(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, 100)
      call check(error, book_fixed(5.0_wp, 6, 2), "  5.00", "B with F6.2")
      if (allocated(error)) return
      if (single_precision) then
         call check(error, book_fixed(res%value, 10, 7), " 1.5499314", "real32 SININT")
      else
         call check(error, book_fixed(res%value, 10, 7), " 1.5499312", "real64 SININT")
      end if
   end subroutine test_book_card_digits

   !> 101 ordinates k = 0..100 with weights 1 4 2 4 ... 2 4 1, X = k*DELX (accumulated).
   subroutine test_book_card_ordinates(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res
      real(wp) :: weights, expected_weight
      integer :: i, k
      character(len=8) :: row

      res = simpson(f_sinc, 5.0_wp, 100)
      call check(error, size(res%steps), 101)
      if (allocated(error)) return
      weights = 0.0_wp
      do i = 1, 101
         k = i - 1
         write (row, '(I0)') k
         call check(error, res%steps(i)%k, k, "k of row " // trim(row))
         if (allocated(error)) return
         if (k == 0 .or. k == 100) then
            expected_weight = 1.0_wp
         else if (mod(k, 2) == 1) then
            expected_weight = 4.0_wp
         else
            expected_weight = 2.0_wp
         end if
         call check(error, res%steps(i)%weight, expected_weight, thr=0.0_wp, &
            message="weight of ordinate " // trim(row))
         if (allocated(error)) return
         call check(error, res%steps(i)%x, real(k, wp)*0.05_wp, thr=tol(1.0e-13_wp, 2.0e-5_wp), &
            message="X of ordinate " // trim(row))
         if (allocated(error)) return
         if (k > 0) then
            call check(error, same(res%steps(i)%fx, sin(res%steps(i)%x)/res%steps(i)%x), &
               "F(X) of ordinate " // trim(row))
            if (allocated(error)) return
         end if
         weights = weights + res%steps(i)%weight
      end do
      call check(error, weights, 300.0_wp, thr=0.0_wp, message="weights sum to 3N")
      if (allocated(error)) return
      call check(error, same(res%steps(1)%fx, 1.0_wp), "F(0) = 1, the book's seed")
      if (allocated(error)) return
      call check(error, same(res%steps(101)%x, 5.0_wp), "last ordinate at B exactly")
   end subroutine test_book_card_ordinates

   !> The book's literal seed 1.0 gives the same bits as F(0) of preset 1.
   subroutine test_seed_is_f0(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: seeded, evaluated

      seeded = simpson(f_sinc, 5.0_wp, 100, f0=1.0_wp)
      evaluated = simpson(f_sinc, 5.0_wp, 100)
      call check(error, same(seeded%value, evaluated%value), "seed 1.0 == F(0)")
      if (allocated(error)) return
      call check(error, same(seeded%sum, evaluated%sum), "same SUM")
   end subroutine test_seed_is_f0

   !> For another integrand the seed is its own F(0): cos(x) on [0, 1] integrates to sin(1).
   subroutine test_seed_generalizes(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_cos, 1.0_wp, 10)
      call check(error, res%status == status_ok, "cos must integrate")
      if (allocated(error)) return
      call check(error, res%value, sin(1.0_wp), thr=tol(1.0e-6_wp, 1.0e-6_wp))
      if (allocated(error)) return
      call check(error, same(res%steps(1)%fx, 1.0_wp), "seed = cos(0) = 1")
      if (allocated(error)) return
      ! Supplying a wrong seed changes the result by DELX/3 times the error of the seed.
      res = simpson(f_cos, 1.0_wp, 10, f0=0.0_wp)
      call check(error, res%value, sin(1.0_wp) - 0.1_wp/3.0_wp, thr=tol(1.0e-6_wp, 1.0e-6_wp))
   end subroutine test_seed_generalizes

   ! ---------------------------------------------------------------------------------------
   ! Error paths
   ! ---------------------------------------------------------------------------------------

   !> IF (N - 2*NHALF) 99,1,99 -- odd N prints message 200; nothing is evaluated.
   subroutine test_odd_panels(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res
      integer :: n

      do n = 1, 101, 10
         res = simpson(f_sinc, 5.0_wp, n)
         call check_outcome(error, res, status_odd_panels, .false., 0)
         if (allocated(error)) return
      end do
      res = simpson(f_sinc, 5.0_wp, 99)
      call check_outcome(error, res, status_odd_panels, .false., 0)
   end subroutine test_odd_panels

   !> A negative odd N is odd too (truncating division, as in the book): the parity test is first.
   subroutine test_odd_panels_negative(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, -3)
      call check_outcome(error, res, status_odd_panels, .false., 0)
      if (allocated(error)) return
      res = simpson(f_sinc, 5.0_wp, -1)
      call check_outcome(error, res, status_odd_panels, .false., 0)
   end subroutine test_odd_panels_negative

   !> N = 0 (DELX = B/0 in the book) and negative even N are INPUT errors.
   subroutine test_n_below_two(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, 0)
      call check_outcome(error, res, status_invalid_input, .false., 0)
      if (allocated(error)) return
      res = simpson(f_sinc, 5.0_wp, -2)
      call check_outcome(error, res, status_invalid_input, .false., 0)
   end subroutine test_n_below_two

   !> More than max_panels panels is refused.
   subroutine test_n_above_limit(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, max_panels + 2)
      call check_outcome(error, res, status_invalid_input, .false., 0)
   end subroutine test_n_above_limit

   !> N = 2: the DO 10 loop (I = 2, 1) does not execute; three ordinates 0, DELX, B.
   subroutine test_two_panels(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 5.0_wp, 2)
      call check_outcome(error, res, status_ok, .true., 3)
      if (allocated(error)) return
      call check(error, res%value, 2.5_wp/3.0_wp*(1.0_wp + 4.0_wp*sin(2.5_wp)/2.5_wp + &
         sin(5.0_wp)/5.0_wp), thr=tol(1.0e-15_wp, 1.0e-6_wp))
      if (allocated(error)) return
      call check(error, res%steps(2)%k, 1)
      if (allocated(error)) return
      call check(error, res%steps(3)%k, 2)
      if (allocated(error)) return
      call check(error, same(res%steps(3)%x, 5.0_wp), "last ordinate is B")
   end subroutine test_two_panels

   !> Simpson's rule integrates cubics exactly (up to rounding), for any even N.
   subroutine test_exact_cubic(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res
      integer :: n
      character(len=8) :: label

      do n = 2, 20, 6
         write (label, '(I0)') n
         res = simpson(f_cubic, 2.5_wp, n)
         call check(error, res%value, cubic_integral(2.5_wp), &
            thr=tol(1.0e-12_wp, 2.0e-5_wp), message="cubic with N = " // trim(label))
         if (allocated(error)) return
      end do
   end subroutine test_exact_cubic

   !> Preset 2, exp(-x**2) on [0, 2]: sqrt(pi)/2*erf(2) = 0.88208139076242168.
   subroutine test_preset_gauss(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(simpson_result) :: res

      call get_quadrature_preset(2, f, expr, found)
      if (.not. found) then
         call test_failed(error, "preset 2 missing")
         return
      end if
      res = simpson(f, 2.0_wp, 100)
      call check(error, res%status == status_ok, "preset 2 must integrate")
      if (allocated(error)) return
      call check(error, res%value, 0.88208139076242168_wp, thr=tol(1.0e-8_wp, 1.0e-6_wp))
      if (allocated(error)) return
      call check(error, res%value, sqrt(acos(-1.0_wp))/2.0_wp*erf(2.0_wp), &
         thr=tol(1.0e-8_wp, 1.0e-6_wp))
   end subroutine test_preset_gauss

   !> Preset 3, 1/(1+x**2) on [0, 1]: atan(1) = pi/4.
   subroutine test_preset_runge(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      type(simpson_result) :: res

      call get_quadrature_preset(3, f, expr, found)
      if (.not. found) then
         call test_failed(error, "preset 3 missing")
         return
      end if
      res = simpson(f, 1.0_wp, 100)
      call check(error, res%status == status_ok, "preset 3 must integrate")
      if (allocated(error)) return
      call check(error, res%value, atan(1.0_wp), thr=tol(1.0e-12_wp, 1.0e-6_wp))
      if (allocated(error)) return
      ! 1/(1+x**2) on [0, 5] with the book's N = 100: atan(5).
      res = simpson(f, 5.0_wp, 100)
      call check(error, res%value, atan(5.0_wp), thr=tol(1.0e-8_wp, 2.0e-6_wp))
   end subroutine test_preset_runge

   !> Halving DELX divides the error by about 16 (fourth-order rule), real64 only.
   subroutine test_convergence(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: coarse, fine
      real(wp) :: ratio

      if (single_precision) return
      coarse = simpson(f_sinc, 5.0_wp, 10)
      fine = simpson(f_sinc, 5.0_wp, 20)
      ratio = abs(coarse%value - si5)/abs(fine%value - si5)
      call check(error, ratio > 12.0_wp .and. ratio < 20.0_wp, "error ratio near 16")
   end subroutine test_convergence

   !> Si is odd: B = -5 gives -Si(5) (DELX negative, ordinates mirrored).
   subroutine test_negative_b(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: pos, neg

      pos = simpson(f_sinc, 5.0_wp, 100)
      neg = simpson(f_sinc, -5.0_wp, 100)
      call check(error, neg%status == status_ok, "negative B must integrate")
      if (allocated(error)) return
      call check(error, same(neg%value, -pos%value), "Si(-5) = -Si(5) bit for bit")
   end subroutine test_negative_b

   !> B = 0: every ordinate is F(0) and DELX = 0, so the integral is 0.
   subroutine test_zero_b(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_sinc, 0.0_wp, 4)
      call check_outcome(error, res, status_ok, .true., 5)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "integral over [0, 0] is 0")
   end subroutine test_zero_b

   !> NaN at an ordinate inside the loop: invalid value, the earlier ordinates are kept.
   subroutine test_nan_ordinate(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      ! B = 4, N = 8: DELX = 0.5; evaluation order k = 0, 1, 8, 2, 3, 4, 5 (X = 2.5 is NaN).
      res = simpson(f_nan_beyond_two, 4.0_wp, 8)
      call check(error, status_name(res%status), status_name(status_invalid_value))
      if (allocated(error)) return
      call check(error, res%converged .eqv. .false., "not converged")
      if (allocated(error)) return
      call check(error, res%value, 2.5_wp, thr=0.0_wp, message="offending X")
      if (allocated(error)) return
      call check(error, size(res%steps), 6, "ordinates 0 1 2 3 4 and 8 were evaluated")
      if (allocated(error)) return
      call check(error, res%iterations, 6)
      if (allocated(error)) return
      call check(error, res%steps(5)%k, 4, "rows sorted by k")
      if (allocated(error)) return
      call check(error, res%steps(6)%k, 8, "B's ordinate last")
   end subroutine test_nan_ordinate

   !> 1/x at X = 0 is +Inf: the seed itself is invalid (no rows).
   subroutine test_infinite_seed(error)
      type(error_type), allocatable, intent(out) :: error
      type(simpson_result) :: res

      res = simpson(f_reciprocal, 1.0_wp, 4)
      call check_outcome(error, res, status_invalid_value, .false., 0)
      if (allocated(error)) return
      call check(error, same(res%value, 0.0_wp), "offending X is 0")
      if (allocated(error)) return
      res = simpson(f_reciprocal, 1.0_wp, 4, f0=ieee_value(1.0_wp, ieee_positive_inf))
      call check_outcome(error, res, status_invalid_value, .false., 0)
   end subroutine test_infinite_seed

   !> Status names used in diagnostics.
   subroutine test_status_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_odd_panels), "odd_panels")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_input), "invalid_input")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_value), "invalid_value")
      if (allocated(error)) return
      call check(error, status_name(99), "unknown")
   end subroutine test_status_names

end module test_simpson_suite
