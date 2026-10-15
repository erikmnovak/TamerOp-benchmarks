using SparseArrays, LinearAlgebra, JSON3
import TamerOp as OP
BLAS.set_num_threads(1)

struct Fixture
    dims::Vector{Int}
    grades::Vector{Int}
    columns::Vector{Vector{Int}}
end

function read_input(path)
    lines = readlines(path)
    n = parse(Int, lines[1])
    length(lines) == n+1 || error("input count")
    dims, grades, columns = Int[], Int[], Vector{Int}[]
    for (i,line) in enumerate(lines[2:end])
        d,g,count,rows... = parse.(Int,split(line))
        length(rows) == count || error("boundary count")
        issorted(rows) && allunique(rows) && all(r -> 0 <= r < i-1, rows) || error("boundary indices")
        push!(dims,d); push!(grades,g); push!(columns,collect(rows) .+ 1)
    end
    Fixture(dims,grades,columns)
end

function construct(f::Fixture)
    nd = maximum(f.dims; init=0)+1
    groups = [findall(==(d), f.dims) for d in 0:nd-1]
    localindex = zeros(Int,length(f.dims))
    for group in groups, (j,cell) in enumerate(group)
        localindex[cell]=j
    end
    boundaries=SparseMatrixCSC{Int,Int}[]
    for h in 2:nd
        cells = groups[h]
        colptr = Vector{Int}(undef, length(cells) + 1)
        colptr[1] = 1
        for (j, cell) in enumerate(cells)
            colptr[j+1] = colptr[j] + length(f.columns[cell])
        end
        rows = Vector{Int}(undef, colptr[end] - 1)
        for (j, cell) in enumerate(cells)
            for (k, row) in enumerate(f.columns[cell])
                rows[colptr[j] + k - 1] = localindex[row]
            end
        end
        # Validated input columns are unique and sorted; the order-preserving
        # degree-local indexing retains that CSC invariant without triplets.
        push!(boundaries, SparseMatrixCSC(length(groups[h-1]), length(cells),
                                          colptr, rows, ones(Int, length(rows))))
    end
    grades = NTuple{1,Int}[(f.grades[i],) for group in groups for i in group]
    OP.DataTypes.GradedComplex(groups,boundaries,grades)
end

function pristine(g, f::Fixture)
    # Compare native storage directly in O(cells + boundary entries). Do not
    # repeatedly copy an entire row-label vector for each boundary column.
    fieldnames(typeof(g)) == (:cell_ids,:dim_offsets,:boundaries,:grades) || error("reset inventory changed")
    groups = [findall(==(d), f.dims) for d in 0:maximum(f.dims; init=0)]
    length(g.cell_ids) == length(g.grades) == length(f.dims) || return false
    length(g.dim_offsets) == length(groups)+1 || return false
    length(g.boundaries) == length(groups)-1 || return false
    first(g.dim_offsets) == 1 && last(g.dim_offsets) == length(f.dims)+1 || return false
    offset = 1
    for h in eachindex(groups)
        ids = groups[h]
        g.dim_offsets[h] == offset && g.dim_offsets[h+1] == offset+length(ids) || return false
        (@view g.cell_ids[offset:offset+length(ids)-1]) == ids || return false
        rows = h == 1 ? Int[] : groups[h-1]
        if h > 1
            b = g.boundaries[h-1]
            size(b) == (length(rows),length(ids)) || return false
            length(b.colptr) == length(ids)+1 && first(b.colptr)==1 || return false
            last(b.colptr)-1 == length(b.rowval) == length(b.nzval) || return false
            issorted(b.colptr) || return false
        end
        for (j,id) in enumerate(ids)
            g.grades[offset+j-1] == (f.grades[id],) || return false
            if h == 1
                isempty(f.columns[id]) || return false
            else
                b = g.boundaries[h-1]; range = nzrange(b,j)
                length(range) == length(f.columns[id]) || return false
                for (k,ptr) in enumerate(range)
                    row = b.rowval[ptr]
                    1 <= row <= length(rows) && rows[row] == f.columns[id][k] && b.nzval[ptr] == 1 || return false
                end
            end
        end
        offset += length(ids)
    end
    return true
