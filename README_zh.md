[English](./README.md) | 中文

# FinAgent — 多智能體股價預測與基本面分析系統

> 基於 LangGraph 的 Multi-Agent 投資分析框架，整合 SEC EDGAR RAG、yfinance 技術分析與即時股價/新聞、DCF 估值模型、同業競爭對比、對抗式辯論機制與跨會話記憶，透過 AWS Bedrock 或 Anthropic API 驅動 Claude 模型，提供 **CLI** 與 **Vue 3 Web UI** 雙介面，並以 LangSmith 全程追蹤 Agent 推理過程。

---

## 系統架構

```
User（CLI 或 Web UI）
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                       │
│                                                              │
│  [memory_load] ──► 從 MemoryStore 載入歷史分析               │
│        │                                                     │
│        ▼                                                     │
│  ┌───────────┐  ┌──────────────┐  ┌────────────┐            │
│  │Fundamental│  │  Technical   │  │ Sentiment  │            │
│  │  Agent    │  │   Agent      │  │   Agent    │            │
│  │SEC EDGAR  │  │  yfinance    │  │  (Haiku)   │            │
│  │RAG+三表JSON│  │MA/RSI/MACD   │  │ 即時新聞   │            │
│  │           │  │即時股價/新聞  │  │ 情緒分析   │            │
│  └─────┬─────┘  └──────┬───────┘  └─────┬──────┘            │
│        └───────────────┴────────────────┘                   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ┌─────────────────────┐  ┌──────────────────────┐    │   │
│  │ │  Valuation Agent    │  │ Peer Comparison Agent │    │   │
│  │ │  DCF + 相對倍數估值  │  │  5 同業競爭對比分析  │    │   │
│  │ │  P/E EV/EBITDA P/FCF│  │  yfinance 即時指標   │    │   │
│  │ └─────────────────────┘  └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│             ┌───────────────────────┐                        │
│             │  Senior Analyst Agent │ ← 帶入歷史記憶 context  │
│             │  初步投資論文生成       │                        │
│             └───────────┬───────────┘                        │
│                         │◄──────────────────────┐            │
│                         ▼                       │            │
│             ┌───────────────────────┐           │            │
│             │    Critic Agent       │───────────┘            │
│             │  對抗式質疑 (N 輪)     │   debate loop          │
│             └───────────────────────┘                        │
│                         │                                    │
│                         ▼                                    │
│             ┌───────────────────────┐                        │
│             │    Final Report       │                        │
│             │  投資建議 + 三表摘要   │                        │
│             └───────────────────────┘                        │
│                         │                                    │
│  [memory_save] ──► 將本次結果存入 MemoryStore                │
└──────────────────────────────────────────────────────────────┘
        │
        ▼（Web 模式）
┌─────────────────────────────────────────────────────────┐
│  FastAPI server.py (port 8000)                          │
│   POST /api/analyze/stream  ── SSE 即時串流進度         │
│   POST /api/compare/stream  ── 雙股並行對比             │
│   POST /api/chat            ── LLM Q&A                 │
│   GET  /api/history/{ticker}── 歷史記錄查詢             │
│   POST /api/export/pdf      ── 下載 PDF 報告            │
│   POST /api/export/excel    ── 下載 Excel 活頁簿        │
└──────────────────────┬──────────────────────────────────┘
                       │ SSE / JSON
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Vue 3 前端 (port 5173)                                       │
│  Single / Compare 模式 │ 即時進度條 │ 7-Tab 分析面板          │
│  即時股價欄 (MarketDataBar)                                   │
│  Report │ Financials │ Valuation │ Peers │ Debate │ News │ Sources │
│  PDF 匯出按鈕 │ Excel 匯出按鈕                                │
│  ChatPanel (浮動 Q&A 側抽屜)                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 核心功能

| 功能 | 說明 |
|------|------|
| **SEC EDGAR RAG** | 從 XBRL API 提取 30+ 財務指標，ChromaDB + BM25 Hybrid Search，Reciprocal Rank Fusion 融合排序 |
| **技術分析** | yfinance 歷史數據，Claude Function Calling 計算 MA50/200、RSI、MACD，自動判斷超買/超賣 |
| **即時股價與新聞** | yfinance 即時報價（現價、漲跌幅、52 週區間、成交量、市值、盤前/盤後價）+ 近期新聞 10 則，前端 MarketDataBar 一目了然 |
| **Sentiment Agent 升級** | Sentiment Agent 使用 `technical_node` 預先抓取的真實新聞標題分析市場情緒，不再依賴 LLM 訓練知識 |
| **DCF 與相對估值** | Valuation Agent 使用 Claude Tool Use 輸出結構化 DCF 模型（5 年 FCF 預測、WACC、終值）及 P/E、EV/EBITDA、P/S、P/FCF、P/B 相對倍數，對比行業平均，得出 EXPENSIVE / FAIR / CHEAP 結論 |
| **同業競爭分析** | Peer Comparison Agent 以 Claude Haiku 識別 5 家同業，透過 yfinance 抓取即時指標（市值、PE、毛利率、成長率），Tool Use 輸出結構化競爭定位（INDUSTRY_LEADER / COMPETITIVE / LAGGARD）及敘事分析 |
| **對抗式辯論** | Analyst 生成初步論文，Critic 提出質疑（債務風險、過高估值、技術信號），多輪辯論後產出最終報告 |
| **財務三表 JSON** | Claude Tool Use 強制輸出結構化 JSON：損益表、資產負債表、現金流量表，含衍生指標（成長率、毛利率、ROE/ROA） |
| **RAG 來源索引** | 每筆分析追蹤 RAG 檢索文件（doc ID、RRF 分數、觸發查詢、內容預覽），可點擊直連 SEC EDGAR 原始申報頁面 |
| **跨會話記憶** | ChromaDB 持久化儲存每次分析結果，下次分析同一 ticker 自動載入歷史論文，追蹤評級演變與基本面趨勢 |
| **PDF / Excel 匯出** | 一鍵下載完整分析報告——PDF（封面、報告、財務三表、估值、同業對比、辯論記錄）及 Excel 活頁簿（5 個分頁：Summary、Financial Statements、Valuation、Peer Comparison、Debate Transcript） |
| **雙 Provider** | 一個 env var 切換 `LLM_PROVIDER=anthropic` 或 `LLM_PROVIDER=bedrock`，不改任何 agent 代碼 |
| **LangSmith Tracing** | 全鏈路追蹤：RAG 檢索步驟、LLM 呼叫、Tool Use、辯論輪次，面試時可即時展示 Agent 思考過程 |
| **Web UI** | Vue 3 + SSE 即時串流進度、Single / Compare 雙模式、7-Tab 分析面板、PDF/Excel 匯出按鈕、浮動 AI 問答側抽屜 |

---

## 技術棧

```
LLM            Claude Sonnet 4.6 / Haiku 4.5 (via Anthropic API or AWS Bedrock)
Orchestration  LangGraph (StateGraph + conditional edges + debate loop)
RAG            ChromaDB (dense) + BM25 (sparse) → RRF fusion
Memory         ChromaDB (semantic search) + JSON files (full record backup)
Financial Data SEC EDGAR XBRL API (30+ GAAP concepts) + yfinance (歷史/即時/新聞)
Tracing        LangSmith (wrap_anthropic + @traceable decorators)
Backend API    FastAPI + uvicorn (SSE streaming)
Export         fpdf2（PDF 生成）+ openpyxl（Excel 活頁簿）
Frontend       Vue 3 + Pinia + Tailwind CSS + Vite
CLI            Typer + Rich (表格、進度條、彩色輸出)
Language       Python 3.11+ / TypeScript
```

---

## 專案結構

```
FinAgent/
├── main.py                          # CLI 入口 (typer)：analyze / history / memory-stats
├── server.py                        # FastAPI 後端：SSE 串流 / Chat / History
├── pyproject.toml                   # 依賴管理
├── .env.example                     # 環境變數模板
│
├── src/
│   ├── agents/
│   │   ├── fundamental.py           # SEC RAG Agent（三表 JSON + RAG 來源）
│   │   ├── technical.py             # yfinance Agent（Function Calling）
│   │   ├── valuation.py             # Valuation Agent（DCF + 相對倍數估值）
│   │   ├── peer_comparison.py       # Peer Comparison Agent（5 同業競爭分析）
│   │   ├── analyst.py               # Senior Analyst（論文生成 + 辯論 + 記憶整合）
│   │   └── critic.py                # Critic（對抗式質疑）
│   │
│   ├── memory/
│   │   └── store.py                 # MemoryStore + AnalysisRecord（跨會話持久化）
│   │
│   ├── tools/
│   │   ├── sec_retriever.py         # HybridRetriever + SEC EDGAR API
│   │   ├── stock_utils.py           # MA / RSI / MACD 計算 + get_live_quote() + get_stock_news()
│   │   ├── exporter.py              # PDF（fpdf2）+ Excel（openpyxl）報告生成
│   │   └── tracing.py               # LangSmith 設定 + Provider 切換 + resolve_model_id
│   │
│   └── workflow/
│       └── langgraph_flow.py        # StateGraph + AnalysisState + memory nodes + debate routing
│
├── frontend/                        # Vue 3 前端
│   ├── index.html
│   ├── package.json                 # Vue 3, Pinia, Tailwind, Vite
│   ├── vite.config.ts               # Dev proxy → :8000
│   ├── tailwind.config.js           # 深色 finance 主題
│   └── src/
│       ├── main.ts
│       ├── style.css                # Tailwind + 共用元件樣式
│       ├── App.vue                  # 根佈局 + 模式切換 + 浮動 Chat 按鈕
│       ├── stores/
│       │   └── analysis.ts          # Pinia 狀態管理（SSE 事件 → 狀態）
│       ├── composables/
│       │   └── useSSE.ts            # fetch + ReadableStream SSE 解析
│       ├── api/
│       │   └── client.ts            # sendChat() / getHistory() / exportReport()
│       └── components/
│           ├── TickerForm.vue       # 股票代碼輸入表單（Single / Compare 切換）
│           ├── ProgressTracker.vue  # 11 步驟進度條
│           ├── AnalysisPanel.vue    # 7-Tab 面板（Report / Financials / Valuation / Peers / Debate / News / Sources）
│           ├── FinancialTables.vue  # 財務三表格
│           ├── ValuationPanel.vue   # DCF + 相對倍數估值面板
│           ├── PeerComparisonPanel.vue # 同業競爭對比表格 + 定位分析
│           ├── DebateTranscript.vue # Analyst / Critic 對話氣泡
│           ├── MarketDataBar.vue    # 即時股價欄（現價、漲跌、52W 區間、成交量、市值）
│           ├── NewsFeed.vue         # 近期新聞列表（可點擊連結、publisher badge、time-ago）
│           ├── ComparisonView.vue   # 雙欄並列 + 摘要對比表
│           ├── ChatPanel.vue        # 浮動 Q&A 側抽屜（Teleport）
│           └── SourcesPanel.vue     # RAG 來源索引 + SEC EDGAR 連結
│
└── data/
    ├── chroma/                      # SEC RAG 向量索引（ChromaDB）
    └── memory/
        ├── chroma/                  # 分析記憶向量索引（ChromaDB）
        └── records/                 # 完整分析記錄 JSON（{record_id}.json）
