#!/usr/bin/env python3
"""Bounded exact fixtures and an independent normalized-bar Ext oracle.

No TamerOp/GAP/SymPy dependency. Scalars are Fraction over QQ and integer residues
in Fp. Matrices are row lists; an empty row list requires explicit ncols where
its otherwise-unrecoverable width matters. Nullspace returns a list of columns.
Importing this module performs no generation or file writes.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

FIELDS = ("QQ", "F2", "F3", "F101")


def field_prime(field):
    return None if field == "QQ" else int(field.removeprefix("F"))


def parse_scalar(value, field):
    """Parse an integer/rational string (or Fraction) in the named field."""
    q = Fraction(str(value).replace("//", "/"))
    p = field_prime(field)
    if p is None:
        return q
    if q.denominator % p == 0:
        raise ValueError(f"denominator is not invertible in {field}: {value}")
    return q.numerator * pow(q.denominator % p, -1, p) % p


def scalar_string(value):
    q = Fraction(value)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def matrix_strings(A):
    return [[scalar_string(x) for x in row] for row in A]


def normalize(value, field):
    p = field_prime(field)
    return Fraction(value) if p is None else value % p


def zeros(m, n, field="QQ"):
    z = parse_scalar(0, field)
    return [[z for _ in range(n)] for _ in range(m)]


def identity(n, field="QQ"):
    A = zeros(n, n, field)
    for i in range(n):
        A[i][i] = parse_scalar(1, field)
    return A


def transpose(A, ncols=None):
    n = len(A[0]) if A else (ncols or 0)
    return [[A[i][j] for i in range(len(A))] for j in range(n)]


def matmul(A, B, field, ncols=None):
    """Row-list multiplication; ncols supplies B's width if B has zero rows."""
    k = len(B)
    n = len(B[0]) if B else (ncols or 0)
    assert all(len(row) == k for row in A)
    assert all(len(row) == n for row in B)
    C = zeros(len(A), n, field)
    for i, row in enumerate(A):
        for t, a in enumerate(row):
            if a:
                for j, b in enumerate(B[t]):
                    if b:
                        C[i][j] = normalize(C[i][j] + a * b, field)
    return C


def rref(matrix, field, ncols=None):
    """Return (copied reduced matrix, zero-based pivot columns), exact in field."""
    n = len(matrix[0]) if matrix else (ncols or 0)
    A = [[parse_scalar(x, field) for x in row] for row in matrix]
    assert all(len(row) == n for row in A)
    pivots = []
    r = 0
    p = field_prime(field)
    for c in range(n):
        i = next((i for i in range(r, len(A)) if A[i][c]), None)
        if i is None:
            continue
        A[r], A[i] = A[i], A[r]
        inv = 1 / A[r][c] if p is None else pow(A[r][c], -1, p)
        A[r] = [normalize(x * inv, field) for x in A[r]]
        for i in range(len(A)):
            if i != r and A[i][c]:
                a = A[i][c]
                A[i] = [normalize(x - a * y, field) for x, y in zip(A[i], A[r])]
        pivots.append(c)
        r += 1
        if r == len(A):
            break
    return A, pivots


def rank(matrix, field, ncols=None):
    return len(rref(matrix, field, ncols=ncols)[1])


def nullspace(matrix, field, ncols=None):
    """Return basis vectors as columns, each a length-ncols Python list."""
    n = len(matrix[0]) if matrix else (ncols or 0)
    R, pivots = rref(matrix, field, ncols=n)
    columns = []
    for j in range(n):
        if j in pivots:
            continue
        v = [parse_scalar(0, field) for _ in range(n)]
        v[j] = parse_scalar(1, field)
        for i, c in enumerate(pivots):
            v[c] = normalize(-R[i][j], field)
        columns.append(v)
    return columns


def inverse(A, field):
    n = len(A)
    R, pivots = rref([a + b for a, b in zip(A, identity(n, field))], field)
    assert pivots[:n] == list(range(n))
    assert [row[:n] for row in R] == identity(n, field)
    return [row[n:] for row in R]


