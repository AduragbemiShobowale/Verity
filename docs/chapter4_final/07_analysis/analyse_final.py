"""Analysis of the final validation simulation (runs 5, 6 and 7) and the unusual-quantity sensitivity replays
(runs 8 to 13, each a replay of run 5). Standard library only.

Inputs  ../03_simulation/raw/run{5,6,7}_replicate{1,2,3}.json   exported from simulation_final_orders
        ../04_sensitivity/raw/runs8to13_replays_of_run5.json
Outputs ../03_simulation/replicate{1,2,3}_orders.csv            one row per order, the columns asked for in 1.3
        metrics_final.json                                       every number quoted in Chapter Four Part B
        ../04_sensitivity/sensitivity_results.csv

Conventions
  flagged          outcome is fail or warn (warn includes duplicates held for confirmation)
  positive class   an order that carries a planted error
  primary measures all 300 erroneous orders against the 200 clean orders
  secondary        the 240 rule-targeted erroneous orders against the same 200 clean orders
  intervals        95 percent Wilson score intervals (Wilson, 1927), z = 1.959964
  SD               sample standard deviation (n - 1)
  percentiles      linear interpolation between order statistics (statistics.quantiles, method='inclusive')
"""
import csv
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SIM = HERE.parent / '03_simulation'
SENS = HERE.parent / '04_sensitivity'
Z = 1.959964

REPS = [(1, 5, 0.42), (2, 6, 0.43), (3, 7, 0.44)]
LABEL = {
    'clean': 'Clean order (no error)',
    'bad_sku': 'SKU not in catalogue', 'inactive_product': 'Discontinued product',
    'missing_address': 'Missing delivery address', 'missing_date': 'Missing delivery date',
    'past_date': 'Delivery date in the past', 'qty_below_min': 'Quantity below minimum',
    'qty_above_max': 'Quantity above maximum', 'fractional_qty': 'Fractional quantity',
    'over_stock': 'Quantity above available stock', 'duplicate': 'Duplicate order',
    'inactive_customer': 'Customer account not active', 'stale_price': 'Price changed after the order was saved',
    'wrong_product': 'Wrong but valid product', 'qty_typo': 'Plausible quantity typing slip',
    'wrong_address': 'Wrong saved address',
}
RULE_LABEL = {
    'mandatory': 'Mandatory fields', 'sku': 'SKU and product active', 'quantity': 'Quantity limits',
    'stock': 'Stock availability', 'customer_status': 'Customer status', 'pricing': 'Pricing',
    'delivery': 'Delivery date and address', 'duplicate': 'Duplicate order', 'unusual_quantity': 'Unusual quantity',
}
SEVERITY = {'duplicate': 'warn', 'unusual_quantity': 'warn'}


def wilson(k, n):
    if n == 0:
        return None
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def prop(k, n):
    return {'k': k, 'n': n, 'pct': round(100 * k / n, 1) if n else None, 'ci95': wilson(k, n)}


def confusion(errors, cleans):
    tp = sum(r['flagged'] for r in errors)
    fn = len(errors) - tp
    fp = sum(r['flagged'] for r in cleans)
    tn = len(cleans) - fp
    p = tp / (tp + fp) if tp + fp else 0
    rc = tp / (tp + fn) if tp + fn else 0
    return {
        'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn, 'n': tp + fn + fp + tn,
        'accuracy': prop(tp + tn, tp + fn + fp + tn),
        'precision': prop(tp, tp + fp),
        'recall': prop(tp, tp + fn),
        'specificity': prop(tn, tn + fp),
        'false_alarm_rate': prop(fp, fp + tn),
        'f1_pct': round(100 * 2 * p * rc / (p + rc), 1) if p + rc else 0,
    }


def describe(xs):
    xs = sorted(xs)
    q = st.quantiles(xs, n=100, method='inclusive')
    return {'n': len(xs), 'mean': round(st.mean(xs), 2), 'sd_sample': round(st.stdev(xs), 2),
            'median': round(st.median(xs), 2), 'p95': round(q[94], 2), 'min': round(xs[0], 2), 'max': round(xs[-1], 2)}


def ms_between(a, b):
    from datetime import datetime
    f = lambda s: datetime.fromisoformat(s)
    return (f(b) - f(a)).total_seconds() * 1000


def analyse(rows):
    clean = [r for r in rows if r['planted_error'] == 'clean']
    err = [r for r in rows if r['planted_error'] != 'clean']
    tgt = [r for r in err if r['rule_targeted']]
    untgt = [r for r in err if not r['rule_targeted']]
    by_type = []
    for key in LABEL:
        rs = [r for r in rows if r['planted_error'] == key]
        if not rs:
            continue
        exp = rs[0]['expected_rule']
        flagged = sum(r['flagged'] for r in rs)
        right = sum(1 for r in rs if exp and exp in r['rules_triggered']) if exp else None
        incidental = [r for r in rs if r['flagged'] and not (exp and exp in r['rules_triggered'])] if key != 'clean' else []
        by_type.append({
            'key': key, 'label': LABEL[key], 'rule_targeted': bool(exp), 'expected_rule': exp, 'n': len(rs),
            'blocked': sum(r['outcome'] == 'fail' for r in rs), 'warned': sum(r['outcome'] == 'warn' for r in rs),
            'passed': sum(r['outcome'] == 'pass' for r in rs),
            'detection': prop(flagged, len(rs)) if key != 'clean' else None,
            'clean_pass': prop(len(rs) - flagged, len(rs)) if key == 'clean' else None,
            'caught_by_expected_rule': right,
            'flagged_by_other_rule_only': len(incidental),
            'other_rules': dict(Counter(x for r in incidental for x in r['rules_triggered'])),
        })
    rules = []
    for rule in RULE_LABEL:
        on = [r for r in rows if rule in r['rules_triggered']]
        on_clean = [r for r in on if r['planted_error'] == 'clean']
        on_target = [r for r in on if r['expected_rule'] == rule]
        rules.append({
            'rule': rule, 'label': RULE_LABEL[rule], 'severity': SEVERITY.get(rule, 'fail'),
            'orders_fired': len(on), 'on_target_type': len(on_target),
            'on_other_error_types': len(on) - len(on_clean) - len(on_target),
            'on_clean_false_alarms': len(on_clean),
            'false_alarm_rate_on_clean': prop(len(on_clean), len(clean)),
        })
    ms = [float(r['validation_ms']) for r in rows]
    by_outcome = {k: describe([float(r['validation_ms']) for r in rows if r['outcome'] == k]) for k in ('pass', 'warn', 'fail')
                  if any(r['outcome'] == k for r in rows)}
    # status history: draft event to the last event recorded for the order (wall clock, see _sim_event_clock)
    hist = []
    for r in rows:
        ev = r['events'] or []
        if len(ev) >= 2:
            hist.append(ms_between(ev[0]['at'], ev[-1]['at']))
    reach = [r for r in rows if r['status_after'] == 'pending_approval']
    complete = [r for r in reach if r['address_label'] and r['region'] and r['input'].get('date_offset') is not None
                and r['line_count'] > 0]
    statuses = Counter(r['status_after'] for r in rows)
    vals = [float(r['total']) for r in rows]
    return {
        'orders': len(rows), 'clean': len(clean), 'errors': len(err), 'rule_targeted': len(tgt), 'no_rule': len(untgt),
        'outcomes': dict(Counter(r['outcome'] for r in rows)),
        'outcomes_by_group': {g: dict(Counter(r['outcome'] for r in rs)) for g, rs in
                              (('clean', clean), ('rule_targeted', tgt), ('no_rule', untgt))},
        'statuses_after_submit': dict(statuses),
        'confusion_all_errors': confusion(err, clean),
        'confusion_rule_targeted': confusion(tgt, clean),
        'no_rule_detection': prop(sum(r['flagged'] for r in untgt), len(untgt)),
        'by_type': by_type,
        'rules': rules,
        'false_alarm_reasons': dict(Counter(x for r in clean if r['flagged'] for x in r['rules_triggered'])),
        'validation_ms': describe(ms),
        'validation_ms_by_outcome': by_outcome,
        'validation_ms_mean_by_block_of_100': [round(st.mean(ms[i:i + 100]), 2) for i in range(0, len(ms), 100)],
        'status_history_draft_to_last_event_ms': describe(hist) if len(hist) > 1 else None,
        'status_history_orders_with_two_or_more_events': len(hist),
        'mandatory_completion_reaching_approval': prop(len(complete), len(reach)),
        'dataset': {
            'customers': len({r['company'] for r in rows}),
            'regions': dict(Counter(r['region'] or 'No address given' for r in rows).most_common()),
            'orders_per_customer_min': min(Counter(r['company'] for r in rows).values()),
            'orders_per_customer_max': max(Counter(r['company'] for r in rows).values()),
            'lines_mean': round(st.mean(r['line_count'] for r in rows), 2),
            'units_mean': round(st.mean(r['units'] for r in rows), 1),
            'value_mean': round(st.mean(vals), 2), 'value_median': round(st.median(vals), 2),
            'value_min': round(min(vals), 2), 'value_max': round(max(vals), 2), 'value_total': round(sum(vals), 2),
        },
    }


