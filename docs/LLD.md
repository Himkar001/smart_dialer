# SmartDialer — Low Level Design

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-08-19 |
| Status | Approved |

---

## 1. Purpose

This document provides the internal design of every SmartDialer component — module structure, data models, core algorithm pseudocode, API examples, and frontend component architecture. Use this as the reference when implementing any individual module.

---

## 2. Project Structure

```
smart_dialer/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, middleware, CORS
│   │   ├── config.py                  # Pydantic Settings from env vars
│   │   ├── database.py                # Async engine, session factory
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py               # Agent ORM + AgentStateMachine
│   │   │   ├── call.py                # Call ORM + CallStateMachine
│   │   │   ├── campaign.py            # Campaign ORM
│   │   │   ├── borrower.py            # Borrower ORM
│   │   │   └── call_event.py          # CallEvent audit log ORM
│   │   │
│   │   ├── schemas/
│   │   │   ├── agent.py               # AgentCreate, AgentResponse, AgentStateUpdate
│   │   │   ├── call.py                # CallResponse, CallEventResponse
│   │   │   ├── campaign.py            # CampaignCreate, CampaignResponse
│   │   │   ├── simulation.py          # SimulationStartRequest, TriggerRequest
│   │   │   └── metrics.py             # MetricsSnapshot, MetricsHistory
│   │   │
│   │   ├── routers/
│   │   │   ├── agents.py              # GET /agents, POST /agents, PATCH /agents/{id}/state
│   │   │   ├── calls.py               # GET /calls, GET /calls/{id}
│   │   │   ├── campaigns.py           # CRUD + start/stop
│   │   │   ├── simulation.py          # start, stop, trigger scenarios
│   │   │   └── metrics.py             # snapshot, history, WebSocket endpoint
│   │   │
│   │   ├── services/
│   │   │   ├── pacing_engine.py       # progressive_dial_count(), predictive_dial_count()
│   │   │   ├── safety_controller.py   # SafetyController.evaluate()
│   │   │   ├── call_allocator.py      # allocate(campaign, count) — atomic binding
│   │   │   ├── answer_rate_tracker.py # Redis rolling window answer rate
│   │   │   └── provider_health.py     # ProviderHealthScorer
│   │   │
│   │   ├── providers/
│   │   │   ├── base.py                # Abstract TelecomProvider
│   │   │   ├── provider_a.py          # ProviderA: fast + reliable
│   │   │   └── provider_b.py          # ProviderB: slow + chaotic
│   │   │
│   │   ├── workers/
│   │   │   ├── celery_app.py          # Celery app instance + config
│   │   │   ├── dialer_worker.py       # @celery_task: main dialing loop
│   │   │   └── heartbeat.py           # @celery_beat: crash detection + cleanup
│   │   │
│   │   └── websocket/
│   │       └── metrics_ws.py          # WebSocket connection manager + broadcaster
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                  # Migration scripts
│   │
│   ├── tests/
│   │   ├── conftest.py                # pytest fixtures (DB, Redis, providers)
│   │   ├── test_agent_state_machine.py
│   │   ├── test_call_state_machine.py
│   │   ├── test_pacing_engine.py
│   │   ├── test_safety_controller.py
│   │   ├── test_call_allocator.py
│   │   ├── test_providers.py
│   │   └── test_failure_scenarios.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    # Root component, routing
│   │   ├── main.tsx                   # React DOM entry
│   │   │
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   │   ├── DashboardLayout.tsx  # Sidebar + main content grid
│   │   │   │   └── Header.tsx           # Top bar with mode toggle + status badge
│   │   │   ├── AgentPool/
│   │   │   │   ├── AgentPool.tsx        # Agent state breakdown panel
│   │   │   │   └── AgentStateBadge.tsx  # Colored badge per state
│   │   │   ├── CallMetrics/
│   │   │   │   ├── CallMetrics.tsx      # Call counter cards
│   │   │   │   └── MetricCard.tsx       # Individual stat card
│   │   │   ├── PacingChart/
│   │   │   │   └── PacingChart.tsx      # Recharts LineChart: pacing vs answer rate
│   │   │   ├── SafetyLog/
│   │   │   │   └── SafetyLog.tsx        # Real-time log of safety controller decisions
│   │   │   ├── FailureScenarios/
│   │   │   │   └── FailureScenarios.tsx # Trigger buttons for 5 scenarios
│   │   │   └── ProviderHealth/
│   │   │       └── ProviderHealth.tsx   # Provider A/B health indicators
│   │   │
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts          # WebSocket connection + auto-reconnect
│   │   │   └── useMetrics.ts            # Metrics state management from WS
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                   # Axios instance + API helpers
│   │   │   └── utils.ts                 # Formatting, color mapping
│   │   │
│   │   └── types/
│   │       └── index.ts                 # TypeScript interfaces matching backend schemas
│   │
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── Dockerfile
│
├── tests/
│   └── load/
│       └── locustfile.py               # Locust load test
│
├── docs/                               # All documentation
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 3. Database Models (Pseudocode)

```python
# models/agent.py
class Agent(Base):
    __tablename__ = "agents"
    id           = Column(UUID, primary_key=True, default=uuid4)
    name         = Column(String(100), nullable=False)
    state        = Column(Enum(AgentState), nullable=False, default=AgentState.OFFLINE)
    campaign_id  = Column(UUID, ForeignKey("campaigns.id"), nullable=True)
    reserved_at  = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_agents_state_campaign", "state", "campaign_id"),
    )

