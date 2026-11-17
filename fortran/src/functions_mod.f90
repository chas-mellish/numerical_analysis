!> Target functions for the Gerald programs and the numbered presets used by `--preset N`.
!>
!> Every method module receives its function through the abstract interface `real_function`,
!> so the algorithms never hard-code the equation the way the 1970s listings did with an
!> arithmetic statement function ("CHANGE FUNCTION DEFINITION CARD TO SOLVE NEW EQUATION").
!>
!> The preset tables mirror the `[[presets]]` entries of the catalog files
!> (`catalog/ch01_p01_bisection.toml`, ...); preset 1 is always the book's own function.
!> The Python engine evaluates the same expressions through `gerald_na.expr`.
!>
!>   Bisection presets (ch01_p01):
!>     1  EXP(-X) - SIN(3.1415926*X/2.)   the book's function, with the book's PI literal
!>     2  X**3 - X - 1
!>     3  COS(X) - X
!>
!>   Quadrature presets (ch03_p01 Simpson, ch03_p02 Romberg), integrands on [0, B]:
!>     1  SIN(X)/X                         the book's integrand, with the X = 0 limit taken as 1
!>     2  EXP(-X**2)
!>     3  1/(1+X**2)
!>
!> New presets are added by writing one pure function with the `real_function` interface and
!> one `case` in the matching `get_*_preset` routine (plus the catalog entry).
module functions_mod
   use precision, only: wp
   implicit none
   private

   public :: real_function
   public :: get_bisection_preset, get_quadrature_preset
   public :: f_book_bisection, f_cubic, f_cos_minus_x
   public :: f_sinc, f_gauss, f_runge

   abstract interface
      !> A real function of one real variable in working precision.
      pure function real_function(x) result(y)
         import :: wp
         implicit none
         real(wp), intent(in) :: x
         real(wp) :: y
      end function real_function
   end interface

   !> The book writes PI as the literal 3.1415926 (Ch. 1, Program 1); kept for fidelity.
   real(wp), parameter, public :: pi_book = 3.1415926_wp

   !> Number of presets per family (valid ids are 1..count).
   integer, parameter, public :: bisection_preset_count = 3
   integer, parameter, public :: quadrature_preset_count = 3

   !> Fixed length of the preset expression strings (trimmed by callers).
   integer, parameter, public :: preset_expr_len = 64

contains

   ! ---------------------------------------------------------------------------------------
   ! Bisection presets
   ! ---------------------------------------------------------------------------------------

   !> Preset 1, the book's function: F(X) = EXPF(-X) - SINF(3.1415926*X/2.)
   !> The operation order of the scan is kept: (3.1415926*X)/2.
   pure function f_book_bisection(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = exp(-x) - sin(pi_book*x/2.0_wp)
   end function f_book_bisection

   !> Preset 2: x**3 - x - 1 (real root near 1.3247).
   pure function f_cubic(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = x**3 - x - 1.0_wp
   end function f_cubic

   !> Preset 3: cos(x) - x (root near 0.7391).
   pure function f_cos_minus_x(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = cos(x) - x
   end function f_cos_minus_x

   ! ---------------------------------------------------------------------------------------
   ! Quadrature presets (Simpson / Romberg)
   ! ---------------------------------------------------------------------------------------

   !> Preset 1, the book's integrand sin(x)/x, with the removable singularity at x = 0
   !> resolved to its limit 1 (the listings seed their sums with 1. for the same reason).
   pure function f_sinc(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      if (x > 0.0_wp .or. x < 0.0_wp) then
         y = sin(x)/x
      else
         y = 1.0_wp
      end if
   end function f_sinc

   !> Preset 2: exp(-x**2).
   pure function f_gauss(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = exp(-x**2)
   end function f_gauss

   !> Preset 3: 1/(1+x**2).
   pure function f_runge(x) result(y)
      real(wp), intent(in) :: x
      real(wp) :: y
      y = 1.0_wp/(1.0_wp + x**2)
   end function f_runge

   ! ---------------------------------------------------------------------------------------
   ! Preset selection
   ! ---------------------------------------------------------------------------------------

   !> Select a bisection preset. `found` is false (and `f` disassociated) for an unknown id.
   subroutine get_bisection_preset(id, f, expr, found)
      integer, intent(in) :: id
      procedure(real_function), pointer, intent(out) :: f
      character(len=preset_expr_len), intent(out) :: expr
      logical, intent(out) :: found

      found = .true.
      select case (id)
      case (1)
         f => f_book_bisection
         expr = "EXP(-X) - SIN(3.1415926*X/2.)"
      case (2)
         f => f_cubic
         expr = "X**3 - X - 1"
      case (3)
         f => f_cos_minus_x
         expr = "COS(X) - X"
      case default
         f => null()
         expr = ""
         found = .false.
      end select
   end subroutine get_bisection_preset

   !> Select a quadrature (Simpson / Romberg) preset. `found` is false for an unknown id.
   subroutine get_quadrature_preset(id, f, expr, found)
      integer, intent(in) :: id
      procedure(real_function), pointer, intent(out) :: f
      character(len=preset_expr_len), intent(out) :: expr
      logical, intent(out) :: found

      found = .true.
      select case (id)
      case (1)
         f => f_sinc
         expr = "SIN(X)/X"
      case (2)
         f => f_gauss
         expr = "EXP(-X**2)"
      case (3)
         f => f_runge
         expr = "1/(1+X**2)"
      case default
         f => null()
         expr = ""
         found = .false.
      end select
   end subroutine get_quadrature_preset

end module functions_mod
