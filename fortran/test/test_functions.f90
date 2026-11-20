!> test-drive suite for `functions_mod`: the target functions and the --preset tables.
module test_functions_suite
   use precision, only: wp, single_precision
   use, intrinsic :: ieee_arithmetic, only: ieee_is_finite, ieee_is_nan
   use functions_mod, only: real_function, get_bisection_preset, get_quadrature_preset, &
      get_derivative_preset, preset_expr_len, bisection_preset_count, quadrature_preset_count, &
      derivative_preset_count, pi_book, f_book_bisection, f_cubic, f_cos_minus_x, f_sinc, &
      f_gauss, f_runge, f_book_derivative, f_sin, f_one_plus_log10
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_functions

contains

   !> Collect all exported unit tests.
   subroutine collect_functions(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("book_function_values", test_book_function_values), &
         new_unittest("bisection_preset_1_is_book", test_bisection_preset_1), &
         new_unittest("bisection_presets_2_3", test_bisection_presets_2_3), &
         new_unittest("bisection_preset_unknown", test_bisection_preset_unknown), &
         new_unittest("quadrature_presets", test_quadrature_presets), &
         new_unittest("quadrature_preset_unknown", test_quadrature_preset_unknown), &
         new_unittest("derivative_presets", test_derivative_presets), &
         new_unittest("derivative_log10_domain", test_derivative_log10_domain), &
         new_unittest("derivative_preset_unknown", test_derivative_preset_unknown) &
      ]
   end subroutine collect_functions

   !> Value tolerance appropriate for the working precision.
   pure real(wp) function tol_wp()
      if (single_precision) then
         tol_wp = 1.0e-6_wp
      else
         tol_wp = 1.0e-13_wp
      end if
   end function tol_wp

   !> The book's function with the book's PI literal: F(0.5) = EXP(-.5) - SIN(.78539815).
   subroutine test_book_function_values(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, pi_book, 3.1415926_wp, "pi_book must be the book literal 3.1415926")
      if (allocated(error)) return
      call check(error, f_book_bisection(0.0_wp), 1.0_wp, thr=tol_wp())
      if (allocated(error)) return
      ! exp(-0.5) - sin(3.1415926*0.5/2)
      call check(error, f_book_bisection(0.5_wp), &
         exp(-0.5_wp) - sin(3.1415926_wp*0.5_wp/2.0_wp), thr=tol_wp())
      if (allocated(error)) return
      call check(error, f_book_bisection(0.5_wp), -0.1005761_wp, thr=1.0e-6_wp, &
         message="F(0.5) must print as the book's -.100576")
   end subroutine test_book_function_values

   !> --preset 1 selects the book's function.
   subroutine test_bisection_preset_1(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found

      call get_bisection_preset(1, f, expr, found)
      call check(error, found, "preset 1 must exist")
      if (allocated(error)) return
      call check(error, associated(f, f_book_bisection), "preset 1 must be f_book_bisection")
      if (allocated(error)) return
      call check(error, trim(expr), "EXP(-X) - SIN(3.1415926*X/2.)")
   end subroutine test_bisection_preset_1

   !> --preset 2 and 3.
   subroutine test_bisection_presets_2_3(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found

      call check(error, bisection_preset_count, 3)
      if (allocated(error)) return

      call get_bisection_preset(2, f, expr, found)
      call check(error, found .and. associated(f, f_cubic), "preset 2 must be f_cubic")
      if (allocated(error)) return
      call check(error, trim(expr), "X**3 - X - 1")
      if (allocated(error)) return
      call check(error, f(1.0_wp), -1.0_wp, thr=tol_wp())
      if (allocated(error)) return
      call check(error, f(2.0_wp), 5.0_wp, thr=tol_wp())
      if (allocated(error)) return

      call get_bisection_preset(3, f, expr, found)
      call check(error, found .and. associated(f, f_cos_minus_x), "preset 3 must be cos(x)-x")
      if (allocated(error)) return
      call check(error, trim(expr), "COS(X) - X")
      if (allocated(error)) return
      call check(error, f(0.0_wp), 1.0_wp, thr=tol_wp())
      if (allocated(error)) return
      call check(error, f(1.0_wp), cos(1.0_wp) - 1.0_wp, thr=tol_wp())
   end subroutine test_bisection_presets_2_3

   !> Unknown ids report found = .false. and a null pointer.
   subroutine test_bisection_preset_unknown(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      integer :: id
      integer, parameter :: bad(3) = [0, 4, -1]

      do id = 1, size(bad)
         call get_bisection_preset(bad(id), f, expr, found)
         call check(error, .not. found, "unknown bisection preset must not be found")
         if (allocated(error)) return
         call check(error, .not. associated(f), "unknown preset must give a null pointer")
         if (allocated(error)) return
      end do
   end subroutine test_bisection_preset_unknown

   !> Simpson / Romberg presets, including the sin(x)/x limit at x = 0.
   subroutine test_quadrature_presets(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found

      call check(error, quadrature_preset_count, 3)
      if (allocated(error)) return

      call get_quadrature_preset(1, f, expr, found)
      call check(error, found .and. associated(f, f_sinc), "quadrature preset 1 must be sinc")
      if (allocated(error)) return
      call check(error, trim(expr), "SIN(X)/X")
      if (allocated(error)) return
      call check(error, f(0.0_wp), 1.0_wp, "sin(x)/x at x = 0 must be the limit 1")
      if (allocated(error)) return
      call check(error, f(-0.0_wp), 1.0_wp, "sin(x)/x at x = -0 must be the limit 1")
      if (allocated(error)) return
      call check(error, f(2.0_wp), sin(2.0_wp)/2.0_wp, thr=tol_wp())
      if (allocated(error)) return

      call get_quadrature_preset(2, f, expr, found)
      call check(error, found .and. associated(f, f_gauss), "quadrature preset 2 must be gauss")
      if (allocated(error)) return
      call check(error, trim(expr), "EXP(-X**2)")
      if (allocated(error)) return
      call check(error, f(1.0_wp), exp(-1.0_wp), thr=tol_wp())
      if (allocated(error)) return

      call get_quadrature_preset(3, f, expr, found)
      call check(error, found .and. associated(f, f_runge), "quadrature preset 3 must be runge")
      if (allocated(error)) return
      call check(error, trim(expr), "1/(1+X**2)")
      if (allocated(error)) return
      call check(error, f(1.0_wp), 0.5_wp, thr=tol_wp())
   end subroutine test_quadrature_presets

   !> Unknown quadrature ids report found = .false.
   subroutine test_quadrature_preset_unknown(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found

      call get_quadrature_preset(4, f, expr, found)
      call check(error, .not. found .and. .not. associated(f), &
         "unknown quadrature preset must not be found")
   end subroutine test_quadrature_preset_unknown

   !> Central-difference presets (ch04_p01), as in catalog/ch04_p01_central_difference.toml.
   subroutine test_derivative_presets(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found

      call check(error, derivative_preset_count, 3)
      if (allocated(error)) return

      call get_derivative_preset(1, f, expr, found)
      call check(error, found .and. associated(f, f_book_derivative), &
         "derivative preset 1 must be the book's X**2*EXP(X)")
      if (allocated(error)) return
      call check(error, trim(expr), "X**2*EXP(X)")
      if (allocated(error)) return
      call check(error, f(0.0_wp), 0.0_wp, thr=0.0_wp, message="F(0) = 0")
      if (allocated(error)) return
      call check(error, f(1.0_wp), exp(1.0_wp), thr=tol_wp())
      if (allocated(error)) return
      ! X**2 is X*X, as gerald_na.expr evaluates an integer exponent.
      call check(error, f(-2.0_wp), (-2.0_wp)*(-2.0_wp)*exp(-2.0_wp), thr=0.0_wp, &
         message="X**2*EXP(X) at -2")
      if (allocated(error)) return

      call get_derivative_preset(2, f, expr, found)
      call check(error, found .and. associated(f, f_sin), "derivative preset 2 must be sin")
      if (allocated(error)) return
      call check(error, trim(expr), "SIN(X)")
      if (allocated(error)) return
      call check(error, f(1.0_wp), sin(1.0_wp), thr=0.0_wp)
      if (allocated(error)) return

      call get_derivative_preset(3, f, expr, found)
      call check(error, found .and. associated(f, f_one_plus_log10), &
         "derivative preset 3 must be 1 + log10(x)")
      if (allocated(error)) return
      call check(error, trim(expr), "1 + LOG10(X)")
      if (allocated(error)) return
      call check(error, f(10.0_wp), 2.0_wp, thr=tol_wp())
      if (allocated(error)) return
      ! The p. 91 table (four decimals): 1 + log x at 0.19 is 0.2788.
      call check(error, f(0.19_wp), 0.2788_wp, thr=5.0e-5_wp, message="p. 91 table at 0.19")
   end subroutine test_derivative_presets

   !> 1 + LOG10(X) outside its domain is not finite (the module turns that into INPUT).
   subroutine test_derivative_log10_domain(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, .not. ieee_is_finite(f_one_plus_log10(0.0_wp)), "LOG10(0) is -Inf")
      if (allocated(error)) return
      call check(error, ieee_is_nan(f_one_plus_log10(-0.05_wp)), "LOG10 of a negative is NaN")
   end subroutine test_derivative_log10_domain

   !> Unknown derivative ids report found = .false.; preset ids are scoped per family.
   subroutine test_derivative_preset_unknown(error)
      type(error_type), allocatable, intent(out) :: error
      procedure(real_function), pointer :: f
      character(len=preset_expr_len) :: expr
      logical :: found
      integer :: id
      integer, parameter :: bad(3) = [0, 4, -1]

      do id = 1, size(bad)
         call get_derivative_preset(bad(id), f, expr, found)
         call check(error, .not. found .and. .not. associated(f), &
            "unknown derivative preset must not be found")
         if (allocated(error)) return
         call check(error, len_trim(expr), 0, "unknown preset has no expression")
         if (allocated(error)) return
      end do
      ! Preset 2 of the derivative family is not the bisection family's preset 2.
      call get_derivative_preset(2, f, expr, found)
      call check(error, .not. associated(f, f_cubic), "derivative preset 2 is not f_cubic")
   end subroutine test_derivative_preset_unknown

end module test_functions_suite
