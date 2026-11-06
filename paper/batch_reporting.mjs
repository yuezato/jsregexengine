// Functional check of the all-start reporter. The color strings use reference
// arrays. The RAM time and bit bounds for packed rank/select are analytical.
import assert from 'node:assert/strict';
import {compile, prepareMatches, bitVector, setBit, hasBit, factors, primitiveExit,
        markLayer, movingAt, stationaryAt} from './all_starts.mjs';
import {positions, crossingWidth, encode, encodeRequests, terminalColumn,
        explicitColumn, explicitTerminals} from './bit_columns.mjs';

const counts = {rows: 0, partitions: 0, pieces: 0, regions: 0, random: 0, tests: 0, explicit: 0, coded: 0};

function partition(nodes, subtreeSize, threshold) {
  const cut = new Set(), pieces = [], owner = new Map(), residuals = [];
  // A completed residual waits only while the smaller sibling is being read.
  function close(node) {
    const children = node.children.slice().sort((a, b) => subtreeSize[b.id] - subtreeSize[a.id]);
    for (const child of children) close(child);
    let size = 1;
    for (let i = 0; i < children.length; i++) size += residuals.pop();
    if (size >= threshold || node.id === 0) {
      cut.add(node.id);
      size = 0;
    }
    residuals.push(size);
    assert(residuals.length <= 1 + Math.floor(Math.log2(nodes.length)));
  }
  close(nodes[0]);
  assert.deepEqual(residuals, [0]);
  function visit(node, piece) {
    if (cut.has(node.id)) {
      if (piece) piece.children.push(node);
      piece = {root: node, nodes: [], children: []};
      pieces.push(piece);
    }
    owner.set(node.id, piece);
    piece.nodes.push(node);
    for (const child of node.children) visit(child, piece);
  }
  visit(nodes[0], null);
  assert(pieces.length <= 1 + nodes.length / threshold);
  assert(pieces.every(p => p.nodes.length <= 2 * threshold - 1));
  return {pieces, owner};
}

