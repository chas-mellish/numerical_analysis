!> Output helpers shared by every driver.
!>
!> * `book_fixed` renders a value the way the book's line printer did for an `Fw.d` edit
!>   descriptor: digits truncated toward zero (round-toward-zero, the `RZ` edit mode) and no
!>   leading zero before the decimal point (`.5000000`, `-.100576`). The listings were run on
!>   a machine that chopped rather than rounded (for example the scan prints the exact
!>   midpoint 0.44140625 as `.4414062` and 0.443359375 as `.4433593`), and that printed no
!>   leading zero. Modern processors print `0.4414063` by default, so both conventions are
!>   applied explicitly here. Field width and decimals are unchanged; a value that does not
!>   fit still prints as asterisks, as `Fw.d` requires.
!> * `book_fixed_nearest` is the same field rounded to nearest (the `RN` edit mode), for the
!>   echoes of data-card values, which the book printed as the exact card digits.
!> * `trace_real`, `trace_int`, `trace_logical` render values for the `--trace` protocol (DD2):
!>   reals with `ES25.17E3` (leading blanks removed), integers with `I0`, logicals `T`/`F`.
!> * `no_commas` makes message text safe for a trace record: commas are the protocol's field
!>   separators, so an `ERROR` message never contains one.
module book_format_mod
   use precision, only: wp
   implicit none
   private

   public :: book_fixed, book_fixed_nearest, book_int, trace_real, trace_int, trace_logical, &
      no_commas

contains

   !> Book-style `Fw.d`: round toward zero and suppress the leading zero of a value below one.
   function book_fixed(x, w, d) result(s)
      real(wp), intent(in) :: x
      integer, intent(in) :: w, d
      character(len=w) :: s

      s = fixed_point(x, w, d, "RZ")
   end function book_fixed

   !> Book-style `Fw.d` rounded to nearest, without the leading zero of a value below one.
   function book_fixed_nearest(x, w, d) result(s)
      real(wp), intent(in) :: x
      integer, intent(in) :: w, d
      character(len=w) :: s

      s = fixed_point(x, w, d, "RN")
   end function book_fixed_nearest

   !> `Fw.d` under the rounding edit mode `mode` (`RZ` or `RN`), leading zero suppressed.
   function fixed_point(x, w, d, mode) result(s)
      real(wp), intent(in) :: x
      integer, intent(in) :: w, d
      character(len=2), intent(in) :: mode
      character(len=w) :: s
      character(len=32) :: fmt
      integer :: p

      write (fmt, '("(", A, ",F", I0, ".", I0, ")")') mode, w, d
      write (s, fmt) x
      ! "0." whose zero is the only integer digit (start of field, or preceded by a blank or
      ! a minus sign) loses the zero; the rest of the field shifts right by one column so the
      ! value stays right-justified.
      p = index(s, "0.")
      if (p >= 1) then
         if (p == 1) then
            s = " "//s(2:)
         else if (s(p - 1:p - 1) == " " .or. s(p - 1:p - 1) == "-") then
            s = " "//s(1:p - 1)//s(p + 1:)
         end if
      end if
   end function fixed_point

   !> `Iw` edit descriptor, for the book's integer fields (for example `I3`).
   function book_int(i, w) result(s)
      integer, intent(in) :: i, w
      character(len=w) :: s
      character(len=16) :: fmt

      write (fmt, '("(I", I0, ")")') w
      write (s, fmt) i
   end function book_int

   !> Trace real: `ES25.17E3`, leading blanks removed (full real64 precision).
   function trace_real(x) result(s)
      real(wp), intent(in) :: x
      character(len=:), allocatable :: s
      character(len=25) :: buf

      write (buf, '(ES25.17E3)') x
      s = trim(adjustl(buf))
   end function trace_real

   !> Trace integer: `I0`.
   function trace_int(i) result(s)
      integer, intent(in) :: i
      character(len=:), allocatable :: s
      character(len=24) :: buf

      write (buf, '(I0)') i
      s = trim(buf)
   end function trace_int

   !> Trace logical: `T` or `F`.
   pure function trace_logical(l) result(s)
      logical, intent(in) :: l
      character(len=1) :: s

      if (l) then
         s = "T"
      else
         s = "F"
      end if
   end function trace_logical

   !> Message text for a trace record: commas are field separators, so replace them.
   pure function no_commas(text) result(s)
      character(len=*), intent(in) :: text
      character(len=len(text)) :: s
      integer :: i

      s = text
      do i = 1, len(s)
         if (s(i:i) == ",") s(i:i) = ";"
      end do
   end function no_commas

end module book_format_mod
