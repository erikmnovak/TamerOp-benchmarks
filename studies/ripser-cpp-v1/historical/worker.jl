using SparseArrays, LinearAlgebra, SHA
import JSON3
load_seconds = @elapsed @eval import TamerOp as OP
emit(x) = (println(JSON3.write(x)); flush(stdout))
emit((kind="ready", julia=string(VERSION), load_seconds, source=pathof(OP), threads=Threads.nthreads(), blas_threads=BLAS.get_num_threads()))

function native(c)
    tokens = split(read(c.path, String))
    n = Int(c.n)
    if c.format == "lower-distance"
        @assert length(tokens) == n*(n-1)÷2
        x = zeros(Float64, n, n); k = 0
        for i in 2:n, j in 1:i-1
            k += 1; x[i,j] = x[j,i] = parse(Float64,tokens[k])
        end
        return x
    end
    @assert length(tokens)%3 == 0
    rows=Int[]; cols=Int[]; vals=Float64[]
    for k in 1:3:length(tokens)
        i=parse(Int,tokens[k])+1; j=parse(Int,tokens[k+1])+1
        v=parse(Float64,tokens[k+2])
        push!(rows,i);push!(cols,j);push!(vals,v)
        push!(rows,j);push!(cols,i);push!(vals,v)
    end
    return sparse(rows,cols,vals,n,n)
end
function signature(x)
    io=IOBuffer()
    if issparse(x)
        write(io,x.colptr);write(io,x.rowval);write(io,x.nzval)
    else
        write(io,x)
    end
    return bytes2hex(sha256(take!(io)))
end
function diagram_data(D,degree)
    diagrams=Any[]
    for q in 0:degree
        bars=Any[Any[b,d] for (b,d) in OP.finite_intervals(D;dim=q)]
        append!(bars,[Any[b,nothing] for b in OP.essential_births(D;dim=q)])
        sort!(bars;by=x->(x[1],something(x[2],Inf)))
        push!(diagrams,bars)
    end
    return diagrams
end
function execute(c)
    GC.gc()
    # The uninterrupted primary timer includes file reading, native input,
    # checked public computation, and complete barcode output to the pipe.
    total = @timed begin
        built=@timed native(c)
        x=built.value
        f=OP.RipsFiltration(max_dim=Int(c.degree)+1,radius=c.threshold)
        answer=@timed OP.persistence_diagram(x,f;field=OP.CoreModules.Fp(Int(c.prime)),max_homology_dim=Int(c.degree),cocycles=false,cache=nothing)
        diagrams=diagram_data(answer.value,Int(c.degree))
        emit((kind="barcode",id=c.id,diagrams))
        (built,answer,x)
    end
    built,answer,x=total.value
    OP.Advanced.check_persistence_diagram(answer.value;throw=true)
    @assert signature(x)==signature(native(c)) "input mutated"
    clean=iszero(total.compile_time)&&iszero(total.recompile_time)
    emit((kind="sample",id=c.id,accepted=clean,seconds=total.time,
        construction_seconds=built.time,query_seconds=answer.time,
        compile_seconds=total.compile_time,recompile_seconds=total.recompile_time,
        allocation_bytes=total.bytes,gc_seconds=total.gctime,
        retained_result_bytes=Base.summarysize(answer.value),reset_verified=true,
        backend=OP.provenance(answer.value).backend))
    nothing
end
for line in eachline(stdin)
    try
        execute(JSON3.read(line))
    catch e
        emit((kind="error",message=sprint(showerror,e,catch_backtrace())))
    end
end
