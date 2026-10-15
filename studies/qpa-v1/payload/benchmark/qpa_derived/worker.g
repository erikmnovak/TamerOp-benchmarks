# Q8-Q10: supported, unmodified QPA operations; the launcher supplies configuration.
if LoadPackage("qpa")<>true then Error("QPA unavailable");fi;
QD_OUT:=fail;;
DV_Field:=function(name) if name="QQ" then return Rationals;fi;return GF(Int(name{[2..Length(name)]}));end;;
DV_Scalar:=function(x,K) return NumeratorRat(x)*One(K)/(DenominatorRat(x)*One(K));end;;
DV_Canonical:=function(x,K) if K=Rationals then return String(x);fi;return String(IntFFE(x));end;;
DV_Path:=function(KQ,p,path) local a,r;r:=One(KQ);for a in path do r:=r*KQ.(p.arrows[a][3]);od;return r;end;;
Read(QD_INPUT);
AlwaysPrintTracebackOnError:=true;;
QD_JSON:=function(out,x)
    local names,i,n,d;
    if x=fail then PrintTo(out,"null");
    elif IsRecord(x) then
        names:=Set(RecNames(x));PrintTo(out,"{");
        for i in [1..Length(names)] do
            if i>1 then PrintTo(out,",");fi;
            QD_JSON(out,names[i]);PrintTo(out,":");QD_JSON(out,x.(names[i]));
        od;PrintTo(out,"}");
    elif IsList(x) and Length(x)=0 then PrintTo(out,"[]");
    elif IsString(x) then PrintTo(out,"\"",ReplacedString(ReplacedString(ReplacedString(x,"\\","\\\\"),"\"","\\\""),"\n","\\n"),"\"");
    elif IsList(x) then
        PrintTo(out,"[");for i in [1..Length(x)] do
            if i>1 then PrintTo(out,",");fi;QD_JSON(out,x[i]);od;PrintTo(out,"]");
    elif IsInt(x) or IsBool(x) then PrintTo(out,String(x));
    else Error("Unsupported JSON type");fi;
end;;
QD_Write:=function(x) QD_JSON(QD_OUT,x);PrintTo(QD_OUT,"\n");end;;
QD_Scalar:=function(x,K) return DV_Scalar(Rat(x),K);end;;
QD_Has:=function(x,name)
    local n;n:=Concatenation("Has",name);
    return IsBoundGlobal(n) and ValueGlobal(n)(x);
end;;
QD_Attrs:=["ProjectiveCover","1stSyzygy","ProjectiveResolution","TopOfModule", "TopOfModuleProjection",
    "MinimalGeneratingSetOfModule","EndOverAlgebra","InjectiveEnvelope","DualOfModule"];;
QD_AlgebraAttrs:=["IndecProjectiveModules","BasisOfProjectives","ZeroModule","SimpleModules","IndecInjectiveModules"];;
QD_Fresh:=function(mods)
    return List(Set(RecNames(mods)),n->rec(name:=n,known:=Set(KnownAttributesOfObject(mods.(n))),
        mathematical_attributes:=Filtered(QD_Attrs,k->QD_Has(mods.(n),k))));
