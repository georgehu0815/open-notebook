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

```mermaid
graph TB
    subgraph USER["User / Browser"]
        B[Browser]
    end

    subgraph FRONTEND["Frontend — Next.js 16 @ :3000"]
        NX[App Router]
        ZS[Zustand Store]
        TQ[TanStack Query]
        AX[Axios Client]
    end

    subgraph API["API — FastAPI @ :5055"]
        MW[Auth Middleware]
        RT[21 Routers]
        SV[16 Services]
        LG[LangGraph Workflows]
        CQ[Command Queue]
    end

    subgraph DB["Database — SurrealDB @ :8000"]
        TB[Core Tables]
        VE[Vector Embeddings]
        MG[13 Migrations]
    end

    subgraph AI["AI Providers — Esperanto"]
        OA[OpenAI]
        AN[Anthropic]
        GO[Google]
        GQ[Groq]
        OL[Ollama]
        MS[Mistral]
        DS[DeepSeek]
        XA[xAI]
    end

    subgraph STORAGE["Local Storage"]
        SQ[SQLite — LangGraph Checkpoints]
        FS[File System — Uploads]
    end

    B --> NX
    NX --> ZS
    NX --> TQ
    TQ --> AX
    AX -->|HTTP REST| MW
    MW --> RT
    RT --> SV
    SV --> LG
    SV --> CQ
    SV --> DB
    LG --> AI
    LG --> SQ
    CQ --> DB
    CQ --> AI
    DB --> VE
```

---

## Three-Tier Architecture

```mermaid
graph LR
    subgraph T1["Tier 1 — Presentation"]
        direction TB
        A1[Pages / App Router]
        A2[Shadcn/ui Components]
        A3[Hooks & Stores]
        A1 --> A2 --> A3
    end

    subgraph T2["Tier 2 — Application"]
        direction TB
        B1[FastAPI Routers]
        B2[Service Layer]
        B3[LangGraph + Commands]
        B1 --> B2 --> B3
    end

    subgraph T3["Tier 3 — Data"]
        direction TB
        C1[SurrealDB Records]
        C2[Vector Embeddings]
        C3[Async Migrations]
        C1 --- C2
        C3 --> C1
    end

    T1 -->|"HTTP REST / Axios"| T2
    T2 -->|"SurrealQL / WebSocket"| T3
```

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

```mermaid
graph LR
    subgraph Routers["API Routers (/api/...)"]
        R1[notebooks]
        R2[sources]
        R3[notes]
        R4[chat]
        R5[source_chat]
        R6[search]
        R7[podcasts]
        R8[models]
        R9[credentials]
        R10[transformations]
        R11[insights]
        R12[commands]
        R13[embedding]
        R14[episode_profiles]
        R15[speaker_profiles]
        R16[settings]
        R17[auth]
        R18[config]
        R19[context]
    end

    subgraph Services["Service Layer"]
        S1[notebook_service]
        S2[sources_service]
        S3[notes_service]
        S4[chat_service]
        S5[search_service]
        S6[podcast_service]
        S7[models_service]
        S8[credentials_service]
        S9[transformations_service]
        S10[insights_service]
        S11[command_service]
        S12[embedding_service]
        S13[settings_service]
        S14[context_service]
    end

    R1 --> S1
    R2 --> S2
    R3 --> S3
    R4 --> S4
    R5 --> S4
    R6 --> S5
    R7 --> S6
    R8 --> S7
    R9 --> S8
    R10 --> S9
    R11 --> S10
    R12 --> S11
    R13 --> S12
    R14 --> S6
    R15 --> S6
    R16 --> S13
    R19 --> S14
```

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

```mermaid
erDiagram
    NOTEBOOK {
        string id PK
        string title
        string description
        datetime created
        datetime updated
    }

    SOURCE {
        string id PK
        string title
        string content_type
        text full_text
        json metadata
        datetime created
        datetime updated
    }

    NOTE {
        string id PK
        string title
        text content
        datetime created
        datetime updated
    }

    SOURCE_INSIGHT {
        string id PK
        string source_id FK
        text content
        string insight_type
        datetime created
    }

    SOURCE_EMBEDDING {
        string id PK
        string source_id FK
        vector embedding_vector
        int chunk_index
    }

    CHAT_SESSION {
        string id PK
        string notebook_id FK
        json messages
        string model_override
    }

    CREDENTIAL {
        string id PK
        string name
        string provider
        string api_key
        string base_url
        json modalities
    }

    MODEL {
        string id PK
        string provider
        string model_id
        string type
        string credential FK
    }

    TRANSFORMATION {
        string id PK
        string name
        text template
        string output_type
    }

    SPEAKER_PROFILE {
        string id PK
        string name
        string voice_id
        string provider
    }

    EPISODE_PROFILE {
        string id PK
        string name
        json speaker_ids
        string style
    }

    PODCAST_EPISODE {
        string id PK
        string notebook_id FK
        string profile_id FK
        string status
        string audio_file
    }

    NOTEBOOK ||--o{ SOURCE : "contains"
    NOTEBOOK ||--o{ NOTE : "contains"
    NOTEBOOK ||--o{ CHAT_SESSION : "has"
    NOTEBOOK ||--o{ PODCAST_EPISODE : "has"
    SOURCE ||--o{ SOURCE_INSIGHT : "generates"
    SOURCE ||--o{ SOURCE_EMBEDDING : "vectorized_as"
    NOTE }o--o{ SOURCE : "references"
    MODEL }o--|| CREDENTIAL : "uses"
    EPISODE_PROFILE }o--o{ SPEAKER_PROFILE : "includes"
    PODCAST_EPISODE }o--|| EPISODE_PROFILE : "uses"
```

