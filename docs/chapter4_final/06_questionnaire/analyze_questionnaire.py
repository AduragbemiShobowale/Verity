"""Questionnaire codebook and analysis for Chapter Four Part A. Standard library only.

  python3 analyze_questionnaire.py responses.csv     analyse a real export (columns as in export_column_template.csv)
  python3 build_questionnaire.py                     writes the questionnaire, codebook and column template from CODES

CODES below is the single source of item codes, wording and response coding. The analysis refuses to run until a
responses file with real rows exists, and it never generates or imputes responses.

Valid response: consent = 1, respondent group given, and all ten SUS items answered.
Target: 150 valid responses from about 190 distributed.
SUS scoring (Brooke, 1996): odd items score - 1, even items 5 - score, sum x 2.5, range 0 to 100.
SUS interpretation: one-sample t test of the mean against 68 (Sauro and Lewis, 2016), the adjective scale of
Bangor, Kortum and Miller (2009), the acceptability ranges of Bangor, Kortum and Miller (2008), and the curved
grading scale of Sauro and Lewis (2016).
Reliability: Cronbach's alpha (Cronbach, 1951), SUS after recoding even items.
"""
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).parent
AGREE5 = '1 Strongly disagree, 2 Disagree, 3 Neither agree nor disagree, 4 Agree, 5 Strongly agree'
IMPORT5 = '1 Not important, 2 Slightly important, 3 Moderately important, 4 Very important, 5 Extremely important'
ERROR_TYPES = [  # worded to match the 15 planted error types of the simulation, in the same order
    ('ERR_SKU', 'An item code that does not exist in the catalogue'),
    ('ERR_DISC', 'A product that is no longer sold'),
    ('ERR_NOADDR', 'No delivery address given'),
    ('ERR_NODATE', 'No delivery date given'),
    ('ERR_PASTDATE', 'A delivery date that has already passed'),
    ('ERR_QMIN', 'A quantity below the minimum order quantity'),
    ('ERR_QMAX', 'A quantity above the maximum order quantity'),
    ('ERR_QFRAC', 'A quantity that is not a whole number'),
    ('ERR_QSTOCK', 'A quantity larger than the stock available'),
    ('ERR_DUP', 'The same order sent twice'),
    ('ERR_ACCT', 'An order from a customer whose account is on hold or blocked'),
    ('ERR_PRICE', 'A price on the order that differs from the current price'),
    ('ERR_WRONGPROD', 'A wrong but similar product, for example 12 mm rods instead of 16 mm'),
    ('ERR_QSLIP', 'A quantity typing slip, for example an extra zero'),
    ('ERR_WRONGADDR', 'The wrong one of the customer\'s delivery addresses'),
]
SUS = [  # standard wording (Brooke, 1996)
    'I think that I would like to use this system frequently.',
    'I found the system unnecessarily complex.',
    'I thought the system was easy to use.',
    'I think that I would need the support of a technical person to be able to use this system.',
    'I found the various functions in this system were well integrated.',
    'I thought there was too much inconsistency in this system.',
    'I would imagine that most people would learn to use this system very quickly.',
    'I found the system very cumbersome to use.',
    'I felt very confident using the system.',
    'I needed to learn a lot of things before I could get going with this system.',
]
CODES = [
    # code, part, section, wording, response type, options / coding
    ('respondent_id', 'Admin', 'Admin', 'Respondent number assigned at collection', 'text', 'R001 onwards'),
    ('submitted_at', 'Admin', 'Admin', 'Date and time the form was submitted', 'datetime', 'ISO 8601'),
    ('consent', 'I', 'Consent', 'I have read the information sheet and agree to take part.', 'single', '1 Yes, 0 No'),
    ('group', 'I', 'Respondent group', 'Which best describes you?', 'single', '1 Staff of the supplier, 2 Customer who places orders'),
    ('P_ROLE', 'I', 'Profile', 'What is your main role?', 'single',
     '1 Order desk or sales, 2 Warehouse, 3 Dispatch or delivery, 4 Finance, 5 Management, 6 Procurement or buying, 7 Site or project manager, 8 Business owner, 9 Other'),
    ('P_YEARS', 'I', 'Profile', 'How long have you worked with building-material orders?', 'single',
     '1 Less than 1 year, 2 1 to 3 years, 3 4 to 6 years, 4 7 to 10 years, 5 More than 10 years'),
    ('P_VOLUME', 'I', 'Profile', 'About how many orders do you place or handle in a typical week?', 'single',
     '1 Fewer than 10, 2 10 to 29, 3 30 to 59, 4 60 or more'),
    ('P_DEVICE', 'I', 'Profile', 'Which device do you mostly use for work messages?', 'single', '1 Smartphone, 2 Laptop or desktop, 3 Tablet, 4 Basic phone'),
    ('H_CHANNELS', 'I', 'Current order handling', 'How are orders sent or received today? Tick all that apply.', 'multi',
     'WhatsApp; E-mail; Phone call; Excel sheet; In person; Other. Exported as H_CHANNELS_WA, _EM, _PH, _XL, _IP, _OT, each 1 ticked 0 not'),
    ('H_MAIN', 'I', 'Current order handling', 'Which one is used most?', 'single', '1 WhatsApp, 2 E-mail, 3 Phone call, 4 Excel sheet, 5 In person, 6 Other'),
    ('H_RECORD', 'I', 'Current order handling', 'Where is the order recorded once received?', 'single',
     '1 Paper book, 2 Excel or another spreadsheet, 3 Accounting software, 4 It is not recorded, 5 Other'),
    ('H_MINUTES', 'I', 'Current order handling', 'About how long does it take to process one order from receipt to approval?', 'single',
     '1 Under 5 minutes, 2 5 to 10 minutes, 3 11 to 20 minutes, 4 21 to 30 minutes, 5 Over 30 minutes'),
    ('E_FREQ', 'I', 'Errors', 'How often does an order contain a mistake?', 'single', '1 Never, 2 Rarely, 3 Sometimes, 4 Often, 5 Very often'),
] + [(c, 'I', 'Errors', f'Which of these mistakes have you seen in the last three months? {t}', 'multi-item', '1 Seen, 0 Not seen')
     for c, t in ERROR_TYPES] + [
    ('E_OTHER', 'I', 'Errors', 'Any other kind of mistake? Please describe.', 'text', 'free text'),
    ('C_CONSEQ', 'I', 'Consequences', 'What has happened as a result of an order mistake? Tick all that apply.', 'multi',
     'Wrong goods delivered; Late delivery; Refund or credit note; Extra calls or messages; Customer lost; Stock records wrong; None. '
     'Exported as C_CONSEQ_WRONG, _LATE, _REFUND, _CALLS, _LOST, _STOCK, _NONE'),
    ('C_REWORK', 'I', 'Consequences', 'About how long does it take to sort out one mistaken order?', 'single',
     '1 Under 10 minutes, 2 10 to 30 minutes, 3 31 to 60 minutes, 4 1 to 4 hours, 5 More than 4 hours'),
] + [(f'IMP{i}', 'I', 'Requirement importance', f'How important is it that the system checks or provides: {t}?', 'likert5', IMPORT5)
     for i, t in enumerate(['the item code (SKU) is valid', 'the quantity is allowed', 'the customer details are correct',
                            'the price is current', 'the order is not a duplicate', 'the stock is available',
                            'every mandatory field is filled', 'the delivery date and address are valid',
                            'a warning when a quantity is unusual for the customer', 'real-time order status',
                            'verification of payment proof', 'a delivery code to confirm handover'], 1)] + \
    [(f'SUS{i}', 'II', 'System Usability Scale', t, 'likert5', AGREE5) for i, t in enumerate(SUS, 1)] + [
    ('PU1', 'II', 'Perceived usefulness', 'Using Verity would reduce the number of orders that have to be corrected.', 'likert5', AGREE5),
    ('PU2', 'II', 'Perceived usefulness', 'Using Verity would reduce the time spent re-entering or re-checking orders.', 'likert5', AGREE5),
    ('PU3', 'II', 'Perceived usefulness', 'Using Verity would reduce the number of wrong orders that reach delivery.', 'likert5', AGREE5),
    ('EOU1', 'II', 'Ease of use', 'Placing an order in the Verity portal is as easy as sending the order in a message.', 'likert5', AGREE5),
    ('EOU2', 'II', 'Ease of use', 'Learning to place orders in Verity would be easy compared with sending a message.', 'likert5', AGREE5),
    ('EOU3', 'II', 'Ease of use', 'Correcting an order that Verity flags is easier than sorting it out by phone or message.', 'likert5', AGREE5),
    ('BI1', 'II', 'Intention', 'If Verity were available, I intend to use it to place or process orders.', 'likert5', AGREE5),
    ('FC1', 'II', 'Facilitating conditions', 'I have a phone or computer I could use to access Verity.', 'likert5', AGREE5),
    ('FC2', 'II', 'Facilitating conditions', 'I have enough mobile data or internet access to use Verity when I need to.', 'likert5', AGREE5),
    ('VOL1', 'II', 'Voluntariness', 'Using Verity would be my own choice rather than something I am required to do.', 'likert5', AGREE5),
    ('COMMENT', 'II', 'Comments', 'Is there anything else you would like to say about Verity?', 'text', 'free text'),
]
MULTI_COLUMNS = {'H_CHANNELS': ['WA', 'EM', 'PH', 'XL', 'IP', 'OT'], 'C_CONSEQ': ['WRONG', 'LATE', 'REFUND', 'CALLS', 'LOST', 'STOCK', 'NONE']}


