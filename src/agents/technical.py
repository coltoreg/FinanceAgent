"""
Technical Agent: yfinance-based technical analysis with function calling.
Calculates MA50/200, RSI, MACD and provides trend assessment.
"""

import json

from src.tools.stock_utils import (
    analyze_technical,
    get_company_info,
    get_live_quote,
    get_stock_news,
    TechnicalIndicators,
)
from src.tools.tracing import get_traced_client, resolve_model_id


TECHNICAL_SYSTEM_PROMPT = """You are an expert technical analyst with deep knowledge of price action,
moving averages, momentum indicators, and chart patterns.

Your analysis should:
1. Interpret MA50/200 crossovers (golden/death cross)
2. Assess RSI for overbought (>70) or oversold (<30) conditions
3. Read MACD divergence and momentum shifts
4. Evaluate volume confirmation of price moves
5. Provide a clear trend direction: BULLISH / BEARISH / NEUTRAL

Always contextualize signals within the broader market context.
Avoid over-interpreting short-term noise."""

# Tool definitions for yfinance function calling
TECHNICAL_TOOLS = [
    {
        "name": "get_technical_indicators",
        "description": "Fetch current technical indicators for a stock: MA50, MA200, RSI, MACD",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL)",
                },
                "period": {
                    "type": "string",
                    "description": "Historical period: 1y, 2y, 5y",
                    "enum": ["1y", "2y", "5y"],
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_company_overview",
        "description": "Fetch basic company info: sector, PE ratio, market cap, analyst targets",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_live_quote",
        "description": (
            "Fetch real-time stock quote: current price, price change %, "
            "pre/post-market price, 52-week high/low, market state"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Fetch recent news headlines for the stock from Yahoo Finance",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                },
                "max_items": {
                    "type": "integer",
                    "description": "Max number of news articles to return (default 8)",
                },
            },
            "required": ["ticker"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a technical analysis tool and return JSON result."""
    if tool_name == "get_technical_indicators":
        ticker = tool_input["ticker"]
        period = tool_input.get("period", "1y")
        indicators = analyze_technical(ticker, period)
        return json.dumps(
            {
                "ticker": indicators.ticker,
                "current_price": round(indicators.current_price, 2),
                "ma50": round(indicators.ma50, 2),
                "ma200": round(indicators.ma200, 2),
                "rsi": round(indicators.rsi, 2),
                "macd": round(indicators.macd, 4),
                "macd_signal": round(indicators.macd_signal, 4),
                "macd_histogram": round(indicators.macd_histogram, 4),
                "price_vs_ma50_pct": round(indicators.price_vs_ma50_pct, 2),
                "price_vs_ma200_pct": round(indicators.price_vs_ma200_pct, 2),
                "overbought": indicators.overbought,
                "oversold": indicators.oversold,
                "golden_cross": indicators.golden_cross,
                "death_cross": indicators.death_cross,
                "volume_ratio": round(indicators.current_volume / indicators.volume_avg, 2),
            }
        )

    if tool_name == "get_company_overview":
        info = get_company_info(tool_input["ticker"])
        return json.dumps(info)

    if tool_name == "get_live_quote":
        quote = get_live_quote(tool_input["ticker"])
        return json.dumps(quote)

    if tool_name == "get_stock_news":
        news = get_stock_news(
            tool_input["ticker"],
            max_items=tool_input.get("max_items", 8),
        )
        return json.dumps(news)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class TechnicalAgent:
    """
    Technical analysis agent using yfinance with Claude function calling.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = get_traced_client()
        self.model = resolve_model_id(model)

    def analyze(self, ticker: str, year: int, depth: str = "standard") -> dict:
        """
        Run technical analysis using multi-turn tool calling.
        Returns structured analysis with trend signals and indicators.
        """
        detail_instruction = (
            "Provide exhaustive technical analysis covering all timeframes and indicator combinations."
            if depth == "detailed"
            else "Provide a clear, actionable technical summary."
        )

        messages = [
            {
                "role": "user",
                "content": (
                    f"Perform a comprehensive technical analysis for {ticker} as of {year}. "
                    f"Use the available tools to fetch current indicators and company overview. "
                    f"{detail_instruction}\n\n"
                    f"Structure your analysis as:\n"
                    f"1. **Trend Direction**: BULLISH / BEARISH / NEUTRAL\n"
                    f"2. **Moving Average Analysis**: MA50 vs MA200 positioning\n"
                    f"3. **Momentum (RSI)**: Overbought/oversold assessment\n"
                    f"4. **MACD Signal**: Momentum direction and divergence\n"
                    f"5. **Volume Confirmation**: Volume vs average\n"
                    f"6. **Key Price Levels**: Support and resistance\n"
                    f"7. **Technical Score**: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL"
                ),
            }
        ]

        # Agentic loop with tool use
        max_rounds = 3
        for _ in range(max_rounds):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=TECHNICAL_SYSTEM_PROMPT,
                tools=TECHNICAL_TOOLS,
                messages=messages,
            )

            # Check if we need to execute tools
            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        result = _execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

                # Add assistant response and tool results to conversation
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # End of conversation
                break

        final_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_text = block.text
                break

        return {
            "ticker": ticker,
            "year": year,
            "agent": "technical",
            "analysis": final_text,
            "data_sources": ["yfinance", "Technical Indicators (MA, RSI, MACD)"],
        }
