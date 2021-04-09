module ExtXYZ

using LinearAlgebra
using JuLIP

cfopen(filename::String, mode::String) = ccall(:fopen, 
                                                Ptr{Cvoid},
                                                (Cstring, Cstring),
                                                filename, mode)
                                                
cfclose(fp::Ptr{Cvoid}) = ccall(:fclose,
                                Cint,
                                (Ptr{Cvoid},),
                                fp)

function cfopen(f::Function, iostream::IOStream)
    newfd = Libc.dup(RawFD(fd(iostream)))
    fp = ccall(:fdopen, Ptr{Cvoid}, (Cint, Cstring), newfd, "r")
    try
        f(fp)
    finally
        cfclose(fp)
    end
end

function cfopen(f::Function, filename::String)
    fp = cfopen(filename, "r")
    try
        f(fp)
    finally
        cfclose(fp)
    end
end

struct DictEntry
    key::Ptr{Cchar}
    data::Ptr{Cvoid}
    data_t::Cint
    nrows::Cint
    ncols::Cint
    next::Ptr{DictEntry}
    first_data_ll::Ptr{Cvoid}
    last_data_ll::Ptr{Cvoid}
    n_in_row::Cint
end

extxyz_dylib = abspath(joinpath(@__DIR__, "../extxyz/_extxyz.so"))

_kv_grammar = ccall((:compile_extxyz_kv_grammar, extxyz_dylib),
                    Ptr{Cvoid},
                    ())

cfree_dict(dict::Ptr{Cvoid}) = ccall((:free_dict, extxyz_dylib),
                                        Cvoid,
                                        (Ptr{Cvoid},),
                                        dict)

cprint_dict(dict::Ptr{Cvoid}) = ccall((:print_dict, extxyz_dylib),
                                        Cvoid,
                                        (Ptr{Cvoid},),
                                        dict)


function cextxyz_read_ll(fp::Ptr{Cvoid}, nat::Ref{Cint}, info::Ref{Ptr{Cvoid}}, arrays::Ref{Ptr{Cvoid}})
    return ccall((:extxyz_read_ll, extxyz_dylib),
                    Cint,
                    (Ptr{Cvoid}, Ptr{Cvoid}, Ref{Cint}, Ptr{Ptr{Cvoid}}, Ptr{Ptr{Cvoid}}),
                    _kv_grammar, fp, nat, info, arrays)
end

const DATA_I = 1
const DATA_F = 2
const DATA_B = 3
const DATA_S = 4

const TYPE_MAP = Dict(DATA_I => Ptr{Cint},
                      DATA_F => Ptr{Cdouble},
                      DATA_B => Ptr{Cint},
                      DATA_S => Ptr{Cstring})

function c_to_julia_dict(c_dict::Ptr{DictEntry}; transpose=false)
    result = Dict{String, Any}()
    node_ptr = c_dict
    while node_ptr != C_NULL
        node = unsafe_load(node_ptr)
        data_ptr = reinterpret(TYPE_MAP[node.data_t], node.data)

        if node.nrows == 0 && node.ncols == 0
            # scalar
            value = unsafe_load(data_ptr)
            # convert to primitive types
            if node.data_t == DATA_S
                value = unsafe_string(value)
            elseif node.data_t == DATA_B
                value = convert(Bool, value)
            end
        else
            # array, either 1D or 2D
            if node.nrows == 0
                # vector (1D array)
                dims = (node.ncols, )
            else
                # matrix (2D array)
                dims = (node.nrows, node.ncols)
            end

            value = unsafe_wrap(Array, 
                                reinterpret(TYPE_MAP[node.data_t], node.data), 
                                dims)

            if node.data_t == DATA_S
                value = unsafe_string.(value)
            elseif node.data_t == DATA_B
                value = !=(0).(value)
            else
                value = copy(value)
            end

            if node.nrows != 0 && node.ncols != 0 && transpose
                value = value'
            end
        end

        key = unsafe_string(node.key)
        result[key] = value
        node_ptr = node.next
    end
    return result
end     


function read_frame_dicts(fp::Ptr{Cvoid}; verbose=false, transpose_arrays=false)
    nat = Ref{Cint}(0)
    info = Ref{Ptr{Cvoid}}()
    arrays = Ref{Ptr{Cvoid}}()
    eof = false
    try
        if cextxyz_read_ll(fp, nat, info, arrays) == 0
            eof = true
            throw(EOFError())
        end

        if verbose
            cprint_dict(info[])
            cprint_dict(arrays[])
        end

        pinfo = reinterpret(Ptr{DictEntry}, info[])
        parrays = reinterpret(Ptr{DictEntry}, arrays[])
        jinfo = c_to_julia_dict(pinfo)
        jarrays = c_to_julia_dict(parrays, transpose=transpose_arrays)
        return nat[], jinfo, jarrays

    finally
        if !eof
            cfree_dict(info[])
            cfree_dict(arrays[])
        end
    end
