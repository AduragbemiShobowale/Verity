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
FT = list(csv.DictReader(open(ROOT / '02_functional_tests' / 'functional_tests.csv', encoding='utf-8')))
RLS = list(csv.DictReader(open(ROOT / '02_functional_tests' / 'rls_results_2026-10-27.csv')))
STAT = list(csv.DictReader(open(ROOT / '01_system_facts' / 'order_statuses.csv')))
RULES = list(csv.DictReader(open(ROOT / '01_system_facts' / 'validation_rules_and_run4_coverage.csv')))
PENDING = '[DATA PENDING]'
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
for name, size in (('Heading 1', 14), ('Heading 2', 12), ('Heading 3', 12)):
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
H1('Chapter Four. Results and Discussion')
H2('4.1 Introduction')
P('This chapter reports the evaluation of Verity, the intelligent order processing system developed in this project. '
  'It is written in two parts that are brought together in Section 4.6. Part A reports the questionnaire given to staff and '
  'customers of the case organisation before and after a demonstration of the system. Part B reports the technical evaluation, '
  'which covers the implemented system with its testing, and a controlled simulation in which orders with known planted '
  'errors were submitted to the live validation engine.')
P('At the time of writing the questionnaire had not been administered and the manual-entry comparison had not been run. '
  'Every result that depends on those activities is therefore marked [DATA PENDING] and every success criterion that rests on '
  'them is given the status Pending. All other figures in this chapter come from files and database queries produced during '
  'the evaluation, and each is listed with its source in the traceability table that accompanies the chapter.')

# =====================================================================================================================
H2('4.2 Part A. Questionnaire results')
P('The questionnaire has two parts. Part I is completed before the demonstration and covers consent, respondent group, '
  'current order handling, experience of order errors and their consequences, and the importance of twelve requirements. '
  'Part II is completed straight after the demonstration and contains the System Usability Scale in its standard wording '
  '(Brooke, 1996) together with items on perceived usefulness, ease of use, intention to use, facilitating conditions and '
  'voluntariness adapted from Davis (1989) and Venkatesh et al. (2003). The target is 150 valid responses from about 190 '
  'questionnaires distributed. No responses had been collected when this chapter was prepared, so Tables 4.1 to 4.4 are shells.')
table('Respondents by group', ['Group', 'Distributed', 'Returned', 'Valid', 'Valid share of returned'],
      [['Staff of the supplier', PENDING, PENDING, PENDING, PENDING], ['Customers', PENDING, PENDING, PENDING, PENDING],
       ['Total', 'about 190', PENDING, f'{PENDING} (target 150)', PENDING]],
      'questionnaire export, analysed with analyze_questionnaire.py. Not yet collected.')
P('Table 4.1 will report how many questionnaires were distributed and returned in each group and how many met the validity '
  'rule applied by the analysis script, which requires recorded consent and a complete set of usability items.')
table('Reliability of the multi-item scales', ['Scale', 'Items', "Cronbach's alpha"],
      [['System Usability Scale', 'SUS1 to SUS10, even items recoded', PENDING], ['Perceived usefulness', 'PU1 to PU3', PENDING],
       ['Ease of use', 'EOU1 to EOU3', PENDING], ['Facilitating conditions', 'FC1 and FC2', PENDING]],
      'questionnaire export, analysed with analyze_questionnaire.py. Not yet collected.')
P("Table 4.2 will report Cronbach's alpha for each multi-item scale (Cronbach, 1951) as a check that the items in each scale "
  'measure the same construct before scale scores are interpreted.')
table('System Usability Scale scores against the benchmark of 68',
      ['Statistic', 'Staff', 'Customers', 'All valid responses'],
      [[x, PENDING, PENDING, PENDING] for x in ('n', 'Mean', 'SD, sample', '95% CI', 't against 68', 'p, two-sided',
                                                 'Adjective, Bangor et al. (2009)', 'Acceptability, Bangor et al. (2008)', 'Grade, Sauro and Lewis (2016)')],
      'questionnaire export, analysed with analyze_questionnaire.py. Not yet collected.')