end;;
QD_Prepare:=function(f)
    local p,K,Q,KQ,rels,A,Aop,cat,n,m,mods,maps;
    p:=StructuralCopy(First(QD_SPEC.posets,p->p.name=f.poset));K:=DV_Field(f.field);
    p.arrows:=List([1..Length(p.covers)],e->[p.covers[e][1],p.covers[e][2],Concatenation("e",String(e))]);
    Q:=Quiver(p.n,p.arrows);KQ:=PathAlgebra(K,Q);
    rels:=List(p.relations,r->DV_Path(KQ,p,r[1])-DV_Path(KQ,p,r[2]));
    if Length(rels)=0 then A:=KQ;else A:=KQ/rels;fi;
    if Dimension(A)<>p.algebra_dim then Error("Incidence algebra dimension");fi;
    Aop:=fail;
    if f.task="tensor" then Aop:=OppositeAlgebra(A);Dimension(Aop);fi;
    mods:=rec();maps:=rec();
    for n in RecNames(f.modules) do
        m:=f.modules.(n);
        mods.(n):=rec(dimensions:=m.dimensions,
            edge_matrices:=List(m.edge_matrices,A->List(A,row->List(row,x->QD_Scalar(x,K)))));
    od;
    for n in RecNames(f.maps) do
        m:=f.maps.(n);
        maps.(n):=rec(source:=m.source,target:=m.target,
            components:=List(m.components,A->List(A,row->List(row,x->QD_Scalar(x,K)))));
    od;
    cat:=rec(p:=p,K:=K,A:=A,Aop:=Aop,modules:=mods,maps:=maps);
    if ForAny(QD_AlgebraAttrs,k->QD_Has(A,k)) then Error("Category contains previous query mathematics");fi;
    if Aop<>fail and ForAny(QD_AlgebraAttrs,k->QD_Has(Aop,k)) then Error("Opposite category contains query mathematics");fi;
    return cat;
end;;
QD_Module:=function(m,c,op)
    local A,arrows,gens,e,u,v,mat,rows;
    if op then A:=c.Aop;else A:=c.A;fi;
    arrows:=ArrowsOfQuiver(QuiverOfPathAlgebra(A));gens:=[];
    # Quiver and OppositeQuiver preserve the supplied arrow enumeration; native input checks below certify it.
    for e in [1..Length(c.p.covers)] do
        u:=c.p.covers[e][1];v:=c.p.covers[e][2];
        if op then mat:=u;u:=v;v:=mat;fi;
        if m.dimensions[u]>0 and m.dimensions[v]>0 then
            mat:=m.edge_matrices[e];
            rows:=List([1..m.dimensions[u]],j->List([1..m.dimensions[v]],i->mat[i][j]));
            # Use each native arrow name, including the opposite-quiver suffix.
            Add(gens,[String(arrows[e]),rows]);
        fi;
    od;
    return RightModuleOverPathAlgebra(A,List(m.dimensions,x->x),gens);
end;;
QD_Construct:=function(f,c)
    local mods,maps,n,s,t,rows,v;
    mods:=rec();maps:=rec();
    for n in Set(RecNames(f.modules)) do mods.(n):=QD_Module(c.modules.(n),c,n="R");od;
    for n in Set(RecNames(f.maps)) do
        s:=c.maps.(n);rows:=[];
        for v in [1..c.p.n] do
            if DimensionVector(mods.(s.source))[v]=0 or DimensionVector(mods.(s.target))[v]=0 then
                Add(rows,NullMat(Maximum(1,DimensionVector(mods.(s.source))[v]),Maximum(1,DimensionVector(mods.(s.target))[v]),c.K));
            else
                Add(rows,List([1..DimensionVector(mods.(s.source))[v]],j->
                    List([1..DimensionVector(mods.(s.target))[v]],i->s.components[v][i][j])));
            fi;
        od;
        maps.(n):=RightModuleHomOverAlgebra(mods.(s.source),mods.(s.target),rows);
        if maps.(n)=fail then Error("Invalid supplied map");fi;
    od;
    return rec(mods:=mods,maps:=maps);
end;;
QD_CheckInputs:=function(f,b,c)
    local name,spec,M,mm,e,u,v,i,j,op,arrows,got;
    for name in RecNames(f.modules) do
        spec:=f.modules.(name);M:=b.mods.(name);mm:=MatricesOfPathAlgebraModule(M);
        if DimensionVector(M)<>spec.dimensions then Error("Native input dimensions differ");fi;
        for e in [1..Length(c.p.covers)] do
            u:=c.p.covers[e][1];v:=c.p.covers[e][2];
            if name="R" then i:=u;u:=v;v:=i;fi;
            for j in [1..spec.dimensions[u]] do for i in [1..spec.dimensions[v]] do
                if mm[e][j][i]<>QD_Scalar(spec.edge_matrices[e][i][j],c.K) then Error("Native input arrow differs");fi;
            od;od;
        od;
    od;
    return true;
