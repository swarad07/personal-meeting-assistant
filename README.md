# Personal Meeting Assistant

A multi-AI-agent system that acts as your personal meeting intelligence hub. It syncs meetings from Granola, integrates with Google Calendar, extracts entities and relationships, builds a knowledge graph, generates pre-meeting briefings, and provides cross-meeting search.

## Features

- **Meeting Sync** — Automatically syncs meetings and transcripts from Granola via MCP
- **Entity Extraction** — AI-powered extraction of people, organizations, topics, and projects
- **Knowledge Graph** — Neo4j-backed relationship graph connecting entities across meetings
- **Pre-Meeting Briefings** — GPT-4o generated briefings with attendee context, open action items, and discussion points
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
| MCP | Granola (cloud), Google Calendar (Docker sidecar) |
| Deployment | Docker Compose |

## Quick Start

```bash
cp .env.example .env          # configure OPENAI_API_KEY
docker compose up -d           # start everything
open http://localhost:3000     # open the app
```

Services started:
- **frontend** — http://localhost:3000
- **backend** — http://localhost:8000
- **postgres** — PostgreSQL 16 + pgvector (port 5432)
- **neo4j** — http://localhost:7474 (browser, bolt on 7687)
- **redis** — Redis 7 (port 6379)
- **gcal-mcp** — Google Calendar MCP server (port 8100)

## Starting and Stopping

### Option A: Full Docker (all services in containers)

```bash
# Start everything
docker compose up -d

# Stop everything (preserves data)
docker compose down

# Stop and delete all data
docker compose down -v
```

### Option B: Local dev (databases in Docker, app runs locally)

This is the recommended setup for development — you get hot reload for both frontend and backend.

**Start databases:**

```bash
docker compose up -d postgres neo4j redis
```

**Start backend** (in one terminal):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Start frontend** (in another terminal):

```bash
cd frontend
npm run dev
```

**Stop the app:**

- Press `Ctrl+C` in each terminal (backend and frontend)

**Stop databases:**

```bash
docker compose down
```

Your data is stored in Docker volumes (`postgres-data`, `neo4j-data`, `redis-data`) and persists across restarts. Use `docker compose down -v` only if you want to wipe everything.

**Restart everything after a break:**

```bash
# 1. Start databases
docker compose up -d postgres neo4j redis

# 2. Run any pending migrations
cd backend && source .venv/bin/activate && alembic upgrade head

# 3. Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. In another terminal, start frontend
cd frontend && npm run dev
```

### Development with Docker (hot reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This mounts source directories for hot reload while using Docker for databases.

## First-Time Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ with a virtual environment
- Node.js 20+
- OpenAI API key
- (Optional) Google Calendar OAuth credentials

### Initial setup

```bash
# Clone and configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY at minimum

# Start databases
docker compose up -d postgres neo4j redis

# Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
alembic upgrade head

# Frontend setup
cd ../frontend
npm install
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture reference, including:

- Agent pipelines (sync, briefing, on-demand)
- Data models and database schemas
- Extensibility patterns (Agent Registry, MCP Provider Registry)
- Entity resolution strategy
- Search architecture
- OAuth flow for Docker
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
