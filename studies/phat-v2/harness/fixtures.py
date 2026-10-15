"""Deterministic filtered F2 chain complexes; no TamerOp or PHAT dependency."""
import argparse
import hashlib
import itertools as it
import json
import random
from pathlib import Path


def ordered(cells):
    """Cells are (dimension, integer grade, boundary indices in original order)."""
    permutation = sorted(range(len(cells)), key=lambda i: (cells[i][1], cells[i][0], i))
    inverse = {old: new for new, old in enumerate(permutation)}
    return [(cells[i][0], cells[i][1], sorted(inverse[j] for j in cells[i][2]))
            for i in permutation]


def graph(level, variant):
    n = (32, 128, 512)[level]
    rng = random.Random(1100 + variant)
    grades = [rng.randrange(6) for _ in range(n)]
    # Forest, cycle, disconnected cycles, and a connected graph with extra edges.
    edges = {(i, i + 1) for i in range(n - 1) if variant != 2 or i % 16 != 15}
    if variant == 1:
        edges.add((0, n - 1))
    if variant == 2:
        edges.update((i, min(i + 15, n - 1)) for i in range(0, n, 16))
    if variant == 3:
        while len(edges) < 4 * n:
            a, b = sorted(rng.sample(range(n), 2))
            edges.add((a, b))
    cells = [(0, g, []) for g in grades]
    for a, b in sorted(edges):
        cells.append((1, max(grades[a], grades[b]) + rng.randrange(3), [a, b]))
    return ordered(cells), None


def simplicial(level, variant):
    # Complete 2-skeleta, triangulated disks, sphere boundaries joined at a
    # vertex, and complete 3-skeleta supply distinct fill-in and homology regimes.
    n = ((9, 15, 24), (5, 10, 20), (4, 12, 32), (7, 11, 16))[variant][level]
    maximal = []
    if variant in (0, 3):
        maximal = list(it.combinations(range(n), 3 if variant == 0 else 4))
    elif variant == 1:
        for x in range(n - 1):
            for y in range(n - 1):
                a = x * n + y
                maximal.extend([(a, a + 1, a + n), (a + 1, a + n, a + n + 1)])
    else:
        for j in range(n):
            vertices = (0, 3 * j + 1, 3 * j + 2, 3 * j + 3)
            maximal.extend(it.combinations(vertices, 3))
    faces = set()
    for simplex in maximal:
        for k in range(1, len(simplex) + 1):
            faces.update(it.combinations(simplex, k))
    faces = sorted(faces, key=lambda s: (len(s), s))
    lookup = {s: i for i, s in enumerate(faces)}
    rng = random.Random(2200 + variant)
    grades = {}
    cells = []
    for s in faces:
        boundary = list(it.combinations(s, len(s) - 1)) if len(s) > 1 else []
        grades[s] = max((grades[t] for t in boundary), default=0) + rng.randrange(2)
        cells.append((len(s) - 1, grades[s], [lookup[t] for t in boundary]))
    return ordered(cells), None


def cubical(level, variant):
    dim, periodic = (2 if variant < 2 else 3), bool(variant % 2)
    n = ((8, 20, 40) if dim == 2 else (3, 5, 8))[level]
    rng = random.Random(3300 + variant)
    vertex_grades = {p: rng.randrange(8) for p in it.product(range(n), repeat=dim)}
    keys = []
    for mask in range(1 << dim):
        ranges = [range(n if periodic or not mask & (1 << k) else n - 1)
                  for k in range(dim)]
        keys.extend((mask, p) for p in it.product(*ranges))
    keys.sort(key=lambda key: (key[0].bit_count(), key))
    lookup = {key: i for i, key in enumerate(keys)}
    cells = []
    for mask, p in keys:
        axes = [k for k in range(dim) if mask & (1 << k)]
        vertices = []
        for bits in it.product((0, 1), repeat=len(axes)):
            q = list(p)
            for k, bit in zip(axes, bits):
                q[k] = (q[k] + bit) % n
            vertices.append(tuple(q))
        faces = set()
        for k in axes:
            q = list(p)
            q[k] = (q[k] + 1) % n
            for position in (p, tuple(q)):
                index = lookup[(mask ^ (1 << k), position)]
                faces.symmetric_difference_update([index])
        cells.append((len(axes), max(vertex_grades[q] for q in vertices), sorted(faces)))
    return ordered(cells), None


