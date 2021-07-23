module extxyz

    use iso_c_binding
    use libAtoms_module, only: Atoms, Dictionary, initialise, finalise, &
        set_value, remove_value, print, has_key, lookup_entry_i, string, subset, &
        T_NONE, T_INTEGER, T_INTEGER_A, T_INTEGER_A2, &
        T_REAL, T_REAL_A, T_REAL_A2, T_LOGICAL, T_LOGICAL_A, T_CHAR, T_CHAR_A

    implicit none

    private

    integer, parameter :: MAX_KEY_LENGTH = 100, MAX_VALUE_LENGTH = 1000
    integer, parameter :: DATA_NONE = 0, DATA_I = 1, DATA_F = 2, DATA_B = 3, DATA_S = 4

    type, bind(c) :: ExtxyzDictEntry
        type(C_PTR) :: key
        type(C_PTR) :: data
        integer(kind=C_INT) :: data_t
        integer(kind=C_INT) :: nrows, ncols
        type(C_PTR) :: next
        type(C_PTR) :: first_data_ll, last_data_ll
        integer(kind=C_INT) :: n_in_row
    end type ExtxyzDictEntry

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

        function extxyz_malloc(nbytes) bind(c) result(buffer)
            use iso_c_binding
            integer(kind=C_SIZE_T), value :: nbytes
            type(C_PTR) :: buffer
        end

        function extxyz_read_ll(kv_grammar, fp, nat, info, arrays) bind(c)
            use iso_c_binding
            integer(kind=C_INT) :: extxyz_read_ll
            type(C_PTR), value :: kv_grammar, fp
            integer(kind=C_INT) :: nat
            type(C_PTR) :: info, arrays
        end function extxyz_read_ll

        function extxyz_write_ll(fp, nat, info, arrays) bind(c)
            use iso_c_binding
            integer(kind=C_INT) :: extxyz_write_ll
            type(C_PTR), value :: fp
            integer(kind=C_INT), value :: nat
            type(C_PTR), value :: info, arrays
        end function extxyz_write_ll

    end interface

    interface read_extxyz
        module procedure read_extxyz_filename
    end interface

    interface write_extxyz
        module procedure write_extxyz_filename
    end interface

    public :: read_extxyz, write_extxyz

contains

! Copy a C string, passed by pointer, to a Fortran string.
! If the C pointer is NULL, the Fortran string is blanked.
! C_string must be NUL terminated, or at least as long as F_string.
! If C_string is longer, it is truncated. Otherwise, F_string is
! blank-padded at the end.
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

! Copy a Fortran string to an allocated C string pointer.
! If the C pointer is NULL, no action is taken. (Maybe auto allocate via libc call?)
! If the length is not passed, the C string must be at least: len(F_string)+1
! If the length is passed and F_string is too long, it is truncated.
subroutine F_string_to_C_string_ptr(F_string, C_string, C_string_len)
    character(len=*), intent(in) :: F_string
    type(C_ptr), intent(in) :: C_string ! target = intent(out)
    integer, intent(in), optional :: C_string_len  ! Max string length,
                                                   ! INCLUDING THE TERMINAL NUL
    character(len=1,kind=C_char), dimension(:), pointer :: p_chars
    integer :: i, strlen
    strlen = len_trim(F_string)
    if (present(C_string_len)) then
       if (C_string_len <= 0) return
       strlen = min(strlen,C_string_len-1)
    end if
    if (.not. C_associated(C_string)) then
       return
    end if
    call C_F_pointer(C_string,p_chars,[strlen+1])
    forall (i=1:strlen)
       p_chars(i) = F_string(i:i)
    end forall
    p_chars(strlen+1) = C_NULL_CHAR
  end subroutine F_string_to_C_string_ptr

function c_dict_to_f_dict(c_dict, f_dict) result(success)
    type(ExtxyzDictEntry), pointer, intent(in) :: c_dict
    type(Dictionary), intent(inout) :: f_dict
    logical :: success

    type(ExtxyzDictEntry), pointer :: node => null()
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
    do while (.true.)
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

        if (c_associated(node%next)) then
            call c_f_pointer(node%next, node)
        else
            exit
        end if
    end do

    success = .true.
end function c_dict_to_f_dict

