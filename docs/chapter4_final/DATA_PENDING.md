# Open items in Chapter Four

## Needs data that does not exist yet

| Where in the chapter | Item | What closes it |
|---|---|---|
| 4.2, Table 4.1 | Respondents distributed, returned and valid, by group | Run the questionnaire (target 150 valid from about 190). Export with the columns in `06_questionnaire/export_column_template.csv`. Run `python3 analyze_questionnaire.py responses.csv`. |
| 4.2, Table 4.2 | Cronbach's alpha for SUS, PU, EOU and FC | Same run, `reliability` in `questionnaire_results.json`. |
| 4.2, Table 4.3 | SUS mean, SD, 95% CI, t test against 68, adjective, acceptability and grade, by group | Same run, `sus`. |
| 4.2, Table 4.4 | Agreement with the PU, EOU, BI1, FC1, FC2 and VOL1 items, with Wilson CIs | Same run, `items`. |
| 4.2, last paragraph | Part I error types seen and requirement importance | Same run, `errors_seen` and the IMP items in `items`. |
| 4.6, Table 4.19 and research question 3 | At least 60 percent fewer manual entry errors | Run the baseline session (`05_baseline_pack/BASELINE_INSTRUCTIONS.md`), then `python3 analyze_baseline.py manual_entries.csv verity_orders.csv`. Below about 80 pairs, report the comparison as indicative only. |
| 4.6, Table 4.19 and research question 4 | 30 to 50 percent faster processing | Same baseline run, `time` in `baseline_results.json`. |
| 4.6, Table 4.19 and research question 5 | Usability and acceptance | Questionnaire results above. |
| 4.6 | Link between Part A and Part B, such as errors respondents report against errors the engine catches | Both of the above. Compare `errors_seen` with the detection rates in Table 4.12. |

## Needs wording that was not supplied

| Where | Item | What closes it |
|---|---|---|
| 4.6, Table 4.19 and the research questions | [EXACT CHAPTER ONE WORDING NEEDED] for each objective and each of the five research questions | Paste the Chapter One wording. The answers assume the research questions follow the order of the objectives. Check that assumption. |
| 4.6, Table 4.19 | Objective 1 is not listed | Supply its wording and success criterion. |
| 4.3, Table 4.7 | Mapping to "the seven checks of Table 2.1" | Confirm that Table 2.1 lists SKU, quantity, customer details, pricing, duplicate orders, stock and mandatory fields, as the brief stated. |
| 4.7 | Limitations "listed by the user" | That list was not available. Add any item it contains that 4.7 does not already cover. The replicates remove the single-run limitation. |
| 06_questionnaire/consent_text.md | [PROJECT CONTACT E-MAIL NEEDED] | Insert the project contact. |
| 05_baseline_pack | Session date (the pack is built for 2 November 2026) | Run `build_baseline_pack.py --session-date YYYY-MM-DD`, then `gen_session_sql.py`. |
