<template>
  <div class="min-h-screen flex flex-col bg-[#0a0f1a]">
    <!-- Header -->
    <header class="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-30">
      <div class="max-w-screen-2xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="text-cyan-400 font-bold text-lg tracking-tight">FinAgent</span>
          <span class="text-gray-600 text-xs hidden sm:inline">Multi-Agent Investment Analysis</span>
        </div>
        <div class="flex items-center gap-2 text-xs text-gray-500">
          <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
          Powered by Claude AI
        </div>
      </div>
    </header>

    <!-- Main content -->
    <main class="flex-1 max-w-screen-2xl mx-auto w-full px-4 py-6 space-y-6">
      <!-- Ticker Form -->
      <TickerForm
        :mode="store.mode"
        :disabled="store.isRunning"
        @submit="handleSubmit"
        @mode="store.setMode"
      />

      <!-- Single mode: progress + panel -->
      <template v-if="store.mode === 'single'">
        <div v-if="store.tickerA.status !== 'idle'" class="card p-4">
          <ProgressTracker :state="store.tickerA" />
        </div>
        <AnalysisPanel
          v-if="store.tickerA.status !== 'idle'"
          :state="store.tickerA"
          class="flex-1"
          style="min-height: 600px"
          @open-chat="store.openChat('A')"
        />
      </template>

      <!-- Compare mode: two-column layout -->
      <template v-else>
        <ComparisonView v-if="store.tickerA.status !== 'idle' || store.tickerB.status !== 'idle'" />
      </template>
    </main>

    <!-- Floating chat button (when analysis is complete and chat is closed) -->
    <button
      v-if="hasChatableResult && store.activeChat === null"
      class="fixed bottom-6 right-6 bg-cyan-500 hover:bg-cyan-400 text-gray-950 font-semibold
             px-4 py-3 rounded-full shadow-lg transition-colors flex items-center gap-2 z-40"
      @click="store.openChat(store.mode === 'single' ? 'A' : 'A')"
    >
      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z" />
      </svg>
      Ask AI about this analysis
    </button>

    <!-- Chat Panel (Teleport in component) -->
    <ChatPanel />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import { useSSE } from '@/composables/useSSE'
import TickerForm from '@/components/TickerForm.vue'
import ProgressTracker from '@/components/ProgressTracker.vue'
import AnalysisPanel from '@/components/AnalysisPanel.vue'
import ComparisonView from '@/components/ComparisonView.vue'
import ChatPanel from '@/components/ChatPanel.vue'

const store = useAnalysisStore()
const { streamAnalysis, streamCompare } = useSSE()

const hasChatableResult = computed(
  () => store.tickerA.status === 'complete' || store.tickerB.status === 'complete'
)

async function handleSubmit(payload: {
  tickerA: string
  tickerB: string
  year: number
  depth: string
}) {
  if (store.mode === 'single') {
    await streamAnalysis({
      ticker: payload.tickerA,
      year: payload.year,
      depth: payload.depth,
      debate_rounds: 2,
      enable_memory: true,
    })
  } else {
    await streamCompare({
      ticker_a: payload.tickerA,
      ticker_b: payload.tickerB,
      year: payload.year,
      depth: payload.depth,
      debate_rounds: 2,
      enable_memory: true,
    })
  }
}
</script>