---

## LangGraph Workflows

Seven state machine workflows handle all AI-powered operations:

```mermaid
graph TD
    subgraph INGESTION["Source Ingestion — source.py"]
        I1([Start]) --> I2[Extract Content\ncontent-core]
        I2 --> I3[Save to SurrealDB]
        I3 --> I4[Chunk + Embed\nbatch embedding]
        I4 --> I5[Run Transformations]
        I5 --> I6([End])
    end

    subgraph CHAT["Notebook Chat — chat.py"]
        C1([Start]) --> C2[Load Message History\nSqliteSaver]
        C2 --> C3[Build System Prompt\nJinja2]
        C3 --> C4[LLM Invocation\nprovision_langchain_model]
        C4 --> C5[Persist Messages]
        C5 --> C6([End])
    end

    subgraph SRCCHAT["Source Chat — source_chat.py"]
        SC1([Start]) --> SC2[Fetch Source Context\ncontext_builder]
        SC2 --> SC3[Build Prompt with Context]
        SC3 --> SC4[LLM Invocation]
        SC4 --> SC5([End])
    end

    subgraph ASK["Search & Synthesis — ask.py"]
        A1([Start]) --> A2[Entry — Parse Query]
        A2 --> A3[Query × N\nParallel Searches]
        A3 --> A4[Retrieve Embeddings\nVector Search]
        A4 --> A5[Final Answer\nSynthesize Results]
        A5 --> A6([End])
    end

    subgraph TRANSFORM["Transformation — transformation.py"]
        T1([Start]) --> T2[Load Transformation Template]
        T2 --> T3[Render Jinja2 Template]
        T3 --> T4[LLM Invocation]
        T4 --> T5[Save Output as Note/Insight]
        T5 --> T6([End])
    end

    subgraph PODCAST["Podcast — via podcast-creator"]
        P1([Start]) --> P2[Load Episode Profile\n+ Speaker Profiles]
        P2 --> P3[Generate Outline\nLLM]
        P3 --> P4[Generate Transcript\nLLM]
        P4 --> P5[TTS Synthesis\nElevenLabs / other]
        P5 --> P6[Merge Audio]
        P6 --> P7([End])
    end
```

### Model Selection Logic

```mermaid
flowchart TD
    REQ[Request with model_id / context] --> CHECK1{Model record\nin DB?}
    CHECK1 -->|Yes| CHECK2{Linked\nCredential?}
    CHECK1 -->|No| FALLBACK1[Use DefaultModels\nby type]
    CHECK2 -->|Yes| CRED[Load Credential Config\nto_esperanto_config]
    CHECK2 -->|No| ENV[key_provider:\nDB Creds → Env Vars]
    CRED --> CTX{Context >\n105K tokens?}
    ENV --> CTX
    FALLBACK1 --> CTX
    CTX -->|Yes| LARGE[Use large_context_model]
    CTX -->|No| NORMAL[Use specified / default model]
    LARGE --> PROV[provision_langchain_model\nEsperanto Factory]
    NORMAL --> PROV
    PROV --> LLM[LangChain LLM Instance]
```

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

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant DB as SurrealDB
    participant AI as Embedding Provider

    UI->>API: POST /api/search/ask {"query": "..."}
    API->>AI: embed(query)
    AI-->>API: query_vector[1536]
    API->>DB: SELECT * FROM source_embedding\nORDER BY vector::distance(embedding, $query_vector)
    DB-->>API: Top-K chunks + source IDs
    API->>DB: Fetch full source records
    DB-->>API: Source content
    API->>AI: LLM synthesize(sources + query)
    AI-->>API: Synthesized answer
    API-->>UI: { answer, sources[] }
