"""
SEC EDGAR retriever using LlamaParse + ChromaDB + BM25 Hybrid Search.
Fetches 10-K/10-Q filings and builds a hybrid retrieval index.

LangSmith tracing:
  - get_company_facts()      → "sec_xbrl_fetch" span (shows ticker, CIK, concepts fetched)
  - HybridRetriever.search() → "hybrid_retrieval" span (shows query, scores, RRF fusion)
"""

import os
import json
import re
import requests
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi

from src.tools.tracing import traceable


# ── SEC EDGAR API endpoints ──────────────────────────────────────────────────
SEC_BASE_URL = "https://data.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_BASE_URL}/submissions"
SEC_COMPANY_FACTS_URL = f"{SEC_BASE_URL}/api/xbrl/companyfacts"

HEADERS = {
    "User-Agent": "FinAgent Research Tool (research@finagent.ai)",
    "Accept-Encoding": "gzip, deflate",
}

# ── XBRL concept map: (primary_concept, fallback_concept) ───────────────────
# Covers Income Statement + Balance Sheet + Cash Flow Statement
XBRL_CONCEPTS: dict[str, tuple[str, ...]] = {
    # ── Income Statement ────────────────────────────────────────────────────
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "rd_expense": ("ResearchAndDevelopmentExpense",),
    "sga_expense": ("SellingGeneralAndAdministrativeExpense",),
    "interest_expense": ("InterestExpense",),
    "income_tax": ("IncomeTaxExpenseBenefit",),
    "ebitda_proxy": ("OperatingIncomeLoss",),  # EBITDA requires D&A; proxy with EBIT
    "eps_basic": ("EarningsPerShareBasic",),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "shares_outstanding": ("CommonStockSharesOutstanding",),
    # ── Balance Sheet ────────────────────────────────────────────────────────
    "total_assets": ("Assets",),
    "current_assets": ("AssetsCurrent",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ),
    "total_liabilities": ("Liabilities",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "long_term_debt": (
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
    ),
    "shareholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "retained_earnings": ("RetainedEarningsAccumulatedDeficit",),
    "goodwill": ("Goodwill",),
    "intangible_assets": ("FiniteLivedIntangibleAssetsNet", "IntangibleAssetsNetExcludingGoodwill"),
    # ── Cash Flow Statement ──────────────────────────────────────────────────
    "operating_cf": ("NetCashProvidedByUsedInOperatingActivities",),
    "investing_cf": ("NetCashProvidedByUsedInInvestingActivities",),
    "financing_cf": ("NetCashProvidedByUsedInFinancingActivities",),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CapitalExpendituresIncurredButNotYetPaid",
    ),
    "depreciation_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
    ),
    "stock_based_compensation": ("ShareBasedCompensation",),
    "dividends_paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "share_repurchase": ("PaymentsForRepurchaseOfCommonStock",),
}