end;;
QD_Ext:=function(M,N,d)
    local cur,groups,t,e,cover;
    cur:=M;groups:=[];
    for t in [1..d] do
        e:=ExtOverAlgebra(cur,N);cover:=ProjectiveCover(cur);
        Add(groups,rec(data:=e,cover:=cover,syzygy:=Source(e[1])));cur:=Source(e[1]);
    od;
    return rec(M:=M,N:=N,groups:=groups);
end;;
QD_Coords:=function(e,h)
    if Length(e.data[2])=0 then return [];fi;
    return e.data[3](h);
end;;
QD_Query:=function(f,b,c)
    local m,E,A,B,T,prod,alpha,beta,cover,lift,ind,first,second,ft,k,s,t,eo,et,
          V,ev,r,l,j,i,images,BR,BL,offR,offL;
    m:=b.mods;E:=rec();
    if f.task="yoneda" then
        E.LM:=QD_Ext(m.L,m.M,1);E.MN:=QD_Ext(m.M,m.N,1);E.LN:=QD_Ext(m.L,m.N,2);
        A:=E.LM.groups[1];B:=E.MN.groups[1];T:=E.LN.groups[2];prod:=[];
        cover:=ProjectiveCover(A.syzygy);
        for alpha in A.data[2] do
            lift:=LiftingMorphismFromProjective(B.cover,cover*alpha);
            ind:=MorphismOnKernel(cover,B.cover,lift,alpha);
            Add(prod,List(B.data[2],beta->QD_Coords(T,ind*beta)));
        od;
        return rec(ext:=E,products:=prod);
    elif f.task="induced" then
        E.LN:=QD_Ext(m.L,m.N,2);E.LpN:=QD_Ext(m.Lp,m.N,2);E.LNp:=QD_Ext(m.L,m.Np,2);
        first:=[];second:=[];ft:=b.maps.f;
        for k in [1,2] do
            s:=E.LpN.groups[k].cover;t:=E.LN.groups[k].cover;
            lift:=LiftingMorphismFromProjective(t,s*ft);
            ft:=MorphismOnKernel(s,t,lift,ft);
            Add(first,List(E.LN.groups[k].data[2],h->QD_Coords(E.LpN.groups[k],ft*h)));
            Add(second,List(E.LN.groups[k].data[2],h->QD_Coords(E.LNp.groups[k],h*b.maps.g)));
        od;
        return rec(ext:=E,first_columns:=first,second_columns:=second);
    elif f.task="tensor" then
        T:=TensorProductOfModules(m.L,m.R);V:=T[1];ev:=T[2];
        BR:=BasisVectors(Basis(m.R));BL:=BasisVectors(Basis(m.L));
        images:=[];offR:=0;offL:=0;
        for k in [1..c.p.n] do
            for j in [1..DimensionVector(m.R)[k]] do
                for i in [1..DimensionVector(m.L)[k]] do
                    Add(images,Coefficients(Basis(V),ev(BL[offL+i],BR[offR+j])));
                od;
            od;
            offR:=offR+DimensionVector(m.R)[k];offL:=offL+DimensionVector(m.L)[k];
        od;
        return rec(dimension:=Dimension(V),elementary_columns:=images);
    fi;
    Error("Unknown task");
end;;
QD_Entries:=function(xs,K)
    return List(xs,x->DV_Canonical(x,K));
end;;
QD_Map:=function(h,c)
    local ds,dt,m;
    ds:=DimensionVector(Source(h));dt:=DimensionVector(Range(h));m:=MatricesOfPathAlgebraMatModuleHomomorphism(h);
    return List([1..c.p.n],v->List([1..dt[v]],i->QD_Entries(List([1..ds[v]],j->m[v][j][i]),c.K)));
