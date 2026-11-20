!> Derivatives by central differences, C. F. Gerald, Applied Numerical Analysis, Ch. 4, Program 1.
!>
!> `central_difference(f, x, h, n_rows)` is the computational core of the book program with all
!> I/O removed: estimates of F'(X) and F''(X) for `n_rows` (the book: 10) values of H, H being
!> divided by ten after every row. It mirrors the scan (book p. 90) statement for statement,
!> keeping the order and grouping of every operation so the two engines agree bit for bit:
!>
!>          FO = F(X)                         once, before the loop (FO: the letter O)
!>          DO 10 I = 1,10
!>          FR = F(X + H)
!>          FL = F(X - H)
!>          DX = (FR - FL)/(2.*H)
!>          DDX = (FR - 2.*FO + FL)/H**2      ((FR - 2*FO) + FL)/(H*H), left to right
!>          PRINT 201, H, DX, DDX             -> one derivative_step per row
!>       10 H = 0.1*H                         accumulated, with a literal of kind wp
!>
!> Branch map (book statement -> result):
!>   DO 10 .. 10 H = 0.1*H, ten rows   -> status_ok, converged (there is no stopping test),
!>                                        value = DX of the last row, iterations = n_rows
!>   X or H not finite, H <= 0, n_rows < 1 (the book divides by zero for H = 0)
!>                                     -> status_invalid_input (INPUT), nothing evaluated
!>   FO, FR or FL not finite           -> status_invalid_value (INPUT; NaN or +-Inf, impossible
!>                                        as an IEEE special on the original machine),
!>                                        failed_at = the offending argument, steps = the rows
!>                                        computed before it
!>   DX or DDX not finite (overflow, or H*H underflowing to 0, which is tested before the
!>   division)                         -> status_invalid_estimate (INPUT), failed_at = H of the
!>                                        row, failed_row = its number, steps = the rows before
module derivative_mod
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
   use precision, only: wp
   use functions_mod, only: real_function
   implicit none
   private

   public :: central_difference, derivative_result, derivative_step, status_name

   !> `DO 10 I = 1,10`: the number of rows the book prints.
   integer, parameter, public :: book_rows = 10

   !> `10 H = 0.1*H`: the factor applied to H after every row (a literal of kind wp, so the
   !> real64 build multiplies by the double nearest to 0.1, as the Python engine does).
   real(wp), parameter, public :: h_factor = 0.1_wp

   !> Status codes of `derivative_result%status`.
   enum, bind(c)
      enumerator :: status_ok = 0
      enumerator :: status_invalid_input = 1
      enumerator :: status_invalid_value = 2
      enumerator :: status_invalid_estimate = 3
   end enum
   public :: status_ok, status_invalid_input, status_invalid_value, status_invalid_estimate

   !> Which evaluation failed for status_invalid_value.
   enum, bind(c)
      enumerator :: which_none = 0
      enumerator :: which_fo = 1
      enumerator :: which_fr = 2
      enumerator :: which_fl = 3
   end enum
   public :: which_none, which_fo, which_fr, which_fl

   !> One printed row (format 201): row number k (the DO index I), H, DX and DDX.
   type :: derivative_step
      integer :: k = 0
      real(wp) :: h = 0.0_wp
      real(wp) :: dx = 0.0_wp
      real(wp) :: ddx = 0.0_wp
   end type derivative_step

   !> Outcome of `central_difference`.
   type :: derivative_result
      !> DX of the last row (status_ok); 0 otherwise.
      real(wp) :: value = 0.0_wp
      !> True for status_ok (the program has no stopping test).
      logical :: converged = .false.
      !> Rows computed (equals size(steps)); n_rows on success.
      integer :: iterations = 0
      !> One of the status_* enumerators.
      integer :: status = status_ok
      !> FO = F(X), the centre value of every DDX.
      real(wp) :: fo = 0.0_wp
      !> DX and DDX of the first row (H as on the data card) and DDX of the last row.
      real(wp) :: first_dx = 0.0_wp
      real(wp) :: first_ddx = 0.0_wp
      real(wp) :: last_ddx = 0.0_wp
      !> status_invalid_value: the argument of the non-finite F; status_invalid_estimate: H.
      real(wp) :: failed_at = 0.0_wp
      !> status_invalid_value: which_fo, which_fr or which_fl.
      integer :: failed_which = which_none
      !> status_invalid_estimate: the row whose DX or DDX is not finite.
      integer :: failed_row = 0
      !> The rows computed, k = 1..iterations.
      type(derivative_step), allocatable :: steps(:)
   end type derivative_result

