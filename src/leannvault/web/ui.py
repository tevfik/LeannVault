"""
Professional Gradio UI for LeannVault.

Provides a user-friendly, colorful web interface for searching.
"""

from pathlib import Path
from typing import Optional

import gradio as gr

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher


def create_ui(index_path: Path, db_path: Path) -> gr.Blocks:
    """
    Create the Gradio UI with a professional look.
    """
    tracker = FileTracker(db_path)
    indexer = Indexer(index_path, tracker)
    searcher = Searcher(index_path, tracker)

    # Custom CSS for better result cards
    custom_css = """
    .result-card {
        border-left: 5px solid #2563eb;
        padding: 15px;
        margin-bottom: 15px;
        background-color: #f8fafc;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    .result-card:hover {
        background-color: #f1f5f9;
        transform: translateX(5px);
    }
    .source-header {
        font-weight: bold;
        color: #1e40af;
        font-size: 1.1em;
        margin-bottom: 5px;
    }
    .metadata-row {
        font-size: 0.85em;
        color: #64748b;
        margin-bottom: 10px;
    }
    .score-badge {
        background-color: #dcfce7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: bold;
    }
    .preview-box {
        background-color: white;
        color: #1e293b;
        padding: 10px;
        border-radius: 4px;
        border: 1px solid #e2e8f0;
        font-style: italic;
    }
    """

    def do_search(query: str, top_k: int) -> str:
        """Perform search and format results with HTML/Markdown."""
        try:
            if not query.strip():
                return "### ⚠️ Please enter a search query."

            if not searcher.is_ready():
                return f"### ❌ Index not ready. Run `leannvault index` first."

            results, latency = searcher.search_with_latency(query, top_k)

            if not results:
                return "### 🔍 No results found."

            output = f"## ⚡ Search completed in {latency:.2f} ms\n\n"

            for i, result in enumerate(results, 1):
                fname = Path(result.source).name if result.source else 'Unknown'
                preview = result.text[:400].replace('\n', ' ') + '...' if len(result.text) > 400 else result.text
                
                output += f"""
<div class="result-card">
    <div class="source-header">#{i} - {fname}</div>
    <div class="metadata-row">
        <span><b>Type:</b> {result.file_type}</span> | 
        <span class="score-badge">Match: {result.score:.4f}</span>
    </div>
    <div class="preview-box">
        "{preview}"
    </div>
    <div style="font-size: 0.8em; color: #94a3b8; margin-top: 5px;">
        Path: {result.current_path}
    </div>
</div>
"""
            return output
        except Exception as e:
            return f"### ❌ Error during search\n\n```python\n{str(e)}\n```"

    def get_status() -> str:
        """Get index status with visual styling."""
        try:
            stats = indexer.get_index_stats()
            status = "🟢 Ready" if searcher.is_ready() else "🔴 Not Ready"
            return f"""
### 📊 System Status: {status}

- **Index Size:** {stats["total_size_mb"]:.2f} MB
- **Documents:** {stats["total_files"]}
- **Tracked Files:** {stats["tracked_files"]}
- **Index Path:** 
  `{stats["index_path"]}`
"""
        except Exception:
            return "### 📊 System Status: 🟠 Unknown"

    # Define the professional theme
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
    ).set(
        body_background_fill="*neutral_50",
        block_title_text_weight="700",
        block_label_text_size="*text_sm",
    )

    with gr.Blocks(
        title="LeannVault 🌌",
        theme=theme,
        css=custom_css
    ) as demo:
        with gr.Row():
            gr.Markdown(
                """
                # 🌌 LeannVault
                ### The Ultimate Knowledge Layer for Your Machine
                *Hash-based vector search powered by LEANN and markitdown.*
                """
            )

        with gr.Row():
            with gr.Column(scale=3):
                with gr.Column(variant="panel"):
                    query_input = gr.Textbox(
                        label="🚀 Semantic Search",
                        placeholder="What are you looking for today?",
                        lines=2,
                        elem_id="search_box"
                    )
                    with gr.Row():
                        top_k_slider = gr.Slider(
                            minimum=1,
                            maximum=20,
                            value=5,
                            step=1,
                            label="Top results",
                        )
                        search_button = gr.Button("🔍 Search Files", variant="primary")
                
                results_output = gr.HTML(label="Search Results")

            with gr.Column(scale=1):
                with gr.Column(variant="panel"):
                    status_output = gr.Markdown(label="Status")
                    status_button = gr.Button("🔄 Refresh Status")
                
                gr.Markdown(
                    """
                    ### 💡 Search Tips
                    - Use natural language
                    - Search for concepts, not just words
                    - Example: *"Autonomous cooking journey senaryoları"*
                    """
                )

        # Event Handlers
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
    """
    demo = create_ui(index_path, db_path)
    app = gr.mount_gradio_app(app, demo, path=path)
    return app
