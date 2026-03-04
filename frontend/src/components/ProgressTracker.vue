<template>
  <div class="space-y-2">
    <!-- Header: ticker + status badge -->
    <div class="flex items-center justify-between">
      <span class="text-cyan-400 font-semibold text-sm tracking-wider">{{ state.ticker }}</span>
      <span
        :class="[
          'text-xs px-2 py-0.5 rounded font-medium',
          state.status === 'running' ? 'bg-cyan-900/50 text-cyan-300' :
          state.status === 'complete' ? 'bg-emerald-900/50 text-emerald-400' :
          state.status === 'error' ? 'bg-red-900/50 text-red-400' :
          'bg-gray-800 text-gray-500'
        ]"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- Progress bar -->
    <div class="h-1.5 bg-gray-800 rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="state.status === 'error' ? 'bg-red-500' : 'bg-cyan-500'"
        :style="{ width: `${progressPct}%` }"
      />
    </div>

    <!-- Step label -->
    <div class="flex items-center gap-2 text-xs text-gray-400 min-h-[1.25rem]">
      <svg
        v-if="state.status === 'running'"
        class="animate-spin w-3 h-3 text-cyan-500 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <svg v-else-if="state.status === 'complete'" class="w-3 h-3 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      <svg v-else-if="state.status === 'error'" class="w-3 h-3 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span>{{ state.currentLabel || (state.status === 'idle' ? 'Ready' : '') }}</span>
      <span v-if="state.status !== 'idle'" class="ml-auto text-gray-600">
        {{ state.currentStepIndex }}/{{ state.totalSteps }}
      </span>
    </div>

    <!-- Rating badge (shown when complete) -->
    <div v-if="state.status === 'complete' && rating" class="flex items-center gap-2">
      <span :class="ratingClass">{{ rating }}</span>
      <span v-if="fundScore" :class="fundScoreClass">{{ fundScore }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TickerState } from '@/stores/analysis'

const props = defineProps<{
  state: TickerState
}>()

const progressPct = computed(() => {
  if (props.state.status === 'complete') return 100
  if (props.state.status === 'error') return props.state.currentStepIndex * (100 / props.state.totalSteps)
  if (props.state.status === 'idle') return 0
  return props.state.currentStepIndex * (100 / props.state.totalSteps)
})

const statusLabel = computed(() => {
  switch (props.state.status) {
    case 'running': return 'Running'
    case 'complete': return 'Complete'
    case 'error': return 'Error'
    default: return 'Idle'
  }
})

const rating = computed(() => props.state.result?.financial_statements?.investment_rating
  ?? _extractRating(props.state.result?.final_report ?? ''))

const fundScore = computed(() => props.state.result?.financial_statements?.fundamental_score ?? '')

const ratingClass = computed(() => {
  const r = rating.value?.toUpperCase() ?? ''
  if (r.includes('STRONG BUY') || r === 'BUY') return 'badge-buy'
  if (r.includes('SELL')) return 'badge-sell'
  return 'badge-hold'
})

const fundScoreClass = computed(() => {
  const s = fundScore.value?.toUpperCase()
  if (s === 'STRONG') return 'text-xs text-emerald-400'
  if (s === 'WEAK') return 'text-xs text-red-400'
  return 'text-xs text-yellow-400'
})

function _extractRating(text: string): string {
  const m = text.match(/\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD)\b/i)
  return m ? m[1].toUpperCase() : ''
}
</script>