def poset(name, n, covers, relations=()):
    leq = [[int(i == j) for j in range(n)] for i in range(n)]
    for u, v in covers:
        assert u < v, "These fixtures use a topological vertex numbering."
        leq[u - 1][v - 1] = 1
    for k in range(n):
        for i in range(n):
            for j in range(n):
                leq[i][j] |= leq[i][k] & leq[k][j]
    return {"name": name, "n": n, "covers": covers, "leq": leq,
            "relations": list(relations), "algebra_dim": sum(map(sum, leq))}


POSETS = [
    poset("chain4", 4, [[1, 2], [2, 3], [3, 4]]),
    poset("diamond", 4, [[1, 2], [1, 3], [2, 4], [3, 4]], [[[1, 3], [2, 4]]]),
    poset("fork3", 4, [[1, 4], [2, 4], [3, 4]]),
]


def module_data(P, dimensions, edge_matrices):
    return {"poset": P["name"], "dimensions": dimensions,
            "edge_matrices": matrix_strings_3d(edge_matrices)}


def matrix_strings_3d(matrices):
    return [matrix_strings(A) for A in matrices]


def supported(P, vertices):
    dims = [int(i + 1 in vertices) for i in range(P["n"])]
    edges = []
    for u, v in P["covers"]:
        edges.append([[1]] if dims[u - 1] and dims[v - 1]
                     else zeros(dims[v - 1], dims[u - 1]))
    return module_data(P, dims, edges)


def simple(P, v):
    return supported(P, {v})


def projective(P, v):
    return supported(P, {i + 1 for i in range(P["n"]) if P["leq"][v - 1][i]})


def injective(P, v):
    return supported(P, {i + 1 for i in range(P["n"]) if P["leq"][i][v - 1]})


def direct_sum(P, modules):
    dims = [sum(M["dimensions"][i] for M in modules) for i in range(P["n"])]
    edges = []
    for e, (u, v) in enumerate(P["covers"]):
        A = zeros(dims[v - 1], dims[u - 1])
        r = c = 0
        for M in modules:
            for i, row in enumerate(M["edge_matrices"][e]):
                for j, x in enumerate(row):
                    A[r + i][c + j] = Fraction(x)
            r += M["dimensions"][v - 1]
            c += M["dimensions"][u - 1]
        edges.append(A)
    return module_data(P, dims, edges)


def parsed_edges(M, field):
    return [[[parse_scalar(x, field) for x in row] for row in A]
            for A in M["edge_matrices"]]


def all_maps(P, M, field):
    """Compose cover maps, checking every possible first-edge route agrees."""
    dims = M["dimensions"]
    edges = parsed_edges(M, field)
    assert len(edges) == len(P["covers"])
    outgoing = {u: [] for u in range(P["n"])}
    maps = {(u, u): identity(dims[u], field) for u in range(P["n"])}
    for (u, v), A in zip(P["covers"], edges):
        u -= 1
        v -= 1
        assert len(A) == dims[v] and all(len(row) == dims[u] for row in A)
        outgoing[u].append((v, A))
    for u in reversed(range(P["n"])):
        for v in range(u + 1, P["n"]):
            if not P["leq"][u][v]:
                continue
            candidates = [matmul(maps[w, v], A, field, ncols=dims[u])
                          for w, A in outgoing[u] if P["leq"][w][v]]
            assert candidates and all(A == candidates[0] for A in candidates)
            maps[u, v] = candidates[0]
    for x in range(P["n"]):
        for y in range(P["n"]):
            for z in range(P["n"]):
                if P["leq"][x][y] and P["leq"][y][z]:
                    assert matmul(maps[y, z], maps[x, y], field, ncols=dims[x]) == maps[x, z]
    return maps


