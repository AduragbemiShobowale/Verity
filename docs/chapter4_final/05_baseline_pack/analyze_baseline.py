"""Scores the manual baseline against the Verity condition. Standard library only.

  python3 analyze_baseline.py manual_entries.csv verity_orders.csv

manual_entries.csv  the Entries sheet of entry_template.xlsx saved as CSV, Manual condition rows
verity_orders.csv   result of query 1 in extract_baseline.sql
Answer key          facilitator_only/ANSWER_KEY.csv

Definitions (fixed before any data were collected)
  error reaching the record  manual: a planted error that was not flagged, or any field typed differently from the
                             message. Verity: an order that was approved while carrying a planted error, or whose
                             approved lines, address or date differ from the message.
  error rate                 orders with an error reaching the record / orders processed in that condition
  error reduction            1 - Verity error rate / manual error rate. Objective 3 target: at least 60 percent.
  time                       manual: Seconds column. Verity: seconds_draft_to_decision (draft saved to approval or
                             rejection in the status history). Compared on orders that have a time in both conditions.
  time saved                 1 - mean Verity time / mean manual time, also reported on medians. Objective 4: 30 to 50 percent.
  pairs                      order references processed in both conditions. Below about 80 pairs the error comparison
                             is indicative only.
Writes baseline_results.json next to this script. Exits without writing anything if the input files hold no real data.
"""
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).parent
Z = 1.959964


def wilson(k, n):
    if not n:
        return None
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def norm_lines(s):
    out = {}
    for part in (s or '').replace(',', ';').split(';'):
        if ' x ' in part:
            sku, q = part.strip().rsplit(' x ', 1)
            try:
                out[sku.strip().upper()] = float(q)
            except ValueError:
                out[sku.strip().upper()] = q.strip()
    return out


def norm(s):
    return ' '.join(str(s or '').lower().replace(',', ' ').split())


if len(sys.argv) != 3 or not all(Path(a).exists() for a in sys.argv[1:]):
    sys.exit('No real baseline data yet: pass manual_entries.csv and verity_orders.csv from the session. Nothing written.')
key = {r['reference']: r for r in csv.DictReader(open(HERE / 'facilitator_only' / 'ANSWER_KEY.csv'))}
manual = [r for r in csv.DictReader(open(sys.argv[1])) if (r.get('Condition') or '').lower() == 'manual' and r.get('Order reference')]
verity = [r for r in csv.DictReader(open(sys.argv[2])) if r.get('ref')]
if not manual or not verity or not any((r.get('Seconds') or '').strip() for r in manual):
    sys.exit('The files contain no completed rows. Nothing written.')

res = {'manual': [], 'verity': []}
for r in manual:
    k = key[r['Order reference'].strip()]
    lines = {}
    for i in range(1, 5):
        sku = (r.get(f'Line {i} item code') or '').strip().upper()
        if sku:
            try:
                lines[sku] = float(r.get(f'Line {i} quantity') or 'nan')
            except ValueError:
                lines[sku] = r.get(f'Line {i} quantity')
    typed = {'customer': norm(r.get('Customer')) != norm(k['customer']),
             'address': norm(r.get('Delivery address')) != norm(k['address_as_sent']),
             'date': (r.get('Delivery date (DD/MM/YYYY)') or '').strip() != ('/'.join(reversed(k['delivery_date_as_sent'].split('-'))) if k['delivery_date_as_sent'] else ''),
             'lines': lines != norm_lines(k['lines_as_sent'])}
    flagged = (r.get('Problem flagged (Yes/No)') or '').strip().lower() == 'yes'
    planted = k['planted_error'] != 'clean'
    res['manual'].append({'ref': k['reference'], 'participant': r.get('Participant ID'), 'planted': k['planted_error'],
                          'flagged': flagged, 'typing_errors': [f for f, bad in typed.items() if bad],
                          'error_reached': (planted and not flagged) or any(typed.values()),
                          'false_flag': flagged and not planted,
                          'seconds': float(r['Seconds']) if (r.get('Seconds') or '').strip() else None})
for r in verity:
    k = key[r['ref']]
    approved = r['final_status'] not in ('draft', 'submitted', 'validation_failed', 'rejected', 'pending_approval', 'cancelled')
    typed = {'address': norm(r.get('address_line')) != norm(k['address_as_sent']),
             'date': (r.get('requested_date') or '') != k['delivery_date_as_sent'],
             'lines': norm_lines(r.get('lines_entered')) != {s: q for s, q in norm_lines(k['lines_as_sent']).items() if not s.startswith('XX-')}}
    planted = k['planted_error'] != 'clean'
    sec = r.get('seconds_draft_to_decision')
    res['verity'].append({'ref': k['reference'], 'participant': r.get('participant'), 'planted': k['planted_error'],
                          'final_status': r['final_status'], 'approved': approved, 'typing_errors': [f for f, bad in typed.items() if bad],
                          'error_reached': approved and (planted or any(typed.values())),
                          'seconds': float(sec) if sec not in (None, '') else None})


def rate(rows):
    k = sum(r['error_reached'] for r in rows)
    return {'orders': len(rows), 'with_error_reaching_record': k, 'pct': round(100 * k / len(rows), 1), 'ci95': wilson(k, len(rows))}


out = {'manual': rate(res['manual']), 'verity': rate(res['verity'])}
m, v = out['manual']['pct'], out['verity']['pct']
out['error_reduction_pct'] = round(100 * (1 - v / m), 1) if m else None
pairs = sorted({r['ref'] for r in res['manual']} & {r['ref'] for r in res['verity']})
out['pairs'] = len(pairs)
out['error_comparison_indicative_only'] = len(pairs) < 80
mt = {r['ref']: r['seconds'] for r in res['manual'] if r['seconds'] is not None}
vt = {r['ref']: r['seconds'] for r in res['verity'] if r['seconds'] is not None}
both = [x for x in pairs if x in mt and x in vt]
if len(both) >= 2:
    a, b = [mt[x] for x in both], [vt[x] for x in both]
    out['time'] = {'orders_with_both_times': len(both),
                   'manual_mean_s': round(st.mean(a), 1), 'manual_median_s': round(st.median(a), 1), 'manual_sd_sample_s': round(st.stdev(a), 1),
                   'verity_mean_s': round(st.mean(b), 1), 'verity_median_s': round(st.median(b), 1), 'verity_sd_sample_s': round(st.stdev(b), 1),
                   'time_saved_on_means_pct': round(100 * (1 - st.mean(b) / st.mean(a)), 1),
                   'time_saved_on_medians_pct': round(100 * (1 - st.median(b) / st.median(a)), 1),
                   'paired_difference_mean_s': round(st.mean(x - y for x, y in zip(a, b)), 1)}
out['objective_3_status'] = ('Met' if out['error_reduction_pct'] is not None and out['error_reduction_pct'] >= 60 else 'Not met')
t = out.get('time', {}).get('time_saved_on_means_pct')
out['objective_4_status'] = None if t is None else ('Met' if t >= 30 else 'Not met')
out['manual_false_flags'] = sum(r['false_flag'] for r in res['manual'])
out['rows'] = res
(HERE / 'baseline_results.json').write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
