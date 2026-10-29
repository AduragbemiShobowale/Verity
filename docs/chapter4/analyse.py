"""Analysis of the 500-order validation simulation (Verity, run 4, seed 0.42).

Reads simulation_orders.json (exported from the simulation_orders table) and
writes metrics.json, which the chart and report builders read. Standard
library only.
"""
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
rows = json.loads((HERE / 'simulation_orders.json').read_text())

LABEL = {
    'clean': 'Clean order (no error)',
    'bad_sku': 'SKU not in catalogue',
    'missing_address': 'Missing delivery address',
    'missing_date': 'Missing delivery date',
    'past_date': 'Delivery date in the past',
    'qty_below_min': 'Quantity below minimum',
    'qty_above_max': 'Quantity above maximum',
    'fractional_qty': 'Fractional quantity',
    'over_stock': 'Quantity above available stock',
    'duplicate': 'Duplicate order',
    'inactive_product': 'Discontinued product',
    'wrong_product': 'Wrong (but valid) product chosen',
    'qty_typo': 'Plausible quantity typo (20 → 200)',
    'wrong_address': 'Wrong saved address chosen',
}
# the rule that is supposed to catch each planted error
EXPECTED_RULE = {
    'bad_sku': 'sku', 'inactive_product': 'sku', 'missing_address': 'mandatory', 'missing_date': 'mandatory',
    'past_date': 'delivery', 'qty_below_min': 'quantity', 'qty_above_max': 'quantity', 'fractional_qty': 'quantity',
    'over_stock': 'stock', 'duplicate': 'duplicate',
}
RULE_LABEL = {
    'mandatory': 'Mandatory fields', 'sku': 'SKU / product active', 'quantity': 'Quantity limits',
    'stock': 'Stock availability', 'pricing': 'Pricing', 'duplicate': 'Duplicate order',
    'delivery': 'Delivery date & address', 'unusual_quantity': 'Unusual quantity', 'customer_status': 'Customer status',
}

flagged = lambda r: r['outcome'] in ('fail', 'warn')
n = len(rows)
clean = [r for r in rows if r['planted_error'] == 'clean']
err = [r for r in rows if r['planted_error'] != 'clean']
tgt = [r for r in err if r['rule_targeted']]
untgt = [r for r in err if not r['rule_targeted']]


def confusion(errors, cleans):
    tp = sum(flagged(r) for r in errors)
    fn = len(errors) - tp
    fp = sum(flagged(r) for r in cleans)
    tn = len(cleans) - fp
    tot = tp + fn + fp + tn
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    return {
        'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn, 'n': tot,
        'accuracy': round(100 * (tp + tn) / tot, 1),
        'precision': round(100 * prec, 1),
        'recall': round(100 * rec, 1),
        'specificity': round(100 * tn / (tn + fp), 1) if tn + fp else 0,
        'f1': round(100 * 2 * prec * rec / (prec + rec), 1) if prec + rec else 0,
    }


# per planted-error category
cats = []
for key in LABEL:
    rs = [r for r in rows if r['planted_error'] == key]
    if not rs:
        continue
    exp = EXPECTED_RULE.get(key)
    right = sum(1 for r in rs if exp and exp in r['rules_triggered']) if exp else None
    incidental = [r for r in rs if flagged(r) and not (exp and exp in r['rules_triggered'])] if key != 'clean' else []
    cats.append({
        'key': key, 'label': LABEL[key], 'targeted': key in EXPECTED_RULE, 'n': len(rs),
        'blocked': sum(r['outcome'] == 'fail' for r in rs),
        'warned': sum(r['outcome'] == 'warn' for r in rs),
        'passed': sum(r['outcome'] == 'pass' for r in rs),
        'flagged': sum(flagged(r) for r in rs),
        'by_expected_rule': right,
        'incidental': len(incidental),
        'incidental_rules': dict(Counter(x for r in incidental for x in r['rules_triggered'])),
        'detection_rate': round(100 * sum(flagged(r) for r in rs) / len(rs), 1) if key != 'clean' else None,
        'pass_rate': round(100 * sum(not flagged(r) for r in rs) / len(rs), 1) if key == 'clean' else None,
    })

# why clean orders were flagged
fp_reasons = Counter(x for r in clean if flagged(r) for x in r['rules_triggered'])

# rules: how often each fired, on erroneous vs clean orders
rule_fires = defaultdict(lambda: {'total': 0, 'on_errors': 0, 'on_clean': 0, 'fail': 0, 'warn': 0})
for r in rows:
    for rule in r['rules_triggered']:
        d = rule_fires[rule]
        d['total'] += 1
        d['on_clean' if r['planted_error'] == 'clean' else 'on_errors'] += 1
