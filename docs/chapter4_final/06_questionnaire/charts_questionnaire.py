"""Questionnaire figures for Chapter Four, from questionnaire_results.json and data/responses_deidentified.csv.
Same palette and style as 07_analysis/charts_final.py. Writes figures/*.svg, *.html and *_data.csv;
render with ../07_analysis/render_final.mjs pointed at this folder (see render_questionnaire.mjs)."""
import csv
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
Q = json.loads((HERE / 'questionnaire_results.json').read_text())
ROWS = list(csv.DictReader(open(HERE / 'data' / 'responses_deidentified.csv', encoding='utf-8')))
INK, INK2, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#fcfcfb'
BLUE, ORANGE = '#2a78d6', '#eb6834'
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"


def page(name, width, height, title, subtitle, body, legend=''):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">
<rect width="{width}" height="{height}" fill="{SURF}"/>
<text x="32" y="44" font-size="22" font-weight="650" fill="{INK}">{escape(title)}</text>
<text x="32" y="72" font-size="15" fill="{INK2}">{escape(subtitle)}</text>
{legend}{body}</svg>'''
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
        out.append(f'<rect x="{cx}" y="{y - 11}" width="14" height="14" rx="3" fill="{color}"/><text x="{cx + 20}" y="{y + 1}" font-size="14" fill="{INK2}">{escape(label)}</text>')
        cx += 30 + len(label) * 7.6
    return ''.join(out)


def sus(r):
    v = {i: float(next(val for k, val in r.items() if k.startswith(f'S{i}.'))) for i in range(1, 11)}
    return 2.5 * sum((v[i] - 1) if i % 2 else (5 - v[i]) for i in range(1, 11))


def fig_sus():
    groups = {'Staff': [sus(r) for r in ROWS if r['A0. Respondent group'] == 'Staff'],
              'Customer': [sus(r) for r in ROWS if r['A0. Respondent group'] == 'Customer']}
    bins = [(lo, lo + 10) for lo in range(0, 100, 10)]
    cnt = {g: [sum(lo <= x < hi or (hi == 100 and x == 100) for x in xs) for lo, hi in bins] for g, xs in groups.items()}
    W, left, right, top, ph = 1200, 90, 40, 130, 340
    plot = W - left - right
    ymax = (max(max(c) for c in cnt.values()) // 5 + 1) * 5
    sy = lambda v: top + ph - ph * v / ymax
    bw = plot / len(bins)
    body, rows = [], []
    for t in range(0, ymax + 1, 5):
        body.append(f'<line x1="{left}" y1="{sy(t)}" x2="{left + plot}" y2="{sy(t)}" stroke="{GRID}"/><text x="{left - 10}" y="{sy(t) + 5}" font-size="13" fill="{MUTED}" text-anchor="end">{t}</text>')
    for i, (lo, hi) in enumerate(bins):
        x = left + i * bw
        for j, (g, col) in enumerate((('Staff', BLUE), ('Customer', ORANGE))):
            c = cnt[g][i]
            if c:
                body.append(f'<rect x="{x + 6 + j * (bw - 12) / 2}" y="{sy(c)}" width="{(bw - 12) / 2 - 2}" height="{top + ph - sy(c)}" fill="{col}" rx="2"/>')
        body.append(f'<text x="{x + bw / 2}" y="{top + ph + 20}" font-size="13" fill="{MUTED}" text-anchor="middle">{lo} to {hi}</text>')
        rows.append([f'{lo} to {hi}', cnt['Staff'][i], cnt['Customer'][i]])
    for v, lab in ((68, 'benchmark 68'), (Q['sus']['All']['mean'], f'mean {Q["sus"]["All"]["mean"]}')):
        x = left + plot * v / 100
        body.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{top + ph}" stroke="{INK2}" stroke-dasharray="5 4"/><text x="{x + 6}" y="{top + 8}" font-size="13" fill="{INK2}">{lab}</text>')
    body.append(f'<text x="{left + plot / 2}" y="{top + ph + 46}" font-size="14" fill="{INK2}" text-anchor="middle">System Usability Scale score, bands of 10 points</text>')
    page('figQ1_sus', W, top + ph + 64, 'Distribution of System Usability Scale scores',
         f'Number of respondents in each band, {len(groups["Staff"])} staff and {len(groups["Customer"])} customers', ''.join(body),
         legend([(BLUE, 'Staff'), (ORANGE, 'Customer')], 32, 104))
    data('figQ1_sus', ['band', 'staff', 'customer'], rows)


def fig_items(name, keys, title, subtitle):
    W, left, right, top, rh = 1200, 470, 80, 130, 40
    plot = W - left - right
    sx = lambda v: left + plot * v / 100
    body, rows = [], []
    for t in range(0, 101, 20):
        body.append(f'<line x1="{sx(t)}" y1="{top - 10}" x2="{sx(t)}" y2="{top + len(keys) * rh}" stroke="{GRID}"/><text x="{sx(t)}" y="{top + len(keys) * rh + 20}" font-size="13" fill="{MUTED}" text-anchor="middle">{t}%</text>')
    body.append(f'<line x1="{sx(50)}" y1="{top - 10}" x2="{sx(50)}" y2="{top + len(keys) * rh}" stroke="{INK2}" stroke-dasharray="5 4"/>')
    for i, k in enumerate(keys):
        it = Q['items'][k]
        y = top + i * rh + rh / 2
        a = it['All']
        lab = f'{k}. {it["wording"]}'
        lab = lab if len(lab) <= 60 else lab[:58] + '...'
        body.append(f'<text x="{left - 14}" y="{y + 5}" font-size="13.5" fill="{INK}" text-anchor="end">{escape(lab)}</text>'
                    f'<line x1="{sx(a["agree_ci95"][0])}" y1="{y}" x2="{sx(a["agree_ci95"][1])}" y2="{y}" stroke="{BLUE}" stroke-width="3" stroke-linecap="round"/>'
                    f'<circle cx="{sx(a["agree_pct"])}" cy="{y}" r="7" fill="{BLUE}" stroke="{SURF}" stroke-width="2"/>'
                    f'<text x="{left + plot + 12}" y="{y + 5}" font-size="13" fill="{INK2}">{a["agree_pct"]}%</text>')
        rows.append([k, it['wording'], a['agree_4_or_5'], a['n'], a['agree_pct'], *a['agree_ci95']])
    page(name, W, top + len(keys) * rh + 50, title, subtitle, ''.join(body))
    data(name, ['item', 'wording', 'agree', 'n', 'agree_pct', 'ci95_low', 'ci95_high'], rows)


fig_sus()
fig_items('figQ2_acceptance', ['PU1', 'PU2', 'PU3', 'PEU1', 'PEU2', 'PEU3', 'BI1', 'FC1', 'FC2', 'VOL1'],
          'Agreement with the acceptance items after the demonstration',
          'Percent of 200 respondents answering 4 or 5, with 95 percent Wilson intervals; dashed line at 50 percent')
fig_items('figQ3_checks', [f'E{i}' for i in range(1, 13)], 'Importance of the checks an order system should make',
          'Percent of 200 respondents rating each check 4 or 5, with 95 percent Wilson intervals; dashed line at 50 percent')
print('written', sorted(p.name for p in OUT.glob('*.svg')))
