# Compiled methods, uncached mathematics. Frozen fixture/oracle code is included
# unchanged; its guarded main is not run.
include(joinpath(@__DIR__, "qpa_diversity.jl"))
using Dates
const UOUT = joinpath(ROOT, "audit/2026-09-27/qpa_uncached")
const UPHASES = ("native_construction", "complete_query", "construction_and_query")
const IR = TamerOp.IndicatorResolutions
const RS = DF.Resolutions
const FU = DF.Functoriality
const U_GLOBALS = (
    (FL, :_FULLCOLUMN_FACTOR_CACHE), (FL, :_NEMO_FULLCOLUMN_FACTOR_CACHE_QQ),
    (FL, :_NEMO_FULLCOLUMN_FACTOR_CACHE_FP), (FL, :_F2_FULLCOLUMN_FACTOR_CACHE),
    (FL, :_F3_FULLCOLUMN_FACTOR_CACHE), (FL, :_FLOAT_SPARSE_FACTOR_CACHE),
    (RS, :_ACTIVE_INDEX_PLAN_CACHE), (RS, :_BASE_VERTEX_GROUPS_CACHE),
    (RS, :_ACTIVE_UPSET_VECTOR_CACHE), (RS, :_DOWNSET_HOM_STRUCTURE_CACHE),
    (RS, :_DOWNSET_POSTCOMPOSE_SYSTEM_CACHE),
    (FU, :_HOM_SOLVE_WORKSPACE_CACHE), (FU, :_HOM_BASIS_SOLVE_PLAN_CACHE),
    (FU, :_SUPPORT_SOLVE_PLAN_CACHE), (FU, :_COEFF_MAP_PLAN_CACHE),
    (FU, :_TENSOR_COEFF_PLAN_CACHES), (FU, :_TENSOR_COEFF_RESULT_CACHES),
)
const U_LIFETIMES = WeakRef[]
# Strong roots for explicitly retained coefficient-category preparation.
const U_COEFFICIENT_PARENTS = Any[]

function uwrite(io, row)
    JSON3.write(io, row); write(io, '\n'); flush(io)
    nothing
end
function u_tls_context()
    get(task_local_storage(), CM._TASK_LOCAL_CACHE_KEY, nothing)
end
function u_tls_counts()
    context = u_tls_context()
    context === nothing && return (; metadata_entries=0, live_owners=0, owner_payloads=0)
    owners = 0; payloads = 0
    for entry in values(context.values)
        owner = entry.owner.value
        if owner !== nothing
            owners += 1
            payloads += length(owner.values)
        end
    end
    (; metadata_entries=length(context.values), live_owners=owners, owner_payloads=payloads)
end
function u_global_counts()
    counts = Dict(string(nameof(m), ".", s) => length(getfield(m, s)) for (m,s) in U_GLOBALS)
    counts["IndicatorResolutions.prefix_families"] = length(IR._INDICATOR_PREFIX_FAMILIES)
    counts["IndicatorResolutions.prefix_entries"] = sum((sum(length, fam.upset_shards)
        for fam in values(IR._INDICATOR_PREFIX_FAMILIES)); init=0)
    counts["IndicatorResolutions.birth_plan_entries"] = sum(length, IR._INDICATOR_BIRTH_PLAN_SHARDS)
    counts
end
function u_poset_state(P)
    pc = getfield(P, :cache)
    cc = pc.cover
    (; n=P.n, cover_edges_prepared=pc.cover_edges !== nothing,
       cover_prepared=cc !== nothing, upsets_prepared=pc.upsets !== nothing,
       downsets_prepared=pc.downsets !== nothing, hom_route_entries=length(pc.hom_route_choice),
       chain_parent_tasks=cc === nothing ? 0 : length(cc.chain_parent.values),
       chain_parent_dense_tasks=cc === nothing || cc.chain_parent_dense === nothing ? 0 : length(cc.chain_parent_dense.values))
end
function u_state(posets)
    (; global_caches=u_global_counts(), task_local=u_tls_counts(),
       posets=Dict(name => u_poset_state(P) for (name,P) in posets),
       retained_coefficient_parent_count=length(U_COEFFICIENT_PARENTS),
       tracked_prior_roots=length(U_LIFETIMES),
       live_prior_roots=count(w -> w.value !== nothing, U_LIFETIMES),
       external_session_cache="absent: native Hom/Ext calls; one-shot Ext creates a fresh local ResolutionCache")
end
function u_module_state(M)
    tasks = Dict{String,Int}()
    for name in fieldnames(typeof(M))
        value = getfield(M, name)
        value isa CM._TaskLocalCache && (tasks[string(name)] = length(value.values))
    end
    payloads = count(A -> A isa CM.BackendMatrix && A.payload !== nothing, (A for (_,A) in M.edge_maps))
    (; type=string(typeof(M)), task_local_payloads=tasks, backend_payloads=payloads,
       cover_edge_count=length(M.edge_maps), dimension_count=length(M.dims),
       direct_sum_stats_prepared=true)
end
u_pair_state(pair) = (; source=u_module_state(pair.M), target=u_module_state(pair.N))
function u_result_state(a)
    a === nothing && return nothing
    (; hom_maps=length(a.maps), ext_dimensions=a.dims,
       resolution_terms=length(a.e.res.Pmods),
       cohomology=[(; degree=getfield(H,:t),
           cached_fields=[string(s) for s in (:_Cx, :_Q, :_Bfull, :_Hrep, :_coord_rows, :_coord_proj, :_checked_coord_plan)
                          if getfield(H,s) !== nothing],
           cycle_factor=getfield(H,:Kfactor)[] !== nothing,
           quotient_factor=getfield(H,:Bfull_factor)[] !== nothing) for H in a.e.cohom])
end

# The context owns weak references, but their live owners can hold mathematical
# payloads. Clear every live owner, including scratch/identity/arena fields that
# the narrower Modules clearing helpers intentionally leave intact.
function u_clear_task_context!()
    context = u_tls_context()
    if context !== nothing
        for entry in values(context.values)
            owner = entry.owner.value
            owner === nothing || CM._clear_task_local!(owner)
        end
        empty!(context.values)
        delete!(task_local_storage(), CM._TASK_LOCAL_CACHE_KEY)
    end
    nothing
end
function u_reset!(posets)
    before = u_state(posets)
    FL._clear_fullcolumn_cache!()
    FL._clear_f2_fullcolumn_cache!()
    FL._clear_f3_fullcolumn_cache!()
    RS._clear_resolution_plan_caches!()
    FU._clear_functoriality_caches!()
    IR._clear_indicator_prefix_caches!()
    # The production helper retains empty typed family containers. Drop them as
    # well, so the reset postcondition is zero for every inventoried store.
    lock(() -> empty!(IR._INDICATOR_PREFIX_FAMILIES), IR._INDICATOR_PREFIX_FAMILY_LOCK)
    u_clear_task_context!()
    for P in values(posets)
        pc = getfield(P, :cache)
        empty!(pc.hom_route_choice)
        pc.cover === nothing || FF._clear_chain_parent_cache!(pc.cover)
    end
    FL._reset_conversion_counters!()
    GC.gc(true)
    after = u_state(posets)
    @assert all(iszero, values(after.global_caches))
    @assert after.task_local.metadata_entries == after.task_local.owner_payloads == 0
    @assert after.live_prior_roots == 0 "A previous native input/result is still reachable after reset"
    @assert all(p -> p.hom_route_entries == p.chain_parent_tasks == p.chain_parent_dense_tasks == 0,
                values(after.posets))
    empty!(U_LIFETIMES)
    (; before, after, verified_empty=true, prior_inputs_and_results_released=true)
end
function u_track!(pair, a)
    # These mutable roots witness the lifetimes of immutable module/result
    # wrappers without relying on weak references to immutable Julia values.
    for M in (pair.M, pair.N)
        push!(U_LIFETIMES, WeakRef(M.dims))
    end
    if a !== nothing
        push!(U_LIFETIMES, WeakRef(a.maps), WeakRef(a.e.cohom), WeakRef(a.e.res.Pmods))
    end
    nothing
end
function u_export(io, a, f, pair, phase, sample, attempt, pass, run_id)
    buffer = IOBuffer()
    export_result(buffer, a, f, pair)
    row = JSON3.read(String(take!(buffer)), Dict{String,Any})
    merge!(row, Dict("tool"=>"TamerOp", "phase"=>phase, "sample"=>sample,
                     "attempt"=>attempt, "pass"=>pass, "run_id"=>run_id))
    uwrite(io, row)
end
function u_construct_and_query(d, maxdegree)
    pair = make_pair(d)
    a = full_query(pair, maxdegree)
    (; pair, a)
end

# No input/result escapes this frame: only scalar counters and inventories.
# The independent construction phase supplies a same-input observation of the
# constructor boundary for the joint timer, avoiding inspection inside it.
@noinline function u_run_phase(f, d, posets, phase, constructor_reference=nothing;
                              export_io=nothing, sample=0, attempt=0, pass=0, run_id="")
    reset = u_reset!(posets)
    a = nothing
    maxdegree = Int(f.maxdegree)
    if phase == "native_construction"
        timed = measure(() -> make_pair(d))
        pair = timed.value
        constructor_prepared = (; observation="actual freshly constructed timed pair",
                                pair=u_pair_state(pair), state=u_state(posets))
    elseif phase == "complete_query"
        pair = make_pair(d)
        constructor_prepared = (; observation="actual freshly constructed pair before query timer",
                                pair=u_pair_state(pair), state=u_state(posets))
        timed = measure(() -> full_query(pair, maxdegree))
        a = timed.value
    elseif phase == "construction_and_query"
        constructor_reference === nothing && error("Missing independent constructor evidence")
        constructor_prepared = (; observation="same fixture/sample independent native_construction observation; no inspection inside joint timer",
                                reference_phase="native_construction", reference=constructor_reference)
        timed = measure(() -> u_construct_and_query(d, maxdegree))
        pair = timed.value.pair
        a = timed.value.a
    else
        error("Unknown phase $phase")
    end
    post_measurement = (; state=u_state(posets), pair=u_pair_state(pair), result=u_result_state(a),
                        conversions=FL._conversion_counters())
    failure = nothing
    try
        if a === nothing
            @assert MD.check_module(pair.M).valid && MD.check_module(pair.N).valid
        else
            verify(a, f, pair; coords=a.coords)
            export_io === nothing || u_export(export_io, a, f, pair, phase, sample, attempt, pass, run_id)
        end
    catch err
        failure = sprint(showerror, err, catch_backtrace())
    end
    validation_state = u_state(posets)
    u_track!(pair, a)
    eligible = timed.compile_seconds == 0 && timed.recompile_seconds == 0 && failure === nothing
    (; seconds=timed.seconds, bytes=timed.bytes, gc_seconds=timed.gc_seconds,
       compile_seconds=timed.compile_seconds, recompile_seconds=timed.recompile_seconds,
       eligible, correctness_passed=failure === nothing, failure,
       reset_evidence=reset, constructor_prepared, post_measurement, validation_state)
end

