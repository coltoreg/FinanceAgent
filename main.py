"""
FinAgent CLI - Multi-Agent Investment Analysis System
Usage: python main.py --ticker NVDA --year 2024 --depth detailed
"""

import sys
import typer
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.markdown import Markdown
from rich import box
from rich.rule import Rule

from src.workflow.langgraph_flow import run_analysis

app = typer.Typer(
    name="finagent",
    help="Multi-Agent Investment Analysis System powered by Claude AI",
    add_completion=False,
)

console = Console()

# ─────────────────────────────────────────────
# Progress Step Mapping
# ─────────────────────────────────────────────

STEP_LABELS = {
    "memory_load": "[dim]Loading historical analyses from memory...[/dim]",
    "fundamental": "[cyan]Fetching SEC EDGAR filings...[/cyan]",
    "technical": "[yellow]Calculating technical indicators (MA, RSI, MACD)...[/yellow]",
    "sentiment": "[magenta]Analyzing market sentiment...[/magenta]",
    "valuation": "[blue]Computing valuation models (DCF & multiples)...[/blue]",
    "peer_comparison": "[cyan]Analyzing competitive peer group...[/cyan]",
    "analyst_initial": "[green]Senior Analyst synthesizing thesis...[/green]",
    "critic": "[red]Critic challenging thesis...[/red]",
    "analyst_rebuttal": "[green]Analyst responding to critique...[/green]",
    "final_report": "[bold white]Generating final report...[/bold white]",
    "memory_save": "[dim]Saving analysis to memory...[/dim]",
}

TOTAL_STEPS = 11


def print_banner(ticker: str, year: int, depth: str) -> None:
    """Print the FinAgent startup banner."""
    banner = Text()
    banner.append("  FinAgent  ", style="bold white on blue")
    banner.append("  Multi-Agent Investment Analysis", style="bold cyan")

    console.print()
    console.print(Panel(banner, box=box.DOUBLE_EDGE, expand=False))
    console.print()

    params_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    params_table.add_column("Key", style="dim")
    params_table.add_column("Value", style="bold")
    params_table.add_row("Ticker", f"[bold cyan]{ticker.upper()}[/bold cyan]")
    params_table.add_row("Year", str(year))
    params_table.add_row("Depth", depth.capitalize())
    console.print(params_table)
    console.print()


def print_section(title: str, content: str, color: str = "cyan") -> None:
    """Print a formatted analysis section."""
    console.print(Rule(f"[bold {color}]{title}[/bold {color}]"))
    console.print(Markdown(content))
    console.print()


