"""Writes questionnaire.md, codebook.csv and export_column_template.csv from CODES in analyze_questionnaire.py."""
import csv
from pathlib import Path
from analyze_questionnaire import CODES, MULTI_COLUMNS, export_columns

HERE = Path(__file__).parent
with open(HERE / 'codebook.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['code', 'part', 'section', 'wording', 'response_type', 'coding'])
    w.writerows(CODES)
with open(HERE / 'export_column_template.csv', 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerow(export_columns())

md = ['# Verity order system questionnaire', '',
      'Part I is completed before the demonstration and Part II straight after it. Codes in brackets are for the data export only and are removed from the printed or online form.', '']
section = part = None
n = 0
for code, p, sec, text, typ, opts in CODES:
    if p == 'Admin':
        continue
    if p != part:
        part = p
        md += ['', f'## Part {p}: ' + ('before the demonstration' if p == 'I' else 'after the demonstration'), '']
        if p == 'II':
            md += ['Please answer about the Verity system you have just seen. For each statement choose one answer: 1 Strongly disagree, 2 Disagree, 3 Neither agree nor disagree, 4 Agree, 5 Strongly agree.', '']
    if sec != section:
        section = sec
        md += [f'### {sec}', '']
        if code == 'IMP1':
            md += ['How important is each of the following to you? 1 Not important, 2 Slightly important, 3 Moderately important, 4 Very important, 5 Extremely important.', '']
    if code == 'ERR_SKU':
        n += 1
        md += [f'{n}. Which of these mistakes have you seen in an order in the last three months? Tick each one you have seen.', '']
    if typ != 'multi-item':
        n += 1
    if typ == 'multi-item':
        md.append(f'   - [ ] {text.split("? ", 1)[1]} ({code})')
    elif typ == 'likert5':
        md.append(f'{n}. {text} ({code})  1  2  3  4  5')
    elif typ == 'text':
        md.append(f'{n}. {text} ({code})  ________________________________')
    else:
        md.append(f'{n}. {text} ({code})')
        md.append('   ' + '   '.join(f'[ ] {o.split(" ", 1)[1] if o[0].isdigit() else o}' for o in opts.split('. Exported')[0].replace(';', ',').split(', ')))
    md.append('')
(HERE / 'questionnaire.md').write_text('\n'.join(md), encoding='utf-8')
print(len(CODES), 'codes,', len(export_columns()), 'export columns')
