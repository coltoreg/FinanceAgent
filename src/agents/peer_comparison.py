"""
Peer Comparison Agent: Identifies 5 industry peers via Claude Haiku,
fetches live metrics via yfinance, and generates competitive positioning analysis.

Runs after ValuationAgent, before AnalystAgent initial thesis.
"""

import json
from src.tools.tracing import get_traced_client, resolve_model_id
from src.tools.stock_utils import get_company_info


EXTRACT_PEER_METRICS_TOOL = {
    "name": "extract_peer_metrics",
    "description": (
        "Standardize raw yfinance metrics for the target company and its peers "
        "into a structured comparison JSON with competitive positioning."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_company": {
                "type": "object",
                "description": "Standardized metrics for the company being analyzed",
                "properties": {
                    "ticker": {"type": "string"},
                    "name": {"type": "string"},
                    "pe_trailing": {"type": ["number", "null"]},
                    "pe_forward": {"type": ["number", "null"]},
                    "net_margin_pct": {"type": ["number", "null"]},
                    "revenue_growth_yoy_pct": {"type": ["number", "null"]},
                    "debt_to_equity": {"type": ["number", "null"]},
                    "roe_pct": {"type": ["number", "null"]},
                    "market_cap_billions": {"type": ["number", "null"]},
                    "analyst_target": {"type": ["number", "null"]},
                    "recommendation": {"type": ["string", "null"]},
                },
                "required": ["ticker", "name"],
            },
            "peers": {
                "type": "array",
                "description": "List of peer companies with standardized metrics",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "name": {"type": "string"},
                        "pe_trailing": {"type": ["number", "null"]},
                        "pe_forward": {"type": ["number", "null"]},
                        "net_margin_pct": {"type": ["number", "null"]},
                        "revenue_growth_yoy_pct": {"type": ["number", "null"]},
                        "debt_to_equity": {"type": ["number", "null"]},
                        "roe_pct": {"type": ["number", "null"]},
                        "market_cap_billions": {"type": ["number", "null"]},
                        "analyst_target": {"type": ["number", "null"]},
                        "recommendation": {"type": ["string", "null"]},
                    },
                    "required": ["ticker", "name"],
                },
                "minItems": 2,
            },
            "peer_analysis": {
                "type": "object",
                "description": "Competitive positioning assessment",
                "properties": {
                    "overall_position": {
                        "type": "string",
                        "enum": ["INDUSTRY_LEADER", "COMPETITIVE", "LAGGARD"],
                        "description": "Overall competitive standing vs peer group",
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top 2-3 competitive advantages with specific data points",
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top 2-3 competitive disadvantages with specific data points",
                    },
                    "valuation_vs_peers": {
                        "type": "string",
                        "enum": ["PREMIUM", "IN_LINE", "DISCOUNT"],
                        "description": "Valuation relative to peers",
                    },
                    "growth_vs_peers": {
                        "type": "string",
                        "enum": [
                            "BEST_IN_CLASS",
                            "ABOVE_AVERAGE",
                            "IN_LINE",
                            "BELOW_AVERAGE",
                        ],
                        "description": "Revenue/earnings growth relative to peers",
                    },
                    "key_differentiator": {
                        "type": "string",
                        "description": "One sentence on main competitive moat or disadvantage",
                    },
                },
                "required": [
                    "overall_position",
                    "strengths",
                    "weaknesses",
                    "valuation_vs_peers",
                    "growth_vs_peers",
                    "key_differentiator",
                ],
            },
        },
        "required": ["target_company", "peers", "peer_analysis"],
    },
}


