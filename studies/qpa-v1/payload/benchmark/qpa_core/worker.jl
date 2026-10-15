# Shared native input decoding and reset instrumentation; no library code changes.
include(joinpath(@__DIR__,"..","qpa_derived","worker.jl"))
const AC=TamerOp.AbelianCategories
include(joinpath(@__DIR__,"diagrams.jl"))

function qc_query(f,b,c)
    f.workflow in ("Q6","Q7") && return qg_query(f,b,c)
    m=b.mods
    if f.task=="hom_basis"
        return (;hom=DF.basis(DF.Hom(m[:M],m[:N])))
    elseif f.task=="ext1_dimension"
        E=qd_ext(m[:M],m[:N],1)
        return (;dimension=DF.dim(E,1),owner=E)
    elseif f.task=="full_hom_ext"
        a=full_query((M=m[:M],N=m[:N]),Int(f.maxdegree))
        return (;hom=a.maps,ext=a.e,coords=a.coords,reps=a.reps)
    elseif f.task=="kernel_image_cokernel"
        h=b.maps[:f]
        kernel,ki=AC.kernel_with_inclusion(h)
        im,ii=AC.image_with_inclusion(h)
        cokernel,cq=AC.cokernel_with_projection(h)
        parts=[FL.solve_fullcolumn(c.field,Matrix(MD.component(ii,v)),Matrix(MD.component(h,v))) for v in 1:c.P.n]
        ip=MD.PMorphism(m[:A],im,parts)
        return (;kernel,im,cokernel,ki,ii,ip,cq)
    elseif f.task in ("projective","injective")
        options=OPT.ResolutionOptions(maxlen=Int(f.maxdegree))
        r=f.task=="projective" ? DF.projective_resolution(m[:X],options) : DF.injective_resolution(m[:X],options)
        terms=DF.resolution_terms(r);diffs=DF.resolution_differentials(r)
        aug=f.task=="projective" ? DF.augmentation_map(r) : DF.coaugmentation_map(r)
        # A request for actual finite terms and maps must materialize lazy components.
        for h in (aug,diffs...),v in 1:c.P.n;MD.component(h,v);end
        return (;terms,diffs,aug,owner=r)
    end
    error("Unknown core task: $(f.task)")
end
function qc_export(f,a,c)
    f.workflow in ("Q6","Q7") && return qg_export(f,a,c)
    if f.task=="hom_basis"
        return (;hom=[qd_map(h) for h in a.hom])
    elseif f.task=="ext1_dimension"
        return (;dimension=a.dimension)
    elseif f.task=="full_hom_ext"
        return (;hom=[qd_map(h) for h in a.hom],ext=qd_ext_export(a.ext,c,Int(f.maxdegree)),
            requested_coordinate_columns=[[canonical.(x) for x in xs] for xs in a.coords])
    elseif f.task=="kernel_image_cokernel"
        return (;kernel=qd_module(a.kernel,c.p),image=qd_module(a.im,c.p),cokernel=qd_module(a.cokernel,c.p),
            kernel_inclusion=qd_map(a.ki),image_inclusion=qd_map(a.ii),image_projection=qd_map(a.ip),cokernel_projection=qd_map(a.cq))
    elseif f.task in ("projective","injective")
        return (;terms=[qd_module(M,c.p) for M in a.terms],differentials=[qd_map(h) for h in a.diffs],augmentation=qd_map(a.aug))
    end
    error("Unknown export")
end
function qc_track(b,a)
    qg_track(b,a)
    for M in values(b.mods);push!(U_LIFETIMES,WeakRef(M.dims));end
    if a!==nothing
        if hasproperty(a,:hom);push!(U_LIFETIMES,WeakRef(a.hom));end
        E=hasproperty(a,:ext) ? a.ext : hasproperty(a,:owner) ? a.owner : nothing
        if E!==nothing && hasproperty(E,:cohom)
            push!(U_LIFETIMES,WeakRef(E.cohom),WeakRef(E.res.Pmods))
        end
        if hasproperty(a,:terms);push!(U_LIFETIMES,WeakRef(a.terms),WeakRef(a.diffs));end
        if hasproperty(a,:kernel)
            for M in (a.kernel,a.im,a.cokernel);push!(U_LIFETIMES,WeakRef(M.dims));end
        end
    end
