"""Analysis of the questionnaire export supplied by the client team (Data_set.xlsx, sheet Responses).

  python3 analyze_dataset.py <path to Data_set.xlsx>

Writes, next to this script,
  data/responses_deidentified.csv   the export without the optional name and e-mail columns
  questionnaire_results.json        every figure reported
  questionnaire_tables.xlsx         the result tables

Statistics as in analyze_questionnaire.py: SUS scored by Brooke (1996), Cronbach's alpha, t intervals with the
sample SD, one-sample t test against 68, Welch t test between groups, Wilson intervals for agreement shares
(agree = 4 or 5 on the five-point scale). C1 to C5 are numeric codes whose labels were not supplied with the file,
so they are reported as code counts only.
"""
import csv
import json
import math
import statistics as st
import sys
from collections import Counter
from pathlib import Path
from openpyxl import Workbook, load_workbook
from analyze_questionnaire import t_sf2, t_crit, wilson, adjective, grade, acceptability

HERE = Path(__file__).parent
PII = ('Optional: Name or company', 'Optional: E-mail')

ws = load_workbook(sys.argv[1], data_only=True)['Responses']
rows = list(ws.iter_rows(values_only=True))
H = [h.strip() if isinstance(h, str) else h for h in rows[0]]
R = [dict(zip(H, r)) for r in rows[1:] if any(v is not None for v in r)]

