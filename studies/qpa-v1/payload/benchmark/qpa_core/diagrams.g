# Public QPA diagram operations, with n=-t for the cochain input convention.
QG_BaseConstruct:=QD_Construct;;
QD_Construct:=function(f,c)
    local b,n,s,cat;
    b:=QG_BaseConstruct(f,c);
    if not IsBound(f.complexes) then return b;fi;
    cat:=CatOfRightAlgebraModules(c.A);b.complexes:=rec();
    for n in RecNames(f.complexes) do
        s:=f.complexes.(n);
        b.complexes.(n):=FiniteComplex(cat,-1,List(Reversed(s.differentials),x->b.maps.(x)));
    od;
    if IsBound(f.chainmap) then
        b.chainmap:=FiniteChainMap(b.complexes.C,b.complexes.D,-2,List(Reversed(f.chainmap.components),x->b.maps.(x)));
    fi;
    return b;
end;;
QG_Query:=function(f,b,c)
    local x,cone,ts,ds,H,t;
    if f.task="pushout" then
        x:=PushOut(b.maps.f,b.maps.g);return rec(U:=Range(x[1]),left:=x[2],right:=x[1]);
    elif f.task="pullback" then
        x:=PullBack(b.maps.f,b.maps.g);return rec(U:=Source(x[1]),left:=x[2],right:=x[1]);
    elif f.task="homology" then
        H:=List([0..2],t->HomologyOfComplex(b.complexes.C,-t));
        for x in H do DimensionVector(x);MatricesOfPathAlgebraModule(x);od;
        return rec(homology:=H,complex:=b.complexes.C);
    fi;
    cone:=MappingCone(b.chainmap)[1];
    ts:=List([-1..2],t->ObjectOfComplex(cone,-t));ds:=List([-1..1],t->DifferentialOfComplex(cone,-t));
    for x in ts do DimensionVector(x);MatricesOfPathAlgebraModule(x);od;
    for x in ds do MatricesOfPathAlgebraMatModuleHomomorphism(x);od;
    return rec(terms:=ts,diffs:=ds,cone:=cone);
end;;
QG_HomologyWitness:=function(C,t,H,c)
    local i,j,q,got;
    # Validation-only witnesses: repeat QPA's documented kernel/image/cokernel
    # construction, then check the actual module returned by the timed call.
    i:=KernelInclusion(DifferentialOfComplex(C,-t));
    j:=LiftingInclusionMorphisms(i,ImageInclusion(DifferentialOfComplex(C,1-t)));
    q:=CoKernelProjection(j);got:=QD_ModuleExport(Range(q),c);
    if got<>QD_ModuleExport(H,c) then Error("Homology witness uses different native coordinates");fi;
    return rec(module:=QD_ModuleExport(H,c),cycles:=QD_ModuleExport(Source(i),c),inclusion:=QD_Map(i,c),quotient:=QD_Map(q,c));
end;;
QG_Export:=function(f,a,c)
    if f.task="pushout" or f.task="pullback" then
        return rec(module:=QD_ModuleExport(a.U,c),left:=QD_Map(a.left,c),right:=QD_Map(a.right,c));
    elif f.task="homology" then
        return rec(homology:=List([0..2],t->QG_HomologyWitness(a.complex,t,a.homology[t+1],c)));
    fi;
    return rec(convention:="QPA",degrees:=[-1..2],terms:=List(a.terms,x->QD_ModuleExport(x,c)),differentials:=List(a.diffs,x->QD_Map(x,c)));
end;;
