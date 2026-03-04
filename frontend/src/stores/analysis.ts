import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface DebateMessage {
  round: number;
  speaker: "analyst" | "critic";
  content: string;
}

export interface RagSource {
  id: string
  query: string
  score: number
  content: string
}

export interface LivePrice {
  ticker: string
  company_name: string
  price: number | null
  previous_close: number | null
  change: number | null
  change_pct: number | null
  market_state: string          // REGULAR | PRE | POST | CLOSED
  pre_market_price: number | null
  post_market_price: number | null
  week52_high: number | null
  week52_low: number | null
  market_cap: number | null
  volume: number | null
  avg_volume: number | null
  currency: string
  fetched_at: string
  error?: string
}

export interface NewsItem {
  title: string
  publisher: string
  url: string
  published_at: string          // ISO-8601
  related_tickers: string[]
}

export interface AnalysisResult {
  ticker: string;
  year: number;
  depth: string;
  fundamental_analysis: string;
  financial_statements: Record<string, any>;
  technical_analysis: string;
  sentiment_analysis: string;
  live_price: LivePrice | null;
  news_items: NewsItem[];
  rag_sources: RagSource[];
  data_sources: string[];
  ticker_cik: string;
  valuation_analysis: string;
  valuation_data: Record<string, any>;
  peer_analysis: string;
  peer_data: Record<string, any>;
  analyst_thesis: string;
  analyst_response: string;
  critic_feedback: string;
  critic_verdict: string;
  debate_transcript: DebateMessage[];
  debate_round: number;
  final_report: string;
  error: string | null;
}

export interface TickerState {
  ticker: string;
  status: "idle" | "running" | "complete" | "error";
  completedSteps: string[];
  currentStep: string | null;
  currentStepIndex: number;
  totalSteps: number;
  currentLabel: string;
  result: AnalysisResult | null;
  error: string | null;
}

function makeTickerState(ticker = ""): TickerState {
  return {
    ticker,
    status: "idle",
    completedSteps: [],
    currentStep: null,
    currentStepIndex: 0,
    totalSteps: 11,
    currentLabel: "",
    result: null,
    error: null,
  };
}

export const useAnalysisStore = defineStore("analysis", () => {
  const mode = ref<"single" | "compare">("single");
  const tickerA = ref<TickerState>(makeTickerState());
  const tickerB = ref<TickerState>(makeTickerState());
  const activeChat = ref<"A" | "B" | null>(null);
  const chatHistory = ref<Array<{ role: string; content: string }>>([]);

  // ── Getters ──────────────────────────────────────────────────────────────

  const isRunning = computed(
    () =>
      tickerA.value.status === "running" || tickerB.value.status === "running",
  );

  const activeChatContext = computed<AnalysisResult | null>(() => {
    if (activeChat.value === "A") return tickerA.value.result;
    if (activeChat.value === "B") return tickerB.value.result;
    return null;
  });

  // ── Actions ──────────────────────────────────────────────────────────────

  function resetTicker(which: "A" | "B") {
    const ticker = which === "A" ? tickerA : tickerB;
    const name = ticker.value.ticker;
    ticker.value = makeTickerState(name);
  }

  function setMode(m: "single" | "compare") {
    mode.value = m;
  }

  function handleProgress(event: {
    ticker: string;
    step: string;
    step_index: number;
    total_steps: number;
    label: string;
  }) {
    const target = event.ticker === tickerA.value.ticker ? tickerA : tickerB;
    target.value.status = "running";
    target.value.currentStep = event.step;
    target.value.currentStepIndex = event.step_index;
    target.value.totalSteps = event.total_steps;
    target.value.currentLabel = event.label;
    if (!target.value.completedSteps.includes(event.step)) {
      target.value.completedSteps = [
        ...target.value.completedSteps,
        event.step,
      ];
    }
  }

  function handleComplete(event: { ticker: string; result: AnalysisResult }) {
    const target = event.ticker === tickerA.value.ticker ? tickerA : tickerB;
    target.value.status = "complete";
    target.value.currentStep = null;
    target.value.currentLabel = "Analysis complete";
    target.value.result = event.result;
  }

  function handleError(event: { ticker: string; message: string }) {
    const target = event.ticker === tickerA.value.ticker ? tickerA : tickerB;
    target.value.status = "error";
    target.value.error = event.message;
    target.value.currentLabel = "Error occurred";
  }

  function startAnalysis(ticker: string, which: "A" | "B" = "A") {
    const target = which === "A" ? tickerA : tickerB;
    target.value = makeTickerState(ticker.toUpperCase());
    target.value.status = "running";
    target.value.currentLabel = "Initializing...";
  }

  function openChat(which: "A" | "B") {
    activeChat.value = which;
    chatHistory.value = [];
  }

  function closeChat() {
    activeChat.value = null;
  }

  function addChatMessage(role: string, content: string) {
    chatHistory.value = [...chatHistory.value, { role, content }];
  }

  return {
    mode,
    tickerA,
    tickerB,
    activeChat,
    chatHistory,
    isRunning,
    activeChatContext,
    resetTicker,
    setMode,
    handleProgress,
    handleComplete,
    handleError,
    startAnalysis,
    openChat,
    closeChat,
    addChatMessage,
  };
});