end

function query_with_backend(g, f::Fixture)
    result=OP.persistence_diagram(g; field=OP.CoreModules.F2(), order=:sublevel, representatives=false)
    finite=NTuple{3,Int}[]; essential=NTuple{2,Int}[]
    for h in 0:maximum(f.dims;init=0)
        for (b,d) in OP.finite_intervals(result;dim=h)
            push!(finite,(h,b,d))
        end
        for b in OP.essential_births(result;dim=h)
            push!(essential,(h,b))
        end
    end
    ((finite=sort!(finite), essential=sort!(essential)), OP.provenance(result).backend)
end

query(g, f::Fixture) = first(query_with_backend(g, f))
combined(f::Fixture) = (g=construct(f); (g,query(g,f)))
combined_with_backend(f::Fixture) = (g=construct(f); (g,query_with_backend(g,f)))
emit(x) = (println(JSON3.write(x)); flush(stdout))

function request(f,phase)
    # This scope returns scalars and serialized output only. No native input,
    # barcode, reduced column or factor survives to supply the next request.
    g = phase=="query" ? construct(f) : nothing
    g===nothing || pristine(g,f) || error("reset failed")
    measurement = if phase=="construction"
        @timed construct(f)
    elseif phase=="query"
        @timed query_with_backend(g,f)
    else
        @timed combined_with_backend(f)
    end
    answer=nothing; backend=nothing
    if phase=="construction"
        g=measurement.value
    elseif phase=="combined"
        g,(answer,backend)=measurement.value
    else
        answer,backend=measurement.value
    end
    pristine(g,f) || error("input changed")
    (seconds=measurement.time, compile_seconds=measurement.compile_time,
     recompile_seconds=measurement.recompile_time, allocation_bytes=measurement.bytes,
     gc_seconds=measurement.gctime, retained_input_bytes=Base.summarysize(g),
     retained_answer_bytes=Base.summarysize(answer), answer=answer, backend=backend)
end

function main()
    length(ARGS)==5 || error("usage: worker list.tsv correctness|timing samples warmups twist")
    timing=ARGS[2]=="timing"; samples=parse(Int,ARGS[3]); warmups=parse(Int,ARGS[4])
    emit((event="metadata",tool="tamerop",julia=string(VERSION),threads=Threads.nthreads(),
          blas_threads=BLAS.get_num_threads(),algorithm="public_persistence_diagram",
          protocol_version=2,gc_policy="before_phase_warmup_then_natural",
          backend_scope="public_result_provenance",
          field="F2",order="sublevel",representatives=false))
    f=Fixture([0,0,1],[0,0,1],[Int[],Int[],[1,2]])
    g=construct(f); g.boundaries[1][1,1]=0
    pristine(g,f) && error("reset guard accepts changed input")
    emit((event="reset_guard",passed=true))
    g=nothing; f=nothing
    for line in eachline(ARGS[1])
        id,path=split(line,'\t'); f=read_input(path)
        for phase in (timing ? ["construction","query","combined"] : ["query"])
            timing && GC.gc()
            emit((event="phase",case=id,phase=phase,forced_gc=timing))
            accepted=0; iteration=0
            while accepted < (timing ? samples : 1)
                emit((event="begin",case=id,phase=phase))
                result=request(f,phase)
                kind = !timing ? "correctness" : iteration<warmups ? "warmup" :
                    (result.compile_seconds>0 || result.recompile_seconds>0) ? "compile_rejected" : "measurement"
                # Correctness qualification records no per-fixture timing,
                # including evaluation cases reserved from performance tuning.
                record = !timing ? (answer=result.answer,backend=result.backend,) : result
                emit(merge((event="sample",case=id,phase=phase,kind=kind,iteration=iteration,
                            reset_verified=true),record))
                result=nothing; record=nothing
                kind in ("measurement","correctness") && (accepted+=1)
                iteration+=1
                iteration <= warmups+samples+3 || error("compilation did not settle")
            end
        end
    end
    emit((event="complete",))
end
main()
