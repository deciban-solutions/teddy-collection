"""Rule inference over a ranking: which criteria reproduce a target order.

Criteria are dicts subject -> value with higher = better; the target is a list
of subjects best-first. Ties never count as reproducing an order.
"""
import itertools
import random
import statistics


def _items(target):
    return list(target)


def kendall_tau_b(x, y):
    """Kendall tau-b between two subject->value dicts (higher = better for both)."""
    c = d = tx = ty = 0
    for a, b in itertools.combinations(list(x), 2):
        dx = x[a] - x[b]
        dy = y[a] - y[b]
        if dx == 0 and dy == 0:
            continue
        if dx == 0:
            tx += 1
            continue
        if dy == 0:
            ty += 1
            continue
        if dx * dy > 0:
            c += 1
        else:
            d += 1
    den = ((c + d + tx) * (c + d + ty)) ** 0.5
    return (c - d) / den if den else 0.0


def single(criteria, target):
    """[(tau, key)] for every criterion against the target, best first."""
    items = _items(target)
    judge = {p: len(items) - i for i, p in enumerate(items)}
    scored = [(kendall_tau_b({p: v[p] for p in items}, judge), k) for k, v in criteria.items()]
    return sorted(scored, key=lambda t: (-t[0], t[1]))


def _same_base(a, b):
    return a.replace("F:-", "F:") == b.replace("F:-", "F:")


def _strict_ok(vals, items):
    if len(set(vals.values())) < len(items):
        return False
    return sorted(items, key=lambda p: vals[p], reverse=True) == items


def lexicographic(criteria, target, max_len=3):
    """Minimal exact lexicographic rules by length: {r: [tuple of keys]}.

    A rule reproduces the target exactly when sorting on its criteria in order
    gives the target with no tied subjects. A rule is minimal when no prefix of
    it already does. A criterion and its F:- negation are never combined.
    """
    items = _items(target)
    keys = list(criteria)
    rounded = {k: {p: round(criteria[k][p], 6) for p in items} for k in keys}
    found = {r: [] for r in range(1, max_len + 1)}
    for r in range(1, max_len + 1):
        for combo in itertools.permutations(keys, r):
            if any(_same_base(a, b) for a, b in itertools.combinations(combo, 2)):
                continue
            vals = {p: tuple(rounded[k][p] for k in combo) for p in items}
            if _strict_ok(vals, items):
                found[r].append(combo)
    have = {c for lst in found.values() for c in lst}
    return {r: [c for c in lst if not any(c[:i] in have for i in range(1, len(c)))]
            for r, lst in found.items()}


def _z(v, items):
    m = statistics.mean(v[p] for p in items)
    sd = statistics.pstdev([v[p] for p in items]) or 1
    return {p: (v[p] - m) / sd for p in items}


def weighted_share(criteria, keys, target, n=400, seed=7):
    """Share of random positive weightings of z-scored `keys` that give the
    target order exactly. A weighting that ties any two subjects fails."""
    items = _items(target)
    z = {k: _z(criteria[k], items) for k in keys}
    rnd = random.Random(seed)
    ok = 0
    for _ in range(n):
        w = [rnd.gammavariate(1, 1) for _ in keys]
        sc = {p: sum(wi * z[k][p] for wi, k in zip(w, keys)) for p in items}
        if len(set(round(v, 9) for v in sc.values())) < len(items):
            continue
        ok += sorted(items, key=lambda p: sc[p], reverse=True) == items
    return ok / n


def _exact_exists(rows, n_items, r):
    """Is there an ordered choice of r distinct rows whose lexicographic tuples strictly
    decrease along items 0..n-1? Depth-first, pruning any prefix that already increases
    somewhere (no later criterion can undo that), so the search is cheap at any size."""
    n = len(rows)

    def walk(prefix, ties):
        # ties: consecutive item pairs still equal under the prefix
        if not ties:
            return True          # strictly decreasing already; any extension stays so
        if len(prefix) == r:
            return False
        for i in range(n):
            if i in prefix:
                continue
            row = rows[i]
            if any(row[p] < row[p + 1] for p in ties):
                continue
            if walk(prefix + (i,), [p for p in ties if row[p] == row[p + 1]]):
                return True
        return False
    return walk((), list(range(n_items - 1)))


def null_rate(n_items, n_criteria=40, trials=40, seed=7, max_len=3):
    """P(at least one exact lexicographic rule of length r exists) among
    `n_criteria` random 1-5 integer criteria over `n_items` subjects."""
    rnd = random.Random(seed)
    items = list(range(n_items))
    hits = {r: 0 for r in range(1, max_len + 1)}
    for _ in range(trials):
        rows = [[rnd.randint(1, 5) for _ in items] for _ in range(n_criteria)]
        for r in hits:
            if n_criteria >= r and _exact_exists(rows, n_items, r):
                hits[r] += 1
    return {r: hits[r] / trials for r in hits}


def run(criteria, target, max_len=3, top=10, seed=7):
    """Full inference summary, JSON-ready."""
    ranked = single(criteria, target)
    lex = lexicographic(criteria, target, max_len)
    n = len(target)
    return {
        "n_items": n, "n_criteria": len(criteria), "target": list(target),
        "top_single": [{"key": k, "tau": round(t, 2)} for t, k in ranked[:top]],
        "rules": {str(r): {"count": len(v), "minimal": [list(c) for c in v[:25]]}
                  for r, v in lex.items()},
        # the null draws as many random criteria as the real set, which lexicographic() searches
        "null_n_criteria": len(criteria),
        "null_rates": {str(r): v for r, v in
                       null_rate(n, len(criteria), seed=seed, max_len=max_len).items()},
    }