def get_cik_for_ticker(ticker: str) -> Optional[str]:
    """Look up CIK number for a stock ticker via SEC EDGAR company tickers JSON."""
    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(tickers_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            return str(entry["cik_str"]).zfill(10)
    return None


def get_recent_filings(cik: str, form_type: str = "10-K", count: int = 3) -> list[dict]:
    """Fetch recent filings metadata for a given CIK."""
    url = f"{SEC_SUBMISSIONS_URL}/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accession_numbers = filings.get("accessionNumber", [])
    primary_documents = filings.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form == form_type and len(results) < count:
            results.append(
                {
                    "form": form,
                    "date": dates[i],
                    "accession": accession_numbers[i].replace("-", ""),
                    "accession_dashes": accession_numbers[i],
                    "primary_doc": primary_documents[i],
                    "cik": cik,
                }
            )
    return results


@traceable(
    name="sec_xbrl_fetch",
    run_type="retriever",
    metadata={"source": "SEC EDGAR XBRL API"},
)
def get_company_facts(ticker: str) -> dict:
    """
    Fetch full financial three-statement data from SEC XBRL API.

    Covers Income Statement, Balance Sheet, and Cash Flow Statement.
    LangSmith trace: shows ticker, CIK resolved, concepts fetched, data points returned.
    """
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return {"ticker": ticker, "cik": None, "error": f"CIK not found for {ticker}"}

    url = f"{SEC_COMPANY_FACTS_URL}/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    facts_json = resp.json()

    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})

    def extract_annual(concepts: tuple[str, ...], n: int = 4, unit: str = "USD") -> list[dict]:
        """
        Try each concept in order; return last n annual (10-K) values.
        Deduplicates by fiscal year end, returns in descending order.
        For pure-ratio concepts (EPS) the unit is 'USD/shares'.
        """
        for concept in concepts:
            concept_data = us_gaap.get(concept, {})
            # Try the specified unit, fallback to first available unit
            units_map = concept_data.get("units", {})
            entries = units_map.get(unit) or next(iter(units_map.values()), [])
            if not entries:
                continue

            annual = [e for e in entries if e.get("form") == "10-K"]
            annual_sorted = sorted(annual, key=lambda x: x.get("end", ""), reverse=True)

            seen_years: set[str] = set()
            result = []
            for entry in annual_sorted:
                fy = entry.get("end", "")[:4]
                if fy not in seen_years:
                    seen_years.add(fy)
                    result.append(
                        {
                            "year": fy,
                            "end_date": entry.get("end", ""),
                            "value": entry.get("val", 0),
                            "accn": entry.get("accn", ""),
                        }
                    )
                if len(result) >= n:
                    break
            if result:
                return result
        return []

    def extract_per_share(concepts: tuple[str, ...], n: int = 4) -> list[dict]:
        return extract_annual(concepts, n=n, unit="USD/shares")

    def extract_shares(concepts: tuple[str, ...], n: int = 4) -> list[dict]:
        return extract_annual(concepts, n=n, unit="shares")

    result: dict = {"ticker": ticker, "cik": cik}

    for field, concepts in XBRL_CONCEPTS.items():
        if field in ("eps_basic", "eps_diluted"):
            result[field] = extract_per_share(concepts)
        elif field == "shares_outstanding":
            result[field] = extract_shares(concepts)
        else:
            result[field] = extract_annual(concepts)

    return result


class HybridRetriever:
    """
    Hybrid search: ChromaDB (dense semantic) + BM25 (sparse keyword).
    Results merged via Reciprocal Rank Fusion (RRF).

    LangSmith: search() is decorated with @traceable to show per-query
    retrieval details (query, dense hits, BM25 hits, final ranked docs).
    """

    def __init__(self, collection_name: str, persist_dir: str = "./data/chroma"):
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
        )
        self.bm25: Optional[BM25Okapi] = None
        self.documents: list[str] = []
        self.doc_ids: list[str] = []

    def add_documents(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """Add documents to ChromaDB and rebuild BM25 index."""
        self.documents.extend(documents)
        self.doc_ids.extend(ids)

        tokenized = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized)

        existing = set(self.collection.get()["ids"])
        new_docs = [
            (doc, id_, meta)
            for doc, id_, meta in zip(
                documents, ids, metadatas or [{}] * len(documents)
            )
            if id_ not in existing
        ]

        if new_docs:
            docs, new_ids, metas = zip(*new_docs)
            self.collection.add(
                documents=list(docs),
                ids=list(new_ids),
                metadatas=list(metas),
            )

    @traceable(
        name="hybrid_retrieval",
        run_type="retriever",
        metadata={"method": "ChromaDB+BM25+RRF"},
    )
    def search(self, query: str, top_k: int = 5, alpha: float = 0.5) -> list[dict]:
        """
        Hybrid search with Reciprocal Rank Fusion (RRF).

        alpha controls dense/sparse balance:
          alpha=1.0 → pure dense (semantic)
          alpha=0.0 → pure sparse (keyword)
          alpha=0.5 → equal weight (default)

        LangSmith trace metadata:
          - query string
          - dense hit count, BM25 hit count
          - final ranked document IDs with RRF scores
        """
        # ── Dense search (ChromaDB) ──────────────────────────────────────────
        dense_ranks: dict[str, int] = {}
        dense_docs: list[str] = []
        dense_ids: list[str] = []

        if self.collection.count() > 0:
            chroma_results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k * 2, self.collection.count()),
            )
            dense_docs = chroma_results["documents"][0]
            dense_ids = chroma_results["ids"][0]
            dense_ranks = {id_: rank for rank, id_ in enumerate(dense_ids)}

        # ── Sparse search (BM25) ─────────────────────────────────────────────
        sparse_ranks: dict[str, int] = {}
        if self.bm25 and self.documents:
            tokenized_query = query.lower().split()
            scores = self.bm25.get_scores(tokenized_query)
            ranked_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )
            for rank, idx in enumerate(ranked_indices[: top_k * 2]):
                sparse_ranks[self.doc_ids[idx]] = rank

        # ── Reciprocal Rank Fusion ───────────────────────────────────────────
        k = 60  # RRF smoothing constant
        all_ids = set(dense_ranks) | set(sparse_ranks)
        rrf_scores: dict[str, float] = {}

        for doc_id in all_ids:
            dense_score = alpha / (k + dense_ranks.get(doc_id, top_k * 2))
            sparse_score = (1 - alpha) / (k + sparse_ranks.get(doc_id, top_k * 2))
            rrf_scores[doc_id] = dense_score + sparse_score

        top_ids = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)[:top_k]

        id_to_doc = dict(zip(dense_ids, dense_docs))
        for idx, doc_id in enumerate(self.doc_ids):
            id_to_doc[doc_id] = self.documents[idx]

        return [
            {"id": doc_id, "content": id_to_doc[doc_id], "score": rrf_scores[doc_id]}
            for doc_id in top_ids
            if doc_id in id_to_doc
        ]


