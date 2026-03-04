"""
Fundamental Agent: SEC EDGAR RAG with LlamaParse + Hybrid Search.

Two outputs per run:
  1. financial_statements (dict) — precise JSON of Income Statement,
     Balance Sheet, and Cash Flow Statement extracted via Claude tool_use
  2. analysis (str)              — narrative analysis with risk assessment

LangSmith traces:
  - "fundamental_rag_retrieval" span  → which queries fired, what was retrieved
  - "extract_financial_statements"    → tool_use call forcing JSON output
  - "fundamental_narrative_analysis"  → narrative LLM call
  All Anthropic API calls auto-traced via wrap_anthropic().
"""

from __future__ import annotations

import json
from typing import Optional

from src.tools.sec_retriever import build_sec_retriever, HybridRetriever
from src.tools.tracing import get_traced_client, resolve_model_id, traceable


# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_ANALYST = """You are a senior financial analyst specializing in SEC filings.
Be precise, data-driven, and cite specific numbers. Flag any concerning trends."""

_SYSTEM_EXTRACTOR = """You are a financial data extractor. Your ONLY job is to call
the provided tool with accurate financial data extracted from the supplied context.
Never hallucinate numbers — use null for any value not found in the data."""


# ── Tool schema for structured JSON output ────────────────────────────────────

def _make_year_value_schema(description: str) -> dict:
    """Array of {year, value_usd, formatted} objects for a financial line item."""
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "properties": {
                "year": {"type": "string", "description": "Fiscal year, e.g. '2024'"},
                "value_usd": {
                    "type": ["number", "null"],
                    "description": "Raw value in USD (or shares/ratio as applicable)",
                },
                "formatted": {
                    "type": "string",
                    "description": "Human-readable, e.g. '$60.9B' or '3.5%'",
                },
            },
            "required": ["year", "value_usd", "formatted"],
        },
    }


FINANCIAL_STATEMENTS_TOOL = {
    "name": "save_financial_statements",
    "description": (
        "Save the structured financial three-statement summary for a company. "
        "Populate every field from the provided XBRL data. "
        "Calculate growth rates and margins where raw values are available. "
        "Use null for values not present in the source data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            # ── Income Statement ─────────────────────────────────────────────
            "income_statement": {
                "type": "object",
                "description": "Annual Income Statement (損益表)",
                "properties": {
                    "revenue": _make_year_value_schema("Total revenue / net sales"),
                    "gross_profit": _make_year_value_schema("Gross profit"),
                    "operating_income": _make_year_value_schema("Operating income (EBIT)"),
                    "net_income": _make_year_value_schema("Net income"),
                    "rd_expense": _make_year_value_schema("Research & Development expense"),
                    "sga_expense": _make_year_value_schema(
                        "Selling, General & Administrative expense"
                    ),
                    "interest_expense": _make_year_value_schema("Interest expense"),
                    "income_tax": _make_year_value_schema("Income tax expense"),
                    "eps_basic": _make_year_value_schema("Basic EPS (USD per share)"),
                    "eps_diluted": _make_year_value_schema("Diluted EPS (USD per share)"),
                    # Derived metrics
                    "revenue_growth_yoy": _make_year_value_schema(
                        "YoY revenue growth rate (%)"
                    ),
                    "gross_margin_pct": _make_year_value_schema("Gross margin (%)"),
                    "operating_margin_pct": _make_year_value_schema("Operating margin (%)"),
                    "net_margin_pct": _make_year_value_schema("Net profit margin (%)"),
                    "rd_as_pct_revenue": _make_year_value_schema(
                        "R&D spending as % of revenue"
                    ),
                },
                "required": [
                    "revenue", "gross_profit", "operating_income", "net_income",
                    "eps_basic", "revenue_growth_yoy", "gross_margin_pct",
                    "net_margin_pct",
                ],
            },
            # ── Balance Sheet ────────────────────────────────────────────────
            "balance_sheet": {
                "type": "object",
                "description": "Annual Balance Sheet (資產負債表)",
                "properties": {
                    "total_assets": _make_year_value_schema("Total assets"),
                    "current_assets": _make_year_value_schema("Current assets"),
                    "cash_and_equivalents": _make_year_value_schema(
                        "Cash and cash equivalents"
                    ),
                    "goodwill": _make_year_value_schema("Goodwill"),
                    "total_liabilities": _make_year_value_schema("Total liabilities"),
                    "current_liabilities": _make_year_value_schema("Current liabilities"),
                    "long_term_debt": _make_year_value_schema("Long-term debt"),
                    "shareholders_equity": _make_year_value_schema(
                        "Total shareholders' equity"
                    ),
                    "retained_earnings": _make_year_value_schema("Retained earnings"),
                    # Derived
                    "debt_to_equity": _make_year_value_schema(
                        "Debt-to-equity ratio (×)"
                    ),
                    "current_ratio": _make_year_value_schema(
                        "Current ratio (current assets / current liabilities)"
                    ),
                    "roe_pct": _make_year_value_schema(
                        "Return on Equity = Net Income / Shareholders Equity (%)"
                    ),
                    "roa_pct": _make_year_value_schema(
                        "Return on Assets = Net Income / Total Assets (%)"
                    ),
                },
                "required": [
                    "total_assets", "total_liabilities", "shareholders_equity",
                    "long_term_debt", "cash_and_equivalents",
                    "debt_to_equity", "roe_pct",
                ],
            },
            # ── Cash Flow Statement ──────────────────────────────────────────
            "cash_flow_statement": {
                "type": "object",
                "description": "Annual Cash Flow Statement (現金流量表)",
                "properties": {
                    "operating_cf": _make_year_value_schema(
                        "Net cash from operating activities"
                    ),
                    "investing_cf": _make_year_value_schema(
                        "Net cash from investing activities"
                    ),
                    "financing_cf": _make_year_value_schema(
                        "Net cash from financing activities"
                    ),
                    "capex": _make_year_value_schema("Capital expenditures (negative = outflow)"),
                    "free_cash_flow": _make_year_value_schema(
                        "Free Cash Flow = Operating CF − CapEx"
                    ),
                    "depreciation_amortization": _make_year_value_schema(
                        "Depreciation & Amortization (non-cash add-back)"
                    ),
                    "stock_based_compensation": _make_year_value_schema(
                        "Stock-based compensation"
                    ),
                    "dividends_paid": _make_year_value_schema("Dividends paid"),
                    "share_repurchase": _make_year_value_schema("Share buybacks"),
                    # Derived
                    "fcf_margin_pct": _make_year_value_schema(
                        "Free Cash Flow margin = FCF / Revenue (%)"
                    ),
                },
                "required": [
                    "operating_cf", "investing_cf", "financing_cf",
                    "capex", "free_cash_flow",
                ],
            },
            # ── Summary ──────────────────────────────────────────────────────
            "fundamental_score": {
                "type": "string",
                "enum": ["STRONG", "MODERATE", "WEAK"],
                "description": "Overall fundamental health score",
            },
            "score_rationale": {
                "type": "string",
                "description": "2-sentence rationale for the fundamental score",
            },
            "top_risks": {
                "type": "array",
                "description": "Top 3 risks from Item 1A",
                "items": {
                    "type": "object",
                    "properties": {
                        "risk": {"type": "string"},
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "description": {"type": "string"},
                    },
                    "required": ["risk", "severity", "description"],
                },
            },
        },
        "required": [
            "income_statement",
            "balance_sheet",
            "cash_flow_statement",
            "fundamental_score",
            "score_rationale",
            "top_risks",
        ],
    },
}


# ── Helper: format USD values ─────────────────────────────────────────────────

def _fmt(value: float | int | None) -> str:
    """Format a USD value as a human-readable string (e.g., $60.9B)."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}${abs_val/1e12:.2f}T"
    if abs_val >= 1e9:
        return f"{sign}${abs_val/1e9:.2f}B"
    if abs_val >= 1e6:
        return f"{sign}${abs_val/1e6:.1f}M"
    return f"{sign}${abs_val:,.0f}"


