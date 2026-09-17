# TradeBay Frontend

Next.js App Router skeleton for the TradeBay B2B platform.

## Stack

- Next.js (App Router), React, TypeScript (strict)
- Tailwind CSS v4, ESLint
- Zod (auth validation), TanStack Query (server state)

## Getting started

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Set `NEXT_PUBLIC_API_URL` to your backend base URL (cookie session auth uses `credentials: include`).

## Scripts

| Script | Description |
| --- | --- |
| `npm run dev` | Dev server (Turbopack) |
| `npm run build` | Production build |
| `npm run start` | Run production server |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |

## Docker

Development image:

```bash
docker build --target development -t tradebay-frontend:dev .
docker run --rm -p 3000:3000 -v "${PWD}:/app" -v /app/node_modules tradebay-frontend:dev
```

Production image:

```bash
docker build --target production --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t tradebay-frontend:prod .
docker run --rm -p 3000:3000 tradebay-frontend:prod
```

## Structure

- `app/` — routes (landing, auth, dashboard domains, admin)
- `components/ui` — shared UI primitives
- `components/layout` — shell, sidebar, top bar
- `features/` — domain feature entry points
- `lib/api` — typed API client and module clients
- `providers/` — React Query + auth/business context

Protected routes call `/auth/me` on load; a `401` redirects to `/login`.
