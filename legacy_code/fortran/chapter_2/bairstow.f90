!===============================================================================
! bairstow.f90
!
! Modern free-form Fortran translation of a 1970s teaching program that finds
! quadratic (and, if needed, one final linear) factors of a real polynomial of
! degree up to 6, using Bairstow's method.
!
! Original source: C. F. Gerald, "Applied Numerical Analysis", Program 2 --
! "QUADRATIC FACTORS OF POLYNOMIALS TO SIXTH DEGREE, BAIRSTOW METHOD",
! written in card-image FORTRAN II / early FORTRAN IV.
!
! NOTES ON THE ORIGINAL LISTING
! ------------------------------
! The scanned/OCR'd listing you supplied contained several corrupted
! characters, some of them the classic "I" <-> "1" (and O <-> 0, l <-> 1,
! S <-> 5, B <-> 8) confusions typical of old line-printer scans. The
! corrections made while transcribing are:
!
!   * DIMENSION A(9), B(9), C(I)   ->  C(9)
!       C is indexed up to C(9) later in the program, so it must be
!       dimensioned (9); "I" here is a misread "9", not a variable.
!
!   * READ 2, R1, Sl, TEST, LIM, N ->  the "Sl" is "S1" (letter l vs digit 1).
!
!   * R1 = R1 + l.  /  S1 = S1 + 1.  ->  logically this must be
!       R = R + 1.  and  S = S + 1.
!       As originally transcribed (bumping R1/S1, which are never read again),
!       the zero-denominator recovery branch would leave R and S completely
!       unchanged and loop forever. Bumping the *working* R and S (which is
!       also the standard textbook remedy for a singular Bairstow step) is
!       the only version that is logically self-consistent, and it is the
!       version implemented below.
!
!   * FORMAT (...,l4,...)  ->  FORMAT (...,I4,...)   (LIM is an INTEGER, so
!       this edit descriptor must be "I4", not "l4" -- the reverse confusion,
!       an "I" misread as a lowercase "l").
!
!   * A handful of other OCR slips (O for 0, "~"/"em dash" for minus signs,
!     "." for "," inside FORMAT/READ lists, "BX" for "8X", "SH" for "5H",
!     stray characters in "F1l0.5") were straightforward to identify from
!     context and from FORMAT-statement Hollerith character counts, and are
!     not called out individually here.
!
!   * The sample data card's polynomial coefficient "-126.218" is very
!     probably a digit transposition of "-261.218": the demonstration output
!     included in the same listing explicitly prints the coefficient of x**2
!     as -261.21800, so -261.218 (not -126.218) is used as the sample value
!     below and in bairstow_demo.txt.
!
!   * IMPORTANT CAVEAT ABOUT THE PRINTED FACTOR, kept faithful to the
!     original: the program prints each factor as "X**2 + r X + s", but the
!     synthetic-division recurrence actually used,
!         b(j) = a(j) + r*b(j-1) + s*b(j-2),
!     divides the polynomial by (X**2 - r*X - s), NOT by (X**2 + r*X + s).
!     This was verified numerically against the worked example in the
!     listing (whose printed r, s values reproduce the demonstration output
!     exactly under this recurrence) and against an independent test
!     polynomial with known roots. It appears to be a genuine labelling
!     quirk in the original 1970s program, not an OCR artifact. This
!     translation keeps the original's printed label for fidelity, but also
!     prints the mathematically correct factor and its roots.
!
!===============================================================================
module bairstow_mod
   implicit none
   integer, parameter :: dp = selected_real_kind(15, 307)
   integer, parameter :: max_degree = 6

