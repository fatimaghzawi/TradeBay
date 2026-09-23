# TradeBay

B2B wholesale marketplace — FastAPI backend, Next.js frontend, MongoDB.

## Stack

| Layer | Tech |
| --- | --- |
| Backend | FastAPI, Motor/MongoDB, JWT auth |
| Frontend | Next.js (App Router), TypeScript, Tailwind |
| Data | MongoDB 7 (replica set) |
| Ops | Docker Compose, GitHub Actions |

## Specs

- [docs/BRD.pdf](docs/BRD.pdf) — Business Requirements
- [docs/ERD.html](docs/ERD.html) — Entity Relationship Diagram

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000  
- Backend: http://localhost:8000  
- Health: `GET /health`, `GET /ready`

### Local (without Docker)

```bash
# MongoDB must be running (replica set)

cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Configuration

Copy `.env.example` to `.env`. Required: `SECRET_KEY`, `JWT_SECRET_KEY`, `MONGODB_URI`, `MONGODB_DATABASE`, `CORS_ORIGINS`.

Do not commit `.env` or real secrets.

## Layout

```text
tradebay/
├── backend/          # FastAPI API
├── frontend/         # Next.js app
├── docs/             # BRD + ERD
├── docker-compose.yml
└── .env.example
```

## License

Proprietary.