class AgentState(str, Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    WRAP_UP = "WRAP_UP"
    PAUSED = "PAUSED"

# models/call.py
class Call(Base):
    __tablename__ = "calls"
    id               = Column(UUID, primary_key=True, default=uuid4)
    campaign_id      = Column(UUID, ForeignKey("campaigns.id"), nullable=False)
    agent_id         = Column(UUID, ForeignKey("agents.id"), nullable=True)
    borrower_id      = Column(UUID, ForeignKey("borrowers.id"), nullable=False)
    state            = Column(Enum(CallState), nullable=False, default=CallState.QUEUED)
    provider         = Column(Enum(ProviderType), nullable=False)
    provider_call_id = Column(String, nullable=True)
    idempotency_key  = Column(String, unique=True, nullable=False)
    attempt          = Column(Integer, default=1)
    initiated_at     = Column(DateTime, nullable=True)
    connected_at     = Column(DateTime, nullable=True)
    completed_at     = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
```

---

## 4. Agent State Machine Implementation

```python
# services/agent_state_machine.py

VALID_AGENT_TRANSITIONS = {
    AgentState.OFFLINE:    [AgentState.AVAILABLE],
    AgentState.AVAILABLE:  [AgentState.RESERVED, AgentState.PAUSED],
    AgentState.RESERVED:   [AgentState.DIALING, AgentState.AVAILABLE],
    AgentState.DIALING:    [AgentState.CONNECTED, AgentState.AVAILABLE],
    AgentState.CONNECTED:  [AgentState.WRAP_UP, AgentState.OFFLINE],
    AgentState.WRAP_UP:    [AgentState.AVAILABLE, AgentState.PAUSED],
    AgentState.PAUSED:     [AgentState.AVAILABLE, AgentState.OFFLINE],
}

async def reserve_agent(db: AsyncSession, campaign_id: UUID) -> Agent | None:
    """
    Atomically reserve one available agent for a campaign.
    Uses SELECT FOR UPDATE SKIP LOCKED to prevent double-reservation.
    Returns None if no agents available.
    """
    async with db.begin():
        result = await db.execute(
            select(Agent)
            .where(Agent.state == AgentState.AVAILABLE)
            .where(Agent.campaign_id == campaign_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        agent = result.scalar_one_or_none()

        if agent is None:
            return None  # No available agents right now

        agent.state = AgentState.RESERVED
        agent.reserved_at = datetime.utcnow()
        agent.heartbeat_at = datetime.utcnow()
        await db.flush()
        return agent

async def transition_agent(
    db: AsyncSession, agent: Agent, to_state: AgentState
) -> Agent:
    """
    Transition agent to a new state, with guard check.
    Raises InvalidTransitionError if transition is not allowed.
    """
    allowed = VALID_AGENT_TRANSITIONS.get(agent.state, [])
    if to_state not in allowed:
        raise InvalidTransitionError(
            f"Agent {agent.id}: {agent.state} → {to_state} is not allowed"
        )
    agent.state = to_state
    agent.updated_at = datetime.utcnow()
    await db.flush()
    return agent
```

---

## 5. Call State Machine Implementation

```python
# services/call_state_machine.py

VALID_CALL_TRANSITIONS = {
    CallState.QUEUED:     [CallState.RESERVED],
    CallState.RESERVED:   [CallState.INITIATED, CallState.FAILED],
    CallState.INITIATED:  [CallState.RINGING, CallState.FAILED],
    CallState.RINGING:    [CallState.ANSWERED, CallState.FAILED],
    CallState.ANSWERED:   [CallState.CONNECTED, CallState.FAILED],
    CallState.CONNECTED:  [CallState.COMPLETED, CallState.FAILED],
    CallState.FAILED:     [CallState.QUEUED],   # retry path
}

async def process_provider_event(
    db: AsyncSession,
    redis: Redis,
    call_id: UUID,
    event_type: str,
    idempotency_key: str,
    raw_payload: dict
) -> Call:
    """
    Process a telecom provider event idempotently.
    """
    # 1. Idempotency check via Redis (fast path)
    if await redis.get(f"event:processed:{idempotency_key}"):
        logger.info(f"Duplicate event ignored: {idempotency_key}")
        return await get_call(db, call_id)

    async with db.begin():
        call = await db.get(Call, call_id, with_for_update=True)

        target_state = EVENT_TO_STATE_MAP[event_type]
        allowed = VALID_CALL_TRANSITIONS.get(call.state, [])

        if target_state not in allowed:
            logger.warning(
                f"Out-of-order event ignored: call={call_id}, "
                f"current={call.state}, event={event_type}"
            )
            return call  # Reject, do not apply

        # 2. Apply transition
        call.state = target_state
        call.updated_at = datetime.utcnow()

        # 3. Log event for audit trail
        event = CallEvent(
            call_id=call_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            raw_payload=raw_payload,
            processed_at=datetime.utcnow()
        )
        db.add(event)

    # 4. Mark idempotency key as processed in Redis (TTL: 24h)
    await redis.setex(f"event:processed:{idempotency_key}", 86400, "1")

    return call
```

---

## 6. Pacing Engine

```python
# services/pacing_engine.py

class PacingEngine:

    async def calculate(self, campaign: Campaign) -> int:
        if campaign.mode == CampaignMode.PROGRESSIVE:
            return await self.progressive_dial_count(campaign.id)
        else:
            return await self.predictive_dial_count(campaign.id)

    async def progressive_dial_count(self, campaign_id: UUID) -> int:
        available = await count_agents(state=AVAILABLE, campaign_id=campaign_id)
        in_flight = await count_calls(
            state__in=[INITIATED, RINGING], campaign_id=campaign_id
        )
        count = max(0, available - in_flight)
        logger.info(f"[PROGRESSIVE] available={available}, in_flight={in_flight}, dial={count}")
        return count

    async def predictive_dial_count(self, campaign_id: UUID) -> int:
        available_agents = await count_agents(state=AVAILABLE, campaign_id=campaign_id)
        ringing_calls    = await count_calls(state__in=[INITIATED, RINGING], campaign_id=campaign_id)
        answer_rate      = await self.answer_rate_tracker.get(campaign_id)  # 0.0–1.0
        provider_health  = await self.provider_health.get_score()            # 0.0–1.0

        if answer_rate <= 0:
            # No history yet — fall back to progressive to be safe
            return await self.progressive_dial_count(campaign_id)

        predicted_connects = ringing_calls * answer_rate
        headroom = available_agents - predicted_connects
        raw_count = headroom / answer_rate
        dial_count = int(raw_count * provider_health)
        dial_count = max(0, dial_count)

        logger.info(
            f"[PREDICTIVE] available={available_agents}, ringing={ringing_calls}, "
            f"answer_rate={answer_rate:.2f}, provider_health={provider_health:.2f}, "
            f"dial_count={dial_count}"
        )
        return dial_count
```

---

## 7. Safety Controller

```python
# services/safety_controller.py

@dataclass
class SafetyDecision:
    action: str           # APPROVE | REDUCE | REJECT | FALLBACK
    approved_count: int
    reason: str

class SafetyController:

    async def evaluate(
        self, campaign_id: UUID, requested_count: int
    ) -> SafetyDecision:

        available_agents = await count_agents(state=AVAILABLE, campaign_id=campaign_id)
        abandoned_rate   = await self.get_abandoned_rate(campaign_id)
        provider_health  = await self.provider_health.get_score()

        # Rule 1: High abandoned rate → reject + force progressive
        if abandoned_rate > settings.SAFETY_ABANDONED_THRESHOLD:
            return SafetyDecision(
                action="FALLBACK",
                approved_count=await self.progressive_fallback(campaign_id),
                reason=f"Abandoned rate {abandoned_rate:.1%} exceeds threshold"
            )

        # Rule 2: Provider critically unhealthy → reject all new calls
        if provider_health < settings.PROVIDER_HEALTH_THRESHOLD_REJECT:
            return SafetyDecision(
                action="REJECT",
                approved_count=0,
                reason=f"Provider health {provider_health:.2f} below reject threshold"
            )

        # Rule 3: Provider degraded → proportionally reduce
        if provider_health < settings.PROVIDER_HEALTH_THRESHOLD_REDUCE:
            reduced = int(requested_count * provider_health)
            return SafetyDecision(
                action="REDUCE",
                approved_count=reduced,
                reason=f"Provider health {provider_health:.2f} — proportional reduction"
            )

        # Rule 4: Requested count too high relative to available agents → cap it
        max_allowed = int(available_agents * settings.MAX_DIAL_RATIO)
        if requested_count > max_allowed:
            return SafetyDecision(
                action="REDUCE",
                approved_count=max_allowed,
                reason=f"Requested {requested_count} exceeds max ratio cap {max_allowed}"
            )

        # All checks pass → approve
        return SafetyDecision(
            action="APPROVE",
            approved_count=requested_count,
            reason="All safety checks passed"
        )
```

---

## 8. Provider Interface

```python
# providers/base.py
from abc import ABC, abstractmethod

class TelecomProvider(ABC):
    """Abstract interface. Dialing logic only talks to this interface."""

    @abstractmethod
    async def initiate_call(self, phone: str, call_id: str) -> ProviderCallResult:
        """Start an outbound call. Returns provider reference ID."""
        ...

    @abstractmethod
    async def cancel_call(self, provider_call_id: str) -> bool:
        """Cancel an in-progress call."""
        ...

    @abstractmethod
    async def get_call_status(self, provider_call_id: str) -> CallStatusResult:
        """Poll current call status (used for recovery)."""
        ...

    @abstractmethod
    async def get_health_score(self) -> float:
        """Return provider health 0.0 (down) to 1.0 (perfect)."""
        ...

# providers/provider_a.py — Fast + Reliable
class ProviderA(TelecomProvider):
    async def initiate_call(self, phone, call_id):
        await asyncio.sleep(random.uniform(0.05, 0.2))  # 50-200ms latency
        if random.random() < 0.02:                       # 2% failure rate
            raise ProviderError("Provider A transient failure")
        return ProviderCallResult(provider_call_id=str(uuid4()), success=True)

    async def get_health_score(self) -> float:
        return 0.95  # Near-perfect health

# providers/provider_b.py — Slow + Chaotic
class ProviderB(TelecomProvider):
    async def initiate_call(self, phone, call_id):
        await asyncio.sleep(random.uniform(0.5, 3.0))   # 500ms–3s latency
        if random.random() < 0.15:                       # 15% failure rate
            raise asyncio.TimeoutError("Provider B timed out")
        return ProviderCallResult(provider_call_id=str(uuid4()), success=True)

    async def emit_events(self, call_id: str, event_queue: asyncio.Queue):
        """Provider B may emit duplicate or out-of-order events."""
        events = ["RINGING", "ANSWERED", "COMPLETED"]
        if random.random() < 0.3:                        # 30% chance of duplicate
            events.insert(1, "ANSWERED")                 # Duplicate ANSWERED
        if random.random() < 0.2:                        # 20% chance of out-of-order
            events = ["COMPLETED", "ANSWERED", "RINGING"] # Reverse order
        for event in events:
            await asyncio.sleep(random.uniform(0.5, 2.0))
            await event_queue.put((call_id, event))
```

---

## 9. Call Allocator

```python
# services/call_allocator.py

async def allocate(
    db: AsyncSession,
    campaign: Campaign,
    provider: TelecomProvider,
    count: int
) -> list[Call]:
    """
    Atomically allocate up to `count` agent-borrower-call-provider bindings.
    Each allocation is independent — partial success is acceptable.
    """
    allocated_calls = []

    for _ in range(count):
        try:
            async with db.begin_nested():  # Savepoint per allocation
                # Step 1: Reserve an agent (atomic DB lock)
                agent = await reserve_agent(db, campaign.id)
                if agent is None:
                    break  # No more agents available

                # Step 2: Reserve a borrower
                borrower = await reserve_borrower(db, campaign.id)
                if borrower is None:
                    await transition_agent(db, agent, AgentState.AVAILABLE)  # rollback agent
                    break

                # Step 3: Create call record
                call = Call(
                    campaign_id=campaign.id,
                    agent_id=agent.id,
                    borrower_id=borrower.id,
                    state=CallState.RESERVED,
                    provider=campaign.provider,
                    idempotency_key=str(uuid4()),
                )
                db.add(call)
                await db.flush()

                # Step 4: Initiate with provider (outside DB transaction for atomicity)
                try:
                    result = await provider.initiate_call(borrower.phone, str(call.id))
                    call.provider_call_id = result.provider_call_id
                    call.state = CallState.INITIATED
                    call.initiated_at = datetime.utcnow()
                    await transition_agent(db, agent, AgentState.DIALING)
                except ProviderError as e:
                    # Provider failed — rollback call and release agent + borrower
                    call.state = CallState.FAILED
                    await transition_agent(db, agent, AgentState.AVAILABLE)
                    borrower.state = BorrowerState.PENDING
                    logger.warning(f"Provider failed for call {call.id}: {e}")

                allocated_calls.append(call)

        except Exception as e:
            logger.error(f"Allocation error: {e}")
            continue  # Move to next allocation slot

    return allocated_calls
```

---

## 10. Worker Crash Recovery

```python
# workers/heartbeat.py

@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Run cleanup check every 10 seconds
    sender.add_periodic_task(10.0, check_stale_workers.s(), name="heartbeat-cleanup")

@celery_app.task
async def check_stale_workers():
    """
    Detect workers that stopped sending heartbeats and release their reservations.
    A worker is considered crashed if heartbeat_at > HEARTBEAT_TIMEOUT_SECONDS ago.
    """
    stale_threshold = datetime.utcnow() - timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)

    async with get_db_session() as db:
        # Find agents stuck in RESERVED/DIALING with old heartbeats
        stale_agents = await db.execute(
            select(Agent)
            .where(Agent.state.in_([AgentState.RESERVED, AgentState.DIALING]))
            .where(Agent.heartbeat_at < stale_threshold)
        )
        for agent in stale_agents.scalars():
            logger.warning(f"Stale agent detected: {agent.id}, releasing...")

            # Find the associated call
            call = await db.execute(
                select(Call)
                .where(Call.agent_id == agent.id)
                .where(Call.state.in_([CallState.RESERVED, CallState.INITIATED]))
            )
            if call:
                call.state = CallState.QUEUED   # Requeue for retry
                call.agent_id = None

            # Release agent back to available
            agent.state = AgentState.AVAILABLE
            agent.reserved_at = None
            await db.commit()
```

---

## 11. WebSocket Metrics Stream

**Endpoint**: `WS /ws/metrics`  
**Broadcast interval**: ~1 second  

```python
# websocket/metrics_ws.py

class MetricsConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                disconnected.append(ws)
        for ws in disconnected:
            self.active_connections.remove(ws)

# Background task — runs every second
async def metrics_broadcaster(manager: MetricsConnectionManager):
    while True:
        snapshot = await build_metrics_snapshot()
        await manager.broadcast(snapshot)
        await asyncio.sleep(1.0)
```

---

## 12. Key API Examples

```bash
# Create a campaign
curl -X POST http://localhost:8000/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{"name": "August Collections", "mode": "predictive", "provider": "provider_b"}'

# Start simulation
curl -X POST http://localhost:8000/api/simulation/start \
  -H "Content-Type: application/json" \
  -d '{"agent_count": 50, "borrower_count": 500}'

# Get current metrics
curl http://localhost:8000/api/metrics/snapshot

# Trigger worker crash scenario
curl -X POST http://localhost:8000/api/simulation/trigger/worker-crash

# Get all active calls
curl "http://localhost:8000/api/calls?state=CONNECTED"
```

---

## 13. Frontend Component Architecture

| Component | Props / State | Behavior |
|---|---|---|
| `DashboardLayout` | — | Sidebar nav + main content grid; dark mode toggle |
| `Header` | `mode`, `onModeToggle` | Shows Progressive/Predictive toggle + campaign status badge |
| `AgentPool` | `agents: AgentMetrics` | Donut chart + count badges per state; color coded |
| `AgentStateBadge` | `state: AgentState` | Maps state to color: AVAILABLE=green, DIALING=blue, etc. |
| `CallMetrics` | `calls: CallMetrics` | Grid of stat cards (Initiated, Connected, Failed, Completed) |
| `MetricCard` | `label`, `value`, `trend` | shadcn/ui Card with large number + trend arrow |
| `PacingChart` | `history: PacingHistory[]` | Recharts LineChart: dial_count, answer_rate, provider_health over time |
| `SafetyLog` | `decisions: SafetyDecision[]` | Scrollable log; each row: timestamp + action badge + reason |
| `ProviderHealth` | `providers: ProviderStatus[]` | Circular health indicators for Provider A + B |
| `FailureScenarios` | — | 5 buttons (shadcn/ui Button variants); call POST endpoints on click; show toast on result |
| `useWebSocket` | `url: string` | Opens WS connection, auto-reconnects on disconnect, returns latest message |
| `useMetrics` | — | Consumes useWebSocket, manages metrics state + history ring buffer |
