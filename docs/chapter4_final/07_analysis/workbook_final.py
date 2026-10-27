"""Builds Verity_Simulation_Data_Final.xlsx.

Starts from the run 4 workbook (docs/chapter4/Verity_Simulation_Data.xlsx), whose sheets are copied unchanged,
and adds for each replicate of the final simulation a raw sheet ("R1 Orders") and a summary sheet ("R1 Summary")
whose figures are live formulas over the raw sheet, then a "Replicate range" sheet and a "Sensitivity" sheet.
Run the xlsx skill's recalc.py afterwards so cached values are stored.
"""
import json
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = Path(__file__).parent
ROOT = HERE.parent
RUN4 = ROOT.parent / 'chapter4' / 'Verity_Simulation_Data.xlsx'
OUT = HERE / 'Verity_Simulation_Data_Final.xlsx'
m = json.loads((HERE / 'metrics_final.json').read_text())

F = 'Arial'
H = Font(name=F, bold=True, color='FFFFFF')
B = Font(name=F, bold=True)
N = Font(name=F)
NOTE = Font(name=F, italic=True, color='595959', size=9)
HEAD_FILL = PatternFill('solid', fgColor='0F3D3E')
thin = Side(style='thin', color='CFD4CD')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
NGN = '"₦"#,##0.00'
PCT = '0.0%'
Z = '1.959964'

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
RULES = ['mandatory', 'sku', 'quantity', 'stock', 'customer_status', 'pricing', 'delivery', 'duplicate', 'unusual_quantity']
RULE_LABEL = {'mandatory': 'Mandatory fields', 'sku': 'SKU and product active', 'quantity': 'Quantity limits',
              'stock': 'Stock availability', 'customer_status': 'Customer status', 'pricing': 'Pricing',
              'delivery': 'Delivery date and address', 'duplicate': 'Duplicate order', 'unusual_quantity': 'Unusual quantity'}
SEV = {'duplicate': 'Warning', 'unusual_quantity': 'Warning'}


def header(ws, row, cols, start=1):
    for i, c in enumerate(cols):
        cell = ws.cell(row=row, column=start + i, value=c)
        cell.font, cell.fill, cell.alignment, cell.border = H, HEAD_FILL, Alignment(wrap_text=True, vertical='center'), BOX


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def wilson(k, n, low=True):
    p = f'({k}/{n})'
    sign = '-' if low else '+'
    return (f'=IF({n}=0,"",({p}+{Z}^2/(2*{n}){sign}{Z}*SQRT({p}*(1-{p})/{n}+{Z}^2/(4*{n}^2)))/(1+{Z}^2/{n}))')


wb = load_workbook(RUN4)
run4_sheets = list(wb.sheetnames)
wsr = wb['README']
r0 = wsr.max_row + 2
add = [
    ('Final simulation, three replicates (added; the run 4 sheets above are unchanged)', B),
    ('R1, R2 and R3 are runs 5, 6 and 7 of run_simulation_final with seeds 0.42, 0.43 and 0.44. Replicate 1 is the headline result.', N),
    ('Each run has 500 orders: 15 planted error types × 20 orders, plus 200 clean orders, one error per order, automatic approval off.', N),
    ('12 types are targeted by a rule. Wrong but valid product, plausible quantity typing slip and wrong saved address have no rule.', N),
    ('Rn Orders: one row per order. Columns Z to AH hold 1 when that rule fired. Rn Summary: every figure is a formula over Rn Orders.', N),
    ('Intervals are 95 percent Wilson score intervals. SD is the sample standard deviation (STDEV.S). Percentiles use PERCENTILE.INC.', N),
    ('Validation time is the clock time of submit_order inside the database, which recalculates, validates and records the status change.', N),
    ('Replicate range: minimum and maximum across the three summaries. Sensitivity: replays of replicate 1 under other unusual-quantity settings.', N),
]
for i, (t, f) in enumerate(add):
    wsr.cell(row=r0 + i, column=1, value=t).font = Font(name=F, bold=f.bold)

ORD_COLS = ['Seq', 'Order no.', 'Simulated day', 'Company', 'Region', 'Lines', 'Units', 'Items (SKU x qty @ unit price)',
            'Subtotal (₦)', 'Delivery fee (₦)', 'Tax (₦)', 'Total (₦)', 'Planted error', 'Has rule', 'Expected rule',
            'Outcome', 'Flagged', 'Status after submit', 'Rules triggered', 'Messages shown', 'Validation time (ms)',
            'Draft event at', 'Submitted event at', 'Last event at', 'Last status'] + [f'Rule: {r}' for r in RULES] + ['Delivery date given']