function checkReport(pattern, word, allowed, threshold) {
  const program = compile(pattern), N = word.length + 1, starts = positions(N);
  const nodes = program.regions.flat().sort((a, b) => a.id - b.id);
  const leaves = [], subtreeSize = [], guide = [], completed = new Map();
  const lambda = Math.ceil(Math.log2(N + 2));
  const explicit = size => lambda <= Math.ceil(Math.sqrt(size));
  for (const v of nodes.slice().reverse()) {
    subtreeSize[v.id] = 1 + v.children.reduce((total, c) => total + subtreeSize[c.id], 0);
    if (v.kind === 'character') leaves[v.id] = 1;
    else if (v.kind === 'assertion') leaves[v.id] = 0;
    else leaves[v.id] = v.children.reduce((sum, c) => sum + leaves[c.id], 0);
  }
  const bit = (v, key, x) => hasBit(guide[v.id][key], x);
  function full(v, x, moving) {
    if (!bit(v, 'full', x)) return null;
    return bit(v, 'still', x) ? x : moving.get(x);
  }

  function column(v, columns, size) {
    const raw = explicit(size);
    const [s, t] = v.children;
    const moving = child => columns.get(child.id).moving;
    let last = null;
    if (v.kind === 'repeat' && v.parts[1] !== '?') {
      const parent = moving(s);
      const stops = starts.map(x => v.parts[2] ? bit(v, 'stop', x) : parent.get(x) === null);
      const terminals = raw ? explicitTerminals(parent, stops) : terminalColumn(parent, stops, leaves[s.id]);
      last = x => {
        const y = parent.get(x);
        assert.notEqual(y, null);
        return stops[y] ? x : terminals.get(y);
      };
    }
    function step(x) {
      if (!bit(v, 'moving', x)) return null;
      switch (v.kind) {
        case 'character': return x + v.direction;
        case 'atomic': return full(s, x, moving(s));
        case 'capture': return moving(s).get(x);
        case 'choice': return moving(bit(s, 'moving', x) ? s : t).get(x);
        case 'sequence': {
          const [left, right] = factors(v);
          const y = bit(right, 'moving', x) ? full(left, x, moving(left)) : moving(left).get(x);
          return x === y ? moving(right).get(x) : full(right, y, moving(right));
        }
        case 'repeat': return moving(s).get(last ? last(x) : x);
        default: assert.fail('Unexpected moving result: ' + v.kind);
      }
    }
    const row = starts.map(step);
    assert(crossingWidth(row) <= leaves[v.id]);
    if (raw) counts.explicit++; else counts.coded++;
    return {moving: raw ? explicitColumn(row, v.direction) : encode(row, v.direction, leaves[v.id]), last};
  }

  // Each region has its own direction. Closed assertions read a bit and
  // closed atomic groups read an endpoint from the completed child region.
  for (let id = program.regions.length - 1; id >= 0; id--) {
    const layout = program.layouts[id], local = layout.nodes, direction = local[0].direction;
    const future = local.map(() => bitVector(N));
    let marks = new Uint8Array(layout.ports), previous = marks.slice();
    const progress = new Uint8Array(local.length), still = progress.slice();
    const ends = Array(local.length).fill(-1);
    for (const v of local) {
      guide[v.id] = Object.fromEntries(['full','moving','still','stop'].map(key => [key, bitVector(N)]));
    }
    function endpoint(v, x) {
      const child = v.children[0];
      if (v.kind === 'assertion') return bit(child, 'full', x) !== v.parts[2] ? x : -1;
      if (v.kind === 'atomic') return full(child, x, completed.get(child.id).moving) ?? -1;
      return primitiveExit(v, word, x);
    }
    const reverseLocal = local.slice().reverse();
    for (const i of starts) {
      const x = direction === 1 ? N - 1 - i : i;
      markLayer(layout, x, direction, id !== 0 || allowed[x], endpoint, future, previous,
                marks, ends, {vertices: 0, edges: 0});
      for (const v of layout.jumps) if (marks[2 * v.index + 1]) setBit(future[v.index], x);
      for (const v of reverseLocal) {
        const j = v.index, g = guide[v.id];
        progress[j] = movingAt(v, x, ends, marks, progress);
        still[j] = stationaryAt(v, x, ends, marks, progress, still);
        if (marks[2 * j]) setBit(g.full, x);
        if (marks[2 * j + 1]) setBit(g.stop, x);
        if (progress[j]) setBit(g.moving, x);
        if (still[j]) setBit(g.still, x);
      }
      [marks, previous] = [previous, marks];
    }
    for (const v of reverseLocal) {
      completed.set(v.id, column(v, completed, subtreeSize[v.id]));
      for (const child of v.children) completed.delete(child.id);
    }
    counts.regions++;
  }

  const reference = prepareMatches(program, word, allowed, true);
  for (const pieceSize of new Set([Math.ceil(Math.sqrt(program.size)), threshold])) {
    counts.partitions++;
    const {pieces, owner} = partition(nodes, subtreeSize, pieceSize);
    counts.pieces += pieces.length;
    const roots = new Map();
    function buildPiece(piece) {
      const local = new Map(piece.children.map(c => [c.id, {moving: roots.get(c.id)}]));
      for (const v of piece.nodes.slice().reverse()) local.set(v.id, column(v, local, program.size));
      return local;
    }
    for (const piece of pieces.slice().reverse()) {
      roots.set(piece.root.id, buildPiece(piece).get(piece.root.id).moving);
    }

    const spans = starts.map(() => Array(program.count).fill(null));
    const requests = new Map([[0, starts.map(x => bit(nodes[0], 'full', x) ? [x, false] : null)]]);
    for (const piece of pieces) {
      const local = buildPiece(piece);
      const next = new Map(piece.children.map(c => [c.id, Array(N).fill(null)]));
      const input = requests.get(piece.root.id);
      requests.delete(piece.root.id);
      for (const start of starts) {
        function visit(v, x, wantMoving) {
          if (owner.get(v.id) !== piece) {
            const pending = next.get(v.id);
            assert.equal(pending[start], null, 'A cut root receives at most one request per start');
            pending[start] = [x, wantMoving];
            return;
          }
          const [s, t] = v.children, cell = local.get(v.id);
          const y = wantMoving ? cell.moving.get(x) : full(v, x, cell.moving);
          assert.notEqual(y, null);
          switch (v.kind) {
            case 'capture':
              spans[start][v.slot] = [Math.min(x, y), Math.max(x, y)];
              visit(s, x, wantMoving);
              break;
            case 'choice': visit(bit(s, wantMoving ? 'moving' : 'full', x) ? s : t, x, wantMoving); break;
            case 'atomic': visit(s, x, false); break;
            case 'assertion': if (!v.parts[2]) visit(s, x, false); break;
            case 'sequence': {
              const [left, right] = factors(v);
              const leftMoving = wantMoving && !bit(right, 'moving', x);
              const lm = local.get(left.id).moving;
              const split = leftMoving ? lm.get(x) : full(left, x, lm);
              visit(left, x, leftMoving);
              visit(right, split, wantMoving && x === split);
              break;
            }
            case 'repeat':
              if (x !== y) visit(s, cell.last ? cell.last(x) : x, true);
              else if (v.parts[1] === '+') visit(s, x, false);
              break;
          }
        }
        if (input[start]) visit(piece.root, ...input[start]);
      }
      for (const child of piece.children) {
        const row = next.get(child.id);
        assert(crossingWidth(row, true) <= 2 * program.size ** 2);
        requests.set(child.id, explicit(program.size) ? row : encodeRequests(row, 2 * program.size ** 2));
      }
    }

    for (const x of starts) {
      const expected = Array(program.count).fill(null);
      const end = reference.report(x, (g, lo, hi) => { expected[g] = [lo, hi]; });
      assert.deepEqual([full(nodes[0], x, roots.get(0)), spans[x]], [end, expected]);
    }
  }
  counts.rows += N;
  counts.tests++;
}

