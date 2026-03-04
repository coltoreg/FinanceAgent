<template>
  <div class="space-y-4">
    <!-- Empty state -->
    <div v-if="!hasData" class="flex items-center justify-center py-16 text-gray-500 text-sm">
      No valuation data available.
    </div>

    <template v-else>
      <!-- Valuation Overview banner -->
      <div
        :class="['rounded-lg px-4 py-3 flex items-center gap-3 border', overallClass.bg, overallClass.border]"
      >
        <span :class="['font-bold text-lg tracking-wide', overallClass.text]">
          {{ overallVerdict }}
        </span>
        <span class="text-gray-300 text-sm">{{ keyJustification }}</span>
      </div>

      <!-- Two-column grid: DCF + Multiples -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- DCF Analysis -->
        <div class="card-inner">
          <h3 class="section-title">DCF Analysis</h3>
          <dl class="metric-list">
            <div class="metric-row">
              <dt>Intrinsic Value</dt>
              <dd class="font-bold text-cyan-300">${{ fmt(dcf.intrinsic_value) }}</dd>
            </div>
            <div class="metric-row">
              <dt>Current Price</dt>
              <dd>${{ fmt(dcf.current_price) }}</dd>
            </div>
            <div class="metric-row">
              <dt>Upside / Downside</dt>
              <dd :class="upsideClass">{{ upsideLabel }}</dd>
            </div>
            <div class="metric-row">
              <dt>WACC</dt>
              <dd>{{ pct(dcf.wacc_used) }}</dd>
            </div>
            <div class="metric-row">
              <dt>Terminal Growth</dt>
              <dd>{{ pct(dcf.terminal_growth_rate) }}</dd>
            </div>
            <div v-if="dcf.terminal_value" class="metric-row">
              <dt>Terminal Value</dt>
              <dd>${{ fmt(dcf.terminal_value) }}B</dd>
            </div>
          </dl>

          <!-- FCF Projections sparkline -->
          <div v-if="fcfProjections.length" class="mt-3">
            <p class="text-xs text-gray-500 mb-1">5-Year FCF Projections (B USD)</p>
            <div class="flex items-end gap-1 h-12">
              <div
                v-for="(val, i) in fcfProjections"
                :key="i"
                :style="{ height: barHeight(val) + '%' }"
                class="flex-1 bg-cyan-700 rounded-sm opacity-80 hover:opacity-100 transition-opacity"
                :title="`Y${i + 1}: $${val.toFixed(1)}B`"
              />
            </div>
            <div class="flex justify-between text-xs text-gray-600 mt-0.5">
              <span v-for="(_, i) in fcfProjections" :key="i">Y{{ i + 1 }}</span>
            </div>
          </div>

          <p v-if="dcf.methodology" class="text-xs text-gray-500 mt-3 leading-relaxed italic">
            {{ dcf.methodology }}
          </p>
        </div>

        <!-- Relative Multiples -->
        <div class="card-inner">
          <h3 class="section-title">Relative Multiples</h3>
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-gray-500 border-b border-gray-700">
                <th class="text-left py-1.5 font-normal">Multiple</th>
                <th class="text-right py-1.5 font-normal">Value</th>
                <th class="text-right py-1.5 font-normal">Sector Avg</th>
                <th class="text-right py-1.5 font-normal">Grade</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="m in multipleRows"
                :key="m.label"
                class="border-b border-gray-800 hover:bg-gray-800/40 transition-colors"
              >
                <td class="py-1.5 text-gray-300">{{ m.label }}</td>
                <td class="py-1.5 text-right font-mono">
                  {{ m.value < 0 ? 'N/A' : m.value.toFixed(1) + 'x' }}
                </td>
                <td class="py-1.5 text-right font-mono text-gray-500">
                  {{ m.sectorAvg < 0 ? '—' : m.sectorAvg.toFixed(1) + 'x' }}
                </td>
                <td class="py-1.5 text-right">
                  <span :class="['badge-small', assessmentClass(m.assessment)]">
                    {{ m.assessment }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Key concern -->
      <div v-if="keyConcern" class="rounded-lg bg-yellow-900/20 border border-yellow-700/40 px-4 py-2.5">
        <span class="text-yellow-400 text-xs font-semibold mr-2">Key Concern</span>
        <span class="text-gray-300 text-sm">{{ keyConcern }}</span>
      </div>

      <!-- Analyst Narrative -->
      <div v-if="valuationAnalysis" class="card-inner">
        <h3 class="section-title">Analyst Narrative</h3>
        <div class="prose-finance text-sm leading-relaxed" v-html="renderedNarrative" />
      </div>

      <!-- Sector avg disclaimer -->
      <p class="text-xs text-gray-600 italic">
        * Sector averages are approximate estimates based on AI training knowledge and may not reflect current market conditions.
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  valuationData: Record<string, any>
  valuationAnalysis: string
}>()

