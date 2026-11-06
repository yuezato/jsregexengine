import {factors} from './pattern.mjs';

export const bitVector = N => new Uint8Array(Math.ceil(N / 8));
export const hasBit = (bits, x) => Boolean(bits[Math.floor(x / 8)] & (1 << (x % 8)));
export function setBit(bits, x) { bits[Math.floor(x / 8)] |= 1 << (x % 8); }

export function movingAt(v, x, ends, marks, progress) {
  const [s, t] = v.children;
  switch (v.kind) {
    case 'sequence': {
      const [l, r] = factors(v);
      return progress[l.index] || (marks[2 * l.index] && progress[r.index]);
    }
    case 'choice': return progress[s.index] || progress[t.index];
    case 'capture': case 'repeat': return progress[s.index];
    default: return marks[2 * v.index] && ends[v.index] !== x;
  }
}

// Close ordinary directed reachability inside one position layer.
export function markLayer(layout, x, direction, rootAllowed, endpoint, future, previous, marks, ends, stats) {
  marks.fill(0);
  const todo = [];
  function mark(p) {
    if (marks[p]) return;
    marks[p] = 1;
    todo.push(p);
  }
  if (rootAllowed) mark(1);
  stats.vertices += layout.ports;
  stats.edges += layout.edges;
  for (const v of layout.atoms) {
    const y = ends[v.index] = endpoint(v, x);
    if (y < 0) continue;
    stats.edges++;
    const a = 2 * v.index;
    if (y !== x && (y === x + direction ? previous[a + 1] : hasBit(future[v.index], y))) mark(a);
  }
  while (todo.length) {
    const p = todo.pop();
    for (const u of layout.pred[p]) mark(u);
    // For non-atoms ends remains -1. Only an active stationary atom has this edge.
    if (p % 2 === 1 && ends[(p - 1) / 2] === x) mark(p - 1);
  }
}

// Read one position layer at a time. Only an atomic jump can ask for an
// exit mark farther away than the previous layer in matching order.
export function sweepRegion(layout, N, allowed, endpoint, visit, stats) {
  const {nodes, ports, jumps} = layout;
  const direction = nodes[0].direction;
  const future = new Array(nodes.length);
  for (const v of jumps) future[v.index] = bitVector(N);
  let marks = new Uint8Array(ports);
  let previous = new Uint8Array(ports);
  const ends = new Array(nodes.length).fill(-1);
  for (let step = 0; step < N; step++) {
    const x = direction === 1 ? N - 1 - step : step;
    markLayer(layout, x, direction, !allowed || allowed[x], endpoint, future, previous, marks, ends, stats);
    for (const v of jumps) {
      if (marks[2 * v.index + 1]) setBit(future[v.index], x);
    }
    visit(x, marks, ends);
    [previous, marks] = [marks, previous];
  }
}

export function checkAllowed(allowed, N) {
  if (allowed && allowed.length !== N) throw new Error('Expected one membership bit per position');
}
