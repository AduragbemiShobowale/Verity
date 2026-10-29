// Screenshots each figures/*.html to a 2x PNG for Word.
// Run: NODE_PATH=$(npm root -g) node render.mjs
import { readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const dir = join(dirname(fileURLToPath(import.meta.url)), 'figures')
const b = await chromium.launch()
const p = await b.newPage({ deviceScaleFactor: 2 })
for (const f of readdirSync(dir).filter((x) => x.endsWith('.html'))) {
  await p.goto('file://' + join(dir, f))
  const svg = await p.$('svg')
  await svg.screenshot({ path: join(dir, f.replace('.html', '.png')) })
  console.log('rendered', f)
}
await b.close()
