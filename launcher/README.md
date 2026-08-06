# CashCow Desktop Launcher

A lightweight, native macOS desktop launcher for **YouTube CashCow**. Built with Python + Tkinter to eliminate manual terminal commands and launch the entire stack with one click.

---

## 🌟 Key Features

* **One-Click Orchestration**: Starts the Uvicorn Backend (`0.0.0.0:8000`) and Next.js Frontend (`localhost:3000`) concurrently using `subprocess.Popen`.
* **Sequential Health Gating**: Waits for `GET /health` (Backend) and `localhost:3000` (Frontend) before automatically opening the browser.
* **Continuous Health Monitoring**: Real-time indicators for:
  - 🟢 / 🔴 **Backend API**
  - 🟢 / 🔴 **Frontend Web Studio**
  - 🟢 / 🔴 **Cloudflare Tunnel** (Auto-detected)
* **Real-time Log Viewer Window**: Tabbed view (All Logs, Backend, Frontend, Launcher) with auto-scroll, regex search filtering, and file export.
* **Clean Termination**: Gracefully stops processes and child worker process groups (`os.setsid` / process group signals) without leaving orphaned ports or background processes.
* **Developer Tools & Future Ready**: Direct buttons for OpenAPI Docs (`/docs`), Settings configuration dialog, and extensibility hooks for future tools.

---

## 📁 Architecture & File Structure

```
launcher/
├── __init__.py           # Package marker
├── __main__.py           # CLI entry point (python -m launcher)
├── main.py               # Application launcher entry point
├── config.py             # Configuration & path management
├── process_manager.py    # Async process spawner & log streamer using Popen
├── health_monitor.py     # Background thread polling /health & localhost:3000
├── log_viewer.py         # Multi-tab searchable Tkinter log window
├── launcher.py           # Main Tkinter GUI application
├── requirements.txt      # Optional PyInstaller dependencies
├── build_mac.sh          # Packaging script for macOS .app bundle
└── README.md             # Documentation
```

---

## 🚀 Quick Start

### Option 1: Run Directly with Python (Recommended during Dev)

Run from the project root:

```bash
# Using python directly
python3 launcher/main.py

# Or via python module syntax
python3 -m launcher
```

### Option 2: Build macOS Standalone Application (.app)

To generate a native macOS Application bundle (`CashCow Launcher.app`):

```bash
./launcher/build_mac.sh
```

This creates:
- `dist/CashCow Launcher.app`

To place a shortcut on your Desktop:

```bash
ln -s "/Users/abhishek/Documents/youtube-cashcow/dist/CashCow Launcher.app" ~/Desktop/"CashCow Launcher"
```

---

## ⚙️ Configuration

By default, the launcher operates on:
* **Project Root**: `/Users/abhishek/Documents/youtube-cashcow`
* **Virtualenv**: `/Users/abhishek/Documents/youtube-cashcow/.venv`
* **Backend CWD**: `cashcow/backend`
* **Frontend CWD**: `cashcow/frontend`
* **Frontend Command**: `npm start` (or `npm run dev`)

Settings are stored in `~/.cashcow_launcher.json` and can be edited anytime via the **⚙️ Settings** button in the launcher UI.

---

## 🛠 Extension Hooks (Future Ready)

To add new buttons or actions to `launcher/launcher.py`, add a button to `_create_ui()`:

```python
btn_custom = ttk.Button(
    container, text="🔧 Custom Action", command=self.on_custom_action
)
btn_custom.pack(fill=tk.X, pady=2)
```

And define the handler:

```python
def on_custom_action(self):
    webbrowser.open("http://localhost:8000/custom")
```
