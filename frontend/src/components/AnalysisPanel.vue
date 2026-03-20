<template>
  <div class="card flex flex-col min-h-0">
    <!-- Header: ticker + rating + chat button -->
    <div class="flex items-center justify-between px-4 pt-3 pb-2 border-b border-gray-700">
      <div class="flex items-center gap-3">
        <span class="text-cyan-400 font-bold text-base tracking-wider">{{ state.ticker }}</span>
        <span v-if="rating" :class="ratingClass">{{ rating }}</span>
        <span v-if="fundScore" :class="fundScoreClass" class="text-xs">{{ fundScore }}</span>
      </div>
      <div v-if="state.status === 'complete'" class="flex items-center gap-2">
        <!-- PDF Export -->
        <button
          :disabled="exporting !== null"
          class="text-xs text-rose-400 hover:text-rose-300 border border-rose-800 hover:border-rose-600
                 px-2.5 py-1 rounded transition-colors flex items-center gap-1 disabled:opacity-40"
          :title="exporting === 'pdf' ? 'Generating PDF…' : 'Download PDF report'"
          @click="handleExport('pdf')"
        >
          <svg v-if="exporting === 'pdf'" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <svg v-else class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
          PDF
        </button>

        <!-- Excel Export -->
        <button
          :disabled="exporting !== null"
          class="text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800 hover:border-emerald-600
                 px-2.5 py-1 rounded transition-colors flex items-center gap-1 disabled:opacity-40"
          :title="exporting === 'excel' ? 'Generating Excel…' : 'Download Excel workbook'"
          @click="handleExport('excel')"
        >
          <svg v-if="exporting === 'excel'" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <svg v-else class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 10h18M3 14h18M10 3v18M14 3v18M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z" />
          </svg>
          Excel
        </button>

        <!-- Ask AI -->
        <button
          class="text-xs text-cyan-400 hover:text-cyan-300 border border-cyan-700 hover:border-cyan-500
                 px-3 py-1 rounded transition-colors flex items-center gap-1.5"
          @click="emit('open-chat')"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z" />
          </svg>
          Ask AI
        </button>
      </div>
    </div>

    <!-- Live market data bar (shown once complete) -->
    <MarketDataBar
      v-if="state.result?.live_price"
      :quote="state.result.live_price"
    />

    <!-- Tab bar -->
    <div class="flex border-b border-gray-700 px-4 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn shrink-0', activeTab === tab.key ? 'active' : '']"
        @click="activeTab = tab.key"
      >
        <span>{{ tab.label }}</span>
        <!-- News count badge -->
        <span
          v-if="tab.key === 'news' && newsCount > 0"
          class="ml-1.5 text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded-full"
        >
          {{ newsCount }}
        </span>
      </button>
    </div>

    <!-- Tab content -->
    <div class="flex-1 overflow-y-auto p-4 min-h-0">
      <!-- Loading state -->
      <div v-if="state.status === 'running'" class="flex flex-col items-center justify-center py-16 gap-4">
        <svg class="animate-spin w-8 h-8 text-cyan-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span class="text-gray-400 text-sm">{{ state.currentLabel }}</span>
      </div>

      <!-- Error state -->
      <div v-else-if="state.status === 'error'" class="p-4 bg-red-900/20 border border-red-700/50 rounded text-red-400 text-sm">
        <p class="font-semibold mb-1">Analysis failed</p>
        <p class="text-xs text-red-300/80">{{ state.error }}</p>
      </div>

      <!-- Idle state -->
      <div v-else-if="state.status === 'idle'" class="flex items-center justify-center py-16 text-gray-600 text-sm">
        Enter a ticker and click "Run Analysis"
      </div>

      <!-- Report tab -->
      <template v-else-if="activeTab === 'report' && state.result">
        <div class="prose-finance" v-html="renderedReport" />
      </template>

      <!-- Financials tab -->
      <template v-else-if="activeTab === 'financials' && state.result">
        <FinancialTables :statements="state.result.financial_statements" />
      </template>

      <!-- Valuation tab -->
      <template v-else-if="activeTab === 'valuation' && state.result">
        <ValuationPanel
          :valuation-data="state.result.valuation_data ?? {}"
          :valuation-analysis="state.result.valuation_analysis ?? ''"
        />
      </template>

      <!-- Peers tab -->
      <template v-else-if="activeTab === 'peers' && state.result">
        <PeerComparisonPanel
          :peer-data="state.result.peer_data ?? {}"
          :peer-analysis="state.result.peer_analysis ?? ''"
          :ticker="state.ticker"
        />
      </template>

      <!-- Debate tab -->
      <template v-else-if="activeTab === 'debate' && state.result">
        <DebateTranscript :transcript="state.result.debate_transcript" />
      </template>

      <!-- News tab -->
      <template v-else-if="activeTab === 'news' && state.result">
        <NewsFeed
          :news="state.result.news_items ?? []"
          :ticker="state.ticker"
          :fetched-at="state.result.live_price?.fetched_at"
        />
      </template>

      <!-- Sources tab -->
      <template v-else-if="activeTab === 'sources' && state.result">
        <SourcesPanel
          :sources="state.result.rag_sources ?? []"
          :data-sources="state.result.data_sources ?? []"
          :cik="state.result.ticker_cik ?? ''"
          :ticker="state.ticker"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import type { TickerState } from '@/stores/analysis'
import { exportReport } from '@/api/client'
import FinancialTables from './FinancialTables.vue'
import ValuationPanel from './ValuationPanel.vue'
import PeerComparisonPanel from './PeerComparisonPanel.vue'
import DebateTranscript from './DebateTranscript.vue'
import SourcesPanel from './SourcesPanel.vue'
import MarketDataBar from './MarketDataBar.vue'
import NewsFeed from './NewsFeed.vue'

const props = defineProps<{
  state: TickerState
}>()

const emit = defineEmits<{
  (e: 'open-chat'): void
}>()

const tabs = [
  { key: 'report', label: 'Report' },
  { key: 'financials', label: 'Financials' },
  { key: 'valuation', label: 'Valuation' },
  { key: 'peers', label: 'Peers' },
  { key: 'debate', label: 'Debate' },
  { key: 'news', label: 'News' },
  { key: 'sources', label: 'Sources' },
]

const activeTab = ref('report')
const exporting = ref<'pdf' | 'excel' | null>(null)

async function handleExport(format: 'pdf' | 'excel') {
  if (!props.state.result || exporting.value !== null) return
  exporting.value = format
  try {
    await exportReport(format, props.state.result as Record<string, any>)
  } catch (err) {
    console.error('Export failed:', err)
  } finally {
    exporting.value = null
  }
}

const newsCount = computed(() => props.state.result?.news_items?.length ?? 0)

const renderedReport = computed(() => {
  const text = props.state.result?.final_report ?? ''
  return marked.parse(text) as string
})

const rating = computed(() => {
  const stmt = props.state.result?.financial_statements
  if (stmt?.investment_rating) return stmt.investment_rating
  return _extractRating(props.state.result?.final_report ?? '')
})

const fundScore = computed(() => props.state.result?.financial_statements?.fundamental_score ?? '')

const ratingClass = computed(() => {
  const r = rating.value?.toUpperCase() ?? ''
  if (r.includes('STRONG BUY') || r === 'BUY') return 'badge-buy'
  if (r.includes('SELL')) return 'badge-sell'
  return 'badge-hold'
})

const fundScoreClass = computed(() => {
  const s = fundScore.value?.toUpperCase()
  if (s === 'STRONG') return 'text-emerald-400'
  if (s === 'WEAK') return 'text-red-400'
  return 'text-yellow-400'
})

function _extractRating(text: string): string {
  const m = text.match(/\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD)\b/i)
  return m ? m[1].toUpperCase() : ''
}
</script>
