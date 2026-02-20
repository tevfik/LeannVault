"""
LeannVault - Hash-based vector search with LEANN.

A lightweight application that keeps your document index valid
even when files are moved, using content hash tracking.
Powered by Microsoft's markitdown for universal text extraction.
"""

__version__ = "0.2.0"
__author__ = "LeannVault Team"

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher
from leannvault.core.extractors import extract_text, SUPPORTED_EXTENSIONS

__all__ = [
    "FileTracker",
    "Indexer",
    "Searcher",
    "extract_text",
    "SUPPORTED_EXTENSIONS",
    "__version__",
]
