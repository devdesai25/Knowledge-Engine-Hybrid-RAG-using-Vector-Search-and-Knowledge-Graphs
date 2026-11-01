# Knowledge Engine — Frontend

Modern, multi-tenant document Q&A frontend interface powered by Hybrid RAG (Dense Vector Search + BM25 + Knowledge Graphs).

Built with React 18, Vite, TypeScript, Tailwind CSS, TanStack Query, Zustand, and React Router.

---

## Getting Started

### 1. Prerequisites
- Node.js (v18+ recommended, v22 tested)
- npm (v10+)

### 2. Installation
From the repository root or inside `/frontend`:

```bash
cd frontend
npm install
```

### 3. Environment Variables
Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Base URL of the FastAPI backend | `http://localhost:8000` |
| `VITE_USE_MOCKS` | `true` to run against in-memory mock API layer; `false` for live backend | `true` |

---

## Development Server

Start the development server:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Swapping Between Mock Mode & Real API

The application has an API abstraction layer (`src/api/index.ts`) that strictly mirrors the planned FastAPI backend endpoints.

### Using Mock Mode (`VITE_USE_MOCKS=true`)
- When enabled, all API calls route to `src/api/mocks/mockApi.ts` with simulated network latency, SSE streaming, tenant isolation, and role permissions.
- A floating **"Switch User"** pill is pinned to the bottom-right of the screen.
- You can instantly toggle between:
  1. **Acme Corp Admin** (`admin@acme.com` — Full upload/delete/admin privileges)
  2. **Acme Corp Member** (`member@acme.com` — Read-only document access, chat Q&A)
  3. **Globex Corp Member** (`member@globex.com` — Tenant B isolated data and responses)
- Demonstrates tenant isolation: Acme Corp and Globex Corporation have different document catalogs and distinct AI chat answers and citation fragments.

### Switching to Live FastAPI Backend (`VITE_USE_MOCKS=false`)
1. Set `VITE_USE_MOCKS=false` in `frontend/.env`.
2. Ensure the FastAPI backend is running:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
3. Restart Vite (`npm run dev`). Requests will be sent directly to the FastAPI server with JWT Bearer authentication headers.

---

## Architecture & Folder Structure

```
frontend/
├── src/
│   ├── api/             # Typed API layer, client fetcher, SSE handler & mock system
│   │   ├── mocks/       # Seed data, tenant-isolated store, simulated SSE streaming
│   │   ├── admin.ts     # Admin user management & invite endpoints
│   │   ├── auth.ts      # Authentication & session endpoints
│   │   ├── chat.ts      # SSE streaming & plain string chat endpoints
│   │   ├── client.ts    # Fetch wrapper with Bearer token & 401/403 handlers
│   │   ├── documents.ts # Document listing, multi-file upload, deletion
│   │   └── index.ts     # Unified API export toggled by VITE_USE_MOCKS
│   ├── components/      # Reusable UI components, layout shell, dev switcher
│   │   ├── dev/         # Floating user & tenant switcher control
│   │   ├── layout/      # Sidebar, Header, ProtectedRoute, AdminRoute, AppLayout
│   │   └── ui/          # Buttons, inputs, badges, skeletons
│   ├── hooks/           # Zustand auth store & theme hooks
│   ├── lib/             # Utility helpers, storage wrapper, theme manager
│   ├── pages/           # Screen routes (Login, Chat, Documents, Admin)
│   └── types/           # Shared TypeScript interfaces (no `any`)
```

---

## Production Build

To type-check and generate production build assets:

```bash
npm run build
```