end

"""
extract "Lattice" entry and apply semantic conversions
"""
function extract_lattice!(result_dict)
    "Lattice" in keys(result_dict) || return nothing
    lattice = pop!(result_dict, "Lattice")
    if size(lattice) == (3, 3)
        lattice = convert(Array{Float64}, lattice)
    elseif size(lattice) == (3,)
        lattice = convert(Array{Float64}, diagm(lattice))
    elseif lattice.shape == (9,)
        lattice = convert(Array{Float64}, reshape(lattice, (3, 3), order='F'))
    else
        error("Lattice has wrong shape!")
    end
    return lattice
end


function read_frame(fp::Ptr{Cvoid}; verbose=false)
    nat, info, arrays = try
        read_frame_dicts(fp; verbose=verbose, transpose_arrays=true)
    catch err
        if isa(err, EOFError) 
            return nothing
        end
        rethrow()
    end

    dict = Dict{String, Any}("__id__" => "JuLIP_Atoms")

    "pos" in keys(arrays) || error("arrays dictionary missing 'pos' entry containing positions")
    dict["X"] = vecs(pop!(arrays, "pos"))
    @assert length(dict["X"]) == nat

    # atomic numbers and symbols
    dict["Z"] = "Z" in keys(arrays) ? pop!(arrays, "Z") : nothing
    if "species" in keys(arrays)
        species = pop!(arrays, "species")
        Zsp = atomic_number.([Symbol(sp) for sp in species])
        if dict["Z"] !== nothing
            all(dict["Z"] .== Zsp) || error("inconsistent 'Z' and 'species' properties")
        else
            dict["Z"] = Zsp
        end
    end
    dict["Z"] === nothing && error("atomic numbers not defined - either 'Z' or 'species' must be present")

    # mass - lookup from atomic number if not present
    if "masses" in keys(arrays)
        dict["M"] = pop!(arrays, "masses")
    elseif "mass" in keys(arrays)
        dict["M"] = pop!(arrays, "mass") # FIXME convert units?
    else
        dict["M"] = [atomic_mass(z) for z in AtomicNumber.(dict["Z"])]
    end

    # momenta / velocities
    if "momenta" in keys(arrays)
        dict["P"] = vecs(pop!(arrays, "momenta"))
    elseif "velo" in keys(arrays)
        dict["P"] = vecs(pop!(arrays, "velo") .* dict["M"]) # FIXME convert units?
    else
        dict["P"] = zeros((3, nat))
    end

    # periodic boundary conditions
    if "pbc" in keys(info)
        dict["pbc"] = pop!(info, "pbc")
    end

    # cell is transpose of the stored lattice
    lattice = extract_lattice!(info)
    dict["cell"] = transpose(lattice)

    # everything else goes in data
    dict["data"] = merge(info, arrays)

    return JuLIP.read_dict(dict)
end

"""
Channel to yield a sequence of frames from an open file pointer
"""
function iread_extxyz(fp::Ptr{Cvoid}, range; kwargs...)
    Channel() do channel
        for frame in 1:first(range)-1
            atoms = read_frame(fp, kwargs...)
            atoms === nothing && break
        end
        for frame in range
            atoms = read_frame(fp, kwargs...)
            atoms === nothing && break
            put!(channel, atoms)
        end
    end
end

"""
Read frames from a ExtXYZ file, specified by a file pointer, filename or IOStream
"""
function read_extxyz(fp::Ptr{Cvoid}, range; kwargs...)
    seq = collect(iread_extxyz(fp, range; kwargs...))
    return length(seq) == 1 ? seq[1] : seq
end

function read_extxyz(file::Union{String,IOStream}, range; kwargs...)
    cfopen(file) do fp
        read_extxyz(fp, range; kwargs...)
    end
end

read_extxyz(file::Union{String,IOStream}, count::Int; kwargs...) = read_extxyz(file, 1:count)
read_extxyz(file::Union{String,IOStream}; kwargs...) = read_extxyz(file, Iterators.countfrom(1))

end


filename = "test.xyz"

seq1 = ExtXYZ.read_extxyz(filename)
seq2 = ExtXYZ.read_extxyz(filename, 4:10)
frame = ExtXYZ.read_extxyz(filename, 4)

f = open(filename, "r")
seq3 = ExtXYZ.read_extxyz(f)
close(f)

@assert all(seq1[4:10] .== seq2)
@assert all(seq1 .== seq3)