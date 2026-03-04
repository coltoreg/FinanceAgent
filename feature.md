根據目前的架構，以下是可以增加的功能，按「投資報酬率」（開發成本 vs 面試展示價值）排序：  
                                                            
  ---                                                                                       
  高價值、容易實作                                          
                                                                                            
  1. Portfolio Agent（投資組合分析）                        

  多個股票同時分析，輸出整體風險集中度、相關性矩陣、配置建議
  新增: src/agents/portfolio.py
  前端: PortfolioView.vue（輸入多股票代號）

  2. Screener 模式（批次篩選）

  輸入一個產業（e.g. "AI Chips"），自動列出 5-10 支股票並快速評分
  新增: POST /api/screen
  前端: ScreenerPanel.vue（表格顯示評分排名）

  3. PDF / Excel 匯出

  分析完成後一鍵下載報告
  後端: weasyprint 或 openpyxl
  前端: 下載按鈕

  4. 價格警報 / Watch List

  設定目標價，當股價突破時推送通知（Webhook / Email）
  新增: src/tools/alert_manager.py

  ---
  中等價值、有難度

  5. Macro Agent（總體經濟）

  分析聯準會利率、通膨、殖利率曲線對個股的影響
  數據源: FRED API（免費）
  新增: src/agents/macro.py

  6. Options Sentiment Agent

  分析期權市場的 Put/Call Ratio、IV Skew、隱含波動率
  數據源: yfinance options chain（已有）
  新增: src/agents/options.py

  7. Earnings Call Transcript 分析

  抓取法說會逐字稿，分析管理層語氣、關鍵詞變化
  數據源: Motley Fool / Alpha Vantage API
  新增: src/tools/earnings_transcript.py

  8. 回測系統（Backtesting）

  驗證過去 AI 評級的準確性（e.g. "BUY 後 12 個月實際漲了多少"）
  新增: src/tools/backtest.py（用 yfinance 歷史價格）
  前端: BacktestPanel.vue（勝率、年化報酬圖表）

  ---
  進階功能

  9. 競爭對手比較 Agent（Peer Comparison）

  自動找出同行業競爭者，並排比較估值倍數
  新增: src/agents/peer_comparison.py
  前端: PeerTable.vue

  10. 新聞實時監控 + RAG 更新

  定時爬取最新新聞並更新向量資料庫，讓 RAG 知識保持最新
  新增: src/tools/news_scraper.py（用 feedparser）
  排程: APScheduler 或 cron job

  11. 使用者認證 + 個人化

  JWT 登入、儲存個人 Watchlist、分析歷史雲端同步
  後端: FastAPI + SQLite/PostgreSQL
  前端: 登入頁、個人頁

  ---
  總結建議

  ┌─────────┬───────────────────────┬────────────────────────────────────────────┐
  │ 優先級  │         功能          │                    原因                    │
  ├─────────┼───────────────────────┼────────────────────────────────────────────┤
  │ 🔴 最高 │ Macro Agent           │ 面試展示「多維度分析」能力                 │
  ├─────────┼───────────────────────┼────────────────────────────────────────────┤
  │ 🔴 最高 │ Peer Comparison Agent │ 估值分析必備，且和現有 ValuationAgent 互補 │
  ├─────────┼───────────────────────┼────────────────────────────────────────────┤
  │ 🟡 中   │ PDF 匯出              │ 實用性高，開發快（1-2小時）                │
  ├─────────┼───────────────────────┼────────────────────────────────────────────┤
  │ 🟡 中   │ 回測系統              │ 驗證 AI 準確性，面試亮點                   │
  ├─────────┼───────────────────────┼────────────────────────────────────────────┤
  │ 🟢 低   │ Portfolio Agent       │ 架構複雜，但商業價值最高                   │
  └─────────┴───────────────────────┴────────────────────────────────────────────┘

  ---
  你想優先實作哪一個？
