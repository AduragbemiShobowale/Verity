"""Builds the manual-entry baseline pack from replicate 1 of the final simulation (run 5).

  python3 build_baseline_pack.py [--session-date YYYY-MM-DD]

The session date is the day the participants will process the orders. Every message is dated that day and every
requested delivery date is written relative to it, so the pack must be rebuilt with the real session date.

Outputs (in this folder)
  sample_80.csv                  facilitator list: reference, message format, set, source order. No error labels.
  messages/B-001.xlsx ...        the 80 incoming orders, in rotation Excel order sheet, e-mail, WhatsApp message
  messages_all.txt               the e-mail and WhatsApp messages in one file, for printing
  reference/price_list.xlsx      price, limits, stock and product status as the typist would look them up
  reference/customer_register.xlsx  customer details, saved addresses and account status
  reference/orders_already_received.csv  orders logged earlier the same day, for spotting repeats
  entry_template.xlsx            one row per order and participant, the manual condition record
  counterbalancing_schedule.csv  condition order and order set for each participant slot
  facilitator_only/ANSWER_KEY.csv  planted error and correct handling per order. Keep away from participants.
"""
import argparse
import csv
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).parent
ROOT = HERE.parent
SEED = 20261027
ap = argparse.ArgumentParser()
ap.add_argument('--session-date', default='2026-11-02')
S = date.fromisoformat(ap.parse_args().session_date)

rows = json.loads((ROOT / '03_simulation' / 'raw' / 'run5_replicate1.json').read_text())
cat = {r['sku']: r for r in csv.DictReader(open(ROOT / '01_system_facts' / 'catalogue_snapshot.csv'))}
fees = {r['region']: r['delivery_fee_ngn'] for r in csv.DictReader(open(ROOT / '01_system_facts' / 'regions.csv'))}
TARGETED = ['bad_sku', 'missing_address', 'missing_date', 'past_date', 'qty_below_min', 'qty_above_max', 'fractional_qty',
            'over_stock', 'duplicate', 'inactive_product', 'inactive_customer', 'stale_price']
NO_RULE = {'wrong_product': 4, 'qty_typo': 3, 'wrong_address': 3}

# ------------------------------------------------------------------ sample
rng = random.Random(SEED)
pool = {}
for r in rows:
    pool.setdefault(r['planted_error'], []).append(r)
picked = []
# customers whose account is not active appear only in those orders, so the register can show one status per customer
inact = rng.sample(pool['inactive_customer'], 2)
picked += inact
blocked_customers = {r['company'] for r in inact}
ok = lambda r: r['company'] not in blocked_customers and r not in picked
for t in TARGETED:
    if t != 'inactive_customer':
        picked += rng.sample([r for r in pool[t] if ok(r)], 2)
extra_pool = [r for t in TARGETED if t != 'inactive_customer' for r in pool[t] if ok(r)]
picked += rng.sample(extra_pool, 38 - len(picked))
for t, k in NO_RULE.items():
    picked += rng.sample([r for r in pool[t] if ok(r)], k)
picked += rng.sample([r for r in pool['clean'] if ok(r)], 32)
assert len(picked) == 80 and len({r['seq'] for r in picked}) == 80
rng.shuffle(picked)

group = lambda r: 'clean' if r['planted_error'] == 'clean' else ('rule' if r['planted_error'] in TARGETED else 'norule')
# two matched sets of 40, alternating within each group
sets = {}
for g in ('clean', 'rule', 'norule'):
    for k, r in enumerate([x for x in picked if group(x) == g]):
        sets[r['seq']] = 1 + k % 2
FORMATS = ['Excel order sheet', 'E-mail', 'WhatsApp message']

# ------------------------------------------------------------------ customer details used in the messages
def cust_index(email):
    dom = email.split('@')[1].split('.')[0]
    return int(''.join(ch for ch in dom if ch.isdigit()))


