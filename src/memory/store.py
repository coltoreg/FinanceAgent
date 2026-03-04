"""
FinAgent Memory Store — persistent cross-session analysis memory.

Architecture:
  ChromaDB collection "finagent_memory"
    → semantic search across all stored analyses
    → filter by ticker, year, rating, score
  JSON files in data/memory/records/{record_id}.json
    → full record backup (financial_statements, full report, debate transcript)

Each run saves an AnalysisRecord with:
  - Investment rating & fundamental score
  - Full final report & analyst thesis
  - Structured financial statements (three tables)
  - Debate transcript summary
  - Metadata: ticker, year, timestamp, model provider

The Analyst Agent loads recent records at analysis start and references
historical thesis evolution, rating changes, and fundamental trends.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions


# ── Constants ─────────────────────────────────────────────────────────────────

COLLECTION_NAME = "finagent_memory"
VALID_RATINGS = {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}
VALID_SCORES = {"STRONG", "MODERATE", "WEAK"}


# ── Data Model ─────────────────────────────────────────────────────────────────

@dataclass
class AnalysisRecord:
    """One complete analysis run stored in memory."""

    ticker: str
    year: int
    timestamp: str                          # ISO 8601 UTC
    depth: str
    investment_rating: str                  # STRONG BUY / BUY / HOLD / SELL / STRONG SELL
    fundamental_score: str                  # STRONG / MODERATE / WEAK
    analyst_thesis: str                     # Initial thesis text
    final_report: str                       # Full final report
    financial_statements: dict              # Structured JSON three tables
    debate_rounds: int
    model_provider: str                     # anthropic / bedrock
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_state(cls, state: dict) -> "AnalysisRecord":
        """Build a record from a completed LangGraph AnalysisState."""
        statements = state.get("financial_statements", {})
        transcript = state.get("debate_transcript", [])
        debate_rounds = max((m["round"] for m in transcript), default=0)

        return cls(
            ticker=state["ticker"],
            year=state["year"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            depth=state.get("depth", "standard"),
            investment_rating=_extract_rating(state.get("analyst_thesis", "")),
            fundamental_score=statements.get("fundamental_score", "UNKNOWN"),
            analyst_thesis=state.get("analyst_thesis", ""),
            final_report=state.get("final_report", ""),
            financial_statements=statements,
            debate_rounds=debate_rounds,
            model_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    # ── Formatting ────────────────────────────────────────────────────────────

    def to_chroma_document(self) -> str:
        """Text embedded in ChromaDB for semantic search."""
        thesis_excerpt = self.analyst_thesis[:600] if self.analyst_thesis else ""
        report_excerpt = self.final_report[:400] if self.final_report else ""
        return (
            f"Analysis of {self.ticker} ({self.year}) on {self.timestamp[:10]}. "
            f"Rating: {self.investment_rating}. "
            f"Fundamental: {self.fundamental_score}. "
            f"Thesis: {thesis_excerpt} "
            f"Report: {report_excerpt}"
        )

    def to_chroma_metadata(self) -> dict:
        """Metadata stored alongside the embedding (must be JSON-scalar values)."""
        return {
            "ticker": self.ticker,
            "year": self.year,
            "timestamp": self.timestamp,
            "depth": self.depth,
            "investment_rating": self.investment_rating,
            "fundamental_score": self.fundamental_score,
            "debate_rounds": self.debate_rounds,
            "model_provider": self.model_provider,
        }

    def to_context_summary(self) -> str:
        """
        Concise summary injected into the Analyst's prompt as historical context.
        Shows rating evolution and key financial trends.
        """
        is_data = self.financial_statements.get("income_statement", {})
        bs_data = self.financial_statements.get("balance_sheet", {})
        cf_data = self.financial_statements.get("cash_flow_statement", {})

        def latest(items: list) -> str:
            return items[0]["formatted"] if items else "N/A"

        metrics = [
            f"Revenue Growth: {latest(is_data.get('revenue_growth_yoy', []))}",
            f"Net Margin: {latest(is_data.get('net_margin_pct', []))}",
            f"ROE: {latest(bs_data.get('roe_pct', []))}",
            f"FCF Margin: {latest(cf_data.get('fcf_margin_pct', []))}",
            f"Debt/Equity: {latest(bs_data.get('debt_to_equity', []))}",
        ]

        thesis_excerpt = (
            self.analyst_thesis[:400] + "..." if len(self.analyst_thesis) > 400
            else self.analyst_thesis
        )

        return (
            f"[{self.timestamp[:10]}] {self.ticker} FY{self.year} | "
            f"Rating: {self.investment_rating} | Fundamental: {self.fundamental_score}\n"
            f"  Key Metrics: {' | '.join(metrics)}\n"
            f"  Thesis: {thesis_excerpt}\n"
        )


# ── Memory Store ───────────────────────────────────────────────────────────────

class MemoryStore:
    """
    Persistent analysis memory backed by ChromaDB (semantic search)
    and JSON files (full record storage).

    Usage:
        store = MemoryStore()
        store.save(AnalysisRecord.from_state(state))
        records = store.load_recent("NVDA", n=3)
        context = store.format_for_context(records)
    """

    def __init__(self, persist_dir: str = "./data/memory"):
        self.persist_dir = Path(persist_dir)
        self.records_dir = self.persist_dir / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

        chroma_dir = str(self.persist_dir / "chroma")
        Path(chroma_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=chroma_dir)
        self._ef = embedding_functions.DefaultEmbeddingFunction()
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._ef,
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def save(self, record: AnalysisRecord) -> str:
        """
        Persist a completed analysis record.
        Returns the record_id for reference.
        """
        # 1. Save full record as JSON (no size limits)
        json_path = self.records_dir / f"{record.record_id}.json"
        json_path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))

        # 2. Add to ChromaDB for semantic search
        chroma_id = f"{record.ticker}_{record.year}_{record.record_id}"
        existing_ids = self._collection.get(ids=[chroma_id])["ids"]
        if chroma_id not in existing_ids:
            self._collection.add(
                ids=[chroma_id],
                documents=[record.to_chroma_document()],
                metadatas=[record.to_chroma_metadata()],
            )

        return record.record_id

    # ── Read ──────────────────────────────────────────────────────────────────

    def load_recent(self, ticker: str, n: int = 3) -> list[AnalysisRecord]:
        """
        Load the most recent N analyses for a given ticker.
        Returns records sorted newest-first.
        """
        results = self._collection.get(
            where={"ticker": ticker},
            include=["metadatas"],
        )
        if not results["ids"]:
            return []

        # Sort by timestamp descending
        paired = sorted(
            zip(results["ids"], results["metadatas"]),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True,
        )[:n]

        records = []
        for chroma_id, meta in paired:
            # Load full record from JSON
            record_id = chroma_id.rsplit("_", 1)[-1]
            json_path = self.records_dir / f"{record_id}.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text())
                    records.append(AnalysisRecord.from_dict(data))
                except (json.JSONDecodeError, TypeError):
                    pass  # Skip corrupted records
        return records

    def load_all(self, ticker: Optional[str] = None) -> list[AnalysisRecord]:
        """Load all stored records, optionally filtered by ticker."""
        where = {"ticker": ticker} if ticker else None
        kwargs = {"where": where} if where else {}
        results = self._collection.get(include=["metadatas"], **kwargs)

        paired = sorted(
            zip(results["ids"], results["metadatas"]),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True,
        )

        records = []
        for chroma_id, _ in paired:
            record_id = chroma_id.rsplit("_", 1)[-1]
            json_path = self.records_dir / f"{record_id}.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text())
                    records.append(AnalysisRecord.from_dict(data))
                except (json.JSONDecodeError, TypeError):
                    pass
        return records

    def search_similar(self, query: str, ticker: Optional[str] = None, n: int = 3) -> list[AnalysisRecord]:
        """
        Semantic search across all stored analyses.
        Optionally restrict to a specific ticker.
        """
        if self._collection.count() == 0:
            return []

        kwargs: dict = {
            "query_texts": [query],
            "n_results": min(n, self._collection.count()),
            "include": ["metadatas", "distances"],
        }
        if ticker:
            kwargs["where"] = {"ticker": ticker}

        results = self._collection.query(**kwargs)
        ids = results["ids"][0]

        records = []
        for chroma_id in ids:
            record_id = chroma_id.rsplit("_", 1)[-1]
            json_path = self.records_dir / f"{record_id}.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text())
                    records.append(AnalysisRecord.from_dict(data))
                except (json.JSONDecodeError, TypeError):
                    pass
        return records

    def list_tickers(self) -> list[str]:
        """Return all unique tickers that have stored analyses."""
        results = self._collection.get(include=["metadatas"])
        tickers = {m.get("ticker", "") for m in results["metadatas"] if m.get("ticker")}
        return sorted(tickers)

    def count(self, ticker: Optional[str] = None) -> int:
        """Count stored records, optionally filtered by ticker."""
        if ticker:
            results = self._collection.get(where={"ticker": ticker}, include=["metadatas"])
            return len(results["ids"])
        return self._collection.count()

    # ── Formatting ────────────────────────────────────────────────────────────

    def format_for_context(self, records: list[AnalysisRecord]) -> str:
        """
        Format a list of records as a structured prompt section
        for injection into the Analyst's initial_analysis prompt.

        Returns empty string if no records.
        """
        if not records:
            return ""

        lines = [
            f"You have {len(records)} previous analysis record(s) for this company.",
            "Use these to track thesis evolution and flag if fundamentals have changed.\n",
        ]
        for i, rec in enumerate(records, 1):
            lines.append(f"── Record {i} ──")
            lines.append(rec.to_context_summary())

        return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_rating(text: str) -> str:
    """
    Extract investment rating from analyst thesis text.
    Looks for patterns like '**Investment Rating**: BUY' or 'Rating: STRONG BUY'.
    """
    for pattern in [
        r"\*{0,2}Investment\s+Rating\*{0,2}[:\s]+([A-Z ]+?)(?:\n|$|\||\*)",
        r"Rating[:\s]+([A-Z ]+?)(?:\n|$|\||\*)",
        r"\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD)\b",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().upper()
            if candidate in VALID_RATINGS:
                return candidate
            # Try to normalize
            for rating in VALID_RATINGS:
                if rating in candidate:
                    return rating
    return "UNKNOWN"
