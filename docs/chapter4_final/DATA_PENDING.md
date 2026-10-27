# Open items in Chapter Four (technical part)

The questionnaire is reported separately from this chapter. Its instrument and analysis script are in 06_questionnaire.

## Needs data that does not exist yet

| Where in the chapter | Item | What closes it |
|---|---|---|
| 4.5, Table 4.18 and research question 3 | At least 60 percent fewer manual entry errors | Run the baseline session (`05_baseline_pack/BASELINE_INSTRUCTIONS.md`), then `python3 analyze_baseline.py manual_entries.csv verity_orders.csv`. Below about 80 pairs, report the comparison as indicative only. |
| 4.5, Table 4.18 and research question 4 | 30 to 50 percent faster processing | Same baseline run, `time` in `baseline_results.json`. |

## Needs wording that was not supplied

| Where | Item | What closes it |
|---|---|---|
| 4.5, Table 4.18 and the research questions | [EXACT CHAPTER ONE WORDING NEEDED] for each objective and each of the five research questions | Paste the Chapter One wording. The answers assume the research questions follow the order of the objectives. Check that assumption. |
| 4.5, Table 4.18 | Objective 1 is not listed | Supply its wording and success criterion. |
| 4.2, Table 4.3 | Mapping to "the seven checks of Table 2.1" | Confirm that Table 2.1 lists SKU, quantity, customer details, pricing, duplicate orders, stock and mandatory fields, as the brief stated. |
| 4.6 | Limitations "listed by the user" | That list was not available. Add any item it contains that 4.6 does not already cover. The replicates remove the single-run limitation. |
| 06_questionnaire/consent_text.md | [PROJECT CONTACT E-MAIL NEEDED] | Insert the project contact. |
| 05_baseline_pack | Session date (the pack is built for 2 November 2026) | Run `build_baseline_pack.py --session-date YYYY-MM-DD`, then `gen_session_sql.py`. |