CUST = {}
for r in rows:
    c = cust_index(r['email'])
    if r['company'] not in CUST:
        CUST[r['company']] = {'c': c, 'contact': r['contact'], 'email': r['email'], 'region': None}
    if r['region']:
        CUST[r['company']]['region'] = r['region']
for name, d in CUST.items():
    d['addr'] = {'Head office': f"{10 + d['c']} Main Road, {d['region']}", 'Site': f"Plot {100 + d['c']}, {d['region']}"}
    d['phone'] = '080' + str(30000000 + d['c'] * 104729).zfill(8)
    d['status'] = 'Active'
for r in inact:
    CUST[r['company']]['status'] = {'on_hold': 'On hold', 'blocked': 'Blocked'}[r['answer']['customer_status']]


def money(x):
    return f'₦{float(x):,.0f}'


def lines_of(r):
    """Order lines exactly as the customer sent them (the simulation input)."""
    out = []
    for it in r['input']['items']:
        p = cat[it['sku']]
        price = float(p['price_ngn'])
        if r['planted_error'] == 'stale_price' and it['sku'] == r['answer']['sku']:
            # the customer quotes from an out-of-date price list (see ANSWER_KEY note)
            price = float(r['answer']['old_price'])
        out.append({'sku': it['sku'], 'name': p['name'], 'unit': p['unit'], 'qty': it['qty'], 'price': price})
    for u in r['input']['unmatched']:
        out.append({'sku': u['sku'], 'name': 'Galvanised wire mesh', 'unit': 'roll', 'qty': 5, 'price': None})
    return out


def fmt_qty(q):
    q = float(q)
    return str(int(q)) if q == int(q) else str(q)


def when(r):
    off = r['input']['date_offset']
    return None if off is None else S + timedelta(days=int(off))


def addr_of(r):
    lab = r['input']['address_label']
    return None if lab is None else CUST[r['company']]['addr'][lab]


# stale price: the price the customer quotes must differ from the current list. The simulation raised the list price
# from old_price to new_price after the draft was saved; the pack shows the current list (old_price) on the price list
# and the customer quoting a price one step lower, so the typist sees the same kind of mismatch.
for r in picked:
    if r['planted_error'] == 'stale_price':
        r['answer'] = dict(r['answer'], quoted_in_message=round(float(r['answer']['old_price']) / 1.05, -2))

