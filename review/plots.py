"""Render the reviewer report from saved measurements, without rerunning timings."""
import argparse
from html import escape
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator, ScalarFormatter

COLORS = {'index': '#1268b3', 'v8': '#d06023', 'v8-linear': '#25835a'}
LABELS = {'index': 'Our word index', 'v8': 'V8 default', 'v8-linear': 'V8 experimental linear'}


def completed(rows):
    """Censored or unmeasured runs have no plotted completion time."""
    return sorted((row for row in rows if row['status'] == 'ok'), key=lambda row: row['N'])


def style(ax, title, xlabel, ylabel, logx=True):
    ax.set_title(title, loc='left', weight='bold', pad=13)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if logx:
        ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.grid(True, which='major', color='#dbe2e8', linewidth=.7)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_locator(NullLocator())


def product_panel(ax, data, normalized=False):
    rows = [row for row in data['measurements'] if row['suite'] == 'product']
    depths = sorted({row['depth'] for row in rows})
    palette = plt.get_cmap('viridis')
    for i, depth in enumerate(depths):
        group = completed([row for row in rows if row['depth'] == depth])
        color = palette(.15 + .65 * i / max(1, len(depths)-1))
        if group:
            ax.plot([row['N'] for row in group],
                [row['median_ms'] * 1000 / row['mN'] if normalized else row['median_ms'] for row in group],
                'o-', color=color,
                markersize=4, linewidth=1.6, label=f"m = {group[0]['m']}")
        for row in rows:
            if row['depth'] == depth and row['status'] == 'timeout':
                height = row['timeout_ms'] * 1000 / row['mN'] if normalized else row['timeout_ms']
                ax.scatter([row['N']], [height], marker='^', facecolors='none', edgecolors=color, s=65)
                ax.annotate('call limit', (row['N'], height), xytext=(0, 7),
                            textcoords='offset points', fontsize=8, ha='center')
    style(ax, 'B  Time per pattern-position pair' if normalized else 'A  Vary m and N independently',
          'Text positions N = n + 1', 'Time / (mN), µs' if normalized else 'Index construction, ms')
    ax.set_xticks([n + 1 for n in data['config']['lengths']])
    ax.legend(fontsize=8, frameon=False, ncol=2)


def comparison_panel(ax, data, suite):
    rows = [row for row in data['measurements'] if row['suite'] == suite]
    has_timeout = False
    for engine in LABELS:
        selected = [row for row in rows if row['engine'] == engine]
        group = completed(selected)
        if group:
            ax.plot([row['n'] for row in group], [row['median_ms'] for row in group],
                    'o-', color=COLORS[engine], label=LABELS[engine], linewidth=1.7, markersize=4)
        for row in selected:
            if row['status'] == 'timeout':
                has_timeout = True
                ax.scatter([row['n']], [row['timeout_ms']], marker='^', facecolors='none',
                           edgecolors=COLORS[engine], s=65, linewidths=1.6, zorder=4)
                ax.annotate(f"limit {row['timeout_ms']/1000:g} s\n({row['phase']})", (row['n'], row['timeout_ms']),
                            xytext=(0, 7), textcoords='offset points', ha='center',
                            color=COLORS[engine], fontsize=8)
    if suite == 'global':
        style(ax, 'C  Enumerate all matches: .*a|b on bⁿ', 'Text length n', 'Index + scan / matchAll, ms')
        ax.set_xticks(data['config']['global_lengths'])
    else:
        style(ax, 'D  One search: (((a?)+?)+?)+?b on aⁿ', 'Text length n',
              'Index + search / exec, ms', logx=False)
        ax.set_xticks(data['config']['backtracking_lengths'])
    handles, labels = ax.get_legend_handles_labels()
    if has_timeout:
        handles.append(Line2D([], [], color='#495564', marker='^', markerfacecolor='none', linestyle='none'))
        labels.append('Call stopped at limit; no completion time')
    ax.legend(handles, labels, fontsize=8, frameon=False, loc='best')
    ax.margins(y=.2)


def save(fig, output, name):
    fig.savefig(output / (name + '.svg'), bbox_inches='tight', metadata={'Date': None})
    fig.savefig(output / (name + '.png'), bbox_inches='tight', dpi=160)
    plt.close(fig)


