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
            type(C_PTR), value :: fp
        end function fclose

        subroutine free_dict(dict) bind(c)
            use iso_c_binding
            type(C_PTR), value :: dict
        end subroutine

        subroutine print_dict(dict) bind(c)
            use iso_c_binding
            type(C_PTR), value :: dict
        end subroutine

        function compile_extxyz_kv_grammar() bind(c)
            use iso_c_binding
            type(C_PTR) :: compile_extxyz_kv_grammar
        end function compile_extxyz_kv_grammar

        function extxyz_read_ll(kv_grammar, fp, nat, info, arrays) bind(c)
            use iso_c_binding
            integer(kind=C_INT) :: extxyz_read_ll
            type(C_PTR), value :: kv_grammar, fp
            type(C_PTR) :: info, arrays
            integer(kind=C_INT) :: nat
        end function extxyz_read_ll

    end interface

    interface read_extxyz
        module procedure read_extxyz_filename
    end interface

    public :: read_extxyz

contains

subroutine C_string_ptr_to_F_string(C_string, F_string)
    use iso_c_binding
    type(C_PTR), intent(in) :: C_string
    character(len=*), intent(out) :: F_string
    character(len=1, kind=C_CHAR), dimension(:), pointer :: p_chars
    integer :: i
    if (.not. c_associated(C_string)) then
        F_string = ' '
    else
        call c_f_pointer(C_string, p_chars, [huge(0)])
        do i = 1, len(F_string)
            if (p_chars(i) == C_NULL_CHAR) exit
            F_string(i:i) = p_chars(i)
        end do
        if (i <= len(F_string)) F_string(i:) = ' '
    end if
end subroutine

subroutine read_extxyz_filename(filename, verbose)
    character(len=*), intent(in) :: filename
    logical, optional, intent(in) :: verbose

    type(DictEntry), pointer :: info, arrays, node
    type(C_PTR) :: fp, c_info, c_arrays
    logical :: do_verbose = .false.
    integer(C_INT) :: err, nat
    character(len=100) :: key

    if (present(verbose)) then
        do_verbose = verbose
    end if

    if (.not. initialised) then
        kv_grammar = compile_extxyz_kv_grammar()
        initialised = .true.
    end if

    c_info = c_loc(info)
    c_arrays = c_loc(arrays)

    fp = fopen(trim(filename)//C_NULL_CHAR, "r"//C_NULL_CHAR)

    err = extxyz_read_ll(kv_grammar, fp, nat, c_info, c_arrays)
    if (err /= 1) then
        return
    end if

    err = fclose(fp)
    if (err /= 0) then
        return
    end if

    if (do_verbose) then
        call print_dict(c_info)
        call print_dict(c_arrays)
    end if

    ! node => info
    call C_string_ptr_to_F_string(info%key, key)
    write(*,*) 'info%key', key
    write(*,*) 'info%data_t', info%data_t
    write(*,*) 'info%nrows', info%nrows
    write(*,*) 'info%ncols', info%ncols
    write(*,*) 'entering loop'
    do while (c_associated(node%next))
        write(*,*) 'accessing key'
        call C_string_ptr_to_F_string(node%key, key)
        write(*,*) key
    end do

    call free_dict(c_info)
    call free_dict(c_arrays)

end subroutine read_extxyz_filename

end module extxyz