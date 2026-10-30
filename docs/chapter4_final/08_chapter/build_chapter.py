"""Builds Chapter_Four.docx and chapter_tables.xlsx. Every number is read from the Stage 1 files at build time.

  python3 build_chapter.py && python3 check_style.py
"""
import csv
import json
from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font as XFont

HERE = Path(__file__).parent
ROOT = HERE.parent
M = json.loads((ROOT / '07_analysis' / 'metrics_final.json').read_text())
R = M['replicates']
R1 = R['1']
RUN4 = json.loads((ROOT.parent / 'chapter4' / 'metrics.json').read_text())
FACTS = json.loads((ROOT / '01_system_facts' / 'system_facts.json').read_text())
MB = json.loads((ROOT / '05_baseline_pack' / 'session_data' / 'manual_vs_simulation_results.json').read_text())
FT = list(csv.DictReader(open(ROOT / '02_functional_tests' / 'functional_tests.csv', encoding='utf-8')))
RLS = list(csv.DictReader(open(ROOT / '02_functional_tests' / 'rls_results_2026-10-27.csv')))
STAT = list(csv.DictReader(open(ROOT / '01_system_facts' / 'order_statuses.csv')))
RULES = list(csv.DictReader(open(ROOT / '01_system_facts' / 'validation_rules_and_run4_coverage.csv')))
WORDING = '[EXACT CHAPTER ONE WORDING NEEDED]'

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for side in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, side, Cm(2.54))
st = doc.styles['Normal']
st.font.name = 'Times New Roman'
st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
for name, size in (('Heading 1', 14), ('Heading 2', 12), ('Heading 3', 11)):
    h = doc.styles[name]
    h.font.name, h.font.size, h.font.bold, h.font.color.rgb = 'Times New Roman', Pt(size), True, RGBColor(0, 0, 0)
    rf = h.element.rPr.rFonts
    for att in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
        rf.attrib.pop(qn(att), None)
    for att in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        rf.set(qn(att), 'Times New Roman')

XL = Workbook()
XL.remove(XL.active)
counters = {'table': 0, 'figure': 0}
TRACE = []


def para(text, style=None, italic=False, size=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=8):
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.5
    return p


def P(text):
    return para(text)


def H1(t):
    doc.add_heading(t, level=1)


def H2(t):
    doc.add_heading(t, level=2)


def H3(t):
    doc.add_heading(t, level=3)


def page_numbers():
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    for kind, text in (('begin', None), (None, 'PAGE'), ('end', None)):
        if kind:
            el = OxmlElement('w:fldChar')
            el.set(qn('w:fldCharType'), kind)
        else:
            el = OxmlElement('w:instrText')
            el.set(qn('xml:space'), 'preserve')
            el.text = text
        run._r.append(el)
    run.font.size = Pt(10)


def note_box(text):
    t = doc.add_table(rows=1, cols=1)
    t.style = 'Table Grid'
    c = t.rows[0].cells[0]
    shade(c, 'FFF6D5')
    c.text = ''
    r = c.paragraphs[0].add_run(text)
    r.italic, r.font.size = True, Pt(10)
    doc.add_paragraph()


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement('w:shd')
    s.set(qn('w:val'), 'clear')
    s.set(qn('w:color'), 'auto')
    s.set(qn('w:fill'), fill)
    tcPr.append(s)


def table(caption, headers, rows, source, widths=None, size=9.5):
    counters['table'] += 1
    n = counters['table']
    cap = para(f'Table 4.{n}: {caption}', align=WD_ALIGN_PARAGRAPH.LEFT, after=4)
    cap.runs[0].bold = True
    cap.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        r = c.paragraphs[0].add_run(str(h))
        r.bold, r.font.size = True, Pt(size)
        shade(c, 'D9E2E1')
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            cells[i].paragraphs[0].add_run(str(v)).font.size = Pt(size)
    if widths:
        t.autofit = False
        grid = t._tbl.tblGrid
        for gc, w in zip(grid.findall(qn('w:gridCol')), widths):
            gc.set(qn('w:w'), str(int(w * 567)))
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    para(f'Source: {source}', italic=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT, after=12)
    ws = XL.create_sheet(f'Table 4.{n}')
    ws.append([f'Table 4.{n}: {caption}'])
    ws['A1'].font = XFont(bold=True)
    ws.append(list(headers))
    for row in rows:
        ws.append([str(v) for v in row])
    ws.append([f'Source: {source}'])
    return f'Table 4.{n}'


def figure(path, caption, source):
    counters['figure'] += 1
    n = counters['figure']
    doc.add_picture(str(path), width=Cm(16))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = para(f'Figure 4.{n}: {caption}', align=WD_ALIGN_PARAGRAPH.LEFT, after=2)
    cap.runs[0].bold = True
    para(f'Source: {source}', italic=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT, after=12)


def pc(x):
    return f'{x:.1f}'


def ci(d):
    return f'{d["ci95"][0]:.1f} to {d["ci95"][1]:.1f}'


def naira(v):
    return f'₦{v:,.2f}'


def trace(number, meaning, where):
    TRACE.append([number, meaning, where])


A, T = R1['confusion_all_errors'], R1['confusion_rule_targeted']
RR = M['replicate_range']
BT = {t['key']: t for t in R1['by_type']}
RU = {r['rule']: r for r in R1['rules']}
TM = R1['validation_ms']
DS = R1['dataset']
NR = R1['no_rule_flag_on_planted_line']
SENS = {(s['factor'], s['history_orders']): s for s in M['sensitivity']}
ft_pass = sum(r['result'] == 'Pass' for r in FT)
ft_fail = [r for r in FT if r['result'] == 'Fail']
MW = 'Verity_Simulation_Data_Final.xlsx'

