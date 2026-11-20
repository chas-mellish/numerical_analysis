!> Working precision for every Gerald program.
!>
!> `wp` is real64 by default. Building with the preprocessor macro `SINGLE`
!> (for example `make build-fortran-single`, i.e. `fpm build --flag -DSINGLE`)
!> selects real32, which reproduces the single-precision digits printed in the book.
module precision
   use, intrinsic :: iso_fortran_env, only: real32, real64
   implicit none
   private

#ifdef SINGLE
   integer, parameter, public :: wp = real32
#else
   integer, parameter, public :: wp = real64
#endif

   !> True when the build uses the book's single precision (`-DSINGLE`).
   logical, parameter, public :: single_precision = wp == real32

end module precision
