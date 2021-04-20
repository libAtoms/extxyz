module extxyz

    use iso_c_binding
    use libAtoms_module, only: Atoms, Dictionary, initialise, finalise, &
        set_value, print, has_key, lookup_entry_i, T_REAL_A, T_REAL_A2

    implicit none

    private

    integer, parameter :: MAX_KEY_LENGTH = 100, MAX_VALUE_LENGTH = 1000
    integer, parameter :: DATA_NONE = 0, DATA_I = 1, DATA_F = 2, DATA_B = 3, DATA_S = 4

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
end subroutine C_string_ptr_to_F_string

function c_dict_to_f_dict(c_dict, f_dict) result(success)
    type(DictEntry), pointer, intent(in) :: c_dict
    type(Dictionary), intent(inout) :: f_dict
    logical :: success

    type(DictEntry), pointer :: node => null()
    character(len=MAX_KEY_LENGTH) :: key
    real(kind=C_DOUBLE), pointer :: real_0, real_1(:), real_2(:, :)
    integer(kind=C_INT), pointer :: int_0, int_1(:), int_2(:, :)
    logical :: logical_0
    logical, allocatable :: logical_1(:)
    type(C_PTR), pointer :: char_0, char_1(:)
    character(len=MAX_VALUE_LENGTH) :: f_char_0
    character(len=MAX_VALUE_LENGTH), allocatable :: f_char_1(:)
    integer :: i

    success = .false.
    node => c_dict
    do while (c_associated(node%next))
        call C_string_ptr_to_F_string(node%key, key)
        if (node%data_t == DATA_I) then
            if (node%nrows == 0 .and. node%ncols == 0) then
                call c_f_pointer(node%data, int_0)
                call set_value(f_dict, key, int_0)
            else if (node%nrows == 0) then
                call c_f_pointer(node%data, int_1, (/ node%ncols /))
                call set_value(f_dict, key, int_1)
            else
                call c_f_pointer(node%data, int_2, (/ node%nrows, node%ncols /))
                call set_value(f_dict, key, transpose(int_2))
            end if
        else if (node%data_t == DATA_F) then
            if (node%nrows == 0 .and. node%ncols == 0) then
                call c_f_pointer(node%data, real_0)
                call set_value(f_dict, key, real_0)
            else if (node%nrows == 0) then
                call c_f_pointer(node%data, real_1, (/ node%ncols /))
                call set_value(f_dict, key, real_1)
            else
                call c_f_pointer(node%data, real_2, (/ node%nrows, node%ncols /))
                call set_value(f_dict, key, transpose(real_2))
            end if
        else if (node%data_t == DATA_B) then
            ! boolean data - read as integer, then convert to logical
            if (node%nrows == 0 .and. node%ncols == 0) then
                call c_f_pointer(node%data, int_0)
                logical_0 = int_0 == 1
                call set_value(f_dict, key, logical_0)
            else if (node%nrows == 0) then
                call c_f_pointer(node%data, int_1, (/ node%ncols /))
                allocate(logical_1(node%nrows))
                logical_1 = int_1 == 1
                call set_value(f_dict, key, logical_1)
                deallocate(logical_1)
            else
                write (*,*) '2-dimensional logical arrays not supported in Fortran'
                return 
            end if            
        else if (node%data_t == DATA_S) then
            ! string data - each entry is a NULL-terminated char*
            if (node%nrows == 0 .and. node%ncols == 0) then
                call c_f_pointer(node%data, char_0)
                call C_string_ptr_to_F_string(char_0, f_char_0)
                call set_value(f_dict, key, f_char_0)
            else if (node%nrows == 0) then
                call c_f_pointer(node%data, char_1, (/ node%ncols /))
                allocate(f_char_1(node%ncols))
                do i=1,node%ncols
                    call C_string_ptr_to_F_string(char_1(i), f_char_1(i))
                end do
                call set_value(f_dict, key, f_char_1)
                deallocate(f_char_1)
            else
                write (*,*) '2-dimensional string arrays not supported in Fortran'
                return 
            end if
        end if
        
        call c_f_pointer(node%next, node)
    end do

    success = .true.
end function c_dict_to_f_dict

subroutine extract_lattice(info, lattice)
    type(Dictionary), intent(in) :: info
    real(C_DOUBLE), intent(out) :: lattice(3, 3) ! FIXME change C_DOUBLE to DP when this moves to QUIP

    integer :: type, idx, size_1, size_2(2)

    lattice(:, :) = 0.0
    if (.not. has_key(info, "Lattice")) return

    idx = lookup_entry_i(info, "Lattice")
    type = info%entries(idx)%type
    size_1 = info%entries(idx)%len
    size_2 = info%entries(idx)%len2

    if (type == T_REAL_A) then
        if (size_1 /= 9) then
            write(*,*) '1-D lattice shape /= (/9/)'
            return
        end if
        lattice = reshape(info%entries(idx)%r_a, (/ 3, 3 /))
    else if (type == T_REAL_A2) then
        if (any(size_2 /= (/3, 3/))) then
            write(*,*) '2-D lattice shape /= (/3, 3/)'
            return
        end if
        lattice(:, :) = info%entries(idx)%r_a2
    else
        write(*,*) 'lattice has incorrect type', type
        return
    end if
end subroutine

function read_extxyz_filename(filename, at, verbose) result(success)
    character(len=*), intent(in) :: filename
    type(Atoms), intent(out) :: at
    logical, optional, intent(in) :: verbose
    logical :: success

    type(DictEntry), pointer :: info => null(), arrays => null()
    type(C_PTR) :: fp, c_info, c_arrays
    logical :: do_verbose = .false.
    integer(C_INT) :: err, nat
    type(Dictionary) :: f_info, f_arrays
    real(C_DOUBLE) :: lattice(3, 3) ! FIXME change C_DOUBLE to DP when this moves to QUIP

    success = .false.
    if (present(verbose)) do_verbose = verbose

    if (.not. initialised) then
        kv_grammar = compile_extxyz_kv_grammar()
        initialised = .true.
    end if

    c_info = c_loc(info)
    c_arrays = c_loc(arrays)

    fp = fopen(trim(filename)//C_NULL_CHAR, "r"//C_NULL_CHAR)

    err = extxyz_read_ll(kv_grammar, fp, nat, c_info, c_arrays)
    if (err /= 1) return

    err = fclose(fp)
    if (err /= 0) return

    if (do_verbose) then
        call print_dict(c_loc(info))
        call print_dict(c_loc(arrays))
    end if

    call initialise(f_info)
    call c_f_pointer(c_info, info)
    if (.not. c_dict_to_f_dict(info, f_info)) then
        call free_dict(c_info)
        call free_dict(c_arrays)
        call finalise(f_info)
        call finalise(f_arrays)        
        return
    end if

    call initialise(f_arrays)
    call c_f_pointer(c_arrays, arrays)
    if (.not. c_dict_to_f_dict(arrays, f_arrays)) then
        call free_dict(c_info)
        call free_dict(c_arrays)
        call finalise(f_info)
        call finalise(f_arrays)
        return
    end if

    if (do_verbose) then
        call print(f_info)
        call print(f_arrays)
    end if

    call extract_lattice(f_info, lattice)
    call initialise(at, nat, lattice, f_arrays, f_info)

    call free_dict(c_info)
    call free_dict(c_arrays)
    call finalise(f_info)
    call finalise(f_arrays)

    success = .true.

end function read_extxyz_filename

end module extxyz