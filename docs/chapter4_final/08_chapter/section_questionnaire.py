# Section 4.2, questionnaire results. Executed by build_chapter.py with its helpers in scope.
import sys as _sys
_sys.path.insert(0, str(ROOT / '06_questionnaire'))
from analyze_questionnaire import t_sf2 as _t_sf2  # noqa: E402

Q = json.loads((ROOT / '06_questionnaire' / 'questionnaire_results.json').read_text())
QF = ROOT / '06_questionnaire' / 'figures'
QSRC = 'questionnaire dataset supplied by the client team, collected 17 to 26 October 2026, analysed with 06_questionnaire/analyze_dataset.py.'
QG = Q['by_group']
CAT = Q['categorical']
IT = Q['items']
SU = Q['sus']


def _pct(k, n):
    return f'{100 * k / n:.1f}'


def _r_p(r, n=200):
    t = r * math.sqrt(n - 2) / math.sqrt(1 - r * r)
    return _t_sf2(abs(t), n - 2)


H2('4.2 Questionnaire results')
H3('4.2.1 Responses and respondents')
P(f'The questionnaire was administered by the client team between 17 and 26 October 2026 to staff of logistics and distribution '
  f'businesses and to business customers who place orders with them. Respondents answered Part I before watching the same '
  f'demonstration of Verity lasting six to eight minutes, and Part II after it. Table 4.1 summarises the responses. Every one of the '
  f'{Q["rows"]} respondents gave consent and confirmed having watched the demonstration. Every respondent also answered all ten '
  f'usability items, so all {Q["valid"]} responses are valid. This reaches the upper end of the range of 100 to 200 respondents set in Section 1.5. The optional name and e-mail fields '
  f'were removed before the analysis, so no result can be linked to a person.')
trace(Q['valid'], 'valid questionnaire responses', '06_questionnaire/questionnaire_results.json valid')
table('Questionnaire responses and validity', ['Measure', 'Staff', 'Customers', 'All'],
      [['Responses received', QG['Staff'], QG['Customer'], Q['rows']], ['Consent given', QG['Staff'], QG['Customer'], Q['valid']],
       ['Demonstration watched', QG['Staff'], QG['Customer'], Q['valid']], ['All ten usability items answered', QG['Staff'], QG['Customer'], Q['valid']],
       ['Valid responses', QG['Staff'], QG['Customer'], Q['valid']], ['Share of valid responses', _pct(QG['Staff'], Q['valid']) + ' percent',
        _pct(QG['Customer'], Q['valid']) + ' percent', '100 percent']], QSRC)

prof_rows = []
for h, lab in (('A1. Main role', 'Main role'), ('A2. Years in this kind of work', 'Years in this kind of work'), ('A3. Type of business', 'Type of business'),
               ('A4. Number of staff in the business', 'Staff in the business'), ('A5. Orders handled/placed on a typical day', 'Orders on a typical day'),
               ('A6. Main operating location', 'Main operating location')):
    for k, v in CAT[h]['All'].items():
        prof_rows.append([lab, k, CAT[h]['Staff'].get(k, 0), CAT[h]['Customer'].get(k, 0), f'{v} ({_pct(v, Q["valid"])})'])
loc = CAT['A6. Main operating location']['All']
P(f'Table 4.2 profiles the respondents. They came from businesses of every size in the questionnaire, from fewer than ten staff to '
  f'250 or more, and from several types of business. The largest single role was Other with {CAT["A1. Main role"]["All"]["Other"]} '
  f'respondents, which limits what can be said about particular job roles. Of all respondents, {loc["Outside Nigeria"]}, or '
  f'{_pct(loc["Outside Nigeria"], Q["valid"])} percent, said that their business operates mainly outside Nigeria. The questionnaire did '
  f'not screen them out, so they are kept in the analysis.')
table('Profile of the respondents', ['Question', 'Answer', 'Staff', 'Customers', 'All, n (%)'], prof_rows, QSRC, widths=[3.6, 5.6, 1.7, 2, 3.1], size=8)

H3('4.2.2 How orders are handled now')
b1, b3, b4, b5, b6, b7 = (CAT[h]['All'] for h in ('B1. Channels used (select all)', 'B3. How order enters records', 'B4. Checks before processing (select all)',
                                                  'B5. Can customers see stock before ordering?', 'B6. Record of who changed/approved order', 'B7. When stock shortages found'))
mc = Q['main_channel_consistency']
rekey = b3['Retyped by hand'] + b3['Copied and pasted']
late = b7['At picking'] + b7['At dispatch'] + b7['After delivery']
hand_rows = [['Channels used, select all', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b1.items()]
hand_rows += [['Main channel, consistent answers only', k, f'{v} ({_pct(v, mc["raw_main_channel_among_channels_used"])})'] for k, v in CAT['B2. Main channel (validated)']['All'].items() if k != 'blank']
hand_rows += [['How the order enters the records', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b3.items()]
hand_rows += [['Checks before processing, select all', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b4.items()]
hand_rows += [['Customers can see stock before ordering', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b5.items()]
hand_rows += [['Record of who changed or approved an order', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b6.items()]
hand_rows += [['When stock shortages are found', k, f'{v} ({_pct(v, Q["valid"])})'] for k, v in b7.items()]
P(f'Table 4.3 describes how orders are handled now. Phone calls were the channel used most widely, by {b1["Phone call"]} respondents, '
  f'and an online portal was already used by {b1["Online portal"]}. Orders were retyped by hand or copied and pasted into the records '
  f'by {rekey} respondents, {_pct(rekey, Q["valid"])} percent. The usual check was a reread by the person who typed the order, reported '
  f'by {b4["The person who typed it rereads it"]} respondents, while {b4["The system checks it automatically"]} reported an automatic '
  f'check. Only {b6["A complete record"]} respondents had a complete record of who changed or approved an order, and {late}, '
  f'{_pct(late, Q["valid"])} percent, said that stock shortages were usually found only after the order had been confirmed.')
P(f'The question on the main channel needs care. Only {mc["raw_main_channel_among_channels_used"]} of the {mc["n"]} respondents named '
  f'as their main channel one that they had also ticked among the channels they use. The table therefore reports the main channel '
  f'for those {mc["raw_main_channel_among_channels_used"]} consistent answers only.')
trace(rekey, 'respondents whose orders are retyped or copied', 'questionnaire_results.json categorical B3, Retyped by hand plus Copied and pasted')
trace(mc['raw_main_channel_among_channels_used'], 'consistent main-channel answers', 'questionnaire_results.json main_channel_consistency')
table('Current order handling', ['Question', 'Answer', 'Respondents, n (%)'], hand_rows, QSRC, widths=[6, 6.4, 3.6], size=8)

H3('4.2.3 Effects of order errors')
P('The answers to section C, on how often errors occur, how many orders they affect, which types respondents had met, where they '
  'are found and how long they take to correct, were supplied as numeric codes. The codes cannot be matched to the options of the '
  'questionnaire with certainty, and the select-all question on error types holds a single number for each respondent, so section C '
  'is not reported. Table 4.4 gives the answers to section D on the effects of errors.')
d_rows = [[k, IT[k]['wording'], IT[k]['All']['mean'], IT[k]['All']['sd_sample'], pc(IT[k]['All']['agree_pct']),
           f"{IT[k]['All']['agree_ci95'][0]:.1f} to {IT[k]['All']['agree_ci95'][1]:.1f}"] for k in [f'D{i}' for i in range(1, 7)]]
dmin = min(IT[f'D{i}']['All']['agree_pct'] for i in range(1, 7))
dmax = max(IT[f'D{i}']['All']['agree_pct'] for i in range(1, 7))
P(f'Between {pc(dmin)} and {pc(dmax)} percent of respondents agreed that order errors in their business cause each of the six effects, '
  f'and every mean lay close to the midpoint of the scale. No effect was agreed by a majority. The respondents therefore did not report '
  f'a clear view that order errors are a serious problem in their business.')
table('Effects of order errors, all respondents', ['Item', 'Order errors in my business...', 'Mean', 'SD', 'Agree %', '95% CI'], d_rows,
      QSRC + ' Agree means 4 or 5 on the five-point scale.', widths=[1.2, 6.6, 1.5, 1.5, 1.8, 3.4], size=8.5)

H3('4.2.4 Importance of the checks')
RULE_FOR = {'E1': 'SKU', 'E2': 'Quantity limits', 'E3': 'Customer status', 'E4': 'Pricing', 'E5': 'Duplicate order', 'E6': 'Stock availability',
            'E7': 'Mandatory fields', 'E8': 'Delivery date and address', 'E9': 'Unusual quantity', 'E10': 'Status timeline',
            'E11': 'Payment verification by Finance', 'E12': 'Delivery code'}
e_rows = [[k, IT[k]['wording'], RULE_FOR[k], IT[k]['All']['mean'], pc(IT[k]['All']['agree_pct']),
           f"{IT[k]['All']['agree_ci95'][0]:.1f} to {IT[k]['All']['agree_ci95'][1]:.1f}"] for k in [f'E{i}' for i in range(1, 13)]]
emin = min(IT[f'E{i}']['All']['agree_pct'] for i in range(1, 13))
emax = max(IT[f'E{i}']['All']['agree_pct'] for i in range(1, 13))
P(f'Section E asked how important each check of an order system is. Table 4.5 sets each check beside the part of Verity that '
  f'provides it, and Figure 4.1 shows the share rating each check as important. Between {pc(emin)} and {pc(emax)} percent rated each '
  f'check 4 or 5, and no check reached half. Respondents did not single out any check as more important than the others, so the '
  f'ratings neither support nor contradict the set of checks built into Verity.')
table('Importance of the checks and the part of Verity that provides each', ['Item', 'Check', 'Provided in Verity by', 'Mean', 'Important %', '95% CI'],
      e_rows, QSRC + ' Important means 4 or 5 on the five-point scale.', widths=[1.1, 6, 3.4, 1.3, 1.8, 2.4], size=8)
figure(QF / 'figQ3_checks.png', 'Share of respondents rating each check as important, with 95 percent Wilson intervals',
       '06_questionnaire/figures/figQ3_checks_data.csv, from the questionnaire dataset.')

H3('4.2.5 Reliability of the scales')
RL = Q['reliability']
P(f"Table 4.6 gives Cronbach's alpha for each multi-item scale (Cronbach, 1951). The System Usability Scale reached {RL['SUS']:.3f} and "
  f"the scales for usefulness and ease of use reached {RL['PU']:.3f} and {RL['PEU']:.3f}, which is adequate for reporting them as scales. "
  f"The two facilitating-conditions items, on having a device and having internet access, gave an alpha of {RL['FC']:.3f}. They do not "
  f"form a scale and are reported as separate items.")
table("Reliability of the multi-item scales", ['Scale', 'Items', "Cronbach's alpha"],
      [['System Usability Scale', 'S1 to S10, even items recoded', f"{RL['SUS']:.3f}"], ['Perceived usefulness', 'PU1 to PU3', f"{RL['PU']:.3f}"],
       ['Perceived ease of use', 'PEU1 to PEU3', f"{RL['PEU']:.3f}"], ['Facilitating conditions', 'FC1 and FC2', f"{RL['FC']:.3f}"],
       ['Effects of order errors', 'D1 to D6', f"{RL['D']:.3f}"], ['Importance of checks', 'E1 to E12', f"{RL['E']:.3f}"]], QSRC)
trace(f"{RL['SUS']:.3f}", 'SUS alpha', 'questionnaire_results.json reliability.SUS')

H3('4.2.6 Usability')
sa, ss, scu = SU['All'], SU['Staff'], SU['Customer']
w = Q['sus_staff_vs_customer_welch']
P(f'Table 4.7 gives the System Usability Scale scores, calculated as Brooke (1996) describes. The mean for all respondents was '
  f'{sa["mean"]:.2f}, with a 95 percent interval of {sa["ci95"][0]:.2f} to {sa["ci95"][1]:.2f}. This is significantly below the benchmark '
  f'of 68 recommended by Sauro and Lewis (2016), with t = {sa["t_vs_68"]:.2f} on {sa["df"]} degrees of freedom and p below 0.001. Staff gave a mean of '
  f'{ss["mean"]:.2f} and customers {scu["mean"]:.2f}, and the difference between them was not significant, with a Welch t of {w["t"]:.2f} '
  f'and p = {w["p_two_sided"]:.2f}. Only {sa["share_above_68"]["k"]} of the {sa["n"]} respondents, {_pct(sa["share_above_68"]["k"], sa["n"])} '
  f'percent, scored Verity above 68.')
P(f'On the adjective scale of Bangor et al. (2009) the mean corresponds to Poor, and on the acceptability ranges of Bangor et al. (2008) '
  f'it falls in the range Not acceptable, although the upper end of the interval reaches the Marginal range. On the curved grading scale '
  f'of Sauro and Lewis (2016) it receives the grade F. The scores were widely spread, with a standard deviation of {sa["sd_sample"]:.2f}, '
  f'and Figure 4.2 shows that respondents in both groups gave scores across the whole range.')
trace(f'{sa["mean"]:.2f}', 'SUS mean all respondents', 'questionnaire_results.json sus.All.mean; questionnaire_tables.xlsx sheet SUS')
table('System Usability Scale scores against the benchmark of 68', ['Statistic', 'Staff', 'Customers', 'All'],
      [['n', ss['n'], scu['n'], sa['n']], ['Mean', f"{ss['mean']:.2f}", f"{scu['mean']:.2f}", f"{sa['mean']:.2f}"],
       ['SD, sample', f"{ss['sd_sample']:.2f}", f"{scu['sd_sample']:.2f}", f"{sa['sd_sample']:.2f}"],
       ['95% CI', *[f"{d['ci95'][0]:.2f} to {d['ci95'][1]:.2f}" for d in (ss, scu, sa)]],
       ['t against 68', *[f"{d['t_vs_68']:.2f}" for d in (ss, scu, sa)]], ['p, two-sided', *['below 0.001' if d['p_two_sided'] < 0.001 else d['p_two_sided'] for d in (ss, scu, sa)]],
       ['Scored above 68', *[f"{d['share_above_68']['k']} of {d['n']}" for d in (ss, scu, sa)]],
       ['Adjective, Bangor et al. (2009)', ss['adjective_bangor_2009'], scu['adjective_bangor_2009'], sa['adjective_bangor_2009']],
       ['Acceptability, Bangor et al. (2008)', ss['acceptability_bangor_2008'], scu['acceptability_bangor_2008'], sa['acceptability_bangor_2008']],
       ['Grade, Sauro and Lewis (2016)', ss['grade_sauro_lewis_2016'], scu['grade_sauro_lewis_2016'], sa['grade_sauro_lewis_2016']]], QSRC)
figure(QF / 'figQ1_sus.png', 'Distribution of System Usability Scale scores by respondent group',
       '06_questionnaire/figures/figQ1_sus_data.csv, from the questionnaire dataset.')

H3('4.2.7 Usefulness, ease of use and intention')
ACC = ['PU1', 'PU2', 'PU3', 'PEU1', 'PEU2', 'PEU3', 'BI1', 'FC1', 'FC2', 'VOL1']
acc_rows = [[k, IT[k]['wording'], IT[k]['Staff']['mean'], IT[k]['Customer']['mean'], IT[k]['All']['mean'], pc(IT[k]['All']['agree_pct']),
             f"{IT[k]['All']['agree_ci95'][0]:.1f} to {IT[k]['All']['agree_ci95'][1]:.1f}"] for k in ACC]
f1 = Q['f1_willingness_yes']
r_pu, r_peu, r_sus = Q['corr_pu_bi1'], Q['corr_peu_bi1'], Q['corr_sus_bi1']
P(f'Table 4.8 and Figure 4.3 give the answers on usefulness, ease of use, intention and the conditions for use. No item was agreed '
  f'by a majority. Agreement that Verity would reduce errors in orders was {pc(IT["PU1"]["All"]["agree_pct"])} percent, and agreement '
  f'that respondents would use Verity if it were available was {pc(IT["BI1"]["All"]["agree_pct"])} percent. The item agreed most often '
  f'was having the phone or computer needed to use Verity, at {pc(IT["FC1"]["All"]["agree_pct"])} percent. Asked in Part I whether '
  f'business customers would be willing to enter their own orders online, {f1["All"]["k"]} of the 200 respondents answered Yes, '
  f'{_pct(f1["All"]["k"], 200)} percent, with a 95 percent interval of {f1["All"]["ci95"][0]:.1f} to {f1["All"]["ci95"][1]:.1f} percent.')
P(f'Intention to use was related more closely to perceived usefulness than to ease of use. The correlation of the intention item with '
  f'the mean of the usefulness items was {r_pu:.2f}, p {"below 0.001" if _r_p(r_pu) < 0.001 else "= " + format(_r_p(r_pu), ".3f")}, while '
  f'its correlation with the mean of the ease-of-use items was {r_peu:.2f}, p = {_r_p(r_peu):.3f}. Its correlation with the usability '
  f'score was also weak, at {r_sus:.2f}, p = {_r_p(r_sus):.3f}. This matches the finding of Davis (1989), reviewed in Section 2.4.1, that usefulness is the '
  f'stronger influence on acceptance. Only {pc(IT["VOL1"]["All"]["agree_pct"])} percent agreed that using Verity would be their own '
  f'choice, which suggests that many respondents expect use to be required by an employer or supplier. Venkatesh et al. (2003) '
  f'treat voluntariness as a moderator of the effect of social influence on intention, which they found to be stronger where use '
  f'is mandatory.')
trace(f'{r_pu:.2f}', 'correlation PU mean with BI1', 'questionnaire_results.json corr_pu_bi1')
table('Usefulness, ease of use, intention and conditions for use', ['Item', 'Statement', 'Staff mean', 'Customer mean', 'All mean', 'Agree %', '95% CI'],
      acc_rows, QSRC + ' Agree means 4 or 5 on the five-point scale.', widths=[1.2, 6.2, 1.6, 1.8, 1.5, 1.5, 2.2], size=8)
figure(QF / 'figQ2_acceptance.png', 'Agreement with the acceptance items, with 95 percent Wilson intervals',
       '06_questionnaire/figures/figQ2_acceptance_data.csv, from the questionnaire dataset.')

H3('4.2.8 Open answers')
f2 = list(CAT['F2. Biggest order-handling problem']['All'].items())
f3 = list(CAT['F3. Additional feature requested']['All'].items())
P(f'Table 4.9 and Table 4.10 list the answers given most often to the two open questions. The problem named most often was '
  f'the answer that {f2[0][0][0].lower() + f2[0][0][1:]}, given by {f2[0][1]} respondents, followed by the answer that '
  f'{f2[1][0][0].lower() + f2[1][0][1:]}, given by {f2[1][1]}. The '
  f'features requested most often were to {f3[0][0][0].lower() + f3[0][0][1:]}, by {f3[0][1]} respondents, and to '
  f'{f3[1][0][0].lower() + f3[1][0][1:]}, by {f3[1][1]}. Both are already part of Verity through its audit trail and status history, '
  f'which suggests that the demonstration did not make them visible.')
table('Biggest order-handling problem, most frequent answers', ['Answer', 'Respondents'], [[k, v] for k, v in f2[:8]], QSRC, widths=[13, 3])
table('Additional features requested, most frequent answers', ['Answer', 'Respondents'], [[k, v] for k, v in f3[:8]], QSRC, widths=[13, 3])

