!> Test runner for every test-drive suite in fortran/test/.
!> Executes each collected suite and stops with a non-zero status on any failure.
!> Register new suites in the `testsuites` array below.
program tester
   use, intrinsic :: iso_fortran_env, only: error_unit
   use testdrive, only: run_testsuite, new_testsuite, testsuite_type
   use test_precision_suite, only: collect_precision
   use test_functions_suite, only: collect_functions
   use test_book_format_suite, only: collect_book_format
   use test_bisection_suite, only: collect_bisection
   use test_lagrange_suite, only: collect_lagrange
   implicit none
   integer :: stat, is
   type(testsuite_type), allocatable :: testsuites(:)
   character(len=*), parameter :: fmt = '("#", *(1x, a))'

   stat = 0

   testsuites = [ &
      new_testsuite("precision", collect_precision), &
      new_testsuite("functions", collect_functions), &
      new_testsuite("book_format", collect_book_format), &
      new_testsuite("bisection", collect_bisection), &
      new_testsuite("lagrange", collect_lagrange) &
   ]

   do is = 1, size(testsuites)
      write (error_unit, fmt) "Testing:", testsuites(is)%name
      call run_testsuite(testsuites(is)%collect, error_unit, stat)
   end do

   if (stat > 0) then
      write (error_unit, '(i0, 1x, a)') stat, "test(s) failed!"
      error stop
   end if
end program tester
