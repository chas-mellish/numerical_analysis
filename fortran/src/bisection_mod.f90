!> Interval halving (bisection), C. F. Gerald, Applied Numerical Analysis, Ch. 1, Program 1.
!>
!> `bisection(f, x1, x2, tol, max_iter)` is the computational core of the book program with all
!> I/O removed. It follows the scan's control flow branch for branch; each of the three
!> arithmetic IFs of the listing,
!>
!>        IF (FX1*FX2) 1, 2, 3          bracket test (negative / zero / positive)
!>        IF (ABSF(FX) - TOL) 8, 8, 9   convergence test
!>        IF (FX*FX1) 10, 11, 12        which half keeps the sign change
!>
!> is expressed with `arith_if`, which returns -1, 0 or +1 for the negative, zero and positive
!> branch, so the exact-zero cases keep their original destinations. The products are formed
!> exactly as in the listing (not replaced by sign comparisons), so a product that underflows
!> to zero still takes the zero branch, as it did on the original machine.
!>
!> Branch map (book label -> result):
!>   1  -> the halving loop (DO 30 I = 1, 25)
!>   2/5 FX1 = 0          -> status_root_at_endpoint, value = X1, iterations = 0
!>   4/7 FX2 = 0          -> status_root_at_endpoint, value = X2, iterations = 0
!>   4/6 product zero, FX1 and FX2 nonzero (underflow) -> status_zero_product_error,
!>                          iterations = 0  (book message 202)
!>   3  product positive  -> status_bracket_error (book message 200)
!>   8  |FX| - TOL <= 0   -> status_ok, converged, value = X, iterations = I (book message 203)
!>   10 FX*FX1 < 0        -> X2 = X
!>   11 FX*FX1 = 0        -> status_zero_product_error, iterations = I >= 1 (book message 205)
!>   12 FX*FX1 > 0        -> X1 = X, FX1 = FX
!>   loop exhausted       -> status_non_convergent, value = last X (book message 204)
!>
!> Correction of an original bug: in the scan, label 5 (`PRINT 201, X1`) has no `CALL EXIT`
!> and falls through to label 4, so F(X1) = 0 with F(X2) /= 0 printed "X1 is a root" and then
!> the 202 "ERROR. FX1 AND FX2 NOT ZERO ..." message. Here F(X1) = 0 is a root at the endpoint
!> (the intent stated by the listing's own comment "WHEN PRODUCT OF FX1*FX2 IS ZERO, X1 OR X2
!> IS A ROOT"). When both F(X1) and F(X2) are zero the original printed both input values as
!> roots; `fx1`/`fx2` in the result let the driver do the same. NaN products (impossible on
!> the original machine) take the positive branch.
module bisection_mod
   use precision, only: wp
   use functions_mod, only: real_function
   implicit none
   private

   public :: bisection, bisection_result, bisection_step
   public :: arith_if, status_name

   !> The book's iteration limit ("LIMIT TO 25 TIMES").
   integer, parameter, public :: book_max_iter = 25

   !> Status codes of `bisection_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_root_at_endpoint = 1
      enumerator :: status_bracket_error = 2
      enumerator :: status_zero_product_error = 3
      enumerator :: status_non_convergent = 4
   end enum
   public :: status_ok, status_root_at_endpoint, status_bracket_error
   public :: status_zero_product_error, status_non_convergent

   !> One row of the iteration table: bracket at the start of iteration `k`, midpoint, F(mid).
   type :: bisection_step
      integer :: k = 0
      real(wp) :: x1 = 0.0_wp
      real(wp) :: x2 = 0.0_wp
      real(wp) :: x = 0.0_wp
      real(wp) :: fx = 0.0_wp
   end type bisection_step

   !> Outcome of `bisection`.
   type :: bisection_result
      !> Root (converged), endpoint root, or last midpoint (zero product in loop, non-convergence).
      real(wp) :: value = 0.0_wp
      !> True for status_ok and status_root_at_endpoint.
      logical :: converged = .false.
      !> Halving iterations performed (0 when the run ended at the bracket test).
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> F at the input endpoints (as computed before the bracket test).
      real(wp) :: fx1 = 0.0_wp
      real(wp) :: fx2 = 0.0_wp
      !> The iteration table, one record per printed "AT X =" line.
      type(bisection_step), allocatable :: steps(:)
   end type bisection_result

contains

   !> Three-way branch of a FORTRAN arithmetic IF: -1 (negative), 0 (zero), +1 (positive).
   !> Both signed zeros take the zero branch; NaN takes the positive branch.
   pure integer function arith_if(v) result(branch)
      real(wp), intent(in) :: v

      if (v < 0.0_wp) then
         branch = -1
      else if (v >= 0.0_wp .and. v <= 0.0_wp) then
         branch = 0
      else
         branch = 1
      end if
   end function arith_if

   !> Lower-case name of a status code (for diagnostics and tests).
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_root_at_endpoint)
         name = "root_at_endpoint"
      case (status_bracket_error)
         name = "bracket_error"
      case (status_zero_product_error)
         name = "zero_product_error"
      case (status_non_convergent)
         name = "non_convergent"
      case default
         name = "unknown"
      end select
   end function status_name

   !> Find a root of `f` in [x1, x2] by interval halving, exactly as the book program does.
   !>
   !> `max_iter` defaults to the book's 25. `tol` is compared with |F(X)| (not with the
   !> bracket width), as in the listing; a negative `tol` can never be met.
   function bisection(f, x1, x2, tol, max_iter) result(res)
      procedure(real_function) :: f
      real(wp), intent(in) :: x1, x2, tol
      integer, intent(in), optional :: max_iter
      type(bisection_result) :: res

      type(bisection_step), allocatable :: steps(:)
      real(wp) :: a, b, fa, x, fx
      integer :: limit, i

      limit = book_max_iter
      if (present(max_iter)) limit = max(max_iter, 0)

      a = x1
      b = x2
      fa = f(a)
      res%fx1 = fa
      res%fx2 = f(b)
      res%converged = .false.
      res%iterations = 0
      allocate (res%steps(0))

      ! IF (FX1*FX2) 1, 2, 3
      select case (arith_if(fa*res%fx2))
      case (1)
         ! 3: TYPE 200 -- not of opposite signs
         res%status = status_bracket_error
         res%value = a
         return
      case (0)
         ! 2: IF (FX1) 4, 5, 4  /  4: IF (FX2) 6, 7, 6
         if (arith_if(fa) == 0) then
            res%status = status_root_at_endpoint
            res%value = a
            res%converged = .true.
         else if (arith_if(res%fx2) == 0) then
            res%status = status_root_at_endpoint
            res%value = b
            res%converged = .true.
         else
            ! 6: PRINT 202 -- product underflowed to zero
            res%status = status_zero_product_error
            res%value = a
         end if
         return
      case default
         ! 1: start the halving process
      end select

      allocate (steps(limit))
      x = a
      do i = 1, limit
         x = (a + b)/2.0_wp
         fx = f(x)
         steps(i) = bisection_step(k=i, x1=a, x2=b, x=x, fx=fx)
         res%iterations = i

         ! IF (ABSF(FX) - TOL) 8, 8, 9
         if (arith_if(abs(fx) - tol) <= 0) then
            ! 8: PRINT 203 -- converged
            res%status = status_ok
            res%value = x
            res%converged = .true.
            res%steps = steps(1:i)
            return
         end if

         ! 9: IF (FX*FX1) 10, 11, 12
         select case (arith_if(fx*fa))
         case (-1)
            ! 10: X2 = X
            b = x
         case (0)
            ! 11: PRINT 205 -- ERROR.
            res%status = status_zero_product_error
            res%value = x
            res%steps = steps(1:i)
            return
         case default
            ! 12: X1 = X, FX1 = FX
            a = x
            fa = fx
         end select
      end do

      ! 30 CONTINUE exhausted: PRINT 204 -- NON-CONVERGENT IN 25 ITERATIONS.
      res%status = status_non_convergent
      res%value = x
      res%steps = steps(1:limit)
   end function bisection

end module bisection_mod