// ── Data accessors ────────────────────────────────────────────────────────────

const hasData = computed(() =>
  props.valuationData && Object.keys(props.valuationData).length > 0
)

const dcf = computed(() => props.valuationData?.dcf ?? {})
const multiples = computed(() => props.valuationData?.multiples ?? {})
const summary = computed(() => props.valuationData?.valuation_summary ?? {})

const overallVerdict = computed(() => summary.value.overall ?? 'N/A')
const keyConcern = computed(() => summary.value.key_concern ?? '')
const keyJustification = computed(() => {
  const reasons: string[] = summary.value.justified_by ?? []
  return reasons[0] ?? ''
})

const fcfProjections = computed<number[]>(() => dcf.value.five_year_fcf_projections ?? [])

// ── Upside / Downside ─────────────────────────────────────────────────────────

const upsideLabel = computed(() => {
  const v = dcf.value.upside_downside_pct
  if (v == null) return 'N/A'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
})

const upsideClass = computed(() => {
  const v = dcf.value.upside_downside_pct
  if (v == null) return 'text-gray-400'
  return v >= 0 ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'
})

// ── Overall verdict styling ───────────────────────────────────────────────────

const overallClass = computed(() => {
  switch (overallVerdict.value) {
    case 'CHEAP':
      return { bg: 'bg-emerald-900/20', border: 'border-emerald-700/40', text: 'text-emerald-400' }
    case 'EXPENSIVE':
      return { bg: 'bg-red-900/20', border: 'border-red-700/40', text: 'text-red-400' }
    default:
      return { bg: 'bg-yellow-900/20', border: 'border-yellow-700/40', text: 'text-yellow-400' }
  }
})

// ── Multiples rows ────────────────────────────────────────────────────────────

const multipleRows = computed(() => {
  const m = multiples.value
  const entries = [
    { label: 'P/E (Trailing)', key: 'pe_trailing' },
    { label: 'P/E (Forward)',  key: 'pe_forward' },
    { label: 'EV/EBITDA',     key: 'ev_ebitda' },
    { label: 'P/S',           key: 'price_to_sales' },
    { label: 'P/FCF',         key: 'price_to_fcf' },
    { label: 'P/B',           key: 'price_to_book' },
  ]
  return entries.map(({ label, key }) => ({
    label,
    value: m[key]?.value ?? -1,
    sectorAvg: m[key]?.sector_avg ?? -1,
    assessment: m[key]?.assessment ?? 'N/A',
  }))
})

function assessmentClass(a: string): string {
  switch (a) {
    case 'CHEAP':
    case 'DISCOUNT':
      return 'badge-cheap'
    case 'EXPENSIVE':
      return 'badge-expensive'
    case 'PREMIUM':
      return 'badge-premium'
    case 'FAIR':
    case 'AT MARKET':
      return 'badge-fair'
    default:
      return 'badge-na'
  }
}

// ── FCF bar chart ─────────────────────────────────────────────────────────────

function barHeight(val: number): number {
  const max = Math.max(...fcfProjections.value)
  if (max <= 0) return 10
  return Math.max(10, (val / max) * 100)
}

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmt(v: number | undefined): string {
  if (v == null) return 'N/A'
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function pct(v: number | undefined): string {
  if (v == null) return 'N/A'
  return (v * 100).toFixed(1) + '%'
}

// ── Narrative ─────────────────────────────────────────────────────────────────

const renderedNarrative = computed(() => marked.parse(props.valuationAnalysis ?? '') as string)
</script>

<style scoped>
.card-inner {
  @apply bg-gray-800/50 rounded-lg p-4 border border-gray-700/50;
}

.section-title {
  @apply text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3;
}

.metric-list {
  @apply space-y-1.5;
}

.metric-row {
  @apply flex justify-between text-sm;
}

.metric-row dt {
  @apply text-gray-500;
}

.metric-row dd {
  @apply text-gray-200;
}

.badge-small {
  @apply text-xs px-1.5 py-0.5 rounded font-medium;
}

.badge-cheap {
  @apply bg-emerald-900/40 text-emerald-400;
}

.badge-expensive {
  @apply bg-red-900/40 text-red-400;
}

.badge-premium {
  @apply bg-orange-900/40 text-orange-400;
}

.badge-fair {
  @apply bg-yellow-900/40 text-yellow-400;
}

.badge-na {
  @apply bg-gray-700/40 text-gray-500;
}
</style>