# =====================================================================================================================
page_numbers()
for txt in ('CHAPTER FOUR', 'RESULTS AND DISCUSSION'):
    tp = para(txt, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    tp.runs[0].bold = True
    tp.runs[0].font.size = Pt(14)
note_box('Note for the group. This chapter combines the questionnaire results, supplied by the client team, with the technical '
         'evaluation of the system and the simulation. The comparison with manual entry was run on a small scale and is reported as '
         'indicative. The speed criterion is reported as Scheduled. '
         'Delete this note before submission.')
H2('4.1 Introduction')
P('This chapter reports the evaluation of Verity, the intelligent order processing system developed in this project. It has two '
  'parts that are brought together in Section 4.6. Section 4.2 reports the questionnaire given to staff of logistics and '
  'distribution businesses and to business customers, before and after a demonstration of Verity. Sections 4.3 to 4.5 report the '
  'technical evaluation, namely the implemented system with its testing, and a controlled simulation in which orders with known '
  'planted errors were submitted to the live validation engine.')
P('The comparison with manual order entry was run on a small scale, with two participants and 40 orders, and its results are '
  'reported as indicative. The time a person spends entering an order in Verity was not measured, so the speed criterion is given '
  'the status Scheduled. All other figures in this '
  'chapter come from files and database queries produced during the evaluation, and each is listed with its source in the '
  'traceability table that accompanies the chapter.')

# =====================================================================================================================
import math
exec((HERE / 'section_questionnaire.py').read_text())

# =====================================================================================================================
H2('4.3 Implemented system and testing')
H3('4.3.1 System components and order lifecycle')
P('Verity is a web application with a React interface hosted on Vercel and a Supabase back end built on PostgreSQL 17. '
  'All business rules run inside the database as functions, and row-level security decides which records each signed-in user '
  'can read. Table 4.11 summarises the components that were built.')
table('Components of the implemented system', ['Component', 'What it does'],
      [['Customer portal', 'Registration, order entry from the catalogue or from an uploaded Excel or CSV sheet, order status, payment proof upload, delivery code'],
       ['Ops Desk', 'Approval queue with validation results, customer screening, cancellations and delivery overrides'],
       ['Finance', 'Payment proof verification, invoices, refunds and credit notes'],
       ['Warehouse', 'Picking, shortage handling, stock levels and new products held hidden until priced'],
       ['Dispatch and driver', 'Driver and vehicle assignment, delivery log with CSV download, delivery confirmation by customer code'],
       ['Administrator', 'Users and roles, prices, regions and settings such as automatic approval'],
       ['Database', f'{FACTS["status_count"]} order statuses, {FACTS["transition_count"]} permitted transitions, {FACTS["rule_count"]} validation rules, status history and audit log']],
      'Verity source code and database, docs/chapter4_final/01_system_facts.', widths=[4, 12])
trace(FACTS['status_count'], 'order statuses', '01_system_facts/system_facts.json status_count')
trace(FACTS['transition_count'], 'permitted transitions', '01_system_facts/system_facts.json transition_count')
P(f'Every order follows a lifecycle built from {FACTS["status_count"]} statuses, shown in Table 4.12. The database accepts '
  f'only the {FACTS["transition_count"]} transitions listed in its transition table, so an order cannot skip a step such as '
  'payment verification, and each change is written to the status history with the time and the user who made it.')
table('Order lifecycle statuses in order', ['No.', 'Status', 'Meaning'],
      [[r['position'], r['status'], r['meaning']] for r in STAT],
      'order_status type and order_transitions table, 01_system_facts/order_statuses.csv and state_machine_transitions.csv.', widths=[1.2, 4, 10.8])
H3('4.3.2 Validation rules')
P('Validation is carried out by nine rules that run every time a customer submits an order. Seven of them block the order '
  'until the customer corrects it and two raise a warning that sends the order to a person for review. Table 4.13 maps the '
  'nine rules to the seven checks set out in Table 2.1. The customer-details check is served by two rules, one for the account '
  'status and one for the delivery address, and the unusual-quantity rule is an addition that no check in Table 2.1 requires.')
DQ = {'Mandatory fields': 'Completeness', 'SKU': 'Accuracy', 'Quantity': 'Accuracy', 'Stock': 'Currency', 'Customer details': 'Completeness',
      'Pricing': 'Accuracy and consistency', 'Duplicate orders': 'Uniqueness'}
table('Validation rules mapped to the seven checks of Table 2.1', ['Rule', 'What it checks', 'Severity', 'Check in Table 2.1', 'Data quality dimension in Table 2.1'],
      [[r['rule'], r['check'], 'Blocking' if r['severity'] == 'blocking' else 'Warning', r['maps_to_seven_checks'].replace('(none; additional check)', 'None, an additional check'),
        DQ.get(r['maps_to_seven_checks'], 'None')] for r in RULES],
      '_validate function, 01_system_facts/validation_rules_and_run4_coverage.csv.', widths=[3.2, 6, 1.8, 2.6, 2.4])
H3('4.3.3 Functional testing')
P(f'Functional testing exercised the order lifecycle end to end against the live database while acting as each role. Every '
  f'test ran inside a transaction that was rolled back, so no test data remained. The fourteen cases of the earlier test run '
  f'were repeated and twelve new cases were added for inactive customers, stale prices, automatic approval, CSV import and '
  f'export, and webhooks. Table 4.14 lists all {len(FT)} cases. Of these, {ft_pass} passed and {len(ft_fail)} failed.')
trace(len(FT), 'functional test cases', '02_functional_tests/functional_tests.csv row count')
trace(ft_pass, 'functional tests passed', '02_functional_tests/functional_tests.csv result = Pass')
table('Functional test cases', ['No.', 'Test case', 'Expected result', 'Actual result', 'Result'],
      [[r['id'], r['test_case'], r['expected_result'], r['actual_result'], r['result']] for r in FT],
      'rolled-back tests run on 27 October 2026, 02_functional_tests/raw_test_output_2026-10-27.json, raw_warehouse_product_test_2026-10-27.txt and test_delivery_log_csv.mjs.',
      widths=[1.1, 4.2, 3.4, 5.9, 1.4], size=8.5)
P('Three results are failures and are reported as such. In case 16b the uploaded sheet quoted cement at ₦9,000 against a list '
  'price of ₦9,500. The upload reader ignores the price column and the line was saved at the list price, so the customer was '
  'charged correctly but was not told that the sheet was out of date. The pricing rule therefore guards against a price that '
  'changes after an order is saved, as case 16a shows, but not against an outdated price on an incoming sheet. Case 19 failed '
  'because the system has no CSV export of orders, and case 21 failed because no webhook is sent when an order changes status. '
  'The only CSV export that exists is the delivery log used by Dispatch. Case 20 was passed by running the application code '
  'that builds that file on the rows the database returned for the Dispatch account, and the browser download step itself was '
  'not exercised.')
H3('4.3.4 Access-control testing')
P('Access control was tested by querying the database directly as each role, bypassing the interface, so that the result '
  'shows what a user could reach even without the application screens. Table 4.15 gives the number of rows each account could '
  'read. Customers saw only their own company records and no product or audit rows, and the driver could read no '
  'business records at all. Attempts by a customer to change a price and to switch off automatic approval changed no rows.')
table('Rows visible to each account when querying the database directly',
      ['Account', 'Customers', 'Products', 'Orders', 'Invoices', 'Payments', 'Audit log', 'Simulation rows', 'Write attempt changed'],
      [[r['role_account'].split('@')[0] + ('' if 'verity' in r['role_account'] else ' (customer)'), r['customers'], r['products'], r['orders'], r['invoices'],
        r['payments'], r['audit_log'], r['simulation_orders'], r['rows_changed_by_write'] or 'not tried'] for r in RLS],
      'row-level security check run on 27 October 2026, 02_functional_tests/rls_results_2026-10-27.csv and rls_check.sql.', size=8.5)
P('The settings table, which holds values such as the tax rate and the automatic-approval switch, was readable by every signed-in '
  'account including drivers and customers. It could not be changed by them, but it is wider read access than the other tables allow.')

H3('4.3.5 Manual end-to-end test')
WT = json.loads((ROOT / '02_functional_tests' / 'manual_walkthrough_2026-10-30.json').read_text())
import datetime as _dt
_f = lambda x: _dt.datetime.fromisoformat(x)
def _mmss(td):
    sec = int(round(td.total_seconds()))
    return f'{sec // 60}:{sec % 60:02d}'
def _words(td):
    sec = int(round(td.total_seconds()))
    return f'{sec // 60} minutes {sec % 60} seconds'
LBL = {'draft': 'Order started by the customer', 'submitted': 'Submitted', 'validation_failed': 'Blocked by validation',
       'pending_approval': 'Passed validation, waiting for Ops Desk', 'awaiting_payment': 'Approved, invoice issued',
       'payment_verification': 'Payment proof uploaded', 'paid': 'Payment confirmed', 'picking': 'Picking started',
       'shortage_hold': 'Shortage found', 'packed': 'Packed', 'assigned': 'Driver assigned', 'out_for_delivery': 'Picked up by driver',
       'delivery_failed': 'Delivery failed', 'delivered': 'Delivered with the customer code'}
wt_rows, wt = [], {}
for o in sorted(WT['orders'], key=lambda o: o['order_no'], reverse=True):
    t0 = _f(o['events'][0]['at'])
    for e in o['events']:
        if e['to'] == 'submitted' and e is not o['events'][1] and e['from'] == 'validation_failed':
            pass
        wt_rows.append([o['order_no'], LBL[e['to']], e['role'].capitalize() if e['role'] != 'ops' else 'Ops Desk', _mmss(_f(e['at']) - t0), e['note'] or ''])
    ev = o['events']
    wt[o['order_no']] = {'total': _f(ev[-1]['at']) - t0, 'approve': next(_f(e['at']) for e in ev if e['to'] == 'awaiting_payment') - t0,
                         'statuses': {e['to'] for e in ev}, 'roles': {e['role'] for e in ev}, 'o': o}
a, b = wt['ORD-9371'], wt['ORD-9370']
fail = next(e for e in b['o']['events'] if e['to'] == 'validation_failed')
resub = next(e for e in b['o']['events'] if e['from'] == 'validation_failed')
stat_all = a['statuses'] | b['statuses']
roles_all = a['roles'] | b['roles']
refund = b['o']['refunds'][0]
P(f'Besides the scripted tests, the system was tested by hand on 30 October 2026, signing in with the demonstration account of '
  f'each role in turn. Two orders were taken from the first entry by the customer to delivery, and the status history recorded every '
  f'step with its time and the account that took it. Table 4.16 lists the steps. Order ORD-9371 went through without problems and '
  f'was delivered {_words(a["total"])} after it was started. While building it the customer saw a stock message for '
  f'electric cable and changed the order before submitting it.')
P(f'Order ORD-9370 was used for the exceptions. Its first submission was blocked by the stock rule and it was corrected and '
  f'resubmitted {int((_f(resub["at"]) - _f(fail["at"])).total_seconds())} seconds later. At picking the Warehouse found less stock than '
  f'ordered and the customer accepted a partial delivery. Finance then paid the refund of {naira(refund["amount"])} with credit note '
  f'{refund["credit_note"]}. On the road the first driver entered a wrong delivery code once and then recorded a vehicle breakdown. '
  f'Dispatch reassigned the order to a second driver, who delivered it with the customer code {_words(b["total"])} after it was '
  f'started. Together the two orders passed through {len(stat_all)} of the {FACTS["status_count"]} statuses and were handled by '
  f'{len(roles_all)} of the seven roles. The three statuses for rejection and cancellation were not reached, either in this test or '
  f'in the scripted tests of Table 4.14.')
P('The accounts were used in quick succession, a few seconds to a few minutes apart, so the times show that each step responded at '
  'once rather than how long the steps take in operation. They are not a measure of processing time and do not replace the comparison with manual '
  'entry that Objective 4 requires.')
trace(_mmss(a['total']), 'ORD-9371 draft to delivered', '02_functional_tests/manual_walkthrough_2026-10-30.json events')
trace(_mmss(b['total']), 'ORD-9370 draft to delivered', '02_functional_tests/manual_walkthrough_2026-10-30.json events')
table('Manual end-to-end test of two orders on 30 October 2026', ['Order', 'Step', 'Done by', 'Time after start, min:s', 'Note recorded'],
      wt_rows, 'status history of orders ORD-9371 and ORD-9370 in the live database, 02_functional_tests/manual_walkthrough_2026-10-30.json and manual_walkthrough.sql.',
      widths=[2, 5, 2.2, 2.6, 4.2], size=8)

# =====================================================================================================================
H2('4.4 Simulation design and dataset')
H3('4.4.1 Procedure')
P('Validation accuracy was measured with a controlled simulation. Orders were generated by a test script and submitted through '
  'the same database functions a customer uses, save_draft followed by submit_order, so the rules saw them exactly as they would '
  'see a real order. Each order was either clean or carried one planted error of a known type. The script held the planted error '
  'only in its own variables and wrote it to a results table after the run, so nothing the validation engine could read revealed '
  'which orders were erroneous. Each run took place inside a transaction that was rolled back, which removed every simulated '
  'customer and order and left the live data unchanged. The status history and the timing of each order were captured before '
  'the rollback.')
H3('4.4.2 Replicates and planted errors')
P('The final simulation used three replicates. Replicate 1 used the random seed 0.42 and is the headline result, while '
  'replicates 2 and 3 used the seeds 0.43 and 0.44. The further replicates '
  'show how much the measures move when the same design is drawn again. Each replicate contained 500 orders, made '
  'up of 200 clean orders and 300 erroneous orders, with 20 orders for each of fifteen planted error types. Twelve of the types '
  'are errors that a rule is designed to catch. The remaining three are realistic mistakes that no rule targets, shown at the '
  'foot of Table 4.17. Including them means the accuracy figures '
  'reflect mistakes the rules were not written for as well as those they were. Automatic approval was switched off so that every '
  'order passing validation went to the Ops Desk queue. Table 4.17 describes each planted error type.')
trace('500 x 3', 'orders per replicate', '03_simulation/raw/run5,6,7 row counts; metrics_final.json replicates.n.orders')
types_rows = [
    ['SKU not in catalogue', 'An extra upload line with an unknown code such as XX-417', 'SKU'],
    ['Discontinued product', 'Sharp sand added after it was marked inactive for the run', 'SKU'],
    ['Missing delivery address', 'No address chosen', 'Mandatory fields'],
    ['Missing delivery date', 'No date chosen', 'Mandatory fields'],
    ['Delivery date in the past', 'Date 1 to 5 days before the run date', 'Delivery date and address'],
    ['Quantity below minimum', 'Minimum order quantity less one', 'Quantity limits'],
    ['Quantity above maximum', 'Maximum order quantity plus 1 to 50', 'Quantity limits'],
    ['Fractional quantity', 'Minimum order quantity plus 0.5', 'Quantity limits'],
    ['Quantity above available stock', 'Available stock plus one, within the order limits', 'Stock availability'],
    ['Duplicate order', 'Same items as the latest clean order that reached approval, else as an earlier history order', 'Duplicate order'],
    ['Customer account not active', 'Draft saved while active, account put on hold or blocked before submission', 'Customer status'],
    ['Price changed after saving', 'List price of one line raised by 5 percent between saving and submitting', 'Pricing'],
    ['Wrong but valid product', 'A neighbouring product such as 16 mm rods for 12 mm, within all limits', 'None'],
    ['Plausible quantity typing slip', 'Cement or iron rods entered at ten times the intended quantity', 'None'],
    ['Wrong saved address', 'The other of the two saved addresses chosen', 'None'],
]
table('Planted error types and how each was created', ['Planted error', 'How it was planted', 'Rule expected to catch it'], types_rows,
      'run_simulation_final, supabase/migrations/0007_simulation_final.sql.', widths=[4.2, 8.3, 3.5])
H3('4.4.3 Customers, catalogue and dataset')
P(f'The simulation used twenty customer profiles and the twelve-product catalogue of the first run. As Section 1.5 sets out, '
  f'the profiles were set up for the test on the pattern of realistic business customers and do not belong to real customers. '
  f'Each customer had two saved addresses in one of six delivery regions and four earlier orders, which give the '
  f'unusual-quantity rule a history to compare against. Table 4.18 lists the companies and Table 4.19 describes the replicate 1 '
  f'dataset. Figure 4.4 shows how the orders were spread across the delivery regions.')
R1ROWS = json.loads((ROOT / '03_simulation' / 'raw' / 'run5_replicate1.json').read_text())
comp = {}
for r in R1ROWS:
    d = comp.setdefault(r['company'], {'contact': r['contact'], 'email': r['email'], 'region': None, 'n': 0})
    d['n'] += 1
    d['region'] = d['region'] or r['region']
table('Customer profiles used in the simulation', ['Company', 'Contact person', 'Region', 'Orders'],
      [[k, v['contact'], v['region'], v['n']] for k, v in sorted(comp.items())],
      'test customer profiles, replicate 1, database run 5, 03_simulation/replicate1_orders.csv.',
      widths=[6.6, 4.4, 3.2, 1.8], size=8.5)
table('Description of the replicate 1 dataset', ['Measure', 'Value'],
      [['Orders', R1['orders']], ['Clean, rule-targeted and no-rule orders', f"{R1['clean']}, {R1['rule_targeted']}, {R1['no_rule']}"],
       ['Customers', DS['customers']], ['Orders per customer', f"{DS['orders_per_customer_min']} to {DS['orders_per_customer_max']}"],
       ['Mean lines per order', DS['lines_mean']], ['Mean units per order', DS['units_mean']],
       ['Order value, mean', naira(DS['value_mean'])], ['Order value, median', naira(DS['value_median'])],
       ['Order value, range', f"{naira(DS['value_min'])} to {naira(DS['value_max'])}"], ['Total order value', naira(DS['value_total'])],
       ['Orders by region', '; '.join(f'{k} {v}' for k, v in DS['regions'].items())]],
      'replicate 1, database run 5, 07_analysis/metrics_final.json dataset.', widths=[5, 11])
trace(naira(DS['value_total']), 'total order value replicate 1', 'metrics_final.json replicates.1.dataset.value_total')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_1_regions.png', 'Simulated orders by delivery region, replicate 1',
       '07_analysis/figures/fig4_1_regions_data.csv, from replicate 1, database run 5.')
