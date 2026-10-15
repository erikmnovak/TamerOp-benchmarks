using SHA, JSON3, LinearAlgebra
emit(x)=(println(JSON3.write(x));flush(stdout))
load_seconds=@elapsed @eval import TamerOp as OP
const OUT=ARGS[1];const CASE=JSON3.read(read(ARGS[2],String));const SAMPLES=parse(Int,ARGS[3]);const DEST=ARGS[4]
signature(x)=bytes2hex(sha256(reinterpret(UInt8,vec(x))))
function query(x,c)
    OP.cubical_persistence(x;input=c.convention=="V" ? :vertices : :top_cells,
        order=Symbol(c.order),field=OP.CoreModules.F2(),
        construction=OP.ConstructionOptions(budget=OP.ConstructionBudget(memory_budget_bytes=128*1024^3)))
end
function canonical(result,c)
    counts=Dict{Tuple{Int,Float64,Float64},Int}();sgn=c.order=="superlevel" ? -1 : 1
    for d in 0:length(c.shape)-1
        for (b,e) in OP.finite_intervals(result;dim=d)
            key=(d,sgn*Float64(b),sgn*Float64(e));@assert isfinite(key[2]) && key[2]<key[3]
            counts[key]=get(counts,key,0)+1
        end
        for b in OP.essential_births(result;dim=d)
            key=(d,sgn*Float64(b),Inf);counts[key]=get(counts,key,0)+1
        end
    end
    [[k[1],k[2],isinf(k[3]) ? nothing : k[3],counts[k]] for k in sort!(collect(keys(counts)))]
end
function main()
    c=CASE
    emit((kind="environment",tool="tamerop",load_seconds,julia=string(VERSION),source=pathof(OP),threads=Threads.nthreads(),blas_threads=BLAS.get_num_threads(),reset="fresh public call; no result or topology cache; immutable package tables retained"))
    emit((kind="start",phase="prepare",case=c.id))
    path=joinpath(OUT,c.input);@assert bytes2hex(sha256(read(path)))==c.compressed_sha256
    raw=read(`gzip -dc $path`);@assert bytes2hex(sha256(raw))==c.raw_sha256
    @assert ENDIAN_BOM==0x04030201
    x=reshape(Float64.(reinterpret(UInt16,raw)),Tuple(Int.(c.shape)));raw=nothing
    before=signature(x);GC.gc()
    emit((kind="start",phase="warm",case=c.id))
    w=x.+1;warm=@timed query(w,c)
    emit((kind="warmup",case=c.id,seconds=warm.time,compile_seconds=warm.compile_time,recompile_seconds=warm.recompile_time))
    warm=nothing;w=nothing;GC.gc()
    accepted=0
    for attempt in 1:8
        accepted==SAMPLES && break
        GC.gc();@assert signature(x)==before
        emit((kind="start",phase="query",case=c.id,attempt))
        measured=@timed query(x,c)
        emit((kind="start",phase="verify",case=c.id,attempt))
        @assert signature(x)==before
        clean=iszero(measured.compile_time)&&iszero(measured.recompile_time);clean && (accepted+=1)
        histogram=canonical(measured.value,c);file=joinpath(DEST,"a$(attempt).json");write(file,JSON3.write(histogram))
        emit((kind="sample",tool="tamerop",case=c.id,sample=accepted,attempt,accepted=clean,seconds=measured.time,
            compile_seconds=measured.compile_time,recompile_seconds=measured.recompile_time,allocation_bytes=measured.bytes,gc_seconds=measured.gctime,
            input_bytes=sizeof(x),result_bytes=Base.summarysize(measured.value),reset_verified=true,input_sha256=before,
            output=basename(file),output_sha256=bytes2hex(sha256(read(file))),intervals=sum(row[4] for row in histogram;init=0)))
        measured=nothing;histogram=nothing
    end
    @assert accepted==SAMPLES
    x=nothing;GC.gc();emit((kind="complete",tool="tamerop",case=c.id))
end
main()
