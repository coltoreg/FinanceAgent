<template>
  <div v-if="statements && !statements.error" class="space-y-6 text-xs">
    <!-- Income Statement -->
    <section>
      <h3 class="text-cyan-400 font-semibold mb-2 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-cyan-500 inline-block"></span>
        Income Statement
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="border-b border-gray-700">
              <th class="text-left py-1 px-2 text-gray-400 font-medium w-48">Metric</th>
              <th
                v-for="yr in yearCols"
                :key="yr"
                class="text-right py-1 px-2 text-gray-400 font-medium"
              >
                {{ yr }}
              </th>
            </tr>
          </thead>
          <tbody>
            <FinRow label="Revenue" :items="is.revenue" :years="yearCols" bold />
            <FinRow label="Gross Profit" :items="is.gross_profit" :years="yearCols" indent />
            <FinRow label="Operating Income" :items="is.operating_income" :years="yearCols" indent />
            <FinRow label="Net Income" :items="is.net_income" :years="yearCols" indent bold />
            <FinRow label="R&D Expense" :items="is.rd_expense" :years="yearCols" indent />
            <FinRow label="EPS (Diluted)" :items="is.eps_diluted" :years="yearCols" />
            <tr class="border-t border-gray-700/50">
              <td colspan="99"></td>
            </tr>
            <FinRow label="Revenue Growth YoY" :items="is.revenue_growth_yoy" :years="yearCols" />
            <FinRow label="Gross Margin %" :items="is.gross_margin_pct" :years="yearCols" />
            <FinRow label="Net Margin %" :items="is.net_margin_pct" :years="yearCols" />
            <FinRow label="R&D % Revenue" :items="is.rd_as_pct_revenue" :years="yearCols" />
          </tbody>
        </table>
      </div>
    </section>

    <!-- Balance Sheet -->
    <section>
      <h3 class="text-yellow-400 font-semibold mb-2 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-yellow-500 inline-block"></span>
        Balance Sheet
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="border-b border-gray-700">
              <th class="text-left py-1 px-2 text-gray-400 font-medium w-48">Metric</th>
              <th v-for="yr in yearCols" :key="yr" class="text-right py-1 px-2 text-gray-400 font-medium">{{ yr }}</th>
            </tr>
          </thead>
          <tbody>
            <FinRow label="Total Assets" :items="bs.total_assets" :years="yearCols" bold />
            <FinRow label="Cash & Equivalents" :items="bs.cash_and_equivalents" :years="yearCols" indent />
            <FinRow label="Total Liabilities" :items="bs.total_liabilities" :years="yearCols" bold />
            <FinRow label="Long-Term Debt" :items="bs.long_term_debt" :years="yearCols" indent />
            <FinRow label="Shareholders' Equity" :items="bs.shareholders_equity" :years="yearCols" bold />
            <tr class="border-t border-gray-700/50"><td colspan="99"></td></tr>
            <FinRow label="Debt / Equity" :items="bs.debt_to_equity" :years="yearCols" />
            <FinRow label="Current Ratio" :items="bs.current_ratio" :years="yearCols" />
            <FinRow label="ROE %" :items="bs.roe_pct" :years="yearCols" />
            <FinRow label="ROA %" :items="bs.roa_pct" :years="yearCols" />
          </tbody>
        </table>
      </div>
    </section>

    <!-- Cash Flow -->
    <section>
      <h3 class="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
        Cash Flow Statement
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="border-b border-gray-700">
              <th class="text-left py-1 px-2 text-gray-400 font-medium w-48">Metric</th>
              <th v-for="yr in yearCols" :key="yr" class="text-right py-1 px-2 text-gray-400 font-medium">{{ yr }}</th>
            </tr>
          </thead>
          <tbody>
            <FinRow label="Operating Cash Flow" :items="cf.operating_cf" :years="yearCols" bold />
            <FinRow label="Investing Cash Flow" :items="cf.investing_cf" :years="yearCols" />
            <FinRow label="Financing Cash Flow" :items="cf.financing_cf" :years="yearCols" />
            <FinRow label="CapEx" :items="cf.capex" :years="yearCols" indent />
            <FinRow label="Free Cash Flow" :items="cf.free_cash_flow" :years="yearCols" bold />
            <FinRow label="Stock-Based Comp" :items="cf.stock_based_compensation" :years="yearCols" indent />
            <tr class="border-t border-gray-700/50"><td colspan="99"></td></tr>
            <FinRow label="FCF Margin %" :items="cf.fcf_margin_pct" :years="yearCols" />
          </tbody>
        </table>
      </div>
    </section>

    <!-- Fundamental Score -->
    <div
      :class="[
        'p-3 rounded border text-sm font-medium',
        score === 'STRONG' ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-400' :
        score === 'WEAK' ? 'bg-red-900/30 border-red-700/50 text-red-400' :
        'bg-yellow-900/30 border-yellow-700/50 text-yellow-400'
      ]"
    >
      Fundamental Score: {{ score || 'N/A' }}
      <span class="text-gray-400 font-normal text-xs ml-2">{{ statements.score_rationale }}</span>
    </div>
  </div>

  <div v-else class="text-gray-500 text-sm text-center py-8">
    No structured financial data available.
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// Inline sub-component for table rows
const FinRow = {
  props: ['label', 'items', 'years', 'bold', 'indent'],
  template: `
    <tr class="border-b border-gray-800 hover:bg-gray-800/30">
      <td :class="['py-1 px-2 text-gray-400', bold ? 'font-semibold text-gray-200' : '', indent ? 'pl-6' : '']">
        {{ label }}
      </td>
      <td
        v-for="yr in years"
        :key="yr"
        class="py-1 px-2 text-right text-gray-300 tabular-nums"
      >
        {{ getVal(items, yr) }}
      </td>
    </tr>
  `,
  methods: {
    getVal(items: any[], yr: any): string {
      const found = (items ?? []).find((i: any) => i.year === yr)
      return found?.formatted ?? '—'
    }
  }
}

const props = defineProps<{
  statements: Record<string, any> | null
}>()

const is = computed(() => props.statements?.income_statement ?? {})
const bs = computed(() => props.statements?.balance_sheet ?? {})
const cf = computed(() => props.statements?.cash_flow_statement ?? {})
const score = computed(() => props.statements?.fundamental_score ?? '')

const yearCols = computed<number[]>(() => {
  const rev = is.value?.revenue ?? []
  const years = rev.slice(0, 4).map((r: any) => r.year).filter(Boolean)
  return years.length ? years : []
})
</script>
