# Open items in Chapter Four

The questionnaire results are in Section 4.2, from the dataset supplied by the client team (06_questionnaire/analyze_dataset.py).

## Needs data that does not exist yet

| Where in the chapter | Item | What closes it |
|---|---|---|
| 4.6, Table 4.29 and research question 3 | At least 60 percent fewer manual entry errors | Run the baseline session (`05_baseline_pack/BASELINE_INSTRUCTIONS.md`), then `python3 analyze_baseline.py manual_entries.csv verity_orders.csv`. Below about 80 pairs, report the comparison as indicative only. |
| 4.6, Table 4.29 and research question 4 | 30 to 50 percent faster processing | Same baseline run, `time` in `baseline_results.json`. |

## Other open items

The objectives, research questions and Table 2.1 mapping now use the wording of Chapters One and Two.

| Where | Item | What closes it |
|---|---|---|
| 4.7 | Limitations "listed by the user" | That list was not available. Add any item it contains that 4.7 does not already cover. The replicates remove the single-run limitation. |
| 05_baseline_pack | Session date (the pack is built for 2 November 2026) | Run `build_baseline_pack.py --session-date YYYY-MM-DD`, then `gen_session_sql.py`. |
| 4.2.3 | Section C of the questionnaire (C1 to C5) | The export holds numeric codes that cannot be matched to the options with certainty, and C3 (select all) holds one number per respondent. Ask the client team for the original labelled export, then report frequency and type of errors and compare C3 with the detection rates in Table 4.21. |
| Data handling | The export links 146 respondents' names and e-mails to their answers, although the questionnaire promised the contact page would never be linked | The analysis uses a de-identified copy. Ask the client team to delete or separate the linked copy. |
