import { ChartColumn, Inbox, Layers, Package, ScanText, Sigma } from '@lucide/vue'
import type { Component } from 'vue'

import type { ReviewSummary } from '@/api/types'

/**
 * The console's pages, in reading order. Read is the home and the first item; each other
 * page is one click away and says what it holds. No "Home", no "Dashboard".
 */
export interface NavItem {
  to: string
  /** The name in the top bar and on the page. */
  label: string
  /** The shorter name under the icon in the phone's tab bar. */
  short: string
  icon: Component
}

export function reviewLabel(summary: ReviewSummary | null): string {
  if (!summary) return 'Review queue'
  if (summary.pending === 0) return 'Review queue (none waiting)'
  return `Review queue (${summary.pending} waiting)`
}

export function navItems(summary: ReviewSummary | null): NavItem[] {
  return [
    { to: '/read', label: 'Read', short: 'Read', icon: ScanText },
    { to: '/review', label: reviewLabel(summary), short: 'Review', icon: Inbox },
    { to: '/jobs', label: 'Jobs', short: 'Jobs', icon: Layers },
    { to: '/evaluation', label: 'Evaluation', short: 'Evaluation', icon: ChartColumn },
    { to: '/models', label: 'Models', short: 'Models', icon: Package },
    { to: '/methods', label: 'Methods', short: 'Methods', icon: Sigma },
  ]
}