P('Table 4.20 shows one order of each kind from replicate 1, with the decision the system took and the first message it showed. '
  'Every order of all three replicates is listed in the accompanying workbook, Verity_Simulation_Data_Final.xlsx.')
LBL = {t['key']: t['label'] for t in R1['by_type']}
DEC = {'pass': 'Passed', 'warn': 'Warned', 'fail': 'Blocked'}
seen, sample = set(), []
for r in R1ROWS:
    if r['planted_error'] not in seen:
        seen.add(r['planted_error'])
        sample.append([r['order_no'], r['company'], naira(float(r['total'])), LBL[r['planted_error']], DEC[r['outcome']],
                       (r['messages'][0][:95] + ('...' if len(r['messages'][0]) > 95 else '')) if r['messages'] else 'none'])
sample.sort(key=lambda x: list(LBL.values()).index(x[3]))
table('Sample of simulated orders and the decision taken, replicate 1', ['Order', 'Company', 'Total', 'Planted error', 'Decision', 'First message shown'],
      sample, 'replicate 1, database run 5, first order of each kind in 03_simulation/replicate1_orders.csv.', widths=[1.7, 3.3, 2.4, 3.2, 1.6, 4.8], size=8)
H3('4.4.4 Relation to the first run')
P('The first run of the simulation, run 4, is kept as the first run and is not replaced. It used 500 orders whose types were drawn '
  'at random, so group sizes were unequal, and it planted no inactive-customer or stale-price errors. A defect in its test script also '
  'submitted 13 of its 35 wrong-product orders with an empty line, which the quantity rule blocked. Those 13 blocks were artefacts '
  'of the script, not detections. The final simulation corrected the defect and added the two '
  'missing types, with twenty orders of every type, so its results are the ones assessed in this chapter.')
trace(13, 'run 4 harness artefacts', '01_system_facts/system_facts.json run4_harness_defect')

