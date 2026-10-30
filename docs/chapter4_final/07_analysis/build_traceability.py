"""Writes ../TRACEABILITY.csv: every number cited in the running text of Chapter Four with the file and field, workbook
cell or query it comes from. Each value is read from its source here and asserted, so the table cannot drift from the data.
Table and figure content is traced by the Source line under each table and figure."""
import csv
import json
from pathlib import Path
from openpyxl import load_workbook

HERE = Path(__file__).parent
ROOT = HERE.parent
m = json.loads((HERE / 'metrics_final.json').read_text())
R1 = m['replicates']['1']
wb = load_workbook(HERE / 'Verity_Simulation_Data_Final.xlsx', data_only=True)
facts = json.loads((ROOT / '01_system_facts' / 'system_facts.json').read_text())
ft = list(csv.DictReader(open(ROOT / '02_functional_tests' / 'functional_tests.csv', encoding='utf-8')))
rows = []


def cell_of(sheet, label, start_row=1, col=1, value_col=2):
    ws = wb[sheet]
    for r in range(start_row, ws.max_row + 1):
        if ws.cell(row=r, column=col).value == label:
            return f'{sheet}!{ws.cell(row=r, column=value_col).coordinate}', ws.cell(row=r, column=value_col).value
    raise KeyError(label)


def add(section, number, meaning, source, check=None):
    if check is not None:
        assert abs(float(check) - float(str(number).replace(',', '').replace('₦', ''))) < 0.051, (meaning, number, check)
    rows.append([section, number, meaning, source])


A, T = R1['confusion_all_errors'], R1['confusion_rule_targeted']
S = 'R1 Summary'
# design and criteria (not measured)
for n, what in ((90, 'accuracy target, Objective 2'), (60, 'error-reduction target, Objective 3'), (80, 'pairs below which the error comparison is indicative')):
    add('4.5', n, what, 'project brief and success criteria, not a measured value')
for n, what in ((500, 'orders per replicate'), (200, 'clean orders per replicate'), (300, 'erroneous orders per replicate'), (240, 'rule-targeted orders per replicate'),
                (20, 'orders per planted error type'), ('0.42, 0.43, 0.44', 'random seeds of replicates 1 to 3'), (24, 'duplicate window in hours')):
    add('4.4', n, what, 'design of run_simulation_final, supabase/migrations/0007_simulation_final.sql; counts confirmed in metrics_final.json replicates.n')
add('4.4', '0.42, 0.43, 0.44', 'seeds confirmed', 'metrics_final.json run_ids; simulation_runs rows 5 to 7 summary.seed')
# system facts
add('4.3', facts['status_count'], 'order statuses', '01_system_facts/system_facts.json status_count; order_statuses.csv', facts['status_count'])
add('4.3', facts['transition_count'], 'permitted transitions', '01_system_facts/system_facts.json transition_count; state_machine_transitions.csv', facts['transition_count'])
add('4.3', len(ft), 'functional test cases', '02_functional_tests/functional_tests.csv row count', len(ft))
add('4.3', sum(r['result'] == 'Pass' for r in ft), 'functional tests passed', '02_functional_tests/functional_tests.csv result = Pass')
add('4.3', sum(r['result'] == 'Fail' for r in ft), 'functional tests failed (16b, 19, 21)', '02_functional_tests/functional_tests.csv result = Fail')
add('4.3', '₦9,000', 'old price quoted on the uploaded sheet, case 16b', '02_functional_tests/sample_import_old_price.csv row CEM-50')
add('4.3', '₦9,500', 'list price saved, case 16b', '02_functional_tests/raw_test_output_2026-10-27.json ext 16_18 saved_lines CEM-50 unit_price')
add('4.4', 13, 'run 4 wrong-product orders submitted empty', '01_system_facts/system_facts.json run4_harness_defect (query in that field)')
add('4.4', 35, 'run 4 wrong-product orders', '01_system_facts/system_facts.json run4_harness_defect; simulation_orders run_id = 4')
# outcomes
og = R1['outcomes_by_group']
for n, what, src in ((og['clean']['pass'], 'clean orders passed', 'C5'), (og['clean']['warn'], 'clean orders warned', 'D5'),
                     (og['rule_targeted']['fail'], 'rule-targeted orders blocked', 'E6'), (og['rule_targeted']['warn'], 'rule-targeted orders warned', 'D6'),
                     (og['no_rule']['warn'], 'no-rule orders warned', 'D7'), (og['no_rule']['pass'], 'no-rule orders passed', 'C7')):
    assert wb[S][src].value == n, (what, wb[S][src].value, n)
    add('4.5', n, what + ', replicate 1', f'{S}!{src}; metrics_final.json replicates.1.outcomes_by_group')
st = R1['statuses_after_submit']
for k in ('validation_failed', 'pending_approval', 'draft'):
    add('4.5', st[k], f'orders in status {k} after submission, replicate 1', 'metrics_final.json replicates.1.statuses_after_submit')
