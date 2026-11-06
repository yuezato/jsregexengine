// The word-space index of Theorem 1.2, including sparse and dense readout.
import {factors, primitiveExit} from './pattern.mjs';
import {checkAllowed, movingAt, sweepRegion} from './layers.mjs';
export {compile} from './pattern.mjs';

const stop = end => ({end, trace: null});
function pair(first, second, direction) {
  if (!first || !second) return null;
  let trace = first.trace ?? second.trace;
  if (first.trace && second.trace) {
    trace = direction === 1 ? {left: first.trace, right: second.trace}
                            : {left: second.trace, right: first.trace};
  }
  return {end: second.end, trace};
}

function selectCell(v, x, ends, marks, tables) {
  const {full, moving, finish} = tables[v.id];
  const [left, right] = v.children;
  const s = left && tables[left.id];
  const canStop = marks[2 * v.index + 1];
  if (v.kind === 'sequence') {
    const [l, r] = factors(v);
    const lt = tables[l.id], rt = tables[r.id];
    const f = lt.full[x];
    if (f) full[x] = pair(f, rt.full[f.end], v.direction);
    // The right child at x is already solved, even when matching backwards.
    const m = rt.moving[x] ? f : lt.moving[x];
    if (m) moving[x] = pair(m, m.end === x ? rt.moving[x] : rt.full[m.end], v.direction);
  } else if (v.kind === 'choice') {
    const t = tables[right.id];
    full[x] = s.full[x] ?? t.full[x];
    moving[x] = s.moving[x] ?? t.moving[x];
  } else if (v.kind === 'capture') {
    const wrap = item => item && ({
      end: item.end,
      trace: {slot: v.slot, lo: Math.min(x, item.end), hi: Math.max(x, item.end), child: item.trace}
    });
    full[x] = wrap(s.full[x]);
    moving[x] = wrap(s.moving[x]);
  } else if (v.kind === 'repeat') {
    const [, q, lazy] = v.parts;
    const step = s.moving[x];
    if (q === '?') {
      const stay = canStop ? stop(x) : null;
      moving[x] = step;
      full[x] = lazy ? stay ?? step : step ?? stay;
      return;
    }
    function extend(body) {
      if (!body) return null;
      const tail = finish[body.end];
      return {end: tail.end, last: tail.last ?? body};
    }
    const result = tail => tail && ({end: tail.end, trace: tail.last?.trace ?? null});
    const moved = extend(step);
    // A stationary mandatory body can read finish[x] once the strict tail is set.
    finish[x] = canStop && (lazy || !step) ? {end: x, last: null} : moved;
    moving[x] = result(moved);
    full[x] = result(q === '*' ? finish[x] : extend(s.full[x]));
  } else if (marks[2 * v.index]) {
    const y = ends[v.index];
    const exportChild = v.kind === 'atomic' || (v.kind === 'assertion' && !v.parts[2]);
    full[x] = exportChild ? {end: y, trace: s.full[x].trace} : stop(y);
    if (y !== x) moving[x] = full[x];
  }
}

// Every child region is complete when its enclosing assertion or atomic group runs.
export function prepareMatches(program, word, allowed = null, verify = false) {
  const N = word.length + 1;
  checkAllowed(allowed, N);
  const tables = new Array(program.size);
  const stats = {vertices: 0, edges: 0, cells: 0, traceVisits: 0, outputSlots: 0};
  for (let i = program.layouts.length - 1; i >= 0; i--) {
    const layout = program.layouts[i];
    const {nodes} = layout;
    for (const v of nodes) {
      const finish = v.kind === 'repeat' && v.parts[1] !== '?' ? new Array(N) : null;
      tables[v.id] = {full: new Array(N).fill(null), moving: new Array(N).fill(null), finish};
    }
    function atomEnd(v, x) {
      if (v.kind === 'assertion') {
        const succeeds = Boolean(tables[v.children[0].id].full[x]);
        return succeeds !== Boolean(v.parts[2]) ? x : -1;
      }
      if (v.kind === 'atomic') return tables[v.children[0].id].full[x]?.end ?? -1;
      return primitiveExit(v, word, x);
    }
    // The literal-list checks can independently verify both presence bits.
    const progress = verify ? new Uint8Array(nodes.length) : null;
    sweepRegion(layout, N, i === 0 ? allowed : null, atomEnd, (x, marks, ends) => {
      for (let k = nodes.length - 1; k >= 0; k--) {
        const v = nodes[k];
        selectCell(v, x, ends, marks, tables);
        if (verify) {
          progress[k] = movingAt(v, x, ends, marks, progress);
          if (Boolean(tables[v.id].full[x]) !== Boolean(marks[2 * k]) ||
              Boolean(tables[v.id].moving[x]) !== Boolean(progress[k])) {
            throw new Error('Viability and selected item disagree at ' + [v.id, x]);
          }
        }
      }
    }, stats);
    stats.cells += 2 * nodes.length * N;
  }
  const entries = tables[program.regions[0][0].id].full;
  function endpoint(x) { return entries[x]?.end ?? null; }
  function report(x, emit) {
    const item = entries[x];
    if (!item) return null;
    const pending = item.trace ? [item.trace] : [];
    while (pending.length) {
      const t = pending.pop();
      stats.traceVisits++;
      if (t.slot !== undefined) {
        emit(t.slot, t.lo, t.hi);
        if (t.child) pending.push(t.child);
      } else {
        pending.push(t.right, t.left);
      }
    }
    return item.end;
  }
  return {endpoint, report, stats};
}

export function matchAllStarts(program, word, allowed = null, verify = false) {
  const index = prepareMatches(program, word, allowed, verify);
  const rows = Array.from({length: word.length + 1}, (_, x) => {
    const end = index.endpoint(x);
    if (end === null) return null;
    const spans = new Array(program.count).fill(null);
    index.stats.outputSlots += spans.length;
    index.report(x, (slot, lo, hi) => { spans[slot] = [lo, hi]; });
    return [end, spans];
  });
  return {rows, stats: index.stats};
}