# =====================================================================================================================
H2('4.5 Simulation results')
H3('4.5.1 Overall outcomes')
og = R1['outcomes_by_group']
P(f'Figure 4.5 shows what happened to each group of orders in replicate 1. Of the 200 clean orders, {og["clean"]["pass"]} passed '
  f'and {og["clean"]["warn"]} were warned. All 240 orders with a rule-targeted error were stopped, {og["rule_targeted"]["fail"]} '
  f'by a blocking rule and {og["rule_targeted"]["warn"]} by the duplicate warning. Of the 60 orders with an error that no rule '
  f'targets, {og["no_rule"]["warn"]} were warned and {og["no_rule"]["pass"]} passed. After submission '
  f'{R1["statuses_after_submit"]["validation_failed"]} orders were in validation failed and {R1["statuses_after_submit"]["pending_approval"]} '
  f'were waiting for approval. The other {R1["statuses_after_submit"]["draft"]} were held as drafts until the customer confirmed a possible repeat.')
trace(og['clean']['warn'], 'clean orders warned, replicate 1', 'metrics_final.json replicates.1.outcomes_by_group.clean.warn; workbook R1 Summary D5')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_2_outcomes.png', 'Outcome of each group of orders in replicate 1',
       '07_analysis/figures/fig4_2_outcomes_data.csv, from replicate 1, database run 5.')
H3('4.5.2 Detection by planted error type')
P('Table 4.21 gives the detection rate for each planted error type with a 95 percent Wilson interval, which behaves better than '
  'the simple normal interval for small groups and for rates near zero or one (Brown et al., 2001; Wilson, 1927). Every one of the '
  'twelve rule-targeted types was flagged in all 20 of its orders, and in each case by the rule designed for it. Figure 4.6 '
  'shows the same rates graphically.')
rows = []
for t in R1['by_type']:
    if t['key'] == 'clean':
        rows.append([t['label'], '', f"{t['n'] - t['clean_pass']['k']} flagged", f"{pc(100 - t['clean_pass']['pct'])} false alarms",
                     f"{100 - t['clean_pass']['ci95'][1]:.1f} to {100 - t['clean_pass']['ci95'][0]:.1f}", ''])
        continue
    d = t['detection']
    rows.append([t['label'], 'Yes' if t['rule_targeted'] else 'No', f"{d['k']}/{d['n']}", pc(d['pct']), ci(d),
                 t['caught_by_expected_rule'] if t['rule_targeted'] else f"{t['flagged_by_other_rule_only']} by other rules"])
table('Detection by planted error type, replicate 1', ['Planted error', 'Has rule', 'Flagged', 'Detection %', '95% CI', 'Caught by expected rule'],
      rows, 'replicate 1, 07_analysis/metrics_final.json by_type, workbook sheet R1 Summary section D.', widths=[5.2, 1.6, 1.8, 2, 2.6, 2.8])
figure(ROOT / '07_analysis' / 'figures' / 'fig4_3_detection.png', 'Detection rate by planted error type with 95 percent Wilson intervals, replicate 1',
       '07_analysis/figures/fig4_3_detection_data.csv, from replicate 1, database run 5.')
P(f'The three types without a rule tell a different story. The quantity typing slip was flagged in {BT["qty_typo"]["detection"]["k"]} '
  f'of 20 orders, and in each of these the unusual-quantity warning named the very line that carried the slip, so this is genuine '
  f'detection by a rule that was not designed for it. The wrong product and the wrong address were each flagged in '
  f'{BT["wrong_product"]["detection"]["k"]} of 20 orders, but in none of those cases did the warning concern the planted error. '
  f'The warnings were about other lines or, once, about a possible repeat, so these flags are coincidental. A wrong but valid '
  f'product or address is in effect invisible to the engine, which is what one would expect of rules that check whether a value '
  f'is allowed rather than whether it is what the customer meant.')
trace(f"{NR['qty_typo']['warning_names_planted_line']}/{NR['qty_typo']['flagged']}", 'typo flags naming the typo line', 'metrics_final.json replicates.1.no_rule_flag_on_planted_line')
H3('4.5.3 Classification performance')
P(f'For the binary measures an order counts as flagged when it is warned or blocked and as positive when it carries a planted error. '
  f'The primary measure uses all 300 erroneous orders against the 200 clean orders, and the secondary measure uses only the 240 '
  f'rule-targeted orders against the same clean orders. Table 4.22 defines the measures. Table 4.23 gives both confusion matrices for replicate 1 and Table 4.24 '
  f'gives the measures with their intervals.')
table('Definitions of the classification measures', ['Measure', 'Definition', 'Formula'],
      [['Accuracy', 'Share of all orders the system judged correctly, erroneous orders flagged and clean orders passed', '(TP + TN) / all orders'],
       ['Precision', 'Of the orders flagged, the share that really carried an error', 'TP / (TP + FP)'],
       ['Recall', 'Of the orders that carried an error, the share the system flagged', 'TP / (TP + FN)'],
       ['Specificity', 'Of the clean orders, the share passed without a flag', 'TN / (TN + FP)'],
       ['False-alarm rate', 'Of the clean orders, the share flagged', 'FP / (FP + TN)'],
       ['F1 score', 'Harmonic mean of precision and recall', '2 x P x R / (P + R)']],
      'standard definitions. TP true positive, FN false negative, FP false positive, TN true negative.', widths=[2.8, 9, 4.2])
table('Confusion matrices, replicate 1', ['Measure set', 'Error flagged', 'Error passed', 'Clean flagged', 'Clean passed', 'Orders'],
      [['Primary, all errors', A['tp'], A['fn'], A['fp'], A['tn'], A['n']], ['Secondary, rule-targeted errors', T['tp'], T['fn'], T['fp'], T['tn'], T['n']]],
      'replicate 1, 07_analysis/metrics_final.json confusion_all_errors and confusion_rule_targeted, workbook R1 Summary sections B and C.')
mrows = []
for nm, key in (('Accuracy', 'accuracy'), ('Precision', 'precision'), ('Recall', 'recall'), ('Specificity', 'specificity'), ('False-alarm rate', 'false_alarm_rate')):
    mrows.append([nm, pc(A[key]['pct']), ci(A[key]), pc(T[key]['pct']), ci(T[key])])
mrows.append(['F1 score', pc(A['f1_pct']), 'not a single proportion', pc(T['f1_pct']), 'not a single proportion'])
table('Validation measures with 95 percent Wilson intervals, replicate 1', ['Measure', 'Primary %', 'Primary 95% CI', 'Secondary %', 'Secondary 95% CI'],
      mrows, 'replicate 1, 07_analysis/metrics_final.json, workbook R1 Summary sections B and C.')
for nm, key in (('accuracy', 'accuracy'), ('precision', 'precision'), ('recall', 'recall'), ('specificity', 'specificity'), ('false alarm rate', 'false_alarm_rate')):
    trace(pc(A[key]['pct']), f'primary {nm}, replicate 1', f'metrics_final.json replicates.1.confusion_all_errors.{key}; workbook R1 Summary B')
trace(pc(T['accuracy']['pct']), 'secondary accuracy, replicate 1', 'metrics_final.json replicates.1.confusion_rule_targeted.accuracy; workbook R1 Summary C')
P(f'On the primary measure the engine reached an accuracy of {pc(A["accuracy"]["pct"])} percent, with a 95 percent interval of '
  f'{ci(A["accuracy"])} percent. The whole interval lies below the 90 percent target, so the primary measure does not meet it. '
  f'Recall was {pc(A["recall"]["pct"])} percent, held down by the {A["fn"]} errors without a rule that passed unflagged.'
  f' On the '
  f'secondary measure accuracy was {pc(T["accuracy"]["pct"])} percent, with an interval of {ci(T["accuracy"])} percent, and recall '
  f'was {pc(T["recall"]["pct"])} percent. Precision was similar on both measures because the false alarms are the same clean '
  f'orders in each. Figure 4.7 shows the measures with their intervals and marks the values from replicates 2 and 3.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_4_measures.png', 'Validation measures with 95 percent Wilson intervals',
       '07_analysis/figures/fig4_4_measures_data.csv, from replicates 1 to 3, database runs 5 to 7.')
H3('4.5.4 Rule activity and false alarms')
P(f'Table 4.25 shows how often each rule fired. The seven blocking rules fired only on erroneous orders and never on a clean '
  f'one. The stock rule also fired on the {RU["stock"]["on_other_error_types"]} orders whose quantity was above the maximum or '
  f'whose product was discontinued, because both also exceed the stock on hand. All {R1["confusion_all_errors"]["fp"]} false alarms on '
  f'clean orders came from the two warning rules, {R1["false_alarm_reasons"].get("unusual_quantity", 0)} from the unusual-quantity '
  f'rule and {R1["false_alarm_reasons"].get("duplicate", 0)} from the duplicate rule. The unusual-quantity rule fired on '
  f'{RU["unusual_quantity"]["orders_fired"]} orders in all, and on {pc(RU["unusual_quantity"]["false_alarm_rate_on_clean"]["pct"])} '
  f'percent of clean orders. Figure 4.8 shows the same counts by kind of order.')
