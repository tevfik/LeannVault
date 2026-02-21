"""
FastAPI application for LeannVault.

Provides REST API endpoints for search and management.
"""

from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    top_k: int = 5


class SearchResultModel(BaseModel):
    """Search result model."""

    id: Union[int, str]
    text: str
    score: float
    source: str
    file_type: str
    content_hash: str
    current_path: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response model."""

    results: list[SearchResultModel]
    latency_ms: float
    total: int


class StatusResponse(BaseModel):
    """Status response model."""

    index_path: str
    index_size_mb: float
    index_files: int
    tracked_files: int
    index_ready: bool


class DeleteRequest(BaseModel):
    """Delete request model."""

    content_hash: Optional[str] = None
    file_path: Optional[str] = None


class SyncRequest(BaseModel):
    """Sync request model."""

    directory: str
    recursive: bool = True


class SyncResponse(BaseModel):
    """Sync response model."""

    valid_files: int
    invalid_files: int
    new_files: int
    moved_files: int


def create_app(index_path: Path, db_path: Path) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        index_path: Path to the LEANN index.
        db_path: Path to the SQLite database.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="LeannVault",
        description="Hash-based vector search with LEANN",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    tracker = FileTracker(db_path)
    indexer = Indexer(index_path, tracker)
    searcher = Searcher(index_path, tracker)

    @app.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get index status."""
        stats = indexer.get_index_stats()
        return StatusResponse(
            index_path=stats["index_path"],
            index_size_mb=stats["total_size_mb"],
            index_files=stats["total_files"],
            tracked_files=stats["tracked_files"],
            index_ready=searcher.is_ready(),
        )

    @app.post("/search", response_model=SearchResponse)
    async def search(request: SearchRequest):
        """Perform semantic search."""
        if not searcher.is_ready():
            raise HTTPException(status_code=503, detail="Index not ready")

        results, latency = searcher.search_with_latency(request.query, request.top_k)

        return SearchResponse(
            results=[
                SearchResultModel(
                    id=r.id,
                    text=r.text,
                    score=r.score,
                    source=r.source,
                    file_type=r.file_type,
                    content_hash=r.content_hash,
                    current_path=r.current_path,
                )
                for r in results
            ],
            latency_ms=latency,
            total=len(results),
        )

    @app.post("/delete")
    async def delete_document(request: DeleteRequest):
        """Delete a document from the index."""
        if request.content_hash:
            if tracker.delete(request.content_hash):
                return {"status": "deleted", "content_hash": request.content_hash}
            raise HTTPException(status_code=404, detail="Document not found")
        elif request.file_path:
            record = tracker.get_by_path(Path(request.file_path))
            if record and tracker.delete(record.content_hash):
                return {"status": "deleted", "file_path": request.file_path}
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(status_code=400, detail="Specify content_hash or file_path")

    @app.post("/sync", response_model=SyncResponse)
    async def sync_directory(request: SyncRequest):
        """Sync a directory."""
        directory = Path(request.directory).expanduser().absolute()
        if not directory.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        valid, invalid = tracker.verify_paths()

        new_files = 0
        moved_files = 0

        glob_pattern = "**/*" if request.recursive else "*"
        for file_path in directory.glob(glob_pattern):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in indexer.SUPPORTED_EXTENSIONS:
                continue

            content_hash = tracker.compute_hash(file_path)
            existing = tracker.get_by_hash(content_hash)

            if existing is None:
                new_files += 1
            elif existing.current_path != str(file_path):
                tracker.update_path(content_hash, file_path)
                moved_files += 1

        return SyncResponse(
            valid_files=valid,
            invalid_files=invalid,
            new_files=new_files,
            moved_files=moved_files,
        )

    @app.get("/files")
    async def list_files(valid_only: bool = True):
        """List all tracked files."""
        records = tracker.list_all(valid_only)
        return [
            {
                "content_hash": r.content_hash,
                "current_path": r.current_path,
                "original_path": r.original_path,
                "file_type": r.file_type,
                "size_bytes": r.size_bytes,
                "is_valid": r.is_valid,
            }
            for r in records
        ]

    from leannvault.web.ui import create_ui
    import gradio as gr

    ui_blocks, theme, custom_css = create_ui(index_path, db_path)
    app = gr.mount_gradio_app(app, ui_blocks, path="/ui", theme=theme, css=custom_css)

    return app
