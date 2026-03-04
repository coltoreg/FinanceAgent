<template>
  <div class="space-y-4">
    <!-- Two-column analysis panels -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="flex flex-col gap-3">
        <ProgressTracker :state="store.tickerA" />
        <AnalysisPanel
          :state="store.tickerA"
          class="flex-1"
          @open-chat="store.openChat('A')"
        />
      </div>
      <div class="flex flex-col gap-3">
        <ProgressTracker :state="store.tickerB" />
        <AnalysisPanel
          :state="store.tickerB"
          class="flex-1"
          @open-chat="store.openChat('B')"
        />
      </div>
    </div>

    <!-- Summary comparison table (shown when both complete) -->
    <div v-if="bothComplete" class="card p-4">
      <h3 class="text-cyan-400 font-semibold text-sm mb-3 uppercase tracking-wider">
        Side-by-Side Comparison
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full text-xs border-collapse">
          <thead>
            <tr class="border-b border-gray-700">
              <th class="text-left py-2 px-3 text-gray-400 w-40">Metric</th>
              <th class="text-center py-2 px-3 text-cyan-400 font-semibold">{{ store.tickerA.ticker }}</th>
              <th class="text-center py-2 px-3 text-cyan-400 font-semibold">{{ store.tickerB.ticker }}</th>
            </tr>
          </thead>
          <tbody>
            <CompRow label="Investment Rating" :a="ratingA" :b="ratingB" />
            <CompRow label="Fundamental Score" :a="fundA" :b="fundB" />
            <CompRow
              label="Revenue (Latest)"
              :a="metricA('income_statement', 'revenue')"
              :b="metricB('income_statement', 'revenue')"
            />
            <CompRow
              label="Net Margin %"
              :a="metricA('income_statement', 'net_margin_pct')"
              :b="metricB('income_statement', 'net_margin_pct')"
            />
            <CompRow
              label="Revenue Growth YoY"
              :a="metricA('income_statement', 'revenue_growth_yoy')"
              :b="metricB('income_statement', 'revenue_growth_yoy')"
            />
            <CompRow
              label="ROE %"
              :a="metricA('balance_sheet', 'roe_pct')"
              :b="metricB('balance_sheet', 'roe_pct')"
            />
            <CompRow
              label="Debt / Equity"
              :a="metricA('balance_sheet', 'debt_to_equity')"
              :b="metricB('balance_sheet', 'debt_to_equity')"
            />
            <CompRow
              label="Free Cash Flow"
              :a="metricA('cash_flow_statement', 'free_cash_flow')"
              :b="metricB('cash_flow_statement', 'free_cash_flow')"
            />
            <CompRow
              label="FCF Margin %"
              :a="metricA('cash_flow_statement', 'fcf_margin_pct')"
              :b="metricB('cash_flow_statement', 'fcf_margin_pct')"
            />
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import ProgressTracker from './ProgressTracker.vue'
import AnalysisPanel from './AnalysisPanel.vue'

const store = useAnalysisStore()

// Inline comparison row sub-component
const CompRow = {
  props: ['label', 'a', 'b'],
  template: `
    <tr class="border-b border-gray-800 hover:bg-gray-800/30">
      <td class="py-2 px-3 text-gray-400">{{ label }}</td>
      <td class="py-2 px-3 text-center text-gray-200 font-medium">{{ a || '—' }}</td>
      <td class="py-2 px-3 text-center text-gray-200 font-medium">{{ b || '—' }}</td>
    </tr>
  `
}

const bothComplete = computed(
  () => store.tickerA.status === 'complete' && store.tickerB.status === 'complete'
)

const ratingA = computed(() => _getRating(store.tickerA.result?.financial_statements, store.tickerA.result?.final_report))
const ratingB = computed(() => _getRating(store.tickerB.result?.financial_statements, store.tickerB.result?.final_report))
const fundA = computed(() => store.tickerA.result?.financial_statements?.fundamental_score ?? '—')
const fundB = computed(() => store.tickerB.result?.financial_statements?.fundamental_score ?? '—')

function metricA(section: string, key: string): string {
  return _getMetric(store.tickerA.result?.financial_statements, section, key)
}
function metricB(section: string, key: string): string {
  return _getMetric(store.tickerB.result?.financial_statements, section, key)
}

function _getRating(statements: any, report: string | undefined): string {
  if (statements?.investment_rating) return statements.investment_rating
  const m = (report ?? '').match(/\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD)\b/i)
  return m ? m[1].toUpperCase() : '—'
}

function _getMetric(statements: any, section: string, key: string): string {
  const items = statements?.[section]?.[key] ?? []
  return items[0]?.formatted ?? '—'
}
</script>