def hom_equations(P, M, N, field=None):
    """Return (cover naturality equation rows, number of unknowns).

    Unknowns flatten each vertex map N_v x M_v column-major, then by vertex.
    This is a direct cover-equation implementation, separate from bar_cochains.
    """
    field = field or M["field"]
    md, nd = M["dimensions"], N["dimensions"]
    me, ne = parsed_edges(M, field), parsed_edges(N, field)
    offsets = []
    nvars = 0
    for a, b in zip(md, nd):
        offsets.append(nvars)
        nvars += a * b
    equations = []
    for e, (u, v) in enumerate(P["covers"]):
        u -= 1
        v -= 1
        for j in range(md[u]):
            for i in range(nd[v]):
                row = [parse_scalar(0, field) for _ in range(nvars)]
                for a in range(md[v]):
                    row[offsets[v] + i + nd[v] * a] += me[e][a][j]
                for b in range(nd[u]):
                    row[offsets[u] + b + nd[u] * j] -= ne[e][i][b]
                equations.append([normalize(x, field) for x in row])
    return equations, nvars


def strict_chains(P, degree):
    chains = [(i,) for i in range(P["n"])]
    for _ in range(degree):
        chains = [chain + (j,) for chain in chains
                  for j in range(chain[-1] + 1, P["n"])
                  if P["leq"][chain[-1]][j]]
    return chains


def bar_cochains(P, M, N, maxdegree, field=None):
    """Build normalized category-bar cochains, independently of resolutions.

    d f(x0,...,x(n+1)) = f(x1,...,x(n+1))*M01
        + sum_i (-1)^i f(chain without xi)
        + (-1)^(n+1) N(n,n+1)*f(x0,...,xn).
    Returns (cochain_dimensions through maxdegree+1, d0...d_maxdegree).
    """
    field = field or M["field"]
    md, nd = M["dimensions"], N["dimensions"]
    mm, nm = all_maps(P, M, field), all_maps(P, N, field)
    levels = [strict_chains(P, n) for n in range(maxdegree + 2)]
    offsets, sizes = [], []
    for chains in levels:
        off, size = {}, 0
        for chain in chains:
            off[chain] = size
            size += md[chain[0]] * nd[chain[-1]]
        offsets.append(off)
        sizes.append(size)
    differentials = []
    for n in range(maxdegree + 1):
        D = zeros(sizes[n + 1], sizes[n], field)
        for chain in levels[n + 1]:
            x, y = chain[0], chain[-1]
            dst = offsets[n + 1][chain]
            src_first = offsets[n][chain[1:]]
            src_last = offsets[n][chain[:-1]]
            for j in range(md[x]):
                for i in range(nd[y]):
                    r = dst + i + nd[y] * j
                    for a in range(md[chain[1]]):
                        D[r][src_first + i + nd[y] * a] += mm[x, chain[1]][a][j]
                    for omit in range(1, n + 1):
                        src = offsets[n][chain[:omit] + chain[omit + 1:]]
                        D[r][src + i + nd[y] * j] += (-1) ** omit
                    for b in range(nd[chain[-2]]):
                        D[r][src_last + b + nd[chain[-2]] * j] += ((-1) ** (n + 1)) * nm[chain[-2], y][i][b]
        differentials.append([[normalize(x, field) for x in row] for row in D])
    return sizes, differentials


def bar_oracle(P, M, N, maxdegree, field=None):
    field = field or M["field"]
    sizes, differentials = bar_cochains(P, M, N, maxdegree, field)
    ranks = [rank(D, field, ncols=sizes[n]) for n, D in enumerate(differentials)]
    for n in range(len(differentials) - 1):
        product = matmul(differentials[n + 1], differentials[n], field, ncols=sizes[n])
        assert all(not x for row in product for x in row), f"bar d² != 0 in degree{n}"
    expected = [sizes[n] - ranks[n] - (ranks[n - 1] if n else 0)
                for n in range(maxdegree + 1)]
    equations, nvars = hom_equations(P, M, N, field)
    hom = nullspace(equations, field, ncols=nvars)
    assert len(hom) == expected[0]
    for v in hom:
        assert all(not normalize(sum(a * b for a, b in zip(row, v)), field)
                   for row in differentials[0])
    return expected, hom, {"bar_cochain_dimensions": sizes,
                           "differential_ranks": ranks,
                           "d_squared_zero": True,
                           "cover_hom_equation_rank": rank(equations, field, ncols=nvars),
                           "hom_coordinate_count": nvars}


