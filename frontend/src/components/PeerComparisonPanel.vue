<template>
  <div class="space-y-4">
    <!-- Empty state -->
    <div v-if="!hasPeerData" class="py-12 text-center text-gray-500 text-sm">
      No peer comparison data available.
    </div>

    <template v-else>
      <!-- Competitive Position Badge -->
      <div class="rounded-lg border p-4 flex items-start gap-4" :class="positionBorderClass">
        <div>
          <span class="text-xs font-semibold uppercase tracking-wider px-2 py-1 rounded"
            :class="positionBadgeClass">
            {{ analysis.overall_position?.replace('_', ' ') ?? 'N/A' }}
          </span>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm text-gray-300">{{ analysis.key_differentiator }}</p>
          <div class="flex flex-wrap gap-2 mt-2">
            <span class="text-xs px-2 py-0.5 rounded" :class="valuationBadgeClass">
              Valuation: {{ analysis.valuation_vs_peers?.replace('_', ' ') ?? 'N/A' }}
            </span>
            <span class="text-xs px-2 py-0.5 rounded" :class="growthBadgeClass">
              Growth: {{ analysis.growth_vs_peers?.replace('_', ' ') ?? 'N/A' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Comparison Table -->
      <div class="overflow-x-auto rounded-lg border border-gray-700">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-gray-700 bg-gray-800/60">
              <th class="text-left px-3 py-2 text-gray-400 font-medium">Ticker</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">P/E</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">Fwd P/E</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">Net Margin</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">Rev Growth</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">D/E</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">Market Cap</th>
              <th class="text-right px-3 py-2 text-gray-400 font-medium">Analyst Target</th>
            </tr>
          </thead>
          <tbody>
            <!-- Target company row (highlighted) -->
            <tr v-if="targetCompany" class="border-b border-gray-700/50 bg-cyan-900/20">
              <td class="px-3 py-2 font-semibold text-cyan-400">
                ★ {{ targetCompany.ticker }}
                <span class="text-gray-500 font-normal ml-1 truncate max-w-[120px] inline-block align-middle text-xs">
                  {{ targetCompany.name }}
                </span>
              </td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmt(targetCompany.pe_trailing, 1) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmt(targetCompany.pe_forward, 1) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmtPct(targetCompany.net_margin_pct) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmtPct(targetCompany.revenue_growth_yoy_pct) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmt(targetCompany.debt_to_equity, 2) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmtBn(targetCompany.market_cap_billions) }}</td>
              <td class="text-right px-3 py-2 text-gray-200">{{ fmtDollar(targetCompany.analyst_target) }}</td>
            </tr>
            <!-- Peer rows -->
            <tr
              v-for="peer in peers"
              :key="peer.ticker"
              class="border-b border-gray-700/30 hover:bg-gray-700/20 transition-colors"
            >
              <td class="px-3 py-2 text-gray-300">
                {{ peer.ticker }}
                <span class="text-gray-500 ml-1 truncate max-w-[120px] inline-block align-middle text-xs">
                  {{ peer.name }}
                </span>
              </td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmt(peer.pe_trailing, 1) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmt(peer.pe_forward, 1) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmtPct(peer.net_margin_pct) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmtPct(peer.revenue_growth_yoy_pct) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmt(peer.debt_to_equity, 2) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmtBn(peer.market_cap_billions) }}</td>
              <td class="text-right px-3 py-2 text-gray-400">{{ fmtDollar(peer.analyst_target) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Strengths & Weaknesses -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <!-- Strengths -->
        <div class="rounded-lg border border-emerald-700/40 bg-emerald-900/10 p-3">
          <p class="text-xs font-semibold text-emerald-400 mb-2">✅ Strengths</p>
          <ul class="space-y-1">
            <li
              v-for="(s, i) in analysis.strengths"
              :key="i"
              class="text-xs text-gray-300 flex gap-2"
            >
              <span class="text-emerald-500 shrink-0">•</span>
              <span>{{ s }}</span>
            </li>
            <li v-if="!analysis.strengths?.length" class="text-xs text-gray-500">None identified</li>
          </ul>
        </div>

        <!-- Weaknesses -->
        <div class="rounded-lg border border-amber-700/40 bg-amber-900/10 p-3">
          <p class="text-xs font-semibold text-amber-400 mb-2">⚠️ Weaknesses</p>
          <ul class="space-y-1">
            <li
              v-for="(w, i) in analysis.weaknesses"
              :key="i"
              class="text-xs text-gray-300 flex gap-2"
            >
              <span class="text-amber-500 shrink-0">•</span>
              <span>{{ w }}</span>
            </li>
            <li v-if="!analysis.weaknesses?.length" class="text-xs text-gray-500">None identified</li>
          </ul>
        </div>
      </div>

      <!-- Analyst Narrative -->
      <div v-if="peerAnalysis" class="rounded-lg border border-gray-700 p-4">
        <p class="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Analyst Narrative</p>
        <div class="prose-finance text-sm" v-html="renderedNarrative" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  peerData: Record<string, any>
  peerAnalysis: string
  ticker: string
}>()

const hasPeerData = computed(
  () => !!props.peerData?.target_company && (props.peerData?.peers?.length ?? 0) >= 1
)

const targetCompany = computed(() => props.peerData?.target_company ?? null)
const peers = computed<any[]>(() => props.peerData?.peers ?? [])
const analysis = computed(() => props.peerData?.peer_analysis ?? {})

const renderedNarrative = computed(() => {
  if (!props.peerAnalysis) return ''
  return marked.parse(props.peerAnalysis) as string
})

// ── Badge colours ───────────────────────────────────────────────────────────

const positionBorderClass = computed(() => {
  const pos = analysis.value?.overall_position ?? ''
  if (pos === 'INDUSTRY_LEADER') return 'border-emerald-600/50 bg-emerald-900/10'
  if (pos === 'LAGGARD') return 'border-red-600/50 bg-red-900/10'
  return 'border-yellow-600/50 bg-yellow-900/10'
})

const positionBadgeClass = computed(() => {
  const pos = analysis.value?.overall_position ?? ''
  if (pos === 'INDUSTRY_LEADER') return 'bg-emerald-700/60 text-emerald-300'
  if (pos === 'LAGGARD') return 'bg-red-700/60 text-red-300'
  return 'bg-yellow-700/60 text-yellow-300'
})

const valuationBadgeClass = computed(() => {
  const v = analysis.value?.valuation_vs_peers ?? ''
  if (v === 'PREMIUM') return 'bg-orange-800/40 text-orange-300'
  if (v === 'DISCOUNT') return 'bg-gray-700/60 text-gray-300'
  return 'bg-yellow-800/40 text-yellow-300'
})

const growthBadgeClass = computed(() => {
  const g = analysis.value?.growth_vs_peers ?? ''
  if (g === 'BEST_IN_CLASS') return 'bg-emerald-800/40 text-emerald-300'
  if (g === 'ABOVE_AVERAGE') return 'bg-yellow-800/40 text-yellow-300'
  if (g === 'BELOW_AVERAGE') return 'bg-red-800/40 text-red-300'
  return 'bg-gray-700/60 text-gray-300'
})

// ── Formatters ───────────────────────────────────────────────────────────────

function fmt(val: number | null | undefined, decimals = 1): string {
  if (val == null) return '—'
  return val.toFixed(decimals) + 'x'
}

function fmtPct(val: number | null | undefined): string {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(1)}%`
}

function fmtBn(val: number | null | undefined): string {
  if (val == null) return '—'
  if (val >= 1000) return `$${(val / 1000).toFixed(1)}T`
  return `$${val.toFixed(1)}B`
}

function fmtDollar(val: number | null | undefined): string {
  if (val == null) return '—'
  return `$${val.toFixed(2)}`
}
</script>
