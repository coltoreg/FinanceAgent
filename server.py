"""
FinAgent FastAPI Server
Provides SSE streaming for LangGraph analysis, parallel comparison,
chat Q&A, and analysis history retrieval.

Usage:
    uvicorn server:app --reload --port 8000
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="FinAgent API",
    description="Multi-Agent Investment Analysis API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    ticker: str
    year: int = 2024
    depth: str = "standard"
    debate_rounds: int = 2
    enable_memory: bool = True


class CompareRequest(BaseModel):
    ticker_a: str
    ticker_b: str
    year: int = 2024
    depth: str = "standard"
    debate_rounds: int = 2
    enable_memory: bool = True


class ChatRequest(BaseModel):
    question: str
    context: dict  # full AnalysisState dict
    history: list[dict] = []


# ─────────────────────────────────────────────
# Step Labels (mirrors main.py STEP_LABELS)
# ─────────────────────────────────────────────

STEP_LABELS: dict[str, str] = {
    "memory_load": "Loading historical analyses from memory...",
    "fundamental": "Fetching SEC EDGAR filings...",
    "technical": "Calculating technical indicators (MA, RSI, MACD)...",
    "sentiment": "Analyzing market sentiment...",
    "valuation": "Computing valuation models (DCF & multiples)...",
    "peer_comparison": "Analyzing competitive peer group...",
    "analyst_initial": "Senior Analyst synthesizing thesis...",
    "critic": "Critic challenging thesis...",
    "analyst_rebuttal": "Analyst responding to critique...",
    "final_report": "Generating final report...",
    "memory_save": "Saving analysis to memory...",
}

STEP_ORDER = list(STEP_LABELS.keys())
TOTAL_STEPS = len(STEP_ORDER)


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────
# Core Analysis Runner (Thread-safe via executor)
# ─────────────────────────────────────────────

async def _stream_analysis(
    ticker: str,
    year: int,
    depth: str,
    debate_rounds: int,
    enable_memory: bool,
) -> AsyncGenerator[str, None]:
    """
    Run LangGraph analysis in a thread pool and yield SSE events.
    Uses asyncio.Queue to bridge the synchronous progress_callback
    and the async generator.
    """
    queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def progress_callback(step_name: str) -> None:
        step_index = STEP_ORDER.index(step_name) if step_name in STEP_ORDER else 0
        event = {
            "type": "progress",
            "ticker": ticker.upper(),
            "step": step_name,
            "step_index": step_index + 1,
            "total_steps": TOTAL_STEPS,
            "label": STEP_LABELS.get(step_name, f"Processing {step_name}..."),
        }
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def run_blocking() -> dict:
        from src.workflow.langgraph_flow import run_analysis
        return run_analysis(
            ticker=ticker,
            year=year,
            depth=depth,
            max_debate_rounds=debate_rounds,
            enable_memory=enable_memory,
            progress_callback=progress_callback,
        )

    # Start the blocking analysis in a thread pool
    future = loop.run_in_executor(None, run_blocking)

    # Stream progress events while waiting
    while not future.done():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.1)
            yield _sse_event(event)
        except asyncio.TimeoutError:
            continue

    # Drain any remaining progress events
    while not queue.empty():
        event = queue.get_nowait()
        yield _sse_event(event)

    # Get result or error
    try:
        result = await future
        yield _sse_event({
            "type": "complete",
            "ticker": ticker.upper(),
            "result": _serialize_state(result),
        })
    except Exception as exc:
        yield _sse_event({
            "type": "error",
            "ticker": ticker.upper(),
            "message": str(exc),
        })


def _serialize_state(state: dict) -> dict:
    """
    Convert AnalysisState to a JSON-serializable dict.
    Ensures debate_transcript list items are plain dicts.
    """
    out = {}
    for k, v in state.items():
        if k == "debate_transcript" and isinstance(v, list):
            out[k] = [dict(msg) for msg in v]
        elif isinstance(v, dict):
            out[k] = v
        else:
            out[k] = v
    return out


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalyzeRequest) -> StreamingResponse:
    """
    SSE endpoint: streams 9 progress events then a 'complete' event
    with the full AnalysisState.
    """
    return StreamingResponse(
        _stream_analysis(
            ticker=req.ticker,
            year=req.year,
            depth=req.depth,
            debate_rounds=req.debate_rounds,
            enable_memory=req.enable_memory,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/compare/stream")
async def compare_stream(req: CompareRequest) -> StreamingResponse:
    """
    SSE endpoint: runs two tickers in parallel, merging their event streams.
    Each event carries a 'ticker' field so the client can route to the right column.
    """
    async def merged_stream() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        async def collect(ticker: str) -> None:
            async for event_str in _stream_analysis(
                ticker=ticker,
                year=req.year,
                depth=req.depth,
                debate_rounds=req.debate_rounds,
                enable_memory=req.enable_memory,
            ):
                await queue.put(event_str)
            await queue.put(None)  # sentinel

        # Launch both streams concurrently
        task_a = asyncio.create_task(collect(req.ticker_a))
        task_b = asyncio.create_task(collect(req.ticker_b))

        done_count = 0
        while done_count < 2:
            item = await queue.get()
            if item is None:
                done_count += 1
            else:
                yield item

        await asyncio.gather(task_a, task_b, return_exceptions=True)

    return StreamingResponse(
        merged_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    """
    Stateless LLM Q&A over the analysis context.
    Uses Claude Haiku for cost efficiency.
    Sends full context + question; returns the assistant's response.
    """
    from src.tools.tracing import get_traced_client, resolve_model_id

    client = get_traced_client()
    ticker = req.context.get("ticker", "the company")
    year = req.context.get("year", "")

    # Build a condensed context summary from the analysis state
    fundamental = req.context.get("fundamental_analysis", "")[:1500]
    technical = req.context.get("technical_analysis", "")[:800]
    sentiment = req.context.get("sentiment_analysis", "")[:600]
    final_report = req.context.get("final_report", "")[:2000]

    system_prompt = f"""You are a senior financial analyst helping explain an AI-generated investment analysis for {ticker} ({year}).

Context from the analysis:
## Fundamental Analysis
{fundamental}

## Technical Analysis
{technical}

## Sentiment Analysis
{sentiment}

## Final Investment Report
{final_report}

Answer questions clearly and concisely. Reference specific data points from the analysis when relevant.
If asked about something not covered in the analysis, say so clearly."""

    messages = []
    for msg in req.history[-10:]:  # keep last 10 messages for context
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": req.question})

    try:
        response = client.messages.create(
            model=resolve_model_id("claude-haiku-4-5-20251001"),
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        return {
            "answer": response.content[0].text,
            "model": response.model,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/history/{ticker}")
async def get_history(ticker: str, limit: int = 10) -> dict:
    """
    Return past analyses for a ticker from the MemoryStore.
    """
    try:
        from src.memory.store import MemoryStore
        store = MemoryStore()
        records = store.load_all(ticker=ticker.upper())[:limit]
        return {
            "ticker": ticker.upper(),
            "records": [
                {
                    "record_id": r.record_id,
                    "timestamp": r.timestamp,
                    "year": r.year,
                    "depth": r.depth,
                    "investment_rating": r.investment_rating,
                    "fundamental_score": r.fundamental_score,
                    "debate_rounds": r.debate_rounds,
                    "model_provider": r.model_provider,
                    "analyst_thesis": r.analyst_thesis[:400],
                }
                for r in records
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "FinAgent API"}
