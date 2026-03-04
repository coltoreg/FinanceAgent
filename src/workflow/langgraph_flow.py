"""
LangGraph workflow: Multi-agent state machine for investment analysis.
Defines State structure, Node logic, and adversarial debate loop.

LangSmith integration:
  - Call setup_langsmith() before build_graph() to enable full tracing.
  - LangGraph automatically creates a root trace per run when
    LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY is set.
  - Each node appears as a child span; Anthropic API calls (via wrap_anthropic)
    appear as grandchild spans showing prompts, completions, and token usage.
  - The hybrid RAG retrieval spans appear nested under the fundamental node,
    showing exactly which documents were retrieved and their RRF scores.

Memory integration:
  - memory_load  (first node) — loads past analyses from MemoryStore into state
  - memory_save  (last node)  — persists current result back to MemoryStore
  - Pass enable_memory=False to run_analysis() to skip both nodes.
"""

from typing import TypedDict, Annotated, Optional
import operator
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from src.agents.fundamental import FundamentalAgent
from src.agents.technical import TechnicalAgent
from src.agents.analyst import AnalystAgent
from src.agents.critic import CriticAgent
from src.agents.valuation import ValuationAgent
from src.agents.peer_comparison import PeerComparisonAgent
from src.tools.tracing import setup_langsmith

# Load .env and configure LangSmith on module import
load_dotenv()
setup_langsmith()


# ─────────────────────────────────────────────
# State Definition
# ─────────────────────────────────────────────

class DebateMessage(TypedDict):
    round: int
    speaker: str   # "analyst" | "critic"
    content: str


class AnalysisState(TypedDict):
    # Input parameters
    ticker: str
    year: int
    depth: str

    # Memory
    memory_context: str         # formatted past analyses injected into Analyst prompt
    past_analyses_count: int    # number of historical records loaded
    memory_record_id: str       # record_id assigned after saving current result

    # Worker agent outputs
    fundamental_analysis: str
    financial_statements: dict  # structured JSON: income stmt / balance sheet / cash flow
    technical_analysis: str
    sentiment_analysis: str

    # Market data (live quote + news from yfinance)
    live_price: dict            # {price, change_pct, market_state, week52_high, ...}
    news_items: list            # [{title, publisher, url, published_at}]

    # Data provenance (RAG sources + CIK for SEC EDGAR links)
    rag_sources: list           # [{id, query, score, content}] from hybrid retrieval
    data_sources: list          # e.g. ["SEC EDGAR XBRL", "yfinance", ...]
    ticker_cik: str             # SEC CIK number (zero-padded 10-digit)

    # Valuation outputs
    valuation_analysis: str   # narrative for Analyst context
    valuation_data: dict      # structured JSON for frontend ValuationPanel

    # Peer comparison outputs
    peer_analysis: str        # narrative for Analyst context
    peer_data: dict           # structured JSON for frontend PeerComparisonPanel

    # Analyst outputs
    analyst_thesis: str
    analyst_response: str

    # Critic outputs
    critic_feedback: str
    critic_verdict: str

    # Debate state
    debate_transcript: Annotated[list[DebateMessage], operator.add]
    debate_round: int
    max_debate_rounds: int

    # Final output
    final_report: str
    error: Optional[str]


# ─────────────────────────────────────────────
# Node Implementations
# ─────────────────────────────────────────────

def memory_load_node(state: AnalysisState) -> dict:
    """
    Load past analyses from MemoryStore for this ticker.
    Formats them as a context string for the Analyst Agent.
    Runs as the FIRST node before any data fetching.
    """
    from src.memory.store import MemoryStore

    store = MemoryStore()
    records = store.load_recent(state["ticker"], n=3)
    context = store.format_for_context(records)

    return {
        "memory_context": context,
        "past_analyses_count": len(records),
    }