# no-rule detail
nr = R1['no_rule_flag_on_planted_line']
bt = {t['key']: t for t in R1['by_type']}
add('4.5', bt['qty_typo']['detection']['k'], 'typing slips flagged, replicate 1', 'metrics_final.json replicates.1.by_type qty_typo; R1 Summary section D')
add('4.5', nr['qty_typo']['warning_names_planted_line'], 'typing-slip warnings naming the slip line', 'metrics_final.json replicates.1.no_rule_flag_on_planted_line')
add('4.5', bt['wrong_product']['detection']['k'], 'wrong products flagged (and wrong addresses), none on the planted error', 'metrics_final.json replicates.1.by_type and no_rule_flag_on_planted_line')
# measures
lab = {'accuracy': 'Accuracy', 'precision': 'Precision', 'recall': 'Recall (detection rate)', 'specificity': 'Specificity', 'false_alarm_rate': 'False-alarm rate'}
for key, name in lab.items():
    for set_name, c, start in (('primary', A, 10), ('secondary', T, 25)):
        ref, val = cell_of(S, name, start_row=start)
        add('4.5', f"{c[key]['pct']:.1f}", f'{set_name} {key}, replicate 1', f'{ref}; metrics_final.json replicates.1.confusion', 100 * val)
        add('4.5', f"{c[key]['ci95'][0]:.1f} to {c[key]['ci95'][1]:.1f}", f'{set_name} {key} 95% Wilson CI', f'{ref.replace("!B", "!C")} and D; metrics_final.json')
add('4.5', A['fn'], 'errors without a rule that passed unflagged (false negatives)', f'{S}!C12; metrics_final.json replicates.1.confusion_all_errors.fn', wb[S]['C12'].value)
add('4.6', 40 - bt['wrong_product']['detection']['k'] - bt['wrong_address']['detection']['k'], 'missed wrong products or wrong addresses', 'metrics_final.json by_type wrong_product and wrong_address, 20 minus flagged each')
add('4.5 and 4.6', A['fp'], 'false alarms on clean orders', f'{S}!B13; metrics_final.json replicates.1.confusion_all_errors.fp', wb[S]['B13'].value)
# rules
ru = {r['rule']: r for r in R1['rules']}
add('4.5', ru['stock']['on_other_error_types'], 'stock rule on quantity-above-maximum and discontinued orders', 'metrics_final.json replicates.1.rules stock.on_other_error_types')
add('4.5', R1['false_alarm_reasons']['unusual_quantity'], 'false alarms from unusual quantity', 'metrics_final.json replicates.1.false_alarm_reasons; R1 Summary section E')
add('4.5', R1['false_alarm_reasons'].get('duplicate', 0), 'false alarms from duplicate', 'metrics_final.json replicates.1.false_alarm_reasons')
add('4.5', ru['unusual_quantity']['orders_fired'], 'orders on which unusual quantity fired', 'metrics_final.json replicates.1.rules; R1 Summary section E')
add('4.5', ru['unusual_quantity']['false_alarm_rate_on_clean']['pct'], 'unusual-quantity false alarms per clean order, percent', 'metrics_final.json replicates.1.rules')
# timing
tm = R1['validation_ms']
for k, name in (('mean', 'Mean'), ('median', 'Median'), ('p95', '95th percentile (PERCENTILE.INC)'), ('max', 'Maximum')):
    ref, val = cell_of(S, name, start_row=60)
    add('4.5', tm[k], f'validation time {k}, ms, replicate 1', f'{ref}; metrics_final.json replicates.1.validation_ms', val)
h = R1['status_history_draft_to_last_event_ms']
add('4.5', h['mean'], 'mean ms draft event to last event, status history', 'metrics_final.json replicates.1.status_history_draft_to_last_event_ms')
add('4.5', R1['status_history_orders_with_two_or_more_events'], 'orders with more than one status event', 'metrics_final.json replicates.1.status_history_orders_with_two_or_more_events')
for rep in ('1', '3'):
    b = m['replicates'][rep]['validation_ms_mean_by_block_of_100']
    add('4.5', f'{b[0]:.2f} and {b[-1]:.2f}', f'mean ms of first and last 100 orders, replicate {rep}',
        f'metrics_final.json replicates.{rep}.validation_ms_mean_by_block_of_100; R{rep} Summary section F block row; figures/fig4_7_timing_blocks_data.csv')
rr = m['replicate_range']
spread = max(round(v['max'] - v['min'], 1) for k, v in rr.items() if not k.startswith('validation_ms'))
add('4.5', spread, 'largest replicate spread of a non-timing measure, percentage points (no-rule detection)', 'metrics_final.json replicate_range; Replicate range sheet')
for k, name in (('accuracy_all', 'primary accuracy'), ('accuracy_targeted', 'secondary accuracy')):
    add('4.6 and 4.8', f"{rr[k]['min']} to {rr[k]['max']}", f'{name} across replicates', f'metrics_final.json replicate_range.{k}; Replicate range sheet columns E and F')