```

---

## Async Command Queue

All heavy operations run as fire-and-forget jobs:

```mermaid
graph LR
    subgraph Triggers["Trigger Points"]
        T1[Source Upload]
        T2[Note Save]
        T3[Insight Create]
        T4[Podcast Request]
        T5[Rebuild Embeddings]
    end

    subgraph Queue["surreal-commands Job Queue"]
        Q1[embed_source_command]
        Q2[embed_note_command]
        Q3[embed_insight_command]
        Q4[create_insight_command]
        Q5[process_source_command]
        Q6[run_transformation_command]
        Q7[generate_podcast_command]
        Q8[rebuild_embeddings_command]
    end

    subgraph Retry["Retry Policy"]
        R1[Exponential Jitter\n1–120s backoff]
        R2[Max 5–15 attempts]
        R3[Stop on ValueError\nRetry on transient errors]
    end

    subgraph Poll["Status Polling"]
        P1["GET /api/commands/id"]
        P2["queued / running / completed / failed"]
    end

    T1 --> Q5
    T2 --> Q2
    T3 --> Q3 & Q4
    T4 --> Q7
    T5 --> Q8
    Q1 & Q2 & Q3 & Q4 & Q5 & Q6 & Q7 & Q8 --> R1
    R1 --> R2 --> R3
    Q5 -.->|status check| P1
    Q7 -.->|status check| P1
    P1 --> P2
```

---

## Frontend Architecture

```mermaid
graph TD
    subgraph APP["Next.js App Router (src/app/)"]
        AUTH["(auth)/login"]
        DASH["(dashboard)/"]
        NB[notebooks/]
        SRC[sources/]
        CHT[chat/]
        SRCH[search/]
        POD[podcasts/]
        MDL[models/]
        SET[settings/]
    end

    subgraph COMPONENTS["Components (src/components/)"]
        UI[ui/ — Radix + Shadcn]
        LAY[layout/ — AppShell, Sidebar]
        COM[common/ — CommandPalette, ModelSelector]
        SRCCOMP[source/ — SourceCard, UploadForm]
        PODCOMP[podcasts/ — EpisodePlayer]
    end

    subgraph STATE["State Management"]
        TQ[TanStack Query\nServer State]
        ZS[Zustand\nAuth + UI State]
    end

    subgraph APICLIENT["API Layer (src/lib/api/)"]
        CL[client.ts — Axios + interceptors]
        NBS[notebooks.ts]
        SRCS[sources.ts]
        CHS[chat.ts]
        NTS[notes.ts]
        MDS[models.ts]
        CRS[credentials.ts]
        SRS[search.ts]
        PDS[podcasts.ts]
    end

    DASH --> NB & SRC & CHT & SRCH & POD & MDL & SET
    AUTH --> ZS
    NB --> COMPONENTS
    SRC --> COMPONENTS
    COMPONENTS --> STATE
    STATE --> TQ & ZS
    TQ --> APICLIENT
    CL -->|"Bearer token\nFormData\ninterceptors"| API[(FastAPI :5055)]
```

### State Management Pattern

| Layer | Technology | Scope | Persistence |
|-------|-----------|-------|-------------|
| Server data (notebooks, sources, notes) | TanStack Query | App-wide | In-memory cache |
| Auth (token, isAuthenticated) | Zustand + persist | App-wide | localStorage |
| UI state (modals, forms) | React useState | Component | In-memory |

---

## Authentication & Security

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant MW as Auth Middleware
    participant API as FastAPI Router

    U->>FE: Enter password
    FE->>MW: POST /api/auth/password
    MW->>MW: Validate OPEN_NOTEBOOK_PASSWORD
    MW-->>FE: { token: "..." }
    FE->>FE: Store token in localStorage

    U->>FE: Navigate to page
    FE->>MW: GET /api/notebooks\nAuthorization: Bearer {token}
    MW->>MW: Validate token
    MW->>API: Forward request
    API-->>FE: Response data

    Note over FE,API: 401 response clears auth → redirect to /login
```

> **Production Warning**: `PasswordAuthMiddleware` is dev-only. Replace with OAuth2/JWT for production deployments.

### Credential Encryption

- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key source**: `OPEN_NOTEBOOK_ENCRYPTION_KEY` environment variable
- **Scope**: All API keys stored in `Credential` records
- **At-rest**: Encrypted in SurrealDB; decrypted only on use

---

## Error Handling

```mermaid
graph TD
    RAW[Raw Exception\nfrom LLM / DB / Network] --> CLS[classify_error\nerror_classifier.py]
    CLS --> MAP{Keyword\nMatching}
    MAP -->|rate limit| RL[RateLimitError → 429]
    MAP -->|auth / key| AE[AuthenticationError → 401]
    MAP -->|not found| NF[NotFoundError → 404]
    MAP -->|invalid input| II[InvalidInputError → 400]
    MAP -->|network| NE[NetworkError → 502]
    MAP -->|other| GE[OpenNotebookError → 500]
    RL & AE & NF & II & NE & GE --> FH[FastAPI Global\nException Handler]
    FH --> JSON["JSON { detail: message }\nHTTP Response"]
    JSON --> FE[Frontend\ngetApiErrorMessage]
    FE --> TOAST[User-visible\nToast / Alert]
```

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