const node = (kind, ...parts) => ({kind, parts});
const a = node('character', 'a'), b = node('character', 'b'), empty = node('empty');
const repeat = (body, kind, lazy) => node('repeat', body, kind, lazy);
const sequence = (s, t) => node('sequence', s, t), choice = (s, t) => node('choice', s, t);
const capture = s => node('capture', s), atomic = s => node('atomic', s);
const assertion = (s, d, negated) => node('assertion', s, d, negated);
let seed = 36771;
function random(limit) {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return Math.floor((seed / 4294967296) * limit);
}
function pattern(depth) {
  if (!depth) return [a, b, empty, node('end'), node('failure')][random(5)];
  switch (random(10)) {
    case 0: case 1: return sequence(pattern(depth - 1), pattern(depth - 1));
    case 2: case 3: return choice(pattern(depth - 1), pattern(depth - 1));
    case 4: return capture(pattern(depth - 1));
    case 5: return assertion(pattern(depth - 1), random(2) ? 1 : -1, Boolean(random(2)));
    case 6: return atomic(pattern(depth - 1));
    default: return repeat(pattern(depth - 1), ['?', '+', '*'][random(3)], Boolean(random(2)));
  }
}
const fixtures = [
  sequence(assertion(capture(repeat(a, '+', false)), 1, false), a),
  repeat(capture(repeat(choice(empty, capture(a)), '+', true)), '+', false),
  repeat(capture(sequence(atomic(repeat(choice(capture(a), b), '+', true)), repeat(a, '?', false))), '*', false),
  sequence(repeat(atomic(repeat(a, '+', false)), '*', false), assertion(capture(repeat(a, '+', true)), -1, false)),
  sequence(assertion(sequence(assertion(capture(repeat(a, '+', false)), -1, false),
                              atomic(repeat(capture(a), '*', true))), 1, false), choice(a, empty)),
];
for (const term of fixtures) {
  for (const word of ['', 'a', 'aa', 'ab', 'aaa', 'aba', 'aabaa']) {
    const N = word.length + 1;
    for (const mask of positions(1 << N)) checkReport(term, word, positions(N).map(x => (mask >> x) & 1), 2);
  }
}
for (let i = 0; i < 1300; i++) {
  const term = pattern(3 + random(4));
  const word = positions(4 + random(22)).map(() => random(3) ? 'a' : 'b').join('');
  checkReport(term, word, positions(word.length + 1).map(() => Number(random(3) !== 0)), 1 + random(6));
  counts.random++;
}
assert(counts.explicit > 0 && counts.coded > 0);
console.log(counts);

