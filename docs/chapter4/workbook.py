"""Builds Verity_Simulation_Data.xlsx from simulation_orders.json.
Summary sheets use formulas over the Orders sheet, so they stay correct if a
row is corrected. Run scripts/recalc.py (xlsx skill) afterwards."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = Path(__file__).parent
rows = json.loads((HERE / 'simulation_orders.json').read_text())
m = json.loads((HERE / 'metrics.json').read_text())
LABEL = {c['key']: c['label'] for c in m['categories']}
TARGETED = {c['key'] for c in m['categories'] if c['targeted']}
RULE_LABEL = {r['rule']: r['label'] for r in m['rules']}

F = 'Arial'
H = Font(name=F, bold=True, color='FFFFFF')
B = Font(name=F, bold=True)
N = Font(name=F)
NOTE = Font(name=F, italic=True, color='595959', size=9)
INPUT = Font(name=F, color='0000FF')
HEAD_FILL = PatternFill('solid', fgColor='0F3D3E')
SUB_FILL = PatternFill('solid', fgColor='E3EEEC')
YELLOW = PatternFill('solid', fgColor='FFFF00')
thin = Side(style='thin', color='CFD4CD')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
NGN = '"₦"#,##0.00'
PCT = '0.0%'

wb = Workbook()


def header(ws, row, cols, start=1):
    for i, c in enumerate(cols):
        cell = ws.cell(row=row, column=start + i, value=c)
        cell.font, cell.fill, cell.alignment, cell.border = H, HEAD_FILL, Alignment(wrap_text=True, vertical='center'), BOX


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def style_all(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.font == Font() or c.font.name != F:
                c.font = Font(name=F, bold=c.font.bold, italic=c.font.italic, color=c.font.color, size=c.font.size or 11)


# ---------------------------------------------------------------- README
ws = wb.active
ws.title = 'README'
lines = [
    ('Verity – 500-order validation simulation (run 4, seed 0.42)', B),
    ('', N),
    ('What this is', B),
    ('500 customer orders were generated and pushed through the real Verity order functions (save_draft, submit_order) on the live database.', N),
    ('Each order carries either no error ("clean") or one planted error. The system did not know which; its validation result is compared with the truth.', N),
    ('The orders and the 20 customer accounts were rolled back after the run, so the live system was not changed. Only these result rows were kept.', N),
    ('All company names, people, e-mails and phone numbers are fictional. E-mails use the reserved .example domain.', N),
    ('', N),
    ('Sheets', B),
    ('Orders – one row per simulated order (raw data).', N),
    ('Customers – the 20 fictional customer companies, with counts calculated from Orders.', N),
    ('By error type – detection per planted error, calculated from Orders.', N),
    ('Confusion matrix – accuracy, precision, recall, specificity and F1, calculated from Orders.', N),
    ('Rules – how often each validation rule fired (counted when the run was analysed).', N),
    ('Timing – server validation time statistics, calculated from Orders.', N),
    ('Success criteria – project targets against the measured results.', N),
    ('Manual baseline – a template to record the manual-entry comparison needed for the error-reduction and speed criteria.', N),
    ('', N),
    ('Definitions', B),
    ('Outcome: pass = sent to approval; warn = passed but flagged for a person (duplicate or unusual quantity); fail = blocked, customer must fix.', N),
    ('Flagged = outcome is warn or fail.', N),
    ('Has rule = Yes if the error type is one a validation rule is designed to catch. No = realistic mistakes with no rule (wrong product, quantity typo, wrong address).', N),
    ('Validation time = time the database took to run submit_order for the order, in milliseconds.', N),
    ('Simulated day = the order\'s position in the run split into 10 equal blocks; it is not a real date.', N),
]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t)
    c.font = Font(name=F, bold=f.bold, size=14 if i == 1 else 11)
ws.column_dimensions['A'].width = 140

# ---------------------------------------------------------------- Orders
wo = wb.create_sheet('Orders')
cols = ['Seq', 'Simulated day', 'Company', 'Contact person', 'E-mail', 'Phone', 'Region', 'Lines', 'Units', 'Items (SKU × qty @ unit price)',
        'Subtotal (₦)', 'Delivery fee (₦)', 'Tax (₦)', 'Total (₦)', 'Planted error', 'Has rule', 'Outcome', 'Flagged',
        'Status after submit', 'Rules triggered', 'Messages shown', 'Validation time (ms)']
header(wo, 1, cols)
for i, r in enumerate(rows, 2):
    items = '; '.join(
        f"{x.get('sku') or '?'} × {x.get('qty')}" + (f" @ {x['unit_price']:,.0f}" if x.get('unit_price') is not None else ' (not in catalogue)')
        for x in r['items'])
    vals = [r['seq'], r['sim_day'], r['company'], r['contact'], r['email'], r['phone'], r['region'] or '(none)', r['line_count'], r['units'], items,
            r['subtotal'], r['delivery_fee'], r['tax'], r['total'], LABEL[r['planted_error']], 'Yes' if r['planted_error'] in TARGETED else 'No',
            r['outcome'], f'=IF(Q{i}="pass","No","Yes")', r['status_after'],
            ', '.join(RULE_LABEL.get(x, x) for x in r['rules_triggered']), ' | '.join(r['messages']), r['validation_ms']]
    for j, v in enumerate(vals, 1):
        c = wo.cell(row=i, column=j, value=v)
        c.font = N
    for col in (11, 12, 13, 14):
        wo.cell(row=i, column=col).number_format = NGN
    wo.cell(row=i, column=22).number_format = '0.00'
last = len(rows) + 1
widths(wo, [6, 9, 30, 20, 34, 13, 15, 7, 7, 46, 15, 13, 13, 15, 32, 9, 9, 9, 18, 36, 60, 12])
wo.freeze_panes = 'D2'
t = Table(displayName='Orders', ref=f'A1:V{last}')
t.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=True)
wo.add_table(t)
O = f"Orders!$O$2:$O${last}"
Q = f"Orders!$Q$2:$Q${last}"
P = f"Orders!$P$2:$P${last}"
C = f"Orders!$C$2:$C${last}"
NN = f"Orders!$N$2:$N${last}"
V = f"Orders!$V$2:$V${last}"

# ---------------------------------------------------------------- Customers
wc = wb.create_sheet('Customers')
header(wc, 1, ['Company', 'Contact person', 'E-mail', 'Phone', 'Region', 'Orders', 'Passed', 'Warned', 'Blocked', 'Order value (₦)'])
custs = {}
for r in rows:
    custs.setdefault(r['company'], r)
for i, (name, r) in enumerate(sorted(custs.items()), 2):
    reg = next((x['region'] for x in rows if x['company'] == name and x['region']), '')
    for j, v in enumerate([name, r['contact'], r['email'], r['phone'], reg,
                           f'=COUNTIF({C},A{i})', f'=COUNTIFS({C},A{i},{Q},"pass")', f'=COUNTIFS({C},A{i},{Q},"warn")',
                           f'=COUNTIFS({C},A{i},{Q},"fail")', f'=SUMIF({C},A{i},{NN})'], 1):
        wc.cell(row=i, column=j, value=v).font = N
    wc.cell(row=i, column=10).number_format = NGN
end = len(custs) + 1
tot = end + 1
wc.cell(row=tot, column=1, value='Total').font = B
for col in 'FGHIJ':
    c = wc[f'{col}{tot}']
    c.value = f'=SUM({col}2:{col}{end})'
    c.font = B
wc[f'J{tot}'].number_format = NGN
widths(wc, [32, 22, 38, 14, 16, 9, 9, 9, 9, 18])

# ---------------------------------------------------------------- By error type
we = wb.create_sheet('By error type')
header(we, 1, ['Planted error', 'Has rule', 'Orders', 'Blocked', 'Warned', 'Passed', 'Flagged', 'Detection rate', 'Note'])
cats = [c for c in m['categories']]
for i, c in enumerate(cats, 2):
    note = ''
    if c['key'] == 'clean':
        note = 'For clean orders the "detection rate" is a false-alarm rate; lower is better.'
    elif not c['targeted'] and c['flagged']:
        rules = ', '.join(f"{RULE_LABEL.get(k, k)} ×{v}" for k, v in c['incidental_rules'].items())
        note = f'Flagged only by unrelated rules: {rules}'
    vals = [c['label'], 'Yes' if c['targeted'] else 'No', f'=COUNTIF({O},A{i})', f'=COUNTIFS({O},A{i},{Q},"fail")',
            f'=COUNTIFS({O},A{i},{Q},"warn")', f'=COUNTIFS({O},A{i},{Q},"pass")', f'=D{i}+E{i}', f'=IF(C{i}=0,0,G{i}/C{i})', note]
    for j, v in enumerate(vals, 1):
        we.cell(row=i, column=j, value=v).font = N
    we.cell(row=i, column=8).number_format = PCT
endc = len(cats) + 1
r0 = endc + 1
we.cell(row=r0, column=1, value='Total').font = B
for col in 'CDEFG':
    we[f'{col}{r0}'] = f'=SUM({col}2:{col}{endc})'
    we[f'{col}{r0}'].font = B
widths(we, [36, 9, 9, 9, 9, 9, 9, 13, 70])

# ---------------------------------------------------------------- Confusion matrix
wm = wb.create_sheet('Confusion matrix')
wm['A1'] = 'Binary view: does the order contain an error, and did the system flag it (warn or fail)?'
wm['A1'].font = B


def matrix(top, title, err_cond):
    wm.cell(row=top, column=1, value=title).font = B
    header(wm, top + 1, ['', 'Flagged by system', 'Passed by system', 'Total'])
    # err_cond: criteria pair on the Has rule column ('*' for all errors, 'Yes' for rule-covered only)
    def cnt(flag, is_err):
        out = f'"{"pass" if not flag else "<>pass"}"'
        if is_err:
            if err_cond == 'all':
                return f'=COUNTIFS({O},"<>Clean order (no error)",{Q},{out})'
            return f'=COUNTIFS({O},"<>Clean order (no error)",{P},"Yes",{Q},{out})'
        return f'=COUNTIFS({O},"Clean order (no error)",{Q},{out})'
    r = top + 2
    wm.cell(row=r, column=1, value='Order has an error').font = B
    wm.cell(row=r, column=2, value=cnt(True, True))
    wm.cell(row=r, column=3, value=cnt(False, True))
    wm.cell(row=r, column=4, value=f'=B{r}+C{r}')
    wm.cell(row=r + 1, column=1, value='Clean order').font = B
    wm.cell(row=r + 1, column=2, value=cnt(True, False))
    wm.cell(row=r + 1, column=3, value=cnt(False, False))
    wm.cell(row=r + 1, column=4, value=f'=B{r + 1}+C{r + 1}')
    tp, fn, fp, tn = f'B{r}', f'C{r}', f'B{r + 1}', f'C{r + 1}'
    metrics = [
        ('Accuracy', f'=({tp}+{tn})/({tp}+{fn}+{fp}+{tn})', '(TP+TN) / all orders'),
        ('Precision', f'={tp}/({tp}+{fp})', 'of flagged orders, share that really had an error'),
        ('Recall (detection rate)', f'={tp}/({tp}+{fn})', 'of erroneous orders, share flagged'),
        ('Specificity', f'={tn}/({tn}+{fp})', 'of clean orders, share passed without a flag'),
        ('F1 score', f'=2*B{r + 4}*B{r + 5}/(B{r + 4}+B{r + 5})', 'harmonic mean of precision and recall'),
    ]
    for k, (name, f, desc) in enumerate(metrics):
        rr = r + 3 + k
        wm.cell(row=rr, column=1, value=name).font = B
        c = wm.cell(row=rr, column=2, value=f)
        c.number_format = PCT
        wm.cell(row=rr, column=3, value=desc).font = NOTE
    return r + 3 + len(metrics)


nxt = matrix(3, 'A. All 500 orders (every planted error, including those no rule targets)', 'all')
matrix(nxt + 2, 'B. Only error types a rule is designed for, plus all clean orders', 'yes')
widths(wm, [42, 18, 46, 10])

# ---------------------------------------------------------------- Rules
wr = wb.create_sheet('Rules')
header(wr, 1, ['Validation rule', 'Severity', 'Orders it fired on', 'On orders with a planted error', 'On clean orders (false alarms)', 'False-alarm share'])
for i, r in enumerate(m['rules'], 2):
    for j, v in enumerate([r['label'], 'Warning' if r['severity'] == 'warn' else 'Blocking', r['total'], r['on_errors'], r['on_clean'],
                           f'=IF(C{i}=0,0,E{i}/C{i})'], 1):
        wr.cell(row=i, column=j, value=v).font = N
    wr.cell(row=i, column=6).number_format = PCT
nr = len(m['rules']) + 3
wr.cell(row=nr, column=1, value='Counts taken from the "Rules triggered" column of Orders when the run was analysed (an order can trigger several rules).').font = NOTE
widths(wr, [28, 11, 18, 28, 28, 16])

# ---------------------------------------------------------------- Timing
wt = wb.create_sheet('Timing')
header(wt, 1, ['Statistic', 'Validation time (ms)'])
stats = [('Orders measured', f'=COUNT({V})'), ('Mean', f'=AVERAGE({V})'), ('Median', f'=MEDIAN({V})'),
         ('95th percentile', f'=PERCENTILE({V},0.95)'), ('Minimum', f'=MIN({V})'), ('Maximum', f'=MAX({V})'),
         ('Standard deviation', f'=STDEVP({V})'),
         ('Mean – passed orders', f'=AVERAGEIF({Q},"pass",{V})'), ('Mean – warned orders', f'=AVERAGEIF({Q},"warn",{V})'),
         ('Mean – blocked orders', f'=AVERAGEIF({Q},"fail",{V})')]
for i, (k, f) in enumerate(stats, 2):
    wt.cell(row=i, column=1, value=k).font = N
    c = wt.cell(row=i, column=2, value=f)
    c.number_format = '0' if i == 2 else '0.00'
h0 = len(stats) + 3
header(wt, h0, ['From (ms)', 'To (ms)', 'Orders'])
for k, b in enumerate(m['hist'], h0 + 1):
    wt.cell(row=k, column=1, value=b['from'])
    wt.cell(row=k, column=2, value=b['to'])
    wt.cell(row=k, column=3, value=f'=COUNTIFS({V},">="&A{k},{V},"<"&B{k})')
wt.cell(row=h0 + len(m['hist']) + 2, column=1, value='Measured inside the database (clock time around submit_order), Supabase Postgres 17, eu-west-1. Excludes network time to the browser.').font = NOTE
widths(wt, [26, 22, 10])

# ---------------------------------------------------------------- Success criteria
wsc = wb.create_sheet('Success criteria')
header(wsc, 1, ['Objective', 'Success criterion', 'Measured result', 'Status', 'Evidence / note'])
crit = [
    ('Build a digital order-processing system', '500 successful simulated orders', f'=COUNTA(Orders!$A$2:$A${last})&" orders processed"',
     'Met', 'Every order was saved, validated and routed by the live functions (Orders sheet).'),
    ('Validate orders automatically', '90% validation accuracy', "=TEXT('Confusion matrix'!B8,\"0.0%\")&\" on all orders; \"&TEXT('Confusion matrix'!B20,\"0.0%\")&\" on rule-covered errors\"",
     'Partly met', 'Below 90% when realistic mistakes with no rule are included; above 90% on the error types the rules cover. 32 of 33 false alarms came from the unusual-quantity warning.'),
    ('Reduce manual data-entry errors', '100% mandatory-field completion', '=TEXT(COUNTIFS(Orders!$S$2:$S$' + str(last) + ',"pending_approval",Orders!$G$2:$G$' + str(last) + ',"<>(none)")/COUNTIF(Orders!$S$2:$S$' + str(last) + ',"pending_approval"),"0%")&" of orders reaching approval had every mandatory field"',
     'Met', 'Orders missing a mandatory field cannot leave validation (blocked by the database).'),
    ('Reduce manual data-entry errors', '60% reduction in manual errors', 'Needs the manual baseline', 'Pending',
     "=\"Indicative only: the system flagged \"&TEXT('Confusion matrix'!B10,\"0.0%\")&\" of erroneous orders before approval. Record the baseline in the Manual baseline sheet to measure the real reduction.\""),
    ('Improve processing speed', '30–50% faster processing', "=TEXT(Timing!B4,\"0.0\")&\" ms median automatic validation per order\"", 'Pending',
     'Automatic checking is near-instant, but the criterion compares end-to-end staff time; needs the manual baseline.'),
]
for i, rowv in enumerate(crit, 2):
    for j, v in enumerate(rowv, 1):
        c = wsc.cell(row=i, column=j, value=v)
        c.font = N
        c.alignment = Alignment(wrap_text=True, vertical='top')
    st = wsc.cell(row=i, column=4)
    st.font = Font(name=F, bold=True, color={'Met': '1F7A4D', 'Partly met': '9A6200', 'Pending': '595959'}[rowv[3]])
widths(wsc, [32, 28, 44, 12, 70])

# ---------------------------------------------------------------- Manual baseline template
wbl = wb.create_sheet('Manual baseline')
wbl['A1'] = 'Manual-entry baseline – fill in the yellow cells (blue text). One row per sample order (about 30 recommended).'
wbl['A1'].font = B
wbl['A2'] = 'Time a person re-keying each order from its original Excel/WhatsApp/e-mail message, count the errors they make, then do the same order in Verity.'
wbl['A2'].font = NOTE
header(wbl, 4, ['Sample #', 'Source message', 'Manual: time (seconds)', 'Manual: errors made', 'Verity: time (seconds)', 'Verity: errors reaching approval', 'Time saved'])
for k in range(5, 35):
    wbl.cell(row=k, column=1, value=k - 4)
    for col in range(2, 7):
        c = wbl.cell(row=k, column=col)
        c.fill, c.font = YELLOW, INPUT
    wbl.cell(row=k, column=7, value=f'=IF(OR(C{k}="",E{k}="",C{k}=0),"",1-E{k}/C{k})').number_format = PCT
# example row
for col, v in zip(range(2, 7), ['WhatsApp message', 180, 1, 95, 0]):
    wbl.cell(row=5, column=col, value=v)
wbl.cell(row=36, column=1, value='Totals').font = B
for col in 'CDEF':
    wbl[f'{col}36'] = f'=SUM({col}5:{col}34)'
    wbl[f'{col}36'].font = B
wbl['A38'] = 'Error reduction'
wbl['A38'].font = B
wbl['C38'] = '=IF(D36=0,"",1-F36/D36)'
wbl['C38'].number_format = PCT
wbl['D38'] = 'target: at least 60%'
wbl['A39'] = 'Time saved'
wbl['A39'].font = B
wbl['C39'] = '=IF(C36=0,"",1-E36/C36)'
wbl['C39'].number_format = PCT
wbl['D39'] = 'target: 30–50%'
wbl['A41'] = 'Row 5 is an example; overwrite or clear it. Yellow cells are inputs; column G and rows 36–39 calculate themselves.'
wbl['A41'].font = NOTE
widths(wbl, [10, 26, 22, 20, 22, 30, 12])

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and (c.font is None or c.font.name != F):
                c.font = Font(name=F, bold=c.font.bold, italic=c.font.italic, color=c.font.color, size=c.font.sz)

out = HERE / 'Verity_Simulation_Data.xlsx'
wb.save(out)
print('saved', out)