(HERE / 'messages').mkdir(exist_ok=True)
(HERE / 'reference').mkdir(exist_ok=True)
(HERE / 'facilitator_only').mkdir(exist_ok=True)
printable = []
index = []
for k, r in enumerate(picked, 1):
    ref = f'B-{k:03d}'
    fm = FORMATS[(k - 1) % 3]
    cu = CUST[r['company']]
    ls = lines_of(r)
    if r['planted_error'] == 'stale_price':
        for l in ls:
            if l['sku'] == r['answer']['sku']:
                l['price'] = r['answer']['quoted_in_message']
    d, a = when(r), addr_of(r)
    ds = d.strftime('%A %d %B %Y') if d else None
    if fm == 'Excel order sheet':
        wb = Workbook()
        ws = wb.active
        ws.title = 'Order'
        ws['A1'] = f"{r['company']} - Purchase order"
        ws['A1'].font = Font(bold=True, size=13)
        info = [('Our reference', f'PO-{ref[2:]}-{cu["c"]:02d}'), ('Date', S.strftime('%d/%m/%Y')), ('Contact', cu['contact']),
                ('Phone', cu['phone']), ('E-mail', cu['email']), ('Deliver to', a or ''), ('Delivery date', d.strftime('%d/%m/%Y') if d else '')]
        for i, (x, y) in enumerate(info, 3):
            ws.cell(row=i, column=1, value=x).font = Font(bold=True)
            ws.cell(row=i, column=2, value=y)
        hr = 3 + len(info) + 1
        for j, h in enumerate(['Item code', 'Description', 'Unit', 'Quantity', 'Unit price (₦)', 'Amount (₦)'], 1):
            c = ws.cell(row=hr, column=j, value=h)
            c.font, c.fill = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='305496')
        for i, l in enumerate(ls, hr + 1):
            q = float(l['qty'])
            vals = [l['sku'], l['name'], l['unit'], q if q != int(q) else int(q), l['price'], f'=D{i}*E{i}' if l['price'] else None]
            for j, v in enumerate(vals, 1):
                ws.cell(row=i, column=j, value=v)
        for col, w in zip('ABCDEF', [12, 34, 9, 10, 15, 15]):
            ws.column_dimensions[col].width = w
        wb.save(HERE / 'messages' / f'{ref}.xlsx')
        file = f'messages/{ref}.xlsx'
    elif fm == 'E-mail':
        body = [f'From: {cu["contact"]} <{cu["email"]}>', 'To: orders@verity.example', f'Date: {S.strftime("%a, %d %b %Y")} 09:{10 + k % 50:02d}',
                f'Subject: Order from {r["company"]}', '', 'Good morning,', '', 'Please supply the following:', '']
        for l in ls:
            p = f' at {money(l["price"])}' if l['price'] else ''
            body.append(f'  - {fmt_qty(l["qty"])} x {l["name"]} ({l["sku"]}){p}')
        body.append('')
        if a:
            body.append(f'Deliver to: {a}')
        if ds:
            body.append(f'Delivery date: {ds}')
        body += ['', 'Regards,', cu['contact'], r['company'], cu['phone']]
        text = '\n'.join(body)
        (HERE / 'messages' / f'{ref}.txt').write_text(text, encoding='utf-8')
        printable.append(f'==== {ref}  (E-mail) ====\n{text}\n')
        file = f'messages/{ref}.txt'
    else:
        body = [f'[{S.strftime("%d/%m/%Y")}, 08:{10 + k % 50:02d}] {cu["contact"]} ({r["company"]}): Good morning, pls send']
        for l in ls:
            short = l['name'].split(',')[0].lower()
            p = f' @{float(l["price"]):,.0f}' if l['price'] else ''
            body.append(f'{short} {l["sku"]} x{fmt_qty(l["qty"])}{p}')
        if a:
            body.append(f'to {a}')
        if ds:
            body.append(f'for {d.strftime("%a %d/%m")}')
        body.append('thanks')
        text = '\n'.join(body)
        (HERE / 'messages' / f'{ref}.txt').write_text(text, encoding='utf-8')
        printable.append(f'==== {ref}  (WhatsApp) ====\n{text}\n')
        file = f'messages/{ref}.txt'
    r['_ref'], r['_format'], r['_file'] = ref, fm, file
    index.append([ref, fm, f'Set {sets[r["seq"]]}', file, r['order_no'], r['seq']])