def _pct_fmt(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "N/A"


def _build_xbrl_context(facts: dict) -> str:
    """
    Serialize raw XBRL facts into a prompt-ready context string.
    Groups by statement for clarity.
    """
    if not facts:
        return "No XBRL data available."

    ticker = facts.get("ticker", "N/A")
    lines = [f"XBRL Financial Data for {ticker} (source: SEC EDGAR)\n"]

    sections = {
        "INCOME STATEMENT": [
            "revenue", "gross_profit", "operating_income", "net_income",
            "rd_expense", "sga_expense", "interest_expense", "income_tax",
            "eps_basic", "eps_diluted",
        ],
        "BALANCE SHEET": [
            "total_assets", "current_assets", "cash_and_equivalents",
            "goodwill", "total_liabilities", "current_liabilities",
            "long_term_debt", "shareholders_equity", "retained_earnings",
        ],
        "CASH FLOW STATEMENT": [
            "operating_cf", "investing_cf", "financing_cf",
            "capex", "depreciation_amortization",
            "stock_based_compensation", "dividends_paid", "share_repurchase",
        ],
    }

    for section_name, fields in sections.items():
        lines.append(f"\n── {section_name} ──")
        for field in fields:
            values = facts.get(field, [])
            if values:
                vals = " | ".join(
                    f"{v['year']}: {_fmt(v['value'])}" for v in values[:4]
                )
                label = field.replace("_", " ").title()
                lines.append(f"  {label}: {vals}")

    return "\n".join(lines)


# ── Agent class ───────────────────────────────────────────────────────────────

class FundamentalAgent:
    """
    Fundamental analysis agent.

    Workflow:
      1. load_data()                → fetch XBRL + build hybrid retriever
      2. extract_financial_statements() → tool_use → precise JSON three tables
      3. analyze()                  → narrative analysis + returns both outputs
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = get_traced_client()
        self.model = resolve_model_id(model)
        self._retriever: Optional[HybridRetriever] = None
        self._facts: dict = {}
        self._ticker: str = ""
        self._year: int = 0

    def load_data(self, ticker: str, year: int, data_dir: str = "./data") -> None:
        """Load XBRL facts and build hybrid retriever index."""
        self._retriever, self._facts = build_sec_retriever(ticker, year, data_dir)
        self._ticker = ticker
        self._year = year

    @traceable(
        name="fundamental_rag_retrieval",
        run_type="retriever",
        metadata={"retriever_type": "HybridRetriever (ChromaDB + BM25 + RRF)"},
    )
    def _retrieve_context(self, queries: list[str]) -> list[dict]:
        """
        Run hybrid retrieval for a list of queries.
        Returns deduplicated results with source IDs and scores.
        LangSmith span shows: queries fired, docs retrieved, RRF scores.
        """
        if not self._retriever:
            return []

        seen: set[str] = set()
        results: list[dict] = []
        for query in queries:
            for hit in self._retriever.search(query, top_k=3):
                if hit["id"] not in seen:
                    seen.add(hit["id"])
                    results.append({**hit, "query": query})
        return results

    @traceable(
        name="extract_financial_statements",
        run_type="llm",
        metadata={"output_format": "structured_json", "method": "tool_use"},
    )
    def extract_financial_statements(self) -> dict:
        """
        Use Claude tool_use to force structured JSON output of the three statements.

        Calculates derived metrics (growth rates, margins, ratios) from raw XBRL values.
        LangSmith span shows: input context, tool schema, extracted JSON.
        """
        xbrl_context = _build_xbrl_context(self._facts)

        # Pre-compute derived metrics to assist Claude
        derived = _compute_derived_metrics(self._facts)

        prompt = f"""Extract the complete financial three-statement summary for {self._ticker}.
Call the save_financial_statements tool with ALL available data.

{xbrl_context}

Pre-computed derived metrics (use these for growth/margin/ratio fields):
{json.dumps(derived, indent=2)}

Rules:
- Use null (JSON null) for any value not in the source data above
- Format values as human-readable strings (e.g. "$60.9B", "3.5%", "2.1×")
- For EPS, format as "$X.XX"
- Populate up to 4 years of history where available
- Calculate Free Cash Flow = Operating CF + CapEx (CapEx is typically negative)"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=_SYSTEM_EXTRACTOR,
            tools=[FINANCIAL_STATEMENTS_TOOL],
            tool_choice={"type": "tool", "name": "save_financial_statements"},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "save_financial_statements":
                statements = block.input
                statements["ticker"] = self._ticker
                statements["fiscal_year"] = self._year
                statements["currency"] = "USD"
                statements["data_source"] = "SEC EDGAR XBRL"
                return statements

        return {
            "ticker": self._ticker,
            "fiscal_year": self._year,
            "error": "Failed to extract structured financial data",
        }

    @traceable(
        name="fundamental_narrative_analysis",
        run_type="llm",
        metadata={"analysis_type": "fundamental"},
    )
    def _generate_narrative(
        self,
        context_docs: list[dict],
        statements: dict,
        depth: str,
    ) -> str:
        """
        Generate narrative analysis from retrieved context + structured statements.
        LangSmith span shows: retrieved context used, generated narrative, token counts.
        """
        context_text = "\n\n".join(
            f"[{doc['id']} | score={doc['score']:.4f}]\n{doc['content']}"
            for doc in context_docs
        ) or "No additional context retrieved."

        # Build a concise financial summary from the structured statements
        is_data = statements.get("income_statement", {})
        bs_data = statements.get("balance_sheet", {})
        cf_data = statements.get("cash_flow_statement", {})

        def latest(items: list[dict]) -> str:
            return items[0]["formatted"] if items else "N/A"

        summary_lines = [
            f"Revenue: {latest(is_data.get('revenue', []))}",
            f"Net Income: {latest(is_data.get('net_income', []))}",
            f"Net Margin: {latest(is_data.get('net_margin_pct', []))}",
            f"Revenue Growth YoY: {latest(is_data.get('revenue_growth_yoy', []))}",
            f"R&D / Revenue: {latest(is_data.get('rd_as_pct_revenue', []))}",
            f"Free Cash Flow: {latest(cf_data.get('free_cash_flow', []))}",
            f"LT Debt: {latest(bs_data.get('long_term_debt', []))}",
            f"Debt/Equity: {latest(bs_data.get('debt_to_equity', []))}",
            f"ROE: {latest(bs_data.get('roe_pct', []))}",
        ]
        financial_summary = "\n".join(f"  {l}" for l in summary_lines)

        risks_text = ""
        for risk in statements.get("top_risks", []):
            risks_text += f"\n- [{risk.get('severity')}] {risk.get('risk')}: {risk.get('description', '')}"

        detail_instr = (
            "Provide an in-depth 500-word analysis with multi-year trend analysis."
            if depth == "detailed"
            else "Provide a focused 200-300 word analysis."
        )

        prompt = f"""Analyze the fundamental investment case for {self._ticker} ({self._year}).

Key Metrics (latest fiscal year):
{financial_summary}

Fundamental Score: {statements.get('fundamental_score', 'N/A')}
{statements.get('score_rationale', '')}

Top Risks:{risks_text if risks_text else ' None identified'}

Retrieved SEC Context:
{context_text}

{detail_instr}

Address: revenue growth quality, margin expansion/compression, R&D investment thesis,
debt sustainability, and cash flow generation ability. Be specific with numbers."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=_SYSTEM_ANALYST,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def analyze(self, ticker: str, year: int, depth: str = "standard") -> dict:
        """
        Full fundamental analysis pipeline.

        Returns:
            {
                "ticker": str,
                "year": int,
                "agent": "fundamental",
                "financial_statements": dict,   # structured JSON three tables
                "analysis": str,                # narrative analysis
                "retrieval_context": list[dict],
                "data_sources": list[str],
            }
        """
        rag_queries = [
            f"{ticker} revenue growth net income profit margin fiscal {year}",
            f"{ticker} R&D research development spending innovation investment",
            f"{ticker} risk factors Item 1A debt obligations balance sheet",
            f"{ticker} free cash flow capital expenditure shareholder returns",
        ]

        context_docs = self._retrieve_context(rag_queries)
        statements = self.extract_financial_statements()
        narrative = self._generate_narrative(context_docs, statements, depth)

        return {
            "ticker": ticker,
            "year": year,
            "cik": self._facts.get("cik", ""),
            "agent": "fundamental",
            "financial_statements": statements,
            "analysis": narrative,
            "retrieval_context": [
                {
                    "id": d["id"],
                    "query": d.get("query", ""),
                    "score": d["score"],
                    "content": d.get("content", "")[:300],
                }
                for d in context_docs
            ],
            "data_sources": ["SEC EDGAR XBRL", "Hybrid RAG (ChromaDB + BM25)"],
        }


# ── Derived metrics computation ───────────────────────────────────────────────

def _compute_derived_metrics(facts: dict) -> dict:
    """
    Pre-compute growth rates, margins, and ratios from raw XBRL values.
    Returns a dict of field → list[{year, value}] for Claude to use directly.
    """

    def vals(field: str) -> list[dict]:
        return facts.get(field, [])

    def as_map(field: str) -> dict[str, float]:
        return {v["year"]: v["value"] for v in vals(field) if v.get("value") is not None}

    revenue_map = as_map("revenue")
    net_income_map = as_map("net_income")
    gross_profit_map = as_map("gross_profit")
    operating_map = as_map("operating_income")
    lt_debt_map = as_map("long_term_debt")
    equity_map = as_map("shareholders_equity")
    assets_map = as_map("total_assets")
    current_assets_map = as_map("current_assets")
    current_liab_map = as_map("current_liabilities")
    operating_cf_map = as_map("operating_cf")
    capex_map = as_map("capex")
    rd_map = as_map("rd_expense")

    years = sorted(revenue_map.keys(), reverse=True)
    derived: dict[str, list] = {
        "revenue_growth_yoy": [],
        "gross_margin_pct": [],
        "operating_margin_pct": [],
        "net_margin_pct": [],
        "rd_as_pct_revenue": [],
        "debt_to_equity": [],
        "roe_pct": [],
        "roa_pct": [],
        "current_ratio": [],
        "free_cash_flow": [],
        "fcf_margin_pct": [],
    }

    for i, year in enumerate(years):
        rev = revenue_map.get(year)
        if not rev:
            continue

        # Revenue growth (YoY)
        if i + 1 < len(years):
            prev_year = years[i + 1]
            prev_rev = revenue_map.get(prev_year)
            if prev_rev and prev_rev != 0:
                growth = (rev - prev_rev) / abs(prev_rev) * 100
                derived["revenue_growth_yoy"].append(
                    {"year": year, "value": growth, "formatted": _pct_fmt(growth)}
                )

        # Margins
        for field, key in [
            ("gross_margin_pct", gross_profit_map),
            ("operating_margin_pct", operating_map),
            ("net_margin_pct", net_income_map),
        ]:
            val = key.get(year)
            if val is not None:
                pct = val / rev * 100
                derived[field].append(
                    {"year": year, "value": pct, "formatted": _pct_fmt(pct)}
                )

        # R&D % revenue
        rd = rd_map.get(year)
        if rd is not None:
            pct = rd / rev * 100
            derived["rd_as_pct_revenue"].append(
                {"year": year, "value": pct, "formatted": _pct_fmt(pct)}
            )

        # Debt / Equity
        debt = lt_debt_map.get(year)
        equity = equity_map.get(year)
        if debt is not None and equity and equity != 0:
            de = debt / abs(equity)
            derived["debt_to_equity"].append(
                {"year": year, "value": de, "formatted": f"{de:.2f}×"}
            )

        # ROE / ROA
        ni = net_income_map.get(year)
        if ni is not None and equity and equity != 0:
            roe = ni / abs(equity) * 100
            derived["roe_pct"].append(
                {"year": year, "value": roe, "formatted": _pct_fmt(roe)}
            )
        assets = assets_map.get(year)
        if ni is not None and assets and assets != 0:
            roa = ni / assets * 100
            derived["roa_pct"].append(
                {"year": year, "value": roa, "formatted": _pct_fmt(roa)}
            )

        # Current ratio
        ca = current_assets_map.get(year)
        cl = current_liab_map.get(year)
        if ca and cl and cl != 0:
            cr = ca / cl
            derived["current_ratio"].append(
                {"year": year, "value": cr, "formatted": f"{cr:.2f}×"}
            )

        # Free Cash Flow
        ocf = operating_cf_map.get(year)
        capex = capex_map.get(year)
        if ocf is not None:
            capex_val = capex if capex is not None else 0
            fcf = ocf + capex_val  # capex is typically stored as negative
            derived["free_cash_flow"].append(
                {"year": year, "value": fcf, "formatted": _fmt(fcf)}
            )
            if rev != 0:
                fcf_margin = fcf / rev * 100
                derived["fcf_margin_pct"].append(
                    {"year": year, "value": fcf_margin, "formatted": _pct_fmt(fcf_margin)}
                )

    return derived