def fundamental_node(state: AnalysisState) -> dict:
    """
    Fetch SEC EDGAR data and produce:
    - fundamental_analysis: narrative string
    - financial_statements: structured JSON three-table summary
    - rag_sources: list of retrieved doc citations with scores
    - data_sources: list of data source labels
    - ticker_cik: SEC CIK for direct EDGAR links

    LangSmith trace shows:
      fundamental_node
        ├─ sec_xbrl_fetch          (XBRL API call, ticker → CIK → all concepts)
        ├─ fundamental_rag_retrieval (4 queries → ChromaDB + BM25 → RRF merge)
        ├─ extract_financial_statements (tool_use → JSON Income/BS/CF)
        └─ fundamental_narrative_analysis (narrative LLM call)
    """
    agent = FundamentalAgent()
    agent.load_data(state["ticker"], state["year"])
    result = agent.analyze(state["ticker"], state["year"], state["depth"])
    return {
        "fundamental_analysis": result["analysis"],
        "financial_statements": result["financial_statements"],
        "rag_sources": result.get("retrieval_context", []),
        "data_sources": result.get("data_sources", []),
        "ticker_cik": result.get("cik", ""),
    }


def technical_node(state: AnalysisState) -> dict:
    """
    Fetch and analyze yfinance technical indicators.
    Also pre-fetches live quote and recent news for display and sentiment use.
    """
    from src.tools.stock_utils import get_live_quote, get_stock_news

    agent = TechnicalAgent()
    result = agent.analyze(state["ticker"], state["year"], state["depth"])

    # Pre-fetch live quote and news independently (don't rely on LLM tool calls)
    try:
        live_price = get_live_quote(state["ticker"])
    except Exception as e:
        live_price = {"ticker": state["ticker"], "error": str(e)}

    try:
        news_items = get_stock_news(state["ticker"], max_items=10)
    except Exception:
        news_items = []

    existing = state.get("data_sources", [])
    merged = list(existing) + [s for s in ["yfinance"] if s not in existing]
    return {
        "technical_analysis": result["analysis"],
        "data_sources": merged,
        "live_price": live_price,
        "news_items": news_items,
    }


def sentiment_node(state: AnalysisState) -> dict:
    """
    Sentiment analysis using real recent news from yfinance + LLM interpretation.
    Falls back to training-knowledge summary if no news is available.
    """
    from src.tools.tracing import get_traced_client, resolve_model_id

    client = get_traced_client()
    ticker = state["ticker"]
    year = state["year"]
    news_items = state.get("news_items", [])

    # Build news context from fetched headlines
    if news_items:
        news_lines = []
        for item in news_items[:8]:
            pub_date = item.get("published_at", "")[:10]
            news_lines.append(
                f"- [{pub_date}] {item['title']} — {item.get('publisher', '')}"
            )
        news_context = "Recent news headlines (from Yahoo Finance):\n" + "\n".join(news_lines)
    else:
        news_context = "No recent news available from Yahoo Finance."

    response = client.messages.create(
        model=resolve_model_id("claude-haiku-4-5-20251001"),
        max_tokens=900,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Analyze market sentiment for {ticker} based on the following recent news "
                    f"and your knowledge around {year}.\n\n"
                    f"{news_context}\n\n"
                    f"Provide:\n"
                    f"1. Overall sentiment (BULLISH / BEARISH / NEUTRAL) with confidence\n"
                    f"2. Key themes from recent news (2–3 bullet points)\n"
                    f"3. Analyst/institutional sentiment indicators\n"
                    f"4. Retail investor / social media tone\n"
                    f"5. Potential upcoming catalysts or risks\n\n"
                    f"Be concise and data-driven. Flag if news is limited or outdated."
                ),
            }
        ],
    )
    return {"sentiment_analysis": response.content[0].text}


def valuation_node(state: AnalysisState) -> dict:
    """
    Quantitative valuation: DCF intrinsic value + relative multiples.
    Runs after sentiment, before analyst_initial so the Analyst can
    reference valuation context in its thesis.
    """
    agent = ValuationAgent()
    result = agent.analyze(
        ticker=state["ticker"],
        year=state["year"],
        financial_statements=state.get("financial_statements", {}),
        live_price=state.get("live_price", {}),
        depth=state.get("depth", "standard"),
    )
    return {
        "valuation_analysis": result["valuation_analysis"],
        "valuation_data": result["valuation_data"],
    }


def peer_comparison_node(state: AnalysisState) -> dict:
    """
    Identify 5 industry peers, fetch live metrics, and produce
    a structured competitive comparison with narrative.
    Runs after valuation, before analyst_initial.
    """
    agent = PeerComparisonAgent()
    result = agent.analyze(
        ticker=state["ticker"],
        year=state["year"],
        financial_statements=state.get("financial_statements", {}),
        live_price=state.get("live_price", {}),
        depth=state.get("depth", "standard"),
    )
    return {
        "peer_analysis": result["peer_analysis"],
        "peer_data": result["peer_data"],
    }