rules = [{'rule': k, 'label': RULE_LABEL.get(k, k), **v} for k, v in sorted(rule_fires.items(), key=lambda kv: -kv[1]['total'])]
SEV = {'unusual_quantity': 'warn', 'duplicate': 'warn'}
for x in rules:
    x['severity'] = SEV.get(x['rule'], 'fail')

# timing
ms = sorted(r['validation_ms'] for r in rows)
pct = lambda p: round(ms[min(len(ms) - 1, int(round(p / 100 * (len(ms) - 1))))], 2)
timing = {'mean': round(st.mean(ms), 2), 'median': round(st.median(ms), 2), 'p95': pct(95), 'min': round(ms[0], 2),
          'max': round(ms[-1], 2), 'sd': round(st.pstdev(ms), 2),
          'by_outcome': {k: round(st.mean([r['validation_ms'] for r in rows if r['outcome'] == k]), 2) for k in ('pass', 'warn', 'fail')}}
bins = list(range(0, int(max(ms)) + 10, 5))
hist = [{'from': b, 'to': b + 5, 'n': sum(b <= v < b + 5 for v in ms)} for b in bins]
while hist and hist[-1]['n'] == 0:
    hist.pop()

# dataset description
vals = [r['total'] for r in rows if r['total'] is not None]
companies = Counter(r['company'] for r in rows)
regions = Counter(r['region'] or 'No address given' for r in rows)
passed_orders = [r for r in rows if r['status_after'] == 'pending_approval']
mandatory_ok = sum(1 for r in passed_orders if r['region'] and r['line_count'] > 0)

metrics = {
    'run': {'run_id': 4, 'seed': 0.42, 'orders': n, 'customers': len(companies), 'products': 12, 'categories': len(LABEL)},
    'groups': {'clean': len(clean), 'errors': len(err), 'targeted': len(tgt), 'untargeted': len(untgt)},
    'outcomes': dict(Counter(r['outcome'] for r in rows)),
    'outcomes_by_group': {
        g: dict(Counter(r['outcome'] for r in rs)) for g, rs in (('Clean orders', clean), ('Errors with a rule', tgt), ('Errors without a rule', untgt))
    },
    'confusion_all': confusion(err, clean),
    'confusion_targeted': confusion(tgt, clean),
    'categories': cats,
    'fp_reasons': dict(fp_reasons),
    'rules': rules,
    'timing': timing, 'hist': hist,
    'dataset': {
        'value_mean': round(st.mean(vals), 2), 'value_median': round(st.median(vals), 2),
        'value_min': round(min(vals), 2), 'value_max': round(max(vals), 2), 'value_total': round(sum(vals), 2),
        'lines_mean': round(st.mean(r['line_count'] for r in rows), 2),
        'units_mean': round(st.mean(r['units'] for r in rows), 1),
        'orders_per_customer': {'min': min(companies.values()), 'max': max(companies.values()), 'mean': round(n / len(companies), 1)},
        'by_region': dict(regions.most_common()),
        'by_company': dict(companies.most_common()),
    },
    'mandatory': {'passed_orders': len(passed_orders), 'complete': mandatory_ok,
                  'pct': round(100 * mandatory_ok / len(passed_orders), 1) if passed_orders else None},
    'statuses': dict(Counter(r['status_after'] for r in rows)),
}
(HERE / 'metrics.json').write_text(json.dumps(metrics, indent=1, ensure_ascii=False))

c = metrics['confusion_all']
print(f"orders {n} | clean {len(clean)} | targeted errors {len(tgt)} | untargeted {len(untgt)}")
print(f"ALL: acc {c['accuracy']} prec {c['precision']} rec {c['recall']} spec {c['specificity']} f1 {c['f1']} {c}")
print('TARGETED:', metrics['confusion_targeted'])
print('timing', timing)
print('fp reasons', dict(fp_reasons))
for x in cats:
    print(f"  {x['label']:<38} n={x['n']:>3} blocked={x['blocked']:>3} warned={x['warned']:>3} passed={x['passed']:>3} right_rule={x['by_expected_rule']} incidental={x['incidental']} {x['incidental_rules']}")
print('rules', [(x['rule'], x['total'], x['on_errors'], x['on_clean']) for x in rules])
print('mandatory', metrics['mandatory'], 'statuses', metrics['statuses'])
print('dataset', {k: v for k, v in metrics['dataset'].items() if k not in ('by_company',)})
