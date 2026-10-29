"""Builds the Chapter 4 figures as standalone SVG/HTML pages from metrics.json.
render.mjs then screenshots them to PNG. Standard library only.

Palette (validated with the dataviz validator, light mode): series blue #2a78d6,
series orange #eb6834; status good #0ca30c, warning #fab219, critical #d03b3b,
always paired with a text label.
"""
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
m = json.loads((HERE / 'metrics.json').read_text())

INK, INK2, MUTED, GRID, BASE, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb'
BLUE, ORANGE = '#2a78d6', '#eb6834'
GOOD, WARN, CRIT = '#0ca30c', '#fab219', '#d03b3b'
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


def legend(items, x, y):
    out, cx = [], x
    for color, label in items:
        out.append(f'<rect x="{cx}" y="{y - 11}" width="14" height="14" rx="3" fill="{color}"/>'
                   f'<text x="{cx + 20}" y="{y + 1}" font-size="14" fill="{INK2}">{escape(label)}</text>')
        cx += 30 + len(label) * 7.6
    return ''.join(out)


def hbar(x, y, w, h, color):
    """Horizontal bar, 4px rounded at the data end, square at the baseline."""
    if w <= 0:
        return ''
    r = min(4, w / 2, h / 2)
    return (f'<path d="M{x},{y} h{w - r} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{w - r} z" fill="{color}"/>')


# ---------------------------------------------------------------- Fig 4.1 outcomes by group (100% stacked)
def fig_outcomes():
    groups = m['outcomes_by_group']
    W, left, right, top, bh, gap = 1200, 250, 40, 130, 56, 30
    plot = W - left - right
    body = []
    for i, (g, d) in enumerate(groups.items()):
        n = sum(d.values())
        y = top + i * (bh + gap)
        body.append(f'<text x="{left - 14}" y="{y + bh / 2 - 4}" font-size="15" font-weight="600" fill="{INK}" text-anchor="end">{escape(g)}</text>'
                    f'<text x="{left - 14}" y="{y + bh / 2 + 16}" font-size="13" fill="{MUTED}" text-anchor="end">{n} orders</text>')
        x = left
        segs = [('pass', GOOD, 'Passed'), ('warn', WARN, 'Warned'), ('fail', CRIT, 'Blocked')]
        nonzero = [s for s in segs if d.get(s[0], 0)]
        for j, (k, color, lab) in enumerate(nonzero):
            v = d.get(k, 0)
            w = plot * v / n
            last = j == len(nonzero) - 1
            seg_w = w - (0 if last else 2)  # 2px surface gap between segments
            if last:
                body.append(hbar(x, y, seg_w, bh, color))
            else:
                body.append(f'<rect x="{x}" y="{y}" width="{seg_w}" height="{bh}" fill="{color}"/>')
            if w > 70:
                tc = INK if k == 'warn' else '#ffffff'
                body.append(f'<text x="{x + w / 2}" y="{y + bh / 2 + 6}" font-size="15" font-weight="650" fill="{tc}" text-anchor="middle">{v} ({round(100 * v / n)}%)</text>')
            elif w > 0:
                body.append(f'<text x="{x + w / 2}" y="{y - 6}" font-size="13" fill="{INK2}" text-anchor="middle">{v}</text>')
            x += w
    H = top + len(groups) * (bh + gap) + 20
    lg = legend([(GOOD, 'Passed – sent to approval'), (WARN, 'Warned – flagged for a person'), (CRIT, 'Blocked – customer must fix')], 32, 104)
    page('fig4_1_outcomes', W, H, 'Validation outcome by order group',
         f"Share of the {m['run']['orders']} simulated orders passed, warned or blocked by the validation engine", ''.join(body), lg)


