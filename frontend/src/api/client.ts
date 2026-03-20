const API_BASE = '/api'

export interface ChatRequest {
  question: string
  context: Record<string, any>
  history: Array<{ role: string; content: string }>
}

export interface ChatResponse {
  answer: string
  model: string
}

export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`Chat API error ${res.status}: ${text}`)
  }

  return res.json()
}

export interface HistoryRecord {
  record_id: string
  timestamp: string
  year: number
  depth: string
  investment_rating: string
  fundamental_score: string
  debate_rounds: number
  model_provider: string
  analyst_thesis: string
}

export async function getHistory(ticker: string, limit = 10): Promise<HistoryRecord[]> {
  const res = await fetch(`${API_BASE}/history/${encodeURIComponent(ticker)}?limit=${limit}`)

  if (!res.ok) {
    throw new Error(`History API error ${res.status}`)
  }

  const data = await res.json()
  return data.records ?? []
}

export async function exportReport(
  format: 'pdf' | 'excel',
  context: Record<string, any>,
): Promise<void> {
  const res = await fetch(`${API_BASE}/export/${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`Export failed ${res.status}: ${text}`)
  }

  const blob = await res.blob()
  const ticker = (context.ticker ?? 'report').toUpperCase()
  const ext = format === 'pdf' ? 'pdf' : 'xlsx'
  const filename = `${ticker}_analysis.${ext}`

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
