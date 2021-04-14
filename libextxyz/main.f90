program extxyz_main

    use extxyz
    implicit none

    call read_extxyz("test.xyz", verbose=.true.)

end program