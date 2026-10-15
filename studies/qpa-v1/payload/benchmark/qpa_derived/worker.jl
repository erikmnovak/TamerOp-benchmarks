# Native public computations, with reset instrumentation reused from the
# previously audited harness. JSON export and independent validation are untimed.
include(joinpath(@__DIR__, "..", "qpa_uncached.jl"))
using SparseArrays
const QD_EVENT_IO = Ref{IO}()

function qd_prepare(f, spec)
    p = only(p for p in spec.posets if p.name == f.poset)
    P = FF.FinitePoset(Bool[p.leq[i][j] != 0 for i in 1:Int(p.n), j in 1:Int(p.n)])
    Pop = FF.FinitePoset(transpose(FF.leq_matrix(P)))
    ps = Dict("forward"=>P,"opposite"=>Pop)
    for Q in values(ps)
        FF.build_cache!(Q; cover=true, updown=true); FF.cover_edges(Q)
    end
    ds = Dict{Symbol,Any}()
    for (name,m) in pairs(f.modules)
        q = name == :R ? Pop : P
        edges = name == :R ? [[Int(e[2]),Int(e[1])] for e in p.covers] : p.covers
        ds[name] = decode_module(m,(covers=edges,),q)
    end
    field=coefficient_field(String(f.field));K=CM.coeff_type(field)
    map_inputs=Dict{Symbol,Vector{Matrix{K}}}()
    for (name,s) in pairs(f.maps)
        source,target=f.modules[Symbol(s.source)],f.modules[Symbol(s.target)]
        map_inputs[name]=[K[CM.coerce(field,rational_input(s.components[v][i][j]))
                            for i in 1:Int(target.dimensions[v]),j in 1:Int(source.dimensions[v])]
                          for v in 1:P.n]
    end
    (; p,P,Pop,ps,ds,map_inputs,field)
end

function qd_construct(f,c)
    mods = Dict(n=>make_module(d) for (n,d) in c.ds)
    K = CM.coeff_type(c.field)
    maps = Dict{Symbol,MD.PMorphism{K}}()
    for (name,s) in pairs(f.maps)
        source,target = mods[Symbol(s.source)],mods[Symbol(s.target)]
        comps = copy.(c.map_inputs[name])
        maps[name] = MD.PMorphism(source,target,comps)
    end
    (;mods,maps)
end

qd_ext(M,N,d) = DF.Ext(M,N,OPT.DerivedFunctorOptions(maxdeg=d,model=:projective))
function qd_tensor(R,L,field)
    K = CM.coeff_type(field)
    T = DF.Tor(R,L,OPT.DerivedFunctorOptions(maxdeg=0,model=:first))
    # The augmentation supplies an elementary-tensor adapter to the existing
    # Tor_0 interface. Every solve, map evaluation and coordinate reduction is
    # charged inside the complete query. Nothing is supplied from an old result.
    res = T.resRop; gens = res.gens[1]
    out = Vector{Vector{K}}()
    for v in 1:R.Q.n
        R.dims[v]*L.dims[v] == 0 && continue
        A = Matrix(MD.component(res.aug,v))
        _,piv0 = FL.rref(field,A)
        piv = collect(Int,piv0)
        @assert length(piv) == R.dims[v]
        lifts = zeros(K,size(A,2),R.dims[v])
        lifts[piv,:] = FL.solve_fullcolumn(field,A[:,piv],Matrix{K}(I,R.dims[v],R.dims[v]))
        active = findall(u->FF.leq(R.Q,u,v),gens)
        @assert length(active)==size(A,2)
        for j in 1:R.dims[v], i in 1:L.dims[v]
            z = zeros(K,T.dims[1])
            for (k,gidx) in enumerate(active)
                u=gens[gidx]; coeff=lifts[k,j]
                iszero(coeff) && continue
                z[(T.offsets[1][gidx]+1):T.offsets[1][gidx+1]] .+= coeff .* MD.map_leq(L,v,u)[:,i]
            end
            push!(out,DF.coordinates(T,0,z))
        end
    end
    (; dimension=DF.dim(T,0), elementary_columns=out, tor=T)
end

function qd_query(f,b,c)
    m=b.mods;K=CM.coeff_type(c.field)
    if f.task == "yoneda"
        A=qd_ext(m[:L],m[:M],2);B=qd_ext(m[:M],m[:N],1)
        T=DF.Ext(A.res,m[:N];maxdeg=2)
        ai=Matrix{K}(I,DF.dim(A,1),DF.dim(A,1));bi=Matrix{K}(I,DF.dim(B,1),DF.dim(B,1))
        _, table = DF.yoneda_product(B,1,bi,A,1,ai;ELN=T)
        products=[[table[:,j,i] for j in axes(bi,2)] for i in axes(ai,2)]
        return (; ext=Dict(:LM=>A,:MN=>B,:LN=>T),products)
    elseif f.task == "induced"
        A=qd_ext(m[:L],m[:N],2);B=qd_ext(m[:Lp],m[:N],2)
        C=DF.Ext(A.res,m[:Np];maxdeg=2)
        first_columns=[[Vector(v) for v in eachcol(DF.ext_map_first(B,A,b.maps[:f];t=k))] for k in 1:2]
        second_columns=[[Vector(v) for v in eachcol(DF.ext_map_second(A,C,b.maps[:g];t=k))] for k in 1:2]
        return (;ext=Dict(:LN=>A,:LpN=>B,:LNp=>C),first_columns,second_columns)
    elseif f.task == "tensor"
        return qd_tensor(m[:R],m[:L],c.field)
    end
    error("Unknown task")
end

qd_matrix(A) = [[canonical(A[i,j]) for j in axes(A,2)] for i in axes(A,1)]
qd_map(f) = [qd_matrix(MD.component(f,v)) for v in 1:f.dom.Q.n]
qd_module(M,p) = (;dimensions=copy(M.dims),edge_matrices=[qd_matrix(M.edge_maps[Int(e[1]),Int(e[2])]) for e in p.covers])
function qd_cochain(E,t,z)
    N=E.N;gens=E.res.gens[t+1];offs=E.offsets[t+1];K=eltype(z)
    # Expand generator images to actual maps P_t -> N. This is validation-only
    # representation export, using structure maps rather than another lift.
    [begin
        active=findall(u->FF.leq(N.Q,u,v),gens)
        A=zeros(K,N.dims[v],length(active))
        for (j,i) in enumerate(active)
            A[:,j]=MD.map_leq(N,gens[i],v)*z[(offs[i]+1):offs[i+1]]
        end
        qd_matrix(A)
    end for v in 1:N.Q.n]
end
function qd_ext_export(E,c,d)
    res=E.res
    (;terms=[qd_module(res.Pmods[k],c.p) for k in 1:d+1],
      differentials=[qd_map(res.d_mor[k]) for k in 1:d],augmentation=qd_map(res.aug),
      cochains=[[qd_cochain(E,k,z) for z in DF.basis(E,k)] for k in 1:d],
      coordinate_columns=[[canonical.(DF.coordinates(E,k,z)) for z in DF.basis(E,k)] for k in 1:d],
      dimensions=[DF.dim(E,k) for k in 1:d])
end
function qd_export(f,a,c)
    if f.task == "tensor"
        return (;dimension=a.dimension,elementary_columns=[canonical.(v) for v in a.elementary_columns])
    end
    ext=Dict(n=>qd_ext_export(E,c,(f.task=="yoneda" && n!=:LN) ? 1 : 2) for (n,E) in a.ext)
    if f.task == "yoneda"
        return (;ext,products=[[canonical.(v) for v in vs] for vs in a.products])
    end
    (;ext,first_columns=[[canonical.(v) for v in vs] for vs in a.first_columns],
      second_columns=[[canonical.(v) for v in vs] for vs in a.second_columns])
end

@noinline function qd_run(f,spec,phase,sample,pass,warm)
    c=qd_prepare(f,spec);reset=u_reset!(c.ps)
    b=nothing;a=nothing;pre=nothing
    if phase=="complete_query"
        b=qd_construct(f,c);pre=Dict(n=>u_module_state(M) for (n,M) in b.mods)
    end
    GC.gc(true)
    uwrite(QD_EVENT_IO[],(;kind="timer_start",case=String(f.id),phase,warmup=warm))
    timed = @timed begin
        if phase != "complete_query"; b=qd_construct(f,c);end
        if phase != "native_construction"; a=qd_query(f,b,c);end
        nothing
    end
    uwrite(QD_EVENT_IO[],(;kind="timer_end",case=String(f.id),phase,warmup=warm))
    if phase=="native_construction";pre=Dict(n=>u_module_state(M) for (n,M) in b.mods);end
    @assert all(M->MD.check_module(M).valid,values(b.mods))
    @assert all(h->MD.check_morphism(h).valid,values(b.maps))
    answer=a===nothing ? nothing : qd_export(f,a,c)
    for M in values(b.mods);push!(U_LIFETIMES,WeakRef(M.dims));end
    if a!==nothing && f.task!="tensor"
        for E in values(a.ext);push!(U_LIFETIMES,WeakRef(E.cohom),WeakRef(E.res.Pmods));end
    elseif a!==nothing
        push!(U_LIFETIMES,WeakRef(a.tor.homol),WeakRef(a.tor.resRop.Pmods))
    end
    (;kind="timing",tool="TamerOp",case=String(f.id),task=String(f.task),field=String(f.field),
      phase,sample,pass,warmup=warm,seconds=timed.time,bytes=timed.bytes,gc_seconds=timed.gctime,
      compile_seconds=timed.compile_time,recompile_seconds=timed.recompile_time,
      eligible=!warm && timed.compile_time==timed.recompile_time==0 && timed.time<=60,
      reset_verified=true,reset,constructor_state=pre,answer)
end

function qd_correctness(f,spec)
    c=qd_prepare(f,spec);reset=u_reset!(c.ps)
    b=qd_construct(f,c)
    @assert all(M->MD.check_module(M).valid,values(b.mods))
    @assert all(h->MD.check_morphism(h).valid,values(b.maps))
    a=qd_query(f,b,c)
    (;kind="correctness",tool="TamerOp",case=String(f.id),task=String(f.task),field=String(f.field),
      reset_verified=true,reset,answer=qd_export(f,a,c))
end

function qd_main()
    Threads.nthreads()==1 || error("Use --threads=1");BLAS.set_num_threads(1)
    input,output,field=ARGS[1:3];samples=parse(Int,ARGS[4]);pass=parse(Int,ARGS[5])
    wanted=length(ARGS)>5 && !isempty(ARGS[6]) ? split(ARGS[6],',') : String[]
    correctness=length(ARGS)>6 && ARGS[7]=="correctness"
    isfile(output) && error("Refusing to overwrite evidence")
    spec=JSON3.read(read(input,String));fs=[f for f in spec.cases if f.field==field && (isempty(wanted)||f.id in wanted)]
    isempty(fs) && error("No cases selected");iseven(pass) && reverse!(fs)
    append!(U_COEFFICIENT_PARENTS,[FL.Nemo.GF(p) for p in (2,3,101)])
    open(output,"w") do io
        QD_EVENT_IO[]=io
        uwrite(io,(;kind="metadata",tool="TamerOp",julia=string(VERSION),field,
            cases=[String(f.id) for f in fs],regime=correctness ? "correctness-only" : "warm-uncached",samples,
            source_hashes=package_hashes(ROOT),julia_options=string(Base.JLOptions())))
        for f in fs
            if correctness
                uwrite(io,qd_correctness(f,spec))
                println("Verified ",f.id);flush(stdout)
                continue
            end
            for phase in spec.phases
                uwrite(io,qd_run(f,spec,String(phase),0,pass,true))
            end
            for sample in 1:samples,phase in spec.phases
                for attempt in 1:3
                    row=qd_run(f,spec,String(phase),sample,pass,false)
                    uwrite(io,(;row...,attempt))
                    row.eligible && break
                end
            end
            println("Completed ",f.id);flush(stdout)
        end
        uwrite(io,(;kind="completed",cases=[String(f.id) for f in fs]))
    end
end
abspath(PROGRAM_FILE)==abspath(@__FILE__) && qd_main()