end
@noinline function qc_run(f,spec,phase,sample,pass,warm,correctness)
    c=qd_prepare(f,spec);reset=u_reset!(c.ps);b=nothing;a=nothing;pre=nothing
    if correctness
        b=qc_construct(f,c);a=qc_query(f,b,c)
    else
        if phase=="complete_query"
            b=qc_construct(f,c);pre=Dict(n=>u_module_state(M) for (n,M) in b.mods)
        end
        GC.gc(true)
        uwrite(QD_EVENT_IO[],(;kind="timer_start",case=String(f.id),phase,warmup=warm))
        timed=@timed begin
            if phase!="complete_query";b=qc_construct(f,c);end
            if phase!="native_construction";a=qc_query(f,b,c);end
            nothing
        end
        uwrite(QD_EVENT_IO[],(;kind="timer_end",case=String(f.id),phase,warmup=warm))
        if phase=="native_construction";pre=Dict(n=>u_module_state(M) for (n,M) in b.mods);end
    end
    @assert all(M->MD.check_module(M).valid,values(b.mods))
    @assert all(h->MD.check_morphism(h).valid,values(b.maps))
    answer=a===nothing ? nothing : qc_export(f,a,c)
    qc_track(b,a)
    if correctness
        return (;kind="correctness",tool="TamerOp",case=String(f.id),task=String(f.task),field=String(f.field),reset_verified=true,reset,answer)
    end
    (;kind="timing",tool="TamerOp",case=String(f.id),task=String(f.task),field=String(f.field),phase,sample,pass,warmup=warm,
        seconds=timed.time,bytes=timed.bytes,gc_seconds=timed.gctime,compile_seconds=timed.compile_time,recompile_seconds=timed.recompile_time,
        eligible=!warm && timed.compile_time==timed.recompile_time==0 && timed.time<=60,reset_verified=true,reset,constructor_state=pre,answer)
end
function qc_main()
    Threads.nthreads()==1 || error("Use --threads=1");BLAS.set_num_threads(1)
    input,output,field=ARGS[1:3];samples=parse(Int,ARGS[4]);pass=parse(Int,ARGS[5]);wanted=isempty(ARGS[6]) ? String[] : split(ARGS[6],',')
    correctness=ARGS[7]=="correctness";isfile(output) && error("Refusing to overwrite evidence")
    spec=JSON3.read(read(input,String));fs=[f for f in spec.cases if f.field==field && (isempty(wanted)||f.id in wanted)]
    isempty(fs) && error("No selected cases");iseven(pass) && reverse!(fs)
    append!(U_COEFFICIENT_PARENTS,[FL.Nemo.GF(p) for p in (2,3,101)])
    open(output,"w") do io
        QD_EVENT_IO[]=io
        uwrite(io,(;kind="metadata",tool="TamerOp",julia=string(VERSION),field,cases=[String(f.id) for f in fs],
            regime=correctness ? "correctness-only" : "warm-uncached",source_hashes=package_hashes(ROOT),julia_options=string(Base.JLOptions())))
        for f in fs
            if correctness
                uwrite(io,qc_run(f,spec,"correctness",0,pass,false,true))
            else
                for phase in spec.phases;uwrite(io,qc_run(f,spec,String(phase),0,pass,true,false));end
                for sample in 1:samples,phase in spec.phases
                    for attempt in 1:3
                        row=qc_run(f,spec,String(phase),sample,pass,false,false);uwrite(io,(;row...,attempt));row.eligible && break
                    end
                end
            end
            println("Completed ",f.id);flush(stdout)
        end
        uwrite(io,(;kind="completed",cases=[String(f.id) for f in fs]))
    end
end
abspath(PROGRAM_FILE)==abspath(@__FILE__) && qc_main()