# ---------------------------------------------------------------- Fig 4.2 detection by error type
def fig_detection():
    cats = [c for c in m['categories'] if c['key'] != 'clean']
    cats.sort(key=lambda c: (not c['targeted'], -c['detection_rate']))
    W, left, right, top, bh, gap = 1200, 330, 120, 120, 24, 12
    plot = W - left - right
    body = []
    for t in (0, 25, 50, 75, 100):
        x = left + plot * t / 100
        body.append(f'<line x1="{x}" y1="{top - 8}" x2="{x}" y2="{top + len(cats) * (bh + gap)}" stroke="{GRID}" stroke-width="1"/>'
                    f'<text x="{x}" y="{top + len(cats) * (bh + gap) + 22}" font-size="13" fill="{MUTED}" text-anchor="middle">{t}%</text>')
    for i, c in enumerate(cats):
        y = top + i * (bh + gap)
        color = BLUE if c['targeted'] else ORANGE
        w = plot * c['detection_rate'] / 100
        body.append(f'<text x="{left - 12}" y="{y + bh / 2 + 5}" font-size="14" fill="{INK}" text-anchor="end">{escape(c["label"])}</text>')
        body.append(hbar(left, y, w, bh, color))
        note = f"{c['flagged']}/{c['n']}"
        if not c['targeted'] and c['flagged']:
            note += ' (other rules)'
        body.append(f'<text x="{left + w + 8}" y="{y + bh / 2 + 5}" font-size="13" fill="{INK2}">{c["detection_rate"]:g}%  ·  {note}</text>')
    body.append(f'<line x1="{left}" y1="{top - 8}" x2="{left}" y2="{top + len(cats) * (bh + gap)}" stroke="{BASE}" stroke-width="1"/>')
    H = top + len(cats) * (bh + gap) + 40
    lg = legend([(BLUE, 'Error type with a validation rule'), (ORANGE, 'Error type with no rule (realistic mistakes)')], 32, 100)
    page('fig4_2_detection', W, H, 'Detection rate by planted error type',
         'Orders blocked or warned, as a share of orders carrying each error', ''.join(body), lg)


# ---------------------------------------------------------------- Fig 4.3 rule activity
def fig_rules():
    rules = m['rules']
    W, left, right, top, bh, gap = 1200, 250, 80, 120, 26, 14
    plot = W - left - right
    mx = max(r['total'] for r in rules)
    step = 20
    body = []
    t = 0
    while t <= mx + step:
        x = left + plot * t / (mx + step)
        body.append(f'<line x1="{x}" y1="{top - 8}" x2="{x}" y2="{top + len(rules) * (bh + gap)}" stroke="{GRID}"/>'
                    f'<text x="{x}" y="{top + len(rules) * (bh + gap) + 22}" font-size="13" fill="{MUTED}" text-anchor="middle">{t}</text>')
        t += step
    for i, r in enumerate(rules):
        y = top + i * (bh + gap)
        sev = 'warning' if r['severity'] == 'warn' else 'blocking'
        body.append(f'<text x="{left - 12}" y="{y + bh / 2 - 2}" font-size="14" fill="{INK}" text-anchor="end">{escape(r["label"])}</text>'
                    f'<text x="{left - 12}" y="{y + bh / 2 + 14}" font-size="12" fill="{MUTED}" text-anchor="end">{sev}</text>')
        we = plot * r['on_errors'] / (mx + step)
        wc = plot * r['on_clean'] / (mx + step)
        if r['on_clean']:
            body.append(f'<rect x="{left}" y="{y}" width="{max(we - 2, 0)}" height="{bh}" fill="{BLUE}"/>')
            body.append(hbar(left + we, y, wc, bh, ORANGE))
        else:
            body.append(hbar(left, y, we, bh, BLUE))
        lab = f"{r['total']}" + (f"  ({r['on_clean']} on clean orders)" if r['on_clean'] else '')
        body.append(f'<text x="{left + we + wc + 8}" y="{y + bh / 2 + 5}" font-size="13" fill="{INK2}">{lab}</text>')
    body.append(f'<line x1="{left}" y1="{top - 8}" x2="{left}" y2="{top + len(rules) * (bh + gap)}" stroke="{BASE}"/>')
    H = top + len(rules) * (bh + gap) + 40
    lg = legend([(BLUE, 'Fired on an order with a planted error'), (ORANGE, 'Fired on a clean order (false alarm)')], 32, 100)
    page('fig4_3_rules', W, H, 'How often each validation rule fired',
         'Number of simulated orders on which each rule raised a failure or warning', ''.join(body), lg)


