"""
Professional Gradio UI for LeannVault v0.3.0.

Provides a user-friendly, multi-tab interface for searching and managing the vault.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List

import gradio as gr

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher


def create_ui(index_path: Path, db_path: Path) -> gr.Blocks:
    """
    Create the multi-tab Gradio UI.
    """
    tracker = FileTracker(db_path)
    indexer = Indexer(index_path, tracker)
    searcher = Searcher(index_path, tracker)

    # Custom CSS for better result cards and layout
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
    .status-panel {
        padding: 10px;
        background-color: #f1f5f9;
        border-radius: 8px;
    }
    """

    def do_search(query: str, top_k: int) -> str:
        """Perform search and format results with HTML/Markdown."""
        try:
            if not query.strip():
                return "### ⚠️ Please enter a search query."

            if not searcher.is_ready():
                return f"### ❌ Index not ready. Run `leannvault index` first."

            results, latency = searcher.search_with_latency(query, int(top_k))

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

    def get_vault_data():
        """Fetch all indexed files from SQLite for the management table."""
        records = tracker.get_all_files()
        data = []
        for r in records:
            data.append({
                "Filename": Path(r.current_path).name,
                "Hash": r.content_hash[:12] + "...",
                "Extension": Path(r.current_path).suffix,
                "Status": "✅ Valid" if r.is_valid else "⚠️ Moved",
                "Current Path": r.current_path,
                "Full Hash": r.content_hash
            })
        return pd.DataFrame(data)

    def delete_files(selected_data: pd.DataFrame):
        """Delete selected files from the vault."""
        if selected_data is None or len(selected_data) == 0:
            return "No files selected.", get_vault_data()
        
        deleted_count = 0
        for _, row in selected_data.iterrows():
            full_hash = row["Full Hash"]
            if tracker.delete(full_hash):
                deleted_count += 1
        
        return f"Successfully removed {deleted_count} files from vault.", get_vault_data()

    def get_system_status() -> str:
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
        gr.Markdown(
            """
            # 🌌 LeannVault
            ### The Ultimate Knowledge Layer for Your Machine
            """
        )

        with gr.Tabs():
            # Tab 1: Search
            with gr.TabItem("🔍 Semantic Search"):
                with gr.Row():
                    with gr.Column(scale=3):
                        with gr.Column(variant="panel"):
                            query_input = gr.Textbox(
                                label="🚀 Search Query",
                                placeholder="What are you looking for today?",
                                lines=2
                            )
                            with gr.Row():
                                top_k_slider = gr.Slider(
                                    minimum=1, maximum=20, value=5, step=1,
                                    label="Top results"
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
                            - Example: *"Transformer architecture overview"*
                            """
                        )

            # Tab 2: Vault Management
            with gr.TabItem("⚙️ Vault Management"):
                gr.Markdown("### 📂 Indexed Files")
                with gr.Column(variant="panel"):
                    vault_table = gr.DataFrame(
                        value=get_vault_data(),
                        headers=["Filename", "Extension", "Status", "Current Path", "Hash"],
                        datatype=["str", "str", "str", "str", "str"],
                        interactive=False,
                    )
                    with gr.Row():
                        refresh_vault_btn = gr.Button("🔄 Refresh List")
                        delete_msg = gr.Markdown("")
                
                gr.Markdown("> **Note:** File management is read-only in this version. Use CLI for advanced operations.")

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
            fn=get_system_status,
            inputs=[],
            outputs=status_output,
        )

        refresh_vault_btn.click(
            fn=get_vault_data,
            inputs=[],
            outputs=vault_table,
        )

        demo.load(
            fn=get_system_status,
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