P('Table 4.3 will report the mean System Usability Scale score for each group with a 95 percent confidence interval and a '
  'one-sample t test against the benchmark of 68 recommended by Sauro and Lewis (2016). The mean will be interpreted with the '
  'adjective scale of Bangor et al. (2009) and the acceptability ranges of Bangor et al. (2008). It will also be placed on the '
  'curved grading scale of Sauro and Lewis (2016).')
table('Acceptance items, percent agreeing or strongly agreeing',
      ['Item', 'Code', 'Staff', 'Customers', 'All', '95% CI for all'],
      [['Perceived usefulness, three items', 'PU1 to PU3', PENDING, PENDING, PENDING, PENDING],
       ['Ease of use compared with sending a message', 'EOU1 to EOU3', PENDING, PENDING, PENDING, PENDING],
       ['Intention to use', 'BI1', PENDING, PENDING, PENDING, PENDING],
       ['Has a device to access Verity', 'FC1', PENDING, PENDING, PENDING, PENDING],
       ['Has enough data or internet access', 'FC2', PENDING, PENDING, PENDING, PENDING],
       ['Use would be voluntary', 'VOL1', PENDING, PENDING, PENDING, PENDING]],
      'questionnaire export, analysed with analyze_questionnaire.py. Not yet collected.')
P('Table 4.4 will report the share of each group agreeing with the acceptance items, with Wilson intervals, so that intention '
  'to use can be read alongside the facilitating-conditions and voluntariness items. Part I results on error types seen and '
  'requirement importance will be reported in the same way once collected, using the error-type wording that matches the '
  'fifteen planted error types of Part B.')

# =====================================================================================================================
H2('4.3 Part B. Implemented system and testing')
P('Verity is a web application with a React interface hosted on Vercel and a Supabase back end built on PostgreSQL 17. '
  'All business rules run inside the database as functions, and row-level security decides which records each signed-in user '
  'can read. Table 4.5 summarises the components that were built.')
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
P(f'Every order follows a lifecycle built from {FACTS["status_count"]} statuses, shown in Table 4.6. The database accepts '
  f'only the {FACTS["transition_count"]} transitions listed in its transition table, so an order cannot skip a step such as '
  'payment verification, and each change is written to the status history with the time and the user who made it.')
table('Order lifecycle statuses in order', ['No.', 'Status', 'Meaning'],
      [[r['position'], r['status'], r['meaning']] for r in STAT],
      'order_status type and order_transitions table, 01_system_facts/order_statuses.csv and state_machine_transitions.csv.', widths=[1.2, 4, 10.8])
P('Validation is carried out by nine rules that run every time a customer submits an order. Seven of them block the order '
  'until the customer corrects it and two raise a warning that sends the order to a person for review. Table 4.7 maps the '
  'nine rules to the seven checks set out in Table 2.1. The customer-details check is served by two rules, one for the account '
  'status and one for the delivery address, and the unusual-quantity rule is an addition that no check in Table 2.1 requires.')
table('Validation rules mapped to the seven checks of Table 2.1', ['Rule', 'What it checks', 'Severity', 'Check in Table 2.1'],
      [[r['rule'], r['check'], 'Blocking' if r['severity'] == 'blocking' else 'Warning', r['maps_to_seven_checks']] for r in RULES],
      '_validate function, 01_system_facts/validation_rules_and_run4_coverage.csv.', widths=[3.5, 7, 2, 3.5])
P(f'Functional testing exercised the order lifecycle end to end against the live database while acting as each role. Every '
  f'test ran inside a transaction that was rolled back, so no test data remained. The fourteen cases of the earlier test run '
  f'were repeated and twelve new cases were added for inactive customers, stale prices, automatic approval, CSV import and '
  f'export, and webhooks. Table 4.8 lists all {len(FT)} cases. Of these, {ft_pass} passed and {len(ft_fail)} failed.')
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
P('Access control was tested by querying the database directly as each role, bypassing the interface, so that the result '
  'shows what a user could reach even without the application screens. Table 4.9 gives the number of rows each account could '
  'read. Customers saw only their own company records and no product or audit rows, and the driver could read no '
  'business records at all. Attempts by a customer to change a price and to switch off automatic approval changed no rows.')
table('Rows visible to each account when querying the database directly',
      ['Account', 'Customers', 'Products', 'Orders', 'Invoices', 'Payments', 'Audit log', 'Simulation rows', 'Write attempt changed'],
      [[r['role_account'].split('@')[0] + ('' if 'verity' in r['role_account'] else ' (customer)'), r['customers'], r['products'], r['orders'], r['invoices'],
        r['payments'], r['audit_log'], r['simulation_orders'], r['rows_changed_by_write'] or 'not tried'] for r in RLS],
      'row-level security check run on 27 October 2026, 02_functional_tests/rls_results_2026-10-27.csv and rls_check.sql.', size=8.5)
P('The settings table, which holds values such as the tax rate and the automatic-approval switch, was readable by every signed-in '
  'account including drivers and customers. It could not be changed by them, but it is wider read access than the other tables allow.')

# =====================================================================================================================
H2('4.4 Simulation design and dataset')
P('Validation accuracy was measured with a controlled simulation. Orders were generated by a test harness and submitted through '
  'the same database functions a customer uses, save_draft followed by submit_order, so the rules saw them exactly as they would '
  'see a real order. Each order was either clean or carried one planted error of a known type. The harness held the planted error '
  'only in its own variables and wrote it to a results table after the run, so nothing the validation engine could read revealed '
  'which orders were erroneous. Each run took place inside a transaction that was rolled back, which removed every simulated '
  'customer and order and left the live data unchanged. The status history and the timing of each order were captured before '
  'the rollback.')
P('The final simulation used three replicates. Replicate 1 used the random seed 0.42 and is the headline result, while '
  'replicates 2 and 3 used the seeds 0.43 and 0.44. The further replicates '
  'show how much the measures move when the same design is drawn again. Each replicate contained 500 orders, made '
  'up of 200 clean orders and 300 erroneous orders, with 20 orders for each of fifteen planted error types. Twelve of the types '
  'are errors that a rule is designed to catch. The remaining three are realistic mistakes that no rule targets, shown at the '
  'foot of Table 4.10. Including them means the accuracy figures '
  'reflect mistakes the rules were not written for as well as those they were. Automatic approval was switched off so that every '
  'order passing validation went to the Ops Desk queue. Table 4.10 describes each planted error type.')
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
P(f'The simulation used the same twenty fictional customer companies and the same twelve-product catalogue as the first run. '
  f'Company names, contact names, telephone numbers and e-mail addresses are invented, and every e-mail address uses the reserved '
  f'.example domain. Each customer had two saved addresses in one of six delivery regions and four earlier orders, which give the '
  f'unusual-quantity rule a history to compare against. Table 4.11 describes the replicate 1 dataset.')
table('Description of the replicate 1 dataset', ['Measure', 'Value'],
      [['Orders', R1['orders']], ['Clean, rule-targeted and no-rule orders', f"{R1['clean']}, {R1['rule_targeted']}, {R1['no_rule']}"],
       ['Customers', DS['customers']], ['Orders per customer', f"{DS['orders_per_customer_min']} to {DS['orders_per_customer_max']}"],
       ['Mean lines per order', DS['lines_mean']], ['Mean units per order', DS['units_mean']],
       ['Order value, mean', naira(DS['value_mean'])], ['Order value, median', naira(DS['value_median'])],
       ['Order value, range', f"{naira(DS['value_min'])} to {naira(DS['value_max'])}"], ['Total order value', naira(DS['value_total'])],
       ['Orders by region', '; '.join(f'{k} {v}' for k, v in DS['regions'].items())]],
      'replicate 1, database run 5, 07_analysis/metrics_final.json dataset.', widths=[5, 11])
trace(naira(DS['value_total']), 'total order value replicate 1', 'metrics_final.json replicates.1.dataset.value_total')
P('The first run of the simulation, run 4, is kept as the first run and is not replaced. It used 500 orders whose types were drawn '
  'at random, so group sizes were unequal, and it planted no inactive-customer or stale-price errors. A defect in its harness also '
  'submitted 13 of its 35 wrong-product orders with an empty line, which the quantity rule blocked. Those 13 blocks were artefacts '
  'of the harness, not detections. The final simulation corrected the defect and added the two '
  'missing types, with twenty orders of every type, so its results are the ones assessed in this chapter.')
trace(13, 'run 4 harness artefacts', '01_system_facts/system_facts.json run4_harness_defect')

# =====================================================================================================================
H2('4.5 Simulation results')
og = R1['outcomes_by_group']
P(f'Figure 4.1 shows what happened to each group of orders in replicate 1. Of the 200 clean orders, {og["clean"]["pass"]} passed '
  f'and {og["clean"]["warn"]} were warned. All 240 orders with a rule-targeted error were stopped, {og["rule_targeted"]["fail"]} '
  f'by a blocking rule and {og["rule_targeted"]["warn"]} by the duplicate warning. Of the 60 orders with an error that no rule '
  f'targets, {og["no_rule"]["warn"]} were warned and {og["no_rule"]["pass"]} passed. After submission '
  f'{R1["statuses_after_submit"]["validation_failed"]} orders were in validation failed and {R1["statuses_after_submit"]["pending_approval"]} '
  f'were waiting for approval. The other {R1["statuses_after_submit"]["draft"]} were held as drafts until the customer confirmed a possible repeat.')
trace(og['clean']['warn'], 'clean orders warned, replicate 1', 'metrics_final.json replicates.1.outcomes_by_group.clean.warn; workbook R1 Summary D5')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_1_outcomes.png', 'Outcome of each group of orders in replicate 1',
       '07_analysis/figures/fig4_1_outcomes_data.csv, from replicate 1, database run 5.')
P('Table 4.12 gives the detection rate for each planted error type with a 95 percent Wilson interval, which behaves better than '
  'the simple normal interval for small groups and for rates near zero or one (Brown et al., 2001; Wilson, 1927). Every one of the '
  'twelve rule-targeted types was flagged in all 20 of its orders, and in each case by the rule designed for it. Figure 4.2 '
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
figure(ROOT / '07_analysis' / 'figures' / 'fig4_2_detection.png', 'Detection rate by planted error type with 95 percent Wilson intervals, replicate 1',
       '07_analysis/figures/fig4_2_detection_data.csv, from replicate 1, database run 5.')
P(f'The three types without a rule tell a different story. The quantity typing slip was flagged in {BT["qty_typo"]["detection"]["k"]} '
  f'of 20 orders, and in each of these the unusual-quantity warning named the very line that carried the slip, so this is genuine '
  f'detection by a rule that was not designed for it. The wrong product and the wrong address were each flagged in '
  f'{BT["wrong_product"]["detection"]["k"]} of 20 orders, but in none of those cases did the warning concern the planted error. '
  f'The warnings were about other lines or, once, about a possible repeat, so these flags are coincidental. A wrong but valid '
  f'product or address is in effect invisible to the engine, which is what one would expect of rules that check whether a value '
  f'is allowed rather than whether it is what the customer meant.')
trace(f"{NR['qty_typo']['warning_names_planted_line']}/{NR['qty_typo']['flagged']}", 'typo flags naming the typo line', 'metrics_final.json replicates.1.no_rule_flag_on_planted_line')
P(f'For the binary measures an order counts as flagged when it is warned or blocked and as positive when it carries a planted error. '
  f'The primary measure uses all 300 erroneous orders against the 200 clean orders, and the secondary measure uses only the 240 '
  f'rule-targeted orders against the same clean orders. Table 4.13 gives both confusion matrices for replicate 1 and Table 4.14 '
  f'gives the measures with their intervals.')
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
  f'orders in each. Figure 4.3 shows the measures with their intervals and marks the values from replicates 2 and 3.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_3_measures.png', 'Validation measures with 95 percent Wilson intervals',
       '07_analysis/figures/fig4_3_measures_data.csv, from replicates 1 to 3, database runs 5 to 7.')
