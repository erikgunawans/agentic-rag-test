"""RAG Evaluation Golden Set — run against a live backend.

Measures retrieval quality with 20 Indonesian legal queries.
Works both as a standalone script and as pytest tests.

Usage:
    python -m scripts.eval_rag --base-url http://localhost:8000 --token <JWT>
    pytest scripts/eval_rag.py -v
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass

import httpx

GOLDEN_SET = [
    # --- Regulation lookup (4) ---
    {
        "query": "Apa sanksi pelanggaran UU Perlindungan Data Pribadi?",
        "expected_keywords": ["sanksi", "data pribadi"],
        "category": None,
    },
    {
        "query": "Ketentuan OJK tentang pelaporan berkala perusahaan publik",
        "expected_keywords": ["OJK", "pelaporan", "publik"],
        "category": None,
    },
    {
        "query": "Peraturan pemerintah tentang pengadaan barang dan jasa",
        "expected_keywords": ["pengadaan", "barang", "jasa"],
        "category": None,
    },
    {
        "query": "Undang-undang ketenagakerjaan tentang pesangon dan PHK",
        "expected_keywords": ["pesangon", "PHK", "ketenagakerjaan"],
        "category": None,
    },
    # --- Contract clause search (4) ---
    {
        "query": "Klausul force majeure dalam perjanjian NDA",
        "expected_keywords": ["force majeure", "NDA"],
        "category": None,
    },
    {
        "query": "Ketentuan kerahasiaan dan non-disclosure dalam kontrak",
        "expected_keywords": ["kerahasiaan", "rahasia"],
        "category": None,
    },
    {
        "query": "Pasal tentang penyelesaian sengketa dan arbitrase",
        "expected_keywords": ["sengketa", "arbitrase"],
        "category": None,
    },
    {
        "query": "Klausul ganti rugi dan tanggung jawab hukum",
        "expected_keywords": ["ganti rugi", "tanggung jawab"],
        "category": None,
    },
    # --- Compliance obligations (4) ---
    {
        "query": "Kewajiban LHKPN bagi pejabat perusahaan BUMN",
        "expected_keywords": ["LHKPN"],
        "category": None,
    },
    {
        "query": "Persyaratan laporan tahunan ke OJK untuk emiten",
        "expected_keywords": ["laporan", "tahunan", "OJK"],
        "category": None,
    },
    {
        "query": "Ketentuan anti pencucian uang dan know your customer",
        "expected_keywords": ["pencucian uang"],
        "category": None,
    },
    {
        "query": "Kewajiban pelaporan insiden kebocoran data pribadi",
        "expected_keywords": ["kebocoran", "data pribadi", "insiden"],
        "category": None,
    },
    # --- Cross-reference queries (4) ---
    {
        "query": "Hubungan antara UU PDP dan peraturan OJK tentang data nasabah",
        "expected_keywords": ["PDP", "OJK", "data"],
        "category": None,
    },
    {
        "query": "Ketentuan yang mengatur tentang PT Maju Bersama",
        "expected_keywords": ["PT Maju Bersama"],
        "category": None,
    },
    {
        "query": "Dokumen yang menyebut pihak kedua dalam perjanjian kerja sama",
        "expected_keywords": ["pihak kedua", "perjanjian"],
        "category": None,
    },
    {
        "query": "Pasal yang dirujuk oleh klausul pemutusan kontrak",
        "expected_keywords": ["pemutusan", "kontrak"],
        "category": None,
    },
    # --- Bilingual queries (4) ---
    {
        "query": "What are the termination clauses in the employment agreement?",
        "expected_keywords": ["termination", "pemutusan"],
        "category": None,
    },
    {
        "query": "Confidentiality obligations dalam NDA antara kedua pihak",
        "expected_keywords": ["confidentiality", "kerahasiaan", "NDA"],
        "category": None,
    },
    {
        "query": "Data protection requirements under Indonesian law",
        "expected_keywords": ["data", "protection", "perlindungan"],
        "category": None,
    },
    {
        "query": "Corporate governance compliance untuk perusahaan publik Indonesia",
        "expected_keywords": ["governance", "compliance"],
        "category": None,
    },
]


@dataclass
class QueryResult:
    query: str
    chunks_returned: int
    keyword_hits: int
    keyword_total: int
    keyword_hit_rate: float
    mrr: float  # 1/rank of first chunk containing any expected keyword


def evaluate_query(
    query_item: dict,
    base_url: str,
    token: str,
    top_k: int = 5,
    *,
    client: httpx.Client | None = None,
) -> QueryResult:
    """Run a single golden query and compute metrics."""
    def _do_request(c: httpx.Client):
        resp = c.post(
            f"{base_url}/documents/search",
            json={"query": query_item["query"], "top_k": top_k, "mode": "hybrid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()

    if client:
        data = _do_request(client)
    else:
        with httpx.Client(timeout=30) as c:
            data = _do_request(c)

    results = data.get("results", [])
    expected_kw = query_item["expected_keywords"]
    all_text = " ".join(r.get("content", "") for r in results).lower()

    # Keyword hit rate
    hits = sum(1 for kw in expected_kw if kw.lower() in all_text)

    # MRR: 1/rank of first chunk containing any keyword
    mrr = 0.0
    for rank, chunk in enumerate(results, 1):
        content = chunk.get("content", "").lower()
        if any(kw.lower() in content for kw in expected_kw):
            mrr = 1.0 / rank
            break

    return QueryResult(
        query=query_item["query"],
        chunks_returned=len(results),
        keyword_hits=hits,
        keyword_total=len(expected_kw),
        keyword_hit_rate=hits / len(expected_kw) if expected_kw else 0.0,
        mrr=mrr,
    )


def evaluate_all(
    base_url: str, token: str, top_k: int = 5
) -> tuple[list[QueryResult], dict]:
    """Run all golden queries and compute aggregate metrics."""
    results = []
    with httpx.Client(timeout=30) as client:
        for item in GOLDEN_SET:
            try:
                r = evaluate_query(item, base_url, token, top_k, client=client)
                results.append(r)
            except Exception as e:
                print(f"  SKIP: {item['query'][:50]}... — {e}")

    if not results:
        return results, {"avg_keyword_hit_rate": 0, "avg_mrr": 0, "queries_with_hits": 0}

    avg_khr = sum(r.keyword_hit_rate for r in results) / len(results)
    avg_mrr = sum(r.mrr for r in results) / len(results)
    queries_with_hits = sum(1 for r in results if r.mrr > 0)

    return results, {
        "avg_keyword_hit_rate": round(avg_khr, 3),
        "avg_mrr": round(avg_mrr, 3),
        "queries_with_hits": queries_with_hits,
        "total_queries": len(results),
        "hit_rate_pct": round(queries_with_hits / len(results) * 100, 1),
    }


def print_report(results: list[QueryResult], metrics: dict):
    """Print a formatted evaluation report."""
    print("\n" + "=" * 80)
    print("  RAG EVALUATION REPORT")
    print("=" * 80)
    print(f"\n{'#':<3} {'Query':<50} {'Chunks':<7} {'KW Hit':<8} {'MRR':<6}")
    print("-" * 80)
    for i, r in enumerate(results, 1):
        q = r.query[:48] + ".." if len(r.query) > 50 else r.query
        kw = f"{r.keyword_hits}/{r.keyword_total}"
        print(f"{i:<3} {q:<50} {r.chunks_returned:<7} {kw:<8} {r.mrr:<6.3f}")

    print("-" * 80)
    print(f"\n  Avg Keyword Hit Rate: {metrics['avg_keyword_hit_rate']:.3f}")
    print(f"  Avg MRR:              {metrics['avg_mrr']:.3f}")
    print(f"  Queries with hits:    {metrics['queries_with_hits']}/{metrics['total_queries']} ({metrics['hit_rate_pct']}%)")
    print("=" * 80)


# --- Pytest entry point ---

def test_rag_golden_set():
    """Pytest: run golden set against configured backend."""
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    token = os.environ.get("TEST_TOKEN", "")
    if not token:
        # Try to login with test credentials
        email = os.environ.get("TEST_EMAIL", "test@test.com")
        password = os.environ.get("TEST_PASSWORD", "")
        if not password:
            import pytest
            pytest.skip("No TEST_TOKEN or TEST_PASSWORD set")
        from supabase import create_client
        sb = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_ANON_KEY", ""),
        )
        auth = sb.auth.sign_in_with_password({"email": email, "password": password})
        token = auth.session.access_token

    results, metrics = evaluate_all(base_url, token)
    print_report(results, metrics)
    assert metrics["avg_keyword_hit_rate"] >= 0.3, (
        f"Keyword hit rate {metrics['avg_keyword_hit_rate']:.3f} below threshold 0.3"
    )


# --- CLI entry point ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Evaluation Golden Set")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="JWT access token")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    results, metrics = evaluate_all(args.base_url, args.token, args.top_k)
    print_report(results, metrics)

    if metrics["avg_keyword_hit_rate"] < 0.3:
        print("\nFAIL: Keyword hit rate below threshold")
        sys.exit(1)
    print("\nPASS")
