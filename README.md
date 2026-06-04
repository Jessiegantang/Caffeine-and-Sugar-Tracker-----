# DrinkMind

DrinkMind is a caffeine and sugar tracking app with a FastAPI backend, SQLite drink data, ChromaDB retrieval, and a Vite frontend.

## Setup

1. Install frontend dependencies:

```bash
npm install
```

2. Install backend dependencies:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure backend environment:

```bash
copy backend\.env.example backend\.env
```

Then edit `backend\.env` and set your API key. Do not commit `.env`.

## Initialize Knowledge Base

Run this once after installing backend dependencies:

```bash
cd backend
python init_rag.py
```

This initializes the SQLite tables and synchronizes available drink knowledge into ChromaDB.

## Start Backend

```bash
cd backend
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

## Start Frontend

In another terminal:

```bash
npm run dev
```

The Vite app prints the local URL, usually `http://localhost:5173`.

## One-Command Demo Start

On Windows PowerShell:

```powershell
.\scripts\start_demo.ps1
```

This starts the FastAPI backend in the background and then starts the Vite frontend in the current terminal.

## Build Frontend

```bash
npm run build
```

Generated files in `dist/` are ignored by git.

## Run Tests

Backend tests use Python's built-in unittest runner:

```bash
cd backend
venv\Scripts\python.exe -m unittest discover -s tests
```

The tests cover intake parsing, local nutrition fallback, SQL exact-match explainability, agent routing, trace recording, memory preferences, health plans, and API smoke checks.

## Demo Script

See `docs/demo_script.md` for the interview demo flow:

- Natural language drink logging
- Asking whether coffee still fits today's budget
- Creating a 7-day health plan and showing weekly progress

## Legacy Tools

Historical repair, dump, search, and debug scripts are kept in `tools/legacy/` so the project root stays focused on the app entry points.