def order_csv(rows, path):
    cols = ['order_no', 'seq', 'sim_day', 'company', 'region', 'line_count', 'units', 'items', 'subtotal', 'delivery_fee',
            'tax', 'total', 'planted_error', 'has_rule', 'expected_rule', 'outcome', 'flagged', 'status_after',
            'rules_triggered', 'messages', 'validation_ms', 'event_draft_at', 'event_submitted_at', 'event_final_at',
            'event_final_status', 'events_json']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            ev = r['events'] or []
            sub = next((e['at'] for e in ev if e['to'] == 'submitted'), '')
            w.writerow([r['order_no'], r['seq'], r['sim_day'], r['company'], r['region'] or '', r['line_count'], r['units'],
                        '; '.join(f"{i.get('sku')} x {i.get('qty')}" + (f" @ {i['unit_price']}" if 'unit_price' in i else f" ({i.get('problem')})")
                                  for i in r['items']),
                        r['subtotal'], r['delivery_fee'], r['tax'], r['total'], r['planted_error'],
                        'Yes' if r['rule_targeted'] else 'No', r['expected_rule'] or '', r['outcome'],
                        'Yes' if r['flagged'] else 'No', r['status_after'], '; '.join(r['rules_triggered']),
                        ' | '.join(r['messages']), r['validation_ms'], ev[0]['at'] if ev else '', sub,
                        ev[-1]['at'] if ev else '', ev[-1]['to'] if ev else '', json.dumps(ev)])


def rng(vals):
    return {'min': min(vals), 'max': max(vals), 'values': vals}


metrics = {'replicates': {}, 'run_ids': {}}
for rep, run, seed in REPS:
    rows = json.loads((SIM / 'raw' / f'run{run}_replicate{rep}.json').read_text())
    assert len(rows) == 500
    metrics['replicates'][rep] = analyse(rows)
    metrics['run_ids'][rep] = {'run_id': run, 'seed': seed}
    order_csv(rows, SIM / f'replicate{rep}_orders.csv')

R = metrics['replicates']
key = lambda f: rng([f(R[k]) for k in (1, 2, 3)])
metrics['replicate_range'] = {
    'accuracy_all': key(lambda m: m['confusion_all_errors']['accuracy']['pct']),
    'precision_all': key(lambda m: m['confusion_all_errors']['precision']['pct']),
    'recall_all': key(lambda m: m['confusion_all_errors']['recall']['pct']),
    'specificity_all': key(lambda m: m['confusion_all_errors']['specificity']['pct']),
    'f1_all': key(lambda m: m['confusion_all_errors']['f1_pct']),
    'false_alarm_rate': key(lambda m: m['confusion_all_errors']['false_alarm_rate']['pct']),
    'accuracy_targeted': key(lambda m: m['confusion_rule_targeted']['accuracy']['pct']),
    'recall_targeted': key(lambda m: m['confusion_rule_targeted']['recall']['pct']),
    'precision_targeted': key(lambda m: m['confusion_rule_targeted']['precision']['pct']),
    'f1_targeted': key(lambda m: m['confusion_rule_targeted']['f1_pct']),
    'no_rule_detection': key(lambda m: m['no_rule_detection']['pct']),
    'validation_ms_mean': key(lambda m: m['validation_ms']['mean']),
    'validation_ms_median': key(lambda m: m['validation_ms']['median']),
    'validation_ms_p95': key(lambda m: m['validation_ms']['p95']),
    'mandatory_completion': key(lambda m: m['mandatory_completion_reaching_approval']['pct']),
}

