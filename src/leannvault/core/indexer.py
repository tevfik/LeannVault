"""
LEANN-based document indexer with hash tracking.

Extracts text from various file formats and indexes them
using LEANN's HNSW backend.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from leannvault.core.tracker import FileTracker, FileRecord


@dataclass
class IndexedDocument:
    """Represents an indexed document."""

    content_hash: str
    text: str
    metadata: dict
    file_record: FileRecord


class Indexer:
    """
    Document indexer using LEANN with hash-based tracking.

    Supports PDF, PPTX, DOCX, and JSON (email) files.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".json"}

    def __init__(
        self,
        index_path: str | Path,
        tracker: FileTracker,
    ):
        """
        Initialize the indexer.

        Args:
            index_path: Path for the LEANN index.
            tracker: FileTracker instance for hash management.
        """
        self.index_path = Path(index_path).expanduser().absolute()
        self.tracker = tracker
        self._builder = None

    def _get_extractor(self, file_path: Path):
        """Get the appropriate text extractor for a file type."""
        from leannvault.core.extractors import (
            extract_text_from_docx,
            extract_text_from_pdf,
            extract_text_from_pptx,
            extract_text_from_json_email,
        )

        extractors = {
            ".pdf": extract_text_from_pdf,
            ".pptx": extract_text_from_pptx,
            ".docx": extract_text_from_docx,
            ".json": extract_text_from_json_email,
        }
        return extractors.get(file_path.suffix.lower())

    def extract_text(self, file_path: Path) -> Optional[str]:
        """
        Extract text from a supported file.

        Args:
            file_path: Path to the file.

        Returns:
            Extracted text or None if extraction failed.
        """
        extractor = self._get_extractor(file_path)
        if extractor is None:
            return None
        return extractor(file_path)

    def index_file(self, file_path: Path, min_text_length: int = 50) -> Optional[IndexedDocument]:
        """
        Index a single file.

        Args:
            file_path: Path to the file.
            min_text_length: Minimum text length to index.

        Returns:
            IndexedDocument if successful, None otherwise.
        """
        file_path = Path(file_path).absolute()
        if not file_path.exists():
            return None

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return None

        content_hash = self.tracker.compute_hash(file_path)
        existing = self.tracker.get_by_hash(content_hash)
        if existing and existing.is_valid:
            return None

        text = self.extract_text(file_path)
        if not text or len(text.strip()) < min_text_length:
            return None

        record = self.tracker.add_file(file_path, content_hash=content_hash)

        metadata = {
            "source": str(file_path),
            "type": file_path.suffix.lower(),
            "size_bytes": file_path.stat().st_size,
            "content_hash": content_hash,
        }

        return IndexedDocument(
            content_hash=content_hash,
            text=text.strip(),
            metadata=metadata,
            file_record=record,
        )

    def index_directory(
        self,
        directory: Path,
        recursive: bool = True,
        min_text_length: int = 50,
    ) -> list[IndexedDocument]:
        """
        Index all supported files in a directory.

        Args:
            directory: Path to the directory.
            recursive: Whether to search recursively.
            min_text_length: Minimum text length to index.

        Returns:
            List of IndexedDocument objects.
        """
        directory = Path(directory).absolute()
        if not directory.exists():
            return []

        documents = []
        glob_pattern = "**/*" if recursive else "*"

        for file_path in directory.glob(glob_pattern):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            doc = self.index_file(file_path, min_text_length)
            if doc:
                documents.append(doc)

        return documents

    def build_index(self, documents: list[IndexedDocument]) -> None:
        """
        Build the LEANN index from indexed documents.

        Args:
            documents: List of IndexedDocument objects.
        """
        try:
            from leann import LeannBuilder
        except ImportError:
            raise ImportError("LEANN not installed. Run: pip install leann")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        builder = LeannBuilder(backend_name="hnsw")

        for doc in documents:
            builder.add_text(doc.text, metadata=doc.metadata)

        builder.build_index(str(self.index_path))

    def get_index_stats(self) -> dict:
        """
        Get statistics about the current index.

        Returns:
            Dictionary with index statistics.
        """
        index_dir = self.index_path.parent
        index_files = list(index_dir.glob("index.*")) + list(index_dir.glob("*.leann.*"))

        total_size = sum(f.stat().st_size for f in index_files if f.is_file())

        return {
            "index_path": str(self.index_path),
            "total_files": len(index_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "tracked_files": self.tracker.count(),
        }