def table(headers, rows):
    return '<table><thead><tr>' + ''.join('<th>' + escape(str(x)) + '</th>' for x in headers) + \
        '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(str(x)) + '</td>' for x in row) +
                                       '</tr>' for row in rows) + '</tbody></table>'


def render(data, output):
    if data.get('schema_version') != 1 or not data.get('complete'):
        raise ValueError('Expected a completed reviewer-demo data.json (schema 1).')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11,
                         'svg.fonttype': 'none', 'svg.hashsalt': 'jsregex-reviewer', 'figure.facecolor': 'white'})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.7), layout='constrained')
    product_panel(axes[0, 0], data)
    product_panel(axes[0, 1], data, normalized=True)
    comparison_panel(axes[1, 0], data, 'global')
    comparison_panel(axes[1, 1], data, 'backtracking')
    fig.suptitle('From a prepared pattern to match results', fontsize=16, weight='bold')
    save(fig, output, 'overview')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), layout='constrained')
    product_panel(axes[0], data)
    product_panel(axes[1], data, normalized=True)
    save(fig, output, 'product-scaling')
    for suite, name in [('global', 'all-matches'), ('backtracking', 'backtracking')]:
        fig, ax = plt.subplots(figsize=(8, 4.8), layout='constrained')
        comparison_panel(ax, data, suite)
        save(fig, output, name)
    env, config = data['environment'], data['config']
    work_rows = []
    for family in dict.fromkeys(row['family'] for row in data['work']):
        group = [row for row in data['work'] if row['family'] == family]
        work_rows.append([family, len(group),
                          f"{max(row['selectCalls']/row['mN'] for row in group):.3f}",
                          f"{max(row['pops']/row['mN'] for row in group):.3f}",
                          f"{max(row['predecessors']/row['mN'] for row in group):.3f}"])
    counts = table(['Family', 'Cases', 'max selections / mN', 'max pops / mN', 'max edge scans / mN'], work_rows)
    admission = table(['Nested lazy-plus depth', 'V8 experimental linear'],
                      [(row['depth'], row['status']) for row in data['admission']])
    exceptional = [row for row in data['measurements'] if row['status'] not in ('ok', 'not-run')]
    exceptions = table(['Experiment', 'Engine', 'n', 'Status', 'Phase / reason'],
        [(row['suite'], LABELS[row['engine']], row['n'], row['status'],
          row.get('phase', row.get('reason', ''))) for row in exceptional])
    svg = (output / 'overview.svg').read_text()
    svg = svg[svg.index('<svg'):]
    metadata = table(['Item', 'Value'], [
        ('Measured (UTC)', data['generated_utc']), ('Node / V8', env['node'] + ' / ' + env['v8']),
        ('Python / matplotlib', env['python'] + ' / ' + env.get('matplotlib', 'unknown')),
        ('Platform / CPU', env['system'] + ' / ' + env['cpu']), ('Node flags', ' '.join(env['flags'])),
        ('Profile', config['profile']), ('Warmups / measured repetitions', f"{config['warmups']} / {config['repeats']}"),
        ('Limit for one prepared call', f"{config['timeout_ms']} ms"), ('Source base commit', env.get('base_commit'))])
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JSRegex: reviewer reproduction</title>
<style>body{max-width:1150px;margin:40px auto;padding:0 24px;color:#202a36;font:16px/1.6 system-ui,sans-serif}
h1,h2{line-height:1.2}h2{margin-top:2em}a{color:#1268b3}code{background:#f0f3f6;padding:2px 4px}
svg{width:100%;height:auto}table{border-collapse:collapse;font-size:14px;width:100%;margin:18px 0}
th,td{text-align:left;border-bottom:1px solid #dbe2e8;padding:8px;vertical-align:top}th{background:#f0f3f6}
.note{border-left:4px solid #1268b3;padding:8px 18px;background:#f4f8fc}li{margin:8px 0}</style>
<h1>JSRegex: measured behavior and counted work</h1>
<p>This report checks match results, varies both input dimensions, and compares identical
matching tasks with two V8 engines. All plots are generated from the raw samples beside this file.</p>
<p class="note"><strong>The product bound comes from the algorithm and its proof.</strong>
The plots illustrate finite runs. Independent operation counts below check the implementation
of the bounded loops; elapsed-time curves alone do not establish an asymptotic bound.</p>
''' + svg + '''
<h2>What each panel computes</h2>
<ul><li><strong>A–B: product scaling.</strong> Start with <code>a?</code>, wrap it in
<code>(…)+?</code> d times. On <code>a</code> repeated n times,
the selected end at x is min(x + 1, n), with d nested captures. The original tree has
m = 2 + 2d occurrences and the text has N = n + 1 positions.
Both m and N vary independently. Only construction of our all-start word index is timed;
every root endpoint is checked afterwards. B divides time by mN; JIT, allocation, garbage
collection and fixed costs can make the ratio fluctuate.</li>
<li><strong>C: all global matches.</strong> <code>.*a|b</code> on n copies of <code>b</code>
returns n one-character intervals. We time our index construction plus scan, or V8's complete
<code>matchAll</code> traversal and collection of the same intervals. All returned intervals
are checked. Repeated searches can revisit long suffixes even when one search uses a linear engine.</li>
<li><strong>D: one unanchored search.</strong> <code>(((a?)+?)+?)+?b</code> on n copies of
<code>a</code> must fail. We time our index construction plus first-match scan, or one V8
<code>exec</code>. The experimental linear engine handles this depth on the recorded version;
the default backtracking engine can reach the call limit. The index prepares all starts even though
this client asks for only one result.</li></ul>
<p>Triangles mark a call stopped at its time limit, not a completed measurement. The data record
whether it stopped in warmup or measurement. Larger inputs for that engine and experiment are
then marked <code>not-run</code>. A rejected pattern is <code>unsupported</code>, never a zero time.
These deliberately demanding families are not a survey of typical production throughput.</p>
<h2>Executed work, independently counted</h2>
<p>All 63 instances passed. Node precise coverage counts actual <code>selectCell</code> calls;
instrumented predecessor lists count actual pops and edge inspections. For every case the
assertions require selections = mN, pops ≤ 2mN, and edge scans ≤ 4mN. Every endpoint and
ordered sparse capture result is checked. A query emitting k captures visits no record for k = 0,
and at most 2k − 1 records otherwise. This instrumentation is outside the timing runs.</p>
''' + counts + '''
<h2>Scope of the experimental V8 engine</h2>
<p>This separate compile-only probe applies the <code>l</code> flag to the same family over
<code>a?</code> at depths 1–10. “Accepted” describes construction of that regex on this runtime,
not a complexity proof or a timed search. Admission can change between V8 versions.</p>
''' + admission + '<h2>Interrupted or rejected measured cases</h2>' + exceptions + '''
<h2>Measurement boundary and environment</h2>
<p>Pattern source/tree construction, our tree preparation, the native RegExp constructor, input
construction, process startup and result validation are outside the clock. V8 may lazily compile
or tier its matcher during a call; the same number of warmups and repetitions is used for each
engine. Each sample calls <code>gc()</code> before starting the clock; allocations and collection
during matching are included. Processes run serially. Inherited <code>NODE_OPTIONS</code> are
removed. Enabling the experimental engine does not enable fallback for the default engine.</p>
<p>A VM time limit surrounds each prepared call, with both timestamps inside it. If setup or the
worker itself fails to return, the driver fails rather than recording that as a matching timeout.</p>
''' + metadata + '''
<h2>Files and reproduction</h2>
<p>Run <code>python3 reproduce.py demo</code> from the repository root. Use
<code>--profile full</code> for a larger grid or <code>--timeout-ms 5000</code> to raise the call limit.</p>
<p><a href="data.json">All raw samples, versions and source fingerprints (JSON)</a> ·
<a href="measurements.csv">Timing summaries (CSV)</a> · <a href="work.csv">Work counts (CSV)</a> ·
<a href="work.txt">Assertion log</a> · <a href="admission.csv">Admission probe (CSV)</a></p>
<p>Standalone figures: <a href="overview.svg">overview SVG</a> / <a href="overview.png">PNG</a>;
<a href="product-scaling.svg">product scaling</a>; <a href="all-matches.svg">all matches</a>;
<a href="backtracking.svg">one search</a>. No web connection is needed to open this report.</p>
</html>'''
    (output / 'index.html').write_text(html)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    args = parser.parse_args()
    render(json.loads(args.data.read_text()), args.data.parent)