table('Rule activity and false alarms, replicate 1',
      ['Rule', 'Severity', 'Orders fired', 'On its target type', 'On other error types', 'On clean orders', 'False alarms per clean order, 95% CI'],
      [[r['label'], 'Warning' if r['severity'] == 'warn' else 'Blocking', r['orders_fired'], r['on_target_type'], r['on_other_error_types'],
        r['on_clean_false_alarms'], f"{pc(r['false_alarm_rate_on_clean']['pct'])} ({ci(r['false_alarm_rate_on_clean'])})"] for r in R1['rules']],
      'replicate 1, 07_analysis/metrics_final.json rules, workbook R1 Summary section E.', size=8.5)
trace(RU['unusual_quantity']['on_clean_false_alarms'], 'unusual-quantity false alarms, replicate 1', 'metrics_final.json replicates.1.rules unusual_quantity; workbook R1 Summary E')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_5_rules.png', 'Number of orders on which each validation rule fired, by kind of order, replicate 1',
       '07_analysis/figures/fig4_5_rules_data.csv, from replicate 1, database run 5.')
H3('4.5.5 Processing time')
blk = R1['validation_ms_mean_by_block_of_100']
P(f'Validation time was measured as the clock time of submit_order inside the database, which validates the order and records '
  f'the status change. It excludes network time and any time a person spends. Table 4.26 gives the statistics '
  f'for replicate 1 and Figure 4.9 shows their distribution. The standard deviation is the sample value. The mean was {TM["mean"]} ms and the median {TM["median"]} ms, '
  f'with a 95th percentile of {TM["p95"]} ms and a maximum of {TM["max"]} ms. The time measured from the draft event to the last '
  f'event in the status history gave a mean of {R1["status_history_draft_to_last_event_ms"]["mean"]} ms over the '
  f'{R1["status_history_orders_with_two_or_more_events"]} orders that had more than one event.')
table('Validation time per order in milliseconds, replicate 1', ['Statistic', 'All orders', 'Passed', 'Warned', 'Blocked'],
      [[lab] + [R1['validation_ms'][k]] + [R1['validation_ms_by_outcome'][o][k] for o in ('pass', 'warn', 'fail')]
       for lab, k in (('Orders', 'n'), ('Mean', 'mean'), ('SD, sample', 'sd_sample'), ('Median', 'median'), ('95th percentile', 'p95'), ('Minimum', 'min'), ('Maximum', 'max'))],
      'replicate 1, 07_analysis/metrics_final.json validation_ms, workbook R1 Summary section F.')
trace(TM['mean'], 'mean validation ms, replicate 1', 'metrics_final.json replicates.1.validation_ms.mean; workbook R1 Summary F')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_6_validation_time.png', 'Distribution of validation time per order, replicate 1',
       '07_analysis/figures/fig4_6_validation_time_data.csv, from replicate 1, database run 5.')
P(f'The time was not stable across the run. Figure 4.10 shows that in replicate 1 the mean rose from {blk[0]:.2f} ms for the first 100 '
  f'orders to {blk[-1]:.2f} ms for the last 100, and replicate 2 followed the same path. The rules that look back over a customer\'s '
  f'earlier orders have more orders to examine as the run goes on, which is consistent with this rise. Replicate 3 stayed between '
  f'{R["3"]["validation_ms_mean_by_block_of_100"][0]:.2f} and {R["3"]["validation_ms_mean_by_block_of_100"][-1]:.2f} ms throughout. The '
  f'test script was the same in every run. It is assumed, but was not confirmed, that the database chose a different query plan '
  f'in that run. In every replicate a single order was validated in well under a second.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_7_timing_blocks.png', 'Validation time per order across each run, mean of each block of 100 orders',
       '07_analysis/figures/fig4_7_timing_blocks_data.csv, from replicates 1 to 3, database runs 5 to 7.')
H3('4.5.6 Variation between replicates')
spread = max(round(RR[k]['max'] - RR[k]['min'], 1) for k in RR if not k.startswith('validation_ms'))
P(f'Table 4.27 sets the key measures of the three replicates side by side. No accuracy or detection measure moved by more than '
  f'{spread} percentage points between replicates, so the headline figures do not depend on the particular seed. The timing '
  f'measures moved by an order of magnitude, as described above.')
trace(spread, 'largest replicate spread of a non-timing measure', 'metrics_final.json replicate_range, max minus min')
rng_rows = []
for lab, k in (('Accuracy, all errors', 'accuracy_all'), ('Precision, all errors', 'precision_all'), ('Recall, all errors', 'recall_all'),
               ('Specificity', 'specificity_all'), ('False-alarm rate', 'false_alarm_rate'), ('F1, all errors', 'f1_all'),
               ('Accuracy, rule-targeted errors', 'accuracy_targeted'), ('Precision, rule-targeted errors', 'precision_targeted'),
               ('Recall, rule-targeted errors', 'recall_targeted'), ('F1, rule-targeted errors', 'f1_targeted'),
               ('No-rule errors flagged', 'no_rule_detection'), ('Mean validation time, ms', 'validation_ms_mean'),
               ('Median validation time, ms', 'validation_ms_median'), ('95th percentile validation time, ms', 'validation_ms_p95'),
               ('Mandatory-field completion, orders reaching approval', 'mandatory_completion')):
    v = RR[k]
    rng_rows.append([lab] + v['values'] + [f"{v['min']} to {v['max']}"])
table('Key measures in each replicate', ['Measure', 'Replicate 1', 'Replicate 2', 'Replicate 3', 'Range'], rng_rows,
      '07_analysis/metrics_final.json replicate_range, workbook sheet Replicate range.', widths=[6.4, 2.3, 2.3, 2.3, 2.7])
trace(f"{RR['accuracy_all']['min']} to {RR['accuracy_all']['max']}", 'primary accuracy range', 'metrics_final.json replicate_range.accuracy_all; workbook Replicate range E4:F4')
H3('4.5.7 Sensitivity of the unusual-quantity warning')
P(f'Because the unusual-quantity rule caused nearly all false alarms and also caught the quantity slips, its setting was examined. '
  f'Replicate 1 was replayed through the live functions with the threshold set from three to five times the customer\'s '
  f'average in steps of one, and with four or ten earlier orders per customer. The replay with the live setting reproduced replicate 1 exactly, with '
  f'no difference in any order, so the six settings in Table 4.28 are compared on identical orders. These runs are for discussion '
  f'only and the live setting was left at three.')