```

---

## 快速開始

### 1. 安裝依賴

```bash
pip install -e .

# 前端依賴
cd frontend && npm install
```

### 2. 設定環境變數

```bash
cp .env.example .env
```

**選擇 Provider：**

**Option A — AWS Bedrock（推薦）**
```dotenv
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**Option B — Anthropic 直連**
```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**啟用 LangSmith 追蹤（選用，強烈建議用於展示）**
```dotenv
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=finagent-demo
```

---

## 執行方式

### CLI 模式

```bash
# 基本用法（自動載入/儲存記憶）
python main.py --ticker NVDA --year 2024

# 完整輸出：三表 + 辯論記錄 + 各 Agent 分析
python main.py --ticker AAPL --year 2024 --depth detailed \
  --financials --sections --transcript

# 縮短辯論輪次（加快速度）
python main.py --ticker MSFT --year 2024 --rounds 1

# 不使用記憶（一次性分析）
python main.py --ticker TSLA --year 2024 --no-memory
```

### Web UI 模式

```bash
# Terminal 1 — 啟動後端 API
uvicorn server:app --reload --port 8000

# Terminal 2 — 啟動前端
cd frontend && npm run dev
# 開啟 http://localhost:5173
```

---

## Web UI 功能

### 介面佈局

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
│ Open  52W: $400─$950      │ Open  52W: $164─$199         │
│ Mkt Cap $2.15T  Vol 45M  │ Mkt Cap $2.95T  Vol 55M     │
│ [Report][Financials]     │ [Report][Financials]         │
│ [Valuation][Peers]       │ [Valuation][Peers]           │
│ [Debate][News 10][Sources]│ [Debate][News 8][Sources]   │
│ <markdown report>        │ <markdown report>            │
├─────────────────────────────────────────────────────────┤
│ Comparison: NVDA BUY STRONG | AAPL HOLD MODERATE        │
└─────────────────────────────────────────────────────────┘
             [💬 Ask AI about this analysis]
```