# sensitivity: replays of run 5 under each factor and history length
sens_rows = json.loads((SENS / 'raw' / 'runs8to13_replays_of_run5.json').read_text())
sens = []
for run in sorted({r['run_id'] for r in sens_rows}):
    rs = [r for r in sens_rows if r['run_id'] == run]
    clean = [r for r in rs if r['planted_error'] == 'clean']
    typo = [r for r in rs if r['planted_error'] == 'qty_typo']
    err = [r for r in rs if r['planted_error'] != 'clean']
    c = confusion(err, clean)
    sens.append({
        'run_id': run, 'factor': float(rs[0]['factor']), 'history_orders': rs[0]['history'],
        'clean_flagged_by_unusual_quantity': prop(sum('unusual_quantity' in r['rules_triggered'] for r in clean), len(clean)),
        'clean_false_alarm_rate_all_rules': c['false_alarm_rate'],
        'typo_detection': prop(sum(r['flagged'] for r in typo), len(typo)),
        'unusual_quantity_fires_total': sum('unusual_quantity' in r['rules_triggered'] for r in rs),
        'accuracy_all': c['accuracy'], 'recall_all': c['recall'],
    })
for s in sens:
    ms = [float(r['validation_ms']) for r in sens_rows if r['run_id'] == s['run_id']]
    s['validation_ms_mean'] = round(st.mean(ms), 2)
    s['validation_ms_median'] = round(st.median(ms), 2)
    s['validation_ms_mean_by_block_of_100'] = [round(st.mean(ms[i:i + 100]), 2) for i in range(0, len(ms), 100)]
metrics['sensitivity'] = sens
with open(SENS / 'sensitivity_results.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['run_id', 'factor', 'history_orders', 'clean_flagged_by_unusual_quantity', 'clean_false_alarm_rate_pct',
                'fa_ci95_low', 'fa_ci95_high', 'typo_detected', 'typo_detection_pct', 'typo_ci95_low', 'typo_ci95_high',
                'unusual_quantity_fires_total', 'accuracy_all_pct', 'recall_all_pct'])
    for s in sens:
        w.writerow([s['run_id'], s['factor'], s['history_orders'], s['clean_flagged_by_unusual_quantity']['k'],
                    s['clean_false_alarm_rate_all_rules']['pct'], *s['clean_false_alarm_rate_all_rules']['ci95'],
                    s['typo_detection']['k'], s['typo_detection']['pct'], *s['typo_detection']['ci95'],
                    s['unusual_quantity_fires_total'], s['accuracy_all']['pct'], s['recall_all']['pct']])

(HERE / 'metrics_final.json').write_text(json.dumps(metrics, indent=1, ensure_ascii=False))

for rep in (1, 2, 3):
    m = R[rep]
    a, t = m['confusion_all_errors'], m['confusion_rule_targeted']
    print(f"rep {rep}: ALL tp{a['tp']} fn{a['fn']} fp{a['fp']} tn{a['tn']} acc {a['accuracy']['pct']} {a['accuracy']['ci95']} "
          f"prec {a['precision']['pct']} rec {a['recall']['pct']} spec {a['specificity']['pct']} f1 {a['f1_pct']} | "
          f"TGT acc {t['accuracy']['pct']} rec {t['recall']['pct']} f1 {t['f1_pct']} | norule {m['no_rule_detection']} | "
          f"ms {m['validation_ms']} | mand {m['mandatory_completion_reaching_approval']} | fa {m['false_alarm_reasons']}")
for s in sens:
    print(s['factor'], s['history_orders'], s['clean_flagged_by_unusual_quantity']['k'], s['clean_false_alarm_rate_all_rules']['pct'],
          s['typo_detection']['k'], s['accuracy_all']['pct'])
