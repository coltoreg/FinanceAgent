<template>
  <Teleport to="body">
    <Transition name="slide">
      <div
        v-if="store.activeChat !== null"
        class="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-gray-900 border-l border-gray-700
               flex flex-col shadow-2xl z-50"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-900">
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z" />
            </svg>
            <span class="text-sm font-semibold text-gray-200">
              Ask AI — {{ contextTicker }}
            </span>
          </div>
          <button
            class="text-gray-400 hover:text-gray-200 transition-colors"
            @click="store.closeChat()"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Messages -->
        <div ref="messagesEl" class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- Empty state -->
          <div v-if="store.chatHistory.length === 0" class="text-center py-8 space-y-2">
            <p class="text-gray-400 text-sm">Ask anything about the analysis</p>
            <div class="flex flex-col gap-2 mt-4">
              <button
                v-for="q in suggestions"
                :key="q"
                class="text-xs text-left bg-gray-800 hover:bg-gray-700 border border-gray-700
                       rounded px-3 py-2 text-gray-300 transition-colors"
                @click="sendQuestion(q)"
              >
                {{ q }}
              </button>
            </div>
          </div>

          <!-- Chat messages -->
          <div
            v-for="(msg, idx) in store.chatHistory"
            :key="idx"
            :class="[
              'rounded-lg p-3 text-sm',
              msg.role === 'user'
                ? 'bg-gray-800 text-gray-200 ml-8'
                : 'bg-cyan-900/20 border border-cyan-800/40 text-gray-300 mr-8'
            ]"
          >
            <div class="text-xs font-medium mb-1"
              :class="msg.role === 'user' ? 'text-gray-400' : 'text-cyan-400'"
            >
              {{ msg.role === 'user' ? 'You' : 'FinAgent AI' }}
            </div>
            <div class="prose-finance" v-html="renderMarkdown(msg.content)" />
          </div>

          <!-- Loading indicator -->
          <div v-if="loading" class="flex items-center gap-2 text-gray-400 text-xs">
            <svg class="animate-spin w-4 h-4 text-cyan-500" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Thinking...
          </div>

          <!-- Error -->
          <div v-if="error" class="text-red-400 text-xs bg-red-900/20 border border-red-700/50 rounded p-2">
            {{ error }}
          </div>
        </div>

        <!-- Input -->
        <div class="border-t border-gray-700 p-3 bg-gray-900">
          <form class="flex gap-2" @submit.prevent="handleSubmit">
            <input
              v-model="input"
              type="text"
              placeholder="Ask about revenue, risk factors, outlook..."
              class="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm
                     text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500
                     transition-colors"
              :disabled="loading"
            />
            <button
              type="submit"
              class="btn-primary px-3"
              :disabled="loading || !input.trim()"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { useAnalysisStore } from '@/stores/analysis'
import { sendChat } from '@/api/client'

const store = useAnalysisStore()
const input = ref('')
const loading = ref(false)
const error = ref('')
const messagesEl = ref<HTMLElement | null>(null)

const contextTicker = computed(
  () => store.activeChat === 'A' ? store.tickerA.ticker : store.tickerB.ticker
)

const suggestions = computed(() => [
  `What are the biggest risks for ${contextTicker.value}?`,
  `Why is the investment rating ${_getRating()}?`,
  `Explain the revenue trend in simple terms`,
  `What does the debt/equity ratio indicate?`,
])

function _getRating(): string {
  const result = store.activeChatContext
  const stmt = result?.financial_statements
  if (stmt?.investment_rating) return stmt.investment_rating
  const m = (result?.final_report ?? '').match(/\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD)\b/i)
  return m ? m[1].toUpperCase() : 'N/A'
}

function renderMarkdown(text: string): string {
  return marked.parse(text) as string
}

async function sendQuestion(question: string) {
  input.value = question
  await handleSubmit()
}

async function handleSubmit() {
  const question = input.value.trim()
  if (!question || loading.value) return

  input.value = ''
  error.value = ''
  store.addChatMessage('user', question)
  loading.value = true

  await scrollToBottom()

  try {
    const context = store.activeChatContext ?? {}
    const res = await sendChat({
      question,
      context: context as Record<string, any>,
      history: store.chatHistory.slice(-10),
    })
    store.addChatMessage('assistant', res.answer)
  } catch (e: any) {
    error.value = e.message ?? 'Failed to get response'
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

// Auto-scroll on new messages
watch(() => store.chatHistory.length, () => scrollToBottom())
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
