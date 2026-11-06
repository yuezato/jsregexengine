"""Finite checks of ordered composition, DFS priorities, and sparse repetition tables."""
from itertools import permutations, product
from math import factorial

VERTICES = range(3)
SETS = [frozenset(i for i in VERTICES if mask & (1 << i)) for mask in range(8)]


def trim(row, component, domain):
    kept = []
    seen = set()
    for vertex, label in row:
        if vertex not in domain or vertex in seen:
            continue
        kept.append((vertex, label))
        if vertex not in component:
            break
        seen.add(vertex)
    return kept


def check_components():
    pairs = [(i, j) for i in VERTICES for j in VERTICES if i != j]
    count = 0
    for mask in range(1 << len(pairs)):
        reachable = [{i} for i in VERTICES]
        for bit, (i, j) in enumerate(pairs):
            if mask & (1 << bit):
                reachable[i].add(j)
        if any(not reachable[j] <= reachable[i] for i in VERTICES for j in reachable[i]):
            continue
        for x in VERTICES:
            component = {j for j in reachable[x] if x in reachable[j]}
            words = [row for k in range(4) for row in product(sorted(reachable[x]), repeat=k)]
            for domain in SETS:
                functions = list(product(*(sorted(reachable[j]) if j in domain else [None]
                                           for j in VERTICES)))
                by_form, by_signature = {}, {}
                for row in words:
                    form = tuple(j for j, _ in trim(((j, None) for j in row), component, domain))
                    observations = []
                    for function in functions:
                        outputs = [function[j] for j in row if j in domain]
                        observations.append((next(iter(outputs), None),
                                             next((y for y in outputs if y != x), None)))
                    signature = tuple(observations)
                    assert by_form.setdefault(form, signature) == signature
                    assert by_signature.setdefault(signature, form) == form
                    count += 1
                a = len(component & domain)
                b = len((reachable[x] - component) & domain)
                assert len(by_form) == (b + 1) * sum(factorial(a) // factorial(a - j) for j in range(a + 1))
    return count


def line_bodies():
    rows = []
    for x in VERTICES:
        words = [row for k in range(3) for row in product(range(x, 3), repeat=k)]
        rows.append([tuple((y, (x, k)) for k, y in enumerate(row)) for row in words])
    return list(product(*rows))


def substitute(row, right):
    return [(z, (left_label, right_label)) for y, left_label in row
            for z, right_label in right[y]]


def first_two(row, x):
    return next(iter(row), None), next((item for item in row if item[0] != x), None)


def compose(first, right, x, moving):
    lfull, lmove = first
    left = lmove if moving and right[x][1] is None else lfull
    if left is None:
        return None
    y, li = left
    z, ri = right[y][1 if moving and y == x else 0]
    return z, (li, ri)


def check_products(bodies):
    count = 0
    for right in bodies:
        for boundary in SETS:
            short_right = [trim(row, {y}, boundary) for y, row in enumerate(right)]
            viable = {y for y in VERTICES if short_right[y]}
            right_queries = [first_two(row, y) for y, row in enumerate(short_right)]
            for left in bodies:
                for x, row in enumerate(left):
                    short_left = trim(row, {x}, viable)
                    actual = trim(substitute(short_left, short_right), {x}, VERTICES)
                    expected = trim(substitute(row, right), {x}, boundary)
                    assert actual == expected
                    left_queries = first_two(short_left, x)
                    assert tuple(compose(left_queries, right_queries, x, moving)
                                 for moving in (False, True)) == first_two(expected, x)
                    count += 1
    return count



def all_ranked_bodies(size):
    """Every ordered subset of forward endpoints, including the stationary option."""
    choices = []
    for x in range(size):
        ends = range(x, size)
        rows = [tuple((y, (x, k)) for k, y in enumerate(order))
                for length in range(len(ends) + 1) for order in permutations(ends, length)]
        choices.append(rows)
    return product(*choices)


def literal_paths(body, greedy):
    positions = range(len(body))
    tails = [[] for _ in positions]
    for x in reversed(positions):
        moves = [(z, (label,) + rest) for y, label in body[x] if y != x
                 for z, rest in tails[y]]
        stop = [(x, ())]
        tails[x] = moves + stop if greedy else stop + moves
    plus = [[(z, (label,) + rest) for y, label in body[x] for z, rest in tails[y]]
            for x in positions]
    return tails, plus


def first_visits(paths):
    seen = set()
    distinct = []
    for endpoint, labels in paths:
        if endpoint not in seen:
            distinct.append((endpoint, labels[-1] if labels else None))
            seen.add(endpoint)
    return distinct


def discovery_tree(body, x, mandatory):
    children = [[] for _ in body]
    seen, preorder, postorder = set(), [], []

    def visit(y, path):
        seen.add(y)
        preorder.append((y, path))
        for z, edge in body[y]:
            if z != y and z not in seen:
                children[y].append((z, edge))
                visit(z, path + (edge,))
        postorder.append((y, path))

    if mandatory:
        for y, edge in body[x]:
            if y not in seen:
                visit(y, (edge,))
    else:
        visit(x, ())
    return children, (preorder, postorder)


def check_spine(tree, start, boundary, selected_edges, orders):
    marked_below = set(boundary)
    first_child = {}
    for u in reversed(range(len(tree))):
        for edge in tree[u]:
            if edge[0] in marked_below:
                first_child[u] = edge
                marked_below.add(u)
                break
    preorder, postorder = orders
    pre_marks = [u for u, _ in preorder if u in boundary]
    post_marks = [u for u, _ in postorder if u in boundary]
    first_agrees = pre_marks[:1] == post_marks[:1]
    assert first_agrees == (not pre_marks or pre_marks[0] not in first_child)
    # Equal restricted orders mean agreement for every subset of the marks.
    assert (pre_marks == post_marks) == all(u not in first_child for u in pre_marks)
    if start not in marked_below:
        assert not pre_marks and start not in selected_edges
        return
    u = start
    while u in selected_edges:
        assert selected_edges[u] == first_child[u]
        u = first_child[u][0]
    assert u in boundary and u not in first_child


def sparse_answers(body, boundary, greedy):
    """Return the full star, full plus and shared moving item at all starts."""
    viable = set(boundary)
    star, plus, moving = ([None] * len(body) for _ in range(3))

    def force(item):
        if item is None:
            return None
        y, edge = item
        stop, last = star[y]
        return stop, edge if last is None else last

    for x in reversed(range(len(body))):
        d = next((it for it in body[x] if it[0] != x and it[0] in viable), None)
        if d is not None:
            viable.add(x)
            moving[x] = force(d)
        if x in viable:
            star[x] = (x, None) if x in boundary and (not greedy or d is None) else moving[x]
        p = next((it for it in body[x] if it[0] in viable), None)
        plus[x] = force(p)
    return star, plus, moving


def forest_tails(body, viable, boundary, greedy):
    """Compute the stop and the last label from one nearest-marked-ancestor query."""
    parents = {}
    for x in viable:
        for y, label in body[x]:
            if y != x and y in viable:
                parents[x] = y, label
                break
    def nearest(marks):
        answer = {}
        for x in sorted(viable, reverse=True):
            if x in marks:
                answer[x] = x
            elif x in parents:
                answer[x] = answer.get(parents[x][0])
        return answer
    stops = viable.difference(parents) if greedy else boundary
    assert stops <= boundary
    last_child = nearest({u for u, (v, _) in parents.items() if v in stops})
    answers = [None] * len(body)
    for x in viable:
        if x in stops:
            answers[x] = (x, None)
        else:
            answers[x] = parents[last_child[x]]
    return answers


def check_repetitions(bodies):
    counts = dict(bodies=0, dfs_orders=0, sparse_items=0, priority_domains=0)
    for body in bodies:
        counts["bodies"] += 1
        positions = range(len(body))
        ranks, full_paths, trees = {}, {}, {}
        for greedy in (False, True):
            for mandatory, paths in enumerate(literal_paths(body, greedy)):
                ranks[greedy, mandatory] = [first_visits(row) for row in paths]
                full_paths[greedy, mandatory] = [dict(reversed(row)) for row in paths]
        for x in positions:
            for mandatory in (False, True):
                children, orders = discovery_tree(body, x, mandatory)
                if not mandatory:
                    trees[x] = children
                for greedy, order in enumerate(orders):
                    assert first_visits(order) == ranks[greedy, mandatory][x]
                    assert dict(order) == full_paths[greedy, mandatory][x]
                    counts["dfs_orders"] += 1
            for greedy in (False, True):
                def moving_list(mandatory):
                    return [item for item in ranks[greedy, mandatory][x] if item[0] != x]
                assert moving_list(False) == moving_list(True)
        for mask in range(1 << len(body)):
            boundary = {i for i in positions if mask & (1 << i)}
            antichain = all(not any(y != x and y in boundary
                                   for y, _ in ranks[False, False][x]) for x in boundary)
            viable = {x for x in positions if any(y in boundary for y, _ in ranks[False, False][x])}
            stars, pluses, optionals = [], [], []
            edges = {x: next(edge for edge in body[x] if edge[0] != x and edge[0] in viable)
                     for x in viable if any(y != x and y in viable for y, _ in body[x])}
            parents = {x: edge[0] for x, edge in edges.items()}
            for x in positions:
                check_spine(trees[x], x, boundary, edges,
                            (ranks[False, False][x], ranks[True, False][x]))
            nonleaves = set(parents.values())
            plus_criterion = all(c not in nonleaves and
                                 next(y for y, _ in body[c] if y in viable) != c
                                 for c in boundary.intersection(parents))
            optional_criterion = all(y == x or y not in boundary
                                     for x in boundary for y, _ in body[x])
            for greedy in (False, True):
                star, plus, move = sparse_answers(body, boundary, greedy)
                assert forest_tails(body, viable, boundary, greedy) == star
                stars.append(star)
                pluses.append(plus)
                optional = []
                for x in positions:
                    moves = [item for item in body[x] if item[0] != x]
                    stops = [(x, None)]
                    row = moves + stops if greedy else stops + moves
                    optional.append(next((item for item in row if item[0] in boundary), None))
                optionals.append(optional)
                for mandatory, full in [(False, star), (True, plus)]:
                    for x in positions:
                        allowed = [it for it in ranks[greedy, mandatory][x] if it[0] in boundary]
                        assert full[x] == next(iter(allowed), None)
                        assert move[x] == next((it for it in allowed if it[0] != x), None)
                        counts["sparse_items"] += 2
            # A strict tail separates the priorities exactly when it passes
            # a stopping vertex that still has a viable advancing edge.
            differing_tails = set()
            for x in reversed(positions):
                if x in parents and (x in boundary or parents[x] in differing_tails):
                    differing_tails.add(x)
            differing_pluses = set()
            advancing_boundary = set()
            for x in positions:
                first_end = next((y for y, _ in body[x] if y in viable), None)
                if first_end in differing_tails:
                    differing_pluses.add(x)
                if (x in boundary and x in parents and first_end == parents[x]
                        and first_end not in differing_tails):
                    advancing_boundary.add(x)
            differing_optionals = {x for x in boundary
                                    if any(y != x and y in boundary for y, _ in body[x])}
            assert differing_optionals <= differing_tails
            assert differing_pluses == differing_tails - advancing_boundary
            for results, expected in [(stars, differing_tails), (pluses, differing_pluses),
                                      (optionals, differing_optionals)]:
                assert {x for x in positions if results[0][x] != results[1][x]} == expected
            assert (stars[0] == stars[1]) == antichain
            assert (pluses[0] == pluses[1]) == plus_criterion
            assert (optionals[0] == optionals[1]) == optional_criterion
            counts["priority_domains"] += 1
    return counts


if __name__ == "__main__":
    families = line_bodies()
    print("component signatures:", check_components())
    print("labelled products:", check_products(families))
    print("labelled rows allowing repeated endpoints:", check_repetitions(families))
    print("all ranked four-position bodies:", check_repetitions(all_ranked_bodies(4)))
