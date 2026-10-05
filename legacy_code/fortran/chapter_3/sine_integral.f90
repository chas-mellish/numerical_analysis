!===============================================================================
! sine_integral.f90
!
! Modern free-form Fortran translation of a 1970s teaching program that
! evaluates the sine integral, Si(B) = integral from 0 to B of sin(x)/x dx,
! by the composite Simpson's 1/3 rule.
!
! Original source: C. F. Gerald, "Applied Numerical Analysis", Chapter 3
! (Integration), Program 1 -- written in card-image FORTRAN II / early
! FORTRAN IV.
!
! NOTES ON THE ORIGINAL LISTING
! ------------------------------
! As with the Bairstow-method listing from Chapter 1, the scanned copy had
! several corrupted characters -- the same handful of OCR confusions
! (digit/letter look-alikes) recur:
!
!   * IF (N = 2*NHALF) 99,1,99   ->  IF (N - 2*NHALF) 99,1,99
!       An arithmetic IF branches on the SIGN of an expression, so this has
!       to be a subtraction ("="  is a misread "-"). It is testing whether N
!       is even: N - 2*(N/2) is 0 for even N, 1 for odd N.
!
!   * DO 10 I = 2.NHALF   ->   DO 10 I = 2, NHALF   ("." misread comma)
!
!   * SININT = DELX/3.*5UM   ->   SININT = DELX/3.*SUM   ("5" misread "S")
!
!   * FORMAT (... ,Fl0.7, ...)   ->   FORMAT (... ,F10.7, ...)
!       ("l" misread "1" -- the reverse of the more common "I"/"1" mix-up).
!
!   * The job-control lines at the top (ZZJ08, ZZFORX5, #LIST PRINTER) are
!     mainframe deck-header cards, not Fortran source, and are dropped.
!
! F(X) = SIN(X)/X has a removable singularity at X = 0 (the limit is 1),
! which the original program dodges by hard-coding the first term of the
! Simpson sum as "1.0" instead of calling F(0.). This translation instead
! makes F itself handle X = 0 explicitly, which is equivalent but keeps the
! special case next to the function it belongs to rather than buried in the
! summation logic.
!
! A note on precision: the original ran in 1970s single precision (note the
! "SINF" name, the old convention for single-precision sine). Run here in
! double precision, B = 5, N = 100 panels gives 1.5499312, matching the true
! value Si(5) = 1.5499312449... to 8 figures. The original listing's printed
! demonstration value, 1.5499307, differs only in the 6th-7th digit, which is
! consistent with 1970s single-precision rounding over 100 accumulated terms
! -- not a bug, just the two programs using different floating-point
! precision.
!===============================================================================
module simpson_mod
   implicit none
   integer, parameter :: dp = selected_real_kind(15, 307)

contains

   pure function f(x) result(y)
      ! f(x) = sin(x)/x, with the x = 0 removable singularity resolved to
      ! its limiting value of 1.
      real(dp), intent(in) :: x
      real(dp) :: y
      if (x == 0.0_dp) then
         y = 1.0_dp
      else
         y = sin(x)/x
      end if
   end function f

end module simpson_mod


program sine_integral
   use simpson_mod
   implicit none

   real(dp) :: b, delx, x, total, sinint
   integer  :: n, nhalf, i

   print '(A)', 'Upper limit of integration B, and number of panels N (even, > 2)?'
   read (*,*) b, n

   nhalf = n/2
   if (n /= 2*nhalf) then
      print '(/,A)', ' WITH ODD NUMBER OF PANELS, SIMPSONS 1/3 RULE DOES NOT APPLY'
      stop 1
   end if

   delx = b/real(n, dp)

   ! First, second, and last ordinates of the composite Simpson sum.
   total = f(0.0_dp) + 4.0_dp*f(delx) + f(b)

   ! Remaining interior ordinates, in (weight-2, weight-4) pairs.
   x = 2.0_dp*delx
   do i = 2, nhalf
      total = total + 2.0_dp*f(x) + 4.0_dp*f(x + delx)
      x = x + 2.0_dp*delx
   end do

   sinint = delx/3.0_dp*total

   print '(/,A,F6.2,A,F10.7,A,I4,A)', &
      ' VALUE OF SINE INTEGRAL FROM X = 0 TO X =', b, ' IS', sinint, ' WITH', n, ' PANELS'

end program sine_integral
