# SmartDialer 🚀

> **Outbound Call Dialer with Progressive & Predictive Pacing — Built for Scale**

A production-grade outbound call center simulation demonstrating distributed systems design, predictive pacing algorithms, mandatory safety gating, and observable failure recovery — all runnable locally with a single command.

---

## ⚡ Quick Start (Docker)

```bash
git clone https://github.com/Himkar001/smart_dialer
cd smart_dialer

# Copy env file
cp backend/.env.example backend/.env

# Boot all 5 services: postgres, redis, backend, celery worker, frontend
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard (React) | http://localhost:3000 |
| API (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| WebSocket metrics | ws://localhost:8000/ws/metrics |

---

## 🧪 Run Tests (No Docker Required)

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows
pip install -r requirements.txt
pytest tests/ -v
```

```
117 passed in 26s ✅
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Dashboard                          │
│  AgentPool | CallMetrics | PacingChart | SafetyLog | Failures│
└─────────────────────────┬───────────────────────────────────┘
                          │  WebSocket (metrics every 2s)
                          │  REST API (start/stop/trigger)
┌─────────────────────────▼───────────────────────────────────┐
│                   FastAPI Backend                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Dialing Pipeline                       │    │
│  │                                                      │    │
│  │  PacingEngine ──► SafetyController ──► CallAllocator │    │
│  │  (formula)         (4-path gate)       (SKIP LOCKED) │    │
│  │                                                      │    │
│  │  AnswerRateTracker   AgentStateMachine  CallStateMachine│  │
│  │  (rolling window)    (7 states)         (9 states)   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Providers:  ProviderA (fast/reliable) | ProviderB (chaotic) │
│  Workers:    Celery + Redis (crash recovery via vis. timeout)│
└──────────┬────────────────────────────┬─────────────────────┘
           │                            │
    ┌──────▼──────┐              ┌──────▼──────┐
    │  PostgreSQL  │              │    Redis    │
    │  (schema +   │              │  (broker +  │
    │   migrations)│              │   backend)  │
    └─────────────┘              └─────────────┘
```

See [`docs/system_architecture.png`](docs/system_architecture.png) for the full diagram.

---

## 📊 Dialing Modes

### Progressive
- Strict **1:1** — one call per available agent
- Zero abandoned calls guaranteed
- Formula: `dial_count = available_agents`

### Predictive
- Dial **more** than available agents, anticipating failed/no-answer calls
- Formula: `dial_count = ⌈ agents × 0.85 / max(answer_rate, 0.10) ⌉`
- **Cold start** (< 10 samples) → falls back to progressive automatically
- **All requests pass through Safety Controller** — no bypass possible

---

## 🛡 Safety Controller

Mandatory gate between pacing engine and provider. 4-path priority decision:

| Priority | Action | Condition | Effect |
|---|---|---|---|
| 1 | **FALLBACK** | Abandoned rate > 3% | Force 1:1 (regulatory compliance) |
| 2 | **REJECT** | Provider health < 0.40 | approved = 0, stop dialing |
| 3 | **REDUCE** | Health < 0.70 OR ratio > 3× | Cap at 1.5× available agents |
| 4 | **APPROVE** | All thresholds met | Pass through unchanged |

---

## ⚡ Failure Scenarios

Trigger from the dashboard or via API:

```bash
curl -X POST http://localhost:8000/api/simulation/trigger/provider-outage
curl -X POST http://localhost:8000/api/simulation/trigger/worker-crash
curl -X POST http://localhost:8000/api/simulation/trigger/agent-drop
curl -X POST http://localhost:8000/api/simulation/trigger/duplicate-storm
curl -X POST http://localhost:8000/api/simulation/trigger/ooo-flood
```

| Scenario | What Breaks | How It Recovers |
|---|---|---|
| `provider-outage` | ProviderB health → 0.1 → Safety REJECTS all calls | Auto-heal in 15s |
| `worker-crash` | All call tasks cancelled → agents stuck DIALING | Stale agent detector releases in 3s |
| `agent-drop` | 50% agents → OFFLINE → dialer places fewer calls | Agents auto-restored in 20s |
| `duplicate-storm` | 5× duplicate RINGING events per call | Idempotency key absorbs all (0 state changes) |
| `ooo-flood` | COMPLETED sent before CONNECTED | State machine transition guards reject all |

---

## 🔑 Key Concurrency Mechanisms

### SKIP LOCKED (Agent Reservation)
```sql
SELECT * FROM agents
WHERE state = 'AVAILABLE' AND campaign_id = $1
LIMIT 1
FOR UPDATE SKIP LOCKED
```
Two Celery workers hitting `reserve_agent()` simultaneously: Worker A locks row → Worker B **skips it** and takes the next one. No double-reservation possible.

