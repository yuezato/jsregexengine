// Input is an occurrence tree in the syntax of reference_semantics.mjs.
// Positions index units in a string (UTF-16) or an array (e.g. code points).
export function compile(pattern) {
  const regions = [[]], repeatBodyCounts = [0];
  const stack = [{term: pattern, region: 0, direction: 1}];
  let count = 0;
  let size = 0;
  while (stack.length) {
    const {term, region, direction, parent, index, insideLoop = false} = stack.pop();
    const {kind, parts} = term;
    const nodes = regions[region];
    const v = {
      kind, parts, direction, region, id: size, index: nodes.length, children: []
    };
    nodes.push(v);
    size++;
    if (insideLoop) repeatBodyCounts[region]++;
    if (parent) parent.children[index] = v;
    if (kind === 'capture') v.slot = count++;
    const closed = kind === 'atomic' || kind === 'assertion';
    const childRegion = closed ? regions.push([]) - 1 : region;
    if (closed) repeatBodyCounts.push(0);
    const loopBody = !closed && (insideLoop || (kind === 'repeat' && parts[1] !== '?'));
    const childDirection = kind === 'assertion' ? parts[1] : direction;
    // Source order gives capture numbering even inside a lookbehind.
    for (let i = parts.length - 1; i >= 0; i--) {
      if (parts[i]?.kind) {
        stack.push({
          term: parts[i], region: childRegion, direction: childDirection,
          parent: v, index: i, insideLoop: loopBody
        });
      }
    }
  }
  const layouts = regions.map(makeLayout);
  // The appendix walk also uses these capture and repetition annotations.
  const mayExport = new Uint8Array(size);
  for (let r = regions.length - 1; r >= 0; r--) {
    const nodes = regions[r];
    for (let i = nodes.length - 1; i >= 0; i--) {
      const v = nodes[i], negative = v.kind === 'assertion' && v.parts[2];
      mayExport[v.id] = v.kind === 'capture' || (!negative && v.children.some(c => mayExport[c.id]));
    }
  }
  const noAtomic = layouts.every(layout => !layout.jumps.length);
  const localCaptures = noAtomic &&
    regions[0].every(v => v.kind !== 'assertion' || !mayExport[v.id]);
  return {regions, layouts, count, size, noAtomic, localCaptures, mayExport, repeatBodyCounts};
}

export function primitiveExit(v, word, x) {
  const arg = v.parts[0];
  switch (v.kind) {
    case 'failure': return -1;
    case 'empty': return x;
    case 'end': return x === word.length ? x : -1;
    case 'position': return arg(word, x, v.direction) ? x : -1;
    case 'character': {
      const i = v.direction === 1 ? x : x - 1;
      if (i < 0 || i >= word.length) return -1;
      const unit = word.unitAt ? word.unitAt(i) : word[i];
      const matches = typeof arg === 'function' ? arg(unit) : unit === arg;
      return matches ? x + v.direction : -1;
    }
    default: throw new Error('Unknown primitive: ' + v.kind);
  }
}

export function factors(v) {
  const [s, t] = v.children;
  return v.direction === 1 ? [s, t] : [t, s];
}

// The structural edges are the same at every position. An atom adds one
// conditional edge starting at its entrance port.
function makeLayout(nodes) {
  const ports = 2 * nodes.length;
  const pred = Array.from({length: ports}, () => []);
  const atoms = [], jumps = [];
  let edges = 0;
  function link(u, v) {
    pred[v].push(u);
    edges++;
  }
  for (const v of nodes) {
    const a = 2 * v.index, b = a + 1;
    const [s, t] = v.children;
    switch (v.kind) {
      case 'choice':
        for (const child of [s, t]) {
          link(a, 2 * child.index);
          link(2 * child.index + 1, b);
        }
        break;
      case 'sequence': {
        const [l, r] = factors(v);
        link(a, 2 * l.index);
        link(2 * l.index + 1, 2 * r.index);
        link(2 * r.index + 1, b);
        break;
      }
      case 'capture': case 'repeat':
        link(a, 2 * s.index);
        link(2 * s.index + 1, b);
        if (v.kind === 'repeat' && v.parts[1] !== '+') link(a, b);
        if (v.kind === 'repeat' && v.parts[1] !== '?') link(2 * s.index + 1, 2 * s.index);
        break;
      default:
        atoms.push(v);
        if (v.kind === 'atomic') jumps.push(v);
    }
  }
  return {nodes, ports, pred, atoms, jumps, edges};
}