def analyst_initial_node(state: AnalysisState) -> dict:
    """Generate the initial investment thesis, optionally referencing memory context."""
    agent = AnalystAgent()
    thesis = agent.initial_analysis(
        ticker=state["ticker"],
        fundamental_analysis=state["fundamental_analysis"],
        technical_analysis=state["technical_analysis"],
        sentiment_analysis=state["sentiment_analysis"],
        depth=state["depth"],
        memory_context=state.get("memory_context", ""),
        valuation_analysis=state.get("valuation_analysis", ""),
        peer_analysis=state.get("peer_analysis", ""),
    )

    new_message: DebateMessage = {
        "round": 1,
        "speaker": "analyst",
        "content": thesis,
    }

    return {
        "analyst_thesis": thesis,
        "debate_transcript": [new_message],
        "debate_round": 1,
    }


def critic_node(state: AnalysisState) -> dict:
    """Challenge the current Analyst thesis."""
    agent = CriticAgent()
    current_round = state["debate_round"]
    current_thesis = state.get("analyst_response") or state["analyst_thesis"]

    critique = agent.critique(
        ticker=state["ticker"],
        analyst_thesis=current_thesis,
        fundamental_data=state["fundamental_analysis"],
        technical_data=state["technical_analysis"],
        sentiment_data=state["sentiment_analysis"],
        debate_round=current_round,
    )

    new_message: DebateMessage = {
        "round": current_round,
        "speaker": "critic",
        "content": critique,
    }

    return {
        "critic_feedback": critique,
        "debate_transcript": [new_message],
    }


def analyst_rebuttal_node(state: AnalysisState) -> dict:
    """Analyst responds to Critic's challenge."""
    agent = AnalystAgent()
    current_round = state["debate_round"]
    current_thesis = state.get("analyst_response") or state["analyst_thesis"]

    response = agent.respond_to_critique(
        ticker=state["ticker"],
        original_thesis=current_thesis,
        critic_feedback=state["critic_feedback"],
        debate_round=current_round,
    )

    next_round = current_round + 1
    new_message: DebateMessage = {
        "round": current_round,
        "speaker": "analyst",
        "content": response,
    }

    return {
        "analyst_response": response,
        "debate_transcript": [new_message],
        "debate_round": next_round,
    }


def final_report_node(state: AnalysisState) -> dict:
    """Generate the final investment report after debate concludes."""
    analyst_agent = AnalystAgent()
    critic_agent = CriticAgent()

    critic_verdict = critic_agent.final_verdict(
        ticker=state["ticker"],
        debate_transcript=state["debate_transcript"],
    )

    final_report = analyst_agent.generate_final_report(
        ticker=state["ticker"],
        year=state["year"],
        fundamental_analysis=state["fundamental_analysis"],
        technical_analysis=state["technical_analysis"],
        sentiment_analysis=state["sentiment_analysis"],
        debate_transcript=state["debate_transcript"],
        depth=state["depth"],
    )

    full_report = f"{final_report}\n\n---\n\n## Risk Assessment (Critic's Final Verdict)\n{critic_verdict}"

    return {
        "final_report": full_report,
        "critic_verdict": critic_verdict,
    }


def memory_save_node(state: AnalysisState) -> dict:
    """
    Persist current analysis result to MemoryStore.
    Runs as the LAST node, after final_report_node.
    Returns the assigned record_id.
    """
    from src.memory.store import AnalysisRecord, MemoryStore

    store = MemoryStore()
    record = AnalysisRecord.from_state(state)
    record_id = store.save(record)

    return {"memory_record_id": record_id}


# ─────────────────────────────────────────────
# Routing Logic
# ─────────────────────────────────────────────

def should_continue_debate(state: AnalysisState) -> str:
    """Determine if another debate round is needed."""
    if state["debate_round"] > state.get("max_debate_rounds", 2):
        return "finalize"
    return "continue"


# ─────────────────────────────────────────────
# Graph Construction
# ─────────────────────────────────────────────

