"""Log viewer window with tabs, auto-scroll, search, and export capabilities."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

from launcher.process_manager import ProcessManager


class LogViewerWindow(tk.Toplevel):
    """Log Viewer window supporting live streaming, search filtering, and tabbed output."""

    def __init__(self, parent: tk.Tk, pm: ProcessManager):
        super().__init__(parent)
        self.pm = pm
        self.title("CashCow — Application Logs")
        self.geometry("900x600")
        self.minsize(700, 450)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self._text_widgets: Dict[str, tk.Text] = {}
        self._setup_ui()

        # Load historical logs
        self._populate_logs()

        # Register live listener
        self.pm.add_log_listener(self._handle_live_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self) -> None:
        # Top toolbar
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(fill=tk.X, side=tk.TOP)

        # Search bar
        ttk.Label(toolbar, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Auto-scroll checkbox
        auto_cb = ttk.Checkbutton(
            toolbar, text="Auto-scroll", variable=self.auto_scroll_var
        )
        auto_cb.pack(side=tk.LEFT, padx=(0, 15))

        # Clear & Export buttons
        btn_clear = ttk.Button(toolbar, text="Clear", command=self._clear_logs)
        btn_clear.pack(side=tk.RIGHT, padx=(5, 0))

        btn_export = ttk.Button(toolbar, text="Export Logs...", command=self._export_logs)
        btn_export.pack(side=tk.RIGHT, padx=(5, 0))

        # Tabs notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        for tab_id, tab_title in [
            ("all", "All Logs"),
            ("backend", "Backend"),
            ("frontend", "Frontend"),
            ("cloudflare", "Cloudflare Tunnel"),
            ("launcher", "Launcher / System"),
        ]:
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=tab_title)

            # Scrollable text widget
            text = tk.Text(
                tab_frame,
                wrap=tk.WORD,
                font=("Menlo", 11) if self.tk.call("tk", "windowingsystem") == "aqua" else ("Consolas", 10),
                bg="#1e1e1e",
                fg="#d4d4d4",
                insertbackground="#ffffff",
                selectbackground="#264f78",
                padx=8,
                pady=8,
            )
            scrollbar = ttk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Highlighting tags
            text.tag_config("ERROR", foreground="#f48771")
            text.tag_config("WARN", foreground="#cca700")
            text.tag_config("INFO", foreground="#75beff")
            text.tag_config("SEARCH", background="#515c6b", foreground="#ffffff")

            self._text_widgets[tab_id] = text

    def _populate_logs(self) -> None:
        """Populate initial history from ProcessManager queues."""
        for line in list(self.pm.launcher_logs):
            self._append_to_tab("launcher", line)
            self._append_to_tab("all", f"[Launcher] {line}")

        for line in list(self.pm.backend_logs):
            self._append_to_tab("backend", line)
            self._append_to_tab("all", f"[Backend] {line}")

        for line in list(self.pm.frontend_logs):
            self._append_to_tab("frontend", line)
            self._append_to_tab("all", f"[Frontend] {line}")

        for line in list(self.pm.cloudflare_logs):
            self._append_to_tab("cloudflare", line)
            self._append_to_tab("all", f"[Cloudflare] {line}")

    def _handle_live_log(self, source: str, line: str) -> None:
        """Thread-safe handler called whenever a process emits output."""
        def update():
            self._append_to_tab(source, line)
            self._append_to_tab("all", f"[{source.capitalize()}] {line}")

        self.after(0, update)

    def _append_to_tab(self, tab_id: str, line: str) -> None:
        text = self._text_widgets.get(tab_id)
        if not text:
            return

        text.configure(state=tk.NORMAL)
        
        # Tag style detection
        tag = None
        upper_line = line.upper()
        if "ERROR" in upper_line or "FAILED" in upper_line or "EXCEPTION" in upper_line:
            tag = "ERROR"
        elif "WARN" in upper_line:
            tag = "WARN"
        elif "INFO" in upper_line:
            tag = "INFO"

        if tag:
            text.insert(tk.END, line, tag)
        else:
            text.insert(tk.END, line)

        # Highlight search query if active
        query = self.search_var.get().strip()
        if query:
            self._highlight_search_in_text(text, query)

        text.configure(state=tk.DISABLED)

        if self.auto_scroll_var.get():
            text.see(tk.END)

    def _on_search_change(self, *args) -> None:
        query = self.search_var.get().strip()
        for text in self._text_widgets.values():
            text.configure(state=tk.NORMAL)
            text.tag_remove("SEARCH", "1.0", tk.END)
            if query:
                self._highlight_search_in_text(text, query)
            text.configure(state=tk.DISABLED)

    def _highlight_search_in_text(self, text: tk.Text, query: str) -> None:
        start_pos = "1.0"
        while True:
            start_pos = text.search(query, start_pos, stopindex=tk.END, nocase=True)
            if not start_pos:
                break
            end_pos = f"{start_pos}+{len(query)}c"
            text.tag_add("SEARCH", start_pos, end_pos)
            start_pos = end_pos

    def _clear_logs(self) -> None:
        current_tab_index = self.notebook.index(self.notebook.select())
        tab_ids = ["all", "backend", "frontend", "launcher"]
        active_tab = tab_ids[current_tab_index]

        text = self._text_widgets[active_tab]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.configure(state=tk.DISABLED)

    def _export_logs(self) -> None:
        current_tab_index = self.notebook.index(self.notebook.select())
        tab_ids = ["all", "backend", "frontend", "launcher"]
        active_tab = tab_ids[current_tab_index]

        text = self._text_widgets[active_tab]
        content = text.get("1.0", tk.END)

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title=f"Export {active_tab.capitalize()} Logs",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"cashcow_{active_tab}_logs.log",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Export Successful", f"Logs exported to {file_path}", parent=self)
            except Exception as exc:
                messagebox.showerror("Export Failed", f"Could not save log file: {exc}", parent=self)

    def _on_close(self) -> None:
        self.pm.remove_log_listener(self._handle_live_log)
        self.destroy()
