import { useAnalysisStore } from '@/stores/analysis'

const API_BASE = '/api'

export function useSSE() {
  const store = useAnalysisStore()

  async function streamAnalysis(params: {
    ticker: string
    year: number
    depth: string
    debate_rounds: number
    enable_memory: boolean
  }) {
    store.startAnalysis(params.ticker, 'A')

    const response = await fetch(`${API_BASE}/analyze/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })

    if (!response.ok) {
      store.handleError({ ticker: params.ticker.toUpperCase(), message: `HTTP ${response.status}` })
      return
    }

    await _readStream(response)
  }

  async function streamCompare(params: {
    ticker_a: string
    ticker_b: string
    year: number
    depth: string
    debate_rounds: number
    enable_memory: boolean
  }) {
    store.startAnalysis(params.ticker_a, 'A')
    store.startAnalysis(params.ticker_b, 'B')

    const response = await fetch(`${API_BASE}/compare/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })

    if (!response.ok) {
      const msg = `HTTP ${response.status}`
      store.handleError({ ticker: params.ticker_a.toUpperCase(), message: msg })
      store.handleError({ ticker: params.ticker_b.toUpperCase(), message: msg })
      return
    }

    await _readStream(response)
  }

  async function _readStream(response: Response) {
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        try {
          const event = JSON.parse(raw)
          _dispatch(event)
        } catch {
          // malformed JSON — skip
        }
      }
    }
  }

  function _dispatch(event: any) {
    switch (event.type) {
      case 'progress':
        store.handleProgress(event)
        break
      case 'complete':
        store.handleComplete(event)
        break
      case 'error':
        store.handleError(event)
        break
    }
  }

  return { streamAnalysis, streamCompare }
}