def export_columns():
    cols = []
    for c, *_ in CODES:
        cols += [f'{c}_{s}' for s in MULTI_COLUMNS[c]] if c in MULTI_COLUMNS else [c]
    return cols


# ------------------------------------------------------------------ statistics
Z = 1.959964


def wilson(k, n):
    if not n:
        return None
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def betacf(a, b, x):
    """Continued fraction for the incomplete beta function (modified Lentz method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1) < 1e-14:
            break
    return h


def betai(a, b, x):
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * betacf(a, b, x) / a
    return 1 - bt * betacf(b, a, 1 - x) / b


def t_sf2(t, df):
    """Two-sided p value of Student's t."""
    return betai(df / 2, 0.5, df / (df + t * t))


def t_crit(df):
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_sf2(mid, df) > 0.05:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def alpha(items):
    k = len(items)
    tot = [sum(v) for v in zip(*items)]
    return round(k / (k - 1) * (1 - sum(st.variance(i) for i in items) / st.variance(tot)), 3)


def describe(xs):
    n = len(xs)
    m, sd = st.mean(xs), st.stdev(xs)
    tc = t_crit(n - 1)
    return {'n': n, 'mean': round(m, 2), 'sd_sample': round(sd, 2), 'median': round(st.median(xs), 2),
            'ci95': [round(m - tc * sd / math.sqrt(n), 2), round(m + tc * sd / math.sqrt(n), 2)]}


def adjective(x):  # Bangor, Kortum and Miller (2009), adjective means
    for cut, name in ((90.9, 'Best imaginable'), (85.5, 'Excellent'), (71.4, 'Good'), (50.9, 'OK'), (35.7, 'Poor'), (20.3, 'Awful')):
        if x >= cut:
            return name
    return 'Worst imaginable'


def grade(x):  # Sauro and Lewis (2016) curved grading scale
    for cut, g in ((84.1, 'A+'), (80.8, 'A'), (78.9, 'A-'), (77.2, 'B+'), (74.1, 'B'), (72.6, 'B-'), (71.1, 'C+'), (65.0, 'C'), (62.7, 'C-'), (51.7, 'D')):
        if x >= cut:
            return g
    return 'F'


def acceptability(x):  # Bangor, Kortum and Miller (2008)
    return 'Acceptable' if x > 70 else ('Marginal' if x >= 50 else 'Not acceptable')


def analyse(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    num = lambda r, c: float(r[c]) if (r.get(c) or '').strip() not in ('', 'NA') else None
    valid = [r for r in rows if (r.get('consent') or '').strip() == '1' and (r.get('group') or '').strip() in ('1', '2')
             and all(num(r, f'SUS{i}') is not None for i in range(1, 11))]
    if not valid:
        sys.exit('No valid responses in the file. Nothing written.')
    out = {'distributed_target': 190, 'valid_target': 150, 'returned': len(rows), 'valid': len(valid),
           'by_group': {'staff': sum(r['group'] == '1' for r in valid), 'customer': sum(r['group'] == '2' for r in valid)}}

    def sus(r):
        s = sum((num(r, f'SUS{i}') - 1) if i % 2 else (5 - num(r, f'SUS{i}')) for i in range(1, 11))
        return s * 2.5
    out['reliability'] = {
        'SUS': alpha([[(num(r, f'SUS{i}') - 1) if i % 2 else (5 - num(r, f'SUS{i}')) for r in valid] for i in range(1, 11)]),
    }
    for scale, items in (('PU', ['PU1', 'PU2', 'PU3']), ('EOU', ['EOU1', 'EOU2', 'EOU3']), ('FC', ['FC1', 'FC2'])):
        rs = [r for r in valid if all(num(r, c) is not None for c in items)]
        if len(rs) > 2:
            out['reliability'][scale] = alpha([[num(r, c) for r in rs] for c in items])
    for label, rs in (('all', valid), ('staff', [r for r in valid if r['group'] == '1']), ('customer', [r for r in valid if r['group'] == '2'])):
        if len(rs) < 2:
            continue
        s = [sus(r) for r in rs]
        d = describe(s)
        t = (d['mean'] - 68) / (d['sd_sample'] / math.sqrt(d['n'])) if d['sd_sample'] else None
        d.update({'t_vs_68': round(t, 3) if t is not None else None, 'df': d['n'] - 1,
                  'p_two_sided': round(t_sf2(abs(t), d['n'] - 1), 4) if t is not None else None,
                  'adjective_bangor_2009': adjective(d['mean']), 'grade_sauro_lewis_2016': grade(d['mean']),
                  'acceptability_bangor_2008': acceptability(d['mean'])})
        out.setdefault('sus', {})[label] = d
        for c in ['PU1', 'PU2', 'PU3', 'EOU1', 'EOU2', 'EOU3', 'BI1', 'FC1', 'FC2', 'VOL1'] + [f'IMP{i}' for i in range(1, 13)]:
            xs = [num(r, c) for r in rs if num(r, c) is not None]
            if len(xs) > 1:
                agree = sum(x >= 4 for x in xs)
                out.setdefault('items', {}).setdefault(label, {})[c] = {**describe(xs), 'agree_4_or_5': agree,
                                                                        'agree_pct': round(100 * agree / len(xs), 1), 'agree_ci95': wilson(agree, len(xs))}
        for c, _ in ERROR_TYPES:
            xs = [num(r, c) for r in rs if num(r, c) is not None]
            if xs:
                k = int(sum(xs))
                out.setdefault('errors_seen', {}).setdefault(label, {})[c] = {'seen': k, 'n': len(xs), 'pct': round(100 * k / len(xs), 1), 'ci95': wilson(k, len(xs))}
    (HERE / 'questionnaire_results.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:4000])


if __name__ == '__main__':
    if len(sys.argv) != 2 or not Path(sys.argv[1]).exists():
        sys.exit('No questionnaire data yet: pass the exported responses CSV. Nothing written.')
    analyse(sys.argv[1])