### 7-Tab 分析面板

| Tab | 內容 |
|-----|------|
| **Report** | 最終投資報告（Markdown 渲染，含 Analyst + Critic 觀點） |
| **Financials** | 財務三表：損益表、資產負債表、現金流量表（多年對比） |
| **Valuation** | DCF 模型（5 年 FCF 預測、WACC、終值、每股內在價值 vs 現價）+ 相對倍數表（P/E、EV/EBITDA、P/S、P/FCF、P/B 各含行業均值與評級） |
| **Peers** | 5 家同業競爭對比表格（市值、PE、毛利率、成長率、分析師目標價）+ 競爭定位評語（INDUSTRY_LEADER / COMPETITIVE / LAGGARD） |
| **Debate** | Analyst ↔ Critic 完整辯論逐字稿（可展開/收合） |
| **News** `10` | Yahoo Finance 近期新聞（標題連結、publisher badge、time-ago、相關 ticker tags） |
| **Sources** | RAG 來源索引：data source badges + 每份檢索文件的 doc ID、RRF 分數、內容預覽、可點擊的 SEC EDGAR 直連 |

### MarketDataBar 即時股價欄

分析完成後顯示於 Tab 列上方，包含：

| 欄位 | 說明 |
|------|------|
| 現價 + 漲跌 | `▲+2.34 (+0.27%)`，綠漲紅跌，自動顯示箭頭 |
| Market State | `Market Open` / `Pre-Market` / `After-Hours` / `Market Closed`（對應顏色 badge） |
| 盤前/盤後價 | 非正常交易時段自動顯示 Pre-market / After-hours 報價 |
| 52W Range | 視覺化進度條，標示當前股價在 52 週高低區間的位置 |
| 市值 | 自動格式化為 T / B / M |
| 成交量 | 若 ≥ 1.5× 均量，以黃色高亮顯示 |
| 更新時間 | 顯示資料抓取的本地時間（含時區） |