SUMMARY_CELLS = {}

for rep in (1, 2, 3):
    run = m['run_ids'][str(rep)]['run_id']
    rows = json.loads((ROOT / '03_simulation' / 'raw' / f'run{run}_replicate{rep}.json').read_text())
    name = f'R{rep} Orders'
    wo = wb.create_sheet(name)
    header(wo, 1, ORD_COLS)
    for i, r in enumerate(rows, 2):
        ev = r['events'] or []
        sub = next((e['at'] for e in ev if e['to'] == 'submitted'), '')
        items = '; '.join(f"{x.get('sku')} x {x.get('qty')}" + (f" @ {float(x['unit_price']):,.0f}" if 'unit_price' in x else f" ({x.get('problem')})")
                          for x in r['items'])
        vals = [r['seq'], r['order_no'], r['sim_day'], r['company'], r['region'] or '(none)', r['line_count'], r['units'], items,
                float(r['subtotal']), float(r['delivery_fee']), float(r['tax']), float(r['total']), LABEL[r['planted_error']],
                'Yes' if r['rule_targeted'] else 'No', r['expected_rule'] or '', r['outcome'], f'=IF(P{i}="pass","No","Yes")',
                r['status_after'], ', '.join(r['rules_triggered']), ' | '.join(r['messages']), float(r['validation_ms']),
                ev[0]['at'] if ev else '', sub, ev[-1]['at'] if ev else '', ev[-1]['to'] if ev else ''] + \
               [1 if x in r['rules_triggered'] else 0 for x in RULES] + ['Yes' if r['input'].get('date_offset') is not None else 'No']
        for j, v in enumerate(vals, 1):
            wo.cell(row=i, column=j, value=v).font = N
        for col in (9, 10, 11, 12):
            wo.cell(row=i, column=col).number_format = NGN
        wo.cell(row=i, column=21).number_format = '0.000'
    last = len(rows) + 1
    widths(wo, [6, 11, 9, 30, 15, 7, 7, 46, 14, 13, 12, 14, 34, 8, 15, 9, 8, 18, 30, 60, 11, 30, 30, 30, 16] + [9] * 9 + [10])
    wo.freeze_panes = 'C2'
    t = Table(displayName=f'R{rep}Orders', ref=f'A1:{get_column_letter(len(ORD_COLS))}{last}')
    t.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=True)
    wo.add_table(t)

    q = lambda col: f"'{name}'!${col}$2:${col}${last}"
    M, NN, P, Q, R, U, E, Fc, AI = q('M'), q('N'), q('P'), q('Q'), q('R'), q('U'), q('E'), q('F'), q('AI')
    rule_col = {r: q(get_column_letter(26 + k)) for k, r in enumerate(RULES)}

    ws = wb.create_sheet(f'R{rep} Summary')
    seed = m['run_ids'][str(rep)]['seed']
    ws['A1'] = f'Replicate {rep} (database run {run}, seed {seed}). Every figure below is a formula over the {name} sheet.'
    ws['A1'].font = B

    # A. outcomes by group
    ws['A3'] = 'A. Outcome of each group'
    ws['A3'].font = B
    header(ws, 4, ['Group', 'Orders', 'Passed', 'Warned', 'Blocked'])
    groups = [('Clean orders', f'{M},"Clean order (no error)"'),
              ('Errors with a rule', f'{M},"<>Clean order (no error)",{NN},"Yes"'),
              ('Errors without a rule', f'{M},"<>Clean order (no error)",{NN},"No"')]
    for k, (g, crit) in enumerate(groups, 5):
        ws.cell(row=k, column=1, value=g)
        ws.cell(row=k, column=2, value=f'=COUNTIFS({crit})')
        for c, o in ((3, 'pass'), (4, 'warn'), (5, 'fail')):
            ws.cell(row=k, column=c, value=f'=COUNTIFS({crit},{P},"{o}")')
    ws.cell(row=8, column=1, value='Total').font = B
    for c in 'BCDE':
        ws[f'{c}8'] = f'=SUM({c}5:{c}7)'
        ws[f'{c}8'].font = B

    # B and C. confusion matrices with measures and Wilson intervals
    def matrix(top, title, extra):
        ws.cell(row=top, column=1, value=title).font = B
        header(ws, top + 1, ['', 'Flagged', 'Passed', 'Total'])
        ws.cell(row=top + 2, column=1, value='Order has an error').font = B
        ws.cell(row=top + 2, column=2, value=f'=COUNTIFS({M},"<>Clean order (no error)"{extra},{Q},"Yes")')
        ws.cell(row=top + 2, column=3, value=f'=COUNTIFS({M},"<>Clean order (no error)"{extra},{Q},"No")')
        ws.cell(row=top + 3, column=1, value='Clean order').font = B
        ws.cell(row=top + 3, column=2, value=f'=COUNTIFS({M},"Clean order (no error)",{Q},"Yes")')
        ws.cell(row=top + 3, column=3, value=f'=COUNTIFS({M},"Clean order (no error)",{Q},"No")')
        for rr in (top + 2, top + 3):
            ws.cell(row=rr, column=4, value=f'=B{rr}+C{rr}')
        tp, fn, fp, tn = f'B{top + 2}', f'C{top + 2}', f'B{top + 3}', f'C{top + 3}'
        header(ws, top + 5, ['Measure', 'Value', '95% CI low', '95% CI high', 'Definition'])
        meas = [('Accuracy', f'({tp}+{tn})', f'({tp}+{fn}+{fp}+{tn})', '(TP+TN) / all orders'),
                ('Precision', tp, f'({tp}+{fp})', 'TP / (TP+FP)'),
                ('Recall (detection rate)', tp, f'({tp}+{fn})', 'TP / (TP+FN)'),
                ('Specificity', tn, f'({tn}+{fp})', 'TN / (TN+FP)'),
                ('False-alarm rate', fp, f'({fp}+{tn})', 'FP / (FP+TN)')]
        cells = {}
        for k, (nm, num, den, d) in enumerate(meas):
            rr = top + 6 + k
            ws.cell(row=rr, column=1, value=nm).font = B
            ws.cell(row=rr, column=2, value=f'={num}/{den}').number_format = PCT
            ws.cell(row=rr, column=3, value=wilson(num, den, True)).number_format = PCT
            ws.cell(row=rr, column=4, value=wilson(num, den, False)).number_format = PCT
            ws.cell(row=rr, column=5, value=d).font = NOTE
            cells[nm] = f'B{rr}'
        rr = top + 6 + len(meas)
        ws.cell(row=rr, column=1, value='F1 score').font = B
        pr, rc = cells['Precision'], cells['Recall (detection rate)']
        ws.cell(row=rr, column=2, value=f'=2*{pr}*{rc}/({pr}+{rc})').number_format = PCT
        ws.cell(row=rr, column=5, value='Harmonic mean of precision and recall. No Wilson interval, F1 is not a single proportion.').font = NOTE
        cells['F1 score'] = f'B{rr}'
        return cells, rr

    all_cells, end = matrix(10, 'B. Primary measure: all 300 erroneous orders against the 200 clean orders', '')
    tgt_cells, end = matrix(end + 2, 'C. Secondary measure: the 240 rule-targeted erroneous orders against the 200 clean orders', f',{NN},"Yes"')

    # D. detection by type
    top = end + 2
    ws.cell(row=top, column=1, value='D. Detection by planted error type').font = B
    header(ws, top + 1, ['Planted error', 'Has rule', 'Expected rule', 'Orders', 'Blocked', 'Warned', 'Passed', 'Flagged',
                         'Detection rate', '95% CI low', '95% CI high', 'Caught by expected rule'])
    for k, (key, lab) in enumerate(LABEL.items()):
        rr = top + 2 + k
        exp = {'bad_sku': 'sku', 'inactive_product': 'sku', 'missing_address': 'mandatory', 'missing_date': 'mandatory',
               'past_date': 'delivery', 'qty_below_min': 'quantity', 'qty_above_max': 'quantity', 'fractional_qty': 'quantity',
               'over_stock': 'stock', 'duplicate': 'duplicate', 'inactive_customer': 'customer_status', 'stale_price': 'pricing'}.get(key)
        vals = [lab, 'Yes' if exp else ('No' if key != 'clean' else ''), exp or '', f'=COUNTIF({M},A{rr})',
                f'=COUNTIFS({M},A{rr},{P},"fail")', f'=COUNTIFS({M},A{rr},{P},"warn")', f'=COUNTIFS({M},A{rr},{P},"pass")',
                f'=E{rr}+F{rr}', f'=IF(D{rr}=0,"",H{rr}/D{rr})', wilson(f'H{rr}', f'D{rr}', True), wilson(f'H{rr}', f'D{rr}', False),
                f'=COUNTIFS({M},A{rr},{rule_col[exp]},1)' if exp else '']
        for j, v in enumerate(vals, 1):
            ws.cell(row=rr, column=j, value=v)
        for c in (9, 10, 11):
            ws.cell(row=rr, column=c).number_format = PCT
    end = top + 2 + len(LABEL)
    ws.cell(row=end, column=1, value='For the clean row the detection rate is the false-alarm rate.').font = NOTE

    # E. rule activity
    top = end + 2
    ws.cell(row=top, column=1, value='E. Rule activity and false alarms').font = B
    header(ws, top + 1, ['Rule', 'Severity', 'Orders it fired on', 'On clean orders (false alarms)', 'False alarms per clean order',
                         '95% CI low', '95% CI high'])
    for k, rule in enumerate(RULES):
        rr = top + 2 + k
        vals = [RULE_LABEL[rule], SEV.get(rule, 'Blocking'), f'=SUM({rule_col[rule]})',
                f'=COUNTIFS({M},"Clean order (no error)",{rule_col[rule]},1)',
                f'=D{rr}/COUNTIF({M},"Clean order (no error)")',
                wilson(f'D{rr}', f'COUNTIF({M},"Clean order (no error)")', True),
                wilson(f'D{rr}', f'COUNTIF({M},"Clean order (no error)")', False)]
        for j, v in enumerate(vals, 1):
            ws.cell(row=rr, column=j, value=v)
        for c in (5, 6, 7):
            ws.cell(row=rr, column=c).number_format = PCT
    end = top + 2 + len(RULES)

    # F. timing
    top = end + 1
    ws.cell(row=top, column=1, value='F. Validation time (ms), clock time of submit_order inside the database').font = B
    header(ws, top + 1, ['Statistic', 'Value'])
    stats = [('Orders measured', f'=COUNT({U})'), ('Mean', f'=AVERAGE({U})'), ('Sample SD (STDEV.S)', f'=_xlfn.STDEV.S({U})'),
             ('Median', f'=MEDIAN({U})'), ('95th percentile (PERCENTILE.INC)', f'=_xlfn.PERCENTILE.INC({U},0.95)'),
             ('Minimum', f'=MIN({U})'), ('Maximum', f'=MAX({U})')]
    tcells = {}
    for k, (nm, f) in enumerate(stats):
        rr = top + 2 + k
        ws.cell(row=rr, column=1, value=nm)
        ws.cell(row=rr, column=2, value=f).number_format = '0' if k == 0 else '0.00'
        tcells[nm] = f'B{rr}'
    rr = top + 2 + len(stats)
    ws.cell(row=rr, column=1, value='Mean of orders 1-100, 101-200, 201-300, 301-400, 401-500').font = B
    for b in range(5):
        ws.cell(row=rr, column=2 + b, value=f"=AVERAGE('{name}'!$U${2 + 100 * b}:$U${101 + 100 * b})").number_format = '0.00'
    end = rr

    # G. mandatory-field completion
    top = end + 2
    ws.cell(row=top, column=1, value='G. Mandatory-field completion among orders reaching approval (status pending_approval)').font = B
    ws.cell(row=top + 1, column=1, value='Orders reaching approval')
    ws.cell(row=top + 1, column=2, value=f'=COUNTIF({R},"pending_approval")')
    ws.cell(row=top + 2, column=1, value='With address, region, delivery date and at least one line')
    ws.cell(row=top + 2, column=2, value=f'=COUNTIFS({R},"pending_approval",{E},"<>(none)",{Fc},">0",{AI},"Yes")')
    ws.cell(row=top + 3, column=1, value='Completion')
    ws.cell(row=top + 3, column=2, value=f'=B{top + 2}/B{top + 1}').number_format = PCT
    ws.cell(row=top + 3, column=3, value=wilson(f'B{top + 2}', f'B{top + 1}', True)).number_format = PCT
    ws.cell(row=top + 3, column=4, value=wilson(f'B{top + 2}', f'B{top + 1}', False)).number_format = PCT
    widths(ws, [44, 12, 12, 14, 14, 14, 12, 10, 13, 11, 11, 14])
    SUMMARY_CELLS[rep] = {'sheet': f'R{rep} Summary', 'all': all_cells, 'tgt': tgt_cells, 'time': tcells,
                          'mand': f'B{top + 3}', 'norule_flag': 'D7', 'norule_n': 'B7'}
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and c.font.name != F:
                c.font = Font(name=F, bold=c.font.bold, italic=c.font.italic, color=c.font.color, size=c.font.sz)

# replicate range
wrr = wb.create_sheet('Replicate range')
wrr['A1'] = 'Key measures in each replicate and their range. Every value is a reference to an Rn Summary sheet.'
wrr['A1'].font = B
header(wrr, 3, ['Measure', 'Replicate 1 (headline)', 'Replicate 2', 'Replicate 3', 'Minimum', 'Maximum'])
measures = [('Accuracy, all errors', 'all', 'Accuracy', PCT), ('Precision, all errors', 'all', 'Precision', PCT),
            ('Recall, all errors', 'all', 'Recall (detection rate)', PCT), ('Specificity', 'all', 'Specificity', PCT),
            ('False-alarm rate', 'all', 'False-alarm rate', PCT), ('F1, all errors', 'all', 'F1 score', PCT),
            ('Accuracy, rule-targeted errors', 'tgt', 'Accuracy', PCT), ('Precision, rule-targeted errors', 'tgt', 'Precision', PCT),
            ('Recall, rule-targeted errors', 'tgt', 'Recall (detection rate)', PCT), ('F1, rule-targeted errors', 'tgt', 'F1 score', PCT),
            ('Validation time mean (ms)', 'time', 'Mean', '0.00'), ('Validation time median (ms)', 'time', 'Median', '0.00'),
            ('Validation time 95th percentile (ms)', 'time', '95th percentile (PERCENTILE.INC)', '0.00'),
            ('Validation time sample SD (ms)', 'time', 'Sample SD (STDEV.S)', '0.00'),
            ('Mandatory-field completion', 'mand', None, PCT), ('Flagged errors without a rule', 'norule', None, PCT)]