def parse_filing_text(text: str) -> dict[str, str]:
    """Parse SEC filing text into key sections (Item 1A, MD&A)."""
    sections: dict[str, str] = {}

    risk_pattern = re.compile(
        r"item\s+1a[\.\s]*risk\s+factors(.*?)(?=item\s+1b|item\s+2|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = risk_pattern.search(text)
    if match:
        sections["risk_factors"] = match.group(1).strip()[:5000]

    mda_pattern = re.compile(
        r"item\s+7[\.\s]*management.*?discussion(.*?)(?=item\s+7a|item\s+8|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = mda_pattern.search(text)
    if match:
        sections["mda"] = match.group(1).strip()[:5000]

    return sections


def build_sec_retriever(
    ticker: str, year: int, data_dir: str = "./data"
) -> tuple[HybridRetriever, dict]:
    """
    Build a HybridRetriever populated with SEC financial data.
    Returns (retriever, raw_facts) where raw_facts covers all three statements.
    """
    collection_name = f"{ticker.lower()}_{year}_sec"
    retriever = HybridRetriever(
        collection_name=collection_name,
        persist_dir=f"{data_dir}/chroma",
    )

    facts = get_company_facts(ticker)
    cik = facts.get("cik")

    # ── Add filing metadata documents ────────────────────────────────────────
    if cik:
        try:
            filings = get_recent_filings(cik, form_type="10-K", count=2)
            for filing in filings:
                doc_text = (
                    f"SEC {filing['form']} Filing for {ticker} "
                    f"filed on {filing['date']}. "
                    f"Accession: {filing['accession_dashes']}."
                )
                retriever.add_documents(
                    documents=[doc_text],
                    ids=[f"{ticker}_{filing['date']}_{filing['form']}"],
                    metadatas=[
                        {"ticker": ticker, "form": filing["form"], "date": filing["date"]}
                    ],
                )
        except Exception:
            pass

    # ── Add each financial metric as a searchable document ──────────────────
    label_map = {
        "revenue": "Revenue",
        "gross_profit": "Gross Profit",
        "operating_income": "Operating Income",
        "net_income": "Net Income",
        "rd_expense": "R&D Expense",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "long_term_debt": "Long-Term Debt",
        "shareholders_equity": "Shareholders Equity",
        "cash_and_equivalents": "Cash and Equivalents",
        "operating_cf": "Operating Cash Flow",
        "investing_cf": "Investing Cash Flow",
        "financing_cf": "Financing Cash Flow",
        "capex": "Capital Expenditure",
    }

    for field, label in label_map.items():
        values = facts.get(field, [])
        if values:
            vals_str = ", ".join(
                f"{v['year']}: ${v['value']:,.0f}" for v in values[:4]
            )
            doc_text = f"{ticker} {label} (annual, USD): {vals_str}"
            retriever.add_documents(
                documents=[doc_text],
                ids=[f"{ticker}_{field}"],
                metadatas=[{"ticker": ticker, "type": field}],
            )

    return retriever, facts
