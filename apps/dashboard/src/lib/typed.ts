import { fieldsOf, formatOf, toDisplay } from '@/inference/grammar'

import { LETTERS } from './plate'

/**
 * A plate as a person types it, judged by the plate automaton while they type, so a
 * correction is validated inline instead of on submit. The spelling is forgiving the way the
 * service's parser is: any separator, no separator, Arabic-Indic digits, a lower-case `ww`.
 * The service still parses the submitted text itself and has the last word.
 */
export interface TypedPlate {
  tokens: string
  valid: boolean
  display: string | null
  message: string
}

const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'
const EXTENDED_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
/**
 * A plate inside running text keeps its token order: a left-to-right override around it
 * (the same reason the plate class overrides bidi), since plain bidi would show 24830-1-ب.
 */
export function ltrPlate(plate: string): string {
  return `\u202D${plate}\u202C`
}

const EXAMPLE = ltrPlate('24830-ب-1')

function kind(char: string): 'digit' | 'letter' | 'mark' | 'other' {
  if (/[0-9]/.test(char)) return 'digit'
  if ((LETTERS as readonly string[]).includes(char)) return 'letter'
  if (char === 'W') return 'mark'
  return 'other'
}

export function toTokens(input: string): string {
  let text = ''
  for (const char of input.trim()) {
    const a = ARABIC_DIGITS.indexOf(char)
    const e = EXTENDED_DIGITS.indexOf(char)
    if (a >= 0) text += String(a)
    else if (e >= 0) text += String(e)
    else if (char === 'w') text += 'W'
    else if (/[\s|_/\\.·•–—−-]/.test(char)) text += '-'
    else text += char
  }
  // without separators, cut where digits meet a letter or the WW mark
  if (!text.includes('-')) {
    let out = ''
    for (const char of text) {
      const last = out[out.length - 1]
      if (last !== undefined && kind(last) !== kind(char) && kind(char) !== 'other') out += '-'
      out += char
    }
    text = out
  }
  return text.replace(/-+/g, '-').replace(/^-|-$/g, '')
}

export function judgePlate(input: string): TypedPlate {
  const tokens = toTokens(input)
  if (!tokens) {
    return {
      tokens,
      valid: false,
      display: null,
      message: `Type the plate, for example ${EXAMPLE}.`,
    }
  }
  const format = formatOf(tokens)
  const fields = fieldsOf(tokens)
  if (!format || !fields) {
    return {
      tokens,
      valid: false,
      display: null,
      message: `Not a plate yet: digits, one of the six letters, then the region, as in ${EXAMPLE}; or digits then WW.`,
    }
  }
  const display = toDisplay(tokens)
  const message =
    format === 'temporary'
      ? `Reads as a temporary plate: digits ${fields.digits}, mark WW.`
      : `Reads as a standard plate: digits ${fields.digits}, letter ${fields.letter ?? ''}, region ${fields.region ?? ''}.`
  return { tokens, valid: true, display, message }
}