(HERE / 'messages_all.txt').write_text('\n'.join(printable), encoding='utf-8')
with open(HERE / 'sample_80.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['reference', 'message_format', 'order_set', 'message_file', 'source_order_no_run5', 'source_seq_run5'])
    w.writerows(index)

# ------------------------------------------------------------------ answer key
CORRECT = {
    'clean': 'Enter as sent. No problem to flag.',
    'bad_sku': 'Flag: the item code is not in the price list. Do not enter the line until the customer confirms.',
    'missing_address': 'Flag: no delivery address. Ask the customer.',
    'missing_date': 'Flag: no delivery date. Ask the customer.',
    'past_date': 'Flag: the delivery date is before the order date.',
    'qty_below_min': 'Flag: quantity is below the minimum order quantity on the price list.',
    'qty_above_max': 'Flag: quantity is above the maximum order quantity on the price list.',
    'fractional_qty': 'Flag: quantity is not a whole number.',
    'over_stock': 'Flag: quantity is more than the stock on hand.',
    'duplicate': 'Flag: same items as an order already received today. Confirm with the customer before entering.',
    'inactive_product': 'Flag: the product is discontinued.',
    'inactive_customer': 'Flag: the customer account is not active, do not accept the order.',
    'stale_price': 'Flag: the quoted unit price differs from the current price list.',
    'wrong_product': 'No visible cue. The customer named a valid neighbouring product. Counts as an error that reached the record if entered as sent.',
    'qty_typo': 'No visible cue except an unusually large quantity. Counts as an error that reached the record if entered as sent.',
    'wrong_address': 'No visible cue. The customer named a valid saved address that was not the intended one.',
}
with open(HERE / 'facilitator_only' / 'ANSWER_KEY.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['reference', 'source_order_no_run5', 'planted_error', 'has_rule', 'expected_rule', 'correct_handling',
                'customer', 'address_as_sent', 'delivery_date_as_sent', 'lines_as_sent', 'intended_values', 'verity_condition_note'])
    for r in picked:
        note = ''
        if r['planted_error'] == 'stale_price':
            note = ('The portal takes prices from the catalogue, so the quoted price is not an input in the Verity condition '
                    '(functional test 16b). Record whether the Ops Desk approver notices the mismatch.')
        if r['planted_error'] == 'inactive_customer':
            note = 'Needs the dummy account for this customer set to the register status before the session (setup SQL).'
        if r['planted_error'] == 'bad_sku':
            note = 'Rendering assumption: the simulated unknown line had no quantity or description; the pack shows "Galvanised wire mesh", 5 rolls.'
        if r['planted_error'] == 'over_stock':
            note = 'Stock levels in the pack are the catalogue snapshot; set live stock to the same levels before the Verity condition.'
        lines = '; '.join(f"{l['sku']} x {fmt_qty(l['qty'])}" for l in lines_of(r))
        w.writerow([r['_ref'], r['order_no'], r['planted_error'], 'Yes' if r['planted_error'] in TARGETED else ('No' if r['planted_error'] != 'clean' else ''),
                    r['expected_rule'] or '', CORRECT[r['planted_error']], r['company'], addr_of(r) or '', when(r).isoformat() if when(r) else '',
                    lines, json.dumps(r['answer']), note])

# ------------------------------------------------------------------ reference pack
wb = Workbook()
ws = wb.active
ws.title = 'Price list'
hdr = ['Item code', 'Description', 'Unit', 'Unit price (₦)', 'Minimum order', 'Maximum order', 'In stock', 'Status']
for j, h in enumerate(hdr, 1):
    ws.cell(row=1, column=j, value=h).font = Font(bold=True)
for i, p in enumerate(sorted(cat.values(), key=lambda x: x['sku']), 2):
    status = 'Discontinued' if p['sku'] == 'SAND-T' else 'Available'
    for j, v in enumerate([p['sku'], p['name'], p['unit'], float(p['price_ngn']), int(p['min_qty']), int(p['max_qty']), int(p['on_hand']), status], 1):
        ws.cell(row=i, column=j, value=v)
ws.cell(row=len(cat) + 3, column=1, value=f'Prices valid from {S.strftime("%d %B %Y")}. Delivery fee by region on the next sheet. VAT 7.5% on goods and delivery.')
ws2 = wb.create_sheet('Delivery fees')
ws2.append(['Region', 'Delivery fee (₦)'])
for k, v in fees.items():
    ws2.append([k, float(v)])
for col, wdt in zip('ABCDEFGH', [11, 34, 9, 14, 13, 13, 9, 13]):
    ws.column_dimensions[col].width = wdt
wb.save(HERE / 'reference' / 'price_list.xlsx')

wb = Workbook()
ws = wb.active
ws.title = 'Customers'
ws.append(['Company', 'Contact', 'E-mail', 'Phone', 'Saved address 1 (Head office)', 'Saved address 2 (Site)', 'Region', 'Account status'])
for name in sorted(CUST):
    d = CUST[name]
    ws.append([name, d['contact'], d['email'], d['phone'], d['addr']['Head office'], d['addr']['Site'], d['region'], d['status']])
for col, wdt in zip('ABCDEFGH', [32, 22, 38, 14, 30, 22, 15, 14]):
    ws.column_dimensions[col].width = wdt
wb.save(HERE / 'reference' / 'customer_register.xlsx')

