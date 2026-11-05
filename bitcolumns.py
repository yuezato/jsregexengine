"""Position columns for the offline reporter (Appendix C).

All offsets refer to positions, with None for absence. Forward colors use
half-open intervals in text order; backward colors use the reversed order.
Integer buffers are byte-rounded, not Python lists of N position objects.
"""
from array import array
from math import isqrt


def packed(maximum, length=0):
    """An unsigned, zero-filled buffer that can store maximum."""
    if maximum <= 0xff:
        return bytearray(length)
    kind = 'H' if maximum <= 0xffff else 'I' if maximum <= 0xffffffff else 'Q'
    return array(kind, [0]) * length


def ceil_sqrt(n):
    return 1 + isqrt(n - 1)


class Encoding:
    """Share a small select-in-a-word table among all columns for one word."""
    def __init__(self, n):
        self.n = n
        self.width = (n + 1).bit_length()  # ceil(log2(N+2))
        self.half = (self.width + 1) // 2
        self.mask = (1 << self.half) - 1
        self.lookup = None

    def explicit(self, size):
        return self.width <= ceil_sqrt(size)

    def select_word(self, word, k):
        if self.lookup is None:
            rows = [b'']
            for bit in range(self.half):
                tag = bytes((bit,))
                rows += [row + tag for row in rows]
            self.lookup = rows
        low = word & self.mask
        count = low.bit_count()
        if k < count:
            return self.lookup[low][k]
        return self.half + self.lookup[word >> self.half][k - count]


