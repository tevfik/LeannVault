#!/usr/bin/env python3
"""
LEANN Search Script for Office 365 corpus index.
Loads the index and performs test queries with latency measurement.
"""

import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_PATH = PROJECT_ROOT / "results" / "index.leann"

try:
    from leann import LeannSearcher
except ImportError:
    print("ERROR: LEANN not installed. Run: pip install leann")
    sys.exit(1)


def search_and_display(searcher: LeannSearcher, query: str, top_k: int = 3):
    print(f"\n{'=' * 60}")
    print(f"Query: '{query}'")
    print("-" * 60)

    start_time = time.perf_counter()
    results = searcher.search(query, top_k=top_k)
    latency_ms = (time.perf_counter() - start_time) * 1000

    for i, result in enumerate(results, 1):
        metadata = result.metadata or {}
        source = metadata.get("source", "Unknown")
        file_type = metadata.get("type", "Unknown")
        text = result.text or ""
        score = result.score or 0

        preview = text[:200] + "..." if len(text) > 200 else text

        print(f"\n  [{i}] Source: {source}")
        print(f"      Type: {file_type}")
        print(f"      Score: {score:.4f}")
        print(f"      Preview: {preview}")

    print(f"\n  Latency: {latency_ms:.2f} ms")
    return latency_ms


def main():
    print("=" * 60)
    print("LEANN Search Test")
    print("=" * 60)
    print(f"\nIndex path: {INDEX_PATH}")

    meta_path = Path(str(INDEX_PATH) + ".meta.json")
    if not meta_path.exists():
        print(f"ERROR: Index metadata not found at {meta_path}")
        print("Run 'scripts/index_leann.py' first.")
        sys.exit(1)

    print("\nLoading index...")
    start_load = time.perf_counter()
    searcher = LeannSearcher(str(INDEX_PATH))
    load_time = (time.perf_counter() - start_load) * 1000
    print(f"Index loaded in {load_time:.2f} ms")

    test_queries = [
        "Autonomous Cooking Journey",
        "AI Act requirements for ovens",
        "Recipe Assistant features",
    ]

    latencies = []
    for query in test_queries:
        latency = search_and_display(searcher, query, top_k=3)
        latencies.append(latency)

    print("\n" + "=" * 60)
    print("SEARCH SUMMARY")
    print("=" * 60)
    print(f"  Queries executed: {len(test_queries)}")
    print(f"  Average latency: {sum(latencies) / len(latencies):.2f} ms")
    print(f"  Min latency: {min(latencies):.2f} ms")
    print(f"  Max latency: {max(latencies):.2f} ms")


if __name__ == "__main__":
    main()