### Sources Tab 詳細說明

Sources Tab 顯示 Fundamental Agent 在 RAG 檢索時實際使用的資料來源：

```
Data Sources
  [SEC EDGAR XBRL ↗]  [Hybrid RAG]  [yfinance ↗]
  [SEC EDGAR Filings (CIK 0001045810) ↗]
  [XBRL Raw Data (JSON) ↗]

RAG Retrieved Documents  (Hybrid Search: ChromaDB + BM25 + RRF)

  ┌─────────────────────────────────────────────────────┐
  │ [XBRL Metric]  NVDA_revenue          ████░ 0.0142  │
  │ NVDA Revenue (annual, USD): 2024: $60,922,000,000.. │
  │ 🔍 "NVDA revenue growth net income profit margin"   │
  │                                         XBRL Data ↗ │
  ├─────────────────────────────────────────────────────┤
  │ [SEC 10-K]  NVDA_2024-01-29_10-K     █████ 0.0156  │
  │ SEC 10-K Filing for NVDA filed on 2024-01-29...     │
  │ 🔍 "NVDA risk factors Item 1A debt obligations"     │
  │                                   View on EDGAR ↗   │
  └─────────────────────────────────────────────────────┘
```

### 匯出功能（PDF & Excel）

分析完成後，面板標題列會顯示 **PDF** 和 **Excel** 匯出按鈕（與「Ask AI」並排）：