function f_dict_to_c_dict(f_dict, c_dict, verbose) result(success)
    type(Dictionary), intent(in) :: f_dict
    type(ExtxyzDictEntry), pointer, intent(inout) :: c_dict
    logical, intent(in) :: verbose
    logical :: success

    type(ExtxyzDictEntry), pointer :: node => null()
    character(len=MAX_KEY_LENGTH) :: key
    real(kind=C_DOUBLE), pointer :: real_0, real_1(:), real_2(:, :)
    integer(kind=C_INT), pointer :: int_0, int_1(:), int_2(:, :)
    type(C_PTR) :: c_char
    type(C_PTR), pointer :: f_char_1(:)
    character(len=MAX_VALUE_LENGTH) :: char_0
    integer :: i, j, k, type, len_string, n_string
    integer(C_SIZE_T) :: nbytes

    success = .false.
    call c_f_pointer(c_loc(c_dict), node)

    do i=1, f_dict%N
        key = string(f_dict%keys(i))
        type = f_dict%entries(i)%type
        nbytes = int(len_trim(key) + 1, C_SIZE_T) ! +1 for NUL char
        node%key = extxyz_malloc(nbytes)
        node%first_data_ll = C_NULL_PTR
        call F_string_to_C_string_ptr(key, node%key)
        if (type == T_INTEGER) then
            allocate(int_0)
            int_0 = f_dict%entries(i)%i
            node%data_t = DATA_I
            node%nrows = 0
            node%ncols = 0
            node%data = c_loc(int_0)
            int_0 => null()
        else if (type == T_REAL) then
            allocate(real_0)
            real_0 = f_dict%entries(i)%r
            node%data_t = DATA_F
            node%nrows = 0
            node%ncols = 0
            node%data = c_loc(real_0)
            real_0 => null()
        else if (type == T_LOGICAL) then
            allocate(int_0)
            int_0 = merge(1, 0, f_dict%entries(i)%l)
            node%data_t = DATA_B
            node%nrows = 0
            node%ncols = 0
            node%data = c_loc(int_0)
            int_0 => null()
        else if (type == T_CHAR) then
            char_0 = string(f_dict%entries(i)%s)
            nbytes = int(len_trim(char_0) + 1, C_SIZE_T)
            node%data = extxyz_malloc(nbytes)
            call F_string_to_C_string_ptr(char_0, node%data)
            node%data_t = DATA_S
            node%nrows = 0
            node%ncols = 0
        else if (type == T_INTEGER_A) then
            allocate(int_1(size(f_dict%entries(i)%i_a)))
            int_1(:) = f_dict%entries(i)%i_a
            node%data_t = DATA_I
            node%nrows = 0
            node%ncols = size(int_1)
            node%data = c_loc(int_1)
            int_1 => null()
        else if (type == T_REAL_A) then
            allocate(real_1(size(f_dict%entries(i)%r_a)))
            real_1(:) = f_dict%entries(i)%r_a
            node%data_t = DATA_F
            node%nrows = 0
            node%ncols = size(real_1)
            node%data = c_loc(real_1)
            real_1 => null()
        else if (type == T_LOGICAL_A) then
            allocate(int_1(size(f_dict%entries(i)%l_a)))
            int_1(:) = merge(1, 0, f_dict%entries(i)%l_a)
            node%data_t = DATA_B
            node%nrows = 0
            node%ncols = size(int_1)
            node%data = c_loc(int_1)
            int_1 => null()
        else if (type == T_CHAR_A) then
            len_string = size(f_dict%entries(i)%s_a, 1)
            n_string = size(f_dict%entries(i)%s_a, 2)
            nbytes = int(n_string * c_sizeof(c_char), C_SIZE_T)
            c_char = extxyz_malloc(nbytes) ! char**
            call c_f_pointer(c_char, f_char_1, (/ n_string /))
            do j = 1, n_string
                char_0 = repeat(' ', len_string)
                do k = 1, len_string
                    char_0(k:k) = f_dict%entries(i)%s_a(k, j)
                end do
                nbytes = int(len_trim(char_0) + 1, C_SIZE_T)
                f_char_1(j) = extxyz_malloc(nbytes) ! char*
                call F_string_to_C_string_ptr(char_0, f_char_1(j))
            end do
            node%data_t = DATA_S
            node%nrows = 0
            node%ncols = n_string
            node%data = c_char
        else if (type == T_INTEGER_A2) then
            allocate(int_2(size(f_dict%entries(i)%i_a2, 2), size(f_dict%entries(i)%i_a2, 1)))
            int_2(:, :) = transpose(f_dict%entries(i)%i_a2)
            node%data_t = DATA_I
            node%nrows = size(int_2, 1)
            node%ncols = size(int_2, 2)
            node%data = c_loc(int_2)
            int_2 => null()
        else if (type == T_REAL_A2) then
            allocate(real_2(size(f_dict%entries(i)%r_a2, 2), size(f_dict%entries(i)%r_a2, 1)))
            real_2(:,:) = transpose(f_dict%entries(i)%r_a2)
            node%data_t = DATA_F
            node%nrows = size(real_2, 1)
            node%ncols = size(real_2, 2)
            node%data = c_loc(real_2)
            real_2 => null()            
        else
            write (*, *) 'Unexpected dictionary entry type', type
            call free_dict(c_loc(c_dict))
            return
        end if

        if (i /= f_dict%N) then
            node%next = extxyz_malloc(c_sizeof(c_dict))
            call c_f_pointer(node%next, node)
        else
            node%next = C_NULL_PTR
        end if
    end do
    success = .true.

