!> Quadratic factors of a polynomial (degree 2 to 6) by Bairstow's method,
!> C. F. Gerald, Applied Numerical Analysis, Ch. 1, Program 2 (book p. 25).
!>
!> `bairstow(coeffs, r1, s1, test, lim, n)` is the computational core of the book program with
!> all I/O removed. `coeffs` is the first data card (A(3) ... A(9): the coefficients of X**6
!> down to X**0), `r1, s1, test, lim, n` the second card. It follows the scan's control flow
!> label for label:
!>
!>          B(1) = 0., B(2) = 0., C(1) = 0., C(2) = 0., R = R1, S = S1
!>       11 KOUNT = 1
!>       16 DO 8 J = 3,9
!>          B(J) = A(J) + R*B(J - 1) + S*B(J - 2)
!>        8 C(J) = B(J) + R*C(J - 1) + S*C(J - 2)
!>          DENOM = C(7)*C(7) - C(8)*C(6)
!>          IF ( DENOM) 9, 10, 9
!>       10 R1 = R1 + 1.           (original bug: see below)
!>          S1 = S1 + 1.
!>          GO TO 11
!>        9 DELR = (-B(8)*C(7) + C(6)*B(9))/DENOM
!>          DELS = (-C(7)*B(9) + B(8)*C(8))/DENOM
!>          R = DELR + R
!>          S = DELS + S
!>          IF ( ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13
!>       13 IF (KOUNT - LIM) 14, 15, 15
!>       15 PRINT 24, LIM          -> status_non_convergent
!>       14 KOUNT = KOUNT + 1
!>          GO TO 16
!>       12 PRINT 17, R, S         -> factor kind quadratic (r, s)
!>          N = N - 2
!>          IF (N - 2) 18, 19, 20
!>       20 DO 21 K = 3,9
!>       21 A(K) = B(K - 2)        reduced polynomial; R and S are NOT reset
!>          GO TO 11
!>       19 PRINT 22, B(5), B(6), B(7)   -> factor kind final_quadratic (a2, a1, a0)
!>       18 PRINT 23, B(6), B(7)         -> factor kind linear (a1, a0)
!>
!> Corrections and modernizations (also in the driver's ERRATA header):
!> * Original bug, corrected: label 10 increments R1 and S1, but GO TO 11 never reloads R and S
!>   from them, so an exactly zero DENOM repeated the same computation forever. Here the
!>   working R and S are incremented by 1 (the book text: "the r and s values are arbitrarily
!>   incremented by one"), and, as GO TO 11 does, KOUNT restarts at 1.
!> * DENOM is tested for an exact zero, as the arithmetic IF does (no epsilon; the earlier
!>   rewrite used |DENOM| < epsilon). A NaN DENOM takes the nonzero branch.
!> * Termination guard (no book equivalent): the nudge can repeat forever when DENOM stays zero
!>   (for example an all-zero polynomial). More than max(LIM, 0) nudges while searching for one
!>   factor ends the run as non-convergent with the book's message 24.
!> * Degree check (no book equivalent): N outside 2..6 (the book would index A(9-N) outside
!>   the array) and a nonzero coefficient of a power above N (the book would factor a different
!>   polynomial from the one it printed) are status_degree_error.
!> * The factor printed as "X**2 + R X + S" (FORMAT 17) is, by the recurrence, the divisor
!>   X**2 - R*X - S. The record keeps the printed R and S; `factor_roots` uses the true divisor.
module bairstow_mod
   use precision, only: wp
   implicit none
   private

   public :: bairstow, bairstow_result, bairstow_step, bairstow_factor
   public :: factor_roots, status_name, factor_kind_name, is_exact_zero

   !> Number of coefficients on the first data card (X**6 ... X**0) and the degree range.
   integer, parameter, public :: n_coeffs = 7
   integer, parameter, public :: min_degree = 2
   integer, parameter, public :: max_degree = 6

   !> Status codes of `bairstow_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_non_convergent = 1
      enumerator :: status_degree_error = 2
   end enum
   public :: status_ok, status_non_convergent, status_degree_error

   !> Kinds of `bairstow_factor%kind` (trace FACTOR records: kind=quadratic|final_quadratic|linear).
   enum, bind(c)
      enumerator :: factor_quadratic = 1
      enumerator :: factor_final_quadratic = 2
      enumerator :: factor_linear = 3
   end enum
   public :: factor_quadratic, factor_final_quadratic, factor_linear

   !> Reasons for status_degree_error (`bairstow_result%degree_problem`).
   enum, bind(c)
      enumerator :: degree_ok = 0
      enumerator :: degree_out_of_range = 1
      enumerator :: degree_high_coefficient = 2
   end enum
   public :: degree_ok, degree_out_of_range, degree_high_coefficient

   !> One Bairstow correction: factor index, KOUNT, the updated R and S, and DELR, DELS.
   type :: bairstow_step
      integer :: factor = 0
      integer :: k = 0
      real(wp) :: r = 0.0_wp
      real(wp) :: s = 0.0_wp
      real(wp) :: delr = 0.0_wp
      real(wp) :: dels = 0.0_wp
   end type bairstow_step

   !> One printed factor. quadratic: coef(1:2) = R, S (FORMAT 17, the divisor is X**2 - R X - S);
   !> final_quadratic: coef(1:3) = B(5), B(6), B(7) (FORMAT 22); linear: coef(1:2) = B(6), B(7)
   !> (FORMAT 23). `ncoef` is the number of meaningful entries of `coef`.
   type :: bairstow_factor
      integer :: kind = factor_quadratic
      integer :: ncoef = 0
      real(wp) :: coef(3) = 0.0_wp
   end type bairstow_factor

   !> Outcome of `bairstow`.
   type :: bairstow_result
      !> Number of factors printed (quadratic factors plus the final one); 0 on an error.
      integer :: value = 0
      !> True for status_ok.
      logical :: converged = .false.
      !> Total number of Bairstow corrections (= size(steps)).
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> Zero-denominator nudges (R = R + 1, S = S + 1) taken during the whole run.
      integer :: nudges = 0
      !> degree_* reason when status = status_degree_error.
      integer :: degree_problem = degree_ok
      !> For degree_high_coefficient: the power of X whose coefficient is not zero.
      integer :: bad_power = -1
      !> All corrections in order, and the factors found (on non-convergence: those before it).
      type(bairstow_step), allocatable :: steps(:)
      type(bairstow_factor), allocatable :: factors(:)
   end type bairstow_result

contains

   !> Exact zero test of an arithmetic IF's zero branch (both signed zeros; NaN is not zero).
   !> Written without `==` so -Wcompare-reals stays quiet.
   pure logical function is_exact_zero(v)
      real(wp), intent(in) :: v

      is_exact_zero = v >= 0.0_wp .and. v <= 0.0_wp
   end function is_exact_zero

   !> Lower-case name of a status code.
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_non_convergent)
         name = "non_convergent"
      case (status_degree_error)
         name = "degree_error"
      case default
         name = "unknown"
      end select
   end function status_name

   !> Trace spelling of a factor kind.
   pure function factor_kind_name(kind) result(name)
      integer, intent(in) :: kind
      character(len=:), allocatable :: name

      select case (kind)
      case (factor_quadratic)
         name = "quadratic"
      case (factor_final_quadratic)
         name = "final_quadratic"
      case (factor_linear)
         name = "linear"
      case default
         name = "unknown"
      end select
   end function factor_kind_name

   !> Factor the polynomial of the data cards exactly as the book program does.
   !>
   !> `coeffs(1:7)` are the coefficients of X**6 ... X**0 (card 1); `r1`, `s1` the starting
   !> R and S, `test` the bound on |DELR| + |DELS|, `lim` the iteration limit per factor and
   !> `n` the degree (card 2).
   function bairstow(coeffs, r1, s1, test, lim, n) result(res)
      real(wp), intent(in) :: coeffs(n_coeffs)
      real(wp), intent(in) :: r1, s1, test
      integer, intent(in) :: lim, n
      type(bairstow_result) :: res

      real(wp) :: a(9), b(9), c(9)
      real(wp) :: r, s, denom, delr, dels
      type(bairstow_step), allocatable :: steps(:)
      type(bairstow_factor), allocatable :: factors(:)
      integer :: degree, kount, j, power, factor, nsteps, nudges_here

      allocate (res%steps(0), res%factors(0), factors(0))
      res%converged = .false.

      if (n < min_degree .or. n > max_degree) then
         res%status = status_degree_error
         res%degree_problem = degree_out_of_range
         return
      end if
      ! A(3) ... A(9) hold X**6 ... X**0; the powers above N must have zero coefficients.
      do power = max_degree, n + 1, -1
         if (.not. is_exact_zero(coeffs(n_coeffs - power))) then
            res%status = status_degree_error
            res%degree_problem = degree_high_coefficient
            res%bad_power = power
            return
         end if
      end do

      a = 0.0_wp
      a(3:9) = coeffs
      b = 0.0_wp
      c = 0.0_wp
      r = r1
      s = s1
      degree = n
      factor = 1
      nsteps = 0
      allocate (steps(max(lim, 1)))

      factors_loop: do
         ! 11 KOUNT = 1
         kount = 1
         nudges_here = 0
         corrections: do
            ! 16 DO 8 J = 3,9
            do j = 3, 9
               b(j) = a(j) + r*b(j - 1) + s*b(j - 2)
               c(j) = b(j) + r*c(j - 1) + s*c(j - 2)
            end do
            denom = c(7)*c(7) - c(8)*c(6)
            ! IF ( DENOM) 9, 10, 9
            if (is_exact_zero(denom)) then
               ! 10: nudge the working R and S (the original bumped R1, S1) and GO TO 11.
               nudges_here = nudges_here + 1
               res%nudges = res%nudges + 1
               if (nudges_here > max(lim, 0)) then
                  call fail_non_convergent()
                  return
               end if
               r = r + 1.0_wp
               s = s + 1.0_wp
               kount = 1
               cycle corrections
            end if
            ! 9: corrections
            delr = (-b(8)*c(7) + c(6)*b(9))/denom
            dels = (-c(7)*b(9) + b(8)*c(8))/denom
            r = delr + r
            s = dels + s
            call add_step(bairstow_step(factor=factor, k=kount, r=r, s=s, delr=delr, dels=dels))
            ! IF ( ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13
            if (abs(delr) + abs(dels) - test <= 0.0_wp) exit corrections
            ! 13 IF (KOUNT - LIM) 14, 15, 15
            if (kount - lim >= 0) then
               call fail_non_convergent()
               return
            end if
            ! 14 KOUNT = KOUNT + 1, GO TO 16
            kount = kount + 1
         end do corrections

         ! 12 PRINT 17, R, S
         factors = [factors, bairstow_factor(kind=factor_quadratic, ncoef=2, &
            coef=[r, s, 0.0_wp])]
         ! N = N - 2;  IF (N - 2) 18, 19, 20
         degree = degree - 2
         if (degree - 2 > 0) then
            ! 20/21: the quotient becomes the polynomial; R and S carry over.
            do j = 3, 9
               a(j) = b(j - 2)
            end do
            factor = factor + 1
            cycle factors_loop
         else if (degree - 2 == 0) then
            ! 19 PRINT 22, B(5), B(6), B(7)
            factors = [factors, bairstow_factor(kind=factor_final_quadratic, ncoef=3, &
               coef=[b(5), b(6), b(7)])]
         else
            ! 18 PRINT 23, B(6), B(7)
            factors = [factors, bairstow_factor(kind=factor_linear, ncoef=2, &
               coef=[b(6), b(7), 0.0_wp])]
         end if
         exit factors_loop
      end do factors_loop

      res%status = status_ok
      res%converged = .true.
      res%value = size(factors)
      res%iterations = nsteps
      res%steps = steps(1:nsteps)
      res%factors = factors

   contains

      !> Append one correction, growing the buffer when needed.
      subroutine add_step(step)
         type(bairstow_step), intent(in) :: step
         type(bairstow_step), allocatable :: grown(:)

         if (nsteps == size(steps)) then
            allocate (grown(2*size(steps)))
            grown(1:nsteps) = steps(1:nsteps)
            call move_alloc(grown, steps)
         end if
         nsteps = nsteps + 1
         steps(nsteps) = step
      end subroutine add_step

      !> 15 PRINT 24, LIM: the factors found so far stay in the result.
      subroutine fail_non_convergent()
         res%status = status_non_convergent
         res%converged = .false.
         res%value = 0
         res%iterations = nsteps
         res%steps = steps(1:nsteps)
         res%factors = factors
      end subroutine fail_non_convergent

   end function bairstow

   !> Roots of a printed factor (the true factor: X**2 - R X - S for kind quadratic).
   !>
   !> Returns `nroots` (0, 1 or 2) roots in `roots`. The arithmetic is the one the Python engine
   !> uses (gerald_na.algorithms.bairstow.factor_roots), so both print identical --verbose text:
   !> quadratic  D = R*R + 4*S;  D >= 0: (R + SQRT(D))/2, (R - SQRT(D))/2,
   !>            else R/2 +- i SQRT(-D)/2;
   !> final_quadratic A2 X**2 + A1 X + A0 (linear when A2 = 0): D = A1*A1 - 4*A2*A0;
   !>            D >= 0: (-A1 + SQRT(D))/(2*A2), (-A1 - SQRT(D))/(2*A2),
   !>            else -A1/(2*A2) +- i SQRT(-D)/(2*A2);
   !> linear     A1 X + A0: -A0/A1, no root when A1 = 0 (a constant factor).
   pure subroutine factor_roots(f, roots, nroots)
      type(bairstow_factor), intent(in) :: f
      complex(wp), intent(out) :: roots(2)
      integer, intent(out) :: nroots
      real(wp) :: a2, a1, a0, d
      logical :: is_linear

      roots = (0.0_wp, 0.0_wp)
      nroots = 0
      select case (f%kind)
      case (factor_quadratic)
         ! X**2 - R X - S
         a2 = 1.0_wp
         a1 = -f%coef(1)
         a0 = -f%coef(2)
         is_linear = .false.
      case (factor_final_quadratic)
         a2 = f%coef(1)
         a1 = f%coef(2)
         a0 = f%coef(3)
         is_linear = is_exact_zero(a2)
      case default
         a2 = 0.0_wp
         a1 = f%coef(1)
         a0 = f%coef(2)
         is_linear = .true.
      end select

      if (is_linear) then
         if (is_exact_zero(a1)) return
         nroots = 1
         roots(1) = cmplx(-a0/a1, 0.0_wp, wp)
         return
      end if
      d = a1*a1 - 4.0_wp*a2*a0
      nroots = 2
      if (d >= 0.0_wp) then
         roots(1) = cmplx((-a1 + sqrt(d))/(2.0_wp*a2), 0.0_wp, wp)
         roots(2) = cmplx((-a1 - sqrt(d))/(2.0_wp*a2), 0.0_wp, wp)
      else
         roots(1) = cmplx(-a1/(2.0_wp*a2), sqrt(-d)/(2.0_wp*a2), wp)
         roots(2) = cmplx(-a1/(2.0_wp*a2), -(sqrt(-d)/(2.0_wp*a2)), wp)
      end if
   end subroutine factor_roots

end module bairstow_mod
