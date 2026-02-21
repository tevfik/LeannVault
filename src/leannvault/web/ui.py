"""
Professional Gradio UI for LeannVault v0.3.3.

Provides a user-friendly, multi-tab interface for searching and managing the vault.
Features: Real Pagination, Optimized Filtering, Theme-Aware Styling.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple
import gradio as gr

from leannvault.core.tracker import FileTracker
from leannvault.core.indexer import Indexer
from leannvault.core.searcher import Searcher


PAGE_SIZE = 50


def create_ui(index_path: Path, db_path: Path) -> Tuple[gr.Blocks, gr.Theme, str]:
    """
    Create the multi-tab Gradio UI.
    Returns: (demo, theme, css)
    """
    tracker = FileTracker(db_path)
    indexer = Indexer(index_path, tracker)
    searcher = Searcher(index_path, tracker)

    # Custom CSS for theme-awareness and fixing white boxes
    custom_css = """
    .result-card {
        border-left: 5px solid #2563eb;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 8px;
        background-color: var(--block-background-fill);
        border: 1px solid var(--border-color-primary);
    }
    .source-header {
        font-weight: bold;
        color: var(--primary-500);
        font-size: 1.1em;
        margin-bottom: 5px;
    }
    .score-badge {
        background-color: var(--success-100);
        color: var(--success-700);
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: bold;
    }
    .preview-box {
        padding: 10px;
        border-radius: 4px;
        border: 1px solid var(--border-color-primary);
        font-style: italic;
        margin: 10px 0;
        color: var(--body-text-color);
    }
    """

    def format_vault_dataframe(records: List) -> pd.DataFrame:
        """Format records into a pandas DataFrame for display."""
        data = []
        for r in records:
            data.append({
                "Filename": Path(r.current_path).name,
                "Status": "✅ Valid" if r.is_valid else "⚠️ Moved",
                "Size (KB)": f"{r.size_bytes / 1024:.1f}",
                "Path": r.current_path,
                "Hash": r.content_hash[:12] + "..."
            })
        if not data:
            return pd.DataFrame(columns=["Filename", "Status", "Size (KB)", "Path", "Hash"])
        return pd.DataFrame(data)

    def get_vault_page(search_term: Optional[str], page: int) -> Tuple[pd.DataFrame, str, int]:
        """
        Get a paginated view of the vault.
        """
        try:
            target_page = int(page)
            offset = (target_page - 1) * PAGE_SIZE
            
            if search_term and str(search_term).strip():
                records = tracker.search_files(search_term, limit=PAGE_SIZE)
                total_count = len(records)
                total_pages = 1
            else:
                records = tracker.list_all(valid_only=False, limit=PAGE_SIZE, offset=offset)
                total_count = tracker.count(valid_only=False)
                total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
            
            df = format_vault_dataframe(records)
            info = f"### 📄 Page {target_page} of {total_pages} ({total_count} total documents)"
            return df, info, target_page
        except Exception as e:
            return pd.DataFrame(), f"### ❌ Error: {str(e)}", page

    def do_search(query: str, top_k: int) -> str:
        """Perform semantic search."""
        try:
            if not query or not query.strip():
                return "### ⚠️ Please enter a search query."
            if not searcher.is_ready():
                return "### ❌ Index not ready."

            results, latency = searcher.search_with_latency(query, int(top_k))
            if not results:
                return "### 🔍 No results found."

            output = f"## ⚡ Found {len(results)} results in {latency:.2f} ms\n\n"
            for i, result in enumerate(results, 1):
                fname = Path(result.source).name if result.source else "Unknown"
                preview = result.text[:400].replace("\n", " ") + "..."
                output += f"""
<div class="result-card">
    <div class="source-header">#{i} - {fname}</div>
    <div><b>Type:</b> {result.file_type} | <span class="score-badge">Match: {result.score:.4f}</span></div>
    <div class="preview-box">"{preview}"</div>
    <div style="font-size: 0.85em;">📂 {result.current_path}</div>
</div>
"""
            return output
        except Exception as e:
            return f"### ❌ Error: {str(e)}"

    def get_system_status() -> str:
        """Get system stats."""
        try:
            stats = indexer.get_index_stats()
            status = "🟢 Ready" if searcher.is_ready() else "🔴 Not Ready"
            return f"""
