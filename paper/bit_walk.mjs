// Boolean viability and the single-start walk of Appendix C.
import {factors, primitiveExit} from './index/pattern.mjs';
import {bitVector, checkAllowed, hasBit, movingAt, setBit, sweepRegion} from './index/layers.mjs';

// Is the first full result present and stationary? The bit-space walk and
// the offline reporter both use this decision to recover a full result.
export function stationaryAt(v, x, ends, marks, progress, still) {
  const [s, t] = v.children;
  switch (v.kind) {
    case 'sequence': return still[s.index] && still[t.index];
    case 'choice': return marks[2 * s.index] ? still[s.index] : still[t.index];
    case 'capture': return still[s.index];
    case 'repeat':
      return marks[2 * v.index + 1] && (v.parts[2] || !progress[s.index]) &&
        (v.parts[1] !== '+' || still[s.index]);
    default: return marks[2 * v.index] && ends[v.index] === x;
  }
}

function evaluateBits(program, word, allowed, makeGuide) {
  const N = word.length + 1;
  checkAllowed(allowed, N);
  const roots = new Array(program.regions.length);
  const guide = makeGuide ? program.regions.map(nodes => nodes.map(() => ({
    full: bitVector(N), moving: bitVector(N), still: bitVector(N), stop: bitVector(N)
  }))) : null;
  const stats = {vertices: 0, edges: 0};
  for (let i = program.layouts.length - 1; i >= 0; i--) {
    const layout = program.layouts[i];
    const {nodes} = layout;
    if (layout.jumps.length) throw new Error('Atomic groups need the locally selected endpoint');
    const success = bitVector(N), rootMoving = bitVector(N);
    roots[i] = {success, moving: rootMoving};
    const progress = new Uint8Array(nodes.length);
    const columns = guide?.[i];
    const still = columns ? new Uint8Array(nodes.length) : null;
    function atomEnd(v, x) {
      if (v.kind === 'assertion') {
        const succeeds = hasBit(roots[v.children[0].region].success, x);
        return succeeds !== Boolean(v.parts[2]) ? x : -1;
      }
      return primitiveExit(v, word, x);
    }
    sweepRegion(layout, N, i === 0 ? allowed : null, atomEnd, (x, marks, ends) => {
      for (let k = nodes.length - 1; k >= 0; k--) {
        const v = nodes[k];
        progress[k] = movingAt(v, x, ends, marks, progress);
        if (still) {
          still[k] = stationaryAt(v, x, ends, marks, progress, still);
          if (marks[2 * k]) setBit(columns[k].full, x);
          if (progress[k]) setBit(columns[k].moving, x);
          if (still[k]) setBit(columns[k].still, x);
          if (marks[2 * k + 1]) setBit(columns[k].stop, x);
        }
      }
      if (marks[0]) setBit(success, x);
      if (progress[0]) setBit(rootMoving, x);
    }, stats);
  }
  return {rootBits: roots[0], guide};
}

// Packed success and progress bits for every start, including nested assertions.
export function viableStarts(program, word, allowed = null) {
  return evaluateBits(program, word, allowed, false).rootBits;
}

// Store decisions for each region. The cursor reconstructs only the last
// surviving call of a positive assertion that can export captures.
export function prepareWalk(program, word, allowed = null) {
  if (!program.noAtomic) throw new Error('The packed matcher requires unit consuming edges');
  const prepared = evaluateBits(program, word, allowed, true);
  function read(x) {
    if (!hasBit(prepared.rootBits.success, x)) return null;
    const spans = new Array(program.count).fill(null);
    const pending = [{region: 0, start: x}];
    let end = x, visits = 0, visitBound = 0;
    while (pending.length) {
      const {region, start} = pending.pop();
      const nodes = program.regions[region], guide = prepared.guide[region];
      const written = new Array(nodes.length).fill(0);
      const reset = new Array(nodes.length).fill(0);
      const assertionStart = new Array(nodes.length);
      let cursor = start, clock = 0;
      const todo = [{v: nodes[0], phase: 'enter', moving: false}];
      function enter(v, moving) { todo.push({v, phase: 'enter', moving}); }
      while (todo.length) {
        const {v, phase, moving, origin} = todo.pop();
        const [s, t] = v.children;
        if (phase === 'close') {
          spans[v.slot] = [Math.min(origin, cursor), Math.max(origin, cursor)];
          written[v.index] = ++clock;
          continue;
        }
        if (phase === 'right') {
          enter(factors(v)[1], moving && cursor === origin);
          continue;
        }
        if (phase === 'tail') {
          if (hasBit(guide[v.index].stop, cursor) && (v.parts[2] || !hasBit(guide[s.index].moving, cursor))) continue;
          reset[v.index] = ++clock;
          todo.push({v, phase: 'tail'});
          enter(s, true);
          continue;
        }
        visits++;
        switch (v.kind) {
          case 'character': cursor += v.direction; break;
          case 'empty': case 'end': case 'position': break;
          case 'assertion':
            if (program.mayExport[v.id]) {
              assertionStart[v.index] = cursor;
              written[v.index] = ++clock;
            }
            break;
          case 'capture':
            todo.push({v, phase: 'close', origin: cursor});
            enter(s, moving);
            break;
          case 'choice':
            enter(hasBit(moving ? guide[s.index].moving : guide[s.index].full, cursor) ? s : t, moving);
            break;
          case 'sequence': {
            const [l, r] = factors(v);
            todo.push({v, phase: 'right', moving, origin: cursor});
            enter(l, moving && !hasBit(guide[r.index].moving, cursor));
            break;
          }
          case 'repeat':
            reset[v.index] = ++clock;
            if (!moving && hasBit(guide[v.index].still, cursor)) {
              if (v.parts[1] === '+') enter(s, false);
            } else {
              if (v.parts[1] !== '?') todo.push({v, phase: 'tail'});
              enter(s, true);
            }
            break;
          default: throw new Error('Unexpected occurrence on a viable walk: ' + v.kind);
        }
      }
      const width = Math.abs(cursor - start);
      visitBound += nodes.length + program.repeatBodyCounts[region] * Math.max(0, width - 1);
      if (region === 0) end = cursor;
      const syntax = [[nodes[0], 0]];
      while (syntax.length) {
        const [v, parentReset] = syntax.pop();
        const barrier = Math.max(parentReset, reset[v.index]);
        const live = written[v.index] > barrier;
        if (v.kind === 'capture' && !live) spans[v.slot] = null;
        if (v.kind === 'assertion') {
          if (live) pending.push({region: v.children[0].region, start: assertionStart[v.index]});
        } else {
          for (const child of v.children) syntax.push([child, barrier]);
        }
      }
    }
    return {row: [end, spans], visits, visitBound};
  }
  return {success: prepared.rootBits.success, read};
}