P(f'Table 4.15 shows how often each rule fired. The seven blocking rules fired only on erroneous orders and never on a clean '
  f'one. The stock rule also fired on the {RU["stock"]["on_other_error_types"]} orders whose quantity was above the maximum or '
  f'whose product was discontinued, because both also exceed the stock on hand. All {R1["confusion_all_errors"]["fp"]} false alarms on '
  f'clean orders came from the two warning rules, {R1["false_alarm_reasons"].get("unusual_quantity", 0)} from the unusual-quantity '
  f'rule and {R1["false_alarm_reasons"].get("duplicate", 0)} from the duplicate rule. The unusual-quantity rule fired on '
  f'{RU["unusual_quantity"]["orders_fired"]} orders in all, and on {pc(RU["unusual_quantity"]["false_alarm_rate_on_clean"]["pct"])} '
  f'percent of clean orders.')
table('Rule activity and false alarms, replicate 1',
      ['Rule', 'Severity', 'Orders fired', 'On its target type', 'On other error types', 'On clean orders', 'False alarms per clean order, 95% CI'],
      [[r['label'], 'Warning' if r['severity'] == 'warn' else 'Blocking', r['orders_fired'], r['on_target_type'], r['on_other_error_types'],
        r['on_clean_false_alarms'], f"{pc(r['false_alarm_rate_on_clean']['pct'])} ({ci(r['false_alarm_rate_on_clean'])})"] for r in R1['rules']],
      'replicate 1, 07_analysis/metrics_final.json rules, workbook R1 Summary section E.', size=8.5)
trace(RU['unusual_quantity']['on_clean_false_alarms'], 'unusual-quantity false alarms, replicate 1', 'metrics_final.json replicates.1.rules unusual_quantity; workbook R1 Summary E')
blk = R1['validation_ms_mean_by_block_of_100']
P(f'Validation time was measured as the clock time of submit_order inside the database, which validates the order and records '
  f'the status change. It excludes network time and any time a person spends. Table 4.16 gives the statistics '
  f'for replicate 1. The standard deviation is the sample value. The mean was {TM["mean"]} ms and the median {TM["median"]} ms, '
  f'with a 95th percentile of {TM["p95"]} ms and a maximum of {TM["max"]} ms. The time measured from the draft event to the last '
  f'event in the status history gave a mean of {R1["status_history_draft_to_last_event_ms"]["mean"]} ms over the '
  f'{R1["status_history_orders_with_two_or_more_events"]} orders that had more than one event.')
table('Validation time per order in milliseconds, replicate 1', ['Statistic', 'All orders', 'Passed', 'Warned', 'Blocked'],
      [[lab] + [R1['validation_ms'][k]] + [R1['validation_ms_by_outcome'][o][k] for o in ('pass', 'warn', 'fail')]
       for lab, k in (('Orders', 'n'), ('Mean', 'mean'), ('SD, sample', 'sd_sample'), ('Median', 'median'), ('95th percentile', 'p95'), ('Minimum', 'min'), ('Maximum', 'max'))],
      'replicate 1, 07_analysis/metrics_final.json validation_ms, workbook R1 Summary section F.')
