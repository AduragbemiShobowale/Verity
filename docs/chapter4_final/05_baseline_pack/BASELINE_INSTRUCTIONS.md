# Manual baseline session: facilitator instructions

This session produces the data for Objective 3 (at least 60 percent fewer manual entry errors) and Objective 4 (30 to 50 percent faster processing). No timings or results exist yet. Do not fill any in on behalf of participants.

## What is in the pack

| File | Use |
|---|---|
| `messages/B-001.xlsx` to `messages/B-080.*` | The 80 incoming orders, rotated across an Excel order sheet, an e-mail and a WhatsApp message. Print the text files from `messages_all.txt`. |
| `reference/price_list.xlsx` | Prices, minimum and maximum order quantities, stock on hand and product status. |
| `reference/customer_register.xlsx` | Customer contacts, the two saved addresses and the account status. |
| `reference/orders_already_received.csv` | Orders logged earlier the same morning, so participants can spot a repeat. |
| `entry_template.xlsx` | The record for the manual condition. One row per order. |
| `counterbalancing_schedule.csv` | Which condition and which order set each participant does first. |
| `sample_80.csv` | Facilitator list of references, formats and sets. It carries no error labels. |
| `facilitator_only/ANSWER_KEY.csv` | Planted error and correct handling for each order. Never show it to a participant or load it into Verity. |
| `setup_baseline_session.sql`, `cleanup_baseline_session.sql` | Prepare and remove the dummy customer accounts. Neither has been run. |
| `extract_baseline.sql` | Pulls the Verity condition results from the database after the session. |
| `analyze_baseline.py` | Scores both conditions once the real files exist. |

The 80 orders come from replicate 1 of the final simulation, drawn with the fixed seed 20261027. They are 32 clean orders, 38 rule-targeted orders with at least 2 of each of the 12 rule-targeted types, and 10 orders with an error no rule targets (4 wrong product, 3 quantity slip, 3 wrong address). They are split into two matched sets of 40, each with 16 clean, 19 rule-targeted and 5 no-rule orders.

## Before the session

1. Choose the session date and rebuild the pack: `python3 build_baseline_pack.py --session-date YYYY-MM-DD`, then `python3 gen_session_sql.py`. Every message is dated that day and every delivery date is relative to it.
2. On the morning of the session, an administrator runs `setup_baseline_session.sql`. It turns automatic approval off, marks SAND-T as discontinued, and creates one dummy login per customer. The password is `Baseline#2026`. It also gives each customer four earlier orders and enters the orders listed in `orders_already_received.csv`.
3. Check that live stock levels match `reference/price_list.xlsx`. The over-stock orders depend on them.
4. Assign each participant a slot (P01 onwards) from `counterbalancing_schedule.csv`. Slots rotate through four sequences: manual set 1 then Verity set 2, Verity set 2 then manual set 1, manual set 2 then Verity set 1, Verity set 1 then manual set 2. Each order is therefore processed manually by some participants and in Verity by others, and the condition order is balanced.
5. Read the consent text in `06_questionnaire/consent_text.md` with each participant and record consent.

## Manual condition

Single entry with the participant's own visual check, as orders are handled today.

1. Give the participant the messages in their set, in reference order, with the three reference files.
2. For each message, the participant opens it, notes the start time, and types the order into one row of `entry_template.xlsx`. The row holds the customer, delivery address, delivery date, item codes and quantities.
3. If anything looks wrong, they set Problem flagged to Yes and describe it, then still type the order as it was sent. They do not correct values.
4. They note the end time. The Seconds column calculates itself.
5. There is no second checker. Do not help or confirm.

## Verity condition

Entry by a dummy customer account, followed by approval by an Ops Desk account.

1. The participant signs in as the customer named in the message, using the e-mail from the customer register and the session password.
2. They create a new order, type the lines, choose the saved address and the delivery date as sent, and write the reference and their slot in Notes, for example `B-017 P03`. Then they submit.
3. If Verity blocks the order or asks for confirmation, they read the message, record nothing extra and move on. They do not fix the order. The system's response is the result being measured.
4. Orders that reach the approval queue are approved or rejected by a second person signed in as `ops@verity.example`, working through the queue in order. The approver may reject an order they judge wrong and should say why in the comment.
5. Timing comes from the status history. Participants do not time anything in this condition.

## After the session

1. Save the Entries sheet of every manual template as CSV and combine them into `manual_entries.csv`.
2. Run both queries in `extract_baseline.sql` and save them as `verity_orders.csv` and `verity_audit.csv`.
3. Run `python3 analyze_baseline.py manual_entries.csv verity_orders.csv`. Below about 80 order pairs, treat the error comparison as indicative only. The script marks this.
4. Run `cleanup_baseline_session.sql`. It restores automatic approval and SAND-T and removes every dummy row.

## Known differences between the two conditions

These are fixed by the design, so state them when reporting.

- In Verity the customer cannot type a unit price. The catalogue price is always used (functional test 16b). The three stale-price orders therefore cannot carry their error into a Verity order. Record whether the approver notices the quoted price.
- The unknown item line in bad-SKU messages shows "Galvanised wire mesh, 5 rolls". The simulated line had no description or quantity, so this is a rendering assumption.
- The Verity condition time includes the approver's queue wait. The manual condition time does not include any second person.
