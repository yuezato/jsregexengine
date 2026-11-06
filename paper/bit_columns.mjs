// Reference implementation of Appendix C's color strings. Scans implement the
// rank/select queries here so that the two encodings can be inspected directly.
import assert from 'node:assert/strict';

export const positions = length => Array.from({length}, (_, x) => x);

export function crossingWidth(row, tagged = false) {
  let width = 0;
  for (let cut = 0; cut + 1 < row.length; cut++) {
    const across = new Set();
    row.forEach((item, x) => {
      if (item === null) return;
      const y = tagged ? item[0] : item;
      if ((x <= cut) !== (y <= cut)) across.add(tagged ? item.join(',') : y);
    });
    width = Math.max(width, across.size);
  }
  return width;
}

class ColorColumn {
  constructor(length, direction, bound) {
    this.length = length;
    this.direction = direction;
    this.bound = bound;
    this.fixed = new Uint8Array(length);
    this.source = Array(length).fill(null);
    this.target = Array(length).fill(null);
    this.free = [];
    this.colorCount = 0;
  }
  position(index) {
    return this.direction === 1 ? index : this.length - 1 - index;
  }
  assign(y) {
    if (this.target[y] === null) {
      const color = this.free.length ? this.free.pop() : this.colorCount++;
      assert(color < this.bound);
      this.target[y] = color;
    }
    return this.target[y];
  }
  release(x) {
    if (this.target[x] !== null) this.free.push(this.target[x]);
  }
  get(x) {
    if (this.fixed[x]) return x;
    const color = this.source[x];
    if (color === null) return null;
    for (let i = this.position(x) + 1; i < this.length; i++) {
      const y = this.position(i);
      if (this.target[y] === color) return y;
    }
    assert.fail('A source color must have a target');
  }
  preimages(y) {
    const color = this.target[y], sources = this.fixed[y] ? [y] : [];
    if (color === null) return sources;
    for (let i = this.position(y) - 1; i >= 0; i--) {
      const x = this.position(i);
      if (this.source[x] === color) sources.push(x);
      if (this.target[x] === color) break;
    }
    return sources;
  }
}

export function encode(row, direction, bound) {
  const width = crossingWidth(row);
  assert(width <= bound);
  const result = new ColorColumn(row.length, direction, bound);
  for (let i = 0; i < row.length; i++) {
    const x = result.position(i), y = row[x];
    result.release(x);
    if (y === x) result.fixed[x] = 1;
    else if (y !== null) {
      assert(result.position(x) < result.position(y));
      result.source[x] = result.assign(y);
    }
  }
  assert.equal(result.colorCount, width);
  assert.deepEqual(positions(row.length).map(x => result.get(x)), row);
  return result;
}

// Delete the stops. The first source of each remaining component discovers its
// top vertex. Its other vertices share a color, and the top is a fixed point.
export function terminalColumn(parent, stops, bound) {
  const result = new ColorColumn(parent.length, parent.direction, bound);
  for (let i = 0; i < parent.length; i++) {
    const x = result.position(i);
    result.release(x);
    if (!stops[x] && parent.get(x) !== null && result.source[x] === null && !result.fixed[x]) {
      let u = x;
      while (!stops[parent.get(u)]) u = parent.get(u);
      result.fixed[u] = 1;
      if (u === x) continue; // A newly discovered component ending here is a singleton.
      const color = result.assign(u), pending = [u];
      while (pending.length) {
        const v = pending.pop();
        assert.equal(result.source[v], null);
        if (v !== u) result.source[v] = color;
        for (const child of parent.preimages(v)) {
          if (!stops[child]) pending.push(child);
        }
      }
    }
  }
  for (const x of positions(parent.length)) {
    if (parent.get(x) === null || stops[x]) {
      assert.equal(result.get(x), null);
    } else {
      let u = x;
      while (!stops[parent.get(u)]) u = parent.get(u);
      assert.equal(result.get(x), u);
    }
  }
  return result;
}

export function encodeRequests(requests, bound) {
  assert(crossingWidth(requests, true) <= bound);
  const forward = encode(requests.map((item, x) => item && item[0] >= x ? item[0] : null), 1, bound);
  const backward = encode(requests.map((item, x) => item && item[0] < x ? item[0] : null), -1, bound);
  return requests.map((item, x) => item && [forward.get(x) ?? backward.get(x), item[1]]);
}

export function explicitColumn(row, direction) {
  return {length: row.length, direction, get: x => row[x]};
}

export function explicitTerminals(parent, stops) {
  const N = parent.length, targets = Array(N).fill(null);
  for (let i = 0; i < N; i++) {
    const x = parent.direction === 1 ? N - 1 - i : i;
    const y = parent.get(x);
    if (y !== null && !stops[x]) targets[x] = stops[y] ? x : targets[y];
  }
  return explicitColumn(targets, parent.direction);
}
