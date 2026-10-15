# Q6-Q7: fresh native input diagrams, followed by supported public operations.
const MC=TamerOp.ModuleComplexes
function qc_construct(f,c)
    b=qd_construct(f,c)
    hasproperty(f,:complexes) || return b
    complexes=Dict(n=>MC.ModuleCochainComplex([b.mods[Symbol(x)] for x in s.terms],
        [b.maps[Symbol(x)] for x in s.differentials];tmin=0,check=true) for (n,s) in pairs(f.complexes))
    chainmap=hasproperty(f,:chainmap) ? MC.ModuleCochainMap(complexes[:C],complexes[:D],
        [b.maps[Symbol(x)] for x in f.chainmap.components];check=true) : nothing
    (;b...,complexes,chainmap)
end
function qg_query(f,b,c)
    if f.task=="pushout"
        U,l,r,_,_=AC.pushout(b.maps[:f],b.maps[:g]);return (;U,l,r)
    elseif f.task=="pullback"
        U,l,r,_,_=AC.pullback(b.maps[:f],b.maps[:g]);return (;U,l,r)
    elseif f.task=="homology"
        return (;homology=[MC.cohomology_module_data(b.complexes[:C],t) for t in 0:2])
    end
    cone=MC.mapping_cone(b.chainmap)
    for h in cone.diffs,v in 1:c.P.n;MD.component(h,v);end
    return (;cone)
end
function qg_export(f,a,c)
    if f.task in ("pushout","pullback")
        return Dict("module"=>qd_module(a.U,c.p),"left"=>qd_map(a.l),"right"=>qd_map(a.r))
    elseif f.task=="homology"
        return (;homology=[Dict("module"=>qd_module(x.H,c.p),"cycles"=>qd_module(x.Z,c.p),
            "inclusion"=>qd_map(x.iZ),"quotient"=>qd_map(x.q)) for x in a.homology])
    end
    (;convention="TamerOp",degrees=collect(-1:2),terms=[qd_module(M,c.p) for M in a.cone.terms],differentials=qd_map.(a.cone.diffs))
end
function qg_track(b,a)
    if hasproperty(b,:complexes)
        for C in values(b.complexes);push!(U_LIFETIMES,WeakRef(C.terms),WeakRef(C.diffs));end
    end
    a===nothing && return
    if hasproperty(a,:U);push!(U_LIFETIMES,WeakRef(a.U.dims));end
    if hasproperty(a,:homology)
        for x in a.homology, M in (x.Z,x.B,x.H);push!(U_LIFETIMES,WeakRef(M.dims));end
    end
    if hasproperty(a,:cone);push!(U_LIFETIMES,WeakRef(a.cone.terms),WeakRef(a.cone.diffs));end
end
