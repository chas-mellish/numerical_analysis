!> test-drive suite for `bairstow_mod` (Gerald Ch. 1, Program 2).
!>
!> Covers the book data cards (factors, printed digits, iteration counts), the step records,
!> the exactly singular Bairstow denominator (R/S nudge), the nudge guard, non-convergence
!> within LIM, the degree branches 2, 3, 4 and 6 (final linear versus final quadratic factor),
!> the DEGREE checks and the roots helper used by --verbose.
module test_bairstow_suite
   use precision, only: wp, single_precision
   use bairstow_mod, only: bairstow, bairstow_result, bairstow_factor, factor_roots, &
      status_name, factor_kind_name, is_exact_zero, n_coeffs, status_ok, &
      status_non_convergent, status_degree_error, degree_out_of_range, &
      degree_high_coefficient, factor_quadratic, factor_final_quadratic, factor_linear
   use book_format_mod, only: book_fixed
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_bairstow

   !> Book data card 1: X**6 ... X**0 of x**5 - 17.8x**4 + 99.41x**3 - 261.218x**2 + ...
   real(wp), parameter :: book_coeffs(n_coeffs) = [0.0_wp, 1.0_wp, -17.8_wp, 99.41_wp, &
      -261.218_wp, 352.611_wp, -134.106_wp]
   !> The printed factor values (scan p. 26) and the exact factors of the book's text.
   real(wp), parameter :: book_printed(6) = [4.19999_wp, -2.09999_wp, 3.29999_wp, &
      -6.20000_wp, 1.00000_wp, -10.30000_wp]
   real(wp), parameter :: exact(6) = [4.2_wp, -2.1_wp, 3.3_wp, -6.2_wp, 1.0_wp, -10.3_wp]