by_no = {r['order_no']: r for r in rows}
log = []
seen = set()
for r in picked:
    if r['planted_error'] != 'duplicate':
        continue
    src = r['answer']['duplicate_of']
    if src in seen:
        continue
    seen.add(src)
    if src in by_no:
        lines = '; '.join(f"{i['sku']} x {fmt_qty(i['qty'])}" for i in by_no[src]['input']['items'])
    else:
        lines = 'CEM-50 x 24; ROD-12 x 14'
    log.append([r['company'], lines])
# unrelated earlier entries, mixed in so the log does not point only at the repeats
for r in rng.sample([x for x in rows if x['planted_error'] == 'clean' and x not in picked and x['company'] not in blocked_customers], 6):
    log.append([r['company'], '; '.join(f"{i['sku']} x {fmt_qty(i['qty'])}" for i in r['input']['items'])])
rng.shuffle(log)
with open(HERE / 'reference' / 'orders_already_received.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['logged_at', 'customer', 'lines', 'note'])
    for k, (co, lines) in enumerate(log):
        w.writerow([f'{S.isoformat()} 07:{10 + k * 6:02d}', co, lines, 'Entered and sent for approval'])

# ------------------------------------------------------------------ entry template
wb = Workbook()
ws = wb.active
ws.title = 'Entries'
cols = ['Participant ID', 'Condition', 'Order reference', 'Customer', 'Delivery address', 'Delivery date (DD/MM/YYYY)']
for k in range(1, 5):
    cols += [f'Line {k} item code', f'Line {k} quantity']
cols += ['Problem flagged (Yes/No)', 'Problem description', 'Start time (HH:MM:SS)', 'End time (HH:MM:SS)', 'Seconds']
for j, h in enumerate(cols, 1):
    c = ws.cell(row=1, column=j, value=h)
    c.font, c.fill, c.alignment = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='0F3D3E'), Alignment(wrap_text=True)
yn = DataValidation(type='list', formula1='"Yes,No"', allow_blank=True)
cond = DataValidation(type='list', formula1='"Manual,Verity"', allow_blank=True)
ws.add_data_validation(yn)
ws.add_data_validation(cond)
for i in range(2, 2 + 80 * 2 * 20):
    if i <= 2 + 400:
        ws.cell(row=i, column=19, value=f'=IF(OR(Q{i}="",R{i}=""),"",ROUND((R{i}-Q{i})*86400,0))')
yn.add('O2:O2000')
cond.add('B2:B2000')
for col in range(1, len(cols) + 1):
    ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 14
ws.freeze_panes = 'D2'
wn = wb.create_sheet('How to fill in')
for t in ['One row per order processed. Manual condition only: Verity times come from the database (extract_baseline.sql).',
          'Type the time you open the message in Start time and the time you finish the row in End time, as HH:MM:SS. Seconds fills itself.',
          'Problem flagged = Yes if you noticed anything wrong with the order. Describe it in Problem description. Enter the order as you would send it on.',
          'Leave a line blank if the order has fewer lines. Do not correct a value you think is wrong, flag it instead.']:
    wn.append([t])
wn.column_dimensions['A'].width = 130
wb.save(HERE / 'entry_template.xlsx')

# ------------------------------------------------------------------ counterbalancing
with open(HERE / 'counterbalancing_schedule.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['participant_slot', 'first_condition', 'first_set', 'second_condition', 'second_set'])
    seqs = [('Manual', 1, 'Verity', 2), ('Verity', 2, 'Manual', 1), ('Manual', 2, 'Verity', 1), ('Verity', 1, 'Manual', 2)]
    for p in range(1, 13):
        w.writerow([f'P{p:02d}', *seqs[(p - 1) % 4]])

print('sample', Counter(r['planted_error'] for r in picked))
print('groups', Counter(group(r) for r in picked), 'sets', Counter((sets[r['seq']], group(r)) for r in picked))
print('formats', Counter(r['_format'] for r in picked), 'inactive customers', blocked_customers)
