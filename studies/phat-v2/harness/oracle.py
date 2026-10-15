"""Independent exact rank-invariant oracle, not a persistence column reducer."""


def rank(columns):
    pivots = {}
    for column in columns:
        while column:
            pivot = column.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = column
                break
            column ^= pivots[pivot]
    return len(pivots)


def validate(cells):
    columns = []
    assert cells == sorted(cells, key=lambda c: (c[1], c[0])), "filtration order"
    for i, (d, g, boundary) in enumerate(cells):
        assert d >= 0 and isinstance(g, int)
        assert boundary == sorted(set(boundary)), "noncanonical boundary"
        square = 0
        for j in boundary:
            assert 0 <= j < i, "boundary must precede cell"
            assert cells[j][0] == d - 1, "boundary degree"
            assert cells[j][1] <= g, "boundary filtration"
            square ^= columns[j]
        assert square == 0, "boundary squared is nonzero"
        columns.append(sum(1 << j for j in boundary))


def barcode(cells):
    """rho(s,t) = dim C_h(s) - rank D_h(s) - rank B_h(t)
                    + rank(B_h(t) projected outside C_h(s)).

    The intersection of B_h(t) with C_h(s) lies in Z_h(s), since d²=0.
    Finite differences of rho recover every nonempty interval multiplicity.
    No pivots pairing birth cells with death cells are used.
    """
    validate(cells)
    levels = sorted({g for _, g, _ in cells})
    answer = {"finite": [], "essential": []}
    if not levels:
        return answer
    for h in range(max(d for d, _, _ in cells) + 1):
        indices = [i for i, (d, _, _) in enumerate(cells) if d == h]
        boundaries = [(g, sum(1 << j for j in b)) for d, g, b in cells if d == h + 1]
        own = [(g, sum(1 << j for j in b)) for d, g, b in cells if d == h]
        masks = [sum(1 << i for i in indices if cells[i][1] <= s) for s in levels]
        cycles = [mask.bit_count() - rank(b for g, b in own if g <= s)
                  for s, mask in zip(levels, masks)]
        image = [rank(b for g, b in boundaries if g <= t) for t in levels]
        rho = {}
        for i, s in enumerate(levels):
            for j in range(i, len(levels)):
                rho[i, j] = cycles[i] - image[j] + rank(
                    b & ~masks[i] for g, b in boundaries if g <= levels[j])
                assert rho[i, j] >= 0
        for i, birth in enumerate(levels):
            for j in range(i + 1, len(levels)):
                count = (rho[i, j - 1] - rho.get((i - 1, j - 1), 0)
                         - rho[i, j] + rho.get((i - 1, j), 0))
                assert count >= 0
                answer["finite"].extend([[h, birth, levels[j]]] * count)
            count = rho[i, len(levels) - 1] - rho.get((i - 1, len(levels) - 1), 0)
            assert count >= 0
            answer["essential"].extend([[h, birth]] * count)
    return {k: sorted(v) for k, v in answer.items()}


def validate_sparse(cells):
    """Same chain/filtration contracts without retaining high-index bit vectors.

    Used for the fixed larger supplement. This is a validity check, not a new
    full-barcode oracle. Its scratch set holds one double boundary at a time.
    """
    previous = None
    for i, (d, g, boundary) in enumerate(cells):
        assert d >= 0 and isinstance(g, int)
        key = (g, d)
        assert previous is None or previous <= key, "filtration order"
        previous = key
        assert boundary == sorted(set(boundary)), "noncanonical boundary"
        square = set()
        for j in boundary:
            assert 0 <= j < i, "boundary must precede cell"
            assert cells[j][0] == d - 1, "boundary degree"
            assert cells[j][1] <= g, "boundary filtration"
            square.symmetric_difference_update(cells[j][2])
        assert not square, "boundary squared is nonzero"