trace(TM['mean'], 'mean validation ms, replicate 1', 'metrics_final.json replicates.1.validation_ms.mean; workbook R1 Summary F')
P(f'The time was not stable across the run. Figure 4.4 shows that in replicate 1 the mean rose from {blk[0]:.2f} ms for the first 100 '
  f'orders to {blk[-1]:.2f} ms for the last 100, and replicate 2 followed the same path. The rules that look back over a customer\'s '
  f'earlier orders have more orders to examine as the run goes on, which is consistent with this rise. Replicate 3 stayed between '
  f'{R["3"]["validation_ms_mean_by_block_of_100"][0]:.2f} and {R["3"]["validation_ms_mean_by_block_of_100"][-1]:.2f} ms throughout. The '
  f'harness was the same in every run. It is assumed, but was not confirmed, that the database chose a different query plan '
  f'in that run. In every replicate a single order was validated in well under a second.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_4_timing.png', 'Validation time per order across each run, mean of each block of 100 orders',
       '07_analysis/figures/fig4_4_timing_data.csv, from replicates 1 to 3, database runs 5 to 7.')
spread = max(round(RR[k]['max'] - RR[k]['min'], 1) for k in RR if not k.startswith('validation_ms'))
P(f'Table 4.17 sets the key measures of the three replicates side by side. No accuracy or detection measure moved by more than '
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
P(f'Because the unusual-quantity rule caused nearly all false alarms and also caught the quantity slips, its setting was examined. '
  f'Replicate 1 was replayed through the live functions with the threshold set from three to five times the customer\'s '
  f'average in steps of one, and with four or ten earlier orders per customer. The replay with the live setting reproduced replicate 1 exactly, with '
  f'no difference in any order, so the six settings in Table 4.18 are compared on identical orders. These runs are for discussion '
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
  f'because each rests on 20 orders, so these differences show a direction rather than settled values. Figure 4.5 shows the trade-off.')
figure(ROOT / '07_analysis' / 'figures' / 'fig4_5_sensitivity.png', 'Effect of the unusual-quantity threshold and history length on false alarms and slip detection',
       '07_analysis/figures/fig4_5_sensitivity_data.csv, from replays of database run 5.')
mand = R1['mandatory_completion_reaching_approval']
P(f'Mandatory-field completion was measured on the orders that reached approval. All {mand["k"]} of the {mand["n"]} orders that '
  f'reached the approval queue in replicate 1 had every mandatory field filled, with a 95 '
  f'percent interval of {ci(mand)} percent, and the same was true in the other replicates. This follows from the design, since '
  f'the mandatory-fields rule blocks any order without them, and the simulation confirms that no such order got through.')
trace(f"{mand['k']}/{mand['n']}", 'mandatory completion, replicate 1', 'metrics_final.json replicates.1.mandatory_completion_reaching_approval; workbook R1 Summary G')

# =====================================================================================================================
H2('4.6 Integrated evaluation and discussion')
P(f'Table 4.19 sets each objective against its success criterion. The wording of the objectives in Chapter One was not available '
  f'when this chapter was drafted, so the table marks where that wording must be inserted and describes each objective in brief. '
  f'Objective 1 is not listed because its criterion was not supplied.')
obj_rows = [
    [f'{WORDING} Objective 2, validation engine for SKU, quantity, customer details, pricing, duplicate orders, stock and mandatory fields',
     'At least 90 percent validation accuracy',
     f'Primary {pc(A["accuracy"]["pct"])} percent, all errors. Secondary {pc(T["accuracy"]["pct"])} percent, rule-targeted errors. Replicates {RR["accuracy_all"]["min"]} to {RR["accuracy_all"]["max"]} and {RR["accuracy_targeted"]["min"]} to {RR["accuracy_targeted"]["max"]}',
     f'{ci(A["accuracy"])} and {ci(T["accuracy"])}', 'Partly met'],
    [f'{WORDING} Objective 3, fewer manual entry errors', 'At least 60 percent fewer manual entry errors', PENDING, PENDING, 'Pending'],
    [f'{WORDING} Objective 3, mandatory fields', '100 percent mandatory-field completion',
     f'{mand["k"]} of {mand["n"]} orders reaching approval, 100 percent in all three replicates', ci(mand), 'Met'],
    [f'{WORDING} Objective 4, processing speed', '30 to 50 percent faster processing', PENDING, PENDING, 'Pending'],
    [f'{WORDING} Objective 5, usability and acceptance', 'Usability and acceptance shown by the questionnaire', PENDING, PENDING, 'Pending'],
    [f'{WORDING} Objective 5, simulated orders', '500 simulated orders processed', '500 orders in each of three replicates, 1,500 in all', 'not applicable', 'Met'],
]
table('Objectives and success criteria', ['Objective', 'Criterion', 'Result', '95% CI', 'Status'], obj_rows,
      'Sections 4.2 to 4.5. Accuracy judged on the primary measure with the secondary measure in support.', widths=[4.5, 3.2, 4.8, 2.2, 1.3], size=8.5)
P(f'The accuracy objective is rated Partly met. On the primary measure accuracy did not reach 90 percent in any replicate, and the '
  f'upper end of the replicate 1 interval was {A["accuracy"]["ci95"][1]:.1f} percent. On the rule-targeted errors it exceeded 90 percent '
  f'in every replicate and the whole interval lay above the target. Both measures share the same false alarms, so the gap between '
  f'them comes from the {A["fn"]} errors without a rule that were missed, {40 - BT["wrong_product"]["detection"]["k"] - BT["wrong_address"]["detection"]["k"]} of them wrong products or wrong addresses. The '
  f'mandatory-fields criterion is Met. The error-reduction and speed criteria remain Pending until the manual baseline is run and '
  f'scored with analyze_baseline.py. Below about 80 paired orders that comparison of errors will be indicative only. Usability and '
  f'acceptance remain Pending until the questionnaire data exist.')
P(f'The research questions are answered below in the order of Chapter One. Their exact wording was not available, so each is '
  f'marked for insertion and, as an assumption, the questions are taken to follow the order of the objectives.')
rq = [
    ('Research question 1', f'{WORDING} The implemented system shows that order entry, validation, approval, payment, picking and '
     f'delivery can be run as one controlled lifecycle of {FACTS["status_count"]} statuses with role-based access, and '
     f'{ft_pass} of {len(FT)} functional tests passed. The failed tests concern features that are missing or incomplete, '
     f'and Section 4.3 reports each of them.'),
    ('Research question 2', f'{WORDING} Automated validation caught every rule-targeted error in all three replicates and reached '
     f'{pc(A["accuracy"]["pct"])} percent accuracy when errors outside the rules were included. That is below the 90 percent target, '
     f'and most of the remaining errors are of a kind no rule can detect.'),
    ('Research question 3', f'{WORDING} No mandatory field was missing on any order that reached approval. Whether Verity reduces '
     f'manual entry errors by 60 percent cannot yet be answered and is {PENDING}.'),
    ('Research question 4', f'{WORDING} Validation itself takes milliseconds per order, but the criterion concerns end-to-end '
     f'processing time against manual handling, and that answer is {PENDING}.'),
    ('Research question 5', f'{WORDING} The answer on usability and acceptance depends on the questionnaire and is {PENDING}.'),
]
for k, v in rq:
    P(f'{k}. {v}')
P(f'The link between Part A and Part B, for example whether the errors respondents report most often are those the engine catches, '
  f'can only be drawn once the questionnaire has been completed and is {PENDING}.')
P('The DeLone and McLean (2003) model of information systems success offers a frame for these results. It links the qualities '
  'of a system to its use and to user satisfaction, and through these to net benefits. Part B gives evidence on system quality. The engine stopped every planted error that '
  'a rule targets and responded within a fraction of a second, although its response time grew as order volume grew in two of '
  'the replicates. On information quality, each message stated the problem in plain words and named the product where the problem lay on a line, which the questionnaire '
  f'can test from the user side, yet {A["fp"]} of the 200 clean orders received a warning that turned out to be unnecessary.'
  ' False alarms of '
  'this kind cost staff time and can teach users to ignore warnings, so they weigh against the net benefits the model predicts. '
  'Service quality, use, user satisfaction and the net benefits themselves rest on the questionnaire and the manual baseline, '
  'and remain to be assessed.')
P('The results also show where the design reaches its limits. The rules check that each value is allowed, so they cannot tell when '
  'a customer chooses an allowed value by mistake. The unusual-quantity warning partly closes that gap for quantities, at the cost of '
  'false alarms, and the sensitivity analysis shows that the balance can be tuned but not removed. Errors in product choice or '
  'address would need a different kind of check, such as confirming the order back to the customer before approval.')

# =====================================================================================================================
H2('4.7 Limitations')
lims = [
    'The orders were generated by a harness, not taken from real customers. Each carried at most one planted error, and the '
    'proportion of erroneous orders was fixed at 60 percent. Real orders may carry several errors, and it is assumed that they are '
    'erroneous far less often, which would lower precision for the same false-alarm rate. The figures are therefore a test of the engine '
    'under known conditions, not an estimate of its performance in daily use.',
    'Only three kinds of error without a rule were planted. Real mistakes outside the rules may be more varied, so the primary '
    'accuracy could be higher or lower in practice.',
    'Each run took place inside one database transaction, so the database clock stood still during the run. The harness used the '
    'wall clock for timing and status history, but every order counted as submitted at the same moment, which keeps all earlier '
    'orders within the 24-hour duplicate window. The customer histories were also synthetic.',
    'Validation time was measured inside the database and excludes network delay and the time people spend. It varied between '
    'replicates by an order of magnitude and grew within two of them. The cause was not confirmed, so the timing results describe '
    'the conditions of these runs only.',
    'The sensitivity analysis was run on replicate 1 alone, and each slip detection rate rests on 20 orders.',
    'The delivery-log export was tested by running its code outside the browser, because the live site could not be reached from '
    'the test environment.',
    'The questionnaire and the manual baseline had not been carried out, so the objectives on error reduction, speed, usability '
    'and acceptance could not be assessed.',
    'The exact wording of the objectives and research questions in Chapter One was not available to this chapter.',
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
  f'approval had its mandatory fields. The questionnaire and the manual baseline remain to be carried out, and the objectives that '
  f'depend on them are Pending.')

# =====================================================================================================================
H2('References')
refs = [
    'Bangor, A., Kortum, P. T., & Miller, J. T. (2008). An empirical evaluation of the System Usability Scale. International Journal of Human–Computer Interaction, 24(6), 574–594. https://doi.org/10.1080/10447310802205776',
    'Bangor, A., Kortum, P., & Miller, J. (2009). Determining what individual SUS scores mean: Adding an adjective rating scale. Journal of Usability Studies, 4(3), 114–123.',
    'Brooke, J. (1996). SUS: A "quick and dirty" usability scale. In P. W. Jordan, B. Thomas, B. A. Weerdmeester, & I. L. McClelland (Eds.), Usability evaluation in industry (pp. 189–194). Taylor & Francis.',
    'Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. Statistical Science, 16(2), 101–133. https://doi.org/10.1214/ss/1009213286',
    'Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. Psychometrika, 16(3), 297–334. https://doi.org/10.1007/BF02310555',
    'Davis, F. D. (1989). Perceived usefulness, perceived ease of use, and user acceptance of information technology. MIS Quarterly, 13(3), 319–340. https://doi.org/10.2307/249008',
    'DeLone, W. H., & McLean, E. R. (2003). The DeLone and McLean model of information systems success: A ten-year update. Journal of Management Information Systems, 19(4), 9–30. https://doi.org/10.1080/07421222.2003.11045748',
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