```mermaid
graph TB
    subgraph HOST["Host Machine"]
        subgraph DC["docker-compose"]
            subgraph SDB["surrealdb container"]
                S1[SurrealDB :8000]
                S2["Persistent Volume: /data/surrealdb"]
                S1 --- S2
            end

            subgraph APP["open_notebook container"]
                A1[FastAPI :5055]
                A2[Next.js :3000]
                A3["surreal-commands Worker"]
                A4["SQLite: /data/sqlite-db — LangGraph Checkpoints"]
                A5["Files: /data/uploads"]
                A1 --- A4
                A1 --- A5
                A3 --- A4
            end
        end

        BR[Browser\n:3000]
        BR --> A2
        A2 -->|HTTP REST| A1
        A1 -->|WebSocket\nSurrealQL| S1
        A3 -->|SurrealQL| S1
    end
```

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

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant CQ as Command Queue
    participant CC as content-core
    participant EMB as Embedding Provider
    participant DB as SurrealDB

    U->>FE: Upload file / paste URL
    FE->>API: POST /api/sources (multipart)
    API->>DB: Create Source record (pending)
    API->>CQ: Enqueue process_source_command
    API-->>FE: { source_id, status: "processing" }

    CQ->>CC: extract_content(file/url)
    CC-->>CQ: { full_text, metadata }
    CQ->>DB: Update Source (full_text, metadata)
    CQ->>CQ: chunk_text(full_text)
    CQ->>EMB: embed_batch(chunks[])
    EMB-->>CQ: vectors[][]
    CQ->>DB: Store SourceEmbedding records
    CQ->>DB: Update Source status = "ready"

    FE->>API: GET /api/sources/{id} (polling)
    API-->>FE: { status: "ready", ... }
```

### Chat Message Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant LG as LangGraph chat.py
    participant SQ as SqliteSaver
    participant LLM as LLM Provider

    U->>FE: Type message + Send
    FE->>FE: Optimistic update\n(add message to UI)
    FE->>API: POST /api/chat\n{ notebook_id, message, session_id }
    API->>LG: graph.ainvoke({ messages, config })
    LG->>SQ: Load message history\n(thread_id = session_id)
    LG->>LG: Build system prompt\n(Jinja2 + context)
    LG->>LLM: ainvoke(messages + system)
    LLM-->>LG: AI response
    LG->>SQ: Persist updated history
    LG-->>API: { output: "..." }
    API-->>FE: { message: { role: "assistant", content: "..." } }
    FE->>FE: Update UI with response
```

### Semantic Search Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant LG as LangGraph ask.py
    participant EMB as Embedding Provider
    participant DB as SurrealDB
    participant LLM as LLM Provider

    U->>FE: Type search query
    FE->>API: POST /api/search/ask\n{ query, notebook_id }
    API->>LG: ask_graph.ainvoke({ query })

    LG->>LG: Entry node:\nparse + expand query
    LG->>EMB: embed(query)
    EMB-->>LG: query_vector[1536]

    loop For each sub-query
        LG->>DB: SELECT * FROM source_embedding\nWHERE vector::distance < threshold\nORDER BY similarity DESC LIMIT K
        DB-->>LG: Top-K chunks
    end

    LG->>DB: Fetch full Source records
    DB-->>LG: Source content + metadata
    LG->>LLM: Synthesize answer\nwith sources as context
    LLM-->>LG: Cited answer
    LG-->>API: { answer, sources[] }
    API-->>FE: Response with citations
    FE->>FE: Render answer + source cards
```

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
Why per-folder?
Each layer has genuinely different rules:

Folder	What its CLAUDE.md covers
open_notebook/ai/	How ModelManager works, Esperanto usage
open_notebook/graphs/	LangGraph node/edge patterns, async rules
open_notebook/database/	SurrealQL syntax, migration authoring
open_notebook/domain/	Repository pattern, model conventions
frontend/	React patterns, TanStack Query cache rules, i18n requirement
A CLAUDE.md at the root would be too generic to be useful in deep subdirectories, and too long to load efficiently.

The hierarchy

CLAUDE.md                  ← project-wide overview (you always get this)
├── api/CLAUDE.md          ← loaded when working in api/
├── frontend/CLAUDE.md     ← loaded when working in frontend/
└── open_notebook/
    ├── CLAUDE.md          ← loaded for any open_notebook/ work
    ├── ai/CLAUDE.md       ← loaded only when in ai/
    └── graphs/CLAUDE.md   ← loaded only when in graphs/
    
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
