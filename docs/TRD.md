# SmartDialer — Technical Requirements Document

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-08-19 |
| Status | Approved |

---

## 1. Purpose and Scope

This document defines the technical specifications for implementing SmartDialer. It covers the exact technology stack, system requirements, API contracts, database schema, concurrency design, configuration, and testing requirements. It serves as the authoritative reference for engineers building any component.

---

## 2. Tech Stack Specification

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11 |
| Web Framework | FastAPI | 0.104+ |
| ORM | SQLAlchemy (async) | 2.0 |
| Migrations | Alembic | 1.12+ |
| Database | PostgreSQL | 15 |
| Cache / Broker | Redis | 7 |
| Task Queue | Celery | 5.3 |
| HTTP Client | httpx | 0.25+ |
| Validation | Pydantic | 2.x |
| Frontend Framework | React | 18 |
| Build Tool | Vite | 5 |
| CSS Framework | Tailwind CSS | 3.4 |
| UI Components | shadcn/ui | latest |
| Charts | Recharts | 2.x |
| Container Orchestration | Docker Compose | 3.8 |
| Testing | pytest + pytest-asyncio | 7.x |
| Load Testing | Locust | 2.x |

---

## 3. System Requirements

### Minimum (Local Development)
| Resource | Minimum |
|---|---|
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 5 GB free |
| Docker Desktop | 24+ |
| Docker Compose | v2+ |
| OS | Windows 10/11, macOS 12+, Ubuntu 20.04+ |

### Without Docker (Manual Setup)
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ running locally
- Redis 7+ running locally

---