def gauge_module(P, M, gauges, field):
    """Keep rational input entries, certify exact inverses in QQ and actual field."""
    rational_gauges = [[[Fraction(x) for x in row] for row in G] for G in gauges]
    inverses = [inverse(G, "QQ") for G in rational_gauges]
    edges = []
    for (u, v), A in zip(P["covers"], M["edge_matrices"]):
        raw = [[Fraction(x) for x in row] for row in A]
        edges.append(matmul(matmul(rational_gauges[v - 1], raw, "QQ", ncols=M["dimensions"][u - 1]),
                            inverses[u - 1], "QQ", ncols=M["dimensions"][u - 1]))
    result = module_data(P, M["dimensions"][:], edges)
    for d, G, H in zip(M["dimensions"], rational_gauges, inverses):
        Gf = [[parse_scalar(x, field) for x in row] for row in G]
        Hf = [[parse_scalar(x, field) for x in row] for row in H]
        assert matmul(Gf, Hf, field, ncols=d) == identity(d, field)
        assert matmul(Hf, Gf, field, ncols=d) == identity(d, field)
    all_maps(P, result, field)
    result["gauge_certificate"] = {"base_dimensions": M["dimensions"],
                                   "base_edge_matrices": M["edge_matrices"],
                                   "gauges": matrix_strings_3d(rational_gauges),
                                   "inverse_gauges": matrix_strings_3d(inverses),
                                   "exact_inverse_verified": True,
                                   "field": field}
    return result


def small_gauges(dimensions):
    # U(1/7)L(2/7), determinant one; seven is invertible in every study field.
    return [[[Fraction(51, 49), Fraction(1, 7)], [Fraction(2, 7), 1]] if d == 2
            else identity(d) for d in dimensions]


def coefficient_bits(modules):
    values = [Fraction(x) for M in modules for A in M["edge_matrices"] for row in A for x in row]
    return {"max_numerator_bits": max((abs(q.numerator).bit_length() for q in values), default=0),
            "max_denominator_bits": max((q.denominator.bit_length() for q in values), default=0)}


def presentation_certificate(P, module, field, codomain_vertices, relation):
    """Certify a projective presentation supported only at the terminal vertex.

    module is the ungauged quotient; relation columns define P4-summand maps.
    The quotient maps use the module's leaf edge columns, which is legitimate
    here because codomain projectives have distinct minimal generators.
    """
    top = P["n"] - 1
    k = len(codomain_vertices)
    R = [[parse_scalar(x, field) for x in row] for row in relation]
    qcols = []
    edge_by_uv = {tuple(uv): A for uv, A in zip(P["covers"], parsed_edges(module, field))}
    for vertex in codomain_vertices:
        A = edge_by_uv[vertex, top + 1]
        qcols.append([row[0] for row in A])
    Q = transpose(qcols, ncols=module["dimensions"][top])
    assert len(Q) == module["dimensions"][top]
    assert rank(Q, field, ncols=k) == len(Q)
    assert all(not x for row in matmul(Q, R, field, ncols=len(relation[0])) for x in row)
    relation_rank = rank(R, field)
    assert relation_rank + len(Q) == k
    # Stalkwise quotient is identity at the leaves; naturality is encoded by Q.
    return {"codomain_projective_vertices": codomain_vertices,
            "domain_projective_vertices": [top + 1] * len(relation[0]),
            "relation_at_top": matrix_strings(relation),
            "quotient_at_top": matrix_strings(Q),
            "relation_rank": relation_rank,
            "quotient_rank": len(Q),
            "quotient_exactness_verified": True,
            "category": "Rep_k(P)"}