### Savepoint Idempotency (Event Processing)
```python
async with db.begin_nested():  # SAVEPOINT
    db.add(call_event)
    await db.flush()           # Triggers UNIQUE constraint check
# IntegrityError on duplicate → outer transaction survives
```
Provider events have a `idempotency_key`. Duplicate events from unreliable providers are caught by the UNIQUE constraint inside a savepoint — the outer transaction continues.

### State Machine Transition Guards
```python
VALID_CALL_TRANSITIONS = {
    CallState.RINGING: {CallState.CONNECTED, CallState.FAILED, CallState.CANCELLED},
    # COMPLETED from RINGING is NOT in this set → silently dropped
}
```
Out-of-order events are checked against an allowlist — invalid transitions are logged and dropped without corrupting state.

---

## 🧩 Project Structure

```
smart_dialer/
├── backend/
│   ├── app/
│   │   ├── models/          # 5 DB models with Alembic migrations
│   │   ├── providers/       # Abstract TelecomProvider + ProviderA/B
│   │   ├── routers/         # FastAPI routes (agents, calls, simulation, ws)
│   │   ├── services/        # All business logic
│   │   │   ├── agent_state_machine.py   # 7 states, SKIP LOCKED
│   │   │   ├── call_state_machine.py    # 9 states, idempotency, OOO guard
│   │   │   ├── call_allocator.py        # 4-step atomic pipeline
│   │   │   ├── dialer.py               # Progressive + Predictive cycles
│   │   │   ├── answer_rate_tracker.py  # Rolling deque, cold-start
│   │   │   ├── pacing_engine.py        # Predictive formula
│   │   │   ├── safety_controller.py    # 4-path mandatory gate
│   │   │   ├── failure_scenarios.py    # 5 injectable failure modes
│   │   │   └── broadcaster.py          # WebSocket metrics push
│   │   └── workers/
│   │       ├── celery_app.py           # Celery config (crash recovery)
│   │       └── dialer_task.py          # Distributed dial task
│   └── tests/               # 117 tests (SQLite in-memory)
│
├── frontend/
│   └── src/
│       ├── components/      # AgentPool, CallMetrics, PacingChart,
│       │                    # SafetyLog, ProviderHealth, FailureScenarios
│       ├── hooks/           # useWebSocket, useMetrics
│       └── lib/             # api.ts, utils.ts
│
└── docs/
    ├── HLD.md               # High-level design + architecture diagrams
    ├── LLD.md               # Low-level design + pseudocode
    ├── PRD.md               # Product requirements (FR-001 to FR-015)
    ├── TRD.md               # Technical requirements + API spec
    └── IMPLEMENTATION_PLAN.md  # Sprint breakdown + ADR
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [HLD.md](docs/HLD.md) | System architecture, component interactions, data flows |
| [LLD.md](docs/LLD.md) | State machine diagrams, pacing formula, pseudocode |
| [PRD.md](docs/PRD.md) | Product requirements, user stories, acceptance criteria |
| [TRD.md](docs/TRD.md) | API specification, database schema, non-functional requirements |
| [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Sprint plan, ADR, trade-offs |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI 0.104, SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL 15 (production), SQLite (tests) |
| **Task Queue** | Celery 5.3 + Redis 7 |
| **Frontend** | React 18, Vite 5, Tailwind CSS 3.4, Recharts 2 |
| **Testing** | pytest-asyncio, aiosqlite (no Docker needed) |
| **Container** | Docker Compose (5 services) |

---

## 💬 Design Question Answer

**"How would you handle predictive dialing at scale with 10,000 agents?"**

The architecture is already designed for horizontal scale:

1. **Celery workers** horizontally scale the dialing layer — add more workers, throughput scales linearly. `SKIP LOCKED` prevents double-reservation at any worker count.

2. **Answer Rate Tracker** → swap `deque` for Redis `SORTED SET` (TTL-based sliding window). Same interface, no code change in callers.

3. **Safety Controller** → stateless pure function. Deploy as multiple replicas behind a load balancer.

4. **Pacing Engine** → shards by campaign ID. Each campaign independently tracked. No cross-campaign state.

5. **Database** → partition `calls` and `call_events` by `campaign_id`. Add read replicas for metrics queries (broadcaster uses read-only SELECTs).

6. **WebSocket** → use Redis Pub/Sub for multi-instance broadcasting. Each backend instance publishes metrics to Redis channel, all subscribe and push to their own connected clients.

The key invariant: **Safety Controller is the only path to the provider**. At any scale, adding workers doesn't bypass the safety gate — it only increases throughput of approved calls.
