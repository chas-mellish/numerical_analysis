!> Command-line flags shared by the drivers that take a function preset (bisection, Simpson,
!> Romberg): `--trace`, `--verbose`, `--help`/`-h` and `--preset N` (or `--preset=N`), in any
!> order. Bairstow and Lagrange take data rather than a function and keep their own parsers,
!> which reject `--preset` with a program-specific message.
!>
!> Errors are reported, not raised: the first bad argument sets `arg_error` and the driver
!> decides how to print it (stderr, or an `ERROR,code=INPUT` record under `--trace`).
module cli_mod
   use book_format_mod, only: trace_int
   implicit none
   private

   !> Longest command-line argument accepted (longer ones are an input error).
   integer, parameter, public :: arg_len = 256

   public :: parse_arguments

contains

   !> Read all command-line flags (any order). Sets `arg_error` on the first bad argument.
   subroutine parse_arguments(trace, verbose, help, preset, arg_error)
      logical, intent(out) :: trace, verbose, help
      integer, intent(out) :: preset
      character(len=:), allocatable, intent(out) :: arg_error
      character(len=arg_len) :: arg
      integer :: i, n, length, stat

      trace = .false.
      verbose = .false.
      help = .false.
      preset = 1
      n = command_argument_count()
      i = 1
      do while (i <= n)
         call get_command_argument(i, arg, length, stat)
         if (stat /= 0 .or. length > arg_len) then
            if (.not. allocated(arg_error)) arg_error = "command-line argument " // &
               trace_int(i) // " is too long"
            i = i + 1
            cycle
         end if
         select case (trim(arg))
         case ("--trace")
            trace = .true.
         case ("--verbose")
            verbose = .true.
         case ("--help", "-h")
            help = .true.
         case ("--preset")
            if (i == n) then
               if (.not. allocated(arg_error)) arg_error = "--preset needs a number"
            else
               i = i + 1
               call get_command_argument(i, arg, length, stat)
               call parse_preset(arg, stat == 0 .and. length <= arg_len, preset, arg_error)
            end if
         case default
            if (index(arg, "--preset=") == 1) then
               call parse_preset(arg(len("--preset=") + 1:), .true., preset, arg_error)
            else if (.not. allocated(arg_error)) then
               arg_error = "unknown argument " // trim(arg) // " (try --help)"
            end if
         end select
         i = i + 1
      end do
   end subroutine parse_arguments

   !> Parse the value of --preset.
   subroutine parse_preset(text, ok, preset, arg_error)
      character(len=*), intent(in) :: text
      logical, intent(in) :: ok
      integer, intent(inout) :: preset
      character(len=:), allocatable, intent(inout) :: arg_error
      integer :: ios, value

      value = 0
      ios = 1
      if (ok .and. len_trim(text) > 0 .and. verify(trim(text), "0123456789") == 0) then
         read (text, *, iostat=ios) value
      end if
      if (ios == 0) then
         preset = value
      else if (.not. allocated(arg_error)) then
         arg_error = "--preset needs a positive integer (got " // trim(text) // ")"
      end if
   end subroutine parse_preset

end module cli_mod
