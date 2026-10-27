# Chapter Four evaluation materials

This folder holds everything behind Chapter Four: the Stage 1 data and the Stage 2 chapter. Every number in the chapter comes from a file here or from a query recorded here. `TRACEABILITY.csv` maps each number in the running text to its source, and the build asserts each value against that source. Run 4 materials in `../chapter4/` are unchanged and remain the first run.

All simulated customers, people and e-mail addresses are fictional and use the reserved `.example` domain. Every simulated order and account was created inside a database transaction that was rolled back. After the runs the live database still held 3 orders and 3 customers, with no simulation users, no stock movements and no leftover trigger.

## How to rebuild

The database-side harness is in `supabase/migrations/0006_functional_tests_extended.sql` and `0007_simulation_final.sql`.

```
cd 07_analysis && python3 analyse_final.py && python3 workbook_final.py && python3 <xlsx skill>/recalc.py Verity_Simulation_Data_Final.xlsx 180
python3 charts_final.py && NODE_PATH=$(npm root -g) node render_final.mjs && python3 build_traceability.py
cd ../08_chapter && python3 build_chapter.py && python3 check_style.py
```

## Files

### 01_system_facts (section 1.1)
| File | Description |
|---|---|
| order_statuses.csv | The 17 order statuses in enum order, with their meaning. |
| state_machine_transitions.csv | The 36 permitted from and to status pairs in `order_transitions`. |
| validation_rules_and_run4_coverage.csv | The nine rules with check, severity, mapping to the seven checks, and how often each fired in run 4. |
| integration_features.csv | CSV import, CSV export and webhooks: implemented or not, where in the code, how tested, test case and result. |
| catalogue_snapshot.csv | The 12 products with price, stock, limits and status, as used by the simulations. |
| regions.csv | Delivery regions and fees. |
| system_facts.json | Counts, live settings, extensions and the documented run 4 harness defect, with the query that verifies it. |

### 02_functional_tests (section 1.2)
| File | Description |
|---|---|
| functional_tests.csv | All 26 cases with expected result, actual result, Pass or Fail, and the evidence file. |
| raw_test_output_2026-10-27.json | Raw output of `_test_extended` (cases 15 to 18) and `_test_flow` (cases 1 to 12), both rolled back. |
| raw_warehouse_product_test_2026-10-27.txt | Raw output of the rolled-back warehouse product test (cases 13 and 14). |
| sample_import_old_price.csv | The sample customer sheet: an old cement price and one unknown item code. |
| run_import_test.mjs | Runs the app's own `src/lib/upload.js` parser on the sample sheet. |
| import_parser_output.json | The parser's output, which was passed to `save_draft`. |
| catalogue_ids.json | Product IDs and prices given to the parser. |
| delivery_log_rows_dispatch.json | Rows `delivery_log()` returned for the Dispatch account. |
| test_delivery_log_csv.mjs | Applies the app's delivery-log CSV code, taken verbatim from `DispatchPages.jsx`, to those rows. |
| exported_delivery_log.csv | The CSV file that code produced (case 20). |
| delivery_log_csv_result.txt | Console output of that test. |
| rls_check.sql | The row-level security query pattern. |
| rls_results_2026-10-27.csv | Rows visible to each account, and the results of the write attempts. |

### 03_simulation (section 1.3)
| File | Description |
|---|---|
| raw/run5_replicate1.json | Replicate 1 (seed 0.42), 500 orders. Every stored field: inputs, answer key, outcome, rules, messages, timing, status-history events. |
| raw/run6_replicate2.json | Replicate 2 (seed 0.43), same fields. |
| raw/run7_replicate3.json | Replicate 3 (seed 0.44), same fields. |
| replicate1_orders.csv | Replicate 1, one row per order, with the columns listed in 1.3. |
| replicate2_orders.csv | Replicate 2, same columns. |
| replicate3_orders.csv | Replicate 3, same columns. |
| extract_mcp.py | Extracts the JSON rows from a saved database query result. |

### 04_sensitivity (section 1.4)
| File | Description |
|---|---|
| raw/runs8to13_replays_of_run5.json | Six replays of replicate 1, at factors 3, 4 and 5 with histories of 4 and 10. Run 8 reproduces run 5 exactly. |
| sensitivity_results.csv | False-alarm rate and slip detection rate, with Wilson intervals, for each setting. |

### 05_baseline_pack (section 1.5, nothing filled in)
| File | Description |
|---|---|
| BASELINE_INSTRUCTIONS.md / .docx | Facilitator instructions for both conditions, plus the known differences between them. |
| sample_80.csv | The 80 references with format, set and source order. It carries no error labels. |
| messages/B-001 to B-080 | The 80 incoming orders, rotated across an Excel sheet (.xlsx), an e-mail (.txt) and a WhatsApp message (.txt). |
| messages_all.txt | The e-mail and WhatsApp messages in one printable file. |
| reference/price_list.xlsx | Price list, with limits, stock and product status. |
| reference/customer_register.xlsx | Customers with saved addresses and account status. |
| reference/orders_already_received.csv | Orders logged earlier the same morning, for spotting repeats. |
| entry_template.xlsx | The manual-condition record: participant, order reference, fields, problem flagged, start, end and seconds. |
| counterbalancing_schedule.csv | Condition order and order set for participant slots P01 to P12. |
| facilitator_only/ANSWER_KEY.csv | Planted error, correct handling and values as sent, for each order. Keep away from participants and from Verity. |
| setup_baseline_session.sql | Dummy accounts and session settings. Not run. It was tested once inside a rolled-back block. |
| cleanup_baseline_session.sql | Removes the dummy rows after the session. Not run. |
| extract_baseline.sql | Read-only queries: elapsed time from draft to approval from the status history, plus the audit-log entries. |
| analyze_baseline.py | Scores both conditions. It refuses to run until real session files exist. |
| build_baseline_pack.py | Regenerates the pack for a given session date, with fixed seed 20261027. |
| gen_session_sql.py | Regenerates the setup and cleanup SQL from the pack. |

### 06_questionnaire (section 1.6, no responses)
| File | Description |
|---|---|
| analyze_questionnaire.py | The item codes (CODES) and the analysis: validity, Cronbach's alpha, SUS against 68, interpretation scales and agreement shares. It refuses to run without data. |
| build_questionnaire.py | Writes the questionnaire, codebook and column template from CODES. |
| questionnaire.md / .docx | Part I (before the demonstration) and Part II (after). |
| codebook.csv | Code, part, section, wording, response type and coding for every item. |
| export_column_template.csv | The column header the response export must use. |
| consent_text.md / .docx | Participant information and consent. |
| demonstration_script.md | The 10-minute demonstration, step by step. |

### 07_analysis (section 1.7)
| File | Description |
|---|---|
| analyse_final.py | Computes every Part B measure, with Wilson intervals and sample SD, and the replicate ranges. |
| metrics_final.json | All computed measures for the three replicates and the sensitivity runs. |
| Verity_Simulation_Data_Final.xlsx | The run 4 workbook unchanged, plus R1 to R3 Orders and Summary sheets with live formulas, a Replicate range sheet and a Sensitivity sheet. |
| workbook_final.py | Builds that workbook. |
| charts_final.py, render_final.mjs | Build Figures 4.1 to 4.8 and render them to PNG. |
| figures/fig4_n_*.png / .svg / .html | Figures 4.1 to 4.8: regions, outcomes, detection, measures, rule activity, time distribution, time across the run, sensitivity. |
| figures/fig4_n_*_data.csv | The data behind each figure. |
| build_traceability.py | Writes and checks TRACEABILITY.csv. |

### 08_chapter (Stage 2)
| File | Description |
|---|---|
| Chapter_Four.docx | The chapter, in the layout of the run 4 chapter: 22 tables and 8 figures, each with a Source line, page numbers, and an APA 7 reference list. |
| chapter_tables.xlsx | Every chapter table as an editable sheet. |
| build_chapter.py | Builds the chapter and its tables from the files above. |
| check_style.py | Checks the running text against the writing rules. Last run: 0 hard findings. |
| traceability_from_chapter.csv | Numbers recorded while the chapter was built. TRACEABILITY.csv is the full, checked version. |

### Root
| File | Description |
|---|---|
| TRACEABILITY.csv | Each number in the running text, with its file and field, workbook cell or query. 83 entries, all checked. |
| DATA_PENDING.md | Every [DATA PENDING] or wording placeholder, and what closes it. |
