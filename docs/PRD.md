# SmartDialer — Product Requirements Document

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-08-19 |
| Status | Draft |
| Author | SmartDialer Team |

---

## 1. Problem Statement

Collections agents in call centers spend significant time:
- Waiting for calls to connect
- Dialing numbers that don't answer
- Sitting idle between completed calls

A smarter dialing system should automate call initiation, manage agent allocation efficiently, and ensure that no compliance boundaries are crossed — particularly around abandoned connected calls, which can become regulatory violations.

---

## 2. Goals and Non-Goals

### Goals
- Improve agent utilization compared to manual dialing
- Support both Progressive (safe) and Predictive (optimized) dialing modes
- Enforce hard safety limits that the pacing engine cannot bypass
- Handle distributed worker failures, provider outages, and duplicate events gracefully
- Be explainable: every decision the system makes should be traceable and auditable

### Non-Goals
- Production-grade telecom integration (mocked for this prototype)
- ML/AI-based prediction (rule-based statistical approach is sufficient)
- Multi-tenant SaaS architecture
- User authentication and authorization
- Billing or call recording features

---

## 3. User Stories

### As a Collections Agent
- **US-001**: I want to be automatically connected to a borrower when I become available, so I don't waste time manually dialing.
- **US-002**: I want my status to be accurately tracked (Available, Dialing, Connected, Wrap-Up) so the system allocates calls correctly.
- **US-003**: I want the system to handle call failures gracefully so I'm not stuck in a broken state.

### As a Campaign Manager
- **US-004**: I want to configure a campaign with a borrower list and choose Progressive or Predictive mode.
- **US-005**: I want to see real-time metrics — agent utilization, calls initiated, connected, failed — on a dashboard.
- **US-006**: I want to switch between Progressive and Predictive modes during a live campaign.
- **US-007**: I want to see why the system made specific pacing decisions (e.g., "initiated 17 calls because answer rate is 62% and 12 agents are available").

### As a Compliance Officer
- **US-008**: I want a guarantee that abandoned call rate never exceeds 3%, enforced by a system-level control.
- **US-009**: I want the predictive algorithm to have no direct access to the telecom provider — all calls must go through a Safety Controller.
- **US-010**: I want every call state transition logged for audit purposes.

---

## 4. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | System shall support Progressive dialing: max concurrent calls ≤ available agents | Must Have |
| FR-002 | System shall support Predictive dialing: initiate calls ahead of agent availability based on pacing algorithm | Must Have |
| FR-003 | Pacing Engine shall never directly initiate calls; all requests must route through Safety Controller | Must Have |
| FR-004 | Safety Controller shall support 4 decisions: Approve, Reduce count, Reject, Fallback to Progressive | Must Have |
| FR-005 | Agent state machine shall support: OFFLINE, AVAILABLE, RESERVED, DIALING, CONNECTED, WRAP_UP, PAUSED | Must Have |
| FR-006 | Two workers must never be able to reserve the same agent (enforced at DB level) | Must Have |
| FR-007 | Call state machine shall support: QUEUED, RESERVED, INITIATED, RINGING, ANSWERED, CONNECTED, COMPLETED, FAILED, CANCELLED | Must Have |
| FR-008 | Duplicate provider events must be handled idempotently (no double state transitions) | Must Have |
| FR-009 | Out-of-order provider events must be rejected gracefully (state machine guards) | Must Have |
| FR-010 | System shall provide Mock Provider A: fast, reliable, low failure rate | Must Have |
| FR-011 | System shall provide Mock Provider B: slow, timeout-prone, duplicate and out-of-order events | Must Have |
| FR-012 | System shall recover from worker crashes: stale reservations released, calls requeued | Must Have |
| FR-013 | System shall degrade gracefully during provider outages: pause new calls, preserve existing calls | Must Have |
| FR-014 | System shall provide a simulation runner with configurable agents, borrowers, provider, and mode | Should Have |
| FR-015 | System shall provide a React dashboard with real-time metrics via WebSocket | Should Have |

---

## 5. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-001 | **Performance** | Dashboard metrics refresh ≤ 1 second latency |
| NFR-002 | **Reliability** | System recovers from any single worker crash within 30 seconds |
| NFR-003 | **Correctness** | Zero duplicate agent reservations under any concurrency scenario |
| NFR-004 | **Observability** | Every pacing decision, safety controller action, and state transition is logged |
| NFR-005 | **Portability** | Full stack runs with single `docker compose up --build` command |
| NFR-006 | **Testability** | Core logic (state machines, pacing, safety) achieves ≥ 80% unit test coverage |
| NFR-007 | **Scalability** | Architecture can explain bottlenecks at 100 → 1,000 → 10,000 agents |
| NFR-008 | **Maintainability** | All modules documented with docstrings; ADR explains key decisions |

---

## 6. Constraints

- Must run locally via Docker Compose without external services
- No real telecom provider integration (Plivo or similar)
- Target timebox: 4–6 hours of core implementation per sprint (5 sprints total)
- Language: Python 3.11 (backend), React 18 (frontend)
- No ML models — rule-based statistical approach for predictive pacing

---

## 7. Success Metrics

| Metric | Target |
|---|---|
| Agent utilization (Progressive) | ≥ 85% of agents active during campaign |
| Agent utilization (Predictive) | ≥ 92% of agents active during campaign |
| Abandoned call rate | < 3% enforced by Safety Controller |
| Duplicate reservation rate | 0% — verified by concurrency tests |
| Worker crash recovery time | < 30 seconds |
| All 5 failure scenarios | Demonstrated and logged correctly |
| `docker compose up` → working | First try, zero manual steps |

---

## 8. Out of Scope

- Real telephony (SIP, WebRTC, Plivo, Twilio)
- Machine learning / AI models
- Multi-campaign management
- User authentication / RBAC
- Production deployment (Kubernetes, cloud)
- Call recording / transcription
- CRM integration

---

## 9. Open Questions

| Question | Resolution |
|---|---|
| Should we use Plivo for real calls? | No — fully mocked. Reduces complexity, allows full control of provider behavior. |
| Progressive or Predictive — which to prioritize? | Both implemented. Progressive first (Sprint 2), Predictive added (Sprint 3). |
| What's the abandoned call threshold? | 3% — industry standard for compliance. Enforced by Safety Controller. |
| Redis vs PostgreSQL for state? | PostgreSQL for durable state (agent, call records). Redis for fast ephemeral state (pub/sub, rate tracking). |

---

## 10. Approval

| Role | Name | Status |
|---|---|---|
| Product Owner | SmartDialer Team | Approved |
| Tech Lead | SmartDialer Team | Approved |
| QA Lead | SmartDialer Team | Pending |
