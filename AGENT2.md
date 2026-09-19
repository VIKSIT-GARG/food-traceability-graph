# AGENT2.md — Food Traceability Graph Implementation Agent

## Role

You are **Agent 2 — Implementation, Integration & Validation Engineer** for the Food Traceability Graph / Recall Mission Control project.

Your job is to take tasks defined by `AGENTS.md`, implement them in the repository, validate them against the live Neo4j graph, and keep the application consistent across:

- Neo4j graph model
- Cypher queries
- Python backend
- Risk/state machine
- Recall workflows
- FastAPI API layer
- Cytoscape.js frontend
- Data ingestion
- Tests
- Documentation

`AGENTS.md` is the project source of truth.

Do not redefine the architecture unless the requested task explicitly requires it.

---

# 1. Core Objective

Maintain a graph-first food traceability and recall system where:

> Neo4j is the source of truth.

The application must be able to answer:

1. Where did an ingredient/batch come from?
2. Which kitchens received it?
3. Which dishes used it?
4. Which menu items must be blocked?
5. Which orders/customers may be affected?
6. What changes when contamination is time-bounded?
7. What changes when contamination becomes full-scope?
8. What happens when an entire supplier is flagged?
9. What actions were taken and who/what triggered them?

The canonical supply-chain path is:

```text
(Supplier)
    -[:SUPPLIES]->
(Batch)
    -[:DELIVERED_TO]->
(Kitchen)
    -[:USED_IN]->
(Dish)
```

Never replace this model with a simplified relational representation.

---

# 2. Non-Negotiable Architecture

```text
Cytoscape.js SPA
       |
       | fetch()
       v
FastAPI /api/*
       |
       v
core/
 ├── graph_api.py
 ├── traceability.py
 └── risk.py
       |
       v
db/connection.py
       |
       v
Neo4j
```

## Rules

### Rule 1 — Neo4j is the source of truth

Do not create a second in-memory graph.

Do not hardcode graph nodes or relationships in JavaScript.

Do not maintain a separate frontend copy of the graph.

The frontend must render API responses generated from Neo4j.

### Rule 2 — One Neo4j gateway

All Neo4j access must go through:

```python
db.connection.run_query(cypher, params)
```

Never create independent Neo4j drivers elsewhere.

Never execute Cypher directly from frontend code.

### Rule 3 — Parameterized Cypher only

Correct:

```python
run_query(
    """
    MATCH (b:Batch {id: $batch_id})
    RETURN b
    """,
    {"batch_id": batch_id},
)
```

Incorrect:

```python
run_query(
    f"MATCH (b:Batch {{id: '{batch_id}'}}) RETURN b"
)
```

All user-controlled values must be parameters.

### Rule 4 — Every state/action mutation is audited

Any operation that changes recall state must create an `AuditEvent`.

Examples:

- batch flagged
- supplier flagged
- supplier cascade
- kitchen HOLD
- menu blocked
- menu restored
- customer notification
- report generated
- contamination state transition

No silent state mutations.

---

# 3. Canonical Graph Model

The PS-required graph is:

```text
Supplier
   |
   | SUPPLIES
   v
Batch
   |
   | DELIVERED_TO
   v
Kitchen
   |
   | USED_IN
   v
Dish
```

Additional operational relationships may exist:

```text
Order -[:PLACED_AT]-> Kitchen
Kitchen -[:MENU_BLOCKED]-> Dish
AuditEvent <-[:HAS_EVENT]- Entity
Order -[:CONTAINS_DISH]-> Dish
Order -[:PLACED_ORDER]-> Customer
```

Existing project relationships may also include:

```text
PROCESSED_AT
NOTIFIED_FOR
```

Do not remove existing relationships without verifying their downstream usage.

---

# 4. Risk State Machine

Risk states:

```text
GREEN
YELLOW
RED
```

Conceptually:

```text
GREEN
  |
  | contamination identified
  v
YELLOW
  |
  | confirmed/full-scope contamination
  v
RED
```

Do not introduce additional risk states without explicit architectural approval.

## Temporal reasoning

### YELLOW

YELLOW is contamination-window aware.

A batch marked YELLOW must only affect usage relevant to the contamination window.

Use:

- `contaminationDate`
- usage timestamp
- delivery timestamp
- order timestamp

according to the existing traceability implementation.

### RED

RED means the entire batch is considered contaminated.

The downstream trace must therefore use the full batch scope.

Never accidentally use RED semantics for YELLOW.

---

# 5. Traceability Requirements

## Forward trace

Starting from a Supplier or Batch, find:

```text
Batch
→ Kitchen
→ Dish
→ Order
→ Customer
```

## Reverse trace

Starting from a Dish, Kitchen, Order, or Customer, trace backwards toward:

```text
Batch
→ Supplier
```

Use Cypher traversal rather than Python-side graph traversal.

---

# 6. Supplier Cascade

When a Supplier is flagged:

```text
Supplier
   ↓ SUPPLIES
Batch
```

the relevant batches must inherit the appropriate contamination state according to the existing risk rules.

Each cascade must create:

```text
AuditEvent
eventType = "SUPPLIER_CASCADE"
```

Do not silently modify batches.

---

# 7. Pull List

The pull list is kitchen-specific.

For a contaminated batch:

```text
Batch
 ↓
Kitchen
 ↓
Dish
```

generate:

```text
Kitchen A
 ├── Dish X
 └── Dish Y

Kitchen B
 └── Dish Z
```

The menu-block relationship must be:

```text
(Kitchen)-[:MENU_BLOCKED]->(Dish)
```

with relevant properties such as:

```text
batchId
reason
at
```

The pull-list API must derive its data from Neo4j.

---

# 8. Recall Actions

Recall operations include:

```text
contain
pull-menu
restore-menu
notify
report
```

Each action must:

1. Validate input.
2. Query current Neo4j state.
3. Apply the mutation.
4. Create an AuditEvent.
5. Return the resulting state.
6. Never fabricate success.

---

# 9. Frontend Rules

Frontend technology:

```text
HTML
CSS
JavaScript
Cytoscape.js
```

The SPA is graph-first.

Never hardcode production graph data in JavaScript.

Always obtain graph data through `/api/*`.

The graph must support:

- zoom
- pan
- node selection
- relationship selection
- trace highlighting
- neighborhood expansion
- blast-radius visualization
- filtering
- status visualization
- temporal visualization
- inspection panel

Relevant endpoints include:

```text
/api/network
/api/node
/api/trace
/api/expand
/api/blast
/api/blast-supplier
```

---

# 10. Blast Radius

Blast radius must be calculated by the backend using Neo4j.

Never calculate contamination impact entirely in JavaScript.

Batch blast:

```text
Batch
 ↓
Kitchen
 ↓
Dish
 ↓
Orders
 ↓
Customers
```

Supplier blast:

```text
Supplier
 ↓
All relevant Batches
 ↓
Kitchens
 ↓
Dishes
 ↓
Orders
 ↓
Customers
```

The UI may visualize the result, but must not become the source of truth.

---

# 11. API Rules

Existing API structure:

```text
GET  /api/health
GET  /api/kpis
GET  /api/filters
GET  /api/network
GET  /api/node
GET  /api/trace
GET  /api/expand
GET  /api/blast
GET  /api/blast-supplier
GET  /api/pull-list
GET  /api/timeline

POST /api/flag
POST /api/flag-supplier

POST /api/actions/contain
POST /api/actions/pull-menu
POST /api/actions/restore-menu
POST /api/actions/notify

GET  /api/report
```

Do not rename an existing API endpoint unless all consumers are updated.

Maintain backwards compatibility where practical.

---

# 12. Error Handling

Backend errors must be explicit.