end;;
QD_ModuleExport:=function(M,c)
    local d,mm;
    d:=DimensionVector(M);mm:=MatricesOfPathAlgebraModule(M);
    return rec(dimensions:=d,edge_matrices:=List([1..Length(c.p.covers)],e->
        List([1..d[c.p.covers[e][2]]],i->QD_Entries(List([1..d[c.p.covers[e][1]]],j->mm[e][j][i]),c.K))));
end;;
QD_ExtExport:=function(E,c)
    local covers,terms,diffs,k,cochains,cc,pi,syzygy,next,coords;
    covers:=List(E.groups,g->g.cover);
    Add(covers,ProjectiveCover(E.groups[Length(E.groups)].syzygy));
    terms:=List(covers,p->QD_ModuleExport(Source(p),c));diffs:=[];cochains:=[];coords:=[];
    for k in [1..Length(E.groups)] do
        Add(diffs,QD_Map(covers[k+1]*E.groups[k].data[1],c));
        Add(cochains,List(E.groups[k].data[2],h->QD_Map(covers[k+1]*h,c)));
        Add(coords,List(E.groups[k].data[2],h->QD_Entries(QD_Coords(E.groups[k],h),c.K)));
    od;
    return rec(terms:=terms,differentials:=diffs,augmentation:=QD_Map(covers[1],c),
        cochains:=cochains,coordinate_columns:=coords,dimensions:=List(E.groups,g->Length(g.data[2])));
end;;
QD_Export:=function(f,a,c)
    local out,n;
    if f.task="tensor" then
        return rec(dimension:=a.dimension,elementary_columns:=List(a.elementary_columns,v->QD_Entries(v,c.K)));
    fi;
    out:=rec(ext:=rec());
    for n in RecNames(a.ext) do out.ext.(n):=QD_ExtExport(a.ext.(n),c);od;
    if f.task="yoneda" then out.products:=List(a.products,vs->List(vs,v->QD_Entries(v,c.K)));
    else
        out.first_columns:=List(a.first_columns,vs->List(vs,v->QD_Entries(v,c.K)));
        out.second_columns:=List(a.second_columns,vs->List(vs,v->QD_Entries(v,c.K)));
    fi;
    return out;
end;;
QD_Run:=function(f,phase,sample,warm)
    local c,b,a,t,mem,ns,allocated,pre,export;
    # A new category prevents retained standard projectives, duals, syzygies,
    # opposite algebras or tensor results from a previous task being reachable.
    c:=QD_Prepare(f);b:=fail;a:=fail;pre:=[];
    if phase="complete_query" then b:=QD_Construct(f,c);pre:=QD_Fresh(b.mods);fi;
    GASMAN("collect");
    QD_Write(rec(kind:="timer_start",case:=f.id,phase:=phase,warmup:=warm));
    mem:=TotalMemoryAllocated();t:=NanosecondsSinceEpoch();
    if phase<>"complete_query" then b:=QD_Construct(f,c);fi;
    if phase<>"native_construction" then a:=QD_Query(f,b,c);fi;
    ns:=NanosecondsSinceEpoch()-t;allocated:=TotalMemoryAllocated()-mem;
    if ns<0 then Error("Benchmark clock returned a negative duration");fi;
    QD_Write(rec(kind:="timer_end",case:=f.id,phase:=phase,warmup:=warm));
    if phase="native_construction" then pre:=QD_Fresh(b.mods);fi;
    if ForAny(pre,s->Length(s.mathematical_attributes)>0) then Error("Constructor retained query mathematics");fi;
    QD_CheckInputs(f,b,c);
    export:=fail;if a<>fail then export:=QD_Export(f,a,c);fi;
    QD_Write(rec(kind:="timing",tool:="QPA",case:=f.id,task:=f.task,field:=f.field,
        phase:=phase,sample:=sample,pass:=QD_PASS,warmup:=warm,nanoseconds:=ns,bytes:=allocated,
        compile_seconds:=fail,recompile_seconds:=fail,
        eligible:=not warm and ns<=60000000000,reset_verified:=true,
        reset:=rec(category:="new incidence category per task; only defining algebra preparation excluded",
            prior_inputs_results_retained:=0,constructor_state:=pre),answer:=export));