## 4. API Specification

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/agents` | List all agents with current state |
| `POST` | `/api/agents` | Create agents (bulk) |
| `PATCH` | `/api/agents/{id}/state` | Manually update agent state |
| `GET` | `/api/calls` | List calls with filters (state, campaign_id) |
| `GET` | `/api/calls/{id}` | Get single call with event history |
| `GET` | `/api/campaigns` | List campaigns |
| `POST` | `/api/campaigns` | Create a new campaign |
| `PATCH` | `/api/campaigns/{id}/start` | Start a campaign |
| `PATCH` | `/api/campaigns/{id}/stop` | Stop a campaign |
| `POST` | `/api/simulation/start` | Start simulation with parameters |
| `POST` | `/api/simulation/stop` | Stop current simulation |
| `POST` | `/api/simulation/trigger/worker-crash` | Trigger worker crash scenario |
| `POST` | `/api/simulation/trigger/provider-outage` | Trigger provider outage scenario |
| `POST` | `/api/simulation/trigger/agent-drop` | Trigger sudden agent drop scenario |
| `GET` | `/api/metrics/snapshot` | Current metrics snapshot |
| `GET` | `/api/metrics/history` | Historical metrics (time-series) |

### WebSocket Endpoint

| Path | Description | Message Interval |
|---|---|---|
| `WS /ws/metrics` | Real-time metrics stream | ~1 second |

**WebSocket Message Schema:**
```json
{
  "timestamp": "2026-08-19T14:00:00Z",
  "agents": {
    "total": 100,
    "available": 42,
    "reserved": 3,
    "dialing": 5,
    "connected": 45,
    "wrap_up": 5,
    "offline": 0
  },
  "calls": {
    "queued": 150,
    "initiated": 5,
    "ringing": 3,
    "connected": 45,
    "completed": 892,
    "failed": 12
  },
  "pacing": {
    "mode": "predictive",
    "dial_count_requested": 18,
    "dial_count_approved": 15,
    "answer_rate": 0.62,
    "provider_health": 0.91
  },
  "safety": {
    "last_decision": "REDUCE",
    "last_reason": "dial_count exceeded 2x available_agents",
    "abandoned_rate": 0.021
  }
}
```

---

## 5. Database Schema

### Table: `agents`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default gen | Unique agent ID |
| `name` | VARCHAR(100) | NOT NULL | Agent display name |
| `state` | ENUM | NOT NULL, default OFFLINE | Current state |
| `campaign_id` | UUID | FK campaigns.id, nullable | Assigned campaign |
| `reserved_at` | TIMESTAMP | nullable | When agent was reserved |
| `heartbeat_at` | TIMESTAMP | nullable | Last worker heartbeat |
| `created_at` | TIMESTAMP | NOT NULL | Record creation time |
| `updated_at` | TIMESTAMP | NOT NULL | Last update time |

**Index**: `(state, campaign_id)` — used for fast agent pool queries

### Table: `borrowers`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique borrower ID |
| `phone` | VARCHAR(20) | NOT NULL | Phone number to dial |
| `campaign_id` | UUID | FK campaigns.id | Campaign assignment |
| `state` | ENUM | NOT NULL | PENDING, RESERVED, CALLED, COMPLETED |
| `attempts` | INTEGER | default 0 | Number of dial attempts |

### Table: `campaigns`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique campaign ID |
| `name` | VARCHAR(200) | NOT NULL | Campaign name |
| `mode` | ENUM | NOT NULL | PROGRESSIVE, PREDICTIVE |
| `state` | ENUM | NOT NULL | DRAFT, ACTIVE, PAUSED, COMPLETED |
| `provider` | ENUM | NOT NULL | PROVIDER_A, PROVIDER_B |
| `max_retries` | INTEGER | default 2 | Max dial attempts per borrower |
| `created_at` | TIMESTAMP | NOT NULL | |

### Table: `calls`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique call ID |
| `campaign_id` | UUID | FK | Campaign |
| `agent_id` | UUID | FK agents.id, nullable | Assigned agent |
| `borrower_id` | UUID | FK borrowers.id | Target borrower |
| `state` | ENUM | NOT NULL | Current call state |
| `provider` | ENUM | NOT NULL | Which provider was used |
| `provider_call_id` | VARCHAR | nullable | Provider's call reference ID |
| `idempotency_key` | VARCHAR | UNIQUE | Prevents duplicate processing |
| `attempt` | INTEGER | default 1 | Retry attempt number |
| `initiated_at` | TIMESTAMP | nullable | When call was started |
| `connected_at` | TIMESTAMP | nullable | When call was answered |
| `completed_at` | TIMESTAMP | nullable | When call ended |
| `created_at` | TIMESTAMP | NOT NULL | |

### Table: `call_events`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Event ID |
| `call_id` | UUID | FK calls.id | Parent call |
| `event_type` | VARCHAR(50) | NOT NULL | RINGING, ANSWERED, COMPLETED, FAILED |
| `idempotency_key` | VARCHAR | UNIQUE | Prevents duplicate event processing |
| `raw_payload` | JSONB | nullable | Raw provider event payload |
| `processed_at` | TIMESTAMP | NOT NULL | When event was processed |

---

## 6. State Machine Formal Specification

### Agent Valid Transitions
| From State | To State | Trigger |
|---|---|---|
| OFFLINE | AVAILABLE | Agent logs in |
| AVAILABLE | RESERVED | Worker acquires DB lock |
| AVAILABLE | PAUSED | Agent requests break |
| RESERVED | DIALING | Call initiated with provider |
| RESERVED | AVAILABLE | Call initiation failed |
| DIALING | CONNECTED | ANSWERED event received |
| DIALING | AVAILABLE | FAILED / CANCELLED event |
| CONNECTED | WRAP_UP | COMPLETED event |
| CONNECTED | OFFLINE | Agent disconnects (failure) |
| WRAP_UP | AVAILABLE | Wrap-up timer expires |
| WRAP_UP | PAUSED | Agent requests break |
| PAUSED | AVAILABLE | Agent resumes |
| PAUSED | OFFLINE | Agent logs out |

### Call Valid Transitions
| From State | To State | Trigger |
|---|---|---|
| QUEUED | RESERVED | Agent + borrower allocated |
| RESERVED | INITIATED | provider.initiate_call() success |
| RESERVED | FAILED | Allocation failed |
| INITIATED | RINGING | Provider event: RINGING |
| RINGING | ANSWERED | Provider event: ANSWERED |
| RINGING | FAILED | Timeout / no answer |
| ANSWERED | CONNECTED | Agent bridged to call |
| ANSWERED | FAILED | Agent dropped |
| CONNECTED | COMPLETED | Provider event: COMPLETED |
| CONNECTED | FAILED | Call dropped unexpectedly |
| FAILED | QUEUED | Retry if attempts < max_retries |

---

## 7. Concurrency Requirements

### Agent Reservation (Critical Path)
```sql
-- Atomic agent reservation — only one worker can succeed
BEGIN;
SELECT id, name FROM agents
WHERE state = 'AVAILABLE'
  AND campaign_id = :campaign_id
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- If row found:
UPDATE agents SET state = 'RESERVED', reserved_at = NOW(), heartbeat_at = NOW()
WHERE id = :agent_id;
COMMIT;
```

`SKIP LOCKED` ensures competing workers skip already-locked rows. No waiting, no deadlocks, no double-reservation.

### Celery Task Idempotency
- Each Celery task carries a unique `task_id` derived from `(call_id, attempt_number)`
- Duplicate task execution is detected via Redis key: `task:{task_id}:processed`
- If key exists → task returns early without side effects

### Distributed Locks (Redis)
- Campaign-level lock prevents two workers from running the pacing loop simultaneously for the same campaign
- Lock key: `lock:pacing:{campaign_id}`, TTL: 5 seconds
- Worker that fails to acquire lock skips this cycle

---

## 8. Event Processing Requirements

### Idempotency Key Design
- Key format: `{provider_call_id}:{event_type}:{event_sequence_number}`
- Stored in `call_events.idempotency_key` with UNIQUE constraint
- On duplicate: DB write fails with unique constraint error → silently swallowed → current state preserved

### Out-of-Order Rejection
- Before applying any transition, check `valid_from_states[target_state]`
- If current state is not in the valid-from set → log warning, return current state unchanged
- Example: `COMPLETED` arriving when state is `QUEUED` → rejected

---

## 9. Configuration (Environment Variables)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery broker URL |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery result backend URL |
| `MAX_DIAL_RATIO` | `3.0` | Max calls / available agents (safety cap) |
| `SAFETY_ABANDONED_THRESHOLD` | `0.03` | Abandoned call rate that triggers reject |
| `PROVIDER_HEALTH_THRESHOLD_REJECT` | `0.4` | Health score below which new calls are rejected |
| `PROVIDER_HEALTH_THRESHOLD_REDUCE` | `0.7` | Health score below which calls are reduced |
| `HEARTBEAT_INTERVAL_SECONDS` | `10` | Worker heartbeat frequency |
| `HEARTBEAT_TIMEOUT_SECONDS` | `30` | After which a worker is considered crashed |
| `ANSWER_RATE_WINDOW` | `100` | Number of recent calls for rolling answer rate |
| `WRAP_UP_SECONDS` | `30` | Agent wrap-up timer duration |
| `PACING_CYCLE_SECONDS` | `2` | How often the pacing engine runs |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 10. Testing Requirements

### Unit Tests (pytest)
| Module | Coverage Target | Key Test Cases |
|---|---|---|
| `agent.py` state machine | ≥ 85% | All valid transitions, all invalid transitions rejected, concurrent reservation |
| `call.py` state machine | ≥ 85% | Idempotent events, out-of-order rejection, all valid transitions |
| `pacing_engine.py` | ≥ 80% | Progressive count, predictive formula, edge cases (0 agents, 0 answer rate) |
| `safety_controller.py` | ≥ 90% | All 4 decision paths, bypass-proof (no way to call provider directly) |
| `provider_a.py` / `provider_b.py` | ≥ 75% | Expected behavior, chaos behavior |

### Integration Tests
| Scenario | Test |
|---|---|
| Full progressive call flow | Agent reserved → Call initiated → RINGING → ANSWERED → COMPLETED → Agent WRAP_UP |
| Double reservation prevention | Two concurrent workers attempt to reserve same agent → only one succeeds |
| Worker crash recovery | Simulate crash after RESERVED, verify cleanup job releases agent |
| Duplicate event handling | Send same ANSWERED event twice → state transitions only once |
| Out-of-order events | Send COMPLETED before RINGING → second event rejected |

### Load Test (Locust)
- **Target**: 100 concurrent virtual agents
- **Duration**: 60 seconds
- **Tasks**: Start simulation, poll metrics, trigger failure scenarios
- **Pass criteria**: p95 API response < 500ms, zero 5xx errors

---

## 11. Docker Compose Services

| Service | Image | Port | Depends On | Purpose |
|---|---|---|---|---|
| `postgres` | postgres:15-alpine | 5432 | — | Primary database |
| `redis` | redis:7-alpine | 6379 | — | Broker + cache |
| `backend` | ./backend (custom) | 8000 | postgres, redis | FastAPI API server |
| `worker` | ./backend (custom) | — | backend, redis | Celery dialing worker |
| `frontend` | ./frontend (custom) | 3000 | backend | React dashboard |

All services include health checks. `backend` waits for `postgres` and `redis` to be healthy before starting.

---

## 12. Security Considerations

> Note: This is a prototype. These are minimal considerations, not production security.

- **No authentication**: The API has no auth. Acceptable for local prototype.
- **CORS**: Backend configured to allow `http://localhost:3000` only.
- **Input Validation**: All API inputs validated via Pydantic schemas. SQLAlchemy ORM prevents SQL injection.
- **Environment Variables**: Secrets (DB password) via `.env` file, not hardcoded. `.env` is in `.gitignore`.
- **No PII in logs**: Phone numbers are masked in logs (show only last 4 digits).