contains

   !> Lower-case name of a status code (for diagnostics and tests).
   pure function status_name(status) result(name)
      integer, intent(in) :: status
      character(len=:), allocatable :: name

      select case (status)
      case (status_ok)
         name = "ok"
      case (status_invalid_input)
         name = "invalid_input"
      case (status_invalid_value)
         name = "invalid_value"
      case (status_invalid_estimate)
         name = "invalid_estimate"
      case default
         name = "unknown"
      end select
   end function status_name

   !> F'(X) and F''(X) by central differences for `n_rows` decreasing H (default `book_rows`),
   !> as the book computes them. Row k uses H = h*0.1**(k-1), accumulated by H = 0.1*H.
   function central_difference(f, x, h, n_rows) result(res)
      procedure(real_function) :: f
      real(wp), intent(in) :: x, h
      integer, intent(in), optional :: n_rows
      type(derivative_result) :: res

      type(derivative_step), allocatable :: rows(:)
      real(wp) :: step, fo, fr, fl, dx, ddx, denominator
      integer :: rows_wanted, k

      res%converged = .false.
      res%iterations = 0
      allocate (res%steps(0))

      rows_wanted = book_rows
      if (present(n_rows)) rows_wanted = n_rows
      if (rows_wanted < 1 .or. .not. ieee_is_finite(x) .or. .not. ieee_is_finite(h)) then
         res%status = status_invalid_input
         return
      end if
      if (.not. h > 0.0_wp) then
         res%status = status_invalid_input
         return
      end if

      allocate (rows(rows_wanted))

      ! FO = F(X)
      fo = f(x)
      if (.not. ieee_is_finite(fo)) then
         call fail_value(which_fo, x, 0)
         return
      end if
      res%fo = fo

      step = h
      do k = 1, rows_wanted
         ! FR = F(X + H)
         fr = f(x + step)
         if (.not. ieee_is_finite(fr)) then
            call fail_value(which_fr, x + step, k - 1)
            return
         end if
         ! FL = F(X - H)
         fl = f(x - step)
         if (.not. ieee_is_finite(fl)) then
            call fail_value(which_fl, x - step, k - 1)
            return
         end if
         ! DX = (FR - FL)/(2.*H)
         dx = (fr - fl)/(2.0_wp*step)
         ! DDX = (FR - 2.*FO + FL)/H**2; H**2 is H*H, and H*H = 0 (underflow) is tested first
         denominator = step*step
         if (denominator > 0.0_wp) then
            ddx = ((fr - 2.0_wp*fo) + fl)/denominator
         else
            ddx = huge(1.0_wp)
         end if
         if (.not. (denominator > 0.0_wp .and. ieee_is_finite(dx) .and. ieee_is_finite(ddx))) then
            res%status = status_invalid_estimate
            res%failed_at = step
            res%failed_row = k
            res%steps = rows(1:k - 1)
            res%iterations = k - 1
            return
         end if
         ! PRINT 201, H, DX, DDX
         rows(k) = derivative_step(k=k, h=step, dx=dx, ddx=ddx)
         ! 10 H = 0.1*H
         step = h_factor*step
      end do

      res%status = status_ok
      res%converged = .true.
      res%iterations = rows_wanted
      res%steps = rows
      res%value = rows(rows_wanted)%dx
      res%first_dx = rows(1)%dx
      res%first_ddx = rows(1)%ddx
      res%last_ddx = rows(rows_wanted)%ddx

   contains

      !> End the run as status_invalid_value, keeping the `done` rows computed so far.
      subroutine fail_value(which, at, done)
         integer, intent(in) :: which, done
         real(wp), intent(in) :: at

         res%status = status_invalid_value
         res%failed_which = which
         res%failed_at = at
         res%steps = rows(1:done)
         res%iterations = done
      end subroutine fail_value

   end function central_difference

end module derivative_mod
