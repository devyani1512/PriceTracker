# Price Tracker — Frontend

A minimal, Notion-inspired front end for the Price Tracker API. Built with
React 18, TypeScript, Vite, Tailwind CSS v3, react-router-dom v6, and Recharts.

## Requirements

- Node.js 18+
- [pnpm](https://pnpm.io/) (`corepack enable` if you don't have it)

## Setup

```bash
cd frontend
pnpm install
cp .env.example .env   # optional, adjust the API URL if needed
```

The API base URL is read from `VITE_API_URL` at build time and defaults to
`http://localhost:8080` when unset. See `.env.example`.

## Development

```bash
pnpm dev        # http://localhost:5173
```

Make sure the backend is running and that CORS allows the dev origin.

## Build

```bash
pnpm typecheck  # tsc --noEmit
pnpm build      # type-check + production build to dist/
pnpm preview    # serve the production build locally
```

## Deploy to Vercel

1. Import the repository in Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Vite** (build command `pnpm build`, output `dist`).
4. Add an environment variable `VITE_API_URL` pointing at your deployed backend.
5. Deploy.

`vercel.json` rewrites all routes to `/index.html` so client-side routing works
on deep links and refresh.

## Project layout

```
src/
  api/            typed API client (client.ts, types.ts, index.ts)
  components/     hand-rolled UI primitives and feature components
  context/        AuthProvider (token in localStorage["pt_token"])
  hooks/          useAsync, useDebounced
  lib/            formatting and small helpers
  pages/          route pages
  App.tsx         routes
  main.tsx        entry point
```
