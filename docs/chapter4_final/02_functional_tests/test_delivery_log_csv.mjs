// Case 20b: delivery log CSV export. Takes the head and line-building code verbatim from
// src/pages/dispatch/DispatchPages.jsx (DeliveryLog csv()) and applies it to the rows that
// delivery_log() returned for dispatch@verity.example (delivery_log_rows_dispatch.json).
// The Blob download itself was not exercised: the live site is not reachable from the test container.
import { readFileSync, writeFileSync } from 'node:fs'
const src = readFileSync(new URL('../../../src/pages/dispatch/DispatchPages.jsx', import.meta.url), 'utf8')
const body = src.match(/const csv = \(\) => \{\n([\s\S]*?)\n\s*const url =/)[1]
const rows = JSON.parse(readFileSync(new URL('./delivery_log_rows_dispatch.json', import.meta.url)))
const text = new Function('rows', body + '\nreturn [head.join(\',\'), ...lines].join(\'\\n\')')(rows)
writeFileSync(new URL('./exported_delivery_log.csv', import.meta.url), text)
const back = text.split('\n')
console.log(JSON.stringify({ header_columns: back[0].split(',').length, data_lines: back.length - 1, rows_in: rows.length }))
console.log(text)