def nonsplit_certificate(P, field):
    S1, S2, E = simple(P, 1), simple(P, 2), supported(P, {1, 2})
    for M in (S1, S2, E):
        all_maps(P, M, field)
    # Hom(S1,E)=0 rules out any section of the nonzero quotient E→S1.
    rows, nvars = hom_equations(P, S1, E, field)
    assert nvars == 1 and rank(rows, field, ncols=nvars) == 1
    injection = [zeros(E["dimensions"][v], S2["dimensions"][v], field) for v in range(P["n"])]
    projection = [zeros(S1["dimensions"][v], E["dimensions"][v], field) for v in range(P["n"])]
    injection[1] = [[parse_scalar(1, field)]]
    projection[0] = [[parse_scalar(1, field)]]
    maps = [parsed_edges(M, field) for M in (S2, E, S1)]
    for e, (u, v) in enumerate(P["covers"]):
        u -= 1
        v -= 1
        assert matmul(maps[1][e], injection[u], field, ncols=S2["dimensions"][u]) == matmul(injection[v], maps[0][e], field, ncols=S2["dimensions"][u])
        assert matmul(maps[2][e], projection[u], field, ncols=E["dimensions"][u]) == matmul(projection[v], maps[1][e], field, ncols=E["dimensions"][u])
    for v in range(P["n"]):
        assert rank(injection[v], field, ncols=S2["dimensions"][v]) == S2["dimensions"][v]
        assert rank(projection[v], field, ncols=E["dimensions"][v]) == S1["dimensions"][v]
        assert S2["dimensions"][v] + S1["dimensions"][v] == E["dimensions"][v]
        assert all(not x for row in matmul(projection[v], injection[v], field, ncols=S2["dimensions"][v]) for x in row)
    return {"middle_module": E, "injection": matrix_strings_3d(injection),
            "projection": matrix_strings_3d(projection), "stalkwise_exact": True,
            "naturality_verified": True, "section_hom_dimension": 0,
            "nonsplit": True}