class PeerComparisonAgent:
    """
    Identifies 5 industry peers, fetches live metrics, and produces
    a structured competitive comparison with narrative analysis.
    Uses Claude Haiku throughout for cost efficiency.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
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
        Main entry point. Returns:
            {"peer_data": {...}, "peer_analysis": "narrative text"}
        """
        company_info = get_company_info(ticker)
        peer_tickers = self._identify_peers(ticker, company_info)
        all_metrics = self._fetch_all_metrics(ticker, company_info, peer_tickers)
        peer_data = self._extract_structured(ticker, all_metrics)
        peer_analysis = self._generate_narrative(ticker, year, peer_data, depth)
        return {"peer_data": peer_data, "peer_analysis": peer_analysis}

    def _identify_peers(self, ticker: str, company_info: dict) -> list[str]:
        """
        Ask Haiku to recommend 5 peer ticker symbols based on sector/industry.
        Returns a list of up to 5 ticker strings.
        """
        name = company_info.get("name", ticker)
        sector = company_info.get("sector", "N/A")
        industry = company_info.get("industry", "N/A")

        prompt = (
            f"List exactly 5 publicly traded competitor ticker symbols for {name} ({ticker}).\n"
            f"Sector: {sector} | Industry: {industry}\n\n"
            "Requirements:\n"
            "- Return ONLY ticker symbols, one per line, no explanations\n"
            "- Choose the most direct competitors by market cap and product overlap\n"
            "- Exclude {ticker} itself\n"
            "- US-listed stocks preferred (NYSE/NASDAQ)\n\n"
            "Example format:\n"
            "AMD\nINTC\nQCOM\nMRVL\nAVGO"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        raw_tickers = [
            line.strip().upper()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("-")
        ]
        # Filter to plausible ticker symbols (1-5 uppercase letters)
        peers = [
            t for t in raw_tickers if t.isalpha() and 1 <= len(t) <= 5 and t != ticker.upper()
        ]
        return peers[:5]

    def _fetch_all_metrics(
        self, ticker: str, company_info: dict, peer_tickers: list[str]
    ) -> dict:
        """
        Build a raw metrics dict for the target + each peer.
        Gracefully skips peers that fail yfinance lookup.
        """
        def _info_to_raw(t: str, info: dict) -> dict:
            market_cap = info.get("market_cap", 0) or 0
            profit_margin = info.get("profit_margin")
            revenue_growth = info.get("revenue_growth")
            return {
                "ticker": t.upper(),
                "name": info.get("name", t),
                "pe_trailing": info.get("pe_ratio"),
                "pe_forward": info.get("forward_pe"),
                "net_margin_pct": round(profit_margin * 100, 2) if profit_margin is not None else None,
                "revenue_growth_yoy_pct": round(revenue_growth * 100, 2) if revenue_growth is not None else None,
                "debt_to_equity": info.get("debt_to_equity"),
                "roe_pct": None,  # yfinance get_company_info doesn't expose ROE directly
                "market_cap_billions": round(market_cap / 1e9, 2) if market_cap else None,
                "analyst_target": info.get("analyst_target"),
                "recommendation": info.get("recommendation"),
            }

        target_raw = _info_to_raw(ticker, company_info)
        peers_raw = []
        for pt in peer_tickers:
            try:
                info = get_company_info(pt)
                peers_raw.append(_info_to_raw(pt, info))
            except Exception:
                # Skip this peer silently
                continue

        return {"target": target_raw, "peers": peers_raw}

    def _extract_structured(self, ticker: str, all_metrics: dict) -> dict:
        """
        Use Claude Tool Use to standardize metrics and produce competitive assessment.
        Falls back to raw metrics dict if tool call fails.
        """
        metrics_json = json.dumps(all_metrics, indent=2)
        prompt = (
            f"Analyze the following raw yfinance metrics for {ticker} and its peers. "
            "Call the extract_peer_metrics tool to produce a standardized comparison "
            "with competitive positioning assessment.\n\n"
            f"Raw metrics:\n{metrics_json}\n\n"
            "Instructions:\n"
            "- Populate all numeric fields from the raw data (use null if unavailable)\n"
            "- Assess overall_position based on margin, growth, and ROE relative to peers\n"
            "- List specific data points in strengths/weaknesses (e.g., '55.6% net margin vs 5.2% peer avg')\n"
            "- valuation_vs_peers: PREMIUM if P/E > 20% above peer median, DISCOUNT if >20% below\n"
            "- growth_vs_peers: BEST_IN_CLASS if top quartile revenue growth"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            tools=[EXTRACT_PEER_METRICS_TOOL],
            tool_choice={"type": "tool", "name": "extract_peer_metrics"},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_peer_metrics":
                return block.input

        # Fallback: return raw structure without competitive analysis
        return {
            "target_company": all_metrics["target"],
            "peers": all_metrics["peers"],
            "peer_analysis": {
                "overall_position": "COMPETITIVE",
                "strengths": [],
                "weaknesses": [],
                "valuation_vs_peers": "IN_LINE",
                "growth_vs_peers": "IN_LINE",
                "key_differentiator": "Insufficient data for full competitive analysis.",
            },
        }

    def _generate_narrative(
        self, ticker: str, year: int, peer_data: dict, depth: str
    ) -> str:
        """
        Generate a concise narrative summary of the competitive positioning.
        """
        target = peer_data.get("target_company", {})
        analysis = peer_data.get("peer_analysis", {})
        peers = peer_data.get("peers", [])
        peer_names = ", ".join(p.get("ticker", "") for p in peers)

        detail = (
            "Provide a 200-300 word detailed competitive positioning narrative."
            if depth == "detailed"
            else "Provide a 100-150 word concise competitive positioning summary."
        )

        prompt = (
            f"Write a competitive analysis narrative for {ticker} ({year}) "
            f"based on peer comparison data.\n\n"
            f"Company: {target.get('name', ticker)} ({ticker})\n"
            f"Peers analyzed: {peer_names}\n"
            f"Overall position: {analysis.get('overall_position', 'N/A')}\n"
            f"Valuation vs peers: {analysis.get('valuation_vs_peers', 'N/A')}\n"
            f"Growth vs peers: {analysis.get('growth_vs_peers', 'N/A')}\n"
            f"Key differentiator: {analysis.get('key_differentiator', '')}\n"
            f"Strengths: {'; '.join(analysis.get('strengths', []))}\n"
            f"Weaknesses: {'; '.join(analysis.get('weaknesses', []))}\n\n"
            f"{detail}\n"
            "Focus on what the comparison means for investors, not just data recitation."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