def build_graph(enable_memory: bool = True) -> StateGraph:
    """
    Build and compile the LangGraph state machine.

    Flow (with memory):
      memory_load → fundamental → technical → sentiment → valuation
        → peer_comparison → analyst_initial → critic ↔ analyst_rebuttal
        → final_report → memory_save → END

    Flow (without memory):
      fundamental → technical → sentiment → valuation
        → peer_comparison → analyst_initial → critic ↔ analyst_rebuttal
        → final_report → END
    """
    graph = StateGraph(AnalysisState)

    # Worker nodes
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("technical", technical_node)
    graph.add_node("sentiment", sentiment_node)
    graph.add_node("valuation", valuation_node)
    graph.add_node("peer_comparison", peer_comparison_node)

    # Reasoning nodes
    graph.add_node("analyst_initial", analyst_initial_node)
    graph.add_node("critic", critic_node)
    graph.add_node("analyst_rebuttal", analyst_rebuttal_node)
    graph.add_node("final_report", final_report_node)

    if enable_memory:
        graph.add_node("memory_load", memory_load_node)
        graph.add_node("memory_save", memory_save_node)
        graph.set_entry_point("memory_load")
        graph.add_edge("memory_load", "fundamental")
    else:
        graph.set_entry_point("fundamental")

    # Worker pipeline
    graph.add_edge("fundamental", "technical")
    graph.add_edge("technical", "sentiment")
    graph.add_edge("sentiment", "valuation")
    graph.add_edge("valuation", "peer_comparison")
    graph.add_edge("peer_comparison", "analyst_initial")

    # Adversarial debate loop
    graph.add_edge("analyst_initial", "critic")
    graph.add_edge("critic", "analyst_rebuttal")
    graph.add_conditional_edges(
        "analyst_rebuttal",
        should_continue_debate,
        {"continue": "critic", "finalize": "final_report"},
    )

    if enable_memory:
        graph.add_edge("final_report", "memory_save")
        graph.add_edge("memory_save", END)
    else:
        graph.add_edge("final_report", END)

    return graph.compile()


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def run_analysis(
    ticker: str,
    year: int,
    depth: str = "standard",
    max_debate_rounds: int = 2,
    enable_memory: bool = True,
    progress_callback=None,
) -> AnalysisState:
    """
    Run the full multi-agent investment analysis pipeline.

    Args:
        ticker:            Stock ticker symbol (e.g., "NVDA")
        year:              Fiscal year for analysis (e.g., 2024)
        depth:             Analysis depth ("standard" or "detailed")
        max_debate_rounds: Number of Analyst-Critic debate rounds
        enable_memory:     Load past analyses and save current result (default True)
        progress_callback: Optional callable(step_name) for progress updates

    Returns:
        Final AnalysisState with all analysis, investment report, and memory metadata
    """
    initial_state: AnalysisState = {
        "ticker": ticker.upper(),
        "year": year,
        "depth": depth,
        "memory_context": "",
        "past_analyses_count": 0,
        "memory_record_id": "",
        "fundamental_analysis": "",
        "financial_statements": {},
        "technical_analysis": "",
        "sentiment_analysis": "",
        "valuation_analysis": "",
        "valuation_data": {},
        "peer_analysis": "",
        "peer_data": {},
        "live_price": {},
        "news_items": [],
        "rag_sources": [],
        "data_sources": [],
        "ticker_cik": "",
        "analyst_thesis": "",
        "analyst_response": "",
        "critic_feedback": "",
        "critic_verdict": "",
        "debate_transcript": [],
        "debate_round": 1,
        "max_debate_rounds": max_debate_rounds,
        "final_report": "",
        "error": None,
    }

    app = build_graph(enable_memory=enable_memory)

    if progress_callback:
        final_state = initial_state
        for step in app.stream(initial_state, stream_mode="updates"):
            node_name = list(step.keys())[0]
            progress_callback(node_name)
            updates = step[node_name]
            if isinstance(updates, dict):
                for k, v in updates.items():
                    if k == "debate_transcript" and isinstance(v, list):
                        existing = final_state.get("debate_transcript", [])
                        final_state = {**final_state, "debate_transcript": existing + v}
                    else:
                        final_state = {**final_state, k: v}
        return final_state
    else:
        return app.invoke(initial_state)
