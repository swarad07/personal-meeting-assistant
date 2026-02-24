# Personal Meeting Assistant

A multi-AI-agent system that acts as your personal meeting intelligence hub. It syncs meetings from Granola, integrates with Google Calendar, extracts entities and relationships, builds a knowledge graph, generates pre-meeting briefings, and provides cross-meeting search.

## Features

- **Meeting Sync** — Automatically syncs meetings and transcripts from Granola (cloud MCP or local cache)
- **Google Calendar** — Pulls upcoming meetings and generates preparation briefs
- **Entity Extraction** — AI-powered extraction of people, organizations, topics, and projects
- **Knowledge Graph** — Neo4j-backed relationship graph connecting entities across meetings
- **Pre-Meeting Briefings** — LLM-generated briefings with attendee context, open action items, and discussion points
- **Hybrid Search** — Full-text (PostgreSQL tsvector), semantic (pgvector), and graph (Neo4j) search with reciprocal rank fusion
- **Action Item Tracking** — Automatic extraction and tracking of todos across meetings
- **Profile Building** — Learns about you and your contacts over time
- **Agent Observability** — Monitor all AI agent runs, errors, and token usage

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, React Flow |
| Backend | Python 3.12, FastAPI, LangGraph, SQLAlchemy 2.0 |
| LLM | OpenAI GPT-4o (extraction, briefings), text-embedding-3-small (vectors) |
| Databases | PostgreSQL 16 + pgvector, Neo4j 5, Redis 7 |
| MCP | Granola (cloud + local cache fallback), Google Calendar (direct OAuth) |
| Deployment | Docker Compose |

---

## Prerequisites

Before you start, make sure you have the following installed:

| Requirement | Version | Check |
|-------------|---------|-------|
| Docker & Docker Compose | Latest | `docker --version` |
| Python | 3.12+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |

You will also need:

- **OpenAI API key** — required. Get one at https://platform.openai.com/api-keys
- **Granola Business account** — optional but recommended for cloud meeting sync. Free users can still use the local cache fallback (macOS only).
- **Google Cloud project** — optional, needed only if you want to pull upcoming meetings from Google Calendar.

---

## Setup Guide

Follow these steps in order. The whole process takes about 10 minutes.

### Step 1: Clone and Configure Environment

```bash
git clone <repo-url> personal-meeting-assistant
cd personal-meeting-assistant
cp .env.example .env
```

Open `.env` in your editor and configure the following:

**Required — OpenAI:**

```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

**Required — Encryption Key:**

The app encrypts sensitive data (API keys, OAuth tokens) at rest. Generate a key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output into your `.env`:

```bash
ENCRYPTION_KEY=your-generated-key-here
```

**Required for local dev — Database URL:**

The default `DATABASE_URL` in `.env.example` uses Docker service names (`postgres`) which only works inside Docker networking. For local development, change it to `localhost`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meeting_assistant
```

Similarly for Neo4j and Redis:

```bash
NEO4J_URI=bolt://localhost:7687
REDIS_URL=redis://localhost:6379/0
```

> If you run everything via `docker compose up -d` (Full Docker mode), keep the service names as-is.

**Optional — Google Calendar:**

