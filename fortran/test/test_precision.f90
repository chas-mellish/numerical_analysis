!> test-drive suite for the `precision` module.
module test_precision_suite
   use, intrinsic :: iso_fortran_env, only: real32, real64
   use precision, only: wp, single_precision
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_precision

contains

   !> Collect all exported unit tests.
   subroutine collect_precision(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("wp_matches_build_mode", test_wp_matches_build_mode), &
         new_unittest("wp_digits", test_wp_digits) &
      ]
   end subroutine collect_precision

   !> `wp` is real64 by default and real32 when built with -DSINGLE.
   subroutine test_wp_matches_build_mode(error)
      type(error_type), allocatable, intent(out) :: error

      if (single_precision) then
         call check(error, wp, real32, "wp must be real32 in a SINGLE build")
      else
         call check(error, wp, real64, "wp must be real64 in the default build")
      end if
   end subroutine test_wp_matches_build_mode

   !> The model of `wp` (binary digits) is consistent with the selected kind.
   subroutine test_wp_digits(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp), parameter :: one = 1.0_wp

      if (single_precision) then
         call check(error, digits(one), digits(1.0_real32), &
            "digits(1.0_wp) must equal real32 digits")
      else
         call check(error, digits(one), digits(1.0_real64), &
            "digits(1.0_wp) must equal real64 digits")
      end if
   end subroutine test_wp_digits

end module test_precision_suite