```
NVDA  [STRONG BUY]  [STRONG]    [PDF]  [Excel]  [Ask AI]
```

**PDF 報告** — 由 `fpdf2` 生成的多頁文件：

| 章節 | 內容 |
|------|------|
| 封面 | Ticker、投資評級 badge、即時股價摘要、生成時間戳 |
| 投資報告 | 完整最終報告（去除 Markdown 標記） |
| 財務三表 | 損益表、資產負債表、現金流量表 |
| 估值分析 | DCF 模型表格 + 相對倍數表格 + 方法論說明 |
| 同業競爭 | 同業指標對比表格 + 競爭優劣勢列表 |
| 辯論記錄 | Analyst ↔ Critic 完整辯論逐字稿（按輪次） |

**Excel 活頁簿** — 由 `openpyxl` 生成的多分頁 `.xlsx`：

| 分頁 | 內容 |
|------|------|
| Summary | 關鍵指標（評級、股價、52 週區間、市值）+ 完整報告文字 |
| Financial Statements | 損益表、資產負債表、現金流量表（各含子標題） |
| Valuation | DCF 模型 + 相對倍數估值 |
| Peer Comparison | 同業指標對比表 + 競爭定位 |
| Debate Transcript | 按輪次顯示的辯論記錄，Analyst/Critic 以不同顏色區分 |

檔案直接在瀏覽器下載，命名為 `{TICKER}_analysis.pdf` / `{TICKER}_analysis.xlsx`。

---

### Chat Panel

點擊「Ask AI」後開啟右側浮動抽屜，以 Claude Haiku 回答關於當前分析結果的任何問題：

```
Ask AI — NVDA

  > What are the biggest risks for NVDA?
  > Why is the investment rating BUY?
  > Explain the revenue trend in simple terms
  > What does the debt/equity ratio indicate?

  [你的問題                              ] [▶]
```

---

## API 端點

| Method | Path | 說明 |
|--------|------|------|
| `POST` | `/api/analyze/stream` | SSE 串流：單一 ticker 分析，推送 11 個進度事件 + 最終結果 |
| `POST` | `/api/compare/stream` | SSE 串流：兩個 ticker 並行分析，事件以 `ticker` 欄位區分 |
| `POST` | `/api/chat` | JSON：以分析結果為 context 的 LLM Q&A |
| `GET` | `/api/history/{ticker}` | JSON：從 MemoryStore 取得歷史分析記錄 |
| `POST` | `/api/export/pdf` | Binary：生成並回傳 PDF 投資報告 |
| `POST` | `/api/export/excel` | Binary：生成並回傳 Excel 活頁簿（`.xlsx`） |
| `GET` | `/api/health` | 健康檢查 |