(HERE / 'data').mkdir(exist_ok=True)
keep = [h for h in H if h not in PII]
with open(HERE / 'data' / 'responses_deidentified.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(keep)
    for r in R:
        w.writerow([r[h] for h in keep])

code = lambda h: h.split('.')[0] if isinstance(h, str) and '.' in h[:5] else h
by_code = {code(h): h for h in H}
FC1 = next(h for h in H if h.startswith('I have the phone'))
FC2 = next(h for h in H if h.startswith('I have the internet'))
VOL = next(h for h in H if h.startswith('Using Verity would be my own'))
GROUP = 'A0. Respondent group'
valid = [r for r in R if r['Informed consent to participate'] == 'Yes' and r.get('Demonstration watched') == 'Yes'
         and all(r[by_code[f'S{i}']] not in (None, '') for i in range(1, 11))]
num = lambda r, h: float(r[h])


def alpha(items):
    k = len(items)
    tot = [sum(v) for v in zip(*items)]
    return round(k / (k - 1) * (1 - sum(st.variance(i) for i in items) / st.variance(tot)), 3)


def describe(xs):
    n, m, sd = len(xs), st.mean(xs), st.stdev(xs)
    tc = t_crit(n - 1)
    return {'n': n, 'mean': round(m, 2), 'sd_sample': round(sd, 2), 'median': round(st.median(xs), 2),
            'ci95': [round(m - tc * sd / math.sqrt(n), 2), round(m + tc * sd / math.sqrt(n), 2)]}


def sus(r):
    return 2.5 * sum((num(r, by_code[f'S{i}']) - 1) if i % 2 else (5 - num(r, by_code[f'S{i}'])) for i in range(1, 11))


def welch(a, b):
    ma, mb, va, vb = st.mean(a), st.mean(b), st.variance(a), st.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    t = (ma - mb) / se
    df = (va / len(a) + vb / len(b)) ** 2 / ((va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
    return {'difference': round(ma - mb, 2), 't': round(t, 3), 'df': round(df, 1), 'p_two_sided': round(t_sf2(abs(t), df), 4)}


groups = {'All': valid, 'Staff': [r for r in valid if r[GROUP] == 'Staff'], 'Customer': [r for r in valid if r[GROUP] == 'Customer']}
out = {'source': Path(sys.argv[1]).name, 'rows': len(R), 'valid': len(valid),
       'validity_rule': 'consent Yes, demonstration watched, all ten SUS items answered',
       'by_group': {g: len(v) for g, v in groups.items()},
       'timestamps': [str(min(r['Timestamp'] for r in R)), str(max(r['Timestamp'] for r in R))]}

scales = {'SUS': None, 'PU': ['PU1', 'PU2', 'PU3'], 'PEU': ['PEU1', 'PEU2', 'PEU3'], 'FC': [FC1, FC2],
          'D': [f'D{i}' for i in range(1, 7)], 'E': [f'E{i}' for i in range(1, 13)]}
out['reliability'] = {'SUS': alpha([[(num(r, by_code[f'S{i}']) - 1) if i % 2 else (5 - num(r, by_code[f'S{i}'])) for r in valid] for i in range(1, 11)])}
for k, items in scales.items():
    if items:
        hs = [by_code.get(i, i) for i in items]
        out['reliability'][k] = alpha([[num(r, h) for r in valid] for h in hs])

out['sus'] = {}
for g, rs in groups.items():
    d = describe([sus(r) for r in rs])
    t = (d['mean'] - 68) / (d['sd_sample'] / math.sqrt(d['n']))
    d.update({'t_vs_68': round(t, 3), 'df': d['n'] - 1, 'p_two_sided': round(t_sf2(abs(t), d['n'] - 1), 4),
              'adjective_bangor_2009': adjective(d['mean']), 'acceptability_bangor_2008': acceptability(d['mean']),
              'grade_sauro_lewis_2016': grade(d['mean']),
              'share_above_68': {'k': sum(sus(r) > 68 for r in rs), 'n': len(rs), 'ci95': wilson(sum(sus(r) > 68 for r in rs), len(rs))}})
    out['sus'][g] = d
out['sus_staff_vs_customer_welch'] = welch([sus(r) for r in groups['Staff']], [sus(r) for r in groups['Customer']])

ITEMS = {'PU1': 'PU1', 'PU2': 'PU2', 'PU3': 'PU3', 'PEU1': 'PEU1', 'PEU2': 'PEU2', 'PEU3': 'PEU3', 'BI1': 'BI1',
         'FC1': FC1, 'FC2': FC2, 'VOL1': VOL, **{f'D{i}': f'D{i}' for i in range(1, 7)}, **{f'E{i}': f'E{i}' for i in range(1, 13)}}
out['items'] = {}
for key, c in ITEMS.items():
    h = by_code.get(c, c)
    out['items'][key] = {'wording': h.split('. ', 1)[-1] if '. ' in h[:6] else h}
    for g, rs in groups.items():
        xs = [num(r, h) for r in rs]
        a = sum(x >= 4 for x in xs)
        out['items'][key][g] = {**describe(xs), 'agree_4_or_5': a, 'agree_pct': round(100 * a / len(xs), 1), 'agree_ci95': wilson(a, len(xs))}
for name, items in (('PU', ['PU1', 'PU2', 'PU3']), ('PEU', ['PEU1', 'PEU2', 'PEU3'])):
    out.setdefault('scale_means', {})[name] = {g: describe([st.mean(num(r, by_code[i]) for i in items) for r in rs]) for g, rs in groups.items()}
out['corr_sus_bi1'] = round(st.correlation([sus(r) for r in valid], [num(r, by_code['BI1']) for r in valid]), 3)
out['corr_pu_bi1'] = round(st.correlation([st.mean(num(r, by_code[i]) for i in ('PU1', 'PU2', 'PU3')) for r in valid], [num(r, by_code['BI1']) for r in valid]), 3)
out['corr_peu_bi1'] = round(st.correlation([st.mean(num(r, by_code[i]) for i in ('PEU1', 'PEU2', 'PEU3')) for r in valid], [num(r, by_code['BI1']) for r in valid]), 3)

CAT = ['A1. Main role', 'A2. Years in this kind of work', 'A3. Type of business', 'A4. Number of staff in the business',
       'A5. Orders handled/placed on a typical day', 'A6. Main operating location', 'B2. Main channel (raw)', 'B2. Main channel (validated)',
       'B3. How order enters records', 'B5. Can customers see stock before ordering?', 'B6. Record of who changed/approved order',
       'B7. When stock shortages found', 'F1. Willingness to enter orders online', 'F2. Biggest order-handling problem', 'F3. Additional feature requested',
       'C1. How often order errors occur', 'C2. Estimated share of orders with error', 'C3. Error types met (select all)',
       'C4. Where errors usually found', 'C5. Time to correct one error']
out['categorical'] = {}
for h in CAT:
    hh = next((x for x in H if x == h), None)
    if hh:
        out['categorical'][h] = {g: dict(Counter(str(r[hh]).strip().rstrip('.') if r[hh] is not None else 'blank' for r in rs).most_common()) for g, rs in groups.items()}
for h in ('B1. Channels used (select all)', 'B4. Checks before processing (select all)'):
    out['categorical'][h] = {g: dict(Counter(x.strip() for r in rs for x in str(r[h] or '').split(';') if x.strip()).most_common()) for g, rs in groups.items()}
out['main_channel_consistency'] = {'raw_main_channel_among_channels_used': sum(1 for r in valid if r['B2. Main channel (validated)']),
                                   'n': len(valid)}
out['f1_willingness_yes'] = {g: {'k': sum(r['F1. Willingness to enter orders online'] == 'Yes' for r in rs), 'n': len(rs),
                                 'ci95': wilson(sum(r['F1. Willingness to enter orders online'] == 'Yes' for r in rs), len(rs))} for g, rs in groups.items()}
(HERE / 'questionnaire_results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))

# tables
wb = Workbook()
wb.remove(wb.active)
def sheet(name, header, body):
    s = wb.create_sheet(name)
    s.append(header)
    for b in body:
        s.append(b)
sheet('Respondents', ['Group', 'Valid responses'], [[g, n] for g, n in out['by_group'].items()])
sheet('Reliability', ['Scale', "Cronbach's alpha"], [[k, v] for k, v in out['reliability'].items()])
sheet('SUS', ['Group', 'n', 'Mean', 'SD', '95% CI low', '95% CI high', 't vs 68', 'df', 'p', 'Adjective', 'Acceptability', 'Grade'],
      [[g, d['n'], d['mean'], d['sd_sample'], *d['ci95'], d['t_vs_68'], d['df'], d['p_two_sided'], d['adjective_bangor_2009'],
        d['acceptability_bangor_2008'], d['grade_sauro_lewis_2016']] for g, d in out['sus'].items()])
sheet('Items', ['Item', 'Wording', 'Group', 'n', 'Mean', 'SD', 'Agree %', 'Agree 95% CI low', 'Agree 95% CI high'],
      [[k, v['wording'], g, v[g]['n'], v[g]['mean'], v[g]['sd_sample'], v[g]['agree_pct'], *v[g]['agree_ci95']]
       for k, v in out['items'].items() for g in ('All', 'Staff', 'Customer')])
wb.save(HERE / 'questionnaire_tables.xlsx')

print(json.dumps({k: out[k] for k in ('rows', 'valid', 'by_group', 'reliability', 'sus_staff_vs_customer_welch', 'corr_sus_bi1', 'corr_pu_bi1', 'corr_peu_bi1', 'main_channel_consistency', 'f1_willingness_yes')}, indent=1))
for g, d in out['sus'].items():
    print(g, {k: d[k] for k in ('n', 'mean', 'sd_sample', 'ci95', 't_vs_68', 'p_two_sided', 'adjective_bangor_2009', 'acceptability_bangor_2008', 'grade_sauro_lewis_2016')})
for k, v in out['items'].items():
    print(k, v['All']['mean'], v['All']['agree_pct'], v['All']['agree_ci95'], '| staff', v['Staff']['mean'], '| cust', v['Customer']['mean'], '|', v['wording'][:60])
