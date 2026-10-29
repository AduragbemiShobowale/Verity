# Chapter 4 – technical evaluation materials

Everything here comes from simulation run 4 (500 orders, seed 0.42) on the live Verity database. All companies, people, e-mails and phone numbers are fictional; e-mails use the reserved `.example` domain.

| File | What it is |
| --- | --- |
| `Chapter4_Technical_Evaluation.docx` | Draft of the technical part of Chapter Four: implementation, functional and access-control tests, simulation design, results, success criteria, discussion, limitations. 13 tables, 5 figures. |
| `Verity_Simulation_Data.xlsx` | All 500 orders plus summary sheets (customers, error types, confusion matrix, rules, timing, success criteria) calculated with formulas, and a **Manual baseline** template to fill in. |
| `figures/*.png` | The five figures at print resolution, for pasting separately if needed. |
| `simulation_orders.json` | Raw export of the `simulation_orders` table. |
| `metrics.json` | Every number used in the chapter. |

## Rebuilding

```bash
python3 analyse.py                                              # simulation_orders.json -> metrics.json
python3 charts.py && NODE_PATH=$(npm root -g) node render.mjs   # figures
python3 workbook.py                                             # Excel workbook (then recalc with LibreOffice)
NODE_PATH=$(npm root -g) node build_doc.cjs                     # Word chapter
```

To produce a new run, call `select run_simulation_detailed(500, <seed>)` in the Supabase SQL editor after `select set_config('request.jwt.claims', _claims('admin@verity.example'), false);`, then export `simulation_orders` for that run id.