### SSE 事件格式

```json
// 進度事件（11 步驟）
{"type":"progress","ticker":"NVDA","step":"fundamental","step_index":2,"total_steps":11,"label":"Fetching SEC EDGAR filings..."}

// 完成事件（含完整 AnalysisState）
{"type":"complete","ticker":"NVDA","result":{...}}

// 錯誤事件
{"type":"error","ticker":"NVDA","message":"..."}
```

---

## CLI 命令總覽

### `analyze`（主命令）

```bash
python main.py [OPTIONS]
```

| 參數 | 預設 | 說明 |
|------|------|------|
| `--ticker` `-t` | 必填 | 股票代碼（NVDA、AAPL、MSFT 等） |
| `--year` `-y` | `2024` | 財政年度 |
| `--depth` `-d` | `standard` | 分析深度：`standard` / `detailed` |
| `--rounds` `-r` | `2` | Analyst ↔ Critic 辯論輪次（1–3） |
| `--financials` `-f` | `False` | 顯示財務三表 |
| `--sections` | `False` | 顯示各 Agent 原始分析段落 |
| `--transcript` | `False` | 顯示完整對抗式辯論記錄 |
| `--no-memory` | `False` | 跳過記憶載入與儲存 |

### `history` / `memory-stats`

```bash
python main.py history NVDA
python main.py history NVDA --limit 5
python main.py memory-stats
```

---

## 記憶系統設計

### 資料流

```
第 1 次分析 NVDA：
  memory_load (0 records) → [analysis] → memory_save → record_id: a1b2c3d4

第 2 次分析 NVDA（三個月後）：
  memory_load (1 record) → analyst_initial (帶入歷史 context)
    → "Has investment case improved vs. prior analysis?"
    → [analysis] → memory_save → record_id: e5f6g7h8
```

### 儲存架構

```
MemoryStore
  ├── ChromaDB (data/memory/chroma/)
  │     語義向量索引，支援跨 ticker 相似性搜尋
  │     metadata: ticker, year, timestamp, rating, score
  │
  └── JSON files (data/memory/records/{record_id}.json)
        完整記錄：三表數據、全文報告、辯論記錄、RAG 來源、模型資訊
```

---

## 財務三表輸出格式

Fundamental Agent 使用 Claude Tool Use 強制輸出以下結構（節錄）：

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

## LangSmith 追蹤架構

