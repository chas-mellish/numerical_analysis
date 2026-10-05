! ============================================================
! bisection.f90
!
! Modernized rewrite of a legacy 1960s FORTRAN interval-halving
! (bisection) root finder. Original used arithmetic IF, GOTO,
! Hollerith FORMATs, and CALL EXIT; this version uses structured
! IF/DO, IMPLICIT NONE, and standard intrinsics.
!
! Solves F(X) = 0 on [X1, X2] given F(X1)*F(X2) < 0.
! ============================================================
program bisection
    implicit none
    real :: x1, x2, x, fx1, fx2, fx, tol
    integer :: i, max_iter
    logical :: found

    max_iter = 25
    found = .false.

    ! Original program READ these from a data card: 0. 1. 1.E-5
    x1  = 0.0
    x2  = 1.0
    tol = 1.0e-5

    fx1 = f(x1)
    fx2 = f(x2)

    ! --- Validate the bracket, same checks as the original ---
    if (fx1 * fx2 > 0.0) then
        print *, "Function values at initial X values are not of " // &
                  "opposite signs. Change inputs."
        stop
    else if (fx1 == 0.0 .and. fx2 == 0.0) then
        print *, "Error: FX1 and FX2 not zero though product tests zero."
        stop
    else if (fx1 == 0.0) then
        print '(A,F10.7,A)', "The input value X = ", x1, &
              " is a root of the equation."
        stop
    else if (fx2 == 0.0) then
        print '(A,F10.7,A)', "The input value X = ", x2, &
              " is a root of the equation."
        stop
    end if

    ! --- Interval halving, limited to max_iter passes ---
    do i = 1, max_iter
        x  = (x1 + x2) / 2.0
        fx = f(x)
        print '(A,F10.7,A,F10.6)', "AT X = ", x, "  F(X) = ", fx

        if (abs(fx) <= tol) then
            found = .true.
            exit
        end if

        if (fx * fx1 < 0.0) then
            ! root is between x1 and x: pull the right edge in
            x2 = x
        else
            ! root is between x and x2: push the left edge up
            x1  = x
            fx1 = fx
        end if
    end do

    if (found) then
        print '(A,F10.7,A,I3,A)', "THE VALUE X = ", x, " IS A ROOT. ", &
              i, " ITERATIONS WERE REQUIRED."
    else
        print *, "Error: maximum iterations exceeded without convergence."
    end if

contains

    real function f(x_in)
        implicit none
        real, intent(in) :: x_in
        real, parameter :: pi = 3.1415926
        ! Original: F(X) = EXPF(-X) - SINF(pi*X/2.)
        f = exp(-x_in) - sin(pi * x_in / 2.0)
    end function f

end program bisection