end;;
QD_Attempt:=function(f,phase,sample,warm)
    local status;
    status:=CALL_WITH_CATCH(function() QD_Run(f,phase,sample,warm);return true;end,[]);
    if not status[1] then
        QD_Write(rec(kind:="failure",tool:="QPA",case:=f.id,task:=f.task,field:=f.field,
            phase:=phase,sample:=sample,pass:=QD_PASS,warmup:=warm,eligible:=false,
            failure:="QPA operation raised an error; exact traceback retained in worker log"));
    fi;
end;;
if not IsBound(QD_CORRECTNESS) then QD_CORRECTNESS:=false;;fi;
QD_Correctness:=function(f)
    local status;
    status:=CALL_WITH_CATCH(function()
        local c,b,a;
        c:=QD_Prepare(f);b:=QD_Construct(f,c);QD_CheckInputs(f,b,c);
        a:=QD_Query(f,b,c);
        QD_Write(rec(kind:="correctness",tool:="QPA",case:=f.id,task:=f.task,field:=f.field,
            reset_verified:=true,answer:=QD_Export(f,a,c)));
        return true;
    end,[]);
    if not status[1] then
        QD_Write(rec(kind:="failure",tool:="QPA",case:=f.id,task:=f.task,field:=f.field,
            phase:="correctness",eligible:=false,
            failure:="QPA operation raised an error; exact traceback retained in worker log"));
    fi;
end;;
QD_Main:=function()
    local fs,f,k,phase,regime,clock;
    clock:=NanosecondsSinceEpochInfo();
    if not QD_CORRECTNESS and (not clock.Monotonic or not clock.Reliable or clock.Resolution<=0) then
        Error("Timing requires a verified monotonic GAP clock; see the QPA clock preflight");
    fi;
    if IsExistingFile(QD_OUTPUT) then Error("Refusing to overwrite evidence");fi;
    QD_OUT:=OutputTextFile(QD_OUTPUT,false);SetPrintFormattingStatus(QD_OUT,false);
    fs:=Filtered(QD_SPEC.cases,f->f.field=QD_FIELD and (Length(QD_CASES)=0 or f.id in QD_CASES));
    if Length(fs)=0 then Error("No cases selected");fi;
    if QD_PASS mod 2=0 then fs:=Reversed(fs);fi;
    regime:="warm-uncached";if QD_CORRECTNESS then regime:="correctness-only";fi;
    QD_Write(rec(kind:="metadata",tool:="QPA",gap:=GAPInfo.Version,qpa:=PackageInfo("qpa")[1].Version,
        field:=QD_FIELD,cases:=List(fs,f->f.id),regime:=regime,samples:=QD_SAMPLES,
        clock:=clock,duration_metric:="elapsed",clock_units:="nanoseconds"));
    for f in fs do
        if QD_CORRECTNESS then QD_Correctness(f);Print("Checked ",f.id,"\n");continue;fi;
        QD_Attempt(f,"construction_and_query",0,true);
        for k in [1..QD_SAMPLES] do
            for phase in QD_SPEC.phases do QD_Attempt(f,phase,k,false);od;
        od;
        Print("Completed ",f.id,"\n");
    od;
    QD_Write(rec(kind:="completed",cases:=List(fs,f->f.id)));CloseStream(QD_OUT);
end;;
if not IsBound(QD_HELPERS_ONLY) or not QD_HELPERS_ONLY then QD_Main();QUIT_GAP(0);fi;
