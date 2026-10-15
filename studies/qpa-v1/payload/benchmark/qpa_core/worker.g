# Reuse input conversion, fresh categories and bounded execution, not mathematics.
QD_HELPERS_ONLY:=true;;
Read("benchmark/qpa_derived/worker.g");
Read("benchmark/qpa_core/diagrams.g");
QD_Query:=function(f,b,c)
    local m,H,X,coords,k,i,q,r,ds,ts,h,t;
    if f.workflow in ["Q6","Q7"] then return QG_Query(f,b,c);fi;
    m:=b.mods;
    if f.task="hom_basis" then return rec(hom:=HomOverAlgebra(m.M,m.N));
    elif f.task="ext1_dimension" then X:=ExtOverAlgebra(m.M,m.N);return rec(dimension:=Length(X[2]));
    elif f.task="full_hom_ext" then
        H:=HomOverAlgebra(m.M,m.N);X:=QD_Ext(m.M,m.N,f.maxdegree);
        coords:=List(X.groups,g->List(g.data[2],h->QD_Coords(g,h)));
        return rec(hom:=H,ext:=X,coords:=coords);
    elif f.task="kernel_image_cokernel" then
        k:=KernelInclusion(b.maps.f);i:=ImageProjectionInclusion(b.maps.f);q:=CoKernelProjection(b.maps.f);
        return rec(kernel:=Source(k),image:=Range(i[1]),cokernel:=Range(q),ki:=k,ip:=i[1],ii:=i[2],cq:=q);
    elif f.task="projective" or f.task="injective" then
        if f.task="projective" then
            r:=ProjectiveResolution(m.X);ds:=List([0..f.maxdegree],k->DifferentialOfComplex(r,k));ts:=List(ds,Source);
        else
            r:=InjectiveResolution(m.X);ds:=List([0..f.maxdegree],k->DifferentialOfComplex(r,-k));ts:=List(ds,Range);
        fi;
        for t in ts do DimensionVector(t);MatricesOfPathAlgebraModule(t);od;
        for h in ds do MatricesOfPathAlgebraMatModuleHomomorphism(h);od;
        return rec(terms:=ts,diffs:=ds{[2..Length(ds)]},aug:=ds[1],owner:=r);
    fi;
    Error("Unknown core task");
end;;
QD_Export:=function(f,a,c)
    if f.workflow in ["Q6","Q7"] then return QG_Export(f,a,c);fi;
    if f.task="hom_basis" then return rec(hom:=List(a.hom,h->QD_Map(h,c)));
    elif f.task="ext1_dimension" then return rec(dimension:=a.dimension);
    elif f.task="full_hom_ext" then
        return rec(hom:=List(a.hom,h->QD_Map(h,c)),ext:=QD_ExtExport(a.ext,c),
            requested_coordinate_columns:=List(a.coords,vs->List(vs,v->QD_Entries(v,c.K))));
    elif f.task="kernel_image_cokernel" then
        return rec(kernel:=QD_ModuleExport(a.kernel,c),image:=QD_ModuleExport(a.image,c),cokernel:=QD_ModuleExport(a.cokernel,c),
            kernel_inclusion:=QD_Map(a.ki,c),image_inclusion:=QD_Map(a.ii,c),image_projection:=QD_Map(a.ip,c),cokernel_projection:=QD_Map(a.cq,c));
    elif f.task="projective" or f.task="injective" then
        return rec(terms:=List(a.terms,M->QD_ModuleExport(M,c)),differentials:=List(a.diffs,h->QD_Map(h,c)),augmentation:=QD_Map(a.aug,c));
    fi;
    Error("Unknown core export");
end;;
QD_Main();QUIT_GAP(0);
