# Verity: intelligent order processing

A web app for a logistics company: customers place their own orders (from the catalogue, by uploading the spreadsheet they already use, or by pasting a WhatsApp message), every order is validated on the server, and the order moves through approval, bank-transfer payment, warehouse picking, dispatch and a customer-held delivery code. One app serves all seven roles.

Built from the *Intelligent Order Processing System* design document (RBS Albergoni Online, Group 6, v1.0). Where this build differs from that document, see [Changes from the design](#changes-from-the-design).

## Stack

| Layer | What |
| --- | --- |
| Front end | React 18 + Vite, react-router, plain CSS (`src/index.css`) |
| Database | Supabase Postgres. All business rules are SQL functions (`supabase/migrations/0002_functions.sql`) |
| Security | Supabase Auth, row-level security on every table, role checks in every function |
| Files | Supabase Storage, private buckets for registration documents and payment proofs |
| Jobs | `pg_cron`: payment-window expiry every 5 min, reminders hourly |
| Live updates | Supabase Realtime on `notifications` (bell + screen refresh) |
| Admin accounts | Edge function `admin-users` (needs the service key, so it can't run in the browser) |

## Run it

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # unit tests for the spreadsheet / message parser
npm run build
```

The app points at the Verity Supabase project by default. To use another project, copy `.env.example` to `.env.local`, then apply `supabase/migrations/*.sql` in order, then `supabase/seed.sql`, and deploy `supabase/functions/admin-users`.

### Demo accounts

All use the password `VerityDemo#2026`. Change or remove these accounts before real use.

| Role | E-mail |
| --- | --- |
| Customer | buyer@adebayo.example, orders@okafor.example |
| Ops & Approval Desk | ops@verity.example |
| Finance | finance@verity.example |
| Warehouse | warehouse@verity.example |
| Dispatch Coordinator | dispatch@verity.example |
| Driver (open on a phone) | driver1@verity.example, driver2@verity.example |
| Administrator | admin@verity.example |

## How an order flows

```
draft → submitted → validation_failed (customer fixes) ─┐
                  → pending_approval → rejected ────────┤ resubmit
                  → awaiting_payment  (auto-approved: clean, prepaid, under the limit)
awaiting_payment → payment_verification → paid | payment_rejected (3 tries)
paid → picking → packed | shortage_hold → (deliver available + refund | wait | cancel)
packed → assigned → out_for_delivery → delivered (correct code) | delivery_failed → reassign
```

The allowed moves live in one table, `order_transitions`; `_transition()` rejects anything else.

## Validation engine (`_validate`)

All rules run on every check and every result is stored (`validation_results`, newest run has `current = true`):

| Rule | Severity |
| --- | --- |
| Mandatory fields (items, address, date) | fail |
| SKU exists and is active, plus every upload line that didn't match the catalogue | fail |
| Quantity is a whole number within the product's min/max | fail |
| Stock: quantity ≤ on hand − reserved | fail |
| Customer account active | fail |
| Price equals the price list within tolerance | fail |
| Delivery date not in the past; address is the customer's own and in an allowed region | fail |
| Duplicate: same items from the same customer within the window | warn (customer must confirm) |
| Unusual quantity: more than 3× the customer's average for that product | warn (shown to Ops) |

## Success criteria: what the simulation actually shows

Admins can run **Reports → Run 500-order simulation**. It creates orders through the real `save_draft` / `submit_order` functions with known planted errors, scores them, then rolls everything back and keeps only the summary.

On purpose, it also plants three realistic mistakes no rule checks for: the neighbouring product picked by mistake, a quantity typo that stays within limits (20→200), and the wrong saved address. Without these the score would only be the rules grading themselves.

Latest run (500 orders, seed 0.42):

| | Result |
| --- | --- |
| Error types the rules target (10 types, 216 orders) | 216/216 caught (100%) |
| Untargeted realistic errors (59 orders) | 10/59 flagged (17%) |
| Clean orders passed without a flag | 207/225 (92%); 18 got an unusual-quantity or duplicate warning |
| Accuracy on targeted errors + clean orders | 95.9% |
| **Accuracy on all 500** | **86.6%, below the 90% target** |
| Stored orders missing a mandatory field | 0 (enforced in the database) |

The **60% error reduction** and **30–50% faster** criteria can't be produced by a script. They need a manual baseline: time people re-keying about 30 sample orders from Excel/WhatsApp, count their errors, and compare with the stage timings on the Reports page.

## Changes from the design

These were agreed before the build:

1. **Payment window pauses while Finance checks a proof.** Expiry only applies in *Awaiting payment* / *Payment rejected*. A rejected proof gives the customer at least 24 h to re-upload.
2. **Stock is re-checked under row locks at approval.** Two orders that both passed the submit-time check can't both reserve the last units.
3. **One rule for revealing the delivery code.** It's created when the order is packed and visible to the customer only while the order is *Out for delivery*. It is not e-mailed. The table holding it is readable only by that customer; the driver gets a typing box and attempts-left count.
4. **Auto-approval is on by default** for prepaid orders that pass every rule with no warnings and are under ₦500,000 (both configurable).
5. **Spreadsheet and message upload.** `.xlsx`/`.csv` files and pasted WhatsApp text are mapped to catalogue products (SKU first, then a cautious name match). Lines that don't match go to the validation engine as SKU failures.
6. **Shortage options** are: deliver what is available and refund the rest (with tax), wait for restock (the reservation is kept), or cancel the whole order (full refund). "Partial delivery" and "cancel affected items" did the same thing in a single delivery, so they were merged.
7. **Only the Ops Desk can override a delivery** (reason of 10+ characters, logged, Admin notified). Admin doesn't, which keeps the separation of duties in §2.
8. **Drivers can't see prices at all.** They read through `driver_deliveries()`, not the orders tables.

## Not done yet

- **E-mail.** Notifications marked `send_email` are queued in `notifications` but not sent. This needs an e-mail provider (e.g. Resend) and a small edge function on a schedule. Supabase's built-in mailer also won't deliver sign-up verification mails to arbitrary addresses without custom SMTP. Until that's configured, set Supabase Auth to not require e-mail confirmation, or confirm users from the dashboard.
- Credit terms, pay-on-delivery, payment gateway, returns, GPS: listed as future work in the design.
- No end-to-end browser tests against the live database yet. The workflow is tested in SQL (`_test_flow` in the project and `run_simulation`).
