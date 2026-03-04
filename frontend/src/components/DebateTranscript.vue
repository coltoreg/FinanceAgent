<template>
  <div v-if="transcript && transcript.length" class="space-y-4">
    <div
      v-for="(msg, idx) in transcript"
      :key="idx"
      :class="[
        'rounded-lg p-4 border text-sm',
        msg.speaker === 'analyst'
          ? 'bg-emerald-900/20 border-emerald-800/50'
          : 'bg-red-900/20 border-red-800/50'
      ]"
    >
      <!-- Speaker header -->
      <div class="flex items-center gap-2 mb-2">
        <span
          :class="[
            'text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded',
            msg.speaker === 'analyst'
              ? 'bg-emerald-800/50 text-emerald-400'
              : 'bg-red-800/50 text-red-400'
          ]"
        >
          {{ msg.speaker === 'analyst' ? 'Analyst' : 'Critic' }}
        </span>
        <span class="text-xs text-gray-500">Round {{ msg.round }}</span>
      </div>

      <!-- Content -->
      <div class="text-gray-300 leading-relaxed whitespace-pre-wrap text-xs">
        {{ expanded[idx] ? msg.content : truncate(msg.content, 400) }}
      </div>

      <!-- Expand/collapse -->
      <button
        v-if="msg.content.length > 400"
        class="mt-2 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        @click="toggleExpand(idx)"
      >
        {{ expanded[idx] ? '▲ Show less' : '▼ Show more' }}
      </button>
    </div>
  </div>

  <div v-else class="text-gray-500 text-sm text-center py-8">
    No debate transcript available.
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { DebateMessage } from '@/stores/analysis'

defineProps<{
  transcript: DebateMessage[]
}>()

const expanded = ref<Record<number, boolean>>({})

function toggleExpand(idx: number) {
  expanded.value = { ...expanded.value, [idx]: !expanded.value[idx] }
}

function truncate(text: string, len: number): string {
  return text.length > len ? text.slice(0, len) + '...' : text
}
</script>
