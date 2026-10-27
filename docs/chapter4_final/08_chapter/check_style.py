"""Checks Chapter_Four.docx against the writing rules. Running text = body paragraphs that are not headings,
captions, Source lines, table cells or references. Prints each finding; exit code 1 if any hard rule is broken."""
import re
import sys
from pathlib import Path
from docx import Document

doc = Document(Path(__file__).parent / 'Chapter_Four.docx')
paras = doc.paragraphs
in_refs = False
body = []
for p in paras:
    t = p.text.strip()
    if not t:
        continue
    if p.style.name.startswith('Heading'):
        in_refs = t == 'References'
        continue
    if in_refs or re.match(r'^(Table|Figure) 4\.\d+: ', t) or t.startswith('Source: '):
        continue
    body.append(t)

CITE = re.compile(r'\((?:[A-Z][A-Za-z&.,\s]+ \d{4}[a-z]?(?:; )?)+\)| \(\d{4}(?:, \d{4})?\)')
hard, soft = [], []
for t in body:
    s = CITE.sub('', t)
    for ch, name in ((':', 'colon'), (';', 'semicolon'), ('–', 'en dash'), ('—', 'em dash'), ('(', 'bracket'), (')', 'bracket'),
                     ('[', 'square bracket'), ('%', 'percent sign')):
        if ch in s.replace('[DATA PENDING]', '').replace('[EXACT CHAPTER ONE WORDING NEEDED]', ''):
            hard.append((name, t[:140]))
    if re.search(r'\s-\s', s):
        hard.append(('spaced hyphen used as dash', t[:140]))
    if re.search(r'\bemail\b|\bE-Mail\b', s, re.I) and 'e-mail' not in s:
        hard.append(('e-mail spelling', t[:140]))
    if re.search(r'\bper ?cent\b', s) and 'percent' not in s:
        hard.append(('percent spelling', t[:140]))
    if re.search(r'chapter four', s) and 'Chapter Four' not in s:
        hard.append(('Chapter Four capitalisation', t[:140]))
    for sent in re.split(r'(?<=\.)\s+', s):
        # A, B and C   or   A, B, and C, with short items: likely a list of three
        for mm in re.finditer(r'(?:^|[,.]\s|\b(?:of|by|with|for|in|on|as|the|a|an|to)\s)([^,.]{1,60}), ([^,.]{1,60}),? (and|or) ([^,.]{1,60})', sent):
            pre = sent[:mm.start(1)]
            if re.search(r'([^,.]{1,60}), $', pre):
                continue  # four or more items
            soft.append(('possible list of three', sent[:200]))
            break
# Every table and figure referred to in the text
txt = ' '.join(body)
caps = [p.text.split(':')[0] for p in paras if re.match(r'^(Table|Figure) 4\.\d+: ', p.text)]
for c in caps:
    kind, n = c.split(' ')
    a, b = n.split('.')
    refs = re.findall(rf'{kind}s? 4\.(\d+)(?: to 4\.(\d+))?', txt)
    ok = any(int(x) == int(b) or (y and int(x) <= int(b) <= int(y)) for x, y in refs)
    if not ok:
        hard.append(('not referred to in text', c))
lim = [t for t in body if re.search(r'\blimitation', t, re.I)]
for name, t in hard:
    print('HARD', name, '|', t)
for name, t in soft:
    print('CHECK', name, '|', t)
print(f'{len(body)} running paragraphs, {len(caps)} captions, {len(hard)} hard findings, {len(soft)} to check by eye')
sys.exit(1 if hard else 0)
