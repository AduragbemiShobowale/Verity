"""Chapter Four Part B figures as standalone SVG and HTML pages, each with its data as CSV, from metrics_final.json.
render_final.mjs screenshots the HTML pages to PNG. Standard library only.

Palette as in docs/chapter4/charts.py (validated with the dataviz validator, light mode): series blue #2a78d6,
series orange #eb6834; status good #0ca30c, warning #fab219, critical #d03b3b, always paired with a text label.
"""
import csv
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
m = json.loads((HERE / 'metrics_final.json').read_text())
R1 = m['replicates']['1']

INK, INK2, MUTED, GRID, BASE, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb'
BLUE, ORANGE = '#2a78d6', '#eb6834'
GOOD, WARN, CRIT = '#0ca30c', '#fab219', '#d03b3b'
GREY = '#9a9890'
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"


def page(name, width, height, title, subtitle, body, legend=''):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">
<rect width="{width}" height="{height}" fill="{SURF}"/>
<text x="32" y="44" font-size="22" font-weight="650" fill="{INK}">{escape(title)}</text>
<text x="32" y="72" font-size="15" fill="{INK2}">{escape(subtitle)}</text>
{legend}
{body}
</svg>'''
    (OUT / f'{name}.svg').write_text(svg)
    (OUT / f'{name}.html').write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:{SURF}}}</style>{svg}')


def data(name, header, rows):
    with open(OUT / f'{name}_data.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def legend(items, x, y):
    out, cx = [], x
    for color, label in items:
        out.append(f'<rect x="{cx}" y="{y - 11}" width="14" height="14" rx="3" fill="{color}"/>'
                   f'<text x="{cx + 20}" y="{y + 1}" font-size="14" fill="{INK2}">{escape(label)}</text>')
        cx += 30 + len(label) * 7.6
    return ''.join(out)


def hbar(x, y, w, h, color):
    if w <= 0:
        return ''
    r = min(4, w / 2, h / 2)
    return f'<path d="M{x},{y} h{w - r} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{w - r} z" fill="{color}"/>'


def xaxis(left, plot, y0, y1, ticks, fmt=lambda t: f'{t}%'):
    out = []
    for t in ticks:
        x = left + plot * t / ticks[-1]
        out.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{GRID}"/>'
                   f'<text x="{x}" y="{y1 + 20}" font-size="13" fill="{MUTED}" text-anchor="middle">{fmt(t)}</text>')
    return ''.join(out)


# ---------------------------------------------------------------- Figure 4.1 outcomes by group
def fig_outcomes():
    names = {'clean': 'Clean orders', 'rule_targeted': 'Errors with a rule', 'no_rule': 'Errors without a rule'}
    groups = R1['outcomes_by_group']
    W, left, right, top, bh, gap = 1200, 250, 40, 130, 56, 30
    plot = W - left - right
    body, rows = [], []
    for i, (g, d) in enumerate(groups.items()):
        n = sum(d.values())
        y = top + i * (bh + gap)
        body.append(f'<text x="{left - 14}" y="{y + bh / 2 - 4}" font-size="15" font-weight="600" fill="{INK}" text-anchor="end">{names[g]}</text>'
                    f'<text x="{left - 14}" y="{y + bh / 2 + 16}" font-size="13" fill="{MUTED}" text-anchor="end">{n} orders</text>')
        x = left
        segs = [s for s in [('pass', GOOD), ('warn', WARN), ('fail', CRIT)] if d.get(s[0], 0)]
        for j, (k, color) in enumerate(segs):
            v = d[k]
            w = plot * v / n
            last = j == len(segs) - 1
            body.append(hbar(x, y, w, bh, color) if last else f'<rect x="{x}" y="{y}" width="{w - 2}" height="{bh}" fill="{color}"/>')
            tc = INK if k == 'warn' else '#ffffff'
            if w > 70:
                body.append(f'<text x="{x + w / 2}" y="{y + bh / 2 + 6}" font-size="15" font-weight="650" fill="{tc}" text-anchor="middle">{v} ({round(100 * v / n)}%)</text>')
            else:
                body.append(f'<text x="{x + w / 2}" y="{y - 6}" font-size="13" fill="{INK2}" text-anchor="middle">{v}</text>')
            x += w
        rows.append([names[g], n, d.get('pass', 0), d.get('warn', 0), d.get('fail', 0)])
    H = top + 3 * (bh + gap) + 20
    page('fig4_2_outcomes', W, H, 'What happened to each group of orders, replicate 1',
         'Share of 500 simulated orders passed, warned or blocked at submission',
         ''.join(body), legend([(GOOD, 'Passed'), (WARN, 'Warned, sent to a person'), (CRIT, 'Blocked, customer must fix')], 32, 104))
    data('fig4_2_outcomes', ['group', 'orders', 'passed', 'warned', 'blocked'], rows)


# ---------------------------------------------------------------- Figure 4.2 detection by type with Wilson intervals
def fig_detection():
    types = [t for t in R1['by_type'] if t['key'] != 'clean']
    types.sort(key=lambda t: (not t['rule_targeted'], -t['detection']['pct'], t['label']))
    W, left, right, top, rh = 1200, 360, 70, 130, 34
    plot = W - left - right
    H = top + len(types) * rh + 60
    body = [xaxis(left, plot, top - 10, top + len(types) * rh, [0, 20, 40, 60, 80, 100])]
    rows = []
    for i, t in enumerate(types):
        y = top + i * rh + rh / 2
        d = t['detection']
        col = BLUE if t['rule_targeted'] else ORANGE
        lo, hi = d['ci95']
        body.append(f'<text x="{left - 14}" y="{y + 5}" font-size="14" fill="{INK}" text-anchor="end">{escape(t["label"])}</text>'
                    f'<line x1="{left + plot * lo / 100}" y1="{y}" x2="{left + plot * hi / 100}" y2="{y}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>'
                    f'<circle cx="{left + plot * d["pct"] / 100}" cy="{y}" r="7" fill="{col}" stroke="{SURF}" stroke-width="2"/>'
                    f'<text x="{left + plot + 12}" y="{y + 5}" font-size="13" fill="{INK2}">{d["k"]}/{d["n"]}</text>')
        rows.append([t['label'], 'Yes' if t['rule_targeted'] else 'No', d['k'], d['n'], d['pct'], lo, hi])
    page('fig4_3_detection', W, H, 'Detection rate by planted error type, replicate 1',
         'Share of the 20 orders of each type that were warned or blocked, with 95 percent Wilson intervals',
         ''.join(body), legend([(BLUE, 'A rule targets this error'), (ORANGE, 'No rule targets this error')], 32, 104))
    data('fig4_3_detection', ['error_type', 'has_rule', 'flagged', 'orders', 'detection_pct', 'ci95_low', 'ci95_high'], rows)


# ---------------------------------------------------------------- Figure 4.3 measures with intervals and replicate range
def fig_measures():
    keys = [('accuracy', 'Accuracy'), ('precision', 'Precision'), ('recall', 'Recall'), ('specificity', 'Specificity')]
    W, left, right, top, rh = 1200, 360, 70, 140, 40
    plot = W - left - right
    lo_axis = 50
    sx = lambda v: left + plot * (v - lo_axis) / (100 - lo_axis)
    rows, body = [], []
    lines = []
    for grp, lab in (('confusion_all_errors', 'all errors'), ('confusion_rule_targeted', 'rule-targeted errors')):
        for k, name in keys:
            if grp == 'confusion_rule_targeted' and k == 'specificity':
                continue
            lines.append((grp, lab, k, name))
    for t in (50, 60, 70, 80, 90, 100):
        body.append(f'<line x1="{sx(t)}" y1="{top - 10}" x2="{sx(t)}" y2="{top + len(lines) * rh}" stroke="{GRID}"/>'
                    f'<text x="{sx(t)}" y="{top + len(lines) * rh + 20}" font-size="13" fill="{MUTED}" text-anchor="middle">{t}%</text>')
    body.append(f'<line x1="{sx(90)}" y1="{top - 10}" x2="{sx(90)}" y2="{top + len(lines) * rh}" stroke="{INK2}" stroke-dasharray="5 4"/>'
                f'<text x="{sx(90) + 6}" y="{top - 16}" font-size="13" fill="{INK2}">90 percent target</text>')
    for i, (grp, lab, k, name) in enumerate(lines):
        y = top + i * rh + rh / 2
        d = R1[grp][k]
        reps = [m['replicates'][r][grp][k]['pct'] for r in '123']
        col = BLUE if grp == 'confusion_all_errors' else ORANGE
        body.append(f'<text x="{left - 14}" y="{y + 5}" font-size="14" fill="{INK}" text-anchor="end">{name}, {lab}</text>'
                    f'<line x1="{sx(d["ci95"][0])}" y1="{y}" x2="{sx(d["ci95"][1])}" y2="{y}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>')
        for v in reps[1:]:
            body.append(f'<circle cx="{sx(v)}" cy="{y}" r="5" fill="{SURF}" stroke="{INK2}" stroke-width="1.5"/>')
        body.append(f'<circle cx="{sx(d["pct"])}" cy="{y}" r="7" fill="{col}" stroke="{SURF}" stroke-width="2"/>'
                    f'<text x="{left + plot + 12}" y="{y + 5}" font-size="13" fill="{INK2}">{d["pct"]}%</text>')
        rows.append([name, lab, d['pct'], d['ci95'][0], d['ci95'][1], *reps])
    H = top + len(lines) * rh + 50
    leg = legend([(BLUE, 'All errors, replicate 1'), (ORANGE, 'Rule-targeted errors, replicate 1')], 32, 104) + \
        f'<circle cx="690" cy="100" r="5" fill="{SURF}" stroke="{INK2}" stroke-width="1.5"/><text x="702" y="105" font-size="14" fill="{INK2}">Replicates 2 and 3</text>'
    page('fig4_4_measures', W, H, 'Validation measures with 95 percent Wilson intervals',
         'Replicate 1 point estimate and interval, with replicates 2 and 3 shown for comparison', ''.join(body), leg)
    data('fig4_4_measures', ['measure', 'error_set', 'replicate1_pct', 'ci95_low', 'ci95_high', 'replicate1', 'replicate2', 'replicate3'], rows)


# ---------------------------------------------------------------- Figure 4.4 validation time across the run
def fig_timing():
    series = [('Replicate 1', m['replicates']['1']['validation_ms_mean_by_block_of_100'], BLUE),
              ('Replicate 2', m['replicates']['2']['validation_ms_mean_by_block_of_100'], ORANGE),
              ('Replicate 3', m['replicates']['3']['validation_ms_mean_by_block_of_100'], GREY)]
    W, left, right, top, ph = 1200, 110, 220, 130, 360
    plot = W - left - right
    ymax = 70
    sx = lambda i: left + plot * i / 4
    sy = lambda v: top + ph - ph * v / ymax
    body = []
    for t in range(0, ymax + 1, 10):
        body.append(f'<line x1="{left}" y1="{sy(t)}" x2="{left + plot}" y2="{sy(t)}" stroke="{GRID}"/>'
                    f'<text x="{left - 10}" y="{sy(t) + 5}" font-size="13" fill="{MUTED}" text-anchor="end">{t}</text>')
    labels = ['1-100', '101-200', '201-300', '301-400', '401-500']
    for i, lab in enumerate(labels):
        body.append(f'<text x="{sx(i)}" y="{top + ph + 22}" font-size="13" fill="{MUTED}" text-anchor="middle">{lab}</text>')
    body.append(f'<text x="{left + plot / 2}" y="{top + ph + 48}" font-size="14" fill="{INK2}" text-anchor="middle">Orders in submission order</text>'
                f'<text x="{left - 60}" y="{top + ph / 2}" font-size="14" fill="{INK2}" text-anchor="middle" transform="rotate(-90 {left - 60} {top + ph / 2})">Mean ms per order</text>')
    rows = []
    nudge = {'Replicate 1': 14, 'Replicate 2': -8, 'Replicate 3': 0}
    for name, vals, col in series:
        pts = ' '.join(f'{sx(i)},{sy(v)}' for i, v in enumerate(vals))
        body.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round"/>')
        body += [f'<circle cx="{sx(i)}" cy="{sy(v)}" r="5" fill="{col}" stroke="{SURF}" stroke-width="2"/>' for i, v in enumerate(vals)]
        body.append(f'<text x="{sx(4) + 14}" y="{sy(vals[-1]) + 5 + nudge[name]}" font-size="14" fill="{INK}">{name}, {vals[-1]} ms</text>')
        rows.append([name] + vals)
    H = top + ph + 70
    page('fig4_7_timing_blocks', W, H, 'Validation time per order across each run',
         'Mean clock time of submit_order inside the database for each block of 100 orders', ''.join(body))
    data('fig4_7_timing_blocks', ['replicate'] + labels, rows)


# ---------------------------------------------------------------- Figure 4.5 sensitivity
def fig_sensitivity():
    S = m['sensitivity']
    W, left, top, pw, ph, gapx = 1200, 90, 175, 470, 300, 110
    body, rows = [], []
    panels = [('False alarms on clean orders', 'clean_false_alarm_rate_all_rules', 25),
              ('Quantity typing slips flagged', 'typo_detection', 100)]
    for p, (title, key, ymax) in enumerate(panels):
        x0 = left + p * (pw + gapx)
        sy = lambda v: top + ph - ph * v / ymax
        body.append(f'<text x="{x0}" y="{top - 20}" font-size="16" font-weight="600" fill="{INK}">{title}</text>')
        for t in range(0, ymax + 1, 5 if ymax == 25 else 20):
            body.append(f'<line x1="{x0}" y1="{sy(t)}" x2="{x0 + pw}" y2="{sy(t)}" stroke="{GRID}"/>'
                        f'<text x="{x0 - 8}" y="{sy(t) + 5}" font-size="13" fill="{MUTED}" text-anchor="end">{t}%</text>')
        for fi, f in enumerate([3.0, 4.0, 5.0]):
            gx = x0 + 40 + fi * 145
            for hi, (h, col) in enumerate(((4, BLUE), (10, ORANGE))):
                s = next(x for x in S if x['factor'] == f and x['history_orders'] == h)
                v = s[key]['pct']
                bx = gx + hi * 46
                body.append(f'<rect x="{bx}" y="{sy(v)}" width="40" height="{top + ph - sy(v)}" fill="{col}" rx="3"/>'
                            f'<text x="{bx + 20}" y="{sy(v) - 8}" font-size="13" fill="{INK2}" text-anchor="middle">{v}</text>')
            body.append(f'<text x="{gx + 43}" y="{top + ph + 22}" font-size="14" fill="{INK2}" text-anchor="middle">{f:g} x average</text>')
    for s in S:
        rows.append([s['factor'], s['history_orders'], s['clean_false_alarm_rate_all_rules']['k'], s['clean_false_alarm_rate_all_rules']['pct'],
                     *s['clean_false_alarm_rate_all_rules']['ci95'], s['typo_detection']['k'], s['typo_detection']['pct'], *s['typo_detection']['ci95']])
    H = top + ph + 50
    page('fig4_8_sensitivity', W, H, 'Effect of the unusual-quantity threshold, replicate 1 replayed',
         'Percent of 200 clean orders flagged, and of 20 quantity slips flagged, for each threshold and history length', ''.join(body),
         legend([(BLUE, '4 earlier orders per customer'), (ORANGE, '10 earlier orders per customer')], 32, 104))
    data('fig4_8_sensitivity', ['factor', 'history_orders', 'clean_flagged', 'false_alarm_pct', 'fa_ci95_low', 'fa_ci95_high',
                                'typos_flagged', 'typo_detection_pct', 'typo_ci95_low', 'typo_ci95_high'], rows)



# ---------------------------------------------------------------- Figure 4.1 orders by region
def fig_regions():
    regs = R1['dataset']['regions']
    W, left, right, top, bh, gap = 1200, 220, 110, 120, 34, 14
    plot = W - left - right
    mx = max(regs.values())
    body, rows = [], []
    for i, (name, n) in enumerate(regs.items()):
        y = top + i * (bh + gap)
        col = GREY if name == 'No address given' else BLUE
        w = plot * n / mx
        body.append(f'<text x="{left - 14}" y="{y + bh / 2 + 5}" font-size="15" fill="{INK}" text-anchor="end">{escape(name)}</text>'
                    + hbar(left, y, w, bh, col) +
                    f'<text x="{left + w + 10}" y="{y + bh / 2 + 5}" font-size="14" fill="{INK2}">{n} ({round(100 * n / 500, 1)}%)</text>')
        rows.append([name, n])
    H = top + len(regs) * (bh + gap) + 20
    page('fig4_1_regions', W, H, 'Simulated orders by delivery region, replicate 1',
         '500 orders from 20 fictional customer companies; orders with a missing address have no region', ''.join(body))
    data('fig4_1_regions', ['region', 'orders'], rows)


# ---------------------------------------------------------------- Figure 4.5 rule activity
def fig_rules():
    rules = sorted(R1['rules'], key=lambda r: -r['orders_fired'])
    W, left, right, top, bh, gap = 1200, 250, 170, 130, 34, 14
    plot = W - left - right
    mx = max(r['orders_fired'] for r in rules)
    body, rows = [], []
    for i, r in enumerate(rules):
        y = top + i * (bh + gap)
        x = left
        parts = [(r['on_target_type'], BLUE), (r['on_other_error_types'], GREY), (r['on_clean_false_alarms'], ORANGE)]
        parts = [p for p in parts if p[0]]
        for j, (v, col) in enumerate(parts):
            w = plot * v / mx
            last = j == len(parts) - 1
            body.append(hbar(x, y, w, bh, col) if last else f'<rect x="{x}" y="{y}" width="{max(w - 2, 0)}" height="{bh}" fill="{col}"/>')
            x += w
        sev = 'warning' if r['severity'] == 'warn' else 'blocking'
        body.append(f'<text x="{left - 14}" y="{y + bh / 2 - 1}" font-size="15" fill="{INK}" text-anchor="end">{escape(r["label"])}</text>'
                    f'<text x="{left - 14}" y="{y + bh / 2 + 15}" font-size="12" fill="{MUTED}" text-anchor="end">{sev}</text>'
                    f'<text x="{x + 10}" y="{y + bh / 2 + 5}" font-size="14" fill="{INK2}">{r["orders_fired"]}'
                    + (f' ({r["on_clean_false_alarms"]} on clean orders)' if r['on_clean_false_alarms'] else '') + '</text>')
        rows.append([r['label'], sev, r['orders_fired'], r['on_target_type'], r['on_other_error_types'], r['on_clean_false_alarms']])
    H = top + len(rules) * (bh + gap) + 20
    page('fig4_5_rules', W, H, 'How often each validation rule fired, replicate 1',
         'Orders on which each rule raised a block or warning, by the kind of order', ''.join(body),
         legend([(BLUE, 'Its target error type'), (GREY, 'Another error type'), (ORANGE, 'Clean order (false alarm)')], 32, 104))
    data('fig4_5_rules', ['rule', 'severity', 'orders_fired', 'on_target_type', 'on_other_error_types', 'on_clean_orders'], rows)


# ---------------------------------------------------------------- Figure 4.6 distribution of validation time
def fig_hist():
    ms = [float(r['validation_ms']) for r in json.loads((HERE.parent / '03_simulation' / 'raw' / 'run5_replicate1.json').read_text())]
    width = 10
    nb = int(max(ms) // width) + 1
    counts = [sum(b * width <= v < (b + 1) * width for v in ms) for b in range(nb)]
    W, left, right, top, ph = 1200, 90, 40, 130, 360
    plot = W - left - right
    ymax = (max(counts) // 20 + 1) * 20
    bw = plot / nb
    sy = lambda v: top + ph - ph * v / ymax
    body, rows = [], []
    for t in range(0, ymax + 1, 20):
        body.append(f'<line x1="{left}" y1="{sy(t)}" x2="{left + plot}" y2="{sy(t)}" stroke="{GRID}"/>'
                    f'<text x="{left - 10}" y="{sy(t) + 5}" font-size="13" fill="{MUTED}" text-anchor="end">{t}</text>')
    for b, c in enumerate(counts):
        x = left + b * bw
        if c:
            body.append(f'<rect x="{x + 1}" y="{sy(c)}" width="{bw - 2}" height="{top + ph - sy(c)}" fill="{BLUE}" rx="2"/>')
        if b % 2 == 0:
            body.append(f'<text x="{x}" y="{top + ph + 20}" font-size="13" fill="{MUTED}" text-anchor="middle">{b * width}</text>')
        rows.append([b * width, (b + 1) * width, c])
    tm = R1['validation_ms']
    for v, lab in ((tm['median'], f'median {tm["median"]} ms'), (tm['p95'], f'95th percentile {tm["p95"]} ms')):
        x = left + plot * v / (nb * width)
        body.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{top + ph}" stroke="{INK2}" stroke-dasharray="5 4"/>'
                    f'<text x="{x + 6}" y="{top + 8}" font-size="13" fill="{INK2}">{lab}</text>')
    body.append(f'<text x="{left + plot / 2}" y="{top + ph + 46}" font-size="14" fill="{INK2}" text-anchor="middle">Validation time per order, ms, in bands of 10 ms</text>')
    H = top + ph + 64
    page('fig4_6_validation_time', W, H, 'Distribution of validation time per order, replicate 1',
         f'Clock time of submit_order inside the database for all 500 orders, mean {tm["mean"]} ms', ''.join(body))
    data('fig4_6_validation_time', ['from_ms', 'to_ms', 'orders'], rows)


fig_regions()
fig_outcomes()
fig_rules()
fig_hist()
fig_detection()
fig_measures()
fig_timing()
fig_sensitivity()
print('figures written to', OUT)
