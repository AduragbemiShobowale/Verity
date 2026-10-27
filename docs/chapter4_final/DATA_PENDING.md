# Open items in Chapter Four (technical part)

The questionnaire is reported separately from this chapter. Its instrument and analysis script are in 06_questionnaire.

## Needs data that does not exist yet

| Where in the chapter | Item | What closes it |
|---|---|---|
| 4.5, Table 4.18 and research question 3 | At least 60 percent fewer manual entry errors | Run the baseline session (`05_baseline_pack/BASELINE_INSTRUCTIONS.md`), then `python3 analyze_baseline.py manual_entries.csv verity_orders.csv`. Below about 80 pairs, report the comparison as indicative only. |
| 4.5, Table 4.18 and research question 4 | 30 to 50 percent faster processing | Same baseline run, `time` in `baseline_results.json`. |

## Other open items

The objectives, research questions and Table 2.1 mapping now use the wording of Chapters One and Two.

| Where | Item | What closes it |
|---|---|---|
| 4.6 | Limitations "listed by the user" | That list was not available. Add any item it contains that 4.6 does not already cover. The replicates remove the single-run limitation. |
| 06_questionnaire/consent_text.md | [PROJECT CONTACT E-MAIL NEEDED] | Insert the project contact. |
| 05_baseline_pack | Session date (the pack is built for 2 November 2026) | Run `build_baseline_pack.py --session-date YYYY-MM-DD`, then `gen_session_sql.py`. |