def build_study():
    modules, fixtures = [], []
    chain, diamond, fork = POSETS

    def add(case, family, field, P, raw_M, raw_N, expected, metadata=None, gauges=None):
        if gauges is None:
            gauges = (small_gauges(raw_M["dimensions"]), small_gauges(raw_N["dimensions"]))
        M = gauge_module(P, raw_M, gauges[0], field)
        N = gauge_module(P, raw_N, gauges[1], field)
        for suffix, module in (("source", M), ("target", N)):
            module.update(id=f"{case}_{field}_{suffix}", field=field)
            modules.append(module)
        observed, hom, oracle = bar_oracle(P, M, N, len(expected) - 1, field)
        assert observed == expected, (case, field, observed, expected)
        fixture = {"case": f"{case}_{field}", "base_case": case, "family": family, "field": field,
                   "source": M["id"], "target": N["id"],
                   "maxdegree": len(expected) - 1, "expected_ext": observed,
                   "expected_hom_basis": [list(map(scalar_string, v)) for v in hom],
                   "category": "Rep_k(P)", "coefficient_bits": coefficient_bits((M, N)),
                   "oracle": oracle, "metadata": metadata or {}}
        fixtures.append(fixture)

    for field in FIELDS:
        add("crossing_intervals", "interval", field, chain,
            supported(chain, {1, 2, 3}), supported(chain, {2, 3, 4}), [0, 1, 0],
            {"source_interval": [1, 3], "target_interval": [2, 4]})
        add("nonsplit_edge", "extension", field, diamond,
            simple(diamond, 1), simple(diamond, 2), [0, 1, 0, 0],
            {"extension_certificate": nonsplit_certificate(diamond, field)})
        add("relation_ext2", "relation", field, diamond,
            simple(diamond, 1), simple(diamond, 4), [0, 0, 1, 0],
            {"minimal_projective_resolution_generators": [[1], [2, 3], [4]]})
        CplusS2 = direct_sum(diamond, [supported(diamond, {1, 2, 3, 4}), simple(diamond, 2)])
        add("projective_source", "projective_control", field, diamond,
            projective(diamond, 2), CplusS2, [2, 0, 0, 0],
            {"source_projective_vertex": 2, "hom_evaluation_vertex": 2})
        add("injective_target", "injective_control", field, diamond,
            CplusS2, injective(diamond, 2), [2, 0, 0, 0],
            {"target_injective_vertex": 2, "hom_dual_evaluation_vertex": 2})
        C = module_data(fork, [1, 1, 1, 2], [[[-1], [-1]], [[1], [0]], [[0], [1]]])
        Ccert = presentation_certificate(fork, C, field, [1, 2, 3], [[1], [1], [1]])
        end_eq, end_nvars = hom_equations(fork, C, C, field)
        Ccert["endomorphism_dimension"] = end_nvars - rank(end_eq, field, ncols=end_nvars)
        assert Ccert["endomorphism_dimension"] == 1
        add("coupled_presentation", "projective_presentation", field, fork,
            C, simple(fork, 4), [0, 1, 0], {"presentation_certificate": Ccert})
        add("coupled_target", "unequal_coupled_target", field, fork,
            direct_sum(fork, [simple(fork, i) for i in (1, 2, 3)]), C, [0, 3, 0],
            {"target_presentation_certificate": Ccert})
        add("coupled_hom_ext", "coupled_hom_and_ext", field, fork,
            C, direct_sum(fork, [C, simple(fork, 4)]), [1, 1, 0],
            {"source_presentation_certificate": Ccert,
             "hom_generator": "inclusion into first summand C",
             "ext_generator": "projection to S4 target summand"})
        if field == "F2":
            D = module_data(fork, [1, 1, 0, 1], [[[1]], [[1]], [[]]])
            ext1 = 1
        else:
            D = module_data(fork, [1, 1, 0, 0], [[], [], []])
            ext1 = 2
        Dcert = presentation_certificate(fork, D, field, [1, 2], [[1, 1], [1, -1]])
        add("characteristic_presentation", "characteristic_change", field, fork,
            D, simple(fork, 4), [0, ext1, 0], {"presentation_certificate": Dcert})

    C = module_data(fork, [1, 1, 1, 2], [[[-1], [-1]], [[1], [0]], [[0], [1]]])
    CC = direct_sum(fork, [C, C])
    SS = direct_sum(fork, [simple(fork, 4), simple(fork, 4)])
    for bits in (4, 16, 64, 256):
        large = 2 ** bits - 1
        for mode, a in (("numerator", Fraction(large)), ("denominator", Fraction(1, large)),
                        ("both", Fraction(large, large - 2))):
            U = identity(4)
            for i, row in enumerate(((1, 2), (3, 5))):
                for j, h in enumerate(row):
                    U[i][j + 2] = a * h
            gauges = ([identity(2), identity(2), identity(2), U],
                      [identity(0), identity(0), identity(0), identity(2)])
            add(f"coefficient_{mode}_{bits}", "coefficient_growth", "QQ", fork,
                CC, SS, [0, 4, 0],
                {"coefficient_mode": mode, "requested_bits": bits,
                 "gauge_parameter": scalar_string(a),
                 "gauge_recipe": "top U(a)=[[I2,a*H],[0,I2]], H=[[1,2],[3,5]], leaves and target identity",
                 "fixed_module_isomorphism_types": "C⊕C → S4⊕S4",
                 "input_bit_lengths_recorded": True}, gauges=gauges)
    return {"schema": 1, "posets": POSETS, "modules": modules, "fixtures": fixtures,
            "oracle_description": "Independent exact normalized category-bar cochains and cover Hom equations; no TamerOp/QPA imports",
            "fields": list(FIELDS), "fixture_count": len(fixtures)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("fixtures.json"))
    args = parser.parse_args()
    data = build_study()
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    for fixture in data["fixtures"]:
        print(f'{fixture["case"]:35s} {fixture["field"]:4s} Ext={fixture["expected_ext"]} bits={fixture["coefficient_bits"]}')
    print(f'Wrote {len(data["fixtures"])} fixtures, {len(data["modules"])} module inputs: {args.output}')


if __name__ == "__main__":
    main()
