"""
Gradio UI for LeannVault.

Provides a user-friendly web interface for searching.
"""

from pathlib import Path
from typing import Optional

import gradio as gr

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher


def create_ui(index_path: Path, db_path: Path) -> gr.Blocks:
    """
    Create the Gradio UI.

    Args:
        index_path: Path to the LEANN index.
        db_path: Path to the SQLite database.

    Returns:
        Gradio Blocks application.
    """
    tracker = FileTracker(db_path)
    indexer = Indexer(index_path, tracker)
    searcher = Searcher(index_path, tracker)

    def do_search(query: str, top_k: int) -> str:
        """Perform search and format results."""
        try:
            if not query.strip():
                return "Please enter a search query."

            if not searcher.is_ready():
                return f"Index not ready at {searcher.index_path}. Run 'leannvault index' first."

            results, latency = searcher.search_with_latency(query, top_k)

            if not results:
                return "No results found."

            output = f"**Search completed in {latency:.2f} ms**\n\n---\n\n"

            for i, result in enumerate(results, 1):
                output += f"### {i}. {Path(result.source).name if result.source else 'Unknown'}\n"
                output += f"- **Type:** {result.file_type}\n"
                output += f"- **Score:** {result.score:.4f}\n"
                if result.current_path:
                    output += f"- **Path:** `{result.current_path}`\n"
                output += f"\n> {result.text[:300]}{'...' if len(result.text) > 300 else ''}\n\n"
                output += "---\n\n"

            return output
        except Exception as e:
            import traceback
            return f"**Error during search:**\n\n```\n{str(e)}\n{traceback.format_exc()}\n```"

    def get_status() -> str:
        """Get index status."""
        stats = indexer.get_index_stats()
        status = "Ready" if searcher.is_ready() else "Not Ready"
        return f"""
**Index Status:** {status}

| Property | Value |
|----------|-------|
| Index Size | {stats["total_size_mb"]:.2f} MB |
| Index Files | {stats["total_files"]} |
| Tracked Files | {stats["tracked_files"]} |
| Index Path | `{stats["index_path"]}` |
"""

    with gr.Blocks(
        title="LeannVault",
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown(
            """
            # LeannVault
            
            Hash-based vector search with LEANN. Keep your index valid even when files move.
            """
        )

        with gr.Row():
            with gr.Column(scale=3):
                query_input = gr.Textbox(
                    label="Search Query",
                    placeholder="Enter your search query...",
                    lines=2,
                )
                top_k_slider = gr.Slider(
                    minimum=1,
                    maximum=20,
                    value=5,
                    step=1,
                    label="Number of Results",
                )
                search_button = gr.Button("Search", variant="primary")
                results_output = gr.Markdown(label="Results")

            with gr.Column(scale=1):
                status_button = gr.Button("Refresh Status")
                status_output = gr.Markdown(label="Status")

        search_button.click(
            fn=do_search,
            inputs=[query_input, top_k_slider],
            outputs=results_output,
        )

        query_input.submit(
            fn=do_search,
            inputs=[query_input, top_k_slider],
            outputs=results_output,
        )

        status_button.click(
            fn=get_status,
            inputs=[],
            outputs=status_output,
        )

        demo.load(
            fn=get_status,
            inputs=[],
            outputs=status_output,
        )

    return demo


def mount_ui(app, index_path: Path, db_path: Path, path: str = "/ui"):
    """
    Mount Gradio UI to a FastAPI app.

    Args:
        app: FastAPI application.
        index_path: Path to the LEANN index.
        db_path: Path to the SQLite database.
        path: Mount path for the UI.
    """
    demo = create_ui(index_path, db_path)
    app = gr.mount_gradio_app(app, demo, path=path)
    return app
