"""Exhaustive small-instance check of the fresh-output chain classification."""
from itertools import combinations, product

from ordered_rows import all_ranked_bodies, line_bodies

OPERATORS = tuple(product("?*+", (False, True)))  # kind, greedy
NO_BODY = object()


def quantify(body, operator, keep):
    """Enumerate paths, then apply the requested observation to the list."""
    kind, greedy = operator
    tails = [()] * len(body)
    outputs = [()] * len(body)
    for x in reversed(range(len(body))):
        stop = [(x, NO_BODY)]
        strict = [(y, val) for y, val in body[x] if y != x]

        def extend(offers):
            return [(z, value if last is NO_BODY else last)
                    for y, value in offers for z, last in tails[y]]

        moves = extend(strict)
        tails[x] = keep(moves + stop if greedy else stop + moves)
        if kind == "+":
            candidates = extend(body[x])
        elif kind == "?":
            candidates = strict + stop if greedy else stop + strict
        else:
            candidates = tails[x]
        # A fresh zero-body invocation returns no defined capture.
        outputs[x] = keep((y, None if val is NO_BODY else val)
                          for y, val in candidates)
    return tuple(outputs)


def distinct_pairs(row):
    return tuple(dict.fromkeys(row))


def normal_form(chain):
    """The first optional and the largest plus after implicit star expansion."""
    optional = plus = None
    for kind, greedy in chain:
        if kind in "?*" and optional is None:
            optional = greedy or plus is True
        if kind in "+*":
            plus = greedy or plus is True
    factors = []
    if optional is not None:
        factors.append(("?", optional))
    if plus is not None:
        factors.append(("+", plus))
    return tuple(factors)


def interpret(body, words, keep):
    rows = {(): tuple(map(keep, body))}
    for word in sorted(words - {()}, key=len):
        rows[word] = quantify(rows[word[1:]], word[0], keep)
    return rows


def separating_example(forms):
    body = (((1, "a"),), ((2, "a"),), ())
    rows = interpret(body, set(forms), distinct_pairs)
    orders = [tuple(y for y, _ in rows[word][0]) for word in forms]
    assert orders == [(1,), (1, 2), (2, 1), (0, 1), (0, 1, 2), (0, 2, 1),
                      (1, 0), (1, 2, 0), (2, 1, 0)]
    domains = [set(i for i in range(3) if mask & (1 << i)) for mask in range(8)]

    def separates(tests):
        answers = {tuple(next((y for y in order if y in test), None) for test in tests)
                   for order in orders}
        return len(answers) == len(forms)

    assert separates([{0}, {2}, {1, 2}, {0, 1}])
    assert not any(separates(tests) for tests in combinations(domains, 3))


def check_products(bodies, pairs):
    needed = {w[k:] for pair in pairs for w in pair for k in range(len(w) + 1)}
    total = 0
    for body in bodies:
        rows = interpret(body, needed, distinct_pairs)
        for word, target in pairs:
            assert rows[word] == rows[target], (body, word, target)
        total += len(pairs)
    return total


if __name__ == "__main__":
    forms = [a + b for a in [(), (("?", False),), (("?", True),)]
             for b in [(), (("+", False),), (("+", True),)]]
    separating_example(forms)
    products = [(x + y, normal_form(x + y)) for x, y in product(forms, repeat=2)]
    stars = [((("*", g),), (("?", g), ("+", g))) for g in (False, True)]
    # Compare raw unfoldings before deleting any repeated result, including
    # parallel labels, several stationary values, and an actual empty map.
    local = [((a, b), normal_form((a, b))) for a, b in product(OPERATORS, repeat=2)
             if (a[0], b[0]) in (("?", "?"), ("+", "+"), ("+", "?"))] + stars
    local_words = {w[k:] for pair in local for w in pair for k in range(len(w) + 1)}
    bodies = line_bodies()
    mixed_labels = (((0, None), (1, "h"), (0, "k"), (1, None)), ((1, "m"),))
    for body in [*bodies, mixed_labels]:
        rows = interpret(body, local_words, tuple)
        for word, target in local:
            assert tuple(map(distinct_pairs, rows[word])) == tuple(map(distinct_pairs, rows[target]))
    print(f"{(len(bodies) + 1) * len(local)} local laws checked on raw lists")
    for x, y in product(forms, repeat=2):
        assert normal_form(x + y + x) == normal_form(x + y)
    chains = {w for k in range(5) for w in product(OPERATORS, repeat=k)}
    for body in bodies:
        rows = interpret(body, chains, distinct_pairs)
        for chain in chains:
            assert rows[chain] == rows[normal_form(chain)], (body, chain)
    print(f"{len(bodies) * (len(chains) - 1)} nonempty chains checked using distinct pairs")
    total = check_products(bodies, products + stars) + check_products(all_ranked_bodies(4), products + stars)
    assert total == 885859
    print(f"{total} pair-order comparisons for 81 products and both star expansions")
