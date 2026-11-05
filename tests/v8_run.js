// Reads JSON lines {pat, word, flags, sticky} on stdin and prints one JSON line each.
// Without sticky: [exec, matchAll], the leftmost match and all matches of `word`.
// With sticky = x: the match of the sticky regex at lastIndex x, i.e. anchored at x.
// A match is [start, end, span or null for each group]; a rejected pattern prints {error}.
const lines = require('fs').readFileSync(0, 'utf8').split('\n').filter(Boolean);
const span = m => [m.index, m.index + m[0].length, ...m.indices.slice(1).map(v => v ? [v[0], v[1]] : null)];
for (const line of lines) {
  const { pat, word, flags = '', sticky } = JSON.parse(line);
  try {
    if (sticky !== undefined) {
      const r = new RegExp(pat, flags + 'dy');
      r.lastIndex = sticky;
      const m = r.exec(word);
      console.log(JSON.stringify(m ? span(m) : null));
    } else {
      const e = new RegExp(pat, flags + 'd').exec(word);
      const all = [...word.matchAll(new RegExp(pat, flags + 'gd'))].map(span);
      console.log(JSON.stringify([e ? span(e) : null, all]));
    }
  } catch (err) {
    console.log(JSON.stringify({ error: String(err) }));
  }
}
