using SparseArrays, LinearAlgebra, SHA
import JSON3
load_seconds=@elapsed @eval import TamerOp as OP
const OUT=ARGS[1];const PASS=parse(Int,ARGS[2]);const IDS=split(ARGS[3],",")
const M=JSON3.read(read(joinpath(OUT,"manifest.json"),String))
emit(x)=(println(JSON3.write(x));flush(stdout))
function rss()
    s=read("/proc/self/status",String)
    Dict(k=>parse(Int,match(Regex("(?m)^"*k*":\\s+(\\d+)"),s).captures[1])*1024 for k in ("VmRSS","VmHWM"))
end
function load_input(path)
    # Decode the interchange file eagerly, as Python json.loads does.
    text=read(path,String);kind=JSON3.read(text).kind
    schema=kind=="cloud" ? @NamedTuple{kind::String,points::Vector{Vector{Float64}}} :
        kind=="dense" ? @NamedTuple{kind::String,matrix::Vector{Vector{Float64}}} :
        @NamedTuple{kind::String,n::Int,rows::Vector{Int},cols::Vector{Int},values::Vector{Float64}}
    return JSON3.read(text,schema)
end
function native(raw)
    raw.kind=="cloud" && return OP.PointCloud([Float64.(v) for v in raw.points])
    raw.kind=="dense" && return permutedims(reduce(hcat,[Float64.(v) for v in raw.matrix]))
    return sparse(Int.(raw.rows).+1,Int.(raw.cols).+1,Float64.(raw.values),Int(raw.n),Int(raw.n))
end
function query(x,c)
    selection=nothing
    if c.landmarks!==nothing
        selection=OP.select_landmarks(x;count=Int(c.landmarks),retain_distances=true)
        idx=OP.landmark_indices(selection);x=x[idx,idx]
    end
    f=c.family=="weighted" ? OP.EdgeWeightedFiltration(max_dim=Int(c.degree)+1,threshold=c.threshold) : OP.RipsFiltration(max_dim=Int(c.degree)+1,radius=c.threshold)
    D=OP.persistence_diagram(x,f;field=OP.CoreModules.Fp(Int(c.prime)),max_homology_dim=Int(c.degree),cocycles=Bool(c.cocycles),cache=nothing)
    return (D,selection)
end
function signature(x)
    io=IOBuffer()
    if x isa OP.PointCloud
        for p in x.points;write(io,p);end
    elseif issparse(x)
        write(io,x.colptr);write(io,x.rowval);write(io,x.nzval)
    else;write(io,x);end
    return bytes2hex(sha256(take!(io)))
end
function output(result,c)
    D,selection=result
    diagrams=Any[];witnesses=Any[]
    for q in 0:Int(c.degree)
        bars=Any[Any[b,d] for (b,d) in OP.finite_intervals(D;dim=q)]
        append!(bars,[Any[b,nothing] for b in OP.essential_births(D;dim=q)])
        sort!(bars;by=x->(x[1],something(x[2],Inf)));push!(diagrams,bars)
        if c.cocycles && q>0
            members=Any[]
            for (kind,vs) in ((:finite,OP.finite_intervals(D;dim=q)),(:essential,OP.essential_births(D;dim=q)))
                for (i,v) in enumerate(vs)
                    b=kind===:finite ? v[1] : v;d=kind===:finite ? v[2] : nothing
                    push!(members,(kind,i,b,d))
                end
            end
            sort!(members;by=v->something(v[4],Inf)-v[3],rev=true)
            for (kind,i,b,d) in Iterators.take(members,6)
                s=d===nothing ? something(c.threshold,max(b,1.0)) : (b+d)/2
                w=OP.Advanced.persistence_cocycle(D;dim=q,kind,index=i,scale=s)
                w.available || error("missing cocycle")
                w.source_vertices===nothing && error("pilot positive-degree witnesses require source vertex identities")
                terms=Any[]
                for (vertices,coefficient) in zip(w.source_vertices,w.cochain.coefficients)
                    v=collect(Int,vertices)
                    selection===nothing || (v=selection.indices[v])
                    push!(terms,vcat(v.-1,Int(coefficient)))
                end
                push!(witnesses,(degree=q,birth=b,death=d,scale=s,terms))
            end
        end
    end
    meta=selection===nothing ? nothing : (indices=OP.landmark_indices(selection).-1,radius=OP.covering_radius(selection),distances=[collect(v) for v in eachrow(OP.landmark_distances(selection))])
    return (;diagrams,witnesses,landmarks=meta)
