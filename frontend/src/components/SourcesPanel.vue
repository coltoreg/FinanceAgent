<template>
  <div class="space-y-6 text-sm">
    <!-- Data Source Badges -->
    <section>
      <h3 class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        Data Sources
      </h3>
      <div class="flex flex-wrap gap-2">
        <a
          v-for="src in normalizedSources"
          :key="src.label"
          :href="src.url || undefined"
          :target="src.url ? '_blank' : undefined"
          :rel="src.url ? 'noopener noreferrer' : undefined"
          :class="[
            'inline-flex items-center gap-2 px-3 py-1.5 rounded border text-xs font-medium transition-colors',
            src.url
              ? 'border-cyan-700/50 bg-cyan-900/20 text-cyan-400 hover:bg-cyan-900/40 cursor-pointer'
              : 'border-gray-700 bg-gray-800/50 text-gray-400 cursor-default',
          ]"
        >
          <component :is="src.icon" class="w-3.5 h-3.5 shrink-0" />
          <span>{{ src.label }}</span>
          <svg v-if="src.url" class="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>

        <!-- SEC EDGAR Company page link (if CIK available) -->
        <a
          v-if="cik"
          :href="`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=10-K&dateb=&owner=include&count=10`"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 px-3 py-1.5 rounded border border-cyan-700/50
                 bg-cyan-900/20 text-cyan-400 hover:bg-cyan-900/40 text-xs font-medium transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>SEC EDGAR Filings (CIK {{ cik }})</span>
          <svg class="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>

        <!-- SEC XBRL facts link -->
        <a
          v-if="cik"
          :href="`https://data.sec.gov/api/xbrl/companyfacts/CIK${cik}.json`"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 px-3 py-1.5 rounded border border-gray-700
                 bg-gray-800/50 text-gray-400 hover:bg-gray-700/50 text-xs font-medium transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582 4 8 4s8 1.79 8 4" />
          </svg>
          <span>XBRL Raw Data (JSON)</span>
          <svg class="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      </div>
    </section>

    <!-- RAG Retrieved Documents -->
    <section v-if="sources && sources.length">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-2">
        RAG Retrieved Documents
        <span class="text-gray-600 font-normal normal-case text-xs">
          (Hybrid Search: ChromaDB + BM25 + RRF)
        </span>
      </h3>

      <div class="space-y-2">
        <div
          v-for="(src, idx) in sources"
          :key="src.id + idx"
          class="bg-gray-800/60 border border-gray-700/50 rounded-lg p-3 space-y-2"
        >
          <!-- Doc header -->
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-2 flex-wrap">
              <!-- Type badge -->
              <span :class="docTypeBadgeClass(src.id)">
                {{ docTypeLabel(src.id) }}
              </span>
              <!-- Doc ID -->
              <span class="text-gray-300 font-medium text-xs font-mono">
                {{ src.id }}
              </span>
            </div>
            <!-- RRF Score -->
            <div class="flex items-center gap-1.5 shrink-0">
              <div class="flex gap-0.5">
                <div
                  v-for="i in 5"
                  :key="i"
                  :class="['w-1.5 h-3 rounded-sm', scoreBarFill(src.score, i)]"
                />
              </div>
              <span class="text-xs text-gray-500 tabular-nums">
                {{ src.score.toFixed(4) }}
              </span>
            </div>
          </div>

          <!-- Content preview -->
          <p class="text-xs text-gray-400 leading-relaxed line-clamp-2">
            {{ src.content || '(no preview)' }}
          </p>

          <!-- Query tag + SEC link -->
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-1.5">
              <svg class="w-3 h-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span class="text-xs text-gray-500 italic">{{ src.query }}</span>
            </div>

            <!-- Link to SEC filing if it's a filing doc -->
            <a
              v-if="isFilingDoc(src.id) && cik"
              :href="`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=10-K&dateb=${filingDate(src.id)}&owner=include&count=1`"
              target="_blank"
              rel="noopener noreferrer"
              class="text-xs text-cyan-500 hover:text-cyan-400 flex items-center gap-1 transition-colors"
            >
              View on EDGAR
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>

            <!-- Link to XBRL concept if it's a metric doc -->
            <a
              v-else-if="isMetricDoc(src.id) && cik"
              :href="`https://data.sec.gov/api/xbrl/companyfacts/CIK${cik}.json`"
              target="_blank"
              rel="noopener noreferrer"
              class="text-xs text-gray-500 hover:text-gray-400 flex items-center gap-1 transition-colors"
            >
              XBRL Data
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="mt-3 flex flex-wrap gap-3 text-xs text-gray-600">
        <span class="flex items-center gap-1">
          <span class="w-2 h-2 rounded-full bg-blue-600 inline-block"></span>
          SEC 10-K Filing
        </span>
        <span class="flex items-center gap-1">
          <span class="w-2 h-2 rounded-full bg-cyan-600 inline-block"></span>
          XBRL Financial Metric
        </span>
        <span class="flex items-center gap-1.5 ml-2">Score bar: RRF fusion relevance</span>
      </div>
    </section>

    <div v-else-if="!sources || sources.length === 0" class="text-gray-600 text-xs">
      No RAG retrieval sources available. Sources are populated after a successful analysis.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import type { RagSource } from '@/stores/analysis'

const props = defineProps<{
  sources: RagSource[]
  dataSources: string[]
  cik: string
  ticker: string
}>()

// ── Data source badge normalization ─────────────────────────────────────────

const DbIcon = { render: () => h('svg', { class: 'w-3.5 h-3.5', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582 4 8 4s8 1.79 8 4' })
]) }

const ChartIcon = { render: () => h('svg', { class: 'w-3.5 h-3.5', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' })
]) }

const BrainIcon = { render: () => h('svg', { class: 'w-3.5 h-3.5', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' })
]) }

const SOURCE_CONFIG: Record<string, { label: string; icon: any; url?: string }> = {
  'SEC EDGAR XBRL': {
    label: 'SEC EDGAR XBRL',
    icon: DbIcon,
    url: 'https://www.sec.gov/cgi-bin/browse-edgar',
  },
  'Hybrid RAG (ChromaDB + BM25)': {
    label: 'Hybrid RAG',
    icon: DbIcon,
  },
  yfinance: {
    label: 'yfinance (Yahoo Finance)',
    icon: ChartIcon,
    url: 'https://finance.yahoo.com',
  },
  'Claude AI': {
    label: 'Claude AI (Sentiment)',
    icon: BrainIcon,
  },
}

const normalizedSources = computed(() =>
  (props.dataSources ?? []).map((s) => SOURCE_CONFIG[s] ?? { label: s, icon: DbIcon })
)

// ── Doc ID parsing helpers ───────────────────────────────────────────────────

// Filing doc pattern: NVDA_2024-01-29_10-K
const FILING_RE = /^([A-Z]+)_(\d{4}-\d{2}-\d{2})_(10-[KQ])$/

// Metric doc pattern: NVDA_revenue
const METRIC_RE = /^([A-Z]+)_([a-z_]+)$/

function isFilingDoc(id: string): boolean {
  return FILING_RE.test(id)
}

function isMetricDoc(id: string): boolean {
  return METRIC_RE.test(id) && !FILING_RE.test(id)
}

function filingDate(id: string): string {
  const m = id.match(FILING_RE)
  return m ? m[2].replace(/-/g, '') : ''
}

function docTypeLabel(id: string): string {
  if (FILING_RE.test(id)) {
    const m = id.match(FILING_RE)
    return m ? `SEC ${m[3]}` : 'SEC Filing'
  }
  if (METRIC_RE.test(id)) {
    const m = id.match(METRIC_RE)
    return m ? 'XBRL Metric' : 'Metric'
  }
  return 'Document'
}

function docTypeBadgeClass(id: string): string {
  if (FILING_RE.test(id)) {
    return 'text-xs px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-400 border border-blue-700/50 font-medium'
  }
  return 'text-xs px-1.5 py-0.5 rounded bg-cyan-900/40 text-cyan-400 border border-cyan-700/50 font-medium'
}

// ── Score bar helpers ────────────────────────────────────────────────────────

// scores are small RRF numbers (~0.01–0.03); normalize to 0–1 across local max
const maxScore = computed(() => {
  const scores = (props.sources ?? []).map((s) => s.score)
  return scores.length ? Math.max(...scores) : 1
})

function scoreBarFill(score: number, barIdx: number): string {
  const normalized = maxScore.value > 0 ? score / maxScore.value : 0
  const filled = normalized >= barIdx / 5
  return filled ? 'bg-cyan-500' : 'bg-gray-700'
}
</script>