class _Bits:
    """rank(end) counts ones strictly before end, with one prefix count per word."""
    def __init__(self, length, encoding):
        self.width = encoding.width
        self.words = packed((1 << self.width) - 1, (length + self.width - 1) // self.width)
        self.length = length

    def set(self, i):
        block, bit = divmod(i, self.width)
        self.words[block] |= 1 << bit

    def finish(self):
        self.prefix = packed(self.length, len(self.words) + 1)
        total = 0
        for i, word in enumerate(self.words):
            total += word.bit_count()
            self.prefix[i + 1] = total
        return total

    def rank(self, end):
        block, bit = divmod(end, self.width)
        count = self.prefix[block]
        if bit:
            count += (self.words[block] & ((1 << bit) - 1)).bit_count()
        return count

    def window(self, start):
        block, bit = divmod(start, self.width)
        word = self.words[block] >> bit
        if bit and block + 1 < len(self.words):
            word |= (self.words[block + 1] & ((1 << bit) - 1)) << (self.width - bit)
        return word


class _Select(_Bits):
    """Long groups store absolute selects, long subgroups store local offsets.
    A short subgroup fits in a W-bit window straddling at most two words.
    """
    def index(self, encoding):
        self.encoding = encoding
        count = self.finish()
        self.small = max(1, self.width // (self.width**2).bit_length())
        self.large = ((self.width + self.small - 1) // self.small) * self.small
        groups = (count + self.small - 1) // self.small
        self.base = packed(encoding.n)
        self.long = packed(encoding.n)
        self.absolute = packed(encoding.n)
        self.offset = packed(self.width**2, groups)
        self.spill = _Bits(groups, encoding)
        self.relative = packed(self.width**2)
        batch = []
        for i, word in enumerate(self.words):
            while word:
                lowest = word & -word
                batch.append(i * self.width + lowest.bit_length() - 1)
                word ^= lowest
                if len(batch) == self.large:
                    self._group(batch)
                    batch.clear()
        if batch:
            self._group(batch)
        self.spill.finish()

    def _group(self, positions):
        start = positions[0]
        group = len(self.base)
        self.base.append(start)
        if positions[-1] - start >= self.width**2:
            self.long.append(len(self.absolute) + 1)
            self.absolute.extend(positions)
            return
        self.long.append(0)
        for j in range(0, len(positions), self.small):
            index = (group * self.large + j) // self.small
            first = positions[j]
            stop = min(j + self.small, len(positions))
            self.offset[index] = first - start
            if positions[stop - 1] - first >= self.width:
                self.spill.set(index)
                self.relative.extend(x - start for x in positions[j:stop])
                # Only the final group can be partial.
                self.relative.extend([0] * (j + self.small - stop))

    def select(self, k):
        group, offset = divmod(k, self.large)
        if self.long[group]:
            return self.absolute[self.long[group] - 1 + offset]
        start = self.base[group]
        sub, inner = divmod(k, self.small)
        block, bit = divmod(sub, self.width)
        if self.spill.words[block] & (1 << bit):
            return start + self.relative[self.spill.rank(sub) * self.small + inner]
        start += self.offset[sub]
        return start + self.encoding.select_word(self.window(start), inner)


class _Neighbors:
    """Next/previous occurrence for a single digit, including across word boundaries."""
    def __init__(self, length, encoding):
        self.bits = _Bits(length, encoding)
        self.length = length

    def index(self):
        words = self.bits.words
        self.before = packed(len(words), len(words))
        self.after = packed(len(words), len(words))
        last = 0
        for i, word in enumerate(words):
            self.before[i] = last
            if word:
                last = i + 1
        last = 0
        for i in reversed(range(len(words))):
            self.after[i] = last
            if words[i]:
                last = i + 1

    def neighbor(self, end, previous):
        if (previous and end == 0) or (not previous and end == self.length):
            return None
        width, words = self.bits.width, self.bits.words
        block, bit = divmod(end - int(previous), width)
        if previous:
            word = words[block] & ((2 << bit) - 1)
            if not word:
                block = self.before[block] - 1
                if block < 0:
                    return None
                word = words[block]
            return block * width + word.bit_length() - 1
        word = words[block] & -(1 << bit)
        if not word:
            block = self.after[block] - 1
            if block < 0:
                return None
            word = words[block]
        return block * width + (word & -word).bit_length() - 1


class _Colors:
    """Small-alphabet successor/predecessor via a constant number of stable digit partitions.

    Spend O(sqrt(size)) bitmaps per level, each O(N) bits. In a coded column
    this radix is O(log N), so scanning all packed bitmap words costs O(N).
    The alphabet has at most 2*size**2 colors, so the number of levels is O(1).
    """
    def __init__(self, symbols, palette, size, encoding):
        self.levels = []
        self.palette = palette
        if not palette:
            self.low = []
            self.mask = 0
            return
        digit_bits = max(1, ceil_sqrt(size).bit_length() - 1)
        digit_bits = min(digit_bits, palette.bit_length())
        self.mask = (1 << digit_bits) - 1
        shift = (palette.bit_length() - 1) // digit_bits * digit_bits
        current = symbols
        while shift:
            bitmaps = [None] * (self.mask + 1)
            for i, symbol in enumerate(current):
                digit = (symbol >> shift) & self.mask
                if bitmaps[digit] is None:
                    bitmaps[digit] = _Select(len(symbols), encoding)
                bitmaps[digit].set(i)
            offsets = [0] * len(bitmaps)
            pos = 0
            for digit, bits in enumerate(bitmaps):
                if bits is not None:
                    bits.index(encoding)
                    offsets[digit] = pos
                    pos += bits.prefix[-1]
            self.levels.append((shift, offsets, bitmaps))
            cursors = offsets.copy()
            following = packed(palette, len(symbols))
            for symbol in current:
                digit = (symbol >> shift) & self.mask
                following[cursors[digit]] = symbol
                cursors[digit] += 1
            current = following
            shift -= digit_bits
        self.low = [None] * (self.mask + 1)
        for i, symbol in enumerate(current):
            digit = symbol & self.mask
            if self.low[digit] is None:
                self.low[digit] = _Neighbors(len(symbols), encoding)
            self.low[digit].bits.set(i)
        for bits in self.low:
            if bits is not None:
                bits.index()

    def neighbor(self, color, end, previous=False):
        if not 0 < color <= self.palette:
            return None
        # Project the boundary into the stable digit blocks; undo the chosen
        # neighbor on return. A neighbor from another prefix fails a block test.
        for shift, offsets, bitmaps in self.levels:
            digit = (color >> shift) & self.mask
            if bitmaps[digit] is None:
                return None
            end = offsets[digit] + bitmaps[digit].rank(end)
        low = self.low[color & self.mask]
        if low is None:
            return None
        pos = low.neighbor(end, previous)
        for shift, offsets, bitmaps in reversed(self.levels):
            if pos is None:
                return None
            digit = (color >> shift) & self.mask
            k = pos - offsets[digit]
            if not 0 <= k < bitmaps[digit].prefix[-1]:
                return None  # crossed into a different prefix's interval
            pos = bitmaps[digit].select(k)
        return pos


class Positions:
    """Explicit partial map. Zero encodes absence, including at position zero."""
    def __init__(self, n):
        self.data = packed(n, n)

    def put(self, x, y):
        self.data[x] = y + 1

    def get(self, x):
        y = self.data[x]
        return y - 1 if y else None


class Colored:
    """Sweep in matching order; release the old target before opening the new interval."""
    def __init__(self, encoding, size, forward):
        self.encoding, self.size, self.forward = encoding, size, forward
        self.n = encoding.n
        limit = min(self.n // 2, 2 * size**2)
        self.sources = packed(limit, self.n)
        self.targets = packed(limit, self.n)
        self.fixed = bytearray(self.n)
        self.free = []
        self.palette = 0
        self.source_index = None

    def order(self, x):
        return x if self.forward else self.n - 1 - x

    def release(self, x):
        color = self.targets[self.order(x)]
        if color:
            self.free.append(color)

    def target(self, y):
        i = self.order(y)
        color = self.targets[i]
        if not color:
            if self.free:
                color = self.free.pop()
            else:
                self.palette += 1
                color = self.palette
            self.targets[i] = color
        return color

    def put(self, x, y):
        if x == y:
            self.fixed[x] = 1
        else:
            self.sources[self.order(x)] = self.target(y)

    def finish(self):
        self.target_index = _Colors(self.targets, self.palette, self.size, self.encoding)
        self.free.clear()
        return self

    def get(self, x):
        if self.fixed[x]:
            return x
        i = self.order(x)
        color = self.sources[i]
        if not color:
            return None
        return self.order(self.target_index.neighbor(color, i + 1))

    def child_after(self, y, previous):
        """Next strict preimage of y, allowing traversal to resume after a child."""
        j = self.order(y)
        color = self.targets[j]
        if not color:
            return None
        if self.source_index is None:
            self.source_index = _Colors(self.sources, self.palette, self.size, self.encoding)
        if previous is None:
            prev_target = self.target_index.neighbor(color, j, previous=True)
            lo = 0 if prev_target is None else prev_target
        else:
            lo = self.order(previous) + 1
        i = self.source_index.neighbor(color, lo)
        return None if i is None or i >= j else self.order(i)


def positions(encoding, size, forward, entry):
    n = encoding.n
    if encoding.explicit(size):
        column = Positions(n)
        for x in range(n):
            y = entry(x)
            if y is not None:
                column.put(x, y)
        return column
    column = Colored(encoding, size, forward)
    for i in range(n):
        x = column.order(i)
        column.release(x)
        y = entry(x)
        if y is not None:
            column.put(x, y)
    return column.finish()


class Tail:
    """Terminal before the first stop; a moving query must take one edge first."""
    def __init__(self, parent, stops, encoding, size, forward):
        self.parent, self.stops = parent, stops
        n = encoding.n
        if encoding.explicit(size):
            terminal = self.terminal = Positions(n)
            for x in (reversed(range(n)) if forward else range(n)):
                y = parent.get(x)
                if y is not None and not stops[x]:
                    terminal.put(x, x if stops[y] else terminal.get(y))
            return

        terminal = self.terminal = Colored(encoding, size, forward)
        for i in range(n):
            x = terminal.order(i)
            terminal.release(x)
            if stops[x] or terminal.fixed[x] or terminal.sources[i] or parent.get(x) is None:
                continue
            u = x
            while not stops[parent.get(u)]:
                u = parent.get(u)
            terminal.fixed[u] = 1
            if u == x:
                continue
            color = terminal.target(u)
            # Walk the component backwards. On return, parent and sibling lookup
            # replace a stack whose size could depend on the length of the word.
            v, previous = u, None
            while True:
                child = parent.child_after(v, previous)
                if child is not None:
                    if stops[child]:
                        previous = child
                    else:
                        terminal.sources[terminal.order(child)] = color
                        v, previous = child, None
                elif v == u:
                    break
                else:
                    previous, v = v, parent.get(v)
        terminal.finish()

    def last(self, x):
        y = self.parent.get(x)
        return x if self.stops[y] else self.terminal.get(y)