// All strict forward forests and all stopping sets containing their roots.
let forestCases = 0;
for (let n = 1; n <= 7; n++) {
  const row = Array(n), starts = positions(n);
  function choose(x) {
    if (x < n) {
      for (const y of [null, ...starts.slice(x + 1)]) { row[x] = y; choose(x + 1); }
      return;
    }
    const bound = crossingWidth(row), parent = encode(row, 1, bound);
    for (const y of starts) assert.deepEqual(parent.preimages(y).sort((a, b) => a - b),
                                             starts.filter(x => row[x] === y));
    const nonroots = starts.filter(x => row[x] !== null);
    for (const mask of positions(1 << nonroots.length)) {
      const stops = row.map(y => y === null);
      nonroots.forEach((v, j) => { if ((mask >> j) & 1) stops[v] = true; });
      terminalColumn(parent, stops, bound);
      forestCases++;
    }
  }
  choose(0);
}
console.log('Forest/stop-set instances:', forestCases);

// The stopping inequality is independent of positional order and allows cycles.
function partialMaps(length, forwardOnly) {
  const maps = [], row = Array(length), domain = positions(length);
  function visit(x) {
    if (x === length) { maps.push(row.slice()); return; }
    for (const value of [null, ...(forwardOnly ? domain.slice(x) : domain)]) {
      row[x] = value;
      visit(x + 1);
    }
  }
  visit(0);
  return maps;
}

function across(row, side) {
  const targets = new Set();
  row.forEach((y, x) => {
    if (y !== null && ((side >> x) & 1) !== ((side >> y) & 1)) targets.add(y);
  });
  return targets.size;
}

let hittingCases = 0, compositionCases = 0, directedCodeCases = 0;
for (let n = 1; n <= 4; n++) {
  const maps = partialMaps(n, false), subsets = positions(1 << n);
  for (const f of maps) {
    const bound = subsets.map(mask => across(f, mask));
    for (const stops of subsets) {
      const ends = Array(n).fill(null), last = Array(n).fill(null);
      for (const x of positions(n)) {
        let u = x;
        for (let step = 0; step < n; step++) {
          const y = f[u];
          if (y === null) break;
          if ((stops >> y) & 1) { ends[x] = y; last[x] = u; break; }
          u = y;
        }
      }
      for (const mask of subsets) {
        assert(across(ends, mask) <= bound[mask]);
        assert(across(last, mask) <= bound[mask]);
        hittingCases++;
      }
    }
    if (n <= 3) for (const g of maps) {
      const composite = f.map(y => y === null ? null : g[y]);
      for (const mask of subsets) {
        assert(across(composite, mask) <= bound[mask] + across(g, mask));
        compositionCases++;
      }
    }
  }
}
for (let n = 1; n <= 6; n++) {
  const indices = positions(n);
  for (const forward of partialMaps(n, true)) {
    for (const direction of [1, -1]) {
      const row = direction === 1 ? forward : forward.slice().reverse().map(y => y === null ? null : n - 1 - y);
      const code = encode(row, direction, crossingWidth(row));
      for (const y of indices) {
        assert.deepEqual(code.preimages(y).sort((a, b) => a - b), indices.filter(x => row[x] === y));
      }
      directedCodeCases++;
    }
  }
}
console.log({hittingCases, compositionCases, directedCodeCases});
