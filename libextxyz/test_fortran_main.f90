program extxyz_main

    use extxyz
    use libAtoms_module, only: system_initialise, system_finalise, Atoms, Print

    implicit none

    type(Atoms) :: at
    logical :: status
    character(1000) :: infile, verbose
    logical do_verbose

    call system_initialise

    call get_command_argument(1, infile)
    call get_command_argument(2, verbose)

    do_verbose = trim(verbose) == 'T'

    status = read_extxyz(infile, at, do_verbose)
    call print(at)
    call system_finalise

end program