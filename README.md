English | [中文](./README_zh.md)

# FinAgent — Multi-Agent Stock Analysis System

> A LangGraph-based Multi-Agent investment analysis framework integrating SEC EDGAR RAG, yfinance technical analysis, real-time stock prices/news, DCF valuation, peer comparison, adversarial debate, and cross-session memory. Powered by Claude models via AWS Bedrock or Anthropic API, with both **CLI** and **Vue 3 Web UI** interfaces, and full LangSmith tracing.

---

## Architecture

```
User (CLI or Web UI)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                       │
│                                                              │
│  [memory_load] ──► Load historical analyses from MemoryStore │
│        │                                                     │
│        ▼                                                     │
│  ┌───────────┐  ┌──────────────┐  ┌────────────┐            │
│  │Fundamental│  │  Technical   │  │ Sentiment  │            │
│  │  Agent    │  │   Agent      │  │   Agent    │            │
│  │SEC EDGAR  │  │  yfinance    │  │  (Haiku)   │            │
│  │RAG+3 Stmt │  │MA/RSI/MACD   │  │ Real News  │            │
│  │           │  │Live Price    │  │ Sentiment  │            │
│  └─────┬─────┘  └──────┬───────┘  └─────┬──────┘            │
│        └───────────────┴────────────────┘                   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ┌─────────────────────┐  ┌──────────────────────┐    │   │
│  │ │  Valuation Agent    │  │ Peer Comparison Agent │    │   │
│  │ │  DCF + Relative     │  │  5 Peer Companies    │    │   │
│  │ │  P/E EV/EBITDA P/FCF│  │  yfinance Metrics    │    │   │
│  │ └─────────────────────┘  └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│             ┌───────────────────────┐                        │
│             │  Senior Analyst Agent │ ← with memory context  │
│             │  Generate Investment  │                        │
│             │  Thesis               │                        │
│             └───────────┬───────────┘                        │
│                         │◄──────────────────────┐            │
│                         ▼                       │            │
│             ┌───────────────────────┐           │            │
│             │    Critic Agent       │───────────┘            │
│             │  Adversarial (N rounds│   debate loop          │
│             └───────────────────────┘                        │
│                         │                                    │
│                         ▼                                    │
│             ┌───────────────────────┐                        │
│             │    Final Report       │                        │
│             │  Investment Reco +    │                        │
│             │  Financial Summary    │                        │
│             └───────────────────────┘                        │
│                         │                                    │
│  [memory_save] ──► Save results to MemoryStore               │
└──────────────────────────────────────────────────────────────┘
        │
        ▼ (Web mode)
┌─────────────────────────────────────────────────────────┐
│  FastAPI server.py (port 8000)                          │
│   POST /api/analyze/stream  ── SSE real-time streaming  │
│   POST /api/compare/stream  ── parallel dual-ticker     │
│   POST /api/chat            ── LLM Q&A                 │
│   GET  /api/history/{ticker}── history lookup           │
└──────────────────────┬──────────────────────────────────┘
                       │ SSE / JSON
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Vue 3 Frontend (port 5173)                             │
│  Single / Compare mode │ Progress bar │ 7-Tab panel     │
│  MarketDataBar (live price)                             │
│  Report │ Financials │ Valuation │ Peers │ Debate │     │
│  News │ Sources                                         │
│  ChatPanel (floating Q&A drawer)                        │
└─────────────────────────────────────────────────────────┘
```

---

## Core Features

| Feature | Description |
|---------|-------------|
| **SEC EDGAR RAG** | Extracts 30+ financial metrics from XBRL API; ChromaDB + BM25 Hybrid Search with Reciprocal Rank Fusion |
| **Technical Analysis** | yfinance historical data; Claude Function Calling for MA50/200, RSI, MACD; auto overbought/oversold detection |
| **Live Price & News** | yfinance real-time quotes (price, change, 52W range, volume, market cap, pre/after-market) + 10 recent news items; displayed in MarketDataBar |
| **Sentiment Agent** | Uses real news headlines fetched by `technical_node` — not LLM training knowledge |
| **DCF & Relative Valuation** | Valuation Agent uses Claude Tool Use to output structured DCF (5-year FCF, WACC, terminal value) + P/E, EV/EBITDA, P/S, P/FCF, P/B vs. industry averages; verdict: EXPENSIVE / FAIR / CHEAP |
| **Peer Comparison** | Peer Agent identifies 5 peers via Claude Haiku; fetches live metrics via yfinance; Tool Use outputs structured competitive positioning (INDUSTRY_LEADER / COMPETITIVE / LAGGARD) |
| **Adversarial Debate** | Analyst generates thesis; Critic challenges (debt risk, overvaluation, technicals); multi-round debate produces final report |
| **Financial Statements JSON** | Claude Tool Use forces structured JSON: income statement, balance sheet, cash flow, with derived metrics (growth rates, margins, ROE/ROA) |
| **RAG Source Index** | Every analysis tracks retrieved documents (doc ID, RRF score, trigger query, content preview) with clickable SEC EDGAR links |
| **Cross-Session Memory** | ChromaDB persists each analysis; next run auto-loads prior thesis for tracking rating evolution and fundamental trends |
| **Dual Provider** | Single env var switches `LLM_PROVIDER=anthropic` or `LLM_PROVIDER=bedrock` — no agent code changes |
| **LangSmith Tracing** | Full trace: RAG retrieval, LLM calls, Tool Use, debate rounds — viewable in real time |
| **Web UI** | Vue 3 + SSE streaming, Single/Compare modes, 7-tab panel, floating AI chat drawer |

---

## Tech Stack

```
LLM            Claude Sonnet 4.6 / Haiku 4.5 (via Anthropic API or AWS Bedrock)
Orchestration  LangGraph (StateGraph + conditional edges + debate loop)
RAG            ChromaDB (dense) + BM25 (sparse) → RRF fusion
Memory         ChromaDB (semantic search) + JSON files (full record backup)
Financial Data SEC EDGAR XBRL API (30+ GAAP concepts) + yfinance (historical/live/news)
Tracing        LangSmith (wrap_anthropic + @traceable decorators)
Backend API    FastAPI + uvicorn (SSE streaming)
Frontend       Vue 3 + Pinia + Tailwind CSS + Vite
CLI            Typer + Rich (tables, progress bars, color output)
Language       Python 3.11+ / TypeScript
```

---

## Project Structure

```
FinAgent/
├── main.py                          # CLI entry (typer): analyze / history / memory-stats
├── server.py                        # FastAPI backend: SSE streaming / Chat / History
├── pyproject.toml                   # Dependency management
├── .env.example                     # Environment variables template
│
├── src/
│   ├── agents/
│   │   ├── fundamental.py           # SEC RAG Agent (3-statement JSON + RAG sources)
│   │   ├── technical.py             # yfinance Agent (Function Calling)
│   │   ├── valuation.py             # Valuation Agent (DCF + relative multiples)
│   │   ├── peer_comparison.py       # Peer Comparison Agent (5 peers)
│   │   ├── analyst.py               # Senior Analyst (thesis + debate + memory)
│   │   └── critic.py                # Critic (adversarial challenges)
│   │
│   ├── memory/
│   │   └── store.py                 # MemoryStore + AnalysisRecord (cross-session persistence)
│   │
│   ├── tools/
│   │   ├── sec_retriever.py         # HybridRetriever + SEC EDGAR API
│   │   ├── stock_utils.py           # MA/RSI/MACD + get_live_quote() + get_stock_news()
│   │   └── tracing.py               # LangSmith config + provider switching + resolve_model_id
│   │
│   └── workflow/
│       └── langgraph_flow.py        # StateGraph + AnalysisState + memory nodes + debate routing
│
├── frontend/                        # Vue 3 frontend
│   ├── index.html
│   ├── package.json                 # Vue 3, Pinia, Tailwind, Vite
│   ├── vite.config.ts               # Dev proxy → :8000
│   ├── tailwind.config.js           # Dark finance theme
│   └── src/
│       ├── main.ts
│       ├── style.css                # Tailwind + shared component styles
│       ├── App.vue                  # Root layout + mode toggle + floating Chat button
│       ├── stores/
│       │   └── analysis.ts          # Pinia state (SSE events → state)
│       ├── composables/
│       │   └── useSSE.ts            # fetch + ReadableStream SSE parsing
│       ├── api/
│       │   └── client.ts            # sendChat() / getHistory()
│       └── components/
│           ├── TickerForm.vue       # Ticker input form (Single / Compare toggle)
│           ├── ProgressTracker.vue  # 11-step progress bar
│           ├── AnalysisPanel.vue    # 7-Tab panel
│           ├── FinancialTables.vue  # 3-statement tables
│           ├── ValuationPanel.vue   # DCF + relative multiples panel
│           ├── PeerComparisonPanel.vue  # Peer comparison table + positioning
│           ├── DebateTranscript.vue # Analyst/Critic chat bubbles
│           ├── MarketDataBar.vue    # Live price bar (price, change, 52W, volume, cap)
│           ├── NewsFeed.vue         # Recent news list (links, publisher badge, time-ago)
│           ├── ComparisonView.vue   # Side-by-side dual comparison
│           ├── ChatPanel.vue        # Floating Q&A drawer (Teleport)
│           └── SourcesPanel.vue     # RAG source index + SEC EDGAR links
│
└── data/
    ├── chroma/                      # SEC RAG vector index (ChromaDB)
    └── memory/
        ├── chroma/                  # Analysis memory vector index (ChromaDB)
        └── records/                 # Full analysis records JSON ({record_id}.json)
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .

# Frontend dependencies
cd frontend && npm install
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

**Choose a Provider:**

**Option A — AWS Bedrock (Recommended)**
```dotenv
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**Option B — Anthropic Direct**
```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Enable LangSmith Tracing (optional, recommended for demos)**
```dotenv
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=finagent-demo
```

---

## Running the Application

### CLI Mode

```bash
# Basic usage (auto load/save memory)
python main.py --ticker NVDA --year 2024

# Full output: financial statements + debate transcript + all agent sections
python main.py --ticker AAPL --year 2024 --depth detailed \
  --financials --sections --transcript

# Fewer debate rounds (faster)
python main.py --ticker MSFT --year 2024 --rounds 1

# Disable memory (one-off analysis)
python main.py --ticker TSLA --year 2024 --no-memory
```

### Web UI Mode

```bash
# Terminal 1 — start backend API
uvicorn server:app --reload --port 8000

# Terminal 2 — start frontend
cd frontend && npm run dev
# Open http://localhost:5173
```

---

## Web UI

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ FinAgent               [Single | Compare]               │
├─────────────────────────────────────────────────────────┤
│ [NVDA____] vs [AAPL____]  Year:[2024] Depth:[std] [Run] │
├──────────────────────────┬──────────────────────────────┤
│ NVDA   ████████░░ 80%    │ AAPL   ████░░░░░░ 40%        │
│ ⟳ Analyst synthesizing  │ ⟳ Valuation models            │
│                          │                              │
│ Rating: BUY ↑            │ Rating: HOLD →               │
│ ─── MarketDataBar ─────  │ ─── MarketDataBar ─────      │
│ $875.40 ▲+2.3% Market    │ $189.50 ▼-0.8% Market Open  │
│ Open  52W: $400─$950     │ Open  52W: $164─$199         │
│ Mkt Cap $2.15T  Vol 45M  │ Mkt Cap $2.95T  Vol 55M     │
│ [Report][Financials]     │ [Report][Financials]         │
│ [Valuation][Peers]       │ [Valuation][Peers]           │
│ [Debate][News 10][Sources]│[Debate][News 8][Sources]    │
│ <markdown report>        │ <markdown report>            │
├─────────────────────────────────────────────────────────┤
│ Comparison: NVDA BUY STRONG | AAPL HOLD MODERATE        │
└─────────────────────────────────────────────────────────┘
             [💬 Ask AI about this analysis]
```

### 7-Tab Analysis Panel

| Tab | Content |
|-----|---------|
| **Report** | Final investment report (Markdown rendered, includes Analyst + Critic views) |
| **Financials** | Income statement, balance sheet, cash flow statement (multi-year) |
| **Valuation** | DCF model (5-year FCF, WACC, terminal value, intrinsic value vs. current price) + relative multiples (P/E, EV/EBITDA, P/S, P/FCF, P/B vs. industry averages) |
| **Peers** | 5-peer comparison table (market cap, PE, gross margin, growth, analyst target) + competitive positioning (INDUSTRY_LEADER / COMPETITIVE / LAGGARD) |
| **Debate** | Full Analyst ↔ Critic debate transcript (expandable/collapsible) |
| **News** `10` | Recent Yahoo Finance news (links, publisher badge, time-ago, related ticker tags) |
| **Sources** | RAG source index: data source badges + doc ID, RRF score, content preview, clickable SEC EDGAR links |

### MarketDataBar

Displayed above the tab panel after analysis completes:

| Field | Description |
|-------|-------------|
| Price + Change | `▲+2.34 (+0.27%)` — green/red with arrow |
| Market State | `Market Open` / `Pre-Market` / `After-Hours` / `Market Closed` (colored badge) |
| Pre/After-hours Price | Shown automatically when outside regular trading hours |
| 52W Range | Visual progress bar showing current price within 52-week high/low range |
| Market Cap | Auto-formatted as T / B / M |
| Volume | Highlighted in yellow if ≥ 1.5× average volume |
| Updated At | Local time of data fetch (with timezone) |

### Chat Panel

Click "Ask AI" to open a floating right-side drawer powered by Claude Haiku:

```
Ask AI — NVDA

  > What are the biggest risks for NVDA?
  > Why is the investment rating BUY?
  > Explain the revenue trend in simple terms
  > What does the debt/equity ratio indicate?

  [Your question here                        ] [▶]
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/analyze/stream` | SSE stream: single-ticker analysis, pushes 11 progress events + final result |
| `POST` | `/api/compare/stream` | SSE stream: two tickers analyzed in parallel; events identified by `ticker` field |
| `POST` | `/api/chat` | JSON: LLM Q&A with analysis result as context |
| `GET` | `/api/history/{ticker}` | JSON: retrieve historical analyses from MemoryStore |
| `GET` | `/api/health` | Health check |

### SSE Event Format

```json
// Progress event (11 steps)
{"type":"progress","ticker":"NVDA","step":"fundamental","step_index":2,"total_steps":11,"label":"Fetching SEC EDGAR filings..."}

// Complete event (with full AnalysisState)
{"type":"complete","ticker":"NVDA","result":{...}}

// Error event
{"type":"error","ticker":"NVDA","message":"..."}
```

---

## CLI Reference

### `analyze` (main command)

```bash
python main.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--ticker` `-t` | required | Stock ticker (NVDA, AAPL, MSFT, etc.) |
| `--year` `-y` | `2024` | Fiscal year |
| `--depth` `-d` | `standard` | Analysis depth: `standard` / `detailed` |
| `--rounds` `-r` | `2` | Analyst ↔ Critic debate rounds (1–3) |
| `--financials` `-f` | `False` | Print financial statements |
| `--sections` | `False` | Print each agent's raw analysis |
| `--transcript` | `False` | Print full debate transcript |
| `--no-memory` | `False` | Skip memory load and save |

### `history` / `memory-stats`

```bash
python main.py history NVDA
python main.py history NVDA --limit 5
python main.py memory-stats
```

---

## Memory System

### Data Flow

```
1st analysis of NVDA:
  memory_load (0 records) → [analysis] → memory_save → record_id: a1b2c3d4

2nd analysis of NVDA (3 months later):
  memory_load (1 record) → analyst_initial (with prior context)
    → "Has investment case improved vs. prior analysis?"
    → [analysis] → memory_save → record_id: e5f6g7h8
```

### Storage Architecture

```
MemoryStore
  ├── ChromaDB (data/memory/chroma/)
  │     Semantic vector index, supports cross-ticker similarity search
  │     metadata: ticker, year, timestamp, rating, score
  │
  └── JSON files (data/memory/records/{record_id}.json)
        Full record: financial statements, full report, debate transcript,
        RAG sources, model info
```

---

## Financial Statements Output Format

Fundamental Agent uses Claude Tool Use to force-output this structure (excerpt):

```json
{
  "ticker": "NVDA",
  "fiscal_year": 2024,
  "currency": "USD",
  "data_source": "SEC EDGAR XBRL",
  "income_statement": {
    "revenue":            [{"year": "2024", "value_usd": 60922000000, "formatted": "$60.92B"}],
    "net_income":         [{"year": "2024", "value_usd": 29760000000, "formatted": "$29.76B"}],
    "revenue_growth_yoy": [{"year": "2024", "value_usd": 122.4,       "formatted": "122.4%"}],
    "net_margin_pct":     [{"year": "2024", "value_usd": 48.8,        "formatted": "48.8%"}]
  },
  "fundamental_score": "STRONG",
  "top_risks": [
    {"risk": "Supply chain concentration", "severity": "HIGH", "description": "..."}
  ]
}
```

---

## LangSmith Tracing

Set `LANGCHAIN_TRACING_V2=true`, then view the full agent reasoning tree at [smith.langchain.com](https://smith.langchain.com):

```
LangGraph Run: NVDA (root trace)
├─ memory_load                         ← load historical memory
├─ fundamental                         ← LangGraph node
│   ├─ sec_xbrl_fetch                  ← @traceable (SEC API → CIK → 30+ XBRL concepts)
│   ├─ fundamental_rag_retrieval       ← @traceable (4 queries → ChromaDB + BM25 → RRF)
│   ├─ extract_financial_statements    ← @traceable (tool_use → JSON statements)
│   └─ fundamental_narrative_analysis  ← @traceable
├─ technical                           ← LangGraph node
│   ├─ Tool: get_technical_indicators  ← function calling
│   ├─ Tool: get_company_overview
│   ├─ get_live_quote()                ← yfinance fast_info (live quote)
│   └─ get_stock_news()                ← yfinance .news (10 recent items)
├─ sentiment                           ← LangGraph node (real news headlines)
├─ valuation                           ← LangGraph node
│   ├─ extract_valuation_metrics (tool_use) ← DCF + P/E + EV/EBITDA + P/S + P/FCF + P/B
│   └─ generate_narrative
├─ peer_comparison                     ← LangGraph node
│   ├─ identify_peers (Haiku)          ← identify 5 peer tickers
│   ├─ fetch_all_metrics               ← yfinance batch fetch
│   ├─ extract_peer_metrics (tool_use) ← structured competitive positioning
│   └─ generate_narrative
├─ analyst_initial                     ← with memory + valuation + peer context
├─ critic  (Round 1)
├─ analyst_rebuttal (Round 1)
├─ critic  (Round 2)
├─ analyst_rebuttal (Round 2)
├─ final_report
└─ memory_save
```

Each LLM span shows: full prompt, model ID, output, token usage, latency.

---

## AWS Bedrock Setup

### Default Model IDs

| Role | Bedrock Inference Profile ID |
|------|------------------------------|
| Sonnet (main reasoning) | `us.anthropic.claude-sonnet-4-6` |
| Haiku (sentiment / Chat) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Opus (optional) | `us.anthropic.claude-opus-4-6-v1` |

Override in `.env`:

```dotenv
BEDROCK_MODEL_SONNET=us.anthropic.claude-sonnet-4-6
BEDROCK_MODEL_HAIKU=us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_MODEL_OPUS=us.anthropic.claude-opus-4-6-v1
```

### AWS Credential Chain (priority order)

1. `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (+ `AWS_SESSION_TOKEN`) in `.env`
2. `~/.aws/credentials` (via `AWS_PROFILE`)
3. EC2 / ECS / Lambda IAM Role

---

## Developer Notes

### RAG Retrieval

```
Query
  │
  ├─► ChromaDB (dense)  → semantic similarity → Top-K
  ├─► BM25 (sparse)     → keyword matching   → Top-K
  │
  └─► Reciprocal Rank Fusion
        score = α/(k + rank_dense) + (1-α)/(k + rank_sparse)
        α=0.5 (tunable), k=60 (RRF constant)
```

### Live Price & News Fetching

`technical_node` fetches data in parallel while running technical analysis:

```python
# src/tools/stock_utils.py

get_live_quote(ticker)
# Returns: price, change, change_pct, market_state,
#          pre_market_price, post_market_price,
#          week52_high, week52_low, market_cap,
#          volume, avg_volume, currency, fetched_at

get_stock_news(ticker, max_items=10)
# Returns: [{title, publisher, url, published_at (ISO), related_tickers}]
```

Fetched data stored in `AnalysisState`:
- `live_price` → `MarketDataBar` in frontend
- `news_items` → `NewsFeed` in frontend + `sentiment_node` context

### Provider Switching

```python
# All agents use uniformly:
self.client = get_traced_client()       # auto-selects Bedrock or Anthropic
self.model  = resolve_model_id(model)   # auto-maps to provider-specific model ID
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic[bedrock]` | Claude API + AWS Bedrock support |
| `langgraph` | Multi-Agent state machine |
| `langsmith` | Full-chain tracing and observability |
| `chromadb` | Vector database (RAG + Memory) |
| `rank-bm25` | BM25 sparse index |
| `yfinance` | Stock historical data and company info |
| `fastapi` | Web API framework |
| `uvicorn` | ASGI server (SSE streaming) |
| `typer` | CLI framework |
| `rich` | Terminal formatting |
| Vue 3 + Pinia | Frontend framework + state management |
| Tailwind CSS | Dark finance theme UI |

---

## Notes

- SEC EDGAR API has rate limits (10 req/s); add delays for bulk queries
- ChromaDB data persists in `./data/`; same ticker RAG uses cache; memory accumulates each run
- `--depth detailed` uses more tokens; use `standard` for demos
- LangSmith free tier has monthly trace limits; see [pricing](https://www.langchain.com/langsmith)
- Never commit `.env` to git; STS temporary credentials expire and must be refreshed
- In dev mode, `vite.config.ts` proxies `/api` to `:8000` — no manual CORS setup needed
- yfinance `.news` count varies by ticker activity (typically 5–15); rate-limited responses degrade gracefully to empty array without breaking the pipeline
- `get_live_quote()` uses dual-layer fetch: `fast_info` (cached) + `.info` (full data); pre/after-hours prices are only populated outside regular trading hours