def algebraic(level, variant):
    rng = random.Random(4400 + variant)
    pairs = (12, 36, 96)[level]
    cells, expected = [], {"finite": [], "essential": []}
    for j in range(pairs):
        degree, birth = j % 3, rng.randrange(5)
        death = birth + rng.randrange(4)
        b = len(cells)
        cells.extend([(degree, birth, []), (degree + 1, death, [b])])
        if birth != death:
            expected["finite"].append([degree, birth, death])
    for h in range(3):
        for _ in range(1 + variant):
            birth = rng.randrange(6)
            cells.append((h, birth, []))
            expected["essential"].append([h, birth])
    # Conjugate the differential by filtration-preserving elementary basis
    # changes. Both adjacent boundary matrices are transformed, not just one.
    dims = [c[0] for c in cells]
    grades = [c[1] for c in cells]
    columns = [sum(1 << row for row in c[2]) for c in cells]
    candidates = [(i, j) for i in range(len(cells)) for j in range(len(cells))
                  if i != j and dims[i] == dims[j] and grades[i] <= grades[j]]
    for _ in range(len(cells) * (2, 4, 8, 16)[variant]):
        i, j = rng.choice(candidates)
        columns[j] ^= columns[i]
        for k in range(len(cells)):
            if dims[k] == dims[i] + 1 and columns[k] & (1 << j):
                columns[k] ^= 1 << i
    transformed = [(dims[j], grades[j], bit_indices(col)) for j, col in enumerate(columns)]
    return ordered(transformed), {k: sorted(v) for k, v in expected.items()}


def bit_indices(bits):
    result = []
    while bits:
        low = bits & -bits
        result.append(low.bit_length() - 1)
        bits ^= low
    return result


def controls():
    triangle = [(0, 0, []), (0, 0, []), (0, 0, []),
                (1, 1, [0, 1]), (1, 1, [0, 2]), (1, 1, [1, 2])]
    filled = triangle + [(2, 2, [3, 4, 5])]
    tetra = [(0, 0, []) for _ in range(4)]
    edges = list(it.combinations(range(4), 2))
    tetra += [(1, 0, list(e)) for e in edges]
    tetra += [(2, 0, [4 + edges.index(e) for e in it.combinations(t, 2)])
              for t in it.combinations(range(4), 3)]
    return {
        "empty": ([], {"finite": [], "essential": []}),
        "vertex": ([(0, -2, [])], {"finite": [], "essential": [[0, -2]]}),
        "edge": ([(0, 0, []), (0, 1, []), (1, 2, [0, 1])],
                 {"finite": [[0, 1, 2]], "essential": [[0, 0]]}),
        "circle": (triangle, {"finite": [[0, 0, 1]] * 2, "essential": [[0, 0], [1, 1]]}),
        "filled_triangle": (filled, {"finite": [[0, 0, 1]] * 2 + [[1, 1, 2]], "essential": [[0, 0]]}),
        "tied_triangle": ([(d, 0, b) for d, _, b in filled], {"finite": [], "essential": [[0, 0]]}),
        "sphere": (tetra, {"finite": [], "essential": [[0, 0], [2, 0]]}),
        "delayed_sphere": (tetra + [(3, 3, [10, 11, 12, 13])],
                           {"finite": [[2, 0, 3]], "essential": [[0, 0]]}),
    }


def encode(cells):
    return (str(len(cells)) + "\n" + "".join(
        " ".join(map(str, [d, g, len(b), *b])) + "\n" for d, g, b in cells)).encode()


def decode(path):
    lines = Path(path).read_text().splitlines()
    n = int(lines[0])
    assert len(lines) == n + 1
    cells = []
    for line in lines[1:]:
        d, g, count, *boundary = map(int, line.split())
        assert count == len(boundary)
        cells.append((d, g, boundary))
    return cells


def generate(destination):
    from oracle import barcode, validate
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    cases = []
    for family, generator in (("graph", graph), ("simplicial", simplicial),
                              ("cubical", cubical), ("algebraic", algebraic)):
        for level in range(3):
            for variant in range(4):
                cells, known = generator(level, variant)
                reserved = variant == 2 and (level > 0 or family in ("graph", "cubical"))
                cases.append((f"{family}_s{level + 1}_v{variant + 1}", family, level,
                              variant, "evaluation" if reserved else "development", cells, known))
    cases += [(name, "control", -1, -1, "control", cells, known)
              for name, (cells, known) in controls().items()]
    manifest = {"schema": 1, "field": "F2", "cases": []}
    for name, family, level, variant, split, cells, known in cases:
        validate(cells)
        expected = barcode(cells)
        if known is not None:
            assert expected == known, (name, "independent oracle disagrees with known bars")
        data = encode(cells)
        (destination / (name + ".txt")).write_bytes(data)
        row = dict(id=name, family=family, size_level=level + 1, variant=variant + 1,
                   split=split, pilot=family != "control" and variant == 0,
                   path=name + ".txt", sha256=hashlib.sha256(data).hexdigest(),
                   cells=len(cells), nonzeros=sum(len(b) for _, _, b in cells),
                   max_degree=max((d for d, _, _ in cells), default=0),
                   grades=len({g for _, g, _ in cells}), expected=expected,
                   output_bars=sum(map(len, expected.values())))
        manifest["cases"].append(row)
        print(name, row["cells"], row["nonzeros"], row["output_bars"], flush=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    generate(parser.parse_args().destination)