contains

   subroutine synthetic_division(a, r, s, b, c)
      ! One pass of synthetic division of the polynomial held in a(3:9) by
      ! (x**2 - r*x - s), giving the quotient in b(3:9); then a second pass
      ! divides b by the same quadratic, giving c(3:9). c is used to build
      ! the linear system solved for the Newton corrections to r and s.
      real(dp), intent(in)  :: a(9)
      real(dp), intent(in)  :: r, s
      real(dp), intent(out) :: b(9), c(9)
      integer :: j

      b = 0.0_dp
      c = 0.0_dp
      do j = 3, 9
         b(j) = a(j) + r*b(j-1) + s*b(j-2)
         c(j) = b(j) + r*c(j-1) + s*c(j-2)
      end do
   end subroutine synthetic_division

   subroutine quadratic_roots(coef_a, coef_b, coef_c, root1, root2)
      ! Roots of coef_a*x**2 + coef_b*x + coef_c = 0, returned as complex
      ! numbers so a negative discriminant never crashes the program.
      real(dp), intent(in)     :: coef_a, coef_b, coef_c
      complex(dp), intent(out) :: root1, root2
      complex(dp) :: disc

      disc  = cmplx(coef_b*coef_b - 4.0_dp*coef_a*coef_c, 0.0_dp, dp)
      root1 = (-coef_b + sqrt(disc)) / (2.0_dp*coef_a)
      root2 = (-coef_b - sqrt(disc)) / (2.0_dp*coef_a)
   end subroutine quadratic_roots

   function fmt_complex(z) result(s)
      complex(dp), intent(in) :: z
      character(len=32) :: s
      if (abs(aimag(z)) < 1.0e-8_dp) then
         write (s, '(F14.6)') real(z, dp)
      else
         write (s, '(F14.6,SP,F14.6,"i")') real(z, dp), aimag(z)
      end if
   end function fmt_complex

end module bairstow_mod


program bairstow_factors
   use bairstow_mod
   implicit none

   real(dp)    :: a(9), b(9), c(9)
   real(dp)    :: r, s, r1, s1, test, denom, delr, dels
   integer     :: n, lim, kount, i, k, m
   complex(dp) :: root1, root2

   print '(A)', 'DEMONSTRATION PROGRAM OUTPUT'

   print '(/,A)', 'Degree of the polynomial (2-6)?'
   read (*,*) n
   if (n < 2 .or. n > max_degree) then
      print '(A)', 'Degree must be between 2 and 6. Stopping.'
      stop 1
   end if

   a = 0.0_dp
   print '(A,I0,A)', 'Enter the ', n+1, ' coefficients, highest power first:'
   read (*,*) (a(i), i = 9-n, 9)

   print '(A)', 'Enter initial R, S, convergence test, and max iterations:'
   read (*,*) r1, s1, test, lim

   print '(/,A,/)', ' THE ORIGINAL POLYNOMIAL'
   print '(A)', '   POWER OF X     COEFFICIENT'
   do i = 9 - n, 9
      m = 9 - i
      print '(5X,I5,10X,F12.5)', m, a(i)
   end do

   print '(/,A)', ' THE QUADRATIC FACTORS ARE:'

   r = r1
   s = s1

   degree_loop: do
      kount = 1
      newton: do
         call synthetic_division(a, r, s, b, c)

         denom = c(7)*c(7) - c(8)*c(6)
         if (abs(denom) < epsilon(1.0_dp)) then
            ! Singular step: nudge r and s and retry (see header notes).
            r = r + 1.0_dp
            s = s + 1.0_dp
            kount = 1
            cycle newton
         end if

         delr = (-b(8)*c(7) + c(6)*b(9)) / denom
         dels = (-c(7)*b(9) + c(8)*b(8)) / denom
         r = r + delr
         s = s + dels

         if (abs(delr) + abs(dels) < test) exit newton

         if (kount >= lim) then
            print '(/,A,I0,A)', ' DOES NOT CONVERGE AFTER ', lim, ' ITERATIONS'
            stop 1
         end if
         kount = kount + 1
      end do newton

      print '(/,A,F10.5,A,F10.5,A)', '   X**2 + ', r, ' X + ', s, '   (as printed by the original program)'
      print '(A,F10.5,A,F10.5)',     '   i.e. the true factor divided out is  X**2 - ', r, ' X - ', s
      call quadratic_roots(1.0_dp, -r, -s, root1, root2)
      print '(A,A)', '   roots: ', trim(fmt_complex(root1))
      print '(A,A)', '          ', trim(fmt_complex(root2))

      n = n - 2
      if (n < 2) then
         print '(/,A,F10.5,A,F10.5)', ' FINAL LINEAR FACTOR: ', b(6), ' X + ', b(7)
         print '(A,F10.5)', '   root: ', -b(7)/b(6)
         exit degree_loop
      else if (n == 2) then
         print '(/,A,F10.5,A,F10.5,A,F10.5)', &
            ' FINAL QUADRATIC FACTOR: ', b(5), ' X**2 + ', b(6), ' X + ', b(7)
         call quadratic_roots(b(5), b(6), b(7), root1, root2)
         print '(A,A)', '   roots: ', trim(fmt_complex(root1))
         print '(A,A)', '          ', trim(fmt_complex(root2))
         exit degree_loop
      else
         do k = 3, 9
            a(k) = b(k - 2)
         end do
      end if
   end do degree_loop

end program bairstow_factors
