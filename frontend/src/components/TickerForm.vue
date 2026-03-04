<template>
  <div class="card p-4">
    <!-- Mode Toggle -->
    <div class="flex items-center gap-2 mb-4">
      <span class="text-xs text-gray-400 uppercase tracking-wider">Mode</span>
      <div class="flex rounded overflow-hidden border border-gray-700">
        <button
          :class="['px-4 py-1.5 text-sm font-medium transition-colors', mode === 'single' ? 'bg-cyan-500/20 text-cyan-400' : 'text-gray-400 hover:text-gray-200']"
          @click="emit('mode', 'single')"
        >
          Single
        </button>
        <button
          :class="['px-4 py-1.5 text-sm font-medium transition-colors border-l border-gray-700', mode === 'compare' ? 'bg-cyan-500/20 text-cyan-400' : 'text-gray-400 hover:text-gray-200']"
          @click="emit('mode', 'compare')"
        >
          Compare
        </button>
      </div>
    </div>

    <!-- Form -->
    <form class="flex flex-wrap gap-3 items-end" @submit.prevent="handleSubmit">
      <!-- Ticker A -->
      <div class="flex flex-col gap-1">
        <label class="text-xs text-gray-400 uppercase tracking-wider">
          {{ mode === 'compare' ? 'Ticker A' : 'Ticker' }}
        </label>
        <input
          v-model="tickerA"
          type="text"
          :placeholder="mode === 'compare' ? 'NVDA' : 'NVDA'"
          class="w-28 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm uppercase
                 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500
                 transition-colors"
          :disabled="disabled"
          maxlength="10"
          required
        />
      </div>

      <!-- VS label + Ticker B -->
      <template v-if="mode === 'compare'">
        <span class="text-gray-500 text-sm mb-1.5">vs</span>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-gray-400 uppercase tracking-wider">Ticker B</label>
          <input
            v-model="tickerB"
            type="text"
            placeholder="AAPL"
            class="w-28 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm uppercase
                   text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500
                   transition-colors"
            :disabled="disabled"
            maxlength="10"
            required
          />
        </div>
      </template>

      <!-- Year -->
      <div class="flex flex-col gap-1">
        <label class="text-xs text-gray-400 uppercase tracking-wider">Year</label>
        <select
          v-model="year"
          class="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100
                 focus:outline-none focus:border-cyan-500 transition-colors"
          :disabled="disabled"
        >
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>

      <!-- Depth -->
      <div class="flex flex-col gap-1">
        <label class="text-xs text-gray-400 uppercase tracking-wider">Depth</label>
        <select
          v-model="depth"
          class="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100
                 focus:outline-none focus:border-cyan-500 transition-colors"
          :disabled="disabled"
        >
          <option value="standard">Standard</option>
          <option value="detailed">Detailed</option>
        </select>
      </div>

      <!-- Submit -->
      <button type="submit" class="btn-primary mb-0.5" :disabled="disabled">
        <span v-if="disabled" class="flex items-center gap-2">
          <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Running...
        </span>
        <span v-else>Run Analysis</span>
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  mode: 'single' | 'compare'
  disabled: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', payload: {
    tickerA: string
    tickerB: string
    year: number
    depth: string
  }): void
  (e: 'mode', mode: 'single' | 'compare'): void
}>()

const tickerA = ref('NVDA')
const tickerB = ref('AAPL')
const year = ref(2025)
const depth = ref('standard')

const years = Array.from({ length: 13 }, (_, i) => 2026 - i)

function handleSubmit() {
  emit('submit', {
    tickerA: tickerA.value.toUpperCase().trim(),
    tickerB: tickerB.value.toUpperCase().trim(),
    year: year.value,
    depth: depth.value,
  })
}
</script>
