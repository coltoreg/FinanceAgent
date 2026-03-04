"""
Senior Analyst Agent: Synthesizes fundamental, technical, and sentiment data
into an initial investment prediction. Participates in adversarial debate loop.
"""

from src.tools.tracing import get_traced_client, resolve_model_id


ANALYST_SYSTEM_PROMPT = """You are a Senior Investment Analyst with 20+ years of experience at top-tier
investment banks. You synthesize multiple data streams into actionable investment theses.

Your role:
1. Weigh fundamental data (SEC filings) against technical signals (price action)
2. Incorporate market sentiment into your thesis
3. Build a coherent investment narrative with clear price targets
4. Acknowledge uncertainty and assign probability to your predictions
5. When responding to Critic's challenges, either defend your position with evidence
   or update your thesis if the criticism reveals a genuine blind spot

Investment ratings scale:
- STRONG BUY: High conviction long, >20% upside
- BUY: Moderate conviction long, 10-20% upside
- HOLD: Neutral, risk-reward balanced
- SELL: Moderate conviction short, 10-20% downside
- STRONG SELL: High conviction short, >20% downside"""


class AnalystAgent:
    """
    Senior Analyst agent that synthesizes multi-source data
    and engages in adversarial debate with the Critic.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = get_traced_client()
        self.model = resolve_model_id(model)

    def initial_analysis(
        self,
        ticker: str,
        fundamental_analysis: str,
        technical_analysis: str,
        sentiment_analysis: str,
        depth: str = "standard",
        memory_context: str = "",
        valuation_analysis: str = "",
        peer_analysis: str = "",
    ) -> str:
        """
        Generate initial investment thesis from all three data sources.
        If memory_context is provided, the Analyst references historical analyses
        to track thesis evolution and flag fundamental changes.
        """
        detail_instruction = (
            "Provide an exhaustive 500-800 word investment thesis with quantitative targets."
            if depth == "detailed"
            else "Provide a focused 200-400 word investment thesis."
        )

        memory_section = (
            f"\n=== HISTORICAL ANALYSIS MEMORY ===\n{memory_context}\n"
            "Consider: Has the investment case improved or deteriorated vs. prior analyses? "
            "Are historical risks materialising? Has the rating trend been consistent?\n"
            if memory_context
            else ""
        )

        valuation_section = (
            f"\n=== VALUATION ANALYSIS (DCF & Multiples) ===\n{valuation_analysis}\n"
            if valuation_analysis
            else ""
        )

        peer_section = (
            f"\n=== PEER COMPARISON ANALYSIS ===\n{peer_analysis}\n"
            if peer_analysis
            else ""
        )

        prompt = f"""You are analyzing {ticker}. Based on the following multi-source research,
provide your initial investment thesis.
{memory_section}
=== FUNDAMENTAL ANALYSIS (SEC Filings) ===
{fundamental_analysis}

=== TECHNICAL ANALYSIS (Price Action) ===
{technical_analysis}

=== SENTIMENT ANALYSIS (Market News) ===
{sentiment_analysis}
{valuation_section}{peer_section}
{detail_instruction}

Structure your response as:
1. **Investment Rating**: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
2. **12-Month Price Target**: $XX (% change from current)
3. **Bull Case**: Top 2 reasons this thesis works
4. **Bear Case**: Top 2 risks to this thesis
5. **Key Catalysts**: Upcoming events that could validate/invalidate
6. **Valuation Assessment**: Is current valuation justified by fundamentals?
7. **Competitive Position**: How does the company rank vs. peers on growth and valuation?
8. **Confidence Level**: HIGH / MEDIUM / LOW
{f'9. **vs. Prior Analysis**: How does this thesis compare to previous records (if memory provided)' if memory_context else ''}

Be specific with numbers and timeframes."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=ANALYST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def respond_to_critique(
        self,
        ticker: str,
        original_thesis: str,
        critic_feedback: str,
        debate_round: int,
    ) -> str:
        """
        Respond to Critic's challenges. Either defend or revise the thesis.
        """
        prompt = f"""You previously provided this investment thesis for {ticker}:

=== YOUR ORIGINAL THESIS ===
{original_thesis}

=== CRITIC'S CHALLENGE (Round {debate_round}) ===
{critic_feedback}

Now respond to the Critic's challenge. You MUST:
1. Address each specific criticism point-by-point
2. Either provide counter-evidence to defend your position, OR
3. Acknowledge valid points and update your thesis accordingly
4. Maintain intellectual honesty — do not dismiss valid criticisms

Structure your response as:
1. **Rebuttals**: Address each critique with evidence or data
2. **Concessions** (if any): Points where the Critic identified genuine risks
3. **Updated Thesis** (if changed): New rating/target if warranted
4. **Final Position**: Restate your rating with any modifications

Keep it concise and data-driven."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            system=ANALYST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def generate_final_report(
        self,
        ticker: str,
        year: int,
        fundamental_analysis: str,
        technical_analysis: str,
        sentiment_analysis: str,
        debate_transcript: list[dict],
        depth: str = "standard",
    ) -> str:
        """
        Generate the final investment report after the debate concludes.
        """
        debate_summary = "\n\n".join(
            f"Round {item['round']} - {item['speaker'].upper()}:\n{item['content']}"
            for item in debate_transcript
        )

        prompt = f"""Based on the complete analysis and adversarial debate for {ticker} ({year}),
generate a comprehensive final investment report.

=== FUNDAMENTAL DATA ===
{fundamental_analysis[:800]}

=== TECHNICAL DATA ===
{technical_analysis[:800]}

=== SENTIMENT DATA ===
{sentiment_analysis[:400]}

=== DEBATE TRANSCRIPT ===
{debate_summary}

Generate a professional investment report with:
1. **Executive Summary** (3 sentences max)
2. **Final Investment Rating**: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
3. **12-Month Price Target** with range (bear/base/bull)
4. **Investment Thesis** (key supporting arguments)
5. **Risk Factors** (top 3 risks with mitigation)
6. **Recommended Action**: Entry strategy, position size guidance
7. **Monitoring Triggers**: Events that would change the thesis

Format with clear headers. Be authoritative and precise."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=ANALYST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