If you want Google Calendar integration, add these (see [Google Calendar Setup](#google-calendar-setup) below for how to get them):

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Optional — Granola cache path (non-macOS):**

The Granola local cache fallback defaults to the macOS path. If you are on Linux or Windows, override it:

```bash
# Linux (if Granola stores data here):
GRANOLA_CACHE_PATH=~/.config/Granola/cache-v3.json

# Windows (use forward slashes):
GRANOLA_CACHE_PATH=C:/Users/YourName/AppData/Roaming/Granola/cache-v3.json
```

Leave all other values at their defaults unless you have a reason to change them.

### Step 2: Start Databases

```bash
docker compose up -d postgres neo4j redis
```

Wait a few seconds for them to initialize. You can verify they are healthy:

```bash
docker compose ps
```

All three services should show `healthy` or `running`.

### Step 3: Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
pip install -e .
alembic upgrade head           # Create database tables
```

Start the backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see output like `Uvicorn running on http://0.0.0.0:8000`. Leave this terminal running.

### Step 4: Frontend Setup

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

You should see `Local: http://localhost:3000`. Leave this terminal running.

### Step 5: First-Run Configuration

Open **http://localhost:3000** in your browser. You will land on the dashboard.

1. **Go to Settings** (gear icon in the left sidebar, or navigate to `/settings`).
2. **Verify OpenAI API Key** — Under the "General" tab, confirm your OpenAI API key is loaded (it shows the last 4 characters masked). You can also enter or change it directly here; changes take effect immediately without restart.
3. **Connect Granola** (if you have a Granola Business account):
   - Switch to the "Connections" tab.
   - Click **Connect** next to "Granola MCP".
   - You will be redirected to Granola's authorization page. Log in and authorize the app.
   - After authorization, you are redirected back. The status should show "connected".
   - Your name and email are automatically detected from your Granola account.
4. **Connect Google Calendar** (if you set up credentials in Step 1):
   - On the same "Connections" tab, click **Connect** next to "Google Calendar".
   - Authorize with your Google account.
   - After authorization, upcoming events will start appearing on the Meetings page.
5. **Trigger a sync** — Go to the Meetings page and click **Sync Meetings** or go to the Agents page and run the "meeting_sync" agent. The status bar at the bottom shows sync progress.

---

## Google Calendar Setup

To connect Google Calendar, you need OAuth 2.0 credentials from Google Cloud Console. This is a one-time setup.

### 1. Create a Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click the project dropdown at the top and select **New Project**.
3. Name it something like "Meeting Assistant" and click **Create**.
4. Make sure the new project is selected in the dropdown.

### 2. Enable the Google Calendar API

1. Go to **APIs & Services > Library** (or search "Calendar API" in the top search bar).
2. Find **Google Calendar API** and click **Enable**.

### 3. Configure the OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** user type (unless you have a Google Workspace org and want Internal).
3. Fill in the required fields:
   - App name: "Meeting Assistant"
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**.
5. On the Scopes page, click **Add or Remove Scopes**, search for `calendar.readonly`, check it, and click **Update**. Then **Save and Continue**.
6. On the Test Users page, click **Add Users** and add your own Google email. Click **Save and Continue**.
7. Click **Back to Dashboard**.

### 4. Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Application type: **Web application**.
4. Name: "Meeting Assistant".
5. Under **Authorized redirect URIs**, click **Add URI** and enter:
   ```
   http://localhost:3000/settings/connections/callback
   ```
6. Click **Create**.
7. Copy the **Client ID** and **Client Secret**.

### 5. Add Credentials to Your Environment

Add the values to your `.env` file:

```bash
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxx
```

Restart the backend after adding these values, then connect via the Settings page in the UI.

---

## Granola Integration

The app supports two modes for syncing meetings from Granola. Cloud MCP is preferred; local cache is the automatic fallback.

### Cloud MCP (recommended)

- Requires a **Granola Business** plan.
- No credentials to configure in `.env` — authentication is handled via OAuth in the browser.
- Go to Settings > Connections > click **Connect** next to Granola MCP.
- Meetings are labeled "Cloud" in the UI.

### Local Cache (fallback)

- Works with any Granola plan (including free).
- macOS only by default — reads from `~/Library/Application Support/Granola/cache-v3.json`.
- If you are not on macOS, set `GRANOLA_CACHE_PATH` in your `.env` to the correct path.
- The app automatically falls back to the local cache if the cloud MCP connection is unavailable.
- Meetings synced this way are labeled "Cache" in the UI.

> If you do not use Granola at all, the app still works — you just won't have meeting data until you connect another source or add meetings manually.

---

## Starting and Stopping

### Day-to-Day Usage (local dev)

**Start:**

```bash
# Terminal 1: databases
docker compose up -d postgres neo4j redis

# Terminal 2: backend
cd backend && source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: frontend
cd frontend && npm run dev
```

**Stop:**

- Press `Ctrl+C` in the backend and frontend terminals.
- Run `docker compose down` to stop databases (data is preserved in Docker volumes).

**Wipe all data and start fresh:**

```bash
docker compose down -v
```

### Full Docker Mode (alternative)

If you prefer running everything in Docker (no local Python/Node needed after build):

```bash
docker compose up -d          # Start all services
docker compose down           # Stop (preserves data)
docker compose down -v        # Stop and wipe data
```

> In Full Docker mode, keep `DATABASE_URL`, `NEO4J_URI`, and `REDIS_URL` using Docker service names (`postgres`, `neo4j`, `redis`) instead of `localhost`.

Your data is stored in Docker volumes (`postgres-data`, `neo4j-data`, `redis-data`) and persists across restarts.

---

## Troubleshooting

### Database connection refused

```
sqlalchemy.exc.OperationalError: could not connect to server: Connection refused
```

Make sure Docker containers are running: `docker compose ps`. If not, run `docker compose up -d postgres neo4j redis`. Also verify your `DATABASE_URL` uses `localhost` (local dev) or `postgres` (Full Docker).

### Granola MCP returns 403

```
403 ERROR — The request could not be satisfied
```

This means you are not on a Granola Business plan, or your OAuth session expired. The app will automatically fall back to the local cache. To use cloud sync, upgrade to Granola Business and reconnect via Settings.

### Google Calendar redirect mismatch

```
Error 400: redirect_uri_mismatch
```

The redirect URI in your Google Cloud Console credentials must exactly match:
```
http://localhost:3000/settings/connections/callback
```

Go to Google Cloud Console > APIs & Services > Credentials, edit your OAuth client, and verify the URI.

### Missing OpenAI API key

If you see errors about missing API key or 401 from OpenAI, check:
1. Your `.env` file has `OPENAI_API_KEY` set, OR
2. You entered the key in Settings > General in the UI.

The UI setting takes priority over the `.env` value. Changes take effect immediately.

### Stale sync in status bar

If the status bar shows a sync that has been running for hours, click the **X** button next to it to cancel the stuck run, then retry manually from the Agents page.

### Neo4j authentication failed

If Neo4j rejects the default password, it may have been initialized with a different one. Either:
- Update `NEO4J_PASSWORD` in your `.env` to match, or
- Wipe and recreate: `docker compose down -v && docker compose up -d postgres neo4j redis`

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture reference, including:

- Agent pipelines (sync, briefing, on-demand)
- Data models and database schemas
- Extensibility patterns (Agent Registry, MCP Provider Registry)
- Entity resolution strategy
- Search architecture
- OAuth flows
- Cost control and rate limiting

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/          # AI agents (sync, briefing pipelines)
│   │   ├── api/routes/      # FastAPI route handlers
│   │   ├── db/              # Database connections (PostgreSQL, Neo4j)
│   │   ├── mcp/             # MCP provider integrations
│   │   ├── models/          # SQLAlchemy ORM models
│   │   └── services/        # Business logic services
│   ├── alembic/             # Database migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # React components
│   │   └── lib/             # API client, types, utilities
│   └── Dockerfile
├── scripts/                 # Seed data and utility scripts
├── docs/                    # Architecture documentation
├── docker-compose.yml       # Production compose
├── docker-compose.dev.yml   # Development override
└── .env.example             # Environment template
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/status/` | System status (providers, active runs, scheduler) |
| POST | `/api/status/cancel-run/{id}` | Cancel a stuck agent run |
| GET | `/api/meetings/` | List meetings (paginated) |
| GET | `/api/meetings/{id}` | Meeting detail with transcript |
| POST | `/api/meetings/sync` | Trigger meeting sync |
| POST | `/api/meetings/sync/full` | Full pipeline (sync + entities + profiles + relationships) |
| POST | `/api/meetings/{id}/resync` | Re-fetch notes for a single meeting |
| POST | `/api/meetings/{id}/generate-summary` | Generate LLM summary for a meeting |
| POST | `/api/meetings/{id}/generate-brief` | Generate next-call preparation brief |
| POST | `/api/search` | Hybrid search |
| GET | `/api/relationships` | Knowledge graph data |
| GET | `/api/profiles/` | List profiles (paginated) |
| GET | `/api/profiles/me` | Own profile |
| GET | `/api/profiles/{id}` | Contact profile detail |
| PATCH | `/api/profiles/{id}` | Update profile |
| POST | `/api/profiles/{id}/generate-bio` | Generate LLM bio for a contact |
| GET | `/api/calendar/events` | Upcoming calendar events |
| GET | `/api/briefings/` | List briefings |
| GET | `/api/briefings/{id}` | Briefing detail |
| POST | `/api/briefings/generate` | Trigger briefing generation |
| GET | `/api/action-items/` | List action items (filterable) |
| PATCH | `/api/action-items/{id}` | Update action item status |
| GET | `/api/agents/` | List AI agents and run counts |
| GET | `/api/agents/{name}` | Agent detail with run history |
| POST | `/api/agents/{name}/trigger` | Trigger an agent run from the UI |
| GET | `/api/connections/` | List MCP connections |
