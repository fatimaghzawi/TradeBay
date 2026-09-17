# TradeBay

TradeBay is a B2B wholesale marketplace platform for identity, catalog, procurement, finance, platform money, trust, and AI-assisted sourcing.

This repository is a production-ready modular monolith: domain boundaries, authentication and authorization, API surface, frontend shell, Docker, tests, and CI. Full commercial workflows are intentionally deferred.

## Architecture

```text
Frontend (Next.js App Router)
        ↓ typed API client
Backend (FastAPI modular monolith)
        ↓ services → repositories
MongoDB (Motor async)
```

Cross-domain reactions use an in-process domain event bus and a shared audit service. AI is isolated behind an `AIProvider` interface and never mutates authoritative business state.

## Technology stack

| Layer      | Stack                                                                              |
| ---------- | ---------------------------------------------------------------------------------- |
| Backend    | Python 3.12+, FastAPI, Pydantic v2, Motor, JWT + httpOnly cookies, Pytest, Ruff, MyPy |
| Frontend   | Next.js (App Router), TypeScript, Tailwind, Zod, TanStack Query, ESLint            |
| Operations | Docker, Compose, MongoDB 7, GitHub Actions                                         |

## Domains

| Domain            | Scope                                                      |
| ----------------- | ---------------------------------------------------------- |
| Identity          | Users, businesses, memberships, RBAC                       |
| Marketplace       | Products, pricing, inventory                               |
| Procurement       | RFQ → quotation → order → shipment                         |
| Communication     | Conversations and messages (structure only)                |
| Negotiation       | Offers, offer line items, and `parent_offer` chains        |
| AI Sourcing       | Sourcing requests and recommendations (no LLM yet)         |
| Business Planner  | Plans, items, and price estimates (no AI yet)              |
| Finance           | Accounts receivable, platform money, and trust             |

## Local development

```bash
cp .env.example .env
docker compose up mongodb -d
```

Compose MongoDB runs as a replica set. Host connections require `directConnection=true` (already set in `.env.example`).

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

**Full stack**

```bash
docker compose up --build
```

## Configuration

Copy `.env.example` to `.env`. Do not commit `.env` or real secrets.

Required variables: `SECRET_KEY`, `JWT_SECRET_KEY`, `MONGODB_URI`, `MONGODB_DATABASE`, `CORS_ORIGINS`.

## Docker

| Service    | Role                                      |
| ---------- | ----------------------------------------- |
| `mongodb`  | Replica set `rs0`; data in a named volume |
| `backend`  | FastAPI application                       |
| `frontend` | Next.js application                       |

All services include health checks. Transactions require the replica set. Containers communicate via Compose service names (`mongodb`, `backend`), not `localhost`.

## Commands

```bash
make backend          # FastAPI with reload
make frontend         # Next.js dev server
make test             # Pytest
make lint             # Ruff + ESLint
make typecheck        # MyPy + TypeScript
make docker-up        # Compose stack
make docker-down      # Stop Compose stack
```

```bash
cd backend && ruff check . && ruff format .
cd backend && mypy app
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Testing and quality

Backend tests live under `tests/unit`, `tests/integration`, and `tests/e2e`. Fixtures cover MongoDB, authenticated users, and business context.

Backend quality gates: Ruff and MyPy. Frontend quality gates: ESLint and TypeScript strict mode.

## Service endpoints

| Endpoint        | Purpose              |
| --------------- | -------------------- |
| `GET /health`   | Liveness             |
| `GET /ready`    | Readiness            |
| `/api/v1/...`   | Versioned public API |

Backend: `http://localhost:8000`  
Frontend: `http://localhost:3000`

## Repository layout

```text
tradebay/
├── backend/app/{core,db,api,shared,modules}
├── frontend/{app,components,features,lib}
├── infrastructure/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Security

- bcrypt password hashing; passwords are never stored in plaintext
- Short-lived access JWTs; refresh tokens in httpOnly Secure cookies, hashed at rest
- Session revocation and refresh-token rotation
- Permission-based authorization (`resource.action`); role names are not checked directly
- CORS allow-list (wildcard origins are not used in production)
- Request IDs and structured logs with secrets excluded
- Centralized error envelopes; stack traces are never returned to clients
