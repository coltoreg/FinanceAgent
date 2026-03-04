<template>
  <div class="space-y-1">
    <!-- Has news -->
    <template v-if="news && news.length">
      <div
        v-for="(item, idx) in news"
        :key="idx"
        class="group flex gap-3 p-3 rounded-lg border border-transparent
               hover:bg-gray-800/60 hover:border-gray-700/50 transition-colors"
      >
        <!-- Index number -->
        <span class="text-gray-600 text-xs tabular-nums pt-0.5 w-4 shrink-0">
          {{ idx + 1 }}
        </span>

        <!-- Content -->
        <div class="flex-1 min-w-0 space-y-1">
          <!-- Title -->
          <a
            v-if="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-sm text-gray-200 hover:text-cyan-400 transition-colors leading-snug
                   line-clamp-2 block font-medium"
          >
            {{ item.title }}
            <svg class="w-3 h-3 inline ml-1 opacity-0 group-hover:opacity-60 transition-opacity"
              fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          <span v-else class="text-sm text-gray-200 leading-snug line-clamp-2 block font-medium">
            {{ item.title }}
          </span>

          <!-- Meta row -->
          <div class="flex items-center gap-2 flex-wrap">
            <!-- Publisher badge -->
            <span class="text-xs bg-gray-800 border border-gray-700 text-gray-400
                         px-1.5 py-0.5 rounded font-medium">
              {{ item.publisher || 'Unknown' }}
            </span>

            <!-- Time ago -->
            <span class="text-xs text-gray-600">
              {{ timeAgo(item.published_at) }}
            </span>

            <!-- Related tickers (other than the main one) -->
            <template v-if="otherTickers(item).length">
              <span
                v-for="t in otherTickers(item).slice(0, 3)"
                :key="t"
                class="text-xs text-cyan-600 font-mono"
              >
                ${{ t }}
              </span>
            </template>
          </div>
        </div>
      </div>

      <!-- Source attribution -->
      <div class="pt-2 border-t border-gray-800 flex items-center justify-between text-xs text-gray-600">
        <span>{{ news.length }} articles · Source: Yahoo Finance</span>
        <span v-if="fetchedAt" class="tabular-nums">Updated {{ timeAgo(fetchedAt) }}</span>
      </div>
    </template>

    <!-- No news -->
    <div v-else class="flex flex-col items-center justify-center py-12 gap-2 text-gray-600">
      <svg class="w-8 h-8 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
      </svg>
      <span class="text-sm">No recent news available</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NewsItem } from '@/stores/analysis'

const props = defineProps<{
  news: NewsItem[]
  ticker: string
  fetchedAt?: string
}>()

function timeAgo(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function otherTickers(item: NewsItem): string[] {
  return (item.related_tickers ?? []).filter(
    (t) => t.toUpperCase() !== props.ticker.toUpperCase()
  )
}
</script>