end function f_dict_to_c_dict


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
            write(*,*) '1-D real lattice shape /= (/9/)'
            return
        end if
        lattice = reshape(info%entries(idx)%r_a, (/ 3, 3 /))
    else if (type == T_INTEGER_A) then
        if (size_1 /= 9) then
            write(*,*) '1-D integer lattice shape /= (/9/)'
            return
        end if
        lattice = real(reshape(info%entries(idx)%i_a, (/ 3, 3 /)), C_DOUBLE)
    else if (type == T_REAL_A2) then
        if (any(size_2 /= (/3, 3/))) then
            write(*,*) '2-D real lattice shape /= (/3, 3/)'
            return
        end if
        lattice(:, :) = info%entries(idx)%r_a2
    else if (type == T_INTEGER_A2) then
        if (any(size_2 /= (/3, 3/))) then
            write(*,*) '2-D integer lattice shape /= (/3, 3/)'
            return
        end if
        lattice(:, :) = real(info%entries(idx)%i_a2, C_DOUBLE)
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

    type(ExtxyzDictEntry), pointer :: info => null(), arrays => null()
    type(C_PTR) :: fp, c_info, c_arrays
    logical :: do_verbose = .false., pbc(3)
    integer(C_INT) :: err, nat
    type(Dictionary) :: f_info, f_arrays
    real(C_DOUBLE) :: lattice(3, 3) ! FIXME change C_DOUBLE to DP when this moves to QUIP
    integer :: i

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
        call print_dict(c_info)
        call print_dict(c_arrays)
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
    call remove_value(f_info, "Lattice")
    if (has_key(f_info, "Properties")) then
        call remove_value(f_info, "Properties")
    end if
    pbc = .true.
    if (has_key(f_info, "pbc")) then
        i = lookup_entry_i(f_info, "pbc")
        pbc(:) = f_info%entries(i)%l_a
        call remove_value(f_info, "pbc")
    end if
    call initialise(at, nat, lattice, f_arrays, f_info)
    at%is_periodic = pbc

    call free_dict(c_info)
    call free_dict(c_arrays)
    call finalise(f_info)
    call finalise(f_arrays)

    success = .true.

end function read_extxyz_filename


function write_extxyz_filename(filename, at, append, verbose) result(success)
    character(len=*), intent(in) :: filename
    type(Atoms), intent(in) :: at
    logical, optional, intent(in) :: append, verbose
    logical :: success

    type(Dictionary) :: params
    type(ExtxyzDictEntry), pointer :: info => null(), arrays => null()
    type(C_PTR) :: fp, c_info, c_arrays
    logical :: do_append = .false., do_verbose = .false.
    integer(C_INT) :: err, nat
    character(1) :: mode

    success = .false.
    if (present(append)) do_append = append
    if (present(verbose)) do_verbose = verbose

    mode = "w"
    if (do_append) mode = "a"

    ! make a copy of Atoms%params so we can add pbc and lattice to it
    call subset(at%params, at%params%keys(1:at%params%N), params)
    call set_value(params, 'pbc', at%is_periodic)
    call set_value(params, 'Lattice', at%lattice)

    allocate(info)
    c_info = c_loc(info)
    if (.not. f_dict_to_c_dict(params, info, do_verbose)) then
        call free_dict(c_info)
        call finalise(params)
        return
    end if    

    allocate(arrays)
    c_arrays = c_loc(arrays)
    if (.not. f_dict_to_c_dict(at%properties, arrays, do_verbose)) then
        call free_dict(c_info)
        call free_dict(c_arrays)
        call finalise(params)
        return
    end if

    if (do_verbose) then
        call print_dict(c_info)
        call print_dict(c_arrays)
    end if

    fp = fopen(trim(filename)//C_NULL_CHAR, mode//C_NULL_CHAR)
    err = extxyz_write_ll(fp, at%N, c_info, c_arrays)
    if (err /= 0) return

    err = fclose(fp)
    if (err /= 0) return    

    call free_dict(c_info)
    call free_dict(c_arrays)
    call finalise(params)
    success = .true.

    write (*,*) 'at%params'
    call print(at%params)

end function write_extxyz_filename

end module extxyz