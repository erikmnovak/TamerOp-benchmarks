# Matched finite-algebra comparison over QQ, F2, F3 and F101.
# Parsing, poset construction, exact oracles and exports stay outside timers.
using TamerOp, JSON3, LinearAlgebra, SHA
@assert realpath(dirname(dirname(pathof(TamerOp)))) == realpath(dirname(Base.active_project()))
const CM = TamerOp.CoreModules
const MD = TamerOp.Modules
const DF = TamerOp.DerivedFunctors
const CC = TamerOp.ChainComplexes
const FL = TamerOp.FieldLinAlg
const FF = TamerOp.FiniteFringe
const OPT = TamerOp.Options
const QQ = Rational{BigInt}
const ROOT = dirname(@__DIR__)
const OUT = joinpath(ROOT, "audit/2026-09-27/qpa_diversity")
const FIXTURES = joinpath(OUT, "fixtures.json")
const PHASES = ("native_construction", "fresh_explicit_bases",
                "first_coordinate_roundtrip", "repeated_coordinate_roundtrip",
                "fresh_explicit_bases_and_coordinates")

function rational_input(s)
    parts = split(replace(String(s), "//" => "/"), '/')
    length(parts) in (1, 2) || error("Invalid rational input: $s")
    parse(BigInt, parts[1]) // (length(parts) == 1 ? big(1) : parse(BigInt, parts[2]))
end
function coefficient_field(label)
    label == "QQ" && return CM.QQField()
    label == "F2" && return CM.F2()
    label == "F3" && return CM.F3()
    label == "F101" && return CM.Fp(101)
    error("Unknown coefficient field: $label")
end
canonical(x::Rational) = denominator(x) == 1 ? string(numerator(x)) : string(numerator(x), '/', denominator(x))
canonical(x::CM.FpElem) = string(x.val)

function decode_module(spec, pospec, P)
    field = coefficient_field(String(spec.field))
    K = CM.coeff_type(field)
    dims = Int.(spec.dimensions)
    length(dims) == P.n || error("Wrong stalk count for $(spec.id)")
    edges = Dict{Tuple{Int,Int}, Matrix{K}}()
    length(pospec.covers) == length(spec.edge_matrices) || error("Wrong edge count")
    for (edge, rows) in zip(pospec.covers, spec.edge_matrices)
        u, v = Int.(edge)
        length(rows) == dims[v] || error("Wrong target dimension")
        A = zeros(K, dims[v], dims[u])
        for i in 1:dims[v]
            length(rows[i]) == dims[u] || error("Wrong source dimension")
            for j in 1:dims[u]
                A[i, j] = CM.coerce(field, rational_input(rows[i][j]))
            end
        end
        edges[(u, v)] = A
    end
    (; P, field, dims, edges)
end
function make_module(d)
    K = CM.coeff_type(d.field)
    MD.PModule{K}(d.P, copy(d.dims), deepcopy(d.edges); field=d.field)
end
make_pair(d) = (M=make_module(d.source), N=make_module(d.target))

function explicit_query(pair, maxdegree)
    maps = DF.basis(DF.Hom(pair.M, pair.N))
    e = DF.Ext(pair.M, pair.N, OPT.DerivedFunctorOptions(maxdeg=maxdegree, model=:projective))
    dims = [DF.dim(e, t) for t in 0:maxdegree]
    reps = [DF.basis(e, t) for t in 1:maxdegree]
    (; maps, e, dims, reps)
end
coordinate_roundtrip(a) = [[DF.coordinates(a.e, t, v) for v in a.reps[t]] for t in eachindex(a.reps)]
function full_query(pair, maxdegree)
    a = explicit_query(pair, maxdegree)
    (; a..., coords=coordinate_roundtrip(a))
end
function columns(vs, ::Type{K}, nrows) where K
    A = zeros(K, nrows, length(vs))
    for (j, v) in enumerate(vs)
        length(v) == nrows || error("Inconsistent vector dimension")
        A[:, j] = v
    end
    A
end
function flatten_map(h, ::Type{K}, nvertices) where K
    answer = K[]
    for v in 1:nvertices
        append!(answer, vec(Matrix(MD.component(h, v))))
    end
    answer
end
function hom_matrix(a, pair)
    K = CM.coeff_type(pair.M.field)
    nrows = sum(pair.M.dims .* pair.N.dims)
    columns([flatten_map(h, K, pair.M.Q.n) for h in a.maps], K, nrows)
end
function verify_roundtrip(a, coords)
    K = eltype(a.e.cohom[1].K)
    for t in eachindex(a.reps)
        dim = a.dims[t + 1]
        @assert length(coords[t]) == dim
        @assert columns(coords[t], K, dim) == Matrix{K}(I, dim, dim)
    end
    true
end
function verify(a, f, pair; coords=nothing)
    field = pair.M.field
    K = CM.coeff_type(field)
    @assert MD.check_module(pair.M).valid && MD.check_module(pair.N).valid
    @assert a.dims == Int.(f.expected_ext)
    @assert length(a.maps) == a.dims[1]
    @assert all(h -> MD.check_morphism(h).valid, a.maps)
    Hmaps = hom_matrix(a, pair)
    expected = [[CM.coerce(field, rational_input(x)) for x in v] for v in f.expected_hom_basis]
    gold = columns(expected, K, size(Hmaps, 1))
    @assert FL.rank(field, Hmaps) == size(Hmaps, 2) == size(gold, 2)
    @assert FL.rank(field, hcat(Hmaps, gold)) == size(gold, 2)
    for t in eachindex(a.reps)
        H = a.e.cohom[t + 1]
        R = columns(a.reps[t], K, H.dimC)
        @assert size(R, 2) == H.dimH
        @assert all(iszero, a.e.complex.d[t + 1] * R)
        @assert CC.coordinates(H, R) == Matrix{K}(I, H.dimH, H.dimH)
        @assert CC.coordinates(H, H.B) == zeros(K, H.dimH, H.dimB)
        # Integer weights avoid accidental noninvertible denominators in Fp.
        w = K[CM.coerce(field, (-1)^j * (2j + 1)) for j in 1:H.dimH]
        z = R * w
        @assert DF.coordinates(a.e, t, z) == w
        @assert DF.representative(a.e, t, w) == z
        if H.dimB > 0
            for j in unique((1, H.dimB))
                @assert DF.coordinates(a.e, t, z + H.B[:, j]) == w
            end
        end
        # A noncycle must remain invalid even if this degree's quotient vanishes.
        D = a.e.complex.d[t + 1]
        noncycle = findfirst(j -> any(!iszero, view(D, :, j)), axes(D, 2))
        if noncycle !== nothing
            bad = zeros(K, H.dimC); bad[noncycle] = one(K)
            rejected = try
                DF.coordinates(a.e, t, bad)
                false
            catch err
                err isa ErrorException || err isa ArgumentError
            end
            @assert rejected
        end
    end
    coords === nothing || verify_roundtrip(a, coords)
    true
end
function measure(fn)
    GC.gc()
    t = @timed fn()
    (; value=t.value, seconds=t.time, bytes=t.bytes, gc_seconds=t.gctime,
       compile_seconds=t.compile_time, recompile_seconds=t.recompile_time)
end
function emit(io, f, sample, phase, timed)
    if io !== nothing
        @assert timed.compile_seconds == 0 && timed.recompile_seconds == 0
        JSON3.write(io, (tool="TamerOp", case=String(f.case), family=String(f.family),
            field=String(f.field), sample, phase, seconds=timed.seconds, bytes=timed.bytes,
            gc_seconds=timed.gc_seconds, compile_seconds=timed.compile_seconds,
            recompile_seconds=timed.recompile_seconds))
        write(io, '\n'); flush(io)
    end
    timed.value
end
function matrix_export(A)
    (; rows=size(A, 1), columns=size(A, 2), values=[[canonical(A[i,j]) for j in axes(A,2)] for i in axes(A,1)])
end
function export_result(io, a, f, pair)
    K = CM.coeff_type(pair.M.field)
    positive = map(eachindex(a.reps)) do t
        H = a.e.cohom[t + 1]
        R = columns(a.reps[t], K, H.dimC)
        (; degree=t, dimH=H.dimH, dimC=H.dimC, dimB=H.dimB,
           representatives=matrix_export(R), outgoing_differential=matrix_export(a.e.complex.d[t + 1]),
           boundaries=matrix_export(H.B), coordinates=matrix_export(CC.coordinates(H,R)))
    end
    JSON3.write(io, (case=String(f.case), family=String(f.family), field=String(f.field),
        source=String(f.source), target=String(f.target), dims=a.dims,
        hom_basis=[canonical.(flatten_map(h,K,pair.M.Q.n)) for h in a.maps],
        hom_coordinate_count=sum(pair.M.dims .* pair.N.dims), ext=positive,
        exact_expected_hom_span=true, naturality=true, cycles=true,
        coordinate_identity=true, mixed_weights=true, boundary_shifts=true,
        invalid_noncycles_rejected=true))
    write(io, '\n'); flush(io)
end
function exercise(f, d, io, sample; export_io=nothing)
    native = emit(io, f, sample, "native_construction", measure(() -> make_pair(d)))
    @assert MD.check_module(native.M).valid && MD.check_module(native.N).valid
    # Construction of fresh pairs is separate from the algebra-only phases.
    pair = make_pair(d)
    a = emit(io, f, sample, "fresh_explicit_bases", measure(() -> explicit_query(pair, Int(f.maxdegree))))
    first = emit(io, f, sample, "first_coordinate_roundtrip", measure(() -> coordinate_roundtrip(a)))
    repeated = emit(io, f, sample, "repeated_coordinate_roundtrip", measure(() -> coordinate_roundtrip(a)))
    verify(a, f, pair; coords=first)
    verify_roundtrip(a, repeated)
    fresh_pair = make_pair(d)
    b = emit(io, f, sample, "fresh_explicit_bases_and_coordinates", measure(() -> full_query(fresh_pair, Int(f.maxdegree))))
    verify(b, f, fresh_pair; coords=b.coords)
    export_io === nothing || export_result(export_io, b, f, fresh_pair)
    nothing
