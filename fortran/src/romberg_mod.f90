!> Romberg integration, C. F. Gerald, Applied Numerical Analysis, Ch. 3, Program 2.
!>
!> `romberg(f, b, tol)` is the computational core of the book program with all I/O removed.
!> It integrates F from 0 to B: a trapezoidal sum with 10 subintervals, then up to 8 halvings
!> of the step, each followed by Richardson extrapolation of the new column of the table
!> TRAP(9,9). The listing, transcribed from the scan (docs/chapter_03_program_02_listing.pdf),
!> is followed statement for statement:
!>
!>          H = B/10.
!>          SUM = 1. + FCN(B)                      1. is FCN(0), the limit of SIN(X)/X
!>          X = 0.0
!>          DO 10 I = 2,10
!>          X = X + H
!>       10 SUM = SUM + FCN(X)*2.
!>          TRAP(1,1) = H/2.*SUM
!>          DO 20 I = 1,8
!>          H = H/2.
!>          X = H
!>          K = 10.*2.**I
!>          DO 30 J = 2,K,2
!>          SUM = SUM + FCN(X)*2.
!>       30 X = X + H + H
!>          TRAP(1,I+1) = H/2.*SUM
!>          DO 40 II = 1,I
!>       40 TRAP(II+1,I+1) = TRAP(II,I+1) + 1./(4.**II - 1.)*(TRAP(II,I+1) -
!>         1 TRAP(II,I))
!>          IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1))- TOL) 50,50,20
!>       20 CONTINUE
!>
!> TRAP(row, col): `col` is the halving index plus one (column 1 = 10 subintervals, column
!> I+1 = 10*2**I subintervals) and `row` the extrapolation order (row 1 = trapezoidal rule).
!> The book prints the table transposed, one line per column: printed line L is
!> TRAP(1..L, L). Since SUM is never reset, each halving only adds the new midpoints, which
!> sit at the odd multiples of the new H; X advances by H + H.
!>
!> Generalization of the seed: the book seeds SUM with the literal 1., the value of its
!> integrand SIN(X)/X at X = 0 (a removable singularity the statement function cannot
!> evaluate). Here the seed is F0 + F(B), where the optional argument `f0` is the ordinate at
!> X = 0 (the book's 1.) and defaults to F(0) (same convention as simpson_mod). The book's
!> preset (functions_mod: f_sinc) returns the limit 1 at X = 0, so both ways give exactly
!> 1. + FCN(B) for the book run.
!>
!> Every expression keeps the listing's operation order with explicit parentheses
!> ((X + H) + H, (H/2.)*SUM, (1./(4.**II - 1.))*(...)), so the compiler cannot reassociate
!> it and the Python port reproduces every value bit for bit.
!>
!> Outcomes:
!>   label 50, |TRAP(I+1,I+1) - TRAP(I,I+1)| - TOL <= 0 after halving I
!>        -> status_ok, converged, value = TRAP(I+1,I+1), iterations = I, I+1 printed rows,
!>           subintervals = K = 10*2**I (book format 202)
!>   DO 20 exhausted (8 halvings without meeting TOL)
!>        -> status_not_converged: still a result (the book prints the 9x9 table and format
!>           201), converged = .false., value = TRAP(9,9), iterations = 8, 9 rows,
!>           subintervals = 2560
!>   F not finite (NaN or +-Inf; no book equivalent, the original machine had no IEEE
!>   specials) -> status_invalid_value, value = the offending X, steps = the halvings
!>           completed before it. Same rule as the Python engine (InputError).
module romberg_mod
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp
   use functions_mod, only: real_function
   implicit none
   private

   public :: romberg, romberg_result, romberg_step, status_name

   !> The book's limit on halvings ("REPEAT UP TO 8 TIMES", DO 20 I = 1,8).
   integer, parameter, public :: book_max_halvings = 8
   !> Subintervals of the first trapezoidal sum ("WITH 10 SUBINTERVALS").
   integer, parameter, public :: book_first_panels = 10
   !> Size of the table, DIMENSION TRAP(9,9).
   integer, parameter, public :: table_size = book_max_halvings + 1

   !> Status codes of `romberg_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_not_converged = 1
      enumerator :: status_invalid_value = 2
   end enum
   public :: status_ok, status_not_converged, status_invalid_value

   !> One halving (one pass through DO 20): the new column of the table and its test.
   type :: romberg_step
      !> Halving index I (1..8).
      integer :: k = 0
      !> Subintervals of the new trapezoidal sum, K = 10*2**I.
      integer :: panels = 0
      !> Step size H after the halving.
      real(wp) :: h = 0.0_wp
      !> Trapezoidal value TRAP(1,I+1).
      real(wp) :: trap = 0.0_wp
      !> Latest diagonal value TRAP(I+1,I+1), the best estimate so far.
      real(wp) :: best = 0.0_wp
      !> |TRAP(I+1,I+1) - TRAP(I,I+1)|, the quantity compared with TOL.
      real(wp) :: diff = 0.0_wp
   end type romberg_step

   !> Outcome of `romberg`.
   type :: romberg_result
      !> TRAP(I+1,I+1) at convergence, TRAP(9,9) when not converged, the offending X when
      !> F was not finite.
      real(wp) :: value = 0.0_wp
      !> True only when the tolerance was met (status_ok).
      logical :: converged = .false.
      !> Halvings performed (the DO 20 index I at exit).
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> Subintervals of the last trapezoidal sum (the book's K: 80 for the data card).
      integer :: subintervals = book_first_panels
      !> Printed rows of the table (iterations + 1).
      integer :: rows = 0
      !> The table TRAP(row, col); entries with row > col or col > rows are zero.
      real(wp) :: trap(table_size, table_size) = 0.0_wp
      !> One record per halving.
      type(romberg_step), allocatable :: steps(:)
   end type romberg_result

contains

   !> Lower-case name of a status code (for diagnostics and tests).
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_not_converged)
         name = "not_converged"
      case (status_invalid_value)
         name = "invalid_value"
      case default
         name = "unknown"
      end select
   end function status_name

   !> Integrate `f` from 0 to `b` by Romberg's method, exactly as the book program does.
   !>
   !> Stops after halving I when |TRAP(I+1,I+1) - TRAP(I,I+1)| <= `tol`; after 8 halvings
   !> without meeting `tol` the result has `converged = .false.` (not an error).
   !> `f0` is the ordinate at X = 0 (the book's literal seed `1.`); when absent, `f(0)` is used.
   !> A non-finite `f0` is status_invalid_value with value 0 (the X it stands for).
   function romberg(f, b, tol, f0) result(res)
      procedure(real_function) :: f
      real(wp), intent(in) :: b, tol
      real(wp), intent(in), optional :: f0
      type(romberg_result) :: res

      type(romberg_step) :: steps(book_max_halvings)
      real(wp) :: h, x, total, fx
      integer :: i, j, ii, k

      res%converged = .false.
      res%iterations = 0
      res%subintervals = book_first_panels
      res%rows = 0
      res%trap = 0.0_wp

      ! H = B/10.  /  SUM = 1. + FCN(B), generalized to F0 + FCN(B) with F0 = FCN(0) by default
      h = b/real(book_first_panels, wp)
      if (present(f0)) then
         fx = f0
         if (.not. ieee_is_finite(fx)) then
            res%status = status_invalid_value
            res%value = 0.0_wp
            allocate (res%steps(0))
            return
         end if
      else
         if (.not. evaluate(0.0_wp, fx)) return
      end if
      total = fx
      if (.not. evaluate(b, fx)) return
      total = total + fx

      ! X = 0.0 / DO 10 I = 2,10 / X = X + H / 10 SUM = SUM + FCN(X)*2.
      x = 0.0_wp
      do i = 2, book_first_panels
         x = x + h
         if (.not. evaluate(x, fx)) return
         total = total + fx*2.0_wp
      end do
      res%trap(1, 1) = (h/2.0_wp)*total
      res%rows = 1

      do i = 1, book_max_halvings
         ! H = H/2. / X = H / K = 10.*2.**I
         h = h/2.0_wp
         x = h
         k = book_first_panels*2**i
         ! DO 30 J = 2,K,2 / SUM = SUM + FCN(X)*2. / 30 X = X + H + H
         do j = 2, k, 2
            if (.not. evaluate(x, fx)) return
            total = total + fx*2.0_wp
            x = (x + h) + h
         end do
         res%trap(1, i + 1) = (h/2.0_wp)*total
         ! DO 40 II = 1,I: Richardson extrapolation of the new column
         do ii = 1, i
            res%trap(ii + 1, i + 1) = res%trap(ii, i + 1) + &
               (1.0_wp/(4.0_wp**ii - 1.0_wp))*(res%trap(ii, i + 1) - res%trap(ii, i))
         end do

         steps(i) = romberg_step(k=i, panels=k, h=h, trap=res%trap(1, i + 1), &
            best=res%trap(i + 1, i + 1), &
            diff=abs(res%trap(i + 1, i + 1) - res%trap(i, i + 1)))
         res%iterations = i
         res%subintervals = k
         res%rows = i + 1

         ! IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1)) - TOL) 50,50,20
         ! (negative or zero -> 50; positive, or NaN as in bisection_mod's arith_if -> 20)
         if (abs(res%trap(i + 1, i + 1) - res%trap(i, i + 1)) - tol <= 0.0_wp) then
            ! 50: I = I + 1 / PRINT 202, TRAP(I,I), K, TOL
            res%status = status_ok
            res%converged = .true.
            res%value = res%trap(i + 1, i + 1)
            res%steps = steps(1:i)
            return
         end if
      end do

      ! 20 CONTINUE exhausted: PRINT 201, TRAP(9,9), TOL -- tolerance not met
      res%status = status_not_converged
      res%value = res%trap(table_size, table_size)
      res%steps = steps

   contains

      !> F(xv) into fv; on a NaN or infinity record status_invalid_value and return false.
      logical function evaluate(xv, fv) result(ok)
         real(wp), intent(in) :: xv
         real(wp), intent(out) :: fv

         fv = f(xv)
         ok = ieee_is_finite(fv)
         if (.not. ok) then
            res%status = status_invalid_value
            res%value = xv
            res%steps = steps(1:res%iterations)
         end if
      end function evaluate

   end function romberg

end module romberg_mod