for k, (nm, grp, key, fmt) in enumerate(measures, 4):
    wrr.cell(row=k, column=1, value=nm)
    for rep in (1, 2, 3):
        s = SUMMARY_CELLS[rep]
        if grp == 'mand':
            ref = f"='{s['sheet']}'!{s['mand']}"
        elif grp == 'norule':
            ref = f"=('{s['sheet']}'!D7+'{s['sheet']}'!E7)/'{s['sheet']}'!B7"
        else:
            ref = f"='{s['sheet']}'!{s[grp][key]}"
        wrr.cell(row=k, column=1 + rep, value=ref).number_format = fmt
    wrr.cell(row=k, column=5, value=f'=MIN(B{k}:D{k})').number_format = fmt
    wrr.cell(row=k, column=6, value=f'=MAX(B{k}:D{k})').number_format = fmt
widths(wrr, [40, 20, 14, 14, 12, 12])

# sensitivity (values exported from the replay runs; rates are formulas)
wsn = wb.create_sheet('Sensitivity')
wsn['A1'] = 'Unusual-quantity sensitivity on replicate 1. Each row is a replay of run 5 with the same 500 orders. For discussion only; the live factor stays at 3.'
wsn['A1'].font = B
header(wsn, 3, ['Run', 'Factor (x customer average)', 'Earlier orders per customer', 'Clean orders', 'Clean flagged by unusual quantity',
                'Clean flagged by any rule', 'False-alarm rate', '95% CI low', '95% CI high', 'Typo orders', 'Typos flagged',
                'Typo detection rate', '95% CI low', '95% CI high', 'Mean validation time (ms)'])
