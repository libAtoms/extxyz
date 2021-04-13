module extxyz

    use iso_c_binding
    implicit none

    private

    type, bind(c) :: DictEntry
        type(C_PTR) :: key
        type(C_PTR) :: data
        integer(kind=C_INT) :: data_t
        integer(kind=C_INT) :: nrows, ncols
        type(C_PTR) :: next
        type(C_PTR) :: first_data_ll, last_data_ll
        integer(kind=C_INT) :: n_in_row
    end type DictEntry

    logical :: initialised = .false.
    type(C_PTR) :: kv_grammar

    interface

        function fopen(filename, mode) bind(c)
            use iso_c_binding
            type(C_PTR) :: fopen
            character(kind=C_CHAR) :: filename(*)
            character(kind=C_CHAR) :: mode(*)
        end function fopen

        function fclose(fp) bind(c)
            use iso_c_binding
            integer(kind=C_INT) :: fclose
            type(C_PTR) :: fp
        end function fclose

        subroutine free_dict(dict) bind(c)
            use iso_c_binding
            type(C_PTR) :: dict
        end subroutine

        subroutine print_dict(dict) bind(c)
            use iso_c_binding
            type(C_PTR) :: dict
        end subroutine

        function compile_extxyz_kv_grammar() bind(c)
            use iso_c_binding
            type(C_PTR) :: compile_extxyz_kv_grammar
        end function compile_extxyz_kv_grammar

        function extxyz_read_ll(kv_grammar, fp, nat, info, arrays) bind(c)
            use iso_c_binding
            integer(kind=C_INT) :: extxyz_read_ll
            type(C_PTR) :: kv_grammar, fp, info, arrays
            integer(kind=C_INT) :: nat
        end function extxyz_read_ll

    end interface

    interface read_extxyz
        module procedure read_extxyz_filename
    end interface

    public :: read_extxyz

contains

subroutine read_extxyz_filename(filename, verbose)
    character(len=*), intent(in) :: filename
    logical, optional, intent(in) :: verbose

    type(DictEntry), pointer :: info, arrays
    type(C_PTR) :: fp, c_info, c_arrays
    logical :: do_verbose = .false.
    integer(C_INT) :: err, nat

    if (present(verbose)) then
        do_verbose = verbose
    end if

    write (*,*) "initialising grammar..."
    if (.not. initialised) then
        kv_grammar = compile_extxyz_kv_grammar()
        initialised = .true.
    end if
    write (*,*) "initialising grammar done"

    allocate(info)
    allocate(arrays)
    c_info = c_loc(info)
    c_arrays = c_loc(arrays)

    write (*,*) "opening file..."
    fp = fopen(trim(filename)//C_NULL_CHAR, "r"//C_NULL_CHAR)
    write (*,*) "opening file done"

    write (*,*) "calling extxyz_read_ll()..."
    err = extxyz_read_ll(kv_grammar, fp, nat, c_info, c_arrays)
    if (err /= 0) then
        return
    end if
    write(*,*) "call to extxyz_read_ll() done"

    write(*,*) "closing file..."
    err = fclose(fp)
    if (err /= 0) then
        return
    end if
    write(*,*) "closing file done"

    if (do_verbose) then
        call print_dict(c_info)
        call print_dict(c_arrays)
    end if

    call free_dict(c_info)
    call free_dict(c_arrays)

end subroutine read_extxyz_filename

end module extxyz