// Builds Chapter4_Technical_Evaluation.docx from metrics.json, simulation_orders.json and figures/*.png.
// Run: NODE_PATH=$(npm root -g) node build_doc.cjs
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, ImageRun, LevelFormat, PageNumber, Footer, Header, TableLayoutType,
} = require('docx')

const HERE = __dirname
const m = JSON.parse(fs.readFileSync(path.join(HERE, 'metrics.json'), 'utf8'))
const rows = JSON.parse(fs.readFileSync(path.join(HERE, 'simulation_orders.json'), 'utf8'))

const FONT = 'Times New Roman'
const TEXT_W = 9026 // A4 width 11906 - 2 x 1440 margins, in DXA
const naira = (v) => (v == null ? '—' : '₦' + Number(v).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const pct = (v) => `${Number(v).toFixed(1)}%`
const cats = Object.fromEntries(m.categories.map((c) => [c.key, c]))
const cm = m.confusion_all
const ct = m.confusion_targeted
const t = m.timing
const d = m.dataset

let tableNo = 0
let figNo = 0

// ------------------------------------------------------------------ helpers
const run = (text, o = {}) => new TextRun({ text, font: FONT, size: 24, ...o })
const P = (content, o = {}) => new Paragraph({
  children: (Array.isArray(content) ? content : [content]).map((x) => (typeof x === 'string' ? run(x) : x)),
  spacing: { after: 160, line: 360 }, alignment: AlignmentType.JUSTIFIED, ...o,
})
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run(text, { bold: true, size: 28 })], spacing: { before: 360, after: 200 } })
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(text, { bold: true, size: 24 })], spacing: { before: 280, after: 160 } })
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [run(text, { bold: true, italics: true, size: 24 })], spacing: { before: 200, after: 120 } })
const bullet = (content) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: (Array.isArray(content) ? content : [content]).map((x) => (typeof x === 'string' ? run(x) : x)),
  spacing: { after: 80, line: 340 },
})
const note = (text) => new Paragraph({ children: [run(text, { italics: true, size: 20, color: '595959' })], spacing: { after: 240 } })

const border = { style: BorderStyle.SINGLE, size: 4, color: '999999' }
const borders = { top: border, bottom: border, left: border, right: border }

function table(caption, headers, body, widthsPct, o = {}) {
  tableNo += 1
  const widths = widthsPct.map((w) => Math.round((TEXT_W * w) / 100))
  widths[widths.length - 1] += TEXT_W - widths.reduce((a, b) => a + b, 0)
  const cell = (text, i, head, shade) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    borders,
    shading: head ? { type: ShadingType.CLEAR, color: 'auto', fill: 'D9E2E1' } : shade ? { type: ShadingType.CLEAR, color: 'auto', fill: shade } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: (o.right || []).includes(i) && !head ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [run(String(text ?? ''), { size: o.size || 20, bold: head || (o.boldLast && body.length && false) })],
    })],
  })
  const trs = [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) })]
  body.forEach((r, ri) => trs.push(new TableRow({
    children: r.map((v, i) => cell(v, i, false, o.boldRows && o.boldRows.includes(ri) ? 'F2F2F2' : undefined)),
  })))
  return [
    new Paragraph({ children: [run(`Table 4.${tableNo}: ${caption}`, { bold: true, size: 22 })], spacing: { before: 200, after: 100 }, keepNext: true }),
    new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, rows: trs }),
    note(o.source || 'Source: Verity simulation run 4 (500 orders, seed 0.42).'),
  ]
}

function figure(file, caption, source) {
  figNo += 1
  const buf = fs.readFileSync(path.join(HERE, 'figures', file))
  const w = buf.readUInt32BE(16)
  const h = buf.readUInt32BE(20)
  const width = 600
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 }, keepNext: true,
      children: [new ImageRun({ type: 'png', data: buf, transformation: { width, height: Math.round((width * h) / w) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [run(`Figure 4.${figNo}: ${caption}`, { bold: true, size: 22 })], spacing: { after: 60 } }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [run(source || 'Source: Verity simulation run 4 (500 orders, seed 0.42).', { italics: true, size: 20, color: '595959' })], spacing: { after: 240 } }),
  ]
}

// ------------------------------------------------------------------ content
const C = []

C.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [run('CHAPTER FOUR', { bold: true, size: 28 })], spacing: { after: 120 } }))
C.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [run('SYSTEM IMPLEMENTATION, TESTING AND RESULTS', { bold: true, size: 28 })], spacing: { after: 240 } }))
C.push(new Paragraph({
  shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'FFF4CE' },
  border: { top: border, bottom: border, left: border, right: border },
  children: [run('Note for the group: this draft covers the technical part of Chapter Four (system testing and the 500-order simulation). The questionnaire results form a separate section; insert them where the group prefers and renumber sections, tables and figures to match. Delete this note before submission.', { italics: true, size: 20 })],
  spacing: { after: 240 },
}))

C.push(H1('4.1 Introduction'))
C.push(P('This chapter presents the implementation of the Intelligent Order Processing System (named Verity) and the results of its technical evaluation. The evaluation had two parts. First, the complete order lifecycle and the role-based access rules were tested end to end against the live system. Second, a simulation of 500 customer orders, each carrying either no error or one known, deliberately planted error, was passed through the system\'s real validation engine so that its decisions could be compared with the known truth. The chapter closes by comparing the measured results with the success criteria set out in Chapter One.'))

C.push(H1('4.2 The Implemented System'))
C.push(P('Verity was implemented as a responsive web application. Customers place their own orders through a self-service portal instead of sending Excel sheets, e-mails or WhatsApp messages for staff to re-type, which removes the manual re-keying step identified as the main source of errors. Orders can be built from the live product catalogue, or created by uploading the customer\'s existing spreadsheet or pasting a message; uploaded lines are matched to catalogue products and any line that cannot be matched is reported to the customer before submission.'))
C.push(P('All business rules are enforced inside the database, not only on screen. Each order moves through a fixed state machine (draft, submitted, pending approval, awaiting payment, paid, picking, packed, assigned, out for delivery, delivered), and any transition not in the permitted list is rejected. Seven roles are supported, each with its own dashboard and permissions.'))
C.push(...table('System components', ['Layer', 'Implementation', 'Purpose'], [
  ['Presentation', 'React 18 single-page application (Vite), deployed on Vercel', 'Role-specific dashboards; phone-first driver screens'],
  ['Security', 'Supabase Auth; row-level security on every table; role check in every function', 'Each user sees and changes only what their role allows'],
  ['Application logic', '69 PostgreSQL functions (PL/pgSQL)', 'Validation engine, approval, payment, picking, shortage, dispatch and delivery-code handling'],
  ['Data', 'PostgreSQL 17 (Supabase, eu-west-1); private file storage', 'Orders, stock, invoices, payments, audit trail; payment proofs and registration documents'],
  ['Scheduling and alerts', 'pg_cron jobs; real-time notification feed', 'Expiry of unpaid orders; in-app notifications to each role'],
], [20, 45, 35], { source: 'Source: Verity source code (github.com/AduragbemiShobowale/Verity).' }))
C.push(P('The validation engine applies nine rules to every order and returns all results at once, so the customer can correct every problem in a single step. Rules are either blocking (the order cannot proceed until fixed) or warnings (the order proceeds but is flagged for the Operations and Approval Desk).'))
C.push(...table('Validation rules', ['Rule', 'Check performed', 'Severity'], [
  ['Mandatory fields', 'Items, delivery address and delivery date are present', 'Blocking'],
  ['SKU / product active', 'Every line is a catalogue product that is still sold', 'Blocking'],
  ['Quantity limits', 'Whole number within the product\'s minimum and maximum', 'Blocking'],
  ['Stock availability', 'Quantity does not exceed stock on hand minus reservations', 'Blocking'],
  ['Customer status', 'Customer account is active', 'Blocking'],
  ['Pricing', 'Line price equals the current price list', 'Blocking'],
  ['Delivery date and address', 'Date not in the past; address belongs to the customer and is in an allowed region', 'Blocking'],
  ['Duplicate order', 'Same items from the same customer within 24 hours', 'Warning (customer must confirm)'],
  ['Unusual quantity', 'Quantity more than three times the customer\'s average for that product', 'Warning (shown to Ops Desk)'],
], [24, 52, 24], { source: 'Source: Verity validation engine (_validate function).' }))

C.push(H1('4.3 Functional and Security Testing'))
C.push(H2('4.3.1 End-to-end functional testing'))
C.push(P('Each step of the order lifecycle was executed against the live database while acting as the relevant role. The test ran inside a transaction that was rolled back afterwards, so it left no data behind. Table 4.3 lists the test cases and their outcomes.'))
C.push(...table('End-to-end functional test cases', ['#', 'Test case', 'Expected result', 'Actual result', 'Result'], [
  ['1', 'Customer submits a valid prepaid order (20 bags cement, 10 iron rods)', 'Auto-approved; stock reserved; invoice issued', 'Status "awaiting payment"; 20 bags reserved; invoice ₦286,487.50', 'Pass'],
  ['2', 'Customer resubmits the same items within 24 hours', 'Duplicate warning; customer must confirm', 'Held for confirmation; after confirming, sent to Ops Desk with warning', 'Pass'],
  ['3', 'Order with no address, past date, quantity below minimum, quantity above stock, fractional quantity and unknown SKU', 'All problems reported together; order blocked', 'Six separate failures returned in one response; status "validation failed"', 'Pass'],
  ['4', 'Customer uploads payment reference', 'Order moves to payment verification', 'Status "payment verification"', 'Pass'],
  ['5', 'Finance confirms payment', 'Order paid and released to warehouse', 'Status "paid"; warehouse notified', 'Pass'],
  ['6', 'Warehouse finds 6 of 10 rods', 'Shortage hold; customer asked to choose', 'Status "shortage hold"; customer and Ops notified', 'Pass'],
  ['7', 'Customer accepts partial delivery', 'Order packed; refund raised for missing items plus tax', 'Packed; refund ₦30,960 (4 × ₦7,200 + 7.5% tax)', 'Pass'],
  ['8', 'Dispatch assigns a driver; driver confirms pickup', 'Out for delivery; delivery code visible to the customer only', 'Status "out for delivery"; code shown on customer dashboard', 'Pass'],
  ['9', 'Driver enters a wrong delivery code', 'Rejected; attempts reduced', '"Wrong code", 4 attempts left', 'Pass'],
  ['10', 'Driver enters the correct code', 'Order delivered', 'Status "delivered"; customer, Ops and Finance notified', 'Pass'],
  ['11', 'Finance pays the refund', 'Credit note issued', 'Credit note CN-9001 recorded', 'Pass'],
  ['12', 'Driver attempts to approve an order', 'Refused', '"You do not have permission to do this."', 'Pass'],
  ['13', 'Warehouse adds a new product; tries to activate it with no price', 'Hidden from customers; activation refused', 'Saved inactive at ₦0; Admin notified; database constraint refused activation', 'Pass'],
  ['14', 'Dispatch attempts to add a product', 'Refused', 'Permission error', 'Pass'],
], [5, 30, 23, 34, 8], { size: 18, source: 'Source: functional test run against the live Verity database (results rolled back).' }))
C.push(H2('4.3.2 Access-control testing'))
C.push(P('Row-level security was tested by querying the database directly as different users, bypassing the user interface. This shows that the restrictions hold even if someone calls the database without using the application screens. At the time of the test the database held three orders, one of which belonged to the customer Okafor Homes.'))
C.push(...table('Records visible to each role when querying the database directly', ['Role', 'Customer records', 'Product rows', 'Orders', 'Invoices', 'Audit log'], [
  ['Customer (Okafor Homes)', '1 (own only)', '0 (catalogue via function: 12)', '1 of 3 (own only)', '1 (own only)', '0'],
  ['Driver', '0', '0 (catalogue: 0)', '0', '0', '0'],
  ['Warehouse', '3', '12', '3', '0', '0'],
  ['Administrator', '3', '12', '3', '3', '85'],
], [26, 15, 21, 15, 11, 12], { source: 'Source: row-level security test, Verity live database.' }))
C.push(P('Customers could see only their own company\'s records, drivers could read nothing directly (their delivery list is served by a dedicated function that returns contact, address and items but no prices, invoice or payment details), and the warehouse could see stock and orders but no financial records. Every action that changes an order is written to an audit log that only the administrator can read and that cannot be edited from the application.'))

C.push(H1('4.4 Simulation Design'))
C.push(P(`To measure how accurately the system validates orders, ${m.run.orders} orders were generated and submitted through the same database functions that real customers use (save_draft and submit_order). Each order was either clean or carried exactly one planted error of a known type. Because the true state of every order was known in advance, the system's decision on each order could be scored as right or wrong.`))
C.push(H2('4.4.1 Customers and catalogue'))
C.push(P(`Twenty fictional customer companies were created for the run, spread across six delivery regions (Table 4.5). Company names, contact persons, e-mail addresses and telephone numbers are invented; e-mail addresses use the reserved ".example" domain so that no real inbox could be contacted. Each company was given two saved delivery addresses and a short history of four earlier orders, so that the unusual-quantity rule had a baseline to compare against. The catalogue contained ${m.run.products} building-materials products with fixed prices, minimum and maximum order quantities and stock levels.`))
const companyRows = Object.entries(d.by_company).sort((a, b) => a[0].localeCompare(b[0])).map(([name, n]) => {
  const r = rows.find((x) => x.company === name)
  const region = rows.find((x) => x.company === name && x.region)?.region || ''
  return [name, r.contact, r.email, region, String(n)]
})
C.push(...table('Fictional customer companies used in the simulation', ['Company', 'Contact person', 'E-mail', 'Region', 'Orders'], companyRows, [31, 19, 34, 10, 6],
  { size: 17, right: [4], source: 'Source: Verity simulation run 4. All names and contact details are fictional.' }))
C.push(H2('4.4.2 Planted errors'))
C.push(P('Thirteen error types were planted (Table 4.6). Ten are errors that a validation rule was designed to catch. The remaining three are realistic mistakes for which no rule exists: choosing a neighbouring but valid product, typing a plausible but wrong quantity, and selecting the wrong one of the customer\'s own saved addresses. These three were included deliberately; without them the test would only measure the rules against the errors they were written for, which would overstate real-world accuracy.'))
C.push(...table('Planted error types and how each was created', ['Error type', 'How it was planted', 'Rule expected to catch it'], [
  ['SKU not in catalogue', 'An extra uploaded line with an unknown product code', 'SKU'],
  ['Missing delivery address', 'Address left empty', 'Mandatory fields'],
  ['Missing delivery date', 'Date left empty', 'Mandatory fields'],
  ['Delivery date in the past', 'Date 1–5 days before the run', 'Delivery date and address'],
  ['Quantity below minimum', 'One line at its minimum quantity minus one', 'Quantity limits'],
  ['Quantity above maximum', 'One line above its maximum quantity', 'Quantity limits'],
  ['Fractional quantity', 'One line with a half unit (e.g. 10.5 bags)', 'Quantity limits'],
  ['Quantity above available stock', 'One line one unit above available stock', 'Stock availability'],
  ['Duplicate order', 'An exact repeat of a recent accepted order', 'Duplicate order'],
  ['Discontinued product', 'A line for a product no longer sold', 'SKU / product active'],
  ['Wrong (but valid) product chosen', 'A neighbouring product, e.g. 16 mm rod instead of 12 mm', 'None'],
  ['Plausible quantity typo', '200–219 bags of cement instead of about 20', 'None (unusual quantity may warn)'],
  ['Wrong saved address chosen', 'The customer\'s other saved address', 'None'],
], [30, 44, 26], { size: 19, source: 'Source: run_simulation_detailed function, Verity.' }))
C.push(H2('4.4.3 Procedure and measures'))
C.push(P('About 43% of orders were planned to be clean and 57% to carry one error, chosen at random with a fixed seed (0.42) so that the run can be repeated exactly. Automatic approval was switched off for the run so that stock was not reserved between orders. The time the database took to validate each order was measured with the server clock. After the last order, all simulated orders and customer accounts were rolled back, so the live system was left unchanged; only the result of each order was kept for analysis.'))
C.push(P('An order was counted as flagged if the system blocked it (fail) or passed it with a warning for a person to check (warn). From this, the standard classification measures were calculated:'))
C.push(bullet([run('Accuracy', { bold: true }), run(': share of all orders the system judged correctly (erroneous orders flagged plus clean orders passed).')]))
C.push(bullet([run('Precision', { bold: true }), run(': of the orders the system flagged, the share that really contained an error.')]))
C.push(bullet([run('Recall (detection rate)', { bold: true }), run(': of the orders that contained an error, the share the system flagged.')]))
C.push(bullet([run('Specificity', { bold: true }), run(': of the clean orders, the share passed without a flag.')]))
C.push(bullet([run('F1 score', { bold: true }), run(': the harmonic mean of precision and recall.')]))

C.push(H1('4.5 Description of the Simulated Orders'))
C.push(P(`The ${m.run.orders} orders came from ${m.run.customers} companies, between ${d.orders_per_customer.min} and ${d.orders_per_customer.max} orders each (mean ${d.orders_per_customer.mean}). Orders had ${d.lines_mean} lines on average, and the total value of priced orders was ${naira(d.value_total)}. Table 4.7 summarises the dataset and Figure 4.1 shows how the orders were spread across delivery regions; the 22 orders with no region are those whose address was deliberately left empty.`))
C.push(...table('Summary of the simulated order dataset', ['Measure', 'Value'], [
  ['Orders submitted', String(m.run.orders)],
  ['Customer companies', String(m.run.customers)],
  ['Clean orders', `${m.groups.clean} (${pct((100 * m.groups.clean) / m.run.orders)})`],
  ['Orders with an error a rule targets', `${m.groups.targeted} (${pct((100 * m.groups.targeted) / m.run.orders)})`],
  ['Orders with an error no rule targets', `${m.groups.untargeted} (${pct((100 * m.groups.untargeted) / m.run.orders)})`],
  ['Average lines per order', String(d.lines_mean)],
  ['Average units per order', String(d.units_mean)],
  ['Order value: mean / median', `${naira(d.value_mean)} / ${naira(d.value_median)}`],
  ['Order value: smallest / largest', `${naira(d.value_min)} / ${naira(d.value_max)}`],
], [55, 45], { right: [1] }))
C.push(...figure('fig4_5_regions.png', 'Simulated orders by delivery region'))
C.push(P('Table 4.8 shows a sample of individual orders and how the system treated each; all 500 orders are listed in the accompanying workbook (Verity_Simulation_Data.xlsx, sheet "Orders").'))
const sampleKeys = ['clean', 'clean', 'bad_sku', 'missing_address', 'past_date', 'fractional_qty', 'over_stock', 'duplicate', 'inactive_product', 'qty_typo', 'wrong_product', 'wrong_address']
const used = new Set()
const sample = sampleKeys.map((k) => {
  const r = rows.find((x) => x.planted_error === k && !used.has(x.seq) && (k !== 'clean' || x.outcome === (used.has('c1') ? 'warn' : 'pass')))
  if (k === 'clean') used.add('c1')
  used.add(r.seq)
  return r
})
const outcomeWord = { pass: 'Passed', warn: 'Warned', fail: 'Blocked' }
C.push(...table('Sample of simulated orders and the system\'s decision', ['#', 'Company', 'Total', 'Planted error', 'Decision', 'Message shown (first)'],
  sample.map((r) => [String(r.seq), r.company, naira(r.total), cats[r.planted_error].label, outcomeWord[r.outcome], (r.messages[0] || '—').slice(0, 90)]),
  [6, 22, 15, 20, 10, 27], { size: 16, right: [2] }))

C.push(H1('4.6 Results'))
C.push(H2('4.6.1 Overall validation outcomes'))
const og = m.outcomes_by_group
C.push(P(`Of the ${m.run.orders} orders, ${m.outcomes.pass} passed, ${m.outcomes.warn} passed with a warning and ${m.outcomes.fail} were blocked. Figure 4.2 breaks this down by order group. Every order carrying a rule-targeted error was either blocked (${og['Errors with a rule'].fail}) or warned (${og['Errors with a rule'].warn}, all duplicates, which the design treats as a warning requiring confirmation). No clean order was blocked; ${og['Clean orders'].warn} clean orders (${pct((100 * og['Clean orders'].warn) / m.groups.clean)}) were passed with a warning. Of the orders carrying realistic mistakes that no rule targets, ${og['Errors without a rule'].pass} (${pct((100 * og['Errors without a rule'].pass) / m.groups.untargeted)}) passed unflagged.`))
C.push(...figure('fig4_1_outcomes.png', 'Validation outcome by order group'))

C.push(H2('4.6.2 Detection by error type'))
C.push(P('Table 4.9 and Figure 4.3 show the result for each planted error type. All ten error types that a rule was designed for were detected in every case (197 of 197 orders), and in every case by the rule intended for that error. The three error types with no rule were detected far less often, and only by coincidence: 13 wrong-product orders were blocked only because the quantity chosen fell outside the substituted product’s order limits, and most flagged quantity typos were caught by the unusual-quantity warning, which is a general check rather than a check for typos.'))
C.push(...table('Detection by planted error type', ['Error type', 'Rule?', 'Orders', 'Blocked', 'Warned', 'Passed', 'Detection'],
  m.categories.map((c) => [c.label, c.targeted ? 'Yes' : 'No', c.n, c.blocked, c.warned, c.passed,
    c.key === 'clean' ? `${pct(100 - c.pass_rate)} false alarm` : pct(c.detection_rate)]).map((r) => r.map(String)),
  [36, 8, 10, 10, 10, 10, 16], { size: 18, right: [2, 3, 4, 5, 6] }))
C.push(...figure('fig4_2_detection.png', 'Detection rate by planted error type'))

C.push(H2('4.6.3 Classification performance'))
C.push(P(`Table 4.10 presents the results as confusion matrices. Treating every planted error as something the system should catch, the system flagged ${cm.tp} of ${cm.tp + cm.fn} erroneous orders and passed ${cm.tn} of ${cm.tn + cm.fp} clean orders. When only the error types the rules were designed for are counted, recall rises to ${pct(ct.recall)}.`))
C.push(...table('Confusion matrices', ['Scope', '', 'Flagged by system', 'Passed by system', 'Total'], [
  ['All errors', 'Order had an error', String(cm.tp), String(cm.fn), String(cm.tp + cm.fn)],
  ['', 'Clean order', String(cm.fp), String(cm.tn), String(cm.fp + cm.tn)],
  ['Rule-targeted errors only', 'Order had an error', String(ct.tp), String(ct.fn), String(ct.tp + ct.fn)],
  ['', 'Clean order', String(ct.fp), String(ct.tn), String(ct.fp + ct.tn)],
], [26, 22, 18, 18, 16], { right: [2, 3, 4] }))
C.push(...table('Classification measures', ['Measure', 'All errors', 'Rule-targeted errors only'], [
  ['Accuracy', pct(cm.accuracy), pct(ct.accuracy)],
  ['Precision', pct(cm.precision), pct(ct.precision)],
  ['Recall (detection rate)', pct(cm.recall), pct(ct.recall)],
  ['Specificity', pct(cm.specificity), pct(ct.specificity)],
  ['F1 score', pct(cm.f1), pct(ct.f1)],
], [40, 30, 30], { right: [1, 2] }))
C.push(P(`Overall accuracy was ${pct(cm.accuracy)} when realistic mistakes outside the rules are included, and ${pct(ct.accuracy)} on the error types the rules cover. The difference is driven by two things: the ${m.groups.untargeted - (cm.tp - ct.tp)} realistic mistakes that passed unflagged, and the ${cm.fp} false alarms on clean orders.`))

C.push(H2('4.6.4 Rule activity and false alarms'))
const uq = m.rules.find((r) => r.rule === 'unusual_quantity')
C.push(P(`Figure 4.4 shows how often each rule fired. All blocking rules fired only on orders that really contained an error. The false alarms came almost entirely from the unusual-quantity warning, which fired on ${uq.total} orders, ${uq.on_clean} of them clean (${m.fp_reasons.unusual_quantity} of the ${cm.fp} false alarms). The rule compares each order with the customer's own average; because each simulated customer had a short history of small orders, larger but legitimate clean orders were flagged. Since this rule is a warning and not a block, these orders still reached the Ops Desk, where a person approves them; the cost of a false alarm is a short manual check, not a rejected order.`))
C.push(...figure('fig4_3_rules.png', 'Number of orders on which each validation rule fired'))

C.push(H2('4.6.5 Processing time'))
C.push(P(`The server took a mean of ${t.mean} ms (median ${t.median} ms) to validate an order, with 95% of orders validated within ${t.p95} ms and the slowest in ${t.max} ms (Table 4.12 and Figure 4.5). Blocked orders took slightly longer on average (${t.by_outcome.fail} ms) than passed orders (${t.by_outcome.pass} ms), because more rule messages were produced. These figures cover validation inside the database only; they exclude network time between the user and the server.`))
C.push(...table('Server validation time per order', ['Statistic', 'Milliseconds'], [
  ['Mean', String(t.mean)], ['Median', String(t.median)], ['95th percentile', String(t.p95)], ['Minimum', String(t.min)], ['Maximum', String(t.max)],
  ['Standard deviation', String(t.sd)], ['Mean, passed orders', String(t.by_outcome.pass)], ['Mean, warned orders', String(t.by_outcome.warn)], ['Mean, blocked orders', String(t.by_outcome.fail)],
], [60, 40], { right: [1] }))
C.push(...figure('fig4_4_timing.png', 'Distribution of server validation time per order'))

C.push(H1('4.7 Evaluation Against the Success Criteria'))
C.push(P('Table 4.13 compares the results with the success criteria set for the project.'))
C.push(...table('Success criteria and measured results', ['Objective', 'Criterion', 'Result', 'Status'], [
  ['Build a digital order-processing system', '500 successful simulated orders', `${m.run.orders} orders processed through the live system`, 'Met'],
  ['Validate orders automatically', '90% validation accuracy', `${pct(cm.accuracy)} on all orders; ${pct(ct.accuracy)} on rule-targeted errors`, 'Partly met'],
  ['Reduce manual data-entry errors', '100% mandatory-field completion', `${m.mandatory.complete} of ${m.mandatory.passed_orders} orders that passed validation (${pct(m.mandatory.pct)}) had every mandatory field`, 'Met'],
  ['Reduce manual data-entry errors', '60% reduction in manual errors', `Requires manual baseline; indicatively the system flagged ${pct(cm.recall)} of erroneous orders before approval`, 'Pending'],
  ['Improve processing speed', '30–50% faster processing', `Automatic validation median ${t.median} ms; end-to-end comparison requires manual baseline`, 'Pending'],
], [24, 22, 40, 14]))
C.push(P('Two criteria were met in full. The accuracy criterion was met for the errors the validation rules are designed to detect but not when realistic mistakes outside the rules are included; this distinction is reported rather than hidden because it reflects how the system would behave with real customers. The error-reduction and speed criteria compare the system with the current manual process and cannot be established by simulation alone: they require timing people as they re-key a sample of real orders from Excel, e-mail and WhatsApp, and counting their errors. A template for recording this baseline is provided in the accompanying workbook (sheet "Manual baseline").'))

C.push(H1('4.8 Discussion'))
C.push(P('The results show that rule-based validation is highly reliable for the errors it is designed to catch: every missing field, invalid product, impossible quantity, stock shortfall, past date and duplicate was stopped or flagged, and in each case the customer was told the exact problem. Because these checks run inside the database and not only in the browser, they cannot be bypassed by an unusual client or a direct database call, and no order missing a mandatory field reached approval.'))
C.push(P('The simulation also shows the limit of the approach. A validation rule can only judge whether an order is possible, not whether it is what the customer intended. A neighbouring product, a plausible quantity typo or the wrong one of two valid addresses all produce valid orders, and most passed unflagged. Reducing these errors needs different measures: showing product images and recent orders during entry, asking the customer to confirm quantities that differ sharply from their history, and making the delivery address prominent on the confirmation screen.'))
C.push(P('The unusual-quantity warning illustrates the trade-off between catching errors and creating extra work. It flagged most of the quantity typos it could see, but also produced most of the false alarms. Raising its threshold, or applying it only after a customer has a longer order history, would reduce false alarms at the cost of missing some typos; this setting can be changed by the administrator without changing the code.'))

C.push(H1('4.9 Limitations of the Evaluation'))
C.push(bullet('The orders and customers were simulated; real customers may make different mistakes, and in different proportions, from those planted here.'))
C.push(bullet('Each simulated customer had a short, uniform order history, which made the unusual-quantity warning more sensitive than it would be with real histories.'))
C.push(bullet('Processing time was measured inside the database; it does not include network delay or the time a person spends filling in the form.'))
C.push(bullet('The error-reduction and speed criteria could not be tested without a manual baseline from the case organisation.'))
C.push(bullet('The evaluation covers one run with a fixed seed; repeated runs with different seeds would show how much the results vary.'))

C.push(H1('4.10 Summary'))
C.push(P(`The implemented system processed all ${m.run.orders} simulated orders and enforced its rules at the database level for every role. It detected every one of the 197 rule-targeted errors, gave no false blocks, and validated orders in about ${Math.round(t.median)} ms each. Overall accuracy was ${pct(cm.accuracy)} including realistic mistakes outside its rules and ${pct(ct.accuracy)} on the errors it was designed to detect. The mandatory-field criterion was met in full; the error-reduction and speed criteria await a manual baseline from the case organisation.`))

// ------------------------------------------------------------------ document
const doc = new Document({
  creator: 'Verity project',
  title: 'Chapter Four: System Implementation, Testing and Results',
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    // dissertation style: black headings in the body font, kept as Word headings so they appear in a table of contents
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 28, bold: true, color: '000000' }, paragraph: { outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 24, bold: true, color: '000000' }, paragraph: { outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 24, bold: true, italics: true, color: '000000' }, paragraph: { outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })] })] }) },
    children: C,
  }],
})
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(HERE, 'Chapter4_Technical_Evaluation.docx'), buf)
  console.log('tables', tableNo, 'figures', figNo)
})
