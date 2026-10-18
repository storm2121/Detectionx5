/** Human names for the identifiers the results files and the service use. */

export const RECOGNIZER_LABELS: Record<string, string> = {
  easyocr: 'EasyOCR (baseline)',
  'crnn-greedy': 'CRNN, greedy',
  'crnn-beam': 'CRNN, constrained beam',
  'crnn-beam-unconstrained': 'CRNN, unconstrained beam',
}

export const FUSION_LABELS: Record<string, string> = {
  legacy_vote: 'Legacy vote',
  probabilistic: 'Product of posteriors',
  probabilistic_weighted: 'Weighted product',
}

export const SET_LABELS: Record<string, string> = {
  eval_synthetic: 'Synthetic test set',
  eval_pseudo_real: 'Pseudo-real set',
  eval_views: 'Multi-view sets',
}

export function recognizerLabel(name: string): string {
  return RECOGNIZER_LABELS[name] ?? name
}

export function fusionLabel(name: string): string {
  return FUSION_LABELS[name] ?? name.replace(/_/g, ' ')
}

export function setLabel(name: string): string {
  return SET_LABELS[name] ?? name.replace(/^eval_/, '').replace(/_/g, ' ')
}