def print_final_report(report: str, ticker: str) -> None:
    """Display the final investment report with rich formatting."""
    console.print()
    console.print(Rule("[bold white on blue] FINAL INVESTMENT REPORT [/bold white on blue]"))
    console.print()
    console.print(
        Panel(
            Markdown(report),
            title=f"[bold]{ticker.upper()} Investment Analysis[/bold]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


def _latest(items: list) -> str:
    """Return the formatted value of the most recent year."""
    return items[0]["formatted"] if items else "N/A"


def _yoy_row(items: list, max_years: int = 4) -> list[str]:
    """Return up to max_years formatted values, newest first."""
    return [item["formatted"] for item in items[:max_years]]


def print_financial_statements(statements: dict) -> None:
    """Display the financial three-statement summary as Rich tables."""
    if not statements or statements.get("error"):
        console.print("[dim]No structured financial data available.[/dim]")
        return

    ticker = statements.get("ticker", "")
    year = statements.get("fiscal_year", "")
    is_data = statements.get("income_statement", {})
    bs_data = statements.get("balance_sheet", {})
    cf_data = statements.get("cash_flow_statement", {})

    # Collect all years present for column headers
    rev_items = is_data.get("revenue", [])
    col_years = [item["year"] for item in rev_items[:4]]
    year_cols = col_years if col_years else ["Latest"]

    def make_table(title: str, color: str) -> Table:
        t = Table(
            title=f"[bold {color}]{title}[/bold {color}]",
            box=box.ROUNDED,
            show_header=True,
            header_style=f"bold {color}",
            padding=(0, 1),
        )
        t.add_column("Metric", style="dim", min_width=30)
        for yr in year_cols:
            t.add_column(str(yr), justify="right", min_width=12)
        return t

    def add_row(table: Table, label: str, items: list, style: str = "") -> None:
        vals = [item["formatted"] for item in items[:len(year_cols)]]
        # Pad with N/A if fewer years available
        while len(vals) < len(year_cols):
            vals.append("[dim]N/A[/dim]")
        table.add_row(f"[{'bold' if style == 'bold' else 'default'}]{label}[/]", *vals)

    console.print()
    console.print(Rule(f"[bold cyan] Financial Statements: {ticker} [/bold cyan]"))

    # ── Income Statement ─────────────────────────────────────────────────────
    tbl = make_table("Income Statement (損益表)", "cyan")
    add_row(tbl, "Revenue", is_data.get("revenue", []), "bold")
    add_row(tbl, "  Gross Profit", is_data.get("gross_profit", []))
    add_row(tbl, "  Operating Income (EBIT)", is_data.get("operating_income", []))
    add_row(tbl, "  Net Income", is_data.get("net_income", []), "bold")
    add_row(tbl, "  R&D Expense", is_data.get("rd_expense", []))
    add_row(tbl, "  SG&A Expense", is_data.get("sga_expense", []))
    add_row(tbl, "EPS (Basic)", is_data.get("eps_basic", []))
    add_row(tbl, "EPS (Diluted)", is_data.get("eps_diluted", []))
    tbl.add_section()
    add_row(tbl, "Revenue Growth YoY", is_data.get("revenue_growth_yoy", []))
    add_row(tbl, "Gross Margin %", is_data.get("gross_margin_pct", []))
    add_row(tbl, "Operating Margin %", is_data.get("operating_margin_pct", []))
    add_row(tbl, "Net Margin %", is_data.get("net_margin_pct", []))
    add_row(tbl, "R&D % Revenue", is_data.get("rd_as_pct_revenue", []))
    console.print(tbl)
    console.print()

    # ── Balance Sheet ────────────────────────────────────────────────────────
    tbl = make_table("Balance Sheet (資產負債表)", "yellow")
    add_row(tbl, "Total Assets", bs_data.get("total_assets", []), "bold")
    add_row(tbl, "  Current Assets", bs_data.get("current_assets", []))
    add_row(tbl, "  Cash & Equivalents", bs_data.get("cash_and_equivalents", []))
    add_row(tbl, "  Goodwill", bs_data.get("goodwill", []))
    tbl.add_section()
    add_row(tbl, "Total Liabilities", bs_data.get("total_liabilities", []), "bold")
    add_row(tbl, "  Current Liabilities", bs_data.get("current_liabilities", []))
    add_row(tbl, "  Long-Term Debt", bs_data.get("long_term_debt", []))
    tbl.add_section()
    add_row(tbl, "Shareholders' Equity", bs_data.get("shareholders_equity", []), "bold")
    add_row(tbl, "  Retained Earnings", bs_data.get("retained_earnings", []))
    tbl.add_section()
    add_row(tbl, "Debt / Equity", bs_data.get("debt_to_equity", []))
    add_row(tbl, "Current Ratio", bs_data.get("current_ratio", []))
    add_row(tbl, "ROE %", bs_data.get("roe_pct", []))
    add_row(tbl, "ROA %", bs_data.get("roa_pct", []))
    console.print(tbl)
    console.print()

    # ── Cash Flow Statement ──────────────────────────────────────────────────
    tbl = make_table("Cash Flow Statement (現金流量表)", "green")
    add_row(tbl, "Operating Cash Flow", cf_data.get("operating_cf", []), "bold")
    add_row(tbl, "Investing Cash Flow", cf_data.get("investing_cf", []))
    add_row(tbl, "Financing Cash Flow", cf_data.get("financing_cf", []))
    add_row(tbl, "  CapEx", cf_data.get("capex", []))
    add_row(tbl, "Free Cash Flow", cf_data.get("free_cash_flow", []), "bold")
    add_row(tbl, "  D&A (non-cash)", cf_data.get("depreciation_amortization", []))
    add_row(tbl, "  Stock-Based Comp", cf_data.get("stock_based_compensation", []))
    add_row(tbl, "  Dividends Paid", cf_data.get("dividends_paid", []))
    add_row(tbl, "  Share Buybacks", cf_data.get("share_repurchase", []))
    tbl.add_section()
    add_row(tbl, "FCF Margin %", cf_data.get("fcf_margin_pct", []))
    console.print(tbl)

    # ── Fundamental score summary ─────────────────────────────────────────────
    score = statements.get("fundamental_score", "N/A")
    score_colors = {"STRONG": "bold green", "MODERATE": "bold yellow", "WEAK": "bold red"}
    score_style = score_colors.get(score, "bold white")

    console.print()
    console.print(
        Panel(
            f"[{score_style}]{score}[/{score_style}]  —  {statements.get('score_rationale', '')}",
            title="[bold]Fundamental Score[/bold]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()


def print_debate_transcript(transcript: list[dict]) -> None:
    """Display the adversarial debate transcript."""
    if not transcript:
        return

    console.print()
    console.print(Rule("[bold yellow] Adversarial Debate Transcript [/bold yellow]"))
    console.print()

    for item in transcript:
        speaker = item["speaker"]
        round_num = item["round"]
        content = item["content"]

        if speaker == "analyst":
            style = "bold green"
            label = f"ANALYST (Round {round_num})"
        else:
            style = "bold red"
            label = f"CRITIC (Round {round_num})"

        console.print(f"[{style}]{label}[/{style}]")
        # Show truncated content in verbose mode only
        truncated = content[:500] + "..." if len(content) > 500 else content
        console.print(Text(truncated, style="dim"))
        console.print()


# ─────────────────────────────────────────────
# CLI Command
# ─────────────────────────────────────────────

@app.command()
def analyze(
    ticker: str = typer.Option(
        ...,
        "--ticker",
        "-t",
        help="Stock ticker symbol (e.g., NVDA, AAPL, MSFT)",
        prompt="Enter stock ticker",
    ),
    year: int = typer.Option(
        2025,
        "--year",
        "-y",
        help="Fiscal year for analysis",
        min=2010,
        max=2026,
    ),
    depth: str = typer.Option(
        "standard",
        "--depth",
        "-d",
        help="Analysis depth: standard or detailed",
        case_sensitive=False,
    ),
    debate_rounds: int = typer.Option(
        2,
        "--rounds",
        "-r",
        help="Number of Analyst-Critic debate rounds (1-3)",
        min=1,
        max=3,
    ),
    show_transcript: bool = typer.Option(
        False,
        "--transcript",
        help="Show the full adversarial debate transcript",
    ),
    show_sections: bool = typer.Option(
        False,
        "--sections",
        help="Show individual agent analysis sections",
    ),
    show_financials: bool = typer.Option(
        False,
        "--financials",
        "-f",
        help="Show structured financial three-statement tables (Income / Balance / Cash Flow)",
    ),
    no_memory: bool = typer.Option(
        False,
        "--no-memory",
        help="Skip loading/saving analysis memory (useful for one-off runs)",
    ),
) -> None:
    """
    Run multi-agent investment analysis for a stock ticker.

    Example:
        python main.py --ticker NVDA --year 2024 --depth detailed
    """
    # Validate depth
    if depth.lower() not in ("standard", "detailed"):
        console.print("[red]Error:[/red] --depth must be 'standard' or 'detailed'")
        raise typer.Exit(1)

    depth = depth.lower()
    print_banner(ticker, year, depth)

    # Progress tracking
    completed_steps = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            "[cyan]Initializing agents...[/cyan]",
            total=TOTAL_STEPS,
        )

        def on_progress(step_name: str) -> None:
            nonlocal completed_steps
            completed_steps += 1
            label = STEP_LABELS.get(step_name, f"Processing {step_name}...")
            progress.update(task, description=label, advance=1)

        try:
            result = run_analysis(
                ticker=ticker,
                year=year,
                depth=depth,
                max_debate_rounds=debate_rounds,
                enable_memory=not no_memory,
                progress_callback=on_progress,
            )
        except Exception as e:
            msg = str(e)
            if "security token" in msg.lower() and "expired" in msg.lower():
                console.print("\n[red bold]AWS 憑證已過期[/red bold]")
                console.print("[yellow]請執行 'aws sso login' 或重新設定 AWS_SESSION_TOKEN[/yellow]")
            console.print(f"\n[red]Error during analysis:[/red] {msg}")
            raise typer.Exit(1)

        progress.update(task, description="[bold green]Analysis complete![/bold green]")

    console.print()
    console.print("[bold green]✓ Analysis completed successfully[/bold green]")
    console.print()

    # Show financial three-statement tables if requested
    if show_financials:
        print_financial_statements(result.get("financial_statements", {}))

    # Show individual sections if requested
    if show_sections:
        print_section(
            "Fundamental Analysis (SEC Filings)",
            result.get("fundamental_analysis", "N/A"),
            color="cyan",
        )
        print_section(
            "Technical Analysis (yfinance)",
            result.get("technical_analysis", "N/A"),
            color="yellow",
        )
        print_section(
            "Sentiment Analysis",
            result.get("sentiment_analysis", "N/A"),
            color="magenta",
        )

    # Show debate transcript if requested
    if show_transcript:
        print_debate_transcript(result.get("debate_transcript", []))

    # Always show the final report
    final_report = result.get("final_report", "No report generated.")
    print_final_report(final_report, ticker)

    # Summary stats
    transcript = result.get("debate_transcript", [])
    debate_rounds_completed = max((m["round"] for m in transcript), default=0)

    console.print()
    stats_table = Table(
        title="Analysis Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue",
    )
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Value", style="bold")
    stats_table.add_row("Ticker", ticker.upper())
    stats_table.add_row("Fiscal Year", str(year))
    stats_table.add_row("Analysis Depth", depth.capitalize())
    stats_table.add_row("Debate Rounds", str(debate_rounds_completed))
    stats_table.add_row("Data Sources", "SEC EDGAR, yfinance, Market Sentiment")

    # Memory stats
    if not no_memory:
        past_count = result.get("past_analyses_count", 0)
        record_id = result.get("memory_record_id", "")
        stats_table.add_row(
            "Memory — Loaded",
            f"{past_count} past record(s) for {ticker.upper()}",
        )
        if record_id:
            stats_table.add_row("Memory — Saved", f"record_id: {record_id}")

    import os
    langsmith_project = os.getenv("LANGCHAIN_PROJECT", "")
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    if tracing_enabled and langsmith_project:
        stats_table.add_row(
            "LangSmith Trace",
            f"[link=https://smith.langchain.com]https://smith.langchain.com[/link] → {langsmith_project}",
        )
    console.print(stats_table)
    console.print()


# ─────────────────────────────────────────────
# History Sub-command
# ─────────────────────────────────────────────

@app.command()
def history(
    ticker: str = typer.Argument(..., help="Stock ticker to query (e.g., NVDA)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max records to show"),
) -> None:
    """
    Show analysis history for a stock ticker stored in memory.

    Example:
        python main.py history NVDA
        python main.py history NVDA --limit 5
    """
    from src.memory.store import MemoryStore

    store = MemoryStore()
    records = store.load_all(ticker=ticker.upper())[:limit]

    if not records:
        console.print(f"\n[yellow]No memory records found for {ticker.upper()}.[/yellow]")
        console.print("[dim]Run an analysis first: python main.py --ticker NVDA[/dim]\n")
        raise typer.Exit(0)

    console.print()
    console.print(Rule(f"[bold cyan] Analysis History: {ticker.upper()} ({len(records)} records) [/bold cyan]"))
    console.print()

    rating_colors = {
        "STRONG BUY": "bold green",
        "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red",
        "STRONG SELL": "bold red",
        "UNKNOWN": "dim",
    }
    score_colors = {"STRONG": "green", "MODERATE": "yellow", "WEAK": "red"}

    tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
    )
    tbl.add_column("Date", style="dim", min_width=12)
    tbl.add_column("Year", justify="center")
    tbl.add_column("Rating", min_width=14)
    tbl.add_column("Fundamental", min_width=10)
    tbl.add_column("Depth", justify="center")
    tbl.add_column("Rounds", justify="center")
    tbl.add_column("Provider", style="dim")
    tbl.add_column("Record ID", style="dim")

    for rec in records:
        r_style = rating_colors.get(rec.investment_rating, "default")
        s_style = score_colors.get(rec.fundamental_score, "default")
        tbl.add_row(
            rec.timestamp[:10],
            str(rec.year),
            f"[{r_style}]{rec.investment_rating}[/{r_style}]",
            f"[{s_style}]{rec.fundamental_score}[/{s_style}]",
            rec.depth,
            str(rec.debate_rounds),
            rec.model_provider,
            rec.record_id,
        )

    console.print(tbl)
    console.print()

    # Show thesis evolution for the most recent record
    if records:
        latest = records[0]
        console.print(
            Panel(
                Text(latest.analyst_thesis[:600] + ("..." if len(latest.analyst_thesis) > 600 else ""), style="dim"),
                title=f"[bold]Latest Thesis ({latest.timestamp[:10]})[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()


@app.command()
def memory_stats() -> None:
    """Show overall memory store statistics across all tickers."""
    from src.memory.store import MemoryStore

    store = MemoryStore()
    tickers = store.list_tickers()

    if not tickers:
        console.print("\n[yellow]Memory store is empty.[/yellow]\n")
        raise typer.Exit(0)

    console.print()
    console.print(Rule("[bold cyan] Memory Store Statistics [/bold cyan]"))
    console.print()

    tbl = Table(box=box.ROUNDED, header_style="bold cyan")
    tbl.add_column("Ticker", min_width=8)
    tbl.add_column("Records", justify="right")
    tbl.add_column("Latest Date", min_width=12)
    tbl.add_column("Latest Rating", min_width=14)

    total = 0
    for t in tickers:
        records = store.load_recent(t, n=1)
        count = store.count(t)
        total += count
        if records:
            latest = records[0]
            tbl.add_row(
                f"[bold]{t}[/bold]",
                str(count),
                latest.timestamp[:10],
                latest.investment_rating,
            )
        else:
            tbl.add_row(f"[bold]{t}[/bold]", str(count), "—", "—")

    console.print(tbl)
    console.print(f"\n[dim]Total records: {total} across {len(tickers)} ticker(s)[/dim]\n")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app()