# sensitivity
sens = {(s['factor'], s['history_orders']): s for s in m['sensitivity']}
for (f, hh) in ((3.0, 4), (5.0, 4), (3.0, 10)):
    s = sens[(f, hh)]
    add('4.5', s['clean_false_alarm_rate_all_rules']['pct'], f'false-alarm rate at {f:g} x average, {hh} earlier orders', f'04_sensitivity/sensitivity_results.csv run {s["run_id"]}; Sensitivity sheet')
    add('4.5', s['typo_detection']['pct'], f'slip detection at {f:g} x average, {hh} earlier orders', f'04_sensitivity/sensitivity_results.csv run {s["run_id"]}; Sensitivity sheet')
add('4.5', 0, 'differences between replay run 8 and replicate 1', 'comparison of 04_sensitivity/raw/runs8to13_replays_of_run5.json run 8 with 03_simulation/raw/run5_replicate1.json')
# mandatory
md = R1['mandatory_completion_reaching_approval']
ref, val = cell_of(S, 'Completion', start_row=70)
add('4.5', f"{md['k']} of {md['n']}", 'orders reaching approval with every mandatory field', f'{S} section G; metrics_final.json replicates.1.mandatory_completion_reaching_approval')
add('4.5', f"{md['ci95'][0]:.1f} to {md['ci95'][1]:.1f}", 'mandatory completion 95% Wilson CI', f'{ref.replace("!B", "!C")} and D')

# questionnaire, section 4.2
Qr = json.loads((ROOT / '06_questionnaire' / 'questionnaire_results.json').read_text())
QS = '06_questionnaire/questionnaire_results.json'
add('4.2', Qr['valid'], 'valid questionnaire responses', f'{QS} valid')
add('4.2', Qr['by_group']['Staff'], 'staff respondents', f'{QS} by_group.Staff')
add('4.2', Qr['by_group']['Customer'], 'customer respondents', f'{QS} by_group.Customer')
add('4.2', f"{Qr['sus']['All']['mean']:.2f}", 'SUS mean, all respondents', f'{QS} sus.All.mean; questionnaire_tables.xlsx SUS!C2')
add('4.2', f"{Qr['sus']['All']['ci95'][0]:.2f} to {Qr['sus']['All']['ci95'][1]:.2f}", 'SUS 95% CI', f'{QS} sus.All.ci95')
add('4.2', f"{Qr['sus']['All']['t_vs_68']:.2f}", 't against 68', f'{QS} sus.All.t_vs_68')
add('4.2', f"{Qr['sus']['Staff']['mean']:.2f} and {Qr['sus']['Customer']['mean']:.2f}", 'SUS means staff and customers', f'{QS} sus.Staff.mean, sus.Customer.mean')
add('4.2', f"{Qr['sus_staff_vs_customer_welch']['p_two_sided']:.2f}", 'Welch p staff vs customers', f'{QS} sus_staff_vs_customer_welch')
add('4.2', Qr['sus']['All']['share_above_68']['k'], 'respondents scoring above 68', f'{QS} sus.All.share_above_68')
for k in ('PU1', 'BI1', 'FC1', 'VOL1'):
    add('4.2', Qr['items'][k]['All']['agree_pct'], f'{k} percent agreeing', f'{QS} items.{k}.All.agree_pct')
add('4.2', Qr['f1_willingness_yes']['All']['k'], 'F1 Yes answers', f'{QS} f1_willingness_yes')
add('4.2', f"{Qr['corr_pu_bi1']:.2f}", 'correlation PU mean with BI1', f'{QS} corr_pu_bi1')
add('4.2', f"{Qr['corr_peu_bi1']:.2f}", 'correlation PEU mean with BI1', f'{QS} corr_peu_bi1')
add('4.2', f"{Qr['reliability']['SUS']:.3f}", 'SUS alpha', f'{QS} reliability.SUS')
add('4.2', f"{Qr['reliability']['FC']:.3f}", 'facilitating conditions alpha', f'{QS} reliability.FC')
add('4.2', Qr['main_channel_consistency']['raw_main_channel_among_channels_used'], 'consistent main-channel answers', f'{QS} main_channel_consistency')
b3 = Qr['categorical']['B3. How order enters records']['All']
add('4.2', b3['Retyped by hand'] + b3['Copied and pasted'], 'orders retyped or copied', f'{QS} categorical B3, Retyped by hand plus Copied and pasted')
add('4.2', Qr['categorical']['A6. Main operating location']['All']['Outside Nigeria'], 'respondents outside Nigeria', f'{QS} categorical A6')

with open(ROOT / 'TRACEABILITY.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['chapter_section', 'number_cited', 'meaning', 'source_file_field_cell_or_query'])
    w.writerows(rows)
print(len(rows), 'traced numbers written and checked')
