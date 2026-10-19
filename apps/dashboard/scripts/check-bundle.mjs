// The bundle check, run after `vite build`: what a first visit downloads (the entry script,
// the modules it preloads and its stylesheets, gzipped) stays inside a budget, and no
// component library comes back into the bundle (ADR 0012). The budgets sit below what the
// console shipped before its redesign (about 121 kB of script and 5 kB of styles, gzipped),
// so the design system cannot quietly grow the first load.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const BUDGET_KB = { js: 110, css: 10 }
const FORBIDDEN = [/primevue/i, /@primeuix/i]

const here = dirname(fileURLToPath(import.meta.url))
const dist = join(here, '..', 'dist')
const index = join(dist, 'index.html')
if (!existsSync(index)) {
    console.error('check-bundle: dist/index.html is missing; run vite build first')
    process.exit(1)
}

const html = readFileSync(index, 'utf-8')
const initial = new Set()
for (const match of html.matchAll(/<(?:script|link)[^>]+(?:src|href)="\/?(assets\/[^"]+)"/g)) {
    initial.add(match[1])
}

const kb = (bytes) => Math.round((bytes / 1024) * 10) / 10
const totals = { js: 0, css: 0 }
for (const asset of initial) {
    const kind = asset.endsWith('.css') ? 'css' : asset.endsWith('.js') ? 'js' : null
    if (!kind) continue
    totals[kind] += gzipSync(readFileSync(join(dist, asset))).length
}

const problems = []
for (const kind of ['js', 'css']) {
    const size = kb(totals[kind])
    console.log(
        `check-bundle: first load ${kind} ${size} kB gzipped (budget ${BUDGET_KB[kind]} kB)`,
    )
    if (size > BUDGET_KB[kind])
        problems.push(`${kind} over budget: ${size} kB > ${BUDGET_KB[kind]} kB`)
}

for (const name of readdirSync(join(dist, 'assets'))) {
    if (!/\.(js|css)$/.test(name)) continue
    const text = readFileSync(join(dist, 'assets', name), 'utf-8')
    for (const pattern of FORBIDDEN) {
        if (pattern.test(text)) problems.push(`${name} contains ${pattern}`)
    }
}

if (problems.length) {
    for (const problem of problems) console.error(`check-bundle: ${problem}`)
    process.exit(1)
}
console.log('check-bundle: within budget, no component library in the bundle')
