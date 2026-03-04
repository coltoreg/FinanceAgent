"""
Critic Agent: Adversarial validation and hallucination checker.
Challenges the Analyst's thesis by identifying blind spots and weak assumptions.
"""

from src.tools.tracing import get_traced_client, resolve_model_id


CRITIC_SYSTEM_PROMPT = """You are a Devil's Advocate — a senior risk manager and contrarian investor
whose job is to stress-test investment theses and find logical flaws.

Your mandate:
1. ALWAYS challenge the Analyst's thesis — this is your core function
2. Focus on: debt risks, valuation concerns, technical overbought signals,
   competitive threats, regulatory risks, and macro headwinds
3. Identify if the Analyst is ignoring red flags or cherry-picking data
4. Check for hallucinations or unsupported claims in the thesis
5. Provide specific, evidence-based counter-arguments

You are NOT a pessimist — you are rigorous. If the thesis is genuinely strong,
say so, but always find at least 2-3 meaningful challenges.

Critique rating: STRONG_CHALLENGE / MODERATE_CHALLENGE / MINOR_CHALLENGE"""


class CriticAgent:
    """
    Critic agent that provides adversarial challenges to the Analyst's thesis.
    Focuses on debt risks, overbought signals, and logical gaps.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = get_traced_client()
        self.model = resolve_model_id(model)

    def critique(
        self,
        ticker: str,
        analyst_thesis: str,
        fundamental_data: str,
        technical_data: str,
        sentiment_data: str,
        debate_round: int,
    ) -> str:
        """
        Challenge the Analyst's thesis with adversarial arguments.
        """
        round_instruction = (
            "This is the FIRST round — provide your most powerful challenges."
            if debate_round == 1
            else f"This is round {debate_round} — the Analyst has responded. "
            f"Escalate or pivot your critique based on their rebuttal. "
            f"If they made valid concessions, acknowledge them but find new angles."
        )

        prompt = f"""The Analyst has provided this investment thesis for {ticker}:

=== ANALYST'S THESIS ===
{analyst_thesis}

=== UNDERLYING DATA ===
Fundamental: {fundamental_data[:600]}

Technical: {technical_data[:600]}

Sentiment: {sentiment_data[:300]}

{round_instruction}

Your critique MUST cover:
1. **Valuation Risk**: Is the current price justified? Signs of overvaluation?
2. **Debt/Balance Sheet Risk**: Hidden leverage, refinancing risk, interest coverage
3. **Technical Overbought/Oversold**: Are technical signals diverging from fundamentals?
4. **Competitive Moat Challenge**: Is the competitive advantage as durable as claimed?
5. **Hallucination Check**: Any unsubstantiated claims or missing data in the thesis?
6. **Macro/Sector Risk**: Industry headwinds being overlooked?

Rate your overall challenge: STRONG_CHALLENGE / MODERATE_CHALLENGE / MINOR_CHALLENGE

Be sharp, specific, and cite data. Do not be diplomatic."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            system=CRITIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def final_verdict(self, ticker: str, debate_transcript: list[dict]) -> str:
        """
        After the debate, provide a final risk assessment summary.
        """
        transcript_text = "\n\n".join(
            f"{item['speaker'].upper()} (Round {item['round']}):\n{item['content'][:400]}"
            for item in debate_transcript
        )

        prompt = f"""After {len(debate_transcript) // 2} rounds of debate on {ticker},
provide your final risk assessment.

=== DEBATE TRANSCRIPT ===
{transcript_text}

Summarize:
1. **Unresolved Risks**: Issues the Analyst failed to adequately address
2. **Conceded Points**: Analyst's arguments you found convincing
3. **Risk Rating**: LOW / MEDIUM / HIGH / VERY_HIGH
4. **Key Downside Scenario**: Most likely path to investment loss
5. **Recommendation Override** (if warranted): Should the rating be downgraded?

Keep it under 300 words. Be decisive."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=CRITIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
