"""
Valuation Agent: Quantitative valuation models for investment analysis.

Provides:
  - DCF intrinsic value estimation
  - Relative multiples (P/E, EV/EBITDA, P/S, P/FCF, P/B) vs sector averages
  - Valuation conclusion: EXPENSIVE / FAIR / CHEAP

Runs after sentiment analysis, before the Analyst initial thesis,
so the Analyst can incorporate valuation context into its narrative.
"""

import json
from src.tools.tracing import get_traced_client, resolve_model_id


# ── Tool schema for structured valuation output ────────────────────────────────

_VALUATION_TOOL = {
    "name": "extract_valuation_metrics",
    "description": (
        "Extract and compute valuation metrics from the provided financial data. "
        "Calculate DCF intrinsic value, relative multiples, and overall assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "dcf": {
                "type": "object",
                "description": "DCF intrinsic value analysis",
                "properties": {
                    "intrinsic_value": {"type": "number", "description": "Per-share intrinsic value from DCF (USD)"},
                    "current_price": {"type": "number", "description": "Current market price (USD)"},
                    "upside_downside_pct": {"type": "number", "description": "% upside (+) or downside (-) to intrinsic value"},
                    "five_year_fcf_projections": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "5-year projected FCF in billions USD"
                    },
                    "terminal_value": {"type": "number", "description": "Terminal value (discounted, billions USD)"},
                    "wacc_used": {"type": "number", "description": "WACC applied (e.g. 0.10 = 10%)"},
                    "terminal_growth_rate": {"type": "number", "description": "Terminal growth rate (e.g. 0.025 = 2.5%)"},
                    "methodology": {"type": "string", "description": "Brief explanation of DCF assumptions"}
                },
                "required": ["intrinsic_value", "current_price", "upside_downside_pct",
                             "wacc_used", "terminal_growth_rate", "methodology"]
            },
            "multiples": {
                "type": "object",
                "description": "Relative valuation multiples vs sector averages",
                "properties": {
                    "pe_trailing": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    },
                    "pe_forward": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    },
                    "ev_ebitda": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    },
                    "price_to_sales": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    },
                    "price_to_fcf": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    },
                    "price_to_book": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                            "sector_avg": {"type": "number"},
                            "assessment": {"type": "string", "enum": ["CHEAP", "DISCOUNT", "AT MARKET", "FAIR", "PREMIUM", "EXPENSIVE", "N/A"]}
                        },
                        "required": ["value", "sector_avg", "assessment"]
                    }
                },
                "required": ["pe_trailing", "pe_forward", "ev_ebitda",
                             "price_to_sales", "price_to_fcf", "price_to_book"]
            },
            "valuation_summary": {
                "type": "object",
                "properties": {
                    "overall": {
                        "type": "string",
                        "enum": ["EXPENSIVE", "FAIR", "CHEAP"],
                        "description": "Overall valuation verdict"
                    },
                    "justified_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Reasons that justify the current valuation level"
                    },
                    "key_concern": {
                        "type": "string",
                        "description": "Primary risk or concern at current valuation"
                    }
                },
                "required": ["overall", "justified_by", "key_concern"]
            }
        },
        "required": ["dcf", "multiples", "valuation_summary"]
    }
}


