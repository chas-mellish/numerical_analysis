!> test-drive suite for `book_format_mod`: book-style Fw.d fields, trace value rendering and
!> comma-free trace messages.
module test_book_format_suite
   use precision, only: wp
   use book_format_mod, only: book_fixed, book_fixed_nearest, book_int, trace_real, trace_int, &
      trace_logical, no_commas
   use testdrive, only: new_unittest, unittest_type, error_type, check
   implicit none
   private

   public :: collect_book_format

contains

   !> Collect all exported unit tests.
   subroutine collect_book_format(testsuite)
      type(unittest_type), allocatable, intent(out) :: testsuite(:)

      testsuite = [ &
         new_unittest("no_leading_zero", test_no_leading_zero), &
         new_unittest("round_toward_zero", test_round_toward_zero), &
         new_unittest("round_to_nearest", test_round_to_nearest), &
         new_unittest("wide_values_unchanged", test_wide_values), &
         new_unittest("book_int", test_book_int), &
         new_unittest("trace_values", test_trace_values), &
         new_unittest("no_commas", test_no_commas) &
      ]
   end subroutine collect_book_format

   !> The book prints ".5000000", "-.100576" and "  .000" (no leading zero, right-justified).
   subroutine test_no_leading_zero(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, book_fixed(0.5_wp, 10, 7), "  .5000000")
      if (allocated(error)) return
      call check(error, book_fixed(-0.1005761_wp, 10, 6), "  -.100576")
      if (allocated(error)) return
      call check(error, book_fixed(0.0_wp, 6, 3), "  .000")
      if (allocated(error)) return
      call check(error, book_fixed(-0.5_wp, 10, 7), " -.5000000")
      if (allocated(error)) return
      call check(error, book_fixed(0.25_wp, 4, 2), " .25")
   end subroutine test_no_leading_zero

   !> Fields are chopped like the book's machine: exact midpoints print truncated.
   subroutine test_round_toward_zero(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, book_fixed(0.44140625_wp, 10, 7), "  .4414062")
      if (allocated(error)) return
      call check(error, book_fixed(0.443359375_wp, 10, 7), "  .4433593")
      if (allocated(error)) return
      call check(error, book_fixed(0.443572998046875_wp, 10, 7), "  .4435729")
      if (allocated(error)) return
      call check(error, book_fixed(-0.000506051_wp, 10, 6), "  -.000506")
   end subroutine test_round_toward_zero

   !> `book_fixed_nearest` (data-card echoes) rounds to nearest; the field layout is the same.
   subroutine test_round_to_nearest(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, book_fixed_nearest(0.443572998046875_wp, 10, 7), "  .4435730")
      if (allocated(error)) return
      call check(error, book_fixed_nearest(-0.5_wp, 10, 7), " -.5000000")
      if (allocated(error)) return
      call check(error, book_fixed_nearest(99.41_wp, 10, 5), "  99.41000")
      if (allocated(error)) return
      call check(error, book_fixed_nearest(15.0_wp, 6, 2), " 15.00")
   end subroutine test_round_to_nearest

   !> Values with an integer part keep their digits; overflow gives asterisks.
   subroutine test_wide_values(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, book_fixed(1.0_wp, 6, 3), " 1.000")
      if (allocated(error)) return
      call check(error, book_fixed(-2.5_wp, 6, 3), "-2.500")
      if (allocated(error)) return
      call check(error, book_fixed(10.5_wp, 6, 3), "10.500")
      if (allocated(error)) return
      call check(error, book_fixed(1000.0_wp, 6, 3), "******")
   end subroutine test_wide_values

   !> I3 as in FORMAT 203.
   subroutine test_book_int(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, book_int(15, 3), " 15")
      if (allocated(error)) return
      call check(error, book_int(5, 3), "  5")
   end subroutine test_book_int

   !> ES25.17E3 without leading blanks, I0, T/F.
   subroutine test_trace_values(error)
      type(error_type), allocatable, intent(out) :: error
      real(wp) :: back
      integer :: ios
      character(len=32) :: text

      call check(error, trace_real(0.5_wp), "5.00000000000000000E-001")
      if (allocated(error)) return
      call check(error, trace_real(-1.0_wp), "-1.00000000000000000E+000")
      if (allocated(error)) return
      ! Full precision: the trace text reads back to the identical value.
      text = trace_real(0.443572998046875_wp/3.0_wp)
      read (text, *, iostat=ios) back
      call check(error, ios, 0, "trace_real output must be readable")
      if (allocated(error)) return
      call check(error, back >= 0.443572998046875_wp/3.0_wp .and. &
         back <= 0.443572998046875_wp/3.0_wp, "trace_real must round-trip exactly")
      if (allocated(error)) return
      call check(error, trace_int(15), "15")
      if (allocated(error)) return
      call check(error, trace_int(-3), "-3")
      if (allocated(error)) return
      call check(error, trace_logical(.true.), "T")
      if (allocated(error)) return
      call check(error, trace_logical(.false.), "F")
   end subroutine test_trace_values

   !> Trace messages never contain the field separator: commas become semicolons.
   subroutine test_no_commas(error)
      type(error_type), allocatable, intent(out) :: error

      call check(error, no_commas("A, B,C"), "A; B;C")
      if (allocated(error)) return
      call check(error, no_commas("no separators"), "no separators")
   end subroutine test_no_commas

end module test_book_format_suite
