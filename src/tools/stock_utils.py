"""
Stock utilities using yfinance for technical analysis.
Provides MA, RSI, MACD calculations, live quote, and news retrieval.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import yfinance as yf


@dataclass
class TechnicalIndicators:
    ticker: str
    current_price: float
    ma50: float
    ma200: float
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    price_vs_ma50_pct: float
    price_vs_ma200_pct: float
    overbought: bool
    oversold: bool
    golden_cross: bool
    death_cross: bool
    volume_avg: float
    current_volume: float


def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch historical price data from yfinance."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    if hist.empty:
        raise ValueError(f"No price data found for ticker: {ticker}")
    return hist


def calculate_ma(prices: pd.Series, window: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return prices.rolling(window=window).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD, Signal line, and Histogram."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def analyze_technical(ticker: str, period: str = "1y") -> TechnicalIndicators:
    """
    Full technical analysis for a given ticker.
    Returns TechnicalIndicators with MA50/200, RSI, MACD signals.
    """
    hist = fetch_price_history(ticker, period)
    close = hist["Close"]
    volume = hist["Volume"]

    ma50 = calculate_ma(close, 50)
    ma200 = calculate_ma(close, 200)
    rsi_series = calculate_rsi(close)
    macd_line, signal_line, histogram = calculate_macd(close)

    current_price = float(close.iloc[-1])
    current_ma50 = float(ma50.iloc[-1])
    current_ma200 = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else current_price
    current_rsi = float(rsi_series.iloc[-1])
    current_macd = float(macd_line.iloc[-1])
    current_signal = float(signal_line.iloc[-1])
    current_histogram = float(histogram.iloc[-1])
    current_volume = float(volume.iloc[-1])
    avg_volume = float(volume.mean())

    price_vs_ma50 = ((current_price - current_ma50) / current_ma50) * 100
    price_vs_ma200 = ((current_price - current_ma200) / current_ma200) * 100

    # Golden cross: MA50 crosses above MA200
    golden_cross = bool(
        current_ma50 > current_ma200
        and float(ma50.iloc[-2]) <= float(ma200.iloc[-2])
        if len(ma50) >= 2 and not pd.isna(ma200.iloc[-2])
        else current_ma50 > current_ma200
    )
    # Death cross: MA50 crosses below MA200
    death_cross = bool(
        current_ma50 < current_ma200
        and float(ma50.iloc[-2]) >= float(ma200.iloc[-2])
        if len(ma50) >= 2 and not pd.isna(ma200.iloc[-2])
        else current_ma50 < current_ma200
    )

    return TechnicalIndicators(
        ticker=ticker,
        current_price=current_price,
        ma50=current_ma50,
        ma200=current_ma200,
        rsi=current_rsi,
        macd=current_macd,
        macd_signal=current_signal,
        macd_histogram=current_histogram,
        price_vs_ma50_pct=price_vs_ma50,
        price_vs_ma200_pct=price_vs_ma200,
        overbought=current_rsi > 70,
        oversold=current_rsi < 30,
        golden_cross=golden_cross,
        death_cross=death_cross,
        volume_avg=avg_volume,
        current_volume=current_volume,
    )


def get_live_quote(ticker: str) -> dict:
    """
    Fetch real-time quote data for a ticker.
    Returns current price, change %, pre/post-market price, 52-week range.
    Falls back gracefully if any field is unavailable.
    """
    stock = yf.Ticker(ticker)

    # fast_info is lighter-weight than .info
    try:
        fi = stock.fast_info
        price = float(fi.last_price) if fi.last_price else None
        prev_close = float(fi.previous_close) if fi.previous_close else None
        market_cap = fi.market_cap if hasattr(fi, "market_cap") else None
        currency = fi.currency if hasattr(fi, "currency") else "USD"
    except Exception:
        price = prev_close = market_cap = None
        currency = "USD"

    # .info for extended fields (52w, pre/post market)
    try:
        info = stock.info
        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low = info.get("fiftyTwoWeekLow")
        pre_market = info.get("preMarketPrice")
        post_market = info.get("postMarketPrice")
        market_state = info.get("marketState", "CLOSED")
        company_name = info.get("longName", ticker)
        volume = info.get("regularMarketVolume")
        avg_volume = info.get("averageVolume")
    except Exception:
        week52_high = week52_low = pre_market = post_market = volume = avg_volume = None
        market_state = "CLOSED"
        company_name = ticker

    change = round(price - prev_close, 2) if price and prev_close else None
    change_pct = round((change / prev_close) * 100, 2) if change and prev_close else None

    return {
        "ticker": ticker.upper(),
        "company_name": company_name,
        "price": price,
        "previous_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "market_state": market_state,         # REGULAR / PRE / POST / CLOSED
        "pre_market_price": pre_market,
        "post_market_price": post_market,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "market_cap": market_cap,
        "volume": volume,
        "avg_volume": avg_volume,
        "currency": currency,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_stock_news(ticker: str, max_items: int = 8) -> list[dict]:
    """
    Fetch recent news articles for a ticker via yfinance.
    Returns a list of {title, publisher, url, published_at, related_tickers}.
    """
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news or []
    except Exception:
        return []

    results = []
    for item in raw_news[:max_items]:
        # yfinance >= 1.1.0 wraps everything under a "content" key
        content = item.get("content") or item
        provider = content.get("provider") or {}
        canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}

        # published time: new API uses ISO string "pubDate", old used Unix "providerPublishTime"
        pub_date = content.get("pubDate") or content.get("displayTime") or ""
        if not pub_date:
            ts = item.get("providerPublishTime")
            pub_date = (
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
            )

        results.append({
            "title": content.get("title") or item.get("title", ""),
            "publisher": provider.get("displayName") or item.get("publisher", ""),
            "url": canonical.get("url") or item.get("link", ""),
            "published_at": pub_date,
            "related_tickers": content.get("relatedTickers") or item.get("relatedTickers", []),
        })
    return results


def get_company_info(ticker: str) -> dict:
    """Fetch basic company information from yfinance."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        "name": info.get("longName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap", 0),
        "pe_ratio": info.get("trailingPE", None),
        "forward_pe": info.get("forwardPE", None),
        "price_to_book": info.get("priceToBook", None),
        "debt_to_equity": info.get("debtToEquity", None),
        "revenue_growth": info.get("revenueGrowth", None),
        "earnings_growth": info.get("earningsGrowth", None),
        "profit_margin": info.get("profitMargins", None),
        "52_week_high": info.get("fiftyTwoWeekHigh", None),
        "52_week_low": info.get("fiftyTwoWeekLow", None),
        "analyst_target": info.get("targetMeanPrice", None),
        "recommendation": info.get("recommendationKey", "N/A"),
    }