# ---------------------------------------------------------------- Fig 4.4 validation time histogram
def fig_timing():
    hist, t = m['hist'], m['timing']
    W, H, left, right, top, bottom = 1200, 560, 80, 40, 110, 70
    plot_w, plot_h = W - left - right, H - top - bottom
    mx = max(b['n'] for b in hist)
    ymax = ((mx // 20) + 1) * 20
    bw = plot_w / len(hist)
    body = []
    for v in range(0, ymax + 1, 20):
        y = top + plot_h - plot_h * v / ymax
        body.append(f'<line x1="{left}" y1="{y}" x2="{W - right}" y2="{y}" stroke="{GRID}"/>'
                    f'<text x="{left - 10}" y="{y + 4}" font-size="13" fill="{MUTED}" text-anchor="end">{v}</text>')
    for i, b in enumerate(hist):
        h = plot_h * b['n'] / ymax
        x = left + i * bw + 1
        w = bw - 2
        y = top + plot_h - h
        if h > 0:
            r = min(4, w / 2, h)
            body.append(f'<path d="M{x},{top + plot_h} v-{h - r} a{r},{r} 0 0 1 {r},-{r} h{w - 2 * r} a{r},{r} 0 0 1 {r},{r} v{h - r} z" fill="{BLUE}"/>')
        if i % 2 == 0:
            body.append(f'<text x="{left + i * bw}" y="{top + plot_h + 22}" font-size="13" fill="{MUTED}" text-anchor="middle">{b["from"]}</text>')
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{W - right}" y2="{top + plot_h}" stroke="{BASE}"/>')
    body.append(f'<text x="{left + plot_w / 2}" y="{H - 18}" font-size="14" fill="{INK2}" text-anchor="middle">Server validation time per order (milliseconds, 5 ms bins)</text>')
    for val, lab in ((t['median'], f"median {t['median']} ms"), (t['p95'], f"95th percentile {t['p95']} ms")):
        x = left + plot_w * val / (len(hist) * 5)
        body.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{top + plot_h}" stroke="{INK}" stroke-width="1.5" stroke-dasharray="5 4"/>'
                    f'<text x="{x + 6}" y="{top + 8}" font-size="13" fill="{INK}">{lab}</text>')
    page('fig4_4_timing', W, H, 'Time the server took to validate each order',
         f"Mean {t['mean']} ms, all {m['run']['orders']} orders validated in under {int(t['max']) + 1} ms (Supabase Postgres, eu-west-1)", ''.join(body))


# ---------------------------------------------------------------- Fig 4.5 orders by region
def fig_regions():
    reg = m['dataset']['by_region']
    W, left, right, top, bh, gap = 1200, 230, 90, 100, 26, 14
    plot = W - left - right
    mx = max(reg.values())
    body = []
    for i, (k, v) in enumerate(reg.items()):
        y = top + i * (bh + gap)
        w = plot * v / (mx * 1.1)
        body.append(f'<text x="{left - 12}" y="{y + bh / 2 + 5}" font-size="14" fill="{INK}" text-anchor="end">{escape(k)}</text>')
        body.append(hbar(left, y, w, bh, BLUE if k != 'No address given' else MUTED))
        body.append(f'<text x="{left + w + 8}" y="{y + bh / 2 + 5}" font-size="13" fill="{INK2}">{v} ({round(100 * v / m["run"]["orders"])}%)</text>')
    body.append(f'<line x1="{left}" y1="{top - 8}" x2="{left}" y2="{top + len(reg) * (bh + gap)}" stroke="{BASE}"/>')
    H = top + len(reg) * (bh + gap) + 20
    page('fig4_5_regions', W, H, 'Simulated orders by delivery region',
         f"{m['run']['orders']} orders from {m['run']['customers']} fictional customer companies", ''.join(body))


for f in (fig_outcomes, fig_detection, fig_rules, fig_timing, fig_regions):
    f()
print('written', sorted(p.name for p in OUT.glob('*.html')))