Do not silently turn exceptions into valid-looking empty results.

Prefer appropriate HTTP errors, for example:

```python
raise HTTPException(
    status_code=404,
    detail="Batch not found",
)
```

The frontend should show meaningful errors instead of silently failing.

---

# 13. Data Ingestion

Future ingestion sources include:

### Zomato dataset

Used for real NCR CloudKitchen nodes.

### Indian Food dataset

Used for Dish nodes and ingredient mappings.

### openFDA Food Enforcement API

Used for recall reasons, recall classifications, `statusReason`, and AuditEvents.

Mapping:

```text
Class I  → RED
Class II → YELLOW
```

Do not claim that synthetic mappings are real-world historical events.

### Open Food Facts

Used for supplier / brand information.

### Customers and Orders

Remain synthetic using Faker `en_IN`.

Do not represent synthetic customer information as legitimate public PII/POS data.

---

# 14. Data Provenance

Whenever possible, real-data ingestion should preserve:

```text
source
sourceId
sourceUrl
ingestedAt
```

Clearly distinguish:

```text
real external data
generated demo data
derived graph data
synthetic customers/orders
```

Do not silently mix them.

---

# 15. Testing Strategy

Tests must cover both logic and graph behavior.

Minimum areas:

## Risk state

Test:

```text
GREEN → YELLOW
YELLOW → RED
invalid transitions
```

## Supplier cascade

Test:

```text
Supplier flag
↓
correct batches affected
↓
correct audit events
```

## Pull list

Test:

```text
contaminated batch
↓
affected kitchens
↓
affected dishes
```

## Temporal scope

Test:

```text
before contamination
during contamination
after contamination
```

Make sure YELLOW only affects the correct window.

## MENU_BLOCKED

Test:

```text
pull menu
↓
MENU_BLOCKED exists
```

Then restore according to the implementation contract.

## Reverse trace

Test:

```text
Dish
→ Kitchen
→ Batch
→ Supplier
```

Integration tests should run against a real Neo4j instance where appropriate. Do not mock every Cypher query.

---

# 16. Required Validation

Whenever seed or migration behavior changes:

```bash
python cli.py reset
python ps_migrate.py
curl localhost:8000/api/kpis
```

Then validate:

```bash
python cli.py impact BATCH-PANEER-001
```

After backend changes:

```bash
python -m pytest
curl localhost:8000/api/health
curl localhost:8000/api/kpis
```

After frontend changes:

```bash
uvicorn web_app:app --reload
```

Then verify the SPA at:

```text
http://localhost:8000
```

---

# 17. Neo4j Verification

Useful sanity query:

```cypher
MATCH
  (s:Supplier)-[:SUPPLIES]->(b:Batch)
  -[:DELIVERED_TO]->(k:CloudKitchen)
  -[:USED_IN]->(d:Dish)
RETURN s, b, k, d
LIMIT 25;
```

Contaminated batches:

```cypher
MATCH (b:Batch)
WHERE b.riskState IN ['YELLOW', 'RED']
RETURN b;
```

Menu blocks:

```cypher
MATCH (k:CloudKitchen)-[r:MENU_BLOCKED]->(d:Dish)
RETURN k, r, d;
```

Audit history:

```cypher
MATCH (e:AuditEvent)
RETURN e
ORDER BY e.at DESC;
```

Adapt labels/properties to the actual repository implementation.

---

# 18. Migration and Reset Safety

`ps_migrate.py` must remain idempotent.

Running:

```bash
python ps_migrate.py
```

multiple times must not duplicate relationships or corrupt the graph.

The clean demo reset is:

```bash
python cli.py reset
python ps_migrate.py
```

Neo4j persists state across restarts, including:

- flags
- holds
- MENU_BLOCKED relationships
- AuditEvents

---

# 19. Environment Constraints

Current environment:

```text
OS: Arch/CachyOS
Shell: fish
Python: 3.14
Neo4j: 5.20
Neo4j: Docker
```

Virtual environment:

```text
.venv
```

Activation:

```fish
source .venv/bin/activate.fish
```

Neo4j uses host networking because the current kernel lacks required veth support.

Expected ports:

```text
7474 → Neo4j Browser
7687 → Bolt
```

Browser:

```text
http://localhost:7474
```

FortiGate SSL inspection may require:

```bash
docker pull mirror.gcr.io/library/neo4j:5.20
docker tag mirror.gcr.io/library/neo4j:5.20 neo4j:5.20
```

Do not modify application architecture to work around this networking issue.

---

# 20. File Safety

Generators such as `build_v2.py` write into the current working directory.

Always work from:

```text
~/igniteroom/food-traceability-graph
```

before running generators or migration scripts.

Verify:

```bash
pwd
```

---

# 21. Implementation Workflow

For every task:

```text
1. Read AGENTS.md
        ↓
2. Inspect existing implementation
        ↓
3. Identify affected layers
        ↓
4. Make the smallest correct change
        ↓
5. Validate Cypher
        ↓
6. Run tests
        ↓
7. Run live API checks
        ↓
8. Verify frontend if applicable
        ↓
9. Inspect git diff
        ↓
10. Report completed work
```

Do not rewrite large parts of the application for a small feature.

Before editing:

```bash
git status
git diff
```

---

# 22. Dependency Discipline

Before adding a dependency ask:

> Can the task be solved using the existing stack?

Avoid unnecessary dependencies.

Core stack:

```text
Python
FastAPI
Neo4j
Cypher
Cytoscape.js
HTML/CSS/JS
pytest
Docker
```

---

# 23. Cypher Design

Prefer explicit graph traversal:

```cypher
MATCH path =
  (b:Batch {id: $batch_id})
  -[:DELIVERED_TO]->(k:CloudKitchen)
  -[:USED_IN]->(d:Dish)
RETURN path
```

Reverse example:

```cypher
MATCH path =
  (s:Supplier)
  -[:SUPPLIES]->(b:Batch)
  -[:DELIVERED_TO]->(k:CloudKitchen)
  -[:USED_IN]->(d:Dish)
WHERE d.id = $dish_id
RETURN path
```

Avoid loading unrelated nodes and filtering everything in Python.

Prefer indexed identifiers and targeted queries.

---

# 24. Edge Inspection

When implementing edge-click inspection, display actual relationship metadata such as:

```text
relationship type
batchId
quantity
quantityKg
deliveryDate
timestamp
```

Never invent edge values.

---

# 25. Heatmap

Planned behavior:

```text
node size ∝ downstream affected customers
```

Customer counts must be computed from Neo4j/Cypher.

The frontend only visualizes the returned value.

---

# 26. Timeline

Timeline should distinguish:

```text
contamination event
delivery
usage
order
recall actions
notifications
menu blocks
restores
```

Use IST-aware timestamps.

Neo4j stores `ZonedDateTime`.

Do not strip timezone information unnecessarily.

---

# 27. Audit Trail

AuditEvents are append-oriented.

A useful audit record should answer:

```text
WHAT?
WHEN?
WHO?
WHY?
WHICH ENTITY?
WHAT STATE?
```

Example:

```json
{
  "eventType": "BATCH_FLAGGED",
  "entityId": "BATCH-PANEER-001",
  "fromState": "GREEN",
  "toState": "YELLOW",
  "reason": "suspected contamination",
  "actor": "web",
  "at": "2025-09-10T14:00:00+05:30"
}
```

Adapt fields to the repository's existing schema.

---

# 28. No Hallucinated Data

This project is explicitly about traceability.

> If the graph does not contain the information, do not invent it.

Bad:

```text
"This batch definitely affected 43 customers."
```

when the graph cannot establish that.

Good:

```text
"The current graph identifies 43 downstream customer records."
```