function uncached_main()
    BLAS.set_num_threads(1)
    Threads.nthreads() == 1 || error("This reset audit requires --threads=1")
    pass = parse(Int, get(ENV,"UNCACHED_PASS","1")); pass in (1,2) || error("Invalid pass")
    samples = parse(Int, get(ENV,"UNCACHED_SAMPLES","3")); samples > 0 || error("Samples must be positive")
    suffix = get(ENV,"UNCACHED_SUFFIX","")
    occursin(r"^[A-Za-z0-9_-]+$",suffix) || error("UNCACHED_SUFFIX must be a nonempty unique filename suffix")
    max_attempts = parse(Int,get(ENV,"UNCACHED_MAX_ATTEMPTS","3")); 1 <= max_attempts <= 5 || error("Invalid attempts")
    warmup_rounds = parse(Int,get(ENV,"UNCACHED_WARMUP_ROUNDS","1")); 1 <= warmup_rounds <= 3 || error("Invalid warmup rounds")
    wanted = split(get(ENV,"UNCACHED_CASES",""), ',')
    spec = JSON3.read(read(FIXTURES,String))
    @assert length(spec.fixtures) == 48
    fs = [f for f in spec.fixtures if wanted == [""] || String(f.case) in wanted]
    isempty(fs) && error("No selected fixtures")
    wanted == [""] || @assert Set(wanted) == Set(String(f.case) for f in fs)
    pass == 2 && reverse!(fs)
    pospecs = Dict(String(p.name) => p for p in spec.posets)
    posets = Dict(String(p.name) => FF.FinitePoset(Bool[p.leq[i][j] != 0 for i in 1:Int(p.n), j in 1:Int(p.n)]) for p in spec.posets)
    for P in values(posets)
        FF.build_cache!(P; cover=true, updown=true)
        FF.cover_edges(P)
    end
    # Nemo field-parent interning is declared coefficient-category preparation.
    empty!(U_COEFFICIENT_PARENTS)
    append!(U_COEFFICIENT_PARENTS, [FL.Nemo.GF(p) for p in (2,3,101)])
    modules = Dict(String(m.id) => decode_module(m,pospecs[String(m.poset)],posets[String(m.poset)]) for m in spec.modules)
    data = map(fs) do f
        source, target = modules[String(f.source)], modules[String(f.target)]
        @assert source.P === target.P && source.field == target.field
        @assert String(f.field) == String(only(m.field for m in spec.modules if String(m.id) == String(f.source)))
        (; source, target)
    end
    mkpath(UOUT)
    name = "tamerop_pass$(pass)$(suffix)"
    rawpath, correctpath, contextpath = (joinpath(UOUT,name*x) for x in (".jsonl","_correctness.jsonl","_context.json"))
    any(ispath, (rawpath,correctpath,contextpath)) && error("Refusing to overwrite an existing suffix")
    run_id = name * "_pid$(getpid())"
    config = (; run_id, process_id=getpid(), tool="TamerOp", tool_version=string(pkgversion(TamerOp)),
        pass,samples,max_attempts,warmup_rounds,julia=string(VERSION),threads=Threads.nthreads(),
        blas_threads=BLAS.get_num_threads(), source=pathof(TamerOp),
        compiled_modules_flag=Base.JLOptions().use_compiled_modules,
        pkgimages_flag=Base.JLOptions().use_pkgimages,
        command=String.(Base.ARGS), julia_options=string(Base.JLOptions()),
        harness_sha256=bytes2hex(sha256(read(@__FILE__))),
        included_harness_sha256=bytes2hex(sha256(read(joinpath(@__DIR__,"qpa_diversity.jl")))),
        fixture_sha256=bytes2hex(sha256(read(FIXTURES))),
        source_hashes=package_hashes(dirname(Base.active_project())),
        cases=String[String(f.case) for f in fs],phases=collect(UPHASES),
        regime="warm-uncached", starting_preparation="Decoded exact scalar arrays; finite-poset order, cover graph, cover edges and upsets/downsets; Nemo coefficient-field parents. Constructor copy/isolation and all module construction are charged in native and combined phases.",
        reset="All inventoried global factors/resolution/functoriality/indicator stores cleared; live task-local owners cleared and TLS context removed; query-derived poset parent/route memo cleared; full GC; zero postconditions plus weak lifetime witnesses. No within-call cache policy disabled.",
        contract="Original 48 diversity fixtures/oracles, natural Hom basis and positive Ext representatives through maxdegree with public coordinates; identical exact verification and export_result. Constructor-only rows validate both native modules.",
        timing="Each phase resets independently. complete_query constructs a fresh pair outside its timer and records actual constructor-prepared state. construction_and_query times copies, both constructors and the full query together, referencing its independent native_construction observation without timed inspection. GC before each timer; validation and export after timer; pass2 reverses fixtures. Shared machine.",
        warmup="Separate throwaway native inputs/results for each selected fixture, all exact callbacks including output materialization; reset before every measured attempt. Warmup counters saved in context; contaminated measurement rows retained and retried up to max_attempts.",
        memory="bytes is Julia allocation traffic during the timer, not retained/peak memory; native FLINT allocations may be omitted", nemo_prepared_fields=length(U_COEFFICIENT_PARENTS))
    config_hash = bytes2hex(sha256(JSON3.write(config)))
    warmups = Any[]
    counts = Dict(p=>0 for p in UPHASES)
    accepted = Dict(p=>0 for p in UPHASES)
    contamination = Dict(p=>0 for p in UPHASES)
    final_reset = nothing
    function savecontext(status, failure=nothing)
        open(contextpath,"w") do io
            JSON3.pretty(io,(; configuration=config, configuration_sha256=config_hash,
                status, failure, warmup_records=warmups, per_phase_rows=counts,
                per_phase_eligible=accepted, per_phase_contaminated=contamination, final_reset))
        end
    end
    savecontext("running")
    println("Source loaded: ",pathof(TamerOp)); flush(stdout)
    try
        open(correctpath,"w") do co
            open(rawpath,"w") do io
                for (f,d) in zip(fs,data), round in 1:warmup_rounds
                    constructor_reference = nothing
                    for phase in UPHASES
                        row = u_run_phase(f,d,posets,phase,constructor_reference)
                        row.correctness_passed || error(row.failure)
                        phase == "native_construction" && (constructor_reference=row.constructor_prepared)
                        push!(warmups,(case=String(f.case),round,phase,seconds=row.seconds,
                            compile_seconds=row.compile_seconds,recompile_seconds=row.recompile_seconds,
                            correctness_passed=true,reset_verified=row.reset_evidence.verified_empty))
                    end
                    println("Warmed ",f.case," ",round); flush(stdout)
                end
                savecontext("measuring")
                for (f,d) in zip(fs,data), sample in 1:samples
                    constructor_reference = nothing
                    for phase in UPHASES
                        for attempt in 1:max_attempts
                            row = u_run_phase(f,d,posets,phase,constructor_reference;
                                export_io=sample==1 && attempt==1 && phase!="native_construction" ? co : nothing,
                                sample,attempt,pass,run_id)
                            uwrite(io,(;record_type="measurement",tool="TamerOp",run_id,process_id=getpid(),
                                configuration_sha256=config_hash,case=String(f.case),family=String(f.family),
                                field=String(f.field),pass,sample,attempt,phase,regime="warm-uncached",row...))
                            counts[phase] += 1
                            if row.eligible
                                accepted[phase] += 1
                            else
                                contamination[phase] += 1
                            end
                            row.correctness_passed || error(row.failure)
                            phase == "native_construction" && (constructor_reference=row.constructor_prepared)
                            row.eligible && break
                        end
                    end
                    println("Completed ",f.case," ",sample); flush(stdout)
                end
                final_reset = u_reset!(posets)
                expected = length(fs)*samples
                all_eligible = all(==(expected),values(accepted))
                footer = (; tool="TamerOp",phase="complete",run_id,configuration_sha256=config_hash,
                    pass,samples,fixture_count=length(fs),cases=String[String(f.case) for f in fs],phases=collect(UPHASES),
                    timing_rows=sum(values(counts)),per_phase_rows=counts,per_phase_eligible=accepted,
                    per_phase_contaminated=contamination,expected_eligible_per_phase=expected,
                    correctness_passed=true,all_samples_eligible=all_eligible,final_reset_verified=true)
                uwrite(io,footer)
                uwrite(co,(;tool="TamerOp",phase="complete",run_id,pass,fixture_count=length(fs),
                    cases=String[String(f.case) for f in fs],per_phase_exports=Dict(p=>length(fs) for p in UPHASES[2:3]),
                    correctness_rows=length(fs)*2,correctness_passed=true))
            end
        end
        savecontext("complete")
    catch err
        failure = sprint(showerror,err,catch_backtrace())
        savecontext("failed",failure)
        open(rawpath,"a") do io
            uwrite(io,(;tool="TamerOp",phase="failure",run_id,pass,failure,
                per_phase_rows=counts,per_phase_eligible=accepted,correctness_passed=false))
        end
        rethrow()
    end
    println("UNCACHED_COMPLETE ",run_id," rows=",sum(values(counts))," eligible=",sum(values(accepted))); flush(stdout)
end
if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    uncached_main()
end