for k, s in enumerate(m['sensitivity'], 4):
    vals = [s['run_id'], s['factor'], s['history_orders'], 200, s['clean_flagged_by_unusual_quantity']['k'],
            s['clean_false_alarm_rate_all_rules']['k'], f'=F{k}/D{k}', wilson(f'F{k}', f'D{k}', True), wilson(f'F{k}', f'D{k}', False),
            s['typo_detection']['n'], s['typo_detection']['k'], f'=K{k}/J{k}', wilson(f'K{k}', f'J{k}', True), wilson(f'K{k}', f'J{k}', False),
            s['validation_ms_mean']]
    for j, v in enumerate(vals, 1):
        wsn.cell(row=k, column=j, value=v)
    for c in (7, 8, 9, 12, 13, 14):
        wsn.cell(row=k, column=c).number_format = PCT
wsn.cell(row=4 + len(m['sensitivity']) + 1, column=1,
         value='Source: runs 8 to 13 in simulation_final_orders (04_sensitivity/raw/runs8to13_replays_of_run5.json). Run 8 reproduces run 5 exactly.').font = NOTE
widths(wsn, [6, 12, 12, 9, 14, 12, 11, 10, 10, 9, 9, 11, 10, 10, 12])

for ws in wb.worksheets:
    if ws.title in run4_sheets and ws.title != 'README':
        continue
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and c.font.name != F:
                c.font = Font(name=F, bold=c.font.bold, italic=c.font.italic, color=c.font.color, size=c.font.sz)
wb.save(OUT)
print('saved', OUT, wb.sheetnames)
