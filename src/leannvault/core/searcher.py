"""
Semantic search using LEANN.

Provides fast, accurate vector search over indexed documents.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from leannvault.core.tracker import FileTracker


@dataclass
class SearchResult:
    """Represents a search result."""

    id: Union[int, str]
    text: str
    score: float
    source: str
    file_type: str
    content_hash: str
    current_path: Optional[str] = None


class Searcher:
    """
    Semantic search over indexed documents.

    Uses LEANN's HNSW backend for fast approximate nearest neighbor search.
    """

    def __init__(
        self,
        index_path: str | Path,
        tracker: FileTracker,
    ):
        """
        Initialize the searcher.

        Args:
            index_path: Path to the LEANN index.
            tracker: FileTracker for resolving current paths.
        """
        self.index_path = Path(index_path).expanduser().absolute()
        self.tracker = tracker
        self._searcher = None

    def _load_searcher(self):
        """Lazy load the LEANN searcher."""
        if self._searcher is None:
            try:
                from leann import LeannSearcher
            except ImportError:
                raise ImportError("LEANN not installed. Run: pip install leann")

            self._searcher = LeannSearcher(str(self.index_path))
        return self._searcher

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Perform semantic search.

        Args:
            query: Search query.
            top_k: Number of results to return.

        Returns:
            List of SearchResult objects.
        """
        searcher = self._load_searcher()
        start_time = time.perf_counter()
        results = searcher.search(query, top_k=top_k)
        latency = (time.perf_counter() - start_time) * 1000

        search_results = []
        for result in results:
            metadata = result.metadata or {}
            content_hash = metadata.get("content_hash", "")

            record = self.tracker.get_by_hash(content_hash) if content_hash else None
            current_path = record.current_path if record else metadata.get("source", "")

            search_results.append(
                SearchResult(
                    id=result.id,
                    text=result.text or "",
                    score=result.score or 0,
                    source=metadata.get("source", "Unknown"),
                    file_type=metadata.get("type", "Unknown"),
                    content_hash=content_hash,
                    current_path=current_path,
                )
            )

        return search_results

    def search_with_latency(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[list[SearchResult], float]:
        """
        Perform semantic search and measure latency.

        Args:
            query: Search query.
            top_k: Number of results to return.

        Returns:
            Tuple of (SearchResult list, latency in ms).
        """
        searcher = self._load_searcher()
        start_time = time.perf_counter()
        results = searcher.search(query, top_k=top_k)
        latency = (time.perf_counter() - start_time) * 1000

        search_results = []
        for result in results:
            metadata = result.metadata or {}
            content_hash = metadata.get("content_hash", "")

            record = self.tracker.get_by_hash(content_hash) if content_hash else None
            current_path = record.current_path if record else metadata.get("source", "")

            search_results.append(
                SearchResult(
                    id=result.id,
                    text=result.text or "",
                    score=result.score or 0,
                    source=metadata.get("source", "Unknown"),
                    file_type=metadata.get("type", "Unknown"),
                    content_hash=content_hash,
                    current_path=current_path,
                )
            )

        return search_results, latency

    def is_ready(self) -> bool:
        """
        Check if the index is ready for searching.

        Returns:
            True if index exists and is ready.
        """
        meta_path = Path(str(self.index_path) + ".meta.json")
        return meta_path.exists()
