!> Simpson's 1/3 rule, C. F. Gerald, Applied Numerical Analysis, Ch. 3, Program 1.
!>
!> `simpson(f, b, n, f0)` is the computational core of the book program with all I/O removed:
!> the integral of `f` from 0 to `b` over `n` panels. It mirrors the scan statement for
!> statement, including the order in which the ordinates are summed, because that order fixes
!> the last digits of the single-precision (book) result:
!>
!>          NHALF = N/2
!>          IF (N - 2*NHALF) 99,1,99            N odd -> message 200 and CALL EXIT
!>        1 XN = N
!>          DELX = B/XN
!>          SUM = 1.0 + 4.*F(DELX) + F(B)       first, second and last ordinates
!>          X = 2.*DELX
!>          DO 10 I = 2,NHALF
!>          SUM = SUM + 2.*F(X) + 4.*F(X+DELX)  the rest, in (weight 2, weight 4) pairs
!>       10 X = X + 2.*DELX                     X accumulates (it is not recomputed as I*DELX)
!>          SININT = DELX/3.*SUM                (DELX/3.)*SUM, left to right
!>
!> The seed `1.0` of the sum is the book's value of F(0): F(X) = SINF(X)/X cannot be evaluated
!> at X = 0, so the listing writes its limit, 1, as a literal. For any integrand the term is
!> F(0) with weight 1. `f0` (optional) is that seed; without it the module evaluates `f(0)`.
!> For preset 1 (`f_sinc`, which returns exactly 1 at 0) both give the same bits.
!>
!> Branch map (book label -> result):
!>   99 N odd              -> status_odd_panels (book message 200), no ordinates evaluated
!>   N < 2 (N = 0 or a negative even N; the book divides by zero at DELX = B/XN)
!>                         -> status_invalid_input (INPUT; no book message)
!>   1 .. SININT           -> status_ok, converged, value = SININT, iterations = N + 1
!>   F not finite          -> status_invalid_value (INPUT; NaN or +-Inf, impossible as an IEEE
!>                            special on the original machine). Checked after each evaluation,
!>                            in the book's evaluation order; steps = the ordinates evaluated
!>                            before it (sorted by k), value = the offending X.
!>
!> Modern loop semantics: the DO loop is zero-trip, so N = 2 (NHALF = 1) skips the loop and gives
!> the three-ordinate Simpson rule. A FORTRAN II/IV processor executes a DO body at least once,
!> so on the original machine N = 2 would have added F(2*DELX) and F(3*DELX), ordinates beyond
!> B -- which is why the listing's comment asks for "N GREATER THAN 2".
module simpson_mod
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp
   use functions_mod, only: real_function
   implicit none
   private

   public :: simpson, simpson_result, simpson_step, status_name

   !> Largest accepted number of panels (one step record is kept per ordinate).
   integer, parameter, public :: max_panels = 1000000

   !> Status codes of `simpson_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_odd_panels = 1
      enumerator :: status_invalid_input = 2
      enumerator :: status_invalid_value = 3
   end enum
   public :: status_ok, status_odd_panels, status_invalid_input, status_invalid_value

   !> One ordinate of the Simpson sum: index k (0..N), abscissa X, F(X) and its weight 1, 4 or 2.
   type :: simpson_step
      integer :: k = 0
      real(wp) :: x = 0.0_wp
      real(wp) :: fx = 0.0_wp
      real(wp) :: weight = 0.0_wp
   end type simpson_step

   !> Outcome of `simpson`.
   type :: simpson_result
      !> SININT = DELX/3.*SUM (status_ok); the offending X for status_invalid_value; else 0.
      real(wp) :: value = 0.0_wp
      !> True for status_ok (the rule is not iterative; it always "converges").
      logical :: converged = .false.
      !> Ordinates evaluated: N + 1 on success (equals size(steps)).
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> DELX = B/XN, the panel width.
      real(wp) :: delx = 0.0_wp
      !> SUM, the weighted sum of the ordinates before the DELX/3 factor.
      real(wp) :: sum = 0.0_wp
      !> The ordinates, sorted by k.
      type(simpson_step), allocatable :: steps(:)
   end type simpson_result

contains

   !> Lower-case name of a status code (for diagnostics and tests).
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_odd_panels)
         name = "odd_panels"
      case (status_invalid_input)
         name = "invalid_input"
      case (status_invalid_value)
         name = "invalid_value"
      case default
         name = "unknown"
      end select
   end function status_name

   !> Integral of `f` from 0 to `b` by Simpson's 1/3 rule with `n` panels, as the book computes it.
   !>
   !> `f0` is the ordinate at X = 0 (the book's literal seed `1.0`); when absent, `f(0)` is used.
   function simpson(f, b, n, f0) result(res)
      procedure(real_function) :: f
      real(wp), intent(in) :: b
      integer, intent(in) :: n
      real(wp), intent(in), optional :: f0
      type(simpson_result) :: res

      type(simpson_step), allocatable :: rows(:)
      logical, allocatable :: done(:)
      real(wp) :: xn, delx, x, total, y0, y1, yb, ya, yc
      integer :: nhalf, i
      logical :: ok

      res%converged = .false.
      res%iterations = 0
      allocate (res%steps(0))

      ! NHALF = N/2;  IF (N - 2*NHALF) 99,1,99
      nhalf = n/2
      if (n - 2*nhalf /= 0) then
         res%status = status_odd_panels
         return
      end if
      if (n < 2 .or. n > max_panels) then
         res%status = status_invalid_input
         return
      end if

      allocate (rows(0:n), done(0:n))
      done = .false.

      ! 1 XN = N;  DELX = B/XN
      xn = real(n, wp)
      delx = b/xn
      res%delx = delx

      ! SUM = 1.0 + 4.*F(DELX) + F(B)
      if (present(f0)) then
         y0 = f0
      else
         y0 = f(0.0_wp)
      end if
      call store(0, 0.0_wp, y0, 1.0_wp, ok)
      if (.not. ok) return
      y1 = f(delx)
      call store(1, delx, y1, 4.0_wp, ok)
      if (.not. ok) return
      yb = f(b)
      call store(n, b, yb, 1.0_wp, ok)
      if (.not. ok) return
      total = y0 + 4.0_wp*y1 + yb

      ! X = 2.*DELX;  DO 10 I = 2,NHALF
      x = 2.0_wp*delx
      do i = 2, nhalf
         ! SUM = SUM + 2.*F(X) + 4.*F(X+DELX)
         ya = f(x)
         call store(2*i - 2, x, ya, 2.0_wp, ok)
         if (.not. ok) return
         yc = f(x + delx)
         call store(2*i - 1, x + delx, yc, 4.0_wp, ok)
         if (.not. ok) return
         total = total + 2.0_wp*ya + 4.0_wp*yc
         ! 10 X = X + 2.*DELX
         x = x + 2.0_wp*delx
      end do

      ! SININT = DELX/3.*SUM
      res%sum = total
      res%value = delx/3.0_wp*total
      res%status = status_ok
      res%converged = .true.
      res%iterations = n + 1
      res%steps = rows(0:n)

   contains

      !> Store ordinate k; on a non-finite F(X) end the run as status_invalid_value.
      subroutine store(k, xk, fk, weight, ok)
         integer, intent(in) :: k
         real(wp), intent(in) :: xk, fk, weight
         logical, intent(out) :: ok

         ok = ieee_is_finite(fk)
         if (.not. ok) then
            res%status = status_invalid_value
            res%value = xk
            res%steps = pack(rows(0:n), done(0:n))
            res%iterations = size(res%steps)
            return
         end if
         rows(k) = simpson_step(k=k, x=xk, fx=fk, weight=weight)
         done(k) = .true.
      end subroutine store

   end function simpson

end module simpson_mod
