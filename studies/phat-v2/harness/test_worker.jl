using Test, JSON3, SparseArrays
module Adapter end
const path = joinpath(@__DIR__, "worker.jl")
const source = read(path, String)
@assert endswith(source, "main()\n")
Base.include_string(Adapter, source[1:end-length("main()\n")], path)
@testset "PHAT adapter fresh-state verification" begin
    f=Adapter.Fixture([0,0,1],[0,0,1],[Int[],Int[],[1,2]])
    @test Adapter.pristine(Adapter.construct(f),f)
    for corrupt! in (g->(g.grades[1]=(4,)), g->(g.cell_ids[1]=99),
                     g->(g.dim_offsets[2]+=1), g->push!(g.dim_offsets,4),
                     g->pop!(g.boundaries), g->(g.boundaries[1].nzval[1]=0),
                     g->(g.boundaries[1].rowval[1]=0),
                     g->(g.boundaries[1].colptr[end]-=1),
                     g->push!(g.boundaries[1].rowval,1))
        g=Adapter.construct(f);corrupt!(g)
        @test !Adapter.pristine(g,f)
    end
    for fixture in (Adapter.Fixture(Int[],Int[],Vector{Int}[]),
                    Adapter.Fixture([0],[2],[Int[]]),
                    Adapter.Fixture([0,2],[0,1],[Int[],Int[]]))
        g=Adapter.construct(fixture)
        @test Adapter.pristine(g,fixture)
        a,route=Adapter.query_with_backend(g,fixture)
        @test a==Adapter.query(g,fixture)
        @test route in (:f2_graph_union_find,:f2_clearing)
        @test Adapter.pristine(g,fixture)
    end
end
