# Open Notebook — System Architecture

> Version 1.7.4 | February 2026

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Three-Tier Architecture](#three-tier-architecture)
3. [Technology Stack](#technology-stack)
4. [API Layer](#api-layer)
5. [Domain Models](#domain-models)
6. [LangGraph Workflows](#langgraph-workflows)
7. [AI Provisioning](#ai-provisioning)
8. [Database Schema](#database-schema)
9. [Async Command Queue](#async-command-queue)
10. [Frontend Architecture](#frontend-architecture)
11. [Authentication & Security](#authentication--security)
12. [Error Handling](#error-handling)
13. [Deployment Architecture](#deployment-architecture)
14. [Data Flow Diagrams](#data-flow-diagrams)

---

## System Overview

Open Notebook is an open-source, privacy-focused AI research assistant. It allows users to ingest multi-modal content (PDFs, audio, video, web pages), generate intelligent notes, search semantically, chat with AI models, and produce professional podcasts — all self-hosted with full control over AI provider selection.


![Architecture Diagram 0](arch-diagrams/diag-00-system-overview.png)


---

## Three-Tier Architecture


![Architecture Diagram 1](arch-diagrams/diag-01-three-tier-architecture.png)


### Service Ports

| Service | Port | Protocol | Role |
|---------|------|----------|------|
| Next.js Frontend | **3000** | HTTP | React UI |
| FastAPI Backend | **5055** | HTTP/REST | API gateway |
| SurrealDB | **8000** | WebSocket/RPC | Graph database |

---

## Technology Stack

### Frontend (`frontend/`)

| Category | Technology | Version |
|----------|-----------|---------|
| Framework | Next.js (React 19) | 16.1.5 |
| Language | TypeScript | 5.x |
| State — Server | TanStack Query | 5.83 |
| State — Client | Zustand | 5.0.6 |
| HTTP Client | Axios | 1.13.5 |
| UI Components | Radix UI + Shadcn/ui | — |
| Styling | Tailwind CSS | 4.x |
| i18n | i18next | — |
| Locales | en-US, pt-BR, zh-CN, zh-TW, ja-JP | 5 |
| Testing | Vitest + Testing Library | — |

### API Backend (`api/` + `open_notebook/`)

| Category | Technology | Version |
|----------|-----------|---------|
| Framework | FastAPI + Uvicorn | 0.104+ |
| Language | Python | 3.11+ |
| Database Driver | SurrealDB async | 1.0.4+ |
| AI Providers | Esperanto | 2.19.3+ |
| Workflows | LangGraph | 1.0.5+ |
| Checkpoint Store | SqliteSaver | — |
| Content Processing | content-core | 1.14.1+ |
| Prompt Templates | AI-Prompter + Jinja2 | 0.3+ |
| Podcast Generation | podcast-creator | 0.11.2+ |
| Job Queue | surreal-commands | 1.3.1+ |
| Logging | Loguru | 0.7.2+ |
| Validation | Pydantic | v2 |
| Encryption | Fernet (AES-128-CBC + HMAC) | — |
| Testing | Pytest + pytest-asyncio | — |

---

## API Layer

### Router → Service Map (21 Routers / 16 Services)


![Architecture Diagram 2](arch-diagrams/diag-02-api-layer.png)


### Key API Endpoints

| Router | Endpoint | Method | Purpose |
|--------|----------|--------|---------|
| auth | `/api/auth/password` | POST | Authenticate, return token |
| notebooks | `/api/notebooks` | GET/POST | List / create notebooks |
| notebooks | `/api/notebooks/{id}` | GET/PUT/DELETE | Single notebook CRUD |
| sources | `/api/sources` | POST | Upload file / URL / text |
| sources | `/api/sources/{id}` | GET/PUT/DELETE | Single source CRUD |
| notes | `/api/notes/{id}` | GET/PUT/DELETE | Note CRUD |
| chat | `/api/chat` | POST | Send notebook chat message |
| source_chat | `/api/sources/{id}/chat` | POST | Chat with single source |
| search | `/api/search/ask` | POST | Multi-stage AI search |
| podcasts | `/api/podcasts` | GET/POST | Podcast management |
| models | `/api/models` | GET/POST | AI model registry |
| credentials | `/api/credentials` | GET/POST | Provider credentials |
| commands | `/api/commands/{id}` | GET | Poll async job status |
| embeddings | `/api/embeddings/rebuild` | POST | Trigger re-embedding |

---

## Domain Models


![Architecture Diagram 3](arch-diagrams/diag-03-domain-models.png)


---

## LangGraph Workflows

Seven state machine workflows handle all AI-powered operations:


![Architecture Diagram 4](arch-diagrams/diag-04-langgraph-workflows.png)


### Model Selection Logic


![Architecture Diagram 5](arch-diagrams/diag-05-langgraph-workflows.png)


---

## AI Provisioning

### Supported Providers (Esperanto v2.19.3+)

| Provider | Chat | Embedding | TTS | Notes |
|----------|------|-----------|-----|-------|
| OpenAI | ✓ | ✓ | ✓ | GPT-4o, o3, etc. |
| Anthropic | ✓ | — | — | Claude 3.5/4.x |
| Google | ✓ | ✓ | — | Gemini Pro/Flash |
| Groq | ✓ | — | — | Fast inference |
| Ollama | ✓ | ✓ | — | Local models |
| Mistral | ✓ | ✓ | — | Mixtral |
| DeepSeek | ✓ | — | — | DeepSeek-R1 |
| xAI | ✓ | — | — | Grok |
| OpenRouter | ✓ | — | — | Meta-router |
| Azure OpenAI | ✓ | ✓ | — | Enterprise |
| Vertex AI | ✓ | ✓ | — | GCP |
| Voyage | — | ✓ | — | High-quality embeddings |
| ElevenLabs | — | — | ✓ | Podcast TTS |

### Credential Resolution Chain

```
Request → Model Record
            ↓
    Linked Credential?
    YES ──→ Credential.to_esperanto_config()
    NO  ──→ DB Credential Records (key_provider)
              ↓
        Environment Variables
              ↓
            Error
```

---

## Database Schema

### SurrealDB Migrations (13 versions)

| Migration | Purpose |
|-----------|---------|
| 1–3 | Core tables: notebooks, sources, notes |
| 4–6 | Relationships: source↔notebook, note↔source |
| 7 | Chat sessions + message history |
| 8–10 | Vector embeddings + semantic search indexes |
| 11 | Credential table + Fernet encryption |
| 12 | Model→Credential relationship |
| 13 | Additional model configuration fields |

### Vector Search Pattern


![Architecture Diagram 6](arch-diagrams/diag-06-database-schema.png)


---

## Async Command Queue

All heavy operations run as fire-and-forget jobs:


![Architecture Diagram 7](arch-diagrams/diag-07-async-command-queue.png)


---

## Frontend Architecture


![Architecture Diagram 8](arch-diagrams/diag-08-frontend-architecture.png)


### State Management Pattern

| Layer | Technology | Scope | Persistence |
|-------|-----------|-------|-------------|
| Server data (notebooks, sources, notes) | TanStack Query | App-wide | In-memory cache |
| Auth (token, isAuthenticated) | Zustand + persist | App-wide | localStorage |
| UI state (modals, forms) | React useState | Component | In-memory |

---

## Authentication & Security


![Architecture Diagram 9](arch-diagrams/diag-09-authentication-security.png)


> **Production Warning**: `PasswordAuthMiddleware` is dev-only. Replace with OAuth2/JWT for production deployments.

### Credential Encryption

- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key source**: `OPEN_NOTEBOOK_ENCRYPTION_KEY` environment variable
- **Scope**: All API keys stored in `Credential` records
- **At-rest**: Encrypted in SurrealDB; decrypted only on use

---

## Error Handling


![Architecture Diagram 10](arch-diagrams/diag-10-error-handling.png)


### Exception Hierarchy

```
OpenNotebookError (base)
├── NotFoundError              → HTTP 404
├── InvalidInputError          → HTTP 400
├── AuthenticationError        → HTTP 401
├── RateLimitError             → HTTP 429
├── ConfigurationError         → HTTP 422
├── NetworkError               → HTTP 502
└── ExternalServiceError       → HTTP 502
```

---

## Deployment Architecture

### Docker Compose Services


![Architecture Diagram 11](arch-diagrams/diag-11-deployment-architecture.png)


### Environment Variables (Key)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SURREAL_URL` | `ws://localhost:8000/rpc` | SurrealDB WebSocket |
| `SURREAL_USER` | `root` | DB authentication |
| `SURREAL_PASSWORD` | `root` | DB authentication |
| `SURREAL_NAMESPACE` | `open_notebook` | DB namespace |
| `SURREAL_DATABASE` | `open_notebook` | DB name |
| `OPEN_NOTEBOOK_ENCRYPTION_KEY` | — | **Required** — Credential encryption |
| `OPEN_NOTEBOOK_PASSWORD` | `open-notebook-change-me` | API auth password |
| `OPEN_NOTEBOOK_CHUNK_SIZE` | `1200` | Embedding chunk size (chars) |
| `OPEN_NOTEBOOK_CHUNK_OVERLAP` | `180` | Chunk overlap (chars) |

---

## Data Flow Diagrams

### Source Ingestion Flow


![Architecture Diagram 12](arch-diagrams/diag-12-data-flow-diagrams.png)


### Chat Message Flow


![Architecture Diagram 13](arch-diagrams/diag-13-data-flow-diagrams.png)


### Semantic Search Flow


![Architecture Diagram 14](arch-diagrams/diag-14-data-flow-diagrams.png)


---

## Key Architectural Patterns

| Pattern | Where Used | Why |
|---------|-----------|-----|
| **Async-first** | All DB, graph, and API ops | Throughput under concurrent requests |
| **Fire-and-forget jobs** | Embeddings, podcasts, transformations | Non-blocking API responses |
| **Repository pattern** | `open_notebook/database/repository.py` | Single source for DB operations |
| **Polymorphic model resolution** | `ObjectModel.get(id)` | Resolve subclass from ID prefix |
| **Singleton config** | `RecordModel` for settings | Application-wide defaults |
| **Credential fallback chain** | `key_provider.py` | DB creds → Env vars → Error |
| **Error classification** | `error_classifier.py` | User-friendly exception messages |
| **State persistence** | SqliteSaver (SQLite) | LangGraph message history |
| **Token budgeting** | `context_builder.py` | Respect LLM context windows |
| **Optimistic updates** | Frontend chat hooks | Perceived performance |
| **Broad cache invalidation** | TanStack Query | Simplicity over precision |

---

## File Structure Summary

```
open-notebook/
├── api/                          # FastAPI backend (42 Python files)
│   ├── main.py                   # App, CORS, auth, exception handlers
│   ├── routers/                  # 21 endpoint routers
│   └── *_service.py              # 16 business logic services
├── open_notebook/                # Core library (38 Python files)
│   ├── domain/                   # Data models + repository
│   ├── database/                 # SurrealDB driver + migrations (13)
│   ├── ai/                       # ModelManager + Esperanto provisioning
│   ├── graphs/                   # 7 LangGraph workflows
│   ├── podcasts/                 # Podcast domain models
│   └── utils/                    # Context building, chunking, embedding
├── commands/                     # 8 async job handlers
├── prompts/                      # Jinja2 prompt templates
├── frontend/                     # Next.js 16 (193 TS/TSX files)
│   └── src/
│       ├── app/                  # App Router pages (auth + dashboard)
│       ├── components/           # UI components
│       └── lib/                  # API client, hooks, stores, i18n
├── tests/                        # Pytest test suite
├── docs/                         # User & deployment documentation
└── docker-compose.yml            # Local development stack
```

---

*Generated: February 2026 | Open Notebook v1.7.4 | MIT License*
