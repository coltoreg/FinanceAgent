<template>
  <div v-if="quote && quote.price" class="flex flex-wrap items-center gap-x-5 gap-y-1.5 px-4 py-2.5
             bg-gray-800/60 border-b border-gray-700/50 text-xs">

    <!-- Price + change -->
    <div class="flex items-baseline gap-2">
      <span class="text-gray-200 font-mono font-semibold text-base">
        {{ fmtPrice(quote.price) }}
      </span>
      <span :class="changeClass" class="flex items-center gap-0.5 font-medium">
        <span>{{ changeArrow }}</span>
        <span>{{ fmtChange(quote.change) }}</span>
        <span class="opacity-75">({{ fmtPct(quote.change_pct) }})</span>
      </span>
    </div>

    <!-- Market state badge -->
    <span :class="marketStateBadge" class="px-1.5 py-0.5 rounded text-xs font-medium">
      {{ marketStateLabel }}
    </span>

    <!-- Pre/Post market price (shown only if outside regular session) -->
    <span
      v-if="quote.market_state === 'PRE' && quote.pre_market_price"
      class="text-yellow-400 text-xs"
    >
      Pre-market: {{ fmtPrice(quote.pre_market_price) }}
    </span>
    <span
      v-else-if="quote.market_state === 'POST' && quote.post_market_price"
      class="text-blue-400 text-xs"
    >
      After-hours: {{ fmtPrice(quote.post_market_price) }}
    </span>

    <span class="text-gray-600">|</span>

    <!-- 52-week range -->
    <div v-if="quote.week52_low && quote.week52_high" class="flex items-center gap-1.5">
      <span class="text-gray-500">52W</span>
      <span class="text-red-400">{{ fmtPrice(quote.week52_low) }}</span>
      <div class="relative w-16 h-1 bg-gray-700 rounded-full overflow-hidden">
        <div
          class="absolute left-0 top-0 h-full bg-cyan-500 rounded-full"
          :style="{ width: `${week52Position}%` }"
        />
      </div>
      <span class="text-emerald-400">{{ fmtPrice(quote.week52_high) }}</span>
    </div>

    <span class="text-gray-600">|</span>

    <!-- Market cap -->
    <div v-if="quote.market_cap" class="flex items-center gap-1">
      <span class="text-gray-500">Mkt Cap</span>
      <span class="text-gray-300">{{ fmtMarketCap(quote.market_cap) }}</span>
    </div>

    <!-- Volume -->
    <div v-if="quote.volume" class="flex items-center gap-1">
      <span class="text-gray-500">Vol</span>
      <span :class="volumeClass">{{ fmtVolume(quote.volume) }}</span>
      <span v-if="quote.avg_volume" class="text-gray-600">
        (avg {{ fmtVolume(quote.avg_volume) }})
      </span>
    </div>

    <!-- Timestamp -->
    <span class="ml-auto text-gray-600 text-xs tabular-nums">
      {{ quote.fetched_at ? fmtTime(quote.fetched_at) : '' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LivePrice } from '@/stores/analysis'

const props = defineProps<{
  quote: LivePrice | null
}>()

// ── Formatting helpers ─────────────────────────────────────────────────────

function fmtPrice(v: number | null): string {
  if (v == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(v)
}

function fmtChange(v: number | null): string {
  if (v == null) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}`
}

function fmtPct(v: number | null): string {
  if (v == null) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

function fmtMarketCap(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  return `$${v.toLocaleString()}`
}

function fmtVolume(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return v.toLocaleString()
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
    })
  } catch {
    return iso
  }
}

// ── Computed ──────────────────────────────────────────────────────────────

const changeClass = computed(() => {
  const c = props.quote?.change ?? 0
  if (c > 0) return 'text-emerald-400'
  if (c < 0) return 'text-red-400'
  return 'text-gray-400'
})

const changeArrow = computed(() => {
  const c = props.quote?.change ?? 0
  if (c > 0) return '▲'
  if (c < 0) return '▼'
  return '─'
})

const marketStateLabel = computed(() => {
  const s = props.quote?.market_state ?? ''
  const labels: Record<string, string> = {
    REGULAR: 'Market Open',
    PRE: 'Pre-Market',
    POST: 'After-Hours',
    CLOSED: 'Market Closed',
  }
  return labels[s] ?? s
})

const marketStateBadge = computed(() => {
  const s = props.quote?.market_state ?? ''
  if (s === 'REGULAR') return 'bg-emerald-900/40 text-emerald-400 border border-emerald-700/40'
  if (s === 'PRE') return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700/40'
  if (s === 'POST') return 'bg-blue-900/40 text-blue-400 border border-blue-700/40'
  return 'bg-gray-800 text-gray-500 border border-gray-700'
})

const week52Position = computed(() => {
  const q = props.quote
  if (!q?.price || !q.week52_low || !q.week52_high) return 50
  const range = q.week52_high - q.week52_low
  if (range === 0) return 50
  return Math.min(100, Math.max(0, ((q.price - q.week52_low) / range) * 100))
})

const volumeClass = computed(() => {
  const q = props.quote
  if (!q?.volume || !q.avg_volume) return 'text-gray-300'
  const ratio = q.volume / q.avg_volume
  if (ratio >= 1.5) return 'text-yellow-400 font-semibold'
  return 'text-gray-300'
})
</script>
