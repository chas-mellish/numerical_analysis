!> Lagrangian polynomial interpolation (program `lagrange_interpolation`; the book reference
!> is unconfirmed and no scan exists, see fortran/app/lagrange_interpolation.f90).
!>
!> `lagrange(x, y, xin)` is the computational core of the book program with all I/O removed.
!> It follows the corrected listing statement for statement:
!>
!>        YOUT = 0.0
!>        DO 20 I = 1,N
!>        TERM = Y(I)
!>        DO 10 J = 1,N
!>        IF (I-J) 9,10,9
!>      9 TERM = TERM*(XIN - X(J))/(X(I) - X(J))
!>     10 CONTINUE
!>     20 YOUT = YOUT + TERM
!>
!> The integer arithmetic IF only skips J = I (its two nonzero branches both go to 9), so it is
!> written `if (i /= j)`. The product is evaluated left to right with explicit parentheses,
!> `(term*(xin - x(j)))/(x(i) - x(j))`, the order the listing implies and the order the Python
!> engine uses, so both engines agree bit for bit.
!>
!> Status map (no book messages exist for these; the original had no checks):
!>   status_ok             value = YOUT, iterations = N, one step per term
!>   status_degree_error   N outside 1..max_points (DIMENSION X(10), Y(10)) -> DEGREE
!>   status_size_mismatch  size(x) /= size(y)                               -> INPUT
!>   status_duplicate_x    X(dup_i) = X(dup_j), i < j: the original divides by zero
!>                         (X(I) - X(J) = 0); rejected before any term       -> INPUT
!>   status_invalid_value  a term or the sum is NaN or +-Inf (overflow); value = the last
!>                         finite partial sum, steps = the rows before it    -> INPUT
module lagrange_mod
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp
   implicit none
   private

   public :: lagrange, lagrange_result, lagrange_step, status_name

   !> DIMENSION X(10), Y(10): the most data pairs the book's program can hold.
   integer, parameter, public :: max_points = 10

   !> Status codes of `lagrange_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_degree_error = 1
      enumerator :: status_size_mismatch = 2
      enumerator :: status_duplicate_x = 3
      enumerator :: status_invalid_value = 4
   end enum
   public :: status_ok, status_degree_error, status_size_mismatch, status_duplicate_x
   public :: status_invalid_value

   !> One pass through the DO 20 loop: the data pair, TERM = Y(I)*L_I(XIN), YOUT after it.
   type :: lagrange_step
      integer :: i = 0
      real(wp) :: x = 0.0_wp
      real(wp) :: y = 0.0_wp
      real(wp) :: term = 0.0_wp
      real(wp) :: partial = 0.0_wp
   end type lagrange_step

   !> Outcome of `lagrange`.
   type :: lagrange_result
      !> YOUT: the interpolating polynomial evaluated at XIN.
      real(wp) :: value = 0.0_wp
      !> True for status_ok (the method is direct: there is nothing to converge).
      logical :: converged = .false.
      !> Number of terms summed (N on success).
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> Number of data pairs N.
      integer :: n = 0
      !> For status_duplicate_x: the first pair of equal X values, dup_i < dup_j (1-based).
      integer :: dup_i = 0
      integer :: dup_j = 0
      !> The terms, one record per pass through the DO 20 loop.
      type(lagrange_step), allocatable :: steps(:)
   end type lagrange_result

contains

   !> Lower-case name of a status code (for diagnostics and tests).
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_degree_error)
         name = "degree_error"
      case (status_size_mismatch)
         name = "size_mismatch"
      case (status_duplicate_x)
         name = "duplicate_x"
      case (status_invalid_value)
         name = "invalid_value"
      case default
         name = "unknown"
      end select
   end function status_name

   !> Evaluate the Lagrangian polynomial through (x(i), y(i)), i = 1..n, at `xin`.
   function lagrange(x, y, xin) result(res)
      real(wp), intent(in) :: x(:), y(:)
      real(wp), intent(in) :: xin
      type(lagrange_result) :: res

      type(lagrange_step), allocatable :: steps(:)
      real(wp) :: term, yout
      integer :: n, i, j

      n = size(x)
      res%n = n
      res%converged = .false.
      res%iterations = 0
      allocate (res%steps(0))

      if (size(y) /= n) then
         res%status = status_size_mismatch
         return
      end if
      if (n < 1 .or. n > max_points) then
         res%status = status_degree_error
         return
      end if
      ! Equal X values would divide by zero in label 9 (X(I) - X(J) = 0).
      do i = 1, n - 1
         do j = i + 1, n
            if (.not. (x(i) < x(j) .or. x(i) > x(j))) then
               res%status = status_duplicate_x
               res%dup_i = i
               res%dup_j = j
               return
            end if
         end do
      end do

      allocate (steps(n))
      yout = 0.0_wp
      do i = 1, n
         ! DO 20 I = 1,N  /  TERM = Y(I)
         term = y(i)
         do j = 1, n
            ! IF (I-J) 9,10,9
            if (i /= j) then
               ! 9 TERM = TERM*(XIN - X(J))/(X(I) - X(J))
               term = (term*(xin - x(j)))/(x(i) - x(j))
            end if
         end do
         ! 20 YOUT = YOUT + TERM
         yout = yout + term
         if (.not. (ieee_is_finite(term) .and. ieee_is_finite(yout))) then
            res%status = status_invalid_value
            res%iterations = i - 1
            res%steps = steps(1:i - 1)
            res%value = 0.0_wp
            if (i > 1) res%value = steps(i - 1)%partial
            return
         end if
         steps(i) = lagrange_step(i=i, x=x(i), y=y(i), term=term, partial=yout)
      end do

      res%status = status_ok
      res%value = yout
      res%converged = .true.
      res%iterations = n
      res%steps = steps
   end function lagrange

end module lagrange_mod
