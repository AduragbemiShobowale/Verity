// Runs the application's own upload parser (src/lib/upload.js) on the sample CSV
// and writes the save_draft payload it would send.
import { readFileSync, writeFileSync } from 'node:fs'
import { parseCsv, rowsToOrder } from '../../../src/lib/upload.js'
const catalogue = JSON.parse(readFileSync(new URL('./catalogue_ids.json', import.meta.url)))
const rows = parseCsv(readFileSync(new URL('./sample_import_old_price.csv', import.meta.url), 'utf8'))
const out = rowsToOrder(rows, catalogue)
writeFileSync(new URL('./import_parser_output.json', import.meta.url), JSON.stringify({ rows, out }, null, 1))
console.log(JSON.stringify(out))
