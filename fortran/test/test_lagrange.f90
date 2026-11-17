!> test-drive suite for `lagrange_mod` (Lagrangian interpolation, program lagrange_interpolation).
!>
!> Covers the book data card (2.3119 at X = 5.0 and the printed digits in both precisions),
!> the per-term trace, reproduction of the data nodes, exactness for polynomials of degree
!> below N, a single point, and every modernized error path: N outside 1..10 (DIMENSION),
!> equal X values (a division by zero in the original), mismatched sizes and overflow.
module test_lagrange_suite
   use precision, only: wp, single_precision
   use lagrange_mod, only: lagrange, lagrange_result, max_points, status_name, status_ok, &
      status_degree_error, status_size_mismatch, status_duplicate_x, status_invalid_value
   use book_format_mod, only: book_fixed, book_int
   use testdrive, only: new_unittest, unittest_type, error_type, check, test_failed
   implicit none
   private

   public :: collect_lagrange

   !> The book's data card: X(I), Y(I) in READ order (X = SINH(Y) to four decimals).
   real(wp), parameter :: book_x(5) = [2.3756_wp, 3.2682_wp, 4.4571_wp, 6.0502_wp, 8.1919_wp]
   real(wp), parameter :: book_y(5) = [1.6_wp, 1.9_wp, 2.2_wp, 2.5_wp, 2.8_wp]
   real(wp), parameter :: book_xin = 5.0_wp
   !> The book's printed value (F10.4) and the real64 reference.
   real(wp), parameter :: book_value = 2.3119_wp
   real(wp), parameter :: real64_value = 2.3119012901784366_wp