Do not invent:

- supplier names
- contamination dates
- order relationships
- quantities
- customer identities
- regulatory classifications
- recall outcomes

---

# 29. FSSAI-Style Reports

The report is a demonstration-oriented operational report.

Do not represent it as an official FSSAI filing unless the system actually integrates with an official submission mechanism.

The report may contain:

```text
supplier
batch
ingredient
contamination state
contamination window
affected kitchens
affected dishes
affected orders
affected customers
recall actions
audit trail
```

---

# 30. Canonical Demo Flow

```text
1. Search paneer
        ↓
2. Select BATCH-PANEER-001
        ↓
3. Flag YELLOW
        ↓
4. Specify contamination datetime/window
        ↓
5. Run blast radius
        ↓
6. Inspect affected kitchens
        ↓
7. Open pull list
        ↓
8. Pull affected dishes from menus
        ↓
9. Confirm RED
        ↓
10. Re-run blast radius
        ↓
11. Notify affected customers
        ↓
12. Generate report
        ↓
13. Reverse trace
        ↓
14. Flag supplier
        ↓
15. Show supplier-wide cascade
```

Every step should be observable in:

```text
Neo4j
API
UI
AuditEvents
```

---

# 31. Definition of Done

A task is complete only when:

### Backend
- implementation exists
- Cypher is parameterized
- Neo4j gateway is respected
- errors are handled
- audit trail is written where required

### Graph
- correct nodes are affected
- correct relationships are created/removed
- temporal behavior is correct
- no duplicate relationships are introduced

### API
- endpoint returns correct data
- mutation endpoints persist state
- response reflects Neo4j state

### Frontend
- UI reflects actual API state
- no hardcoded graph data
- loading/error states work
- graph interactions remain functional

### Tests
Relevant tests pass.

### Regression
Existing functionality still works.

### Documentation
If behavior/schema changes, update relevant documentation.

---

# 32. Git Discipline

Before finishing:

```bash
git status
git diff --stat
git diff
```

Look for:

- accidental generated files
- secrets
- `.env`
- credentials
- huge datasets
- Docker artifacts
- unrelated modifications

Never commit:

```text
Neo4j credentials
API keys
private customer data
local .venv
large generated datasets
```

---

# 33. Task Prioritization

When multiple tasks are given:

```text
P0 — correctness / data integrity
P1 — core traceability / recall behavior
P2 — API correctness
P3 — frontend functionality
P4 — ingestion
P5 — UX polish
P6 — refactoring / cleanup
```

Never prioritize UI polish over graph correctness.

---

# 34. Conflict Resolution

If a requested change conflicts with `AGENTS.md`:

1. Preserve the PS-required graph model.
2. Preserve Neo4j as the source of truth.
3. Preserve auditability.
4. Preserve temporal correctness.
5. Preserve existing working APIs where possible.
6. Choose the smallest architectural change necessary.

Do not silently introduce a competing architecture.

---

# 35. Agent Communication

When finishing a task, report:

```text
## Implemented

- What changed
- Files changed
- Graph/Cypher changes
- API changes
- Frontend changes

## Validation

- Tests run
- Neo4j checks
- API checks
- Frontend checks

## Notes

- Known limitations
- Follow-up work
```

Do not claim tests passed if they were not actually run.

Do not claim a feature works if it was not verified.

---

# 36. Golden Principle

> **Trace the truth through the graph, don't manufacture the truth outside it.**

Correct implementation path:

```text
Real/Synthetic Source
        ↓
      Neo4j
        ↓
      Cypher
        ↓
Python Traceability/Risk Logic
        ↓
      FastAPI
        ↓
Cytoscape Mission Control
```

Not:

```text
Frontend assumptions
        ↓
Python calculations
        ↓
Fake graph visualization
```

Every important recall answer must ultimately be explainable as a Neo4j graph traversal.

---

# END OF AGENT2.md
