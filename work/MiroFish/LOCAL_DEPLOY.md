# MiroFish Local Deploy Notes

## What This Repo Actually Is

MiroFish is a `Node.js + Python` monorepo.

- Frontend: `Vite + Vue 3`
- Backend: `Flask`
- Default local URLs:
  - Frontend: `http://localhost:3000`
  - Backend: `http://localhost:5001`
- Required runtime secrets for real prediction workflows:
  - `LLM_API_KEY`
  - `ZEP_API_KEY`

This is not a `Java + MySQL + Redis` project. The upstream `README.md` and code confirm the real deployment path is `npm` plus Python dependencies.

## Repo Layout

- `frontend/`: Vue app
- `backend/`: Flask API and simulation engine
- `.env`: runtime config loaded by `backend/app/config.py`

## Local Setup On This Mac

### Prerequisites

- Node.js `20.20.1`
- Python `3.11.15`
- Project backend virtualenv at `backend/.venv`

### Install commands used

```bash
cd /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish
npm ci

cd /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/frontend
npm ci

python3 -m venv /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/backend/.venv
/Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/backend/.venv/bin/pip install -r /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/backend/requirements.txt
```

### Start commands used

```bash
cd /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/backend
./.venv/bin/python run.py
```

```bash
cd /Users/liming/Documents/codex-ai-gua-jia-01/work/MiroFish/frontend
npm run dev
```

## Smoke Test Checklist

- Backend health endpoint returns `{"status":"ok","service":"MiroFish Backend"}`
- Frontend home page loads on `http://localhost:3000`
- Browser can navigate the main views without a white screen
- Frontend can reach backend on `http://localhost:5001`

## Known Limits

- The backend only checks that `LLM_API_KEY` and `ZEP_API_KEY` are non-empty at startup.
- Real graph generation, simulation, and report flows still need valid credentials.
- Placeholder values in `.env` are only for local startup and basic smoke tests.
- Upstream root scripts expect `uv`; this machine can run the backend directly from `backend/.venv` even if `uv` is not installed.

## Troubleshooting

- If frontend install fails, rerun `npm ci` in both the repo root and `frontend/`.
- If backend start fails on missing packages, rerun the `pip install -r backend/requirements.txt` command inside `backend/.venv`.
- If backend starts but feature APIs fail, replace placeholder keys in `.env` with real LLM and Zep credentials.
- If port `3000` or `5001` is busy, stop the conflicting process or override the port before startup.