contains

   !> Collect all exported unit tests.
   subroutine collect_lagrange(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_card_value", test_book_card_value), &
         new_unittest("book_card_printed_digits", test_book_card_digits), &
         new_unittest("book_card_terms", test_book_card_terms), &
         new_unittest("swapped_columns_do_not_give_book_value", test_swapped_columns), &
         new_unittest("nodes_reproduced", test_nodes_reproduced), &
         new_unittest("exact_for_low_degree_polynomials", test_polynomial_exactness), &
         new_unittest("single_point_is_constant", test_single_point), &
         new_unittest("two_points_linear_extrapolation", test_two_points), &
         new_unittest("ten_points_allowed", test_ten_points), &
         new_unittest("zero_points_is_degree_error", test_zero_points), &
         new_unittest("eleven_points_is_degree_error", test_eleven_points), &
         new_unittest("size_mismatch", test_size_mismatch), &
         new_unittest("duplicate_x_is_input_error", test_duplicate_x), &
         new_unittest("overflow_is_invalid_value", test_overflow), &
         new_unittest("status_names", test_status_names) &
      ]
   end subroutine collect_lagrange

   ! ---------------------------------------------------------------------------------------

   !> Exact equality without a real == comparison (-Wcompare-reals).
   pure logical function same(a, b)
      real(wp), intent(in) :: a, b
      same = .not. (a < b .or. a > b)
   end function same

   !> Check |actual - expected| <= tol, with a message naming the quantity.
   subroutine check_close(error, actual, expected, tol, what)
      type(error_type), allocatable, intent(out) :: error
      real(wp), intent(in) :: actual, expected, tol
      character(len=*), intent(in) :: what
      character(len=128) :: msg

      if (abs(actual - expected) > tol) then
         write (msg, '(a, ": ", es24.16, " differs from ", es24.16)') what, actual, expected
         call test_failed(error, trim(msg))
      end if
   end subroutine check_close

   !> Golden: 2.3119 within one unit of the printed F10.4 digit; real64 to 1e-12.
   subroutine test_book_card_value(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange(book_x, book_y, book_xin)
      call check(error, res%status, status_ok)
      if (allocated(error)) return
      call check(error, res%converged, "book card must succeed")
      if (allocated(error)) return
      call check(error, res%iterations, 5)
      if (allocated(error)) return
      call check(error, res%n, 5)
      if (allocated(error)) return
      call check_close(error, res%value, book_value, 1.0e-4_wp, "value vs book")
      if (allocated(error)) return
      if (single_precision) then
         call check_close(error, res%value, real64_value, 5.0e-6_wp, "real32 value")
      else
         call check_close(error, res%value, real64_value, 1.0e-12_wp, "real64 value")
      end if
   end subroutine test_book_card_value

   !> FORMAT 200 fields of the book card print the book's digits in either precision.
   subroutine test_book_card_digits(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange(book_x, book_y, book_xin)
      call check(error, book_int(res%n, 3), "  5")
      if (allocated(error)) return
      call check(error, book_fixed(book_xin, 10, 3), "     5.000")
      if (allocated(error)) return
      call check(error, book_fixed(res%value, 10, 4), "    2.3119")
   end subroutine test_book_card_digits

   !> One step per term: the data pair, TERM, and the running sum ending at the value.
   subroutine test_book_card_terms(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res
      real(wp) :: total, basis
      integer :: i, j

      res = lagrange(book_x, book_y, book_xin)
      call check(error, size(res%steps), 5)
      if (allocated(error)) return
      total = 0.0_wp
      do i = 1, 5
         call check(error, res%steps(i)%i, i)
         if (allocated(error)) return
         call check(error, same(res%steps(i)%x, book_x(i)) .and. same(res%steps(i)%y, book_y(i)), &
            "step data pair")
         if (allocated(error)) return
         basis = 1.0_wp
         do j = 1, 5
            if (j /= i) basis = basis*(book_xin - book_x(j))/(book_x(i) - book_x(j))
         end do
         call check_close(error, res%steps(i)%term, book_y(i)*basis, &
            100*epsilon(1.0_wp), "term = Y(I)*L_I(XIN)")
         if (allocated(error)) return
         total = total + res%steps(i)%term
         call check(error, same(res%steps(i)%partial, total), "partial is the running sum")
         if (allocated(error)) return
      end do
      call check(error, same(res%steps(5)%partial, res%value), "last partial is the value")
      if (allocated(error)) return
      ! The terms of the book card (real64 reference, see the catalog / study page).
      call check_close(error, res%steps(3)%term, 2.2763529777459395_wp, 1.0e-5_wp, "term 3")
   end subroutine test_book_card_terms

   !> Reading the pairs as Y, X instead of X, Y does not give the book's 2.3119.
   subroutine test_swapped_columns(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange(book_y, book_x, book_xin)
      call check(error, res%status, status_ok)
      if (allocated(error)) return
      call check(error, abs(res%value - book_value) > 1.0_wp, "swapped order must differ")
   end subroutine test_swapped_columns

   !> P(X(k)) = Y(k) at every node (all other terms vanish exactly).
   subroutine test_nodes_reproduced(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res
      integer :: k

      do k = 1, 5
         res = lagrange(book_x, book_y, book_x(k))
         call check(error, res%status, status_ok)
         if (allocated(error)) return
         call check_close(error, res%value, book_y(k), 8*epsilon(1.0_wp)*abs(book_y(k)), &
            "node value")
         if (allocated(error)) return
      end do
   end subroutine test_nodes_reproduced

   !> Lagrange interpolation through N points is exact for polynomials of degree < N.
   subroutine test_polynomial_exactness(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: x(4), y(4)
      type(lagrange_result) :: res
      integer :: i

      x = [-1.0_wp, 0.5_wp, 2.0_wp, 3.0_wp]
      do i = 1, 4
         y(i) = cubic(x(i))
      end do
      res = lagrange(x, y, 1.25_wp)
      call check_close(error, res%value, cubic(1.25_wp), 1.0e3_wp*epsilon(1.0_wp), "cubic")
      if (allocated(error)) return
      ! A quadratic through three points, evaluated outside the nodes (extrapolation).
      res = lagrange(x(1:3), x(1:3)**2, 4.0_wp)
      call check_close(error, res%value, 16.0_wp, 1.0e3_wp*epsilon(1.0_wp), "quadratic")
   contains
      pure real(wp) function cubic(t)
         real(wp), intent(in) :: t
         cubic = 2.0_wp*t**3 - t**2 + 0.5_wp*t - 3.0_wp
      end function cubic
   end subroutine test_polynomial_exactness

   !> N = 1: the interpolant is the constant Y(1); the inner loop multiplies nothing.
   subroutine test_single_point(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange([3.0_wp], [7.0_wp], 100.0_wp)
      call check(error, res%status, status_ok)
      if (allocated(error)) return
      call check(error, same(res%value, 7.0_wp), "constant interpolant")
      if (allocated(error)) return
      call check(error, res%iterations, 1)
      if (allocated(error)) return
      call check(error, size(res%steps), 1)
   end subroutine test_single_point

   !> N = 2: the straight line, also outside the nodes.
   subroutine test_two_points(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange([1.0_wp, 3.0_wp], [2.0_wp, 6.0_wp], 5.0_wp)
      call check_close(error, res%value, 10.0_wp, 10*epsilon(1.0_wp), "line at 5")
   end subroutine test_two_points

   !> N = 10 (the DIMENSION) is accepted.
   subroutine test_ten_points(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: x(max_points)
      type(lagrange_result) :: res
      integer :: i

      x = [(real(i, wp), i = 1, max_points)]
      res = lagrange(x, 2.0_wp*x + 1.0_wp, 4.5_wp)
      call check(error, res%status, status_ok)
      if (allocated(error)) return
      call check(error, res%iterations, max_points)
      if (allocated(error)) return
      call check_close(error, res%value, 10.0_wp, 1.0e4_wp*epsilon(1.0_wp), "line, 10 points")
   end subroutine test_ten_points

   subroutine test_zero_points(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: empty(0)
      type(lagrange_result) :: res

      res = lagrange(empty, empty, 1.0_wp)
      call check(error, res%status, status_degree_error)
      if (allocated(error)) return
      call check(error, res%n, 0)
      if (allocated(error)) return
      call check(error, size(res%steps), 0)
      if (allocated(error)) return
      call check(error, .not. res%converged, "not converged")
   end subroutine test_zero_points

   subroutine test_eleven_points(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: x(max_points + 1)
      type(lagrange_result) :: res
      integer :: i

      x = [(real(i, wp), i = 1, max_points + 1)]
      res = lagrange(x, x, 1.5_wp)
      call check(error, res%status, status_degree_error)
      if (allocated(error)) return
      call check(error, res%n, max_points + 1)
   end subroutine test_eleven_points

   subroutine test_size_mismatch(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange([1.0_wp, 2.0_wp], [1.0_wp], 1.5_wp)
      call check(error, res%status, status_size_mismatch)
   end subroutine test_size_mismatch

   !> Equal X values divide by zero in the original; here the first equal pair is reported.
   subroutine test_duplicate_x(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res

      res = lagrange([1.0_wp, 2.0_wp, 3.0_wp, 2.0_wp], [1.0_wp, 2.0_wp, 3.0_wp, 4.0_wp], 0.0_wp)
      call check(error, res%status, status_duplicate_x)
      if (allocated(error)) return
      call check(error, res%dup_i, 2)
      if (allocated(error)) return
      call check(error, res%dup_j, 4)
      if (allocated(error)) return
      call check(error, size(res%steps), 0)
      if (allocated(error)) return
      ! -0.0 and +0.0 are equal X values as well.
      res = lagrange([0.0_wp, -0.0_wp], [1.0_wp, 2.0_wp], 1.0_wp)
      call check(error, res%status, status_duplicate_x)
   end subroutine test_duplicate_x

   !> A term that overflows stops the run with the rows completed before it.
   subroutine test_overflow(error)
      type(error_type), allocatable, intent(out) :: error
      type(lagrange_result) :: res
      real(wp) :: big

      big = huge(1.0_wp)/4
      res = lagrange([1.0_wp, 2.0_wp], [1.0_wp, 4.0_wp*big], 1.5_wp*big)
      call check(error, res%status, status_invalid_value)
      if (allocated(error)) return
      call check(error, res%iterations, 1)
      if (allocated(error)) return
      call check(error, size(res%steps), 1)
      if (allocated(error)) return
      call check(error, same(res%value, res%steps(1)%partial), "value = last finite partial sum")
   end subroutine test_overflow

   subroutine test_status_names(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, status_name(status_ok), "ok")
      if (allocated(error)) return
      call check(error, status_name(status_degree_error), "degree_error")
      if (allocated(error)) return
      call check(error, status_name(status_size_mismatch), "size_mismatch")
      if (allocated(error)) return
      call check(error, status_name(status_duplicate_x), "duplicate_x")
      if (allocated(error)) return
      call check(error, status_name(status_invalid_value), "invalid_value")
      if (allocated(error)) return
      call check(error, status_name(-1), "unknown")
   end subroutine test_status_names

end module test_lagrange_suite