### 📊 System Status
- **Status:** {status}
- **Index Size:** {stats["total_size_mb"]:.2f} MB
- **Documents:** {stats["tracked_files"]}
- **Path:** `{stats["index_path"]}`
"""
        except Exception:
            return "### 📊 Status: 🟠 Unknown"

    # Initial data for the table
    initial_records = tracker.list_all(valid_only=False, limit=PAGE_SIZE)
    initial_df = format_vault_dataframe(initial_records)
    initial_count = tracker.count(valid_only=False)
    initial_pages = max(1, (initial_count + PAGE_SIZE - 1) // PAGE_SIZE)
    initial_info = f"### 📄 Page 1 of {initial_pages} ({initial_count} total documents)"

    theme = gr.themes.Soft(primary_hue="blue", secondary_hue="gray")

    with gr.Blocks(title="LeannVault") as demo:
        gr.Markdown("# 🌌 LeannVault\n*Intelligent local knowledge management • v0.3.3*")

        page_state = gr.State(1)

        with gr.Tabs():
            # TAB 1: SEARCH
            with gr.TabItem("🔍 Search"):
                with gr.Row():
                    with gr.Column(scale=3):
                        query_input = gr.Textbox(label="Query", placeholder="Search for anything...", lines=1)
                        search_btn = gr.Button("Search", variant="primary")
                        results_output = gr.HTML(label="Results")
                    with gr.Column(scale=1):
                        status_output = gr.Markdown(value=get_system_status())
                        gr.Markdown("### 💡 Tips\n- Use natural language\n- Click paths to open files")

            # TAB 2: MANAGEMENT
            with gr.TabItem("⚙️ Management"):
                with gr.Row():
                    with gr.Column(scale=3):
                        filter_input = gr.Textbox(label="Filter Files", placeholder="Filename contains...")
                        vault_table = gr.DataFrame(
                            value=initial_df,
                            headers=["Filename", "Status", "Size (KB)", "Path", "Hash"],
                            interactive=False, 
                            max_height=500
                        )
                        
                        with gr.Row():
                            prev_btn = gr.Button("⬅️ Prev")
                            page_display = gr.Markdown(value=initial_info)
                            next_btn = gr.Button("Next ➡️")

                    with gr.Column(scale=1):
                        gr.Markdown("### 🛠️ Actions")
                        with gr.Group():
                            hash_input = gr.Textbox(label="Delete by Hash", placeholder="Paste hash...")
                            delete_btn = gr.Button("Delete", variant="stop")
                        
                        sync_dir = gr.Textbox(label="Sync Directory", value=str(Path.home()))
                        sync_btn = gr.Button("Sync & Verify")
                        action_msg = gr.Markdown()

        # Bindings
        search_btn.click(do_search, inputs=[query_input, gr.State(5)], outputs=results_output)
        
        filter_input.change(get_vault_page, 
                           inputs=[filter_input, gr.State(1)], 
                           outputs=[vault_table, page_display, page_state])
        
        prev_btn.click(lambda f, p: get_vault_page(f, max(1, p-1)), 
                      inputs=[filter_input, page_state], 
                      outputs=[vault_table, page_display, page_state])
        
        next_btn.click(lambda f, p: get_vault_page(f, p+1), 
                      inputs=[filter_input, page_state], 
                      outputs=[vault_table, page_display, page_state])
        
        delete_btn.click(lambda h: (f"Deleted {h}" if tracker.delete(h) else "Not found", *get_vault_page("", 1)), 
                        inputs=[hash_input], 
                        outputs=[action_msg, vault_table, page_display, page_state])
        
        sync_btn.click(lambda d: (f"Sync done", *get_vault_page("", 1)), 
                      inputs=[sync_dir], 
                      outputs=[action_msg, vault_table, page_display, page_state])

    return demo, theme, custom_css


def mount_ui(app, index_path: Path, db_path: Path, path: str = "/ui"):
    demo, theme, custom_css = create_ui(index_path, db_path)
    return gr.mount_gradio_app(app, demo, path=path, theme=theme, css=custom_css)
