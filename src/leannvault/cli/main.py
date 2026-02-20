"""
LeannVault CLI - Command-line interface for hash-based vector search.

Commands:
    sync    - Scan directory and update path mappings
    index   - Index files from a directory
    search  - Semantic search across indexed documents
    delete  - Remove documents from index
    serve   - Start the web UI
    status  - Show index status
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional

console = Console()

DEFAULT_INDEX_PATH = Path.home() / ".leannvault" / "index.leann"
DEFAULT_DB_PATH = Path.home() / ".leannvault" / "vault.db"


def get_tracker(db_path: Path):
    """Get or create the file tracker."""
    from leannvault.core.tracker import FileTracker

    return FileTracker(db_path)


def get_indexer(index_path: Path, tracker):
    """Get the indexer."""
    from leannvault.core.indexer import Indexer

    return Indexer(index_path, tracker)


def get_searcher(index_path: Path, tracker):
    """Get the searcher."""
    from leannvault.core.searcher import Searcher

    return Searcher(index_path, tracker)


@click.group()
@click.version_option(version="0.2.0", prog_name="leannvault")
@click.option(
    "--index-path",
    type=click.Path(),
    default=str(DEFAULT_INDEX_PATH),
    help="Path to LEANN index",
)
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DEFAULT_DB_PATH),
    help="Path to SQLite database",
)
@click.pass_context
def cli(ctx, index_path, db_path):
    """
    LeannVault - Hash-based vector search with LEANN.

    Keep your index valid even when files move.
    """
    ctx.ensure_object(dict)
    ctx.obj["index_path"] = Path(index_path).expanduser()
    ctx.obj["db_path"] = Path(db_path).expanduser()


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Scan recursively")
@click.pass_context
def sync(ctx, directory, recursive):
    """
    Scan directory and update path mappings.

    Verifies that tracked files still exist and updates paths
    for files that have moved.
    """
    tracker = get_tracker(ctx.obj["db_path"])
    directory = Path(directory).expanduser().absolute()

    console.print(f"[bold blue]Scanning directory:[/] {directory}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Verifying tracked paths...", total=None)
        valid, invalid = tracker.verify_paths()
        progress.update(task, description="Verifying tracked paths... Done")

    console.print(f"[green]Valid files:[/] {valid}")
    console.print(f"[red]Invalid files:[/] {invalid}")

    console.print("\n[bold blue]Scanning for new/moved files...[/]")
    indexed_count = 0
    moved_count = 0

    from leannvault.core.indexer import Indexer

    indexer = Indexer(ctx.obj["index_path"], tracker)

    glob_pattern = "**/*" if recursive else "*"
    for file_path in directory.glob(glob_pattern):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in indexer.SUPPORTED_EXTENSIONS:
            continue

        content_hash = tracker.compute_hash(file_path)
        existing = tracker.get_by_hash(content_hash)

        if existing is None:
            indexed_count += 1
        elif existing.current_path != str(file_path):
            tracker.update_path(content_hash, file_path)
            moved_count += 1

    console.print(f"[green]New files found:[/] {indexed_count}")
    console.print(f"[yellow]Moved files updated:[/] {moved_count}")


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Index recursively")
@click.option("--min-length", default=50, help="Minimum text length to index")
@click.pass_context
def index(ctx, directory, recursive, min_length):
    """
    Index files from a directory.

    Extracts text and builds a LEANN index for semantic search.
    """
    tracker = get_tracker(ctx.obj["db_path"])
    indexer = get_indexer(ctx.obj["index_path"], tracker)
    directory = Path(directory).expanduser().absolute()

    console.print(f"[bold blue]Indexing directory:[/] {directory}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting text from documents...", total=None)
        documents = indexer.index_directory(directory, recursive, min_length)
        progress.update(task, description=f"Extracted {len(documents)} documents")

    if not documents:
        console.print("[yellow]No documents found to index.[/]")
        return

    console.print(f"[green]Documents to index:[/] {len(documents)}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building LEANN index...", total=None)
        indexer.build_index(documents)
        progress.update(task, description="Building LEANN index... Done")

    stats = indexer.get_index_stats()
    console.print(f"\n[bold green]Indexing Complete![/]")
    console.print(f"  Index size: {stats['total_size_mb']:.2f} MB")
    console.print(f"  Tracked files: {stats['tracked_files']}")


@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Number of results")
@click.pass_context
def search(ctx, query, top_k):
    """
    Semantic search across indexed documents.

    Returns the top-k most relevant documents for the query.
    """
    tracker = get_tracker(ctx.obj["db_path"])
    searcher = get_searcher(ctx.obj["index_path"], tracker)

    if not searcher.is_ready():
        console.print("[red]Error:[/] Index not found. Run 'leannvault index' first.")
        return

    console.print(f"[bold blue]Searching for:[/] {query}")

    results, latency = searcher.search_with_latency(query, top_k)

    table = Table(title=f"Search Results ({latency:.2f} ms)")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Source", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Score", style="magenta")
    table.add_column("Preview", style="white")

    for i, result in enumerate(results, 1):
        preview = result.text[:100] + "..." if len(result.text) > 100 else result.text
        table.add_row(
            str(i),
            Path(result.source).name if result.source else "Unknown",
            result.file_type,
            f"{result.score:.4f}",
            preview.replace("\n", " "),
        )

    console.print(table)


@cli.command()
@click.option("--hash", "content_hash", help="Delete by content hash")
@click.option("--path", "file_path", help="Delete by file path")
@click.pass_context
def delete(ctx, content_hash, file_path):
    """
    Remove documents from the index.

    Specify either --hash or --path to identify the document.
    """
    tracker = get_tracker(ctx.obj["db_path"])

    if content_hash:
        if tracker.delete(content_hash):
            console.print(f"[green]Deleted:[/] {content_hash[:16]}...")
        else:
            console.print(f"[red]Not found:[/] {content_hash[:16]}...")
    elif file_path:
        record = tracker.get_by_path(Path(file_path))
        if record and tracker.delete(record.content_hash):
            console.print(f"[green]Deleted:[/] {file_path}")
        else:
            console.print(f"[red]Not found:[/] {file_path}")
    else:
        console.print("[red]Error:[/] Specify --hash or --path")


@cli.command()
@click.option("--port", default=8000, help="Server port")
@click.option("--host", default="127.0.0.1", help="Server host")
@click.option("--share", is_flag=True, help="Enable Gradio sharing")
@click.pass_context
def serve(ctx, port, host, share):
    """
    Start the web UI.

    Launches FastAPI + Gradio interface for interactive searching.
    """
    from leannvault.web.api import create_app
    from leannvault.web.ui import create_ui
    import uvicorn
    import gradio as gr

    # Create UI and launch it with share option
    demo = create_ui(ctx.obj["index_path"], ctx.obj["db_path"])
    
    if share:
        console.print("[bold yellow]Gradio sharing enabled...[/]")
        # Launch independently for sharing
        demo.launch(server_name=host, server_port=port, share=True)
    else:
        # Standard FastAPI mount
        app = create_app(
            index_path=ctx.obj["index_path"],
            db_path=ctx.obj["db_path"],
        )
        app = gr.mount_gradio_app(app, demo, path="/")
        console.print(f"[bold green]Starting server at http://{host}:{port}[/]")
        uvicorn.run(app, host=host, port=port)


@cli.command()
@click.pass_context
def status(ctx):
    """
    Show index status.

    Displays statistics about the current index and tracked files.
    """
    tracker = get_tracker(ctx.obj["db_path"])
    indexer = get_indexer(ctx.obj["index_path"], tracker)
    searcher = get_searcher(ctx.obj["index_path"], tracker)

    stats = indexer.get_index_stats()

    table = Table(title="LeannVault Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Index Path", str(stats["index_path"]))
    table.add_row("Index Size", f"{stats['total_size_mb']:.2f} MB")
    table.add_row("Index Files", str(stats["total_files"]))
    table.add_row("Tracked Files", str(stats["tracked_files"]))
    table.add_row("Index Ready", "Yes" if searcher.is_ready() else "No")

    console.print(table)


if __name__ == "__main__":
    cli()
