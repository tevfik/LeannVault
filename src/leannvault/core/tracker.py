"""
Hash-based file tracking with SQLite.

Maps file content hashes to current paths, ensuring the index
remains valid even when files are moved.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FileRecord:
    """Represents a tracked file in the database."""

    content_hash: str
    current_path: str
    original_path: str
    file_type: str
    size_bytes: int
    indexed_at: str
    last_seen_at: str
    is_valid: bool = True


class FileTracker:
    """
    SQLite-based file tracker using content hashes.

    The tracker maintains a mapping from content hashes to file paths,
    allowing the index to remain valid when files are moved.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize the file tracker.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path).expanduser().absolute()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    content_hash TEXT PRIMARY KEY,
                    current_path TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    is_valid INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_path
                ON files(current_path)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_valid
                ON files(is_valid)
            """)
            conn.commit()

    @staticmethod
    def compute_hash(file_path: Path, chunk_size: int = 8192) -> str:
        """
        Compute SHA-256 hash of file content.

        Args:
            file_path: Path to the file.
            chunk_size: Size of chunks to read at a time.

        Returns:
            Hexadecimal hash string.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def add_file(
        self,
        file_path: Path,
        content_hash: Optional[str] = None,
        original_path: Optional[str] = None,
    ) -> Optional[FileRecord]:
        """
        Add or update a file record in the tracker.

        Args:
            file_path: Current path to the file.
            content_hash: Pre-computed hash (optional, computed if not provided).
            original_path: Original path (defaults to current path).

        Returns:
            The created or updated FileRecord, or None if creation failed.
        """
        file_path = Path(file_path).absolute()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if content_hash is None:
            content_hash = self.compute_hash(file_path)

        now = datetime.now().isoformat()
        original = original_path or str(file_path)
        file_type = file_path.suffix.lower()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO files (content_hash, current_path, original_path, file_type, size_bytes, indexed_at, last_seen_at, is_valid)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(content_hash) DO UPDATE SET
                    current_path = excluded.current_path,
                    last_seen_at = excluded.last_seen_at,
                    is_valid = 1
            """,
                (
                    content_hash,
                    str(file_path),
                    original,
                    file_type,
                    file_path.stat().st_size,
                    now,
                    now,
                ),
            )
            conn.commit()

        return self.get_by_hash(content_hash)

    def get_by_hash(self, content_hash: str) -> Optional[FileRecord]:
        """
        Retrieve a file record by content hash.

        Args:
            content_hash: SHA-256 hash of the file content.

        Returns:
            FileRecord if found, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM files WHERE content_hash = ?", (content_hash,))
            row = cursor.fetchone()
            if row:
                return FileRecord(
                    content_hash=row["content_hash"],
                    current_path=row["current_path"],
                    original_path=row["original_path"],
                    file_type=row["file_type"],
                    size_bytes=row["size_bytes"],
                    indexed_at=row["indexed_at"],
                    last_seen_at=row["last_seen_at"],
                    is_valid=bool(row["is_valid"]),
                )
        return None

    def get_by_path(self, path: Path) -> Optional[FileRecord]:
        """
        Retrieve a file record by current path.

        Args:
            path: Current file path.

        Returns:
            FileRecord if found, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM files WHERE current_path = ?", (str(path.absolute()),)
            )
            row = cursor.fetchone()
            if row:
                return FileRecord(
                    content_hash=row["content_hash"],
                    current_path=row["current_path"],
                    original_path=row["original_path"],
                    file_type=row["file_type"],
                    size_bytes=row["size_bytes"],
                    indexed_at=row["indexed_at"],
                    last_seen_at=row["last_seen_at"],
                    is_valid=bool(row["is_valid"]),
                )
        return None

    def update_path(self, content_hash: str, new_path: Path) -> bool:
        """
        Update the current path for a file (after it was moved).

        Args:
            content_hash: Hash of the file content.
            new_path: New current path.

        Returns:
            True if updated, False if not found.
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE files SET current_path = ?, last_seen_at = ?, is_valid = 1 WHERE content_hash = ?",
                (str(new_path.absolute()), now, content_hash),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_invalid(self, content_hash: str) -> bool:
        """
        Mark a file as invalid (deleted or inaccessible).

        Args:
            content_hash: Hash of the file content.

        Returns:
            True if marked, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE files SET is_valid = 0 WHERE content_hash = ?", (content_hash,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, content_hash: str) -> bool:
        """
        Delete a file record from the tracker.

        Args:
            content_hash: Hash of the file content.

        Returns:
            True if deleted, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM files WHERE content_hash = ?", (content_hash,))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_files(self, valid_only: bool = False, limit: Optional[int] = None, offset: Optional[int] = None) -> list[FileRecord]:
        """Alias for list_all with pagination to support UI."""
        return self.list_all(valid_only=valid_only, limit=limit, offset=offset)

    def list_all(self, valid_only: bool = True, limit: Optional[int] = None, offset: Optional[int] = None) -> list[FileRecord]:
        """
        List all tracked files.

        Args:
            valid_only: If True, only return valid files.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of FileRecord objects.
        """
        query = "SELECT * FROM files"
        params = []
        if valid_only:
            query += " WHERE is_valid = 1"
        
        query += " ORDER BY indexed_at DESC"
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            records = []
            for row in cursor.fetchall():
                records.append(
                    FileRecord(
                        content_hash=row["content_hash"],
                        current_path=row["current_path"],
                        original_path=row["original_path"],
                        file_type=row["file_type"],
                        size_bytes=row["size_bytes"],
                        indexed_at=row["indexed_at"],
                        last_seen_at=row["last_seen_at"],
                        is_valid=bool(row["is_valid"]),
                    )
                )
        return records

    def search_files(self, name_query: str, limit: int = 100) -> list[FileRecord]:
        """Search files by name in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM files WHERE current_path LIKE ? ORDER BY indexed_at DESC LIMIT ?",
                (f"%{name_query}%", limit),
            )
            records = []
            for row in cursor.fetchall():
                records.append(
                    FileRecord(
                        content_hash=row["content_hash"],
                        current_path=row["current_path"],
                        original_path=row["original_path"],
                        file_type=row["file_type"],
                        size_bytes=row["size_bytes"],
                        indexed_at=row["indexed_at"],
                        last_seen_at=row["last_seen_at"],
                        is_valid=bool(row["is_valid"]),
                    )
                )
        return records

    def count(self, valid_only: bool = True) -> int:
        """
        Count tracked files.

        Args:
            valid_only: If True, only count valid files.

        Returns:
            Number of tracked files.
        """
        with sqlite3.connect(self.db_path) as conn:
            if valid_only:
                cursor = conn.execute("SELECT COUNT(*) FROM files WHERE is_valid = 1")
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM files")
            return cursor.fetchone()[0]

    def verify_paths(self) -> tuple[int, int]:
        """
        Verify all tracked paths exist and update validity.

        Returns:
            Tuple of (valid_count, invalid_count).
        """
        valid = 0
        invalid = 0
        for record in self.list_all(valid_only=False):
            path = Path(record.current_path)
            if path.exists():
                valid += 1
                self.update_path(record.content_hash, path)
            else:
                invalid += 1
                self.mark_invalid(record.content_hash)
        return valid, invalid