contains

   !> Collect all exported unit tests.
   subroutine collect_bairstow(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_factors", test_book_card_factors), &
         new_unittest("book_card_printed_digits", test_book_printed_digits), &
         new_unittest("book_card_iterations", test_book_iterations), &
         new_unittest("step_records", test_step_records), &
         new_unittest("singular_denominator_nudge", test_singular_denominator), &
         new_unittest("singular_denominator_cubic", test_singular_cubic), &
         new_unittest("nudge_guard_zero_polynomial", test_nudge_guard), &
         new_unittest("non_convergent_within_lim", test_non_convergent), &
         new_unittest("lim_is_per_factor", test_lim_per_factor), &
         new_unittest("lim_zero_allows_one_correction", test_lim_zero), &
         new_unittest("negative_test_never_converges", test_negative_test), &
         new_unittest("degree_2_constant_quotient", test_degree_2), &
         new_unittest("degree_3_final_linear", test_degree_3), &
         new_unittest("degree_4_final_quadratic", test_degree_4), &
         new_unittest("degree_6_three_factors", test_degree_6), &
         new_unittest("degree_out_of_range", test_degree_out_of_range), &
         new_unittest("degree_high_coefficient", test_degree_high_coefficient), &
         new_unittest("factor_roots", test_factor_roots), &
         new_unittest("names", test_names) &
      ]
   end subroutine collect_bairstow

   ! ---------------------------------------------------------------------------------------
   ! Helpers
   ! ---------------------------------------------------------------------------------------

   !> Tolerance on converged factors: tight in real64, single-precision noise in real32.
   pure real(wp) function factor_tol()
      if (single_precision) then
         factor_tol = 2.0e-5_wp
      else
         factor_tol = 1.0e-8_wp
      end if
   end function factor_tol

   !> The coefficients of the book's polynomial with the given degree layout (X**6 first).
   pure function card(c6, c5, c4, c3, c2, c1, c0) result(c)
      real(wp), intent(in) :: c6, c5, c4, c3, c2, c1, c0
      real(wp) :: c(n_coeffs)
      c = [c6, c5, c4, c3, c2, c1, c0]
   end function card

   subroutine check_status(error, res, status, nfactors, iterations)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result), intent(in) :: res
      integer, intent(in) :: status, nfactors
      integer, intent(in), optional :: iterations

      call check(error, status_name(res%status), status_name(status))
      if (allocated(error)) return
      call check(error, size(res%factors), nfactors, "number of factors")
      if (allocated(error)) return
      call check(error, res%converged .eqv. (status == status_ok), "converged flag")
      if (allocated(error)) return
      call check(error, res%iterations, size(res%steps), "iterations = size(steps)")
      if (allocated(error)) return
      if (status == status_ok) then
         call check(error, res%value, nfactors, "value = number of factors")
         if (allocated(error)) return
      end if
      if (present(iterations)) call check(error, res%iterations, iterations, "iterations")
   end subroutine check_status

   subroutine check_factor(error, f, kind, coef, tol)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_factor), intent(in) :: f
      integer, intent(in) :: kind
      real(wp), intent(in) :: coef(:), tol
      integer :: i

      call check(error, factor_kind_name(f%kind), factor_kind_name(kind))
      if (allocated(error)) return
      call check(error, f%ncoef, size(coef), "ncoef")
      if (allocated(error)) return
      do i = 1, size(coef)
         call check(error, f%coef(i), coef(i), thr=tol, &
            message="factor coefficient " // achar(iachar("0") + i))
         if (allocated(error)) return
      end do
   end subroutine check_factor

   ! ---------------------------------------------------------------------------------------
   ! Book data cards
   ! ---------------------------------------------------------------------------------------

   !> 0. 1. -17.8 99.41 -261.218 352.611 -134.106 / 0. 0. 1.E-5 20 5: the exact factors
   !> x**2 - 4.2x + 2.1, x**2 - 3.3x + 6.2 and x - 10.3 (printed R, S = 4.2, -2.1; 3.3, -6.2).
   subroutine test_book_card_factors(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 5)
      call check_status(error, res, status_ok, 3)
      if (allocated(error)) return
      call check(error, res%nudges, 0, "no zero denominator on the book card")
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, exact(1:2), factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_quadratic, exact(3:4), factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(3), factor_linear, exact(5:6), factor_tol())
   end subroutine test_book_card_factors

   !> The book prints chopped digits 4.19999 -2.09999 / 3.29999 -6.20000 / 1.00000 -10.30000.
   !> Every value agrees within 2E-5 in both builds; the exact text differs in documented
   !> last digits (real64: 3.30000; real32: 4.20000 -2.10000 -6.19999 -10.29999).
   subroutine test_book_printed_digits(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      character(len=10) :: expected(6), got(6)
      real(wp) :: values(6)
      integer :: i

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 5)
      call check_status(error, res, status_ok, 3)
      if (allocated(error)) return
      values = [res%factors(1)%coef(1:2), res%factors(2)%coef(1:2), res%factors(3)%coef(1:2)]
      do i = 1, 6
         call check(error, values(i), book_printed(i), thr=2.0e-5_wp, &
            message="printed factor value within 2E-5 of the book")
         if (allocated(error)) return
         got(i) = book_fixed(values(i), 10, 5)
      end do
      if (single_precision) then
         expected = [character(len=10) :: "   4.20000", "  -2.10000", "   3.29999", &
            "  -6.19999", "   1.00000", " -10.29999"]
      else
         expected = [character(len=10) :: "   4.19999", "  -2.09999", "   3.30000", &
            "  -6.20000", "   1.00000", " -10.30000"]
      end if
      do i = 1, 6
         call check(error, got(i), expected(i))
         if (allocated(error)) return
      end do
   end subroutine test_book_printed_digits

   !> 8 corrections for the first factor and 5 for the second, in both precisions.
   subroutine test_book_iterations(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 5)
      call check_status(error, res, status_ok, 3, iterations=13)
      if (allocated(error)) return
      call check(error, count(res%steps%factor == 1), 8, "corrections for factor 1")
      if (allocated(error)) return
      call check(error, count(res%steps%factor == 2), 5, "corrections for factor 2")
   end subroutine test_book_iterations

   !> STEP rows: k counts 1.. within each factor, R = DELR + R, the next factor starts from the
   !> previous factor's R and S, and only the last correction of a factor meets TEST.
   subroutine test_step_records(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      real(wp) :: r_prev, s_prev
      integer :: i, expected_k

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 5)
      call check_status(error, res, status_ok, 3)
      if (allocated(error)) return
      r_prev = 0.0_wp
      s_prev = 0.0_wp
      expected_k = 0
      do i = 1, size(res%steps)
         if (i > 1) then
            if (res%steps(i)%factor /= res%steps(i - 1)%factor) expected_k = 0
         end if
         expected_k = expected_k + 1
         call check(error, res%steps(i)%k, expected_k, "k within the factor")
         if (allocated(error)) return
         call check(error, res%steps(i)%r, res%steps(i)%delr + r_prev, "R = DELR + R")
         if (allocated(error)) return
         call check(error, res%steps(i)%s, res%steps(i)%dels + s_prev, "S = DELS + S")
         if (allocated(error)) return
         call check(error, abs(res%steps(i)%delr) + abs(res%steps(i)%dels) <= 1.0e-5_wp .eqv. &
            (i == 8 .or. i == 13), "only the last correction of a factor meets TEST")
         if (allocated(error)) return
         r_prev = res%steps(i)%r
         s_prev = res%steps(i)%s
      end do
      call check(error, res%factors(1)%coef(1), res%steps(8)%r, "factor 1 R is the last R")
      if (allocated(error)) return
      call check(error, res%factors(2)%coef(2), res%steps(13)%s, "factor 2 S is the last S")
   end subroutine test_step_records

   ! ---------------------------------------------------------------------------------------
   ! Singular denominator (label 10) and the nudge guard
   ! ---------------------------------------------------------------------------------------

   !> x**4 - 16 from R = S = 0: B = C = A, so DENOM = C(7)**2 - C(8)*C(6) = 0 - 0*0 is exactly
   !> zero. The original looped forever (it bumped R1, S1); here R = S = 1 and the search
   !> restarts with KOUNT = 1, ending with x**2 - 4 (R = 0, S = 4) and the final x**2 + 4.
   subroutine test_singular_denominator(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      real(wp) :: c(n_coeffs)

      c = card(0.0_wp, 0.0_wp, 1.0_wp, 0.0_wp, 0.0_wp, 0.0_wp, -16.0_wp)
      ! DENOM at R = S = 0 is C(7)*C(7) - C(8)*C(6) with C(j) = A(j): exactly zero.
      call check(error, is_exact_zero(c(5)*c(5) - c(6)*c(4)), "DENOM is exactly zero at R=S=0")
      if (allocated(error)) return
      res = bairstow(c, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 4)
      call check_status(error, res, status_ok, 2, iterations=11)
      if (allocated(error)) return
      call check(error, res%nudges, 1, "one nudge")
      if (allocated(error)) return
      call check(error, res%steps(1)%k, 1, "KOUNT restarts at 1 after the nudge")
      if (allocated(error)) return
      ! The first correction starts from the nudged R = S = 1.
      call check(error, res%steps(1)%r - res%steps(1)%delr, 1.0_wp, "R nudged to 1")
      if (allocated(error)) return
      call check(error, res%steps(1)%s - res%steps(1)%dels, 1.0_wp, "S nudged to 1")
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, [0.0_wp, 4.0_wp], factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_final_quadratic, &
         [1.0_wp, 0.0_wp, 4.0_wp], factor_tol())
   end subroutine test_singular_denominator

   !> x**3 - 8 from R = S = 0 is singular too; after the nudge the real factor needs 26
   !> corrections (non-convergent within the book's LIM = 20, convergent with LIM = 50).
   subroutine test_singular_cubic(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      real(wp) :: c(n_coeffs)

      c = card(0.0_wp, 0.0_wp, 0.0_wp, 1.0_wp, 0.0_wp, 0.0_wp, -8.0_wp)
      res = bairstow(c, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 3)
      call check_status(error, res, status_non_convergent, 0, iterations=20)
      if (allocated(error)) return
      call check(error, res%nudges, 1, "one nudge before the 20 corrections")
      if (allocated(error)) return
      res = bairstow(c, 0.0_wp, 0.0_wp, 1.0e-5_wp, 50, 3)
      call check_status(error, res, status_ok, 2, iterations=26)
      if (allocated(error)) return
      ! x**2 + 2x + 4 = X**2 - R X - S with R = -2, S = -4, then x - 2.
      call check_factor(error, res%factors(1), factor_quadratic, [-2.0_wp, -4.0_wp], &
         factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_linear, [1.0_wp, -2.0_wp], 1.0e-6_wp)
   end subroutine test_singular_cubic

   !> An all-zero polynomial keeps DENOM = 0 after every nudge. The original looped forever;
   !> here the run stops after LIM + 1 nudges with the book's non-convergence message.
   subroutine test_nudge_guard(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(spread(0.0_wp, 1, n_coeffs), 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 4)
      call check_status(error, res, status_non_convergent, 0, iterations=0)
      if (allocated(error)) return
      call check(error, res%nudges, 21, "LIM + 1 nudges")
   end subroutine test_nudge_guard

   ! ---------------------------------------------------------------------------------------
   ! Non-convergence within LIM (labels 13/15)
   ! ---------------------------------------------------------------------------------------

   !> LIM = 3 and 7 stop during the first factor (it needs 8): LIM corrections, no factor.
   subroutine test_non_convergent(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      integer :: lim

      do lim = 3, 7, 4
         res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, lim, 5)
         call check_status(error, res, status_non_convergent, 0, iterations=lim)
         if (allocated(error)) return
         call check(error, res%value, 0, "no factor count on failure")
         if (allocated(error)) return
         call check(error, res%steps(lim)%k, lim, "last KOUNT = LIM")
         if (allocated(error)) return
      end do
   end subroutine test_non_convergent

   !> LIM bounds KOUNT per factor: LIM = 8 suffices although the run needs 8 + 5 = 13
   !> corrections. Started at the first factor (R1 = 4.2, S1 = -2.1), factor 1 takes one
   !> correction and factor 2 five: LIM = 4 fails in factor 2 and keeps factor 1.
   subroutine test_lim_per_factor(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 8, 5)
      call check_status(error, res, status_ok, 3, iterations=13)
      if (allocated(error)) return
      res = bairstow(book_coeffs, 4.2_wp, -2.1_wp, 1.0e-5_wp, 5, 5)
      call check_status(error, res, status_ok, 3, iterations=6)
      if (allocated(error)) return
      res = bairstow(book_coeffs, 4.2_wp, -2.1_wp, 1.0e-5_wp, 4, 5)
      call check_status(error, res, status_non_convergent, 1, iterations=5)
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, exact(1:2), factor_tol())
      if (allocated(error)) return
      call check(error, res%steps(5)%factor, 2, "failure during factor 2")
      if (allocated(error)) return
      call check(error, res%steps(5)%k, 4, "KOUNT = LIM at the failure")
   end subroutine test_lim_per_factor

   !> IF (KOUNT - LIM) 14, 15, 15 after the first correction: LIM = 0 allows one correction.
   subroutine test_lim_zero(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 0, 5)
      call check_status(error, res, status_non_convergent, 0, iterations=1)
   end subroutine test_lim_zero

   !> A negative TEST can never be met: LIM corrections, then message 24.
   subroutine test_negative_test(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, -1.0_wp, 20, 5)
      call check_status(error, res, status_non_convergent, 0, iterations=20)
   end subroutine test_negative_test

   ! ---------------------------------------------------------------------------------------
   ! Degree branches: IF (N - 2) 18, 19, 20
   ! ---------------------------------------------------------------------------------------

   !> N = 2: the quadratic factor is the polynomial (divided by its leading coefficient) and
   !> label 18 prints the constant quotient as .00000X + A.
   subroutine test_degree_2(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(card(0.0_wp, 0.0_wp, 0.0_wp, 0.0_wp, 2.0_wp, -6.0_wp, 4.0_wp), &
         0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 2)
      call check_status(error, res, status_ok, 2, iterations=3)
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, [3.0_wp, -2.0_wp], factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_linear, [0.0_wp, 2.0_wp], 0.0_wp)
   end subroutine test_degree_2

   !> N = 3: (x - 1)(x - 2)(x - 3) = (x**2 - 3x + 2)(x - 3): one quadratic, final linear.
   subroutine test_degree_3(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(card(0.0_wp, 0.0_wp, 0.0_wp, 1.0_wp, -6.0_wp, 11.0_wp, -6.0_wp), &
         0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 3)
      call check_status(error, res, status_ok, 2, iterations=8)
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, [3.0_wp, -2.0_wp], factor_tol())
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_linear, [1.0_wp, -3.0_wp], 1.0e-6_wp)
   end subroutine test_degree_3

   !> N = 4: (x**2 - 5x + 4)(x**2 - 5x + 6): one quadratic, then FORMAT 22's final quadratic.
   subroutine test_degree_4(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(card(0.0_wp, 0.0_wp, 1.0_wp, -10.0_wp, 35.0_wp, -50.0_wp, 24.0_wp), &
         0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 4)
      call check_status(error, res, status_ok, 2, iterations=11)
      if (allocated(error)) return
      call check_factor(error, res%factors(1), factor_quadratic, [5.0_wp, -4.0_wp], 1.0e-6_wp)
      if (allocated(error)) return
      call check_factor(error, res%factors(2), factor_final_quadratic, &
         [1.0_wp, -5.0_wp, 6.0_wp], 1.0e-6_wp)
   end subroutine test_degree_4

   !> N = 6: (x - 1)(x - 2)...(x - 6) gives two quadratics and a final quadratic (A reduced
   !> twice by DO 21); the product of the true factors has the roots 1 ... 6.
   subroutine test_degree_6(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      complex(wp) :: roots(2)
      real(wp) :: found(6), sorted(6), tol
      integer :: i, j, nroots, m

      res = bairstow(card(1.0_wp, -21.0_wp, 175.0_wp, -735.0_wp, 1624.0_wp, -1764.0_wp, &
         720.0_wp), 0.0_wp, 0.0_wp, 1.0e-5_wp, 50, 6)
      call check_status(error, res, status_ok, 3)
      if (allocated(error)) return
      call check(error, factor_kind_name(res%factors(3)%kind), "final_quadratic")
      if (allocated(error)) return
      m = 0
      do i = 1, 3
         call factor_roots(res%factors(i), roots, nroots)
         call check(error, nroots, 2, "two roots per factor")
         if (allocated(error)) return
         do j = 1, 2
            m = m + 1
            found(m) = real(roots(j), wp)
         end do
      end do
      sorted = found
      do i = 1, 5
         do j = i + 1, 6
            if (sorted(j) < sorted(i)) sorted([i, j]) = sorted([j, i])
         end do
      end do
      tol = merge(1.0e-3_wp, 1.0e-5_wp, single_precision)
      do i = 1, 6
         call check(error, sorted(i), real(i, wp), thr=tol, message="root of the sextic")
         if (allocated(error)) return
      end do
   end subroutine test_degree_6

   !> N outside 2..6 is a DEGREE error before any computation.
   subroutine test_degree_out_of_range(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res
      integer :: n
      integer, parameter :: bad(4) = [-1, 0, 1, 7]
      integer :: i

      do i = 1, size(bad)
         n = bad(i)
         res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, n)
         call check_status(error, res, status_degree_error, 0, iterations=0)
         if (allocated(error)) return
         call check(error, res%degree_problem, degree_out_of_range, "degree out of range")
         if (allocated(error)) return
      end do
   end subroutine test_degree_out_of_range

   !> A nonzero coefficient above X**N is a DEGREE error naming the highest such power.
   subroutine test_degree_high_coefficient(error)
      type(error_type), allocatable, intent(out) :: error
      type(bairstow_result) :: res

      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 4)
      call check_status(error, res, status_degree_error, 0)
      if (allocated(error)) return
      call check(error, res%degree_problem, degree_high_coefficient, "high coefficient")
      if (allocated(error)) return
      call check(error, res%bad_power, 5, "X**5 is not zero")
      if (allocated(error)) return
      ! N = 6 accepts the book card (leading coefficient zero): the last factor is then the
      ! final quadratic .00000X**2 + 1.00000X + -10.30000.
      res = bairstow(book_coeffs, 0.0_wp, 0.0_wp, 1.0e-5_wp, 20, 6)
      call check_status(error, res, status_ok, 3, iterations=13)
      if (allocated(error)) return
      call check_factor(error, res%factors(3), factor_final_quadratic, &
         [0.0_wp, 1.0_wp, -10.3_wp], factor_tol())
   end subroutine test_degree_high_coefficient

   ! ---------------------------------------------------------------------------------------
   ! Roots helper (--verbose) and names
   ! ---------------------------------------------------------------------------------------

   subroutine test_factor_roots(error)
      type(error_type), allocatable, intent(out) :: error
      complex(wp) :: roots(2)
      integer :: nroots

      ! X**2 - 4.2 X + 2.1 (printed R = 4.2, S = -2.1): real roots 2.1 +- sqrt(2.31).
      call factor_roots(bairstow_factor(kind=factor_quadratic, ncoef=2, &
         coef=[4.2_wp, -2.1_wp, 0.0_wp]), roots, nroots)
      call check(error, nroots, 2)
      if (allocated(error)) return
      call check(error, real(roots(1), wp), 2.1_wp + sqrt(2.31_wp), thr=1.0e-5_wp)
      if (allocated(error)) return
      call check(error, real(roots(2), wp), 2.1_wp - sqrt(2.31_wp), thr=1.0e-5_wp)
      if (allocated(error)) return
      call check(error, is_exact_zero(aimag(roots(1))), "real root")
      if (allocated(error)) return
      ! X**2 - 3.3 X + 6.2: complex pair 1.65 +- i sqrt(3.4775).
      call factor_roots(bairstow_factor(kind=factor_quadratic, ncoef=2, &
         coef=[3.3_wp, -6.2_wp, 0.0_wp]), roots, nroots)
      call check(error, real(roots(1), wp), 1.65_wp, thr=1.0e-6_wp)
      if (allocated(error)) return
      call check(error, aimag(roots(1)), sqrt(3.4775_wp), thr=1.0e-5_wp)
      if (allocated(error)) return
      call check(error, aimag(roots(2)), -sqrt(3.4775_wp), thr=1.0e-5_wp)
      if (allocated(error)) return
      ! 1.00000X + -10.30000: root 10.3; .00000X + 2.00000: no root.
      call factor_roots(bairstow_factor(kind=factor_linear, ncoef=2, &
         coef=[1.0_wp, -10.3_wp, 0.0_wp]), roots, nroots)
      call check(error, nroots, 1)
      if (allocated(error)) return
      call check(error, real(roots(1), wp), 10.3_wp, thr=1.0e-5_wp)
      if (allocated(error)) return
      call factor_roots(bairstow_factor(kind=factor_linear, ncoef=2, &
         coef=[0.0_wp, 2.0_wp, 0.0_wp]), roots, nroots)
      call check(error, nroots, 0, "constant factor has no root")
      if (allocated(error)) return
      ! Final quadratic 2X**2 - 10X + 12 = 2(x - 2)(x - 3), and with A2 = 0 a linear factor.
      call factor_roots(bairstow_factor(kind=factor_final_quadratic, ncoef=3, &
         coef=[2.0_wp, -10.0_wp, 12.0_wp]), roots, nroots)
      call check(error, real(roots(1), wp), 3.0_wp, thr=1.0e-6_wp)
      if (allocated(error)) return
      call check(error, real(roots(2), wp), 2.0_wp, thr=1.0e-6_wp)
      if (allocated(error)) return
      call factor_roots(bairstow_factor(kind=factor_final_quadratic, ncoef=3, &
         coef=[0.0_wp, 1.0_wp, -10.3_wp]), roots, nroots)
      call check(error, nroots, 1, "A2 = 0 is linear")
      if (allocated(error)) return
      call check(error, real(roots(1), wp), 10.3_wp, thr=1.0e-5_wp)
   end subroutine test_factor_roots

   subroutine test_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_non_convergent), "non_convergent")
      if (allocated(error)) return
      call check(error, status_name(status_degree_error), "degree_error")
      if (allocated(error)) return
      call check(error, status_name(99), "unknown")
      if (allocated(error)) return
      call check(error, factor_kind_name(factor_quadratic), "quadratic")
      if (allocated(error)) return
      call check(error, factor_kind_name(factor_final_quadratic), "final_quadratic")
      if (allocated(error)) return
      call check(error, factor_kind_name(factor_linear), "linear")
      if (allocated(error)) return
      call check(error, factor_kind_name(0), "unknown")
   end subroutine test_names

end module test_bairstow_suite
