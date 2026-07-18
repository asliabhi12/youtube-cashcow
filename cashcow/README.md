# CashCow

Local-first video automation. Runs entirely on your machine — no cloud, no authentication, no Docker.

The app is two processes:

- **backend** — FastAPI server on `http://localhost:8000`
- **frontend** — Next.js dashboard on `http://localhost:3000`

## Structure

```
cashcow/
├── backend/      FastAPI server (Python 3.12)
├── frontend/     Next.js 15 dashboard
├── downloads/    downloaded source media (runtime)
├── output/       processed video output (runtime)
├── presets/      saved workflow presets
├── workflows/    workflow definitions
├── package.json  monorepo dev scripts
└── README.md
```

## Prerequisites

- Node.js 20+
- Python 3.12+

## Install

```bash
# from cashcow/
npm install                      # root dev tooling (concurrently)

cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..

cd frontend
npm install
cd ..
```

## Run

Start both processes together from the repo root:

```bash
npm run dev
```

- Backend → http://localhost:8000 (health check at `/health`)
- Frontend → http://localhost:3000

Or run them individually:

```bash
npm run dev:backend
npm run dev:frontend
```

The dashboard header shows **🟢 Server Running** when it can reach the backend, **🔴 Server Offline** otherwise.
