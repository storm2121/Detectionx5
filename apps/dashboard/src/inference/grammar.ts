import exported from './grammar.json'

/**
 * The plate automaton, exported from plate_reader/grammar.py by `plate export web` (a
 * Python test fails if this copy drifts from the grammar). States are integers, DEAD (-1)
 * is the rejecting sink, transitions are indexed by symbol index.
 */
export interface GrammarExport {
  schema: string
  symbols: string[]
  start: number
  dead: number
  transitions: number[][]
  accepting: string[][]
  charset: string[]
  charset_id: string
}

export const GRAMMAR = exported as GrammarExport
export const DEAD = GRAMMAR.dead
export const SYMBOLS = GRAMMAR.symbols
export const SYMBOL_INDEX = new Map(SYMBOLS.map((symbol, index) => [symbol, index]))
export const SEPARATOR = '-'

export function step(state: number, symbolIndex: number): number {
  if (state === DEAD) return DEAD
  return GRAMMAR.transitions[state]?.[symbolIndex] ?? DEAD
}

export function run(tokens: string, state: number = GRAMMAR.start): number {
  let current = state
  for (const symbol of tokens) {
    const index = SYMBOL_INDEX.get(symbol)
    if (index === undefined) return DEAD
    current = step(current, index)
    if (current === DEAD) return DEAD
  }
  return current
}

export function isAccepting(state: number): boolean {
  return state !== DEAD && (GRAMMAR.accepting[state]?.length ?? 0) > 0
}

export function accepts(tokens: string): boolean {
  return isAccepting(run(tokens))
}

/** The format of an accepted token string (the smallest name, as in Python). */
export function formatOf(tokens: string): string | null {
  const state = run(tokens)
  if (!isAccepting(state)) return null
  const names = [...(GRAMMAR.accepting[state] ?? [])].sort()
  return names[0] ?? null
}

/** Display spelling: temporary plates read `72173 WW`, standard ones keep their dashes. */
export function toDisplay(tokens: string): string {
  return formatOf(tokens) === 'temporary' ? tokens.replace(`${SEPARATOR}WW`, ' WW') : tokens
}

export interface PlateFieldsOf {
  digits: string
  letter: string | null
  region: string | null
}

export function fieldsOf(tokens: string): PlateFieldsOf | null {
  const format = formatOf(tokens)
  if (!format) return null
  const parts = tokens.split(SEPARATOR)
  if (format === 'temporary') return { digits: parts[0] ?? '', letter: null, region: null }
  return { digits: parts[0] ?? '', letter: parts[1] ?? null, region: parts[2] ?? null }
}