設定 `LANGCHAIN_TRACING_V2=true` 後，前往 [smith.langchain.com](https://smith.langchain.com) 查看完整的 Agent 推理樹：

```
LangGraph Run: NVDA (root trace)
├─ memory_load                         ← 載入歷史記憶
├─ fundamental                         ← LangGraph node
│   ├─ sec_xbrl_fetch                  ← @traceable (SEC API 呼叫 → CIK 解析 → 30+ XBRL 概念)
│   ├─ fundamental_rag_retrieval       ← @traceable (4 queries → ChromaDB + BM25 → RRF)
│   ├─ extract_financial_statements    ← @traceable (tool_use → JSON 三表)
│   └─ fundamental_narrative_analysis  ← @traceable (敘事分析)
├─ technical                           ← LangGraph node
│   ├─ Tool: get_technical_indicators  ← function calling
│   ├─ Tool: get_company_overview
│   ├─ get_live_quote()                ← yfinance fast_info（即時報價）
│   └─ get_stock_news()               ← yfinance .news（近 10 則新聞）
├─ sentiment                           ← LangGraph node（使用真實新聞標題分析）
├─ valuation                           ← LangGraph node
│   ├─ extract_valuation_metrics (tool_use) ← DCF + P/E + EV/EBITDA + P/S + P/FCF + P/B
│   └─ generate_narrative              ← 估值敘事分析
├─ peer_comparison                     ← LangGraph node
│   ├─ identify_peers (Haiku)          ← 識別 5 家同業 ticker
│   ├─ fetch_all_metrics               ← yfinance 批次抓取各同業指標
│   ├─ extract_peer_metrics (tool_use) ← 結構化競爭定位輸出
│   └─ generate_narrative              ← 競爭分析敘事
├─ analyst_initial                     ← LangGraph node（含歷史記憶 + 估值 + 同業 context）
├─ critic  (Round 1)                   ← LangGraph node
├─ analyst_rebuttal (Round 1)          ← LangGraph node
├─ critic  (Round 2)                   ← LangGraph node
├─ analyst_rebuttal (Round 2)          ← LangGraph node
├─ final_report                        ← LangGraph node
└─ memory_save                         ← 儲存本次結果
```

每個 LLM span 顯示：完整 prompt、model ID、輸出、token 用量、延遲。

---

## AWS Bedrock 設定

### 目前使用的預設模型 ID

| 用途 | Bedrock Inference Profile ID |
|------|------------------------------|
| Sonnet（主要推理） | `us.anthropic.claude-sonnet-4-6` |
| Haiku（情緒分析 / Chat） | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Opus（可選） | `us.anthropic.claude-opus-4-6-v1` |

在 `.env` 中覆蓋：

```dotenv
BEDROCK_MODEL_SONNET=us.anthropic.claude-sonnet-4-6
BEDROCK_MODEL_HAIKU=us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_MODEL_OPUS=us.anthropic.claude-opus-4-6-v1
```

### AWS Credential Chain（優先順序）

1. `.env` 中的 `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`（+ `AWS_SESSION_TOKEN`）
2. `~/.aws/credentials`（透過 `AWS_PROFILE`）
3. EC2 / ECS / Lambda IAM Role

---

## 開發指南

### RAG 檢索機制

```
Query
  │
  ├─► ChromaDB (dense)  → 語義相似度排序 → Top-K
  ├─► BM25 (sparse)     → 關鍵字匹配排序 → Top-K
  │
  └─► Reciprocal Rank Fusion
        score = α/(k + rank_dense) + (1-α)/(k + rank_sparse)
        α=0.5 (可調整), k=60 (RRF 常數)
```

### 即時股價與新聞抓取

`technical_node` 在執行技術分析的同時，並行呼叫以下兩個工具預先抓取數據：

```python
# src/tools/stock_utils.py

get_live_quote(ticker)
# 回傳: price, change, change_pct, market_state,
#       pre_market_price, post_market_price,
#       week52_high, week52_low, market_cap,
#       volume, avg_volume, currency, fetched_at

get_stock_news(ticker, max_items=10)
# 回傳: [{title, publisher, url, published_at (ISO), related_tickers}]
```

抓取的數據存入 `AnalysisState`：
- `live_price` → 前端 `MarketDataBar` 顯示
- `news_items` → 前端 `NewsFeed` 顯示 + `sentiment_node` 作為新聞 context

`sentiment_node` 改用真實新聞分析情緒（而非 LLM 訓練知識）：

```python
# 以實際標題建構 news_context
news_lines = [f"- [{pub_date}] {item['title']} — {item['publisher']}" ...]
# 傳入 Haiku，產出 BULLISH/BEARISH/NEUTRAL + 關鍵主題
```

---

### 估值模型（Valuation Agent）

`valuation_node` 在 sentiment 之後、analyst_initial 之前執行，為 Analyst 提供量化估值 context：

```python
# src/agents/valuation.py

ValuationAgent.analyze(ticker, year, financial_statements, live_price)
# 輸出:
#   valuation_data     → 結構化 JSON（前端 ValuationPanel）
#   valuation_analysis → 敘事文字（注入 Analyst prompt）

# DCF 假設：
#   - Base FCF from financial statements
#   - 5 年成長率 = revenue_growth_yoy
#   - 終值成長率 = 2.5%
#   - WACC = 10%
#   - 行業平均倍數來自 Claude 訓練知識（prompt 中注明近似值）
```

### 同業競爭分析（Peer Comparison Agent）

`peer_comparison_node` 使用 Claude Haiku 識別同業，成本最小化：

```python
# src/agents/peer_comparison.py

PeerComparisonAgent.analyze(ticker, year, financial_statements, live_price)
# 步驟：
#   1. Haiku → 識別 5 家同業 ticker
#   2. yfinance → 批次抓取各同業 P/E、毛利率、成長率、市值、分析師目標價
#   3. Tool Use → 輸出結構化競爭定位 JSON
#   4. Haiku → 生成競爭分析敘事
#
# 輸出:
#   peer_data     → 結構化 JSON（前端 PeerComparisonPanel）
#   peer_analysis → 敘事文字（注入 Analyst prompt）
```

### RAG 來源追蹤

每份被檢索的文件都會記錄在 `AnalysisState.rag_sources`：

```python
{
    "id": "NVDA_2024-01-29_10-K",   # 文件唯一 ID
    "query": "NVDA risk factors...", # 觸發此文件的查詢
    "score": 0.0156,                 # RRF 融合分數
    "content": "SEC 10-K Filing...", # 文件內容預覽（前 300 字）
}
```

前端 Sources Tab 以 SEC CIK 自動生成可點擊的直連連結。

### 對抗辯論狀態機

```python
# 條件路由：繼續辯論 or 進入報告
def should_continue_debate(state) -> str:
    return "continue" if state["debate_round"] <= max_rounds else "finalize"
```

### Provider 切換不影響 Agent 代碼

```python
# 所有 Agent 統一使用
self.client = get_traced_client()       # 自動選擇 Bedrock or Anthropic
self.model  = resolve_model_id(model)   # 自動映射 provider-specific model ID
```

---

## 依賴套件

| 套件 | 用途 |
|------|------|
| `anthropic[bedrock]` | Claude API + AWS Bedrock 支援 |
| `langgraph` | Multi-Agent 狀態機 |
| `langsmith` | 全鏈路追蹤與可觀測性 |
| `chromadb` | 向量資料庫（RAG + Memory） |
| `rank-bm25` | BM25 稀疏索引 |
| `yfinance` | 股票歷史數據與公司資訊 |
| `fastapi` | Web API 框架 |
| `uvicorn` | ASGI 伺服器（SSE 串流支援） |
| `fpdf2` | PDF 報告生成（純 Python） |
| `openpyxl` | Excel 活頁簿生成 |
| `typer` | CLI 框架 |
| `rich` | 終端美化輸出 |
| Vue 3 + Pinia | 前端框架 + 狀態管理 |
| Tailwind CSS | 深色 finance 主題 UI |

---

## 注意事項

- SEC EDGAR API 有速率限制（10 req/s），大量查詢建議加入延遲
- ChromaDB 資料持久化在 `./data/`，同一 ticker 第二次執行 RAG 會使用快取；記憶則每次累積
- `--depth detailed` 使用更多 token，建議面試展示時用 `standard`
- LangSmith 免費方案有每月 trace 數量限制，請參閱 [官方定價](https://www.langchain.com/langsmith)
- `.env` 請勿提交至 git；STS 臨時憑證過期後須重新取得
- 前端開發模式下，`vite.config.ts` 已設定 `/api` proxy 至 `:8000`，無需手動處理 CORS
- yfinance `.news` 回傳的新聞數量依 ticker 熱度而異（通常 5–15 則）；若遇速率限制，`news_items` 會退化為空陣列，不影響主流程
- `get_live_quote()` 使用 `fast_info`（快速快取）+ `.info`（完整資料）雙層抓取；盤前/盤後報價僅在非正常交易時段有值