class ValuationAgent:
    """
    Quantitative valuation agent that computes DCF and relative multiples.

    Uses Claude Tool Use to produce structured JSON (valuation_data),
    then generates a narrative valuation analysis (valuation_analysis).
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = get_traced_client()
        self.model = resolve_model_id(model)

    def analyze(
        self,
        ticker: str,
        year: int,
        financial_statements: dict,
        live_price: dict,
        depth: str = "standard",
    ) -> dict:
        """
        Run valuation analysis.

        Args:
            ticker:               Stock ticker symbol
            year:                 Fiscal year of the analysis
            financial_statements: Structured JSON from FundamentalAgent
            live_price:           Live quote dict from yfinance
            depth:                "standard" or "detailed"

        Returns:
            {
              "valuation_data":     dict,   # structured JSON for frontend
              "valuation_analysis": str,    # narrative for Analyst context
            }
        """
        context = self._build_context(ticker, year, financial_statements, live_price)

        # Step 1: Structured extraction via tool use
        valuation_data = self._extract_structured(ticker, context)

        # Step 2: Narrative analysis
        valuation_analysis = self._generate_narrative(
            ticker, year, valuation_data, context, depth
        )

        return {
            "valuation_data": valuation_data,
            "valuation_analysis": valuation_analysis,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_context(
        self,
        ticker: str,
        year: int,
        financial_statements: dict,
        live_price: dict,
    ) -> str:
        """Summarise available financial data into a structured prompt block."""
        is_data = financial_statements.get("income_statement", {})
        bs_data = financial_statements.get("balance_sheet", {})
        cf_data = financial_statements.get("cash_flow_statement", {})

        def latest(items: list) -> str:
            return items[0]["value"] if items else "N/A"

        def latest_fmt(items: list) -> str:
            return items[0]["formatted"] if items else "N/A"

        price = live_price.get("price") or "N/A"
        market_cap = live_price.get("market_cap") or "N/A"
        currency = live_price.get("currency", "USD")

        lines = [
            f"=== FINANCIAL DATA: {ticker} FY{year} ===",
            "",
            "── Income Statement ──",
            f"Revenue:          {latest_fmt(is_data.get('revenue', []))}",
            f"Gross Profit:     {latest_fmt(is_data.get('gross_profit', []))}",
            f"Operating Income: {latest_fmt(is_data.get('operating_income', []))}",
            f"Net Income:       {latest_fmt(is_data.get('net_income', []))}",
            f"EPS (Basic):      {latest_fmt(is_data.get('eps_basic', []))}",
            f"EPS (Diluted):    {latest_fmt(is_data.get('eps_diluted', []))}",
            f"Revenue Growth:   {latest_fmt(is_data.get('revenue_growth_yoy', []))}",
            f"Gross Margin:     {latest_fmt(is_data.get('gross_margin_pct', []))}",
            f"Operating Margin: {latest_fmt(is_data.get('operating_margin_pct', []))}",
            f"Net Margin:       {latest_fmt(is_data.get('net_margin_pct', []))}",
            "",
            "── Balance Sheet ──",
            f"Cash & Equivalents: {latest_fmt(bs_data.get('cash_and_equivalents', []))}",
            f"Total Assets:       {latest_fmt(bs_data.get('total_assets', []))}",
            f"Long-Term Debt:     {latest_fmt(bs_data.get('long_term_debt', []))}",
            f"Total Liabilities:  {latest_fmt(bs_data.get('total_liabilities', []))}",
            f"Shareholders Equity:{latest_fmt(bs_data.get('shareholders_equity', []))}",
            f"Debt/Equity:        {latest_fmt(bs_data.get('debt_to_equity', []))}",
            "",
            "── Cash Flow ──",
            f"Operating CF: {latest_fmt(cf_data.get('operating_cf', []))}",
            f"Free Cash Flow:{latest_fmt(cf_data.get('free_cash_flow', []))}",
            f"CapEx:         {latest_fmt(cf_data.get('capex', []))}",
            f"D&A (non-cash):{latest_fmt(cf_data.get('depreciation_amortization', []))}",
            "",
            "── Live Market Data ──",
            f"Current Price: {price} {currency}",
            f"Market Cap:    {market_cap}",
            f"52W High:      {live_price.get('week52_high', 'N/A')}",
            f"52W Low:       {live_price.get('week52_low', 'N/A')}",
        ]
        return "\n".join(lines)

    def _extract_structured(self, ticker: str, context: str) -> dict:
        """
        Use Claude Tool Use to extract structured valuation metrics.
        Falls back to an empty dict on any error.
        """
        prompt = f"""You are a quantitative financial analyst. Using the financial data below,
compute valuation metrics for {ticker} by calling the extract_valuation_metrics tool.

{context}

Calculation guidance:
- EPS = Net Income / Shares Outstanding (use EPS (Diluted) directly if available)
- P/E trailing = Current Price / EPS (trailing twelve months)
- P/E forward = Current Price / next-year EPS estimate (apply revenue growth rate to estimate)
- Market Cap from live data; EV = Market Cap + Long-Term Debt - Cash
- EBITDA ≈ Operating Income + D&A; EV/EBITDA = EV / EBITDA
- P/S = Market Cap / Revenue (annual)
- P/FCF = Current Price / (Free Cash Flow per share)
- P/B = Current Price / (Shareholders Equity per share, i.e. Book Value per share)
- DCF: use most recent FCF as base year, grow at revenue_growth_yoy for 5 years,
  then terminal growth at 2.5%, WACC = 10%. Discount back to present to get intrinsic value.
- Sector averages: use your training knowledge of the company's primary sector.
  Add a disclaimer in methodology that sector averages are approximate.
- If data is insufficient to compute a multiple, use -1 for value and note N/A for assessment.

Call the tool with your computed results."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                tools=[_VALUATION_TOOL],
                tool_choice={"type": "any"},
                messages=[{"role": "user", "content": prompt}],
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "extract_valuation_metrics":
                    return block.input

        except Exception:
            pass

        return {}

    def _generate_narrative(
        self,
        ticker: str,
        year: int,
        valuation_data: dict,
        context: str,
        depth: str,
    ) -> str:
        """Generate a narrative valuation analysis for the Analyst Agent."""
        length = (
            "Provide a detailed 400-600 word valuation narrative."
            if depth == "detailed"
            else "Provide a concise 200-300 word valuation narrative."
        )

        summary = valuation_data.get("valuation_summary", {})
        overall = summary.get("overall", "N/A")
        dcf = valuation_data.get("dcf", {})
        multiples = valuation_data.get("multiples", {})

        structured_summary = json.dumps(
            {"dcf": dcf, "multiples": multiples, "valuation_summary": summary},
            indent=2,
        )

        prompt = f"""Based on the computed valuation metrics below, write a valuation analysis for {ticker} ({year}).

=== COMPUTED VALUATION METRICS ===
{structured_summary}

=== RAW FINANCIAL CONTEXT ===
{context[:800]}

Overall Verdict: {overall}

{length}

Address:
1. DCF analysis — intrinsic value vs current price, key assumptions, confidence level
2. Multiple analysis — which multiples look stretched/cheap relative to sector
3. Valuation verdict — is the premium/discount justified by growth and quality?
4. Key risk — what could compress/expand multiples?

Be analytical and data-driven. Cite specific numbers."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            return f"Valuation narrative unavailable: {exc}"