srows = []
for (f, h), s in sorted(SENS.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    fa, ty = s['clean_false_alarm_rate_all_rules'], s['typo_detection']
    srows.append([f'{f:g} x average', h, f"{fa['k']}/200", pc(fa['pct']), ci(fa), f"{ty['k']}/20", pc(ty['pct']), ci(ty), pc(s['accuracy_all']['pct'])])
table('Unusual-quantity sensitivity on replicate 1',
      ['Threshold', 'Earlier orders', 'Clean flagged', 'False-alarm %', '95% CI', 'Slips flagged', 'Slip detection %', '95% CI', 'Accuracy, all errors %'],
      srows, 'replays of database run 5 as runs 8 to 13, 04_sensitivity/sensitivity_results.csv, workbook sheet Sensitivity.', size=8.5)
s34, s54, s310 = SENS[(3.0, 4)], SENS[(5.0, 4)], SENS[(3.0, 10)]
P(f'Raising the threshold from three to five times the average with four earlier orders cut false alarms on clean orders from '
  f'{pc(s34["clean_false_alarm_rate_all_rules"]["pct"])} to {pc(s54["clean_false_alarm_rate_all_rules"]["pct"])} percent, but '
  f'the share of quantity slips caught fell from {pc(s34["typo_detection"]["pct"])} to {pc(s54["typo_detection"]["pct"])} percent. '
  f'A longer history of ten orders caught more slips at the same threshold but also raised false alarms, to '
  f'{pc(s310["clean_false_alarm_rate_all_rules"]["pct"])} percent at three times the average. The intervals for the slips are wide '
  f'because each rests on 20 orders, so these differences show a direction rather than settled values. Figure 4.11 shows the trade-off.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_8_sensitivity.png', 'Effect of the unusual-quantity threshold and history length on false alarms and slip detection',
       '07_analysis/figures/fig4_8_sensitivity_data.csv, from replays of database run 5.')
H3('4.5.8 Mandatory-field completion')
mand = R1['mandatory_completion_reaching_approval']
P(f'Mandatory-field completion was measured on the orders that reached approval. All {mand["k"]} of the {mand["n"]} orders that '
  f'reached the approval queue in replicate 1 had every mandatory field filled, with a 95 '
  f'percent interval of {ci(mand)} percent, and the same was true in the other replicates. This follows from the design, since '
  f'the mandatory-fields rule blocks any order without them, and the simulation confirms that no such order got through.')
trace(f"{mand['k']}/{mand['n']}", 'mandatory completion, replicate 1', 'metrics_final.json replicates.1.mandatory_completion_reaching_approval; workbook R1 Summary G')

H3('4.5.9 Comparison with manual entry')
mr, vr = MB['manual_error_rate'], MB['verity_error_rate']
P(f'Two participants who had not seen the answer key each handled 20 of the order messages of the comparison pack by hand on 30 '
  f'October 2026, as orders are handled today. Each checked the message against the reference sheets of the pack and typed the '
  f'order into an entry sheet without correcting it, noting the time at the start and at the end. The {MB["orders"]} orders were taken from '
  f'replicate 1 of the simulation, so the outcome of Verity on each of them was already known. In Verity the customer enters the '
  f'order against the live catalogue and no member of staff retypes it, so an error reaches the record only when the system does '
  f'not flag it. The comparison used the definitions fixed before any data were collected. By hand an error reached the record '
  f'when a planted error was not flagged or when any field was typed differently from the message. Table 4.29 gives the results.')
cmp_rows = [
    ['Orders with an error reaching the record', f'{mr["k"]} of {mr["n"]}, {pc(mr["pct"])} percent', ci(mr), f'{vr["k"]} of {vr["n"]}, {pc(vr["pct"])} percent', ci(vr)],
    ['Planted errors flagged', f'{MB["manual_planted_errors_caught"]["k"]} of {MB["manual_planted_errors_caught"]["n"]}', ci(MB['manual_planted_errors_caught']),
     f'{MB["verity_planted_errors_flagged"]["k"]} of {MB["verity_planted_errors_flagged"]["n"]}', ci(MB['verity_planted_errors_flagged'])],
    ['Rule-targeted errors flagged', f'{MB["manual_caught_rule_targeted"]["k"]} of {MB["manual_caught_rule_targeted"]["n"]}', ci(MB['manual_caught_rule_targeted']),
     f'{MB["verity_flagged_rule_targeted"]["k"]} of {MB["verity_flagged_rule_targeted"]["n"]}', ci(MB['verity_flagged_rule_targeted'])],
    ['Errors with no rule flagged', f'{MB["manual_caught_no_rule"]["k"]} of {MB["manual_caught_no_rule"]["n"]}', ci(MB['manual_caught_no_rule']),
     f'{MB["verity_flagged_no_rule"]["k"]} of {MB["verity_flagged_no_rule"]["n"]}', ci(MB['verity_flagged_no_rule'])],
    ['Orders with a field typed differently from the message', f'{MB["manual_orders_with_typing_error"]["k"]} of {MB["manual_orders_with_typing_error"]["n"]}', ci(MB['manual_orders_with_typing_error']), 'not applicable', ''],
    ['Clean orders wrongly flagged', f'{MB["manual_false_flags_on_clean"]["k"]} of {MB["manual_false_flags_on_clean"]["n"]}', ci(MB['manual_false_flags_on_clean']),
     f'{MB["verity_false_flags_on_clean"]["k"]} of {MB["verity_false_flags_on_clean"]["n"]}', ci(MB['verity_false_flags_on_clean'])],
    ['Time per order, median and mean', f'{MB["manual_seconds"]["median"]:.0f} s and {MB["manual_seconds"]["mean"]:.0f} s', '', 'not measured for a person', ''],
]
table('Manual entry and Verity on the same 40 orders', ['Measure', 'Manual entry', '95% CI', 'Verity', '95% CI'], cmp_rows,
      'Entry sheets of participants P01 and P02, answer key of the comparison pack and replicate 1 of the simulation, scored with score_manual_vs_simulation.py.',
      widths=[5.2, 3.2, 2.4, 3.2, 2.4], size=8.5)
P(f'An error reached the record in {pc(mr["pct"])} percent of the orders handled by hand and in {pc(vr["pct"])} percent of the same '
  f'orders through Verity, a reduction of {pc(MB["error_reduction_pct"])} percent, and the two 95 percent intervals do not overlap. '
  f'The manual errors had two sources. The participants flagged {MB["manual_planted_errors_caught"]["k"]} of the '
  f'{MB["manual_planted_errors_caught"]["n"]} planted errors, and {MB["manual_orders_with_typing_error"]["k"]} of the {MB["orders"]} '
  f'orders were typed with at least one field that differed from the message, most often the address or an order line. The slips '
  f'included a delivery date of 5 November typed for 3 November and a quantity of 60 typed for 1. All {vr["k"]} errors that would '
  f'have passed Verity were errors that no rule targets, and {MB["verity_errors_passed_by_type"]["wrong_address"]} of them were '
  f'wrong addresses. One counted '
  f'manual slip, an address written with Rd for Road, would not misdirect a delivery. Without it the manual rate is '
  f'{pc(MB["manual_rate_excluding_abbreviation_only"]["pct"])} percent and the reduction {pc(MB["error_reduction_excluding_abbreviation_only_pct"])} percent.')
P(f'By hand the participants took a median of {MB["manual_seconds"]["median"]:.0f} seconds per order, and orders they flagged took '
  f'a median of {MB["manual_seconds_flagged_median"]:.0f} seconds. The time a person spends entering an order in Verity was not '
  f'measured, so this baseline cannot yet be turned into a saving of time. With {MB["orders"]} orders and two participants the '
  f'comparison is indicative only. Its Verity side rests on the simulation rather than on people entering the orders, so it assumes '
  f'that a customer entering an order in Verity makes the planted mistakes and no others.')
for v, m_, w in [(f"{mr['k']}/{mr['n']}", 'manual orders with an error reaching the record', 'manual_vs_simulation_results.json manual_error_rate'),
                 (f"{vr['k']}/{vr['n']}", 'Verity orders with an error reaching the record', 'manual_vs_simulation_results.json verity_error_rate'),
                 (pc(MB['error_reduction_pct']), 'error reduction, percent', 'manual_vs_simulation_results.json error_reduction_pct'),
                 (f"{MB['manual_seconds']['median']:.0f}", 'manual median seconds per order', 'manual_vs_simulation_results.json manual_seconds.median')]:
    trace(v, m_, w)

# =====================================================================================================================
H2('4.6 Evaluation against the success criteria and discussion')
H3('4.6.1 Evaluation against the objectives')
P('Table 4.30 sets each objective of Section 1.3, in its Chapter One wording, against its success criterion and the result of '
  'this evaluation.')
OBJ = [
    'To design and develop a web-based order processing system that replaces manual order entry done through Excel sheets and through e-mail and WhatsApp messages.',
    'To implement an automatic validation engine that checks SKU, quantity, customer details, pricing, duplicate orders, stock and mandatory fields, and to achieve at least 90 percent validation accuracy.',
    'To reduce manual data-entry errors by at least 60 percent and to achieve 100 percent completion of mandatory fields.',
    'To improve order processing speed by 30 to 50 percent through digital approval, payment confirmation, fulfilment and delivery workflows.',
    'To evaluate the usability and acceptance of the system through a questionnaire and a test run of 500 simulated orders.',
]
obj_rows = [
    [f'1. {OBJ[0]}', 'A working web-based system through which orders are entered and processed without rekeying',
     f'Built and deployed. Orders are entered in the portal, from an uploaded Excel or CSV sheet, or from a pasted message. {ft_pass} of {len(FT)} functional tests passed. CSV export of orders and webhooks are not built',
     'not applicable', 'Met'],
    [f'2. {OBJ[1]}', 'At least 90 percent validation accuracy',
     f'Primary {pc(A["accuracy"]["pct"])} percent, all errors. Secondary {pc(T["accuracy"]["pct"])} percent, rule-targeted errors. Replicates {RR["accuracy_all"]["min"]} to {RR["accuracy_all"]["max"]} and {RR["accuracy_targeted"]["min"]} to {RR["accuracy_targeted"]["max"]}',
     f'{ci(A["accuracy"])} and {ci(T["accuracy"])}', 'Partly met'],
    [f'3. {OBJ[2]}', 'At least 60 percent fewer manual entry errors',
     f'An error reached the record in {MB["manual_error_rate"]["k"]} of 40 orders by hand and {MB["verity_error_rate"]["k"]} of the same 40 through Verity, a reduction of {pc(MB["error_reduction_pct"])} percent. Two participants, indicative',
     f'{ci(MB["manual_error_rate"])} and {ci(MB["verity_error_rate"])}', 'Met, indicative'],
    ['3. As above', '100 percent completion of mandatory fields',
     f'{mand["k"]} of {mand["n"]} orders reaching approval, 100 percent in all three replicates', ci(mand), 'Met'],
    [f'4. {OBJ[3]}', '30 to 50 percent faster processing',
     f'Manual handling took a median of {MB["manual_seconds"]["median"]:.0f} s per order. Verity validates in {RR["validation_ms_median"]["min"]} to {RR["validation_ms_median"]["max"]} ms, but the time a person spends entering an order in Verity was not measured',
     'not applicable', 'Scheduled'],
    [f'5. {OBJ[4]}', 'Test run of 500 simulated orders', '500 orders in each of three replicates, 1,500 in all', 'not applicable', 'Met'],
    ['5. As above', 'Usability and acceptance shown by the questionnaire',
     f'System Usability Scale mean {Q["sus"]["All"]["mean"]:.2f}, significantly below 68. {pc(Q["items"]["BI1"]["All"]["agree_pct"])} percent would use Verity',
     f'{Q["sus"]["All"]["ci95"][0]:.2f} to {Q["sus"]["All"]["ci95"][1]:.2f}', 'Not met'],
]
table('Objectives of Section 1.3 and their success criteria', ['Objective, Chapter One wording', 'Criterion', 'Result', '95% CI', 'Status'], obj_rows,
      'Section 1.3 and Sections 4.2 to 4.5 of this chapter. Accuracy judged on the primary measure with the secondary measure in support.',
      widths=[5.2, 3, 4.6, 2, 1.4], size=8.5)
P(f'Objective 1 is rated Met because orders can be entered and taken through the whole lifecycle without being retyped by staff. '
  f'Two features named in the scope of Section 1.5 are missing, the CSV export of orders and the webhooks for connection to other '
  f'systems, and the route for pasting a WhatsApp message was built but not covered by a functional test. The accuracy part of '
  f'Objective 2 is rated Partly met. On the primary measure accuracy did not reach 90 percent in any replicate, and the upper end '
  f'of the replicate 1 interval was {A["accuracy"]["ci95"][1]:.1f} percent. On the rule-targeted errors it exceeded 90 percent in '
  f'every replicate and the whole interval lay above the target. Both measures share the same false alarms, so the gap between '
  f'them comes from the {A["fn"]} errors without a rule that were missed, '
  f'{40 - BT["wrong_product"]["detection"]["k"] - BT["wrong_address"]["detection"]["k"]} of them wrong products or wrong addresses.')
P(f'Objective 3 is Met on indicative evidence. Its mandatory-fields criterion is Met, and in the comparison with manual entry an '
  f'error reached the record in {pc(MB["verity_error_rate"]["pct"])} percent of orders through Verity against '
  f'{pc(MB["manual_error_rate"]["pct"])} percent by hand, a reduction of {pc(MB["error_reduction_pct"])} percent against a target of '
  f'60 percent. The comparison covered {MB["orders"]} orders handled by two participants, below the 80 paired orders planned, so it '
  f'is indicative only. The speed criterion of Objective 4 is Scheduled. Manual handling took a median of '
  f'{MB["manual_seconds"]["median"]:.0f} seconds per order, but the time a person spends entering the same order in Verity was not '
  f'measured, so no saving can yet be stated. The simulated test run required by Objective 5 is Met, but its usability and '
  'acceptance part is Not met. The mean usability score was significantly below the benchmark of 68, and no acceptance item was '
  'agreed by a majority of respondents.')
H3('4.6.2 Answers to the research questions')
P('Each research question of Section 1.4 is restated below in its Chapter One wording and answered from the evidence of this chapter.')
RQ = [
    ('How can an order processing system be designed to replace manual order entry in a logistics company.',
     f'Verity shows that it can be done by having the customer enter the order against the live catalogue and by running every '
     f'later step as one controlled lifecycle of {FACTS["status_count"]} statuses, with each role limited to its own actions and '
     f'every change recorded. Customers can also upload a spreadsheet or paste a message, which the system reads into the same '
     f'validated form. Of {len(FT)} functional tests, {ft_pass} passed, and the failures concern features that are missing or '
     f'incomplete, as Section 4.3 reports.'),
    ('How accurately can an automatic validation engine detect erroneous orders.',
     f'Every error that a rule targets was detected in all three replicates, which gave an accuracy of {pc(T["accuracy"]["pct"])} '
     f'percent on those errors. When realistic errors that no rule targets were included the accuracy was '
     f'{pc(A["accuracy"]["pct"])} percent, below the 90 percent target, and most of the errors that passed were of a kind no rule '
     f'can detect.'),
    ('By how much does the system reduce manual data-entry errors compared with manual entry.',
     f'In the comparison of Section 4.5.9 an error reached the record in {pc(MB["manual_error_rate"]["pct"])} percent of orders '
     f'handled by hand and in {pc(MB["verity_error_rate"]["pct"])} percent of the same orders through Verity, a reduction of '
     f'{pc(MB["error_reduction_pct"])} percent. The reduction comes from two sources. Verity stops every error a rule targets, which '
     f'the participants mostly missed, and it removes retyping, which caused slips in nearly half of the manual orders. Errors that '
     f'lie inside the allowed values, such as a wrong but valid product, pass both. With two participants the answer is indicative.'),
    ('By how much does the system improve order processing speed.',
     f'Validation itself takes milliseconds per order, but the question concerns end-to-end processing time against manual '
     f'handling. By hand the participants took a median of {MB["manual_seconds"]["median"]:.0f} seconds per order. The time a '
     f'person spends entering the same order in Verity was not measured, so the gain cannot yet be stated.'),
    ('How usable and acceptable do intended users find the system.',
     f'Intended users found Verity of poor usability on the evidence of the demonstration. The mean System Usability Scale score '
     f'was {Q["sus"]["All"]["mean"]:.2f}, significantly below the benchmark of 68, and staff and customers did not differ. Acceptance '
     f'was also low, since {pc(Q["items"]["BI1"]["All"]["agree_pct"])} percent said they would use Verity if it were available, and '
     f'intention was linked more to perceived usefulness than to ease of use.'),
]
for i, (q, a_) in enumerate(RQ, 1):
    qp = para(f'Research question {i}. {q}', align=WD_ALIGN_PARAGRAPH.LEFT, after=2)
    qp.runs[0].bold = True
    P(a_)
H3('4.6.3 Link between the questionnaire and the technical evaluation')
P(f'The two parts of the evaluation point in different directions. The simulation shows an engine that stopped every planted error '
  f'a rule targets, yet only {pc(Q["items"]["PU1"]["All"]["agree_pct"])} percent of respondents agreed that Verity would reduce errors '
  f'in orders. The respondents judged Verity from a demonstration lasting six to eight minutes, so the gap may reflect what the '
  f'demonstration showed rather than what the system does. The open answers support this reading. The two features requested most '
  f'often, a history of changes and approvals and a history of corrections, are already provided by the audit trail and the status '
  f'history, and the problem named most often concerned mobile access and low data use. The importance ratings of Table 4.5 do not '
  f'favour any check over the others, so they give no user priority against which the detection rates of Table 4.21 can be read. '
  f'Section C, which would have shown the error types respondents meet most often, could not be decoded, so the planted error types '
  f'cannot yet be compared with the errors seen in practice.')
H3('4.6.4 Discussion')
P('Section 2.4.3 adopted the information systems success model of DeLone and McLean (2003) as the frame that links what the '
  'simulation measures to the outcomes the study expects. In that frame the validation engine stands for information quality, '
  'and the reductions in error and processing time sought by Objectives 3 and 4 stand for net benefits. The evidence on '
  'information quality is strong for the errors the rules were written for. Every one of them was stopped in every replicate, and '
  f'no order reached approval with a mandatory field missing. It is weaker in two respects. Of the 200 clean orders, {A["fp"]} '
  'received a warning that turned out to be unnecessary, and warnings of this kind cost staff time and can teach users to ignore '
  'them. The engine also missed most errors that lie inside the allowed values. On system quality, validation responded within '
  'a fraction of a second, although its response time grew with the number of orders in two of the replicates. The small comparison '
  'with manual entry gives first evidence of net benefits, since far fewer errors reached the record through Verity than by hand, '
  'and it begins to close the second gap identified in Section 2.6, the lack of a comparison between validated digital entry and '
  'manual entry. The gain in speed remains to be measured. The questionnaire adds evidence on use and user satisfaction, and both are weak. A usability '
  f'score of {Q["sus"]["All"]["mean"]:.2f} and an intention to use of {pc(Q["items"]["BI1"]["All"]["agree_pct"])} percent mean that, in '
  'the terms of the model, the system quality shown in the simulation would not by itself lead to net benefits.')
P('The questionnaire results also bear on the acceptance theories of Section 2.4. In line with Davis (1989), intention was linked '
  'more closely to perceived usefulness than to ease of use, so the most direct route to acceptance is to show users the errors '
  'and rework the system removes. Fewer than half of the respondents agreed that their use would be voluntary. Where use is '
  'mandatory, Venkatesh et al. (2003) found that the expectations of managers and peers weigh more on intention, so the support of '
  'management would matter for adoption. The low usability score still matters in that setting. It is assumed here, though not '
  'tested, that staff required to use a system they find difficult may work around it.')
P('The pattern of what the engine missed matches the evidence reviewed in Section 2.2.2. Barchard and Pace (2011) found that only '
  'a small share of data entry errors are blank or outside the allowable range, so most cannot be caught by looking for obviously '
  'wrong values. The simulation shows the same limit from the system side. The rules check that each value is allowed, so they '
  'cannot tell when a customer chooses an allowed value by mistake, and a wrong but valid product or address passed in most cases. '
  'The unusual-quantity warning partly closes the gap for quantities, at the cost of false alarms, and the sensitivity analysis '
  'shows that the balance can be tuned but not removed. Errors in product choice or address would need a different kind of '
  'check, such as confirming the order back to the customer before approval.')
P('Two further results bear on the design set out in Chapter Two. Section 2.2.3 argued, following Elmagarmid et al. (2007), that '
  'an order system can prevent duplicates at intake rather than clean them afterwards, and all 20 planted duplicates in each '
  'replicate were held for the customer to confirm. Table 2.1 expects the pricing check to stop an outdated price. The engine '
  'did so when the price changed after an order was saved, but an outdated price quoted on an uploaded sheet was replaced by the '
  'list price without telling the customer, as functional test 16b shows. Finally, the integration route of Section 2.3.5 is only '
  'partly in place, since CSV import works but CSV export of orders and webhooks have not been built.')

# =====================================================================================================================
H2('4.7 Limitations')
lims = [
    'The orders were generated for the test, not taken from real customers. Each carried at most one planted error, and the '
    'proportion of erroneous orders was fixed at 60 percent. Real orders may carry several errors, and it is assumed that they are '
    'erroneous far less often, which would lower precision for the same false-alarm rate. The figures are therefore a test of the engine '
    'under known conditions, not an estimate of its performance in daily use.',
    'Only three kinds of error without a rule were planted. Real mistakes outside the rules may be more varied, so the primary '
    'accuracy could be higher or lower in practice.',
    'Each run took place inside one database transaction, so the database clock stood still during the run. The script used the '
    'wall clock for timing and status history, but every order counted as submitted at the same moment, which keeps all earlier '
    'orders within the 24-hour duplicate window. The customer histories were also synthetic.',
    'Validation time was measured inside the database and excludes network delay and the time people spend. It varied between '
    'replicates by an order of magnitude and grew within two of them. The cause was not confirmed, so the timing results describe '
    'the conditions of these runs only.',
    'The sensitivity analysis was run on replicate 1 alone, and each slip detection rate rests on 20 orders.',
    'The delivery-log export was tested by running its code outside the browser, because the live site could not be reached from '
    'the test environment.',
    'The comparison with manual entry covered 40 orders handled by two participants, so its results are indicative only. Its '
    'Verity side rests on the simulation outcome for the same orders rather than on people entering them in Verity, and the time a '
    'person spends entering an order in Verity was not measured, so no gain in speed is reported.',
    'The questionnaire respondents judged Verity from a demonstration video rather than by using it themselves, so their usability '
    'scores describe an impression of the system rather than experience of it. The questionnaire was administered by the client '
    'team to the people it could reach, which is not a random sample, and 45 respondents worked mainly outside Nigeria.',
    'The answers to section C of the questionnaire were supplied as numeric codes that could not be matched to the options with '
    'certainty, so frequency and type of order errors could not be reported. On the main channel, only 82 of the 200 answers were '
    'consistent with the channels the same respondent had ticked.',
]
for x in lims:
    P(x)

# =====================================================================================================================
H2('4.8 Summary')
P(f'Verity was built as a working order processing system with a controlled order lifecycle and nine validation rules, '
  f'protected by role-based access. Of {len(FT)} functional tests, {ft_pass} passed and the {len(ft_fail)} failures were reported. In three replicates of 500 '
  f'simulated orders the engine flagged every error that a rule targets, and accuracy on that basis was between '
  f'{RR["accuracy_targeted"]["min"]} and {RR["accuracy_targeted"]["max"]} percent. When realistic errors that no rule targets were '
  f'included, accuracy was between {RR["accuracy_all"]["min"]} and {RR["accuracy_all"]["max"]} percent, below the 90 percent target. '
  f'Nearly all false alarms came from the unusual-quantity warning, which also caught most quantity slips. Every order that reached '
  f'approval had its mandatory fields. In the questionnaire, {Q["valid"]} respondents gave Verity a mean usability score of '
  f'{Q["sus"]["All"]["mean"]:.2f}, significantly below the benchmark of 68, and {pc(Q["items"]["BI1"]["All"]["agree_pct"])} percent '
  f'said they would use it, so the usability and acceptance part of Objective 5 is Not met. In a small comparison with manual '
  f'entry, an error reached the record in {pc(MB["verity_error_rate"]["pct"])} percent of orders through Verity against '
  f'{pc(MB["manual_error_rate"]["pct"])} percent by hand, an indicative reduction of {pc(MB["error_reduction_pct"])} percent, while '
  f'the gain in speed remains to be measured.')

# =====================================================================================================================
H2('References')
refs = [
    'Bangor, A., Kortum, P. T., & Miller, J. T. (2008). An empirical evaluation of the System Usability Scale. International Journal of Human–Computer Interaction, 24(6), 574–594. https://doi.org/10.1080/10447310802205776',
    'Bangor, A., Kortum, P., & Miller, J. (2009). Determining what individual SUS scores mean: Adding an adjective rating scale. Journal of Usability Studies, 4(3), 114–123.',
    'Barchard, K. A., & Pace, L. A. (2011). Preventing human error: The impact of data entry methods on data accuracy and statistical results. Computers in Human Behavior, 27(5), 1834–1839. https://doi.org/10.1016/j.chb.2011.04.004',
    'Brooke, J. (1996). SUS: A "quick and dirty" usability scale. In P. W. Jordan, B. Thomas, B. A. Weerdmeester, & I. L. McClelland (Eds.), Usability evaluation in industry (pp. 189–194). Taylor & Francis.',
    'Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. Statistical Science, 16(2), 101–133. https://doi.org/10.1214/ss/1009213286',
    'Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. Psychometrika, 16(3), 297–334. https://doi.org/10.1007/BF02310555',
    'Davis, F. D. (1989). Perceived usefulness, perceived ease of use, and user acceptance of information technology. MIS Quarterly, 13(3), 319–340. https://doi.org/10.2307/249008',
    'DeLone, W. H., & McLean, E. R. (2003). The DeLone and McLean model of information systems success: A ten-year update. Journal of Management Information Systems, 19(4), 9–30. https://doi.org/10.1080/07421222.2003.11045748',
    'Elmagarmid, A. K., Ipeirotis, P. G., & Verykios, V. S. (2007). Duplicate record detection: A survey. IEEE Transactions on Knowledge and Data Engineering, 19(1), 1–16. https://doi.org/10.1109/TKDE.2007.250581',
    'Sauro, J., & Lewis, J. R. (2016). Quantifying the user experience: Practical statistics for user research (2nd ed.). Morgan Kaufmann.',
    'Venkatesh, V., Morris, M. G., Davis, G. B., & Davis, F. D. (2003). User acceptance of information technology: Toward a unified view. MIS Quarterly, 27(3), 425–478. https://doi.org/10.2307/30036540',
    'Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22(158), 209–212. https://doi.org/10.1080/01621459.1927.10502953',
]
for r in refs:
    p = para(r, align=WD_ALIGN_PARAGRAPH.LEFT)
    p.paragraph_format.left_indent = Cm(1.27)
    p.paragraph_format.first_line_indent = Cm(-1.27)

doc.save(HERE / 'Chapter_Four.docx')
XL.save(HERE / 'chapter_tables.xlsx')
with open(HERE / 'traceability_from_chapter.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['number_cited', 'meaning', 'source_file_and_field_or_cell'])
    w.writerows(TRACE)
print('tables', counters['table'], 'figures', counters['figure'])
