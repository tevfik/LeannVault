"""
Professional Gradio UI for LeannVault v0.3.1.

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
    .vault-table-container {
        max-height: 400px;
        overflow-y: auto;
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
        """Fetch indexed files for the management table."""
        records = tracker.get_all_files()
        data = []
        for r in records:
            data.append({
                "Filename": Path(r.current_path).name,
                "Status": "✅ Valid" if r.is_valid else "⚠️ Moved",
                "Size (KB)": f"{r.size_bytes / 1024:.1f}",
                "Current Path": r.current_path,
                "Hash": r.content_hash
            })
        if not data:
            return pd.DataFrame(columns=["Filename", "Status", "Size (KB)", "Current Path", "Hash"])
        return pd.DataFrame(data)

    def delete_file_by_hash(file_hash: str):
        """Delete a single file from the vault."""
        if not file_hash:
            return "### ⚠️ Please provide a hash.", get_vault_data()
        
        if tracker.delete(file_hash):
            return f"### ✅ Deleted record: `{file_hash[:12]}...`", get_vault_data()
        return f"### ❌ Hash not found: `{file_hash}`", get_vault_data()

    def run_sync(directory: str):
        """Trigger a sync operation."""
        if not directory:
            return "### ⚠️ Please provide a directory to sync."
        try:
            # We use the tracker's verify_paths logic
            valid, invalid = tracker.verify_paths()
            return f"### ✅ Sync complete! Valid: {valid}, Invalidated: {invalid}", get_vault_data()
        except Exception as e:
            return f"### ❌ Sync failed: {str(e)}", get_vault_data()

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

    # Define theme
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
    ).set(
        body_background_fill="*neutral_50",
        block_title_text_weight="700",
    )

    with gr.Blocks(title="LeannVault 🌌", theme=theme, css=custom_css) as demo:
        gr.Markdown("# 🌌 LeannVault\n*Intelligent local knowledge management*")

        with gr.Tabs():
            # TAB 1: SEARCH
            with gr.TabItem("🔍 Search"):
                with gr.Row():
                    with gr.Column(scale=3):
                        query_input = gr.Textbox(label="Query", placeholder="What are you looking for?", lines=1)
                        search_btn = gr.Button("Search", variant="primary")
                        results_output = gr.HTML(label="Results")
                    with gr.Column(scale=1):
                        status_output = gr.Markdown(label="Status")
                        gr.Markdown("### 💡 Tips\nSearch for concepts, e.g., 'safety requirements' or 'project roadmap'.")

            # TAB 2: MANAGEMENT
            with gr.TabItem("⚙️ Management"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### 📂 Vault Files")
                        vault_table = gr.DataFrame(
                            value=get_vault_data(),
                            headers=["Filename", "Status", "Size (KB)", "Current Path", "Hash"],
                            interactive=False,
                            wrap=True
                        )
                        refresh_btn = gr.Button("🔄 Refresh Table")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 🛠️ Actions")
                        with gr.Column(variant="panel"):
                            hash_input = gr.Textbox(label="Delete by Hash", placeholder="Paste hash from table...")
                            delete_btn = gr.Button("🗑️ Delete from Vault", variant="stop")
                        
                        with gr.Column(variant="panel"):
                            sync_dir = gr.Textbox(label="Sync Directory", value=str(Path.home()))
                            sync_btn = gr.Button("🔄 Sync & Verify Paths")
                        
                        action_msg = gr.Markdown("")

        # Bindings
        search_btn.click(do_search, inputs=[query_input, gr.State(5)], outputs=results_output)
        refresh_btn.click(get_vault_data, outputs=vault_table)
        delete_btn.click(delete_file_by_hash, inputs=[hash_input], outputs=[action_msg, vault_table])
        sync_btn.click(run_sync, inputs=[sync_dir], outputs=[action_msg, vault_table])
        demo.load(get_system_status, outputs=status_output)

    return demo


def mount_ui(app, index_path: Path, db_path: Path, path: str = "/ui"):
    demo = create_ui(index_path, db_path)
    return gr.mount_gradio_app(app, demo, path=path)