end
function package_hashes(root)
    paths = String[]
    for dir in ("src", "ext")
        for (base, _, files) in walkdir(joinpath(root, dir)), file in files
            endswith(file, ".jl") && push!(paths, relpath(joinpath(base,file), root))
        end
    end
    for file in ("Project.toml", "Manifest.toml", "linalg_thresholds.toml")
        isfile(joinpath(root,file)) && push!(paths, file)
    end
    Dict(p => bytes2hex(sha256(read(joinpath(root,p)))) for p in sort(paths))
end
function main()
    BLAS.set_num_threads(1)
    pass = parse(Int, get(ENV,"DIVERSITY_PASS","1")); pass in (1,2) || error("Invalid pass")
    samples = parse(Int, get(ENV,"DIVERSITY_SAMPLES","3")); samples > 0 || error("Samples must be positive")
    wanted = split(get(ENV,"DIVERSITY_CASES",""), ',')
    spec = JSON3.read(read(FIXTURES,String))
    fs = [f for f in spec.fixtures if wanted == [""] || String(f.case) in wanted]
    isempty(fs) && error("No selected fixtures")
    if wanted != [""]
        @assert Set(String.(wanted)) == Set(String(f.case) for f in fs)
    end
    pass == 2 && reverse!(fs)
    pospecs = Dict(String(p.name) => p for p in spec.posets)
    # Category construction is shared, as is GAP's incidence-algebra construction.
    posets = Dict(String(p.name) => FF.FinitePoset(Bool[p.leq[i][j] != 0 for i in 1:Int(p.n), j in 1:Int(p.n)]) for p in spec.posets)
    modules = Dict(String(m.id) => decode_module(m,pospecs[String(m.poset)],posets[String(m.poset)]) for m in spec.modules)
    data = map(fs) do f
        source, target = modules[String(f.source)], modules[String(f.target)]
        @assert source.P === target.P && source.field == target.field
        @assert String(f.field) == String(only(m.field for m in spec.modules if String(m.id) == String(f.source)))
        (; source, target)
    end
    mkpath(OUT)
    name = "tamerop_pass$(pass)" * get(ENV,"DIVERSITY_SUFFIX","")
    println("Source loaded: ",pathof(TamerOp)); flush(stdout)
    # Exercise exactly the measured callbacks before opening measurement output.
    for (f,d) in zip(fs,data)
        exercise(f,d,nothing,0)
        println("Warmed ",f.case); flush(stdout)
    end
    open(joinpath(OUT,name*"_correctness.jsonl"),"w") do co
        open(joinpath(OUT,name*".jsonl"),"w") do io
            for (f,d) in zip(fs,data), sample in 1:samples
                exercise(f,d,io,sample; export_io=sample==1 ? co : nothing)
                println("Completed ",f.case," ",sample); flush(stdout)
            end
            footer=(tool="TamerOp",phase="complete",pass,samples,fixture_count=length(fs),
                cases=String[String(f.case) for f in fs],phases=collect(PHASES),
                timing_rows=length(fs)*samples*length(PHASES),correctness_passed=true)
            JSON3.write(io,footer); write(io,'\n')
            JSON3.write(co,(tool="TamerOp",phase="complete",fixture_count=length(fs),
                cases=String[String(f.case) for f in fs],correctness_passed=true)); write(co,'\n')
        end
    end
    project_root=dirname(Base.active_project())
    open(joinpath(OUT,name*"_context.json"),"w") do io
        JSON3.pretty(io,(pass,samples,julia=string(VERSION),threads=Threads.nthreads(),
            blas_threads=BLAS.get_num_threads(),source=pathof(TamerOp),
            compiled_modules_flag=Base.JLOptions().use_compiled_modules,
            harness_sha256=bytes2hex(sha256(read(@__FILE__))),fixture_sha256=bytes2hex(sha256(read(FIXTURES))),
            source_hashes=package_hashes(project_root),cases=String[String(f.case) for f in fs],
            phases=collect(PHASES),
            contract="Unequal modules on the identical finite poset over identical exact coefficient fields. Hom natural maps and positive Ext representatives through maxdegree, with checked public coordinates. Complete Hom spans checked against independent fixture oracles; maps, cycles, coordinate identities, noncycles, mixtures and boundary shifts verified exactly. No cross-field basis-identification claim.",
            timing="Native construction includes both M and N. Parsing, field conversion and finite-poset construction excluded. Fresh algebra-only phases use separate newly constructed pairs; first/repeated coordinate phases share the first Ext result. No timed source-module reuse between independent phases, no clearing of library structural caches. Every fixture warms exactly the measured callbacks. GC before every timer; pass2 reverses fixtures. Shared machine.",
            exports="Hom vectors concatenate column-major vertex component matrices in vertex order. QQ entries are reduced numerator/denominator strings; finite-field entries are canonical residue integer strings. Explicit matrix shapes preserve zero-dimensional cases."))
    end
end
if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