end
function main()
    emit((kind="environment",tool="tamerop",pass_id=PASS,load_seconds,julia=string(VERSION),threads=Threads.nthreads(),blas_threads=BLAS.get_num_threads(),source=pathof(OP),memory=rss(),startup_scope="development snapshot with existing package caches; not standard installed startup"))
    for c in sort(collect(M.cases);by=c->something(findfirst(==(String(c.id)),IDS),length(IDS)+1))
        c.id in IDS || continue
        emit((kind="start",case=c.id,phase="prepare"))
        try
            path=joinpath(OUT,c.input);@assert bytes2hex(sha256(read(path)))==c.sha256
            raw=load_input(path);x=native(raw);before=signature(x)
            emit((kind="start",case=c.id,phase="warm"))
            warm=@timed query(x,c)
            @assert before==signature(x)
            emit((kind="first_use",case=c.id,seconds=warm.time,compile_seconds=warm.compile_time,recompile_seconds=warm.recompile_time,scope="same fixture; mathematical result discarded"))
            warm=nothing;x=nothing;GC.gc()
            accepted=0;expected_hash=nothing
            for attempt in 1:Int(M.max_attempts)
                accepted==M.samples && break
                GC.gc();emit((kind="start",case=c.id,phase="query",attempt))
                built=@timed native(raw);x=built.value;before=signature(x)
                t=@timed query(x,c)
                @assert before==signature(x)
                D=t.value[1];OP.Advanced.check_persistence_diagram(D;throw=true)
                clean=iszero(t.compile_time)&&iszero(t.recompile_time)&&iszero(built.compile_time)&&iszero(built.recompile_time)
                clean && (accepted+=1)
                emit((kind="sample",tool="tamerop",case=c.id,pass_id=PASS,attempt,sample=accepted,accepted=clean,seconds=t.time,construction_seconds=built.time,construction_plus_query_seconds=built.time+t.time,compile_seconds=t.compile_time,recompile_seconds=t.recompile_time,construction_compile_seconds=built.compile_time+built.recompile_time,allocation_bytes=t.bytes,gc_seconds=t.gctime,result_bytes=Base.summarysize(t.value),memory=rss(),reset_verified=true,backend=OP.provenance(D).backend,reduction_stats=get(OP.provenance(D),:reduction_stats,nothing)))
                if clean
                    emit((kind="start",case=c.id,phase="validation_export"))
                    encoded=Vector{UInt8}(codeunits(JSON3.write(output(t.value,c))))
                    digest=bytes2hex(sha256(encoded))
                    expected_hash===nothing && (expected_hash=digest)
                    @assert digest==expected_hash "mathematical output changed between fresh samples"
                    emit((kind="output_check",case=c.id,sample=accepted,sha256=digest))
                    if accepted==1
                        dest=joinpath(ENV["RIPSER_OUTPUT_DIR"],"tamerop_p$(PASS)_$(c.id).json.gz")
                        open(pipeline(`gzip -1 -c`;stdout=dest),"w") do io
                            write(io,encoded)
                        end
                    end
                    encoded=nothing
                end
                t=nothing;D=nothing;x=nothing;built=nothing
            end
            accepted==M.samples || error("insufficient compilation-free samples")
            raw=nothing;GC.gc();emit((kind="case_complete",case=c.id))
        catch e
            emit((kind="case_error",case=c.id,error=sprint(showerror,e,catch_backtrace())))
            GC.gc()
        end
    end
    emit((kind="complete",tool="tamerop",pass_id=PASS))
end
main()
