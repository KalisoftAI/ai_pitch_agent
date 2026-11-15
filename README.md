# Kalika Outreach

Sales / Outreach workspace: FastAPI backend + React (Vite) frontend, deployed on Cloud Run.

All documentation has been consolidated into **[OUTREACH_MASTER.md](OUTREACH_MASTER.md)**:
architecture, local setup, environment variables, API map, the end-to-end outreach workflow,
testing commands, deployment notes and known gaps.

Quick start:

```powershell
C:\Python314\python.exe -m uvicorn sales_fastapi.main:app --reload --port 8000
npm --prefix frontend install
npm --prefix frontend run dev
```

Build for production (served by FastAPI from `/static/assets`):

```powershell
npm --prefix frontend run build
```
