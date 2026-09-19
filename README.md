# 🍲 Food Traceability Graph — Recall Mission Control

> **Neo4j-Powered Supply-Chain Traceability & Recall Intelligence Engine**  
> *Engineered for Cloud Kitchen Networks across Delhi NCR (Gurugram · Noida · Delhi)*

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Render_Cloud-0ea5e9?style=for-the-badge)](https://food-traceability-demo.onrender.com)
[![Neo4j 5](https://img.shields.io/badge/Neo4j-5.20_Graph_DB-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Cytoscape.js](https://img.shields.io/badge/Cytoscape.js-3.30_SPA-f59e0b?style=for-the-badge)](https://js.cytoscape.org/)
[![Python Tests](https://img.shields.io/badge/Pytest-32_Passed-10b981?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-8b5cf6?style=for-the-badge)](LICENSE)

---

### 🚀 Instant Access
- **Live Demo (Zero Setup):** [https://food-traceability-demo.onrender.com](https://food-traceability-demo.onrender.com)  
  *(Hosted on Render Free Tier. If idle, first wake-up takes ~50s while the container starts)*
- **GitHub Repository:** [https://github.com/VIKSIT-GARG/food-traceability-graph](https://github.com/VIKSIT-GARG/food-traceability-graph)

---

## 1. The Problem
**Neo4j Hackathon — Theme: Logistics & Supply Chain Transparency**

With the explosive expansion of multi-brand cloud kitchens across Gurugram, Noida, and Delhi, tracking ingredient provenance is essential for food safety and health regulations. When a specific supplier batch—such as a paneer batch—is flagged as spoiled or contaminated with microbial pathogens, relational/flat databases struggle to answer multi-hop containment questions in seconds:

1. **Which cloud kitchens** received this batch?
2. **Which specific dishes / recipes** used this batch in their preparation?
3. **Which customer orders** contained those dishes?
4. **Which consumers** must be alerted for safety outreach?

### The Core Objective
Build a connected **Food Traceability Graph** representing the physical food supply chain:

```text
(Supplier) ──[:SUPPLIES]──► (Batch) ──[:DELIVERED_TO]──► (CloudKitchen) ──[:USED_IN]──► (Dish)
                                                                ▲
                                                                │ [:PLACED_AT]
                                                            (Order) ──[:CONTAINS_DISH]──► (Dish)
                                                                ▲
                                                                │ [:PLACED_ORDER]
                                                           (Customer)
```

**What We Built:** An operations mission control where an operator flags a **Supplier** or **Batch** as contaminated (`GREEN` → `YELLOW` → `RED`). Cypher traverses the downstream dependencies in milliseconds, outputting:
- Per-kitchen physical quarantine pull lists.
- One-click menu blacklisting (`MENU_BLOCKED` edges on POS).
- Downstream affected orders and customer contact lists.
- Full chronological audit logs.
- FSSAI / FoSCoS digital recall compliance dossiers (JSON/PDF).

---

## 2. What Makes This Different

| Feature | Food Traceability Graph | Traditional Flat / SQL Systems |
|---|---|---|
| **Primary Interface** | **Graph-First**: Interactive Cytoscape.js visual canvas. Neo4j is the single source of truth; every node and relationship is queried live via Cypher. | Static relational tables or disconnected summary dashboards. |
| **Domain Model** | **Kitchen is the Cook**: `(Kitchen)-[:USED_IN {batchId, timestamp, qtyKg}]->(Dish)` and `(Order)-[:PLACED_AT]->(Kitchen)`. | Generic foreign keys with loss of kitchen prep context. |
| **Temporal Reasoning** | **Contamination Windows**: Flagging `YELLOW` triggers a timestamp window (`contamination_date`). Only usages, deliveries, and orders processed during/after the window are flagged. `RED` initiates full-batch recall. | Recalls entire historical inventory indiscriminately, causing massive food waste. |
| **Supplier Cascade** | **Network-Wide Blast**: Flagging a supplier cascades down all active batches with individual audit logging, quantifying the full enterprise blast radius. | Manual batch-by-batch investigation across multiple ERP tables. |
| **Actionable Recall** | **Immediate Containment**: Per-kitchen inventory pull lists, automated `MENU_BLOCKED` edge injection, kitchen hold status toggling, and customer outreach tracking. | Read-only reports with no direct operational containment triggers. |
| **Workstation Query Console** | **Dual Engine + Guardrails**: Embedded bottom query console supporting 3-layer guardrailed read-only Cypher + instant natural operator commands (`contaminated`, `blast`, `trace`). | Separate DB administration client required. |
| **Design System** | **Cold-Chain & Forensic Theme**: Clean, authentic dark palette grounded in cold storage monitoring and food safety laboratories (built with `frontend-design` principles). | Generic cyberpunk neon or standard bootstrap templates. |

---

## 3. System Architecture

```text
                                  ┌──────────────────────────────────────────────┐
                                  │           GRAPH-FIRST FRONTEND (SPA)         │
                                  │   Cytoscape.js Graph View  ·  Operations HUD  │
                                  │   Interactive Bottom Query & Cypher Console  │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                               JSON API (/api/*)
                                                         │
                        ┌────────────────────────────────┴────────────────────────────────┐
                        ▼                                                                 ▼
           ┌─────────────────────────────┐                                   ┌─────────────────────────────┐
           │    NEO4J MODE (web_app.py)   │                                   │   DEMO MODE (demo_server.py)│
           │  FastAPI + Official Driver  │                                   │  FastAPI + In-Memory Graph  │
           └──────────────┬──────────────┘                                   └──────────────┬──────────────┘
                          │                                                                 │
                          ▼                                                                 │
           ┌─────────────────────────────┐                                                  │
           │      CORE LOGIC ENGINE      │                                                  │
           │  • core/graph_api.py        │◄─────────────────────────────────────────────────┘
           │  • core/traceability.py     │          Identical API Contracts
           │  • core/risk.py             │
           │  • core/query_agent.py      │ (Read-only Cypher with Layered Guardrails)
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │   db/connection.py          │  Parameterised Cypher & Thread-Safe Driver
           └──────────────┬──────────────┘
                          │
                          ▼
           ┌─────────────────────────────┐
           │     NEO4J 5 GRAPH DATABASE  │
           │  Supplier · Batch · Kitchen │
           │  Facility · Dish · Customer │
           └─────────────────────────────┘
```

---

## 4. Quick Start

### ⚡ Option A: Zero Setup / Without Docker (Instant Demo)
*Ideal for quick evaluation, judges, and machines without Docker installed.*

```bash
# 1. Clone repository
git clone https://github.com/VIKSIT-GARG/food-traceability-graph.git
cd food-traceability-graph

# 2. Install lightweight demo dependencies
pip install -r requirements-demo.txt

# 3. Launch standalone in-memory demo server
python demo_server.py
```
👉 Open your browser at **`http://localhost:8000`**  
*Reset demo state anytime via:* `curl -X POST http://localhost:8000/api/demo/reset`

---

### 🐳 Option B: With Docker (Full Production Engine + Live Neo4j)
*Connects to a real Neo4j 5 instance with persistent graph mutations, read-only Cypher console, and full audit logs.*

```bash
# 1. Start Neo4j 5 container
docker compose up -d

# 2. Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Seed database and run canonical schema migration
python cli.py reset
python ps_migrate.py    # Migrates canonical edges to the problem-statement schema

# 5. Start FastAPI application
uvicorn web_app:app --reload --port 8000
```
👉 Open your browser at **`http://localhost:8000`**  
👉 Neo4j Browser available at **`http://localhost:7474`** (`neo4j` / `tracegraph`)

> [!IMPORTANT]
> Always execute `python ps_migrate.py` after `python cli.py reset`. This migrates the canonical seed dataset into problem-statement relationships: `(:Supplier)-[:SUPPLIES]->(:Batch)` and `(:CloudKitchen)-[:USED_IN]->(:Dish)`.

---

### ☁️ Option B2: Neo4j Desktop or Neo4j Aura Cloud
The application communicates via standard Bolt protocol:
- **Neo4j Desktop:** Create a local DBMS (5.x) and set `NEO4J_URI=bolt://localhost:7687` and `NEO4J_PASSWORD` in `.env`.
- **Neo4j Aura Free:** Create a free cloud database instance, then set:
  ```dotenv
  NEO4J_URI=neo4j+s://<db-id>.databases.neo4j.io
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=<your-aura-password>
  ```
- Initialize and launch:
  ```bash
  pip install -r requirements.txt
  python cli.py reset && python ps_migrate.py
  uvicorn web_app:app --reload
  ```

---

### 🚀 Option C: Deployed Cloud Instance (Render)
The repository contains a fully configured [`render.yaml`](render.yaml) Blueprint:
1. Push repo to GitHub.
2. Log into [render.com](https://render.com) → **New +** → **Blueprint** → Select repository.
3. Render installs `requirements-demo.txt` and runs `demo_server.py`.
4. Automated deployment with continuous `/api/health` checks.

---

## 5. Environment Configuration (`.env`)

```dotenv
# Neo4j Database Connection
NEO4J_URI=bolt://localhost:7687          # Use neo4j+s:// for Aura Cloud
NEO4J_USER=neo4j
NEO4J_PASSWORD=tracegraph
NEO4J_DATABASE=neo4j

# Application Timezone
APP_TIMEZONE=Asia/Kolkata                # All audit timestamps are in IST
```
*(Demo mode completely ignores database environment variables)*

---

## 6. Using the Application

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TRACE-NCR // RECALL MISSION CONTROL           [🕸 Graph View] [📊 Dashboard]    ● LIVE TELEMETRY│
├───────────────────┬────────────────────────────────────────────────────────────────────────────┤
│ SEARCH & FILTERS  │                                                                            │
│ 🔍 batch/dish...   │                                                                            │
│ Supplier: (any)   │                            CYTOSCAPE GRAPH CANVAS                          │
│ Kitchen: (any)    │                                                                            │
│ Risk Level:       │         (Supplier) ──► (Batch 🔴) ──► (Kitchen) ──► (Dish) ──► (Order)      │
│ [x] 🟢 [x] 🟡 [x] 🔴│                                                                            │
│                   │                                                                            │
├───────────────────┴────────────────────────────────────────────────────────────────────────────┤
│ >_ Query & Cypher Console   [>_ Cypher Engine] [⌘ Commands]   Preset: [ Paneer Recall... ▼ ]  │
│  MATCH (s:Supplier)-[:SUPPLIES]->(b:Batch {id: ...})  │  Results (25 rows in 12ms) [JSON] [CSV]│
│  -[:DELIVERED_TO]->(k:CloudKitchen)-[:USED_IN]->(d)  ├────────────────────────────────────────┤
│  RETURN s.name, b.id, b.status, k.name, d.name        │  # | Supplier | Batch | Kitchen | Dish │
│  [⚡ Paneer Corridor] [🔴 RED Kitchens] [👤 Customers] │  1 | DairyPure| BATCH | SpiceHub| Paneer...
│  Ctrl+Enter to execute                [▶ Run Query]   │  (Click any Entity ID to jump on graph)│
└───────────────────────────────────────────────────────┴────────────────────────────────────────┘
```

### 6.1 Dual Views
- **🕸 Graph View (Default):** Interactive Cytoscape.js exploration stage with real-time topological layouts, corridor highlights, blast radii, and the bottom query workstation.
- **📊 Operations Dashboard:** Operational mission control displaying fleet KPI cards, contamination watchlist, per-kitchen live inventory quarantine table, customer outreach records, and full audit stream.

### 6.2 Graph Interactions
- **Click Node:** Immediately illuminates its full downstream delivery & usage path in amber (`#d97706`) and opens the inspector panel.
- **Shift + Click Node:** Traverses upstream to original raw ingredient batches and supplier farms.
- **Select Batch:** Reveals recall controls: one-click **"Pull from menu"** / **"Restore"**, and live per-kitchen status chips (`LIVE` ➔ `PULLED`).
- **Select Supplier:** Inspect aggregated batch portfolios, trigger cascade contamination flagging, or calculate network-wide blast impact.
- **💥 Recall Impact Button:** Illuminates the full blast radius in biohazard crimson (`#dc2626`), dims unrelated entities, and triggers the emergency recall alert banner.
- **🕰 Timeline Drawer:** Displays batch audit history with visual markers distinguishing historical safe processing from events inside the contamination window.
- **📋 Kitchen Pull List Drawer:** Generates kitchen-specific quarantine lists specifying exact menu items to remove.

### 6.3 Fully Fledged Bottom Query Console
Anchored at the bottom with a 290px viewable workspace (expandable to 460px or collapsible to 38px):
- **`>_ Cypher Engine`**: Executes arbitrary read-only Cypher queries directly against Neo4j with **3-Layer Security Guardrails**:
  1. *Regex Denylist*: Destructive statements (`CREATE`, `MERGE`, `DELETE`, `SET`, `DROP`, `CALL`, `LOAD CSV`, `FOREACH`) are strictly rejected.
  2. *Structure Verification*: Enforces single statements, mandatory `RETURN`, and whitelisted graph labels/relationship types.
  3. *Neo4j READ Session*: Executed inside a read-access transaction session with a 5.0s timeout and auto `LIMIT 200`.
- **`⌘ Commands Mode`**: High-speed operator shortcuts:
  - `contaminated` — Highlights all active flagged batches & suppliers across NCR.
  - `trace <ID>` or `trace up <ID>` — Traces corridor paths and outputs structured hop tables.
  - `blast <ID>` — Detonates recall blast radius and lists exposure categories.
  - `pull list [ID]` — Fetches live kitchen quarantine lists with one-click menu block.
  - `supplier <name>` / `kitchen <name>` / `orders on` — Real-time filter manipulation.
- **High-Impact Query Presets**:
  1. *Paneer Recall Corridor* — Supplier to batch to kitchen to affected dish.
  2. *Cloud Kitchens Holding RED Batches* — Kitchens with active contaminated stock.
  3. *Orders in Contamination Window* — Orders and customer contacts needing safety outreach.
  4. *Supplier Risk Scoreboard* — Aggregate batch counts, recalls, and safety metrics.
  5. *Active Menu-Blocked Quarantine Items* — Active blocked menu items.
  6. *All Flagged Batches & Suppliers* — Summary of suspected and confirmed inventory.
- **Interactive Node Linking**: Clicking any node ID in query results (`BATCH-PANEER-001`, `CK-GUR-01`, etc.) automatically centers, zooms, and highlights that entity in Cytoscape.
- **`🕸 Sync Graph`**: Injects query result nodes and relationships directly into the active graph canvas.
- **Instant Export**: One-click **CSV** and **JSON** export buttons for compliance records.

---

## 7. 2-Minute Demo Script

Follow this script to demonstrate all core capabilities in under 2 minutes:

1. **Initial Telemetry**: Open `http://localhost:8000`. The header displays live KPIs from Neo4j; notice `BATCH-CREAM-001` begins pre-flagged as `🟡 YELLOW`.
2. **Path Exploration**: Click `BATCH-PANEER-001`. Its downstream path through Delhi NCR kitchens and dishes illuminates instantly.
3. **Contamination Command**: In the bottom query console, click the **`contaminated`** chip (or type it). Every flagged path across NCR illuminates in crimson.
4. **Flag Suspect**: In the inspector, transition `BATCH-PANEER-001` from `🟢 GREEN` ➔ `🟡 YELLOW`, select reason *"Customer illness complaints"*, and set contamination date `2025-09-10 14:00`.
5. **Temporal Window**: Click **🕰 Timeline**. Notice usages before 14:00 are marked `SAFE`, while usages after 14:00 are marked `IN CONTAMINATION WINDOW`.
6. **Confirm Contamination**: Transition `BATCH-PANEER-001` from `🟡 YELLOW` ➔ `🔴 RED`. The emergency banner activates with exact blast counts.
7. **Kitchen Containment**: Click **📋 Pull from Menu**. Notice kitchen tags flip from `LIVE` ➔ `PULLED`, writing `MENU_BLOCKED` edges to Neo4j.
8. **Customer Outreach**: Click **📨 Notify Customers**. Affected customer records update to `NOTIFIED (SMS)`.
9. **FSSAI Compliance Report**: Click **📜 FSSAI Report**. View the generated compliance dossier with audit timestamps and containment actions.
10. **Reverse Traceability**: In the query console, execute `MATCH p=(c:Customer {id:"CUS-001"})-[:PLACED_ORDER]->(o)-[:CONTAINS_DISH]->(d)<-[:USED_IN]-(k)<-[:DELIVERED_TO]-(b)<-[:SUPPLIES]-(s) RETURN p`. Click **🕸 Sync Graph** to view the reverse provenance path on the canvas.

---

## 8. Complete API Reference

| Method | Endpoint | Description | Mode |
|---|---|---|---|
| `GET` | `/api/health` | Service health status and active mode (`neo4j` or `demo`) | All |
| `GET` | `/api/kpis` | Fleet counts (nodes, edges, flagged batches, blocked menu items, holds) | All |
| `GET` | `/api/filters` | Dynamic select options (suppliers, kitchens, ingredients, locations) | All |
| `GET` | `/api/network` | Filtered graph elements (`q`, `supplier`, `kitchen`, `statuses`, `include_orders`) | All |
| `GET` | `/api/node/{label}/{id}` | Deep properties, degree metrics, and incident relationships | All |
| `GET` | `/api/trace/{label}/{id}` | Multi-hop corridor traversal (`?direction=down` or `?direction=up`) | All |
| `GET` | `/api/expand/{label}/{id}` | 1-hop neighborhood subgraph expansion | All |
| `GET` | `/api/blast/{batch_id}` | Downstream blast impact (`?window=auto|on|off`) | All |
| `GET` | `/api/blast-supplier/{id}` | Enterprise-wide blast radius for a supplier's batch portfolio | All |
| `GET` | `/api/contamination` | Union contamination map of all active `YELLOW` and `RED` entities | All |
| `GET` | `/api/pull-list/{batch_id}` | Per-kitchen dishes to pull with physical quarantine status | All |
| `GET` | `/api/timeline/{batch_id}` | Chronological batch audit stream with temporal markers | All |
| `POST` | `/api/flag/{batch_id}` | Transitions batch risk state (`new_status`, `reason`, `contamination_date`) | All |
| `POST` | `/api/flag-supplier/{id}` | Transitions supplier risk state and cascades to all active batches | All |
| `POST` | `/api/actions/contain/{id}` | Toggles cloud kitchen hold status (`status=HOLD` or `status=RELEASED`) | All |
| `POST` | `/api/actions/pull-menu/{id}`| Writes `MENU_BLOCKED` relationships in Neo4j for affected dishes | All |
| `POST` | `/api/actions/restore-menu/{id}`| Removes `MENU_BLOCKED` relationships after batch quarantine clears | All |
| `POST` | `/api/actions/notify/{id}` | Records customer safety outreach records (`NOTIFIED_FOR`) | All |
| `GET` | `/api/report/{batch_id}` | Generates FSSAI / FoSCoS digital recall report JSON | All |
| `POST` | `/api/query/cypher` | Guardrailed read-only Cypher query execution (returns nodes, edges, table) | Neo4j |
| `POST` | `/api/demo/reset` | Resets in-memory demo graph back to clean initial state | Demo |

---

## 9. Neo4j Graph Data Model

```text
(:Supplier {
    id: "SUP-001",
    name: "Dairy Pure Farms",
    location: "Karnal, Haryana",
    status: "GREEN" | "YELLOW" | "RED",
    statusReason: "Microbial test alert"
})
  │
  │ [:SUPPLIES]
  ▼
(:Batch {
    id: "BATCH-PANEER-001",
    ingredientName: "Paneer",
    manufactureDate: datetime("2025-09-08T08:00:00Z"),
    status: "GREEN" | "YELLOW" | "RED",
    contaminationDate: datetime("2025-09-10T14:00:00Z"),
    statusReason: "Customer complaints"
})
  │
  ├─────────────────────────────────────────┐
  │ [:DELIVERED_TO {deliveryDate, qtyKg}]   │ [:PROCESSED_AT {timestamp}]
  ▼                                         ▼
(:CloudKitchen {                          (:Facility {
    id: "CK-GUR-01",                          id: "FAC-001",
    name: "Cyber Hub Central",                name: "Karnal Cold Processing",
    location: "Gurugram",                     stepType: "Pasteurization"
    containmentStatus: "NORMAL" | "HOLD"  })
})
  │
  │ [:USED_IN {timestamp, qtyKg}]
  ▼
(:Dish {
    id: "DSH-001",
    name: "Paneer Butter Masala",
    price: 320.0,
    blocked: true | false
})
  ▲
  │ [:CONTAINS_DISH {quantity}]
(:Order {
    id: "ORD-1001",
    timestamp: datetime("2025-09-10T19:30:00Z")
})
  │
  │ [:PLACED_AT]
  ├──► (:CloudKitchen)
  ▲
  │ [:PLACED_ORDER]
(:Customer {
    id: "CUS-001",
    name: "Aarav Sharma",
    phone: "+91-98110-11201",
    email: "aarav@example.in"
})
```

### Operational Incident Relationships
- `(:CloudKitchen)-[:MENU_BLOCKED {batchId, reason, at}]->(:Dish)` — Active dish blacklisting per kitchen.
- `(:Customer)-[:NOTIFIED_FOR {status, channel, at}]->(:Order)` — Customer outreach tracking.
- `(:Batch|Supplier)-[:HAS_EVENT]->(:AuditEvent {event, reason, actor, at})` — Immutable state transitions.

---

## 10. Project Directory Layout

```text
food-traceability-graph/
├── core/
│   ├── graph_api.py          # Cypher graph converters, filtering, blast calculation
│   ├── query_agent.py        # 3-layer guardrailed read-only Cypher query engine
│   ├── risk.py               # GREEN/YELLOW/RED state machine, supplier cascade, audit
│   └── traceability.py       # Forward/reverse traversal, pull lists, timeline, FSSAI report
├── db/
│   ├── connection.py         # Thread-safe Neo4j driver gateway with connection pooling
│   ├── schema.py             # Constraints and indexes definition
│   └── seed.py               # Delhi NCR demo seed dataset (shared by both modes)
├── web/
│   ├── index.html            # Main SPA layout with graph canvas & bottom query workstation
│   ├── styles.css            # Base command center styling & cold-chain color palette
│   ├── dashboard.css         # Operations dashboard & bottom query console styles
│   └── app.js                # Cytoscape graph engine, query runner, recall actions
├── tests/
│   ├── test_api.py           # API endpoint tests (FastAPI TestClient)
│   ├── test_risk.py          # State machine transitions and invalid jump guards
│   ├── test_seed_data.py     # Database seed data referential integrity
│   └── test_traceability.py  # Multi-hop impact, pull lists, and reverse trace logic
├── cli.py                    # Command-line interface for admin operations
├── ps_migrate.py             # Problem-statement canonical graph migration script
├── web_app.py                # FastAPI web server (Neo4j mode)
├── demo_server.py            # Standalone in-memory server (Zero-Docker demo mode)
├── config.py                 # Configuration and IST timezone helpers
├── docker-compose.yml        # Neo4j 5 container orchestration
├── render.yaml               # Render Blueprint for automated cloud deployment
├── requirements.txt          # Full dependencies (FastAPI, neo4j, etc.)
└── requirements-demo.txt     # Minimal dependencies for zero-Docker demo mode
```

---

## 11. Delhi NCR Demo Dataset

- **5 Suppliers:** Dairy Pure Farms (Karnal), Haryana Fresh Dairy, Delhi Organic Co, NCR Poultry Hub, Jaipur Spices.
- **4 Facilities:** Karnal Pasteurization, Sonipat Chilling Unit, Okhla Distribution Hub, Gurugram Packaging.
- **6 Cloud Kitchens:** Cyber Hub Central (Gurugram), Sector 29 (Gurugram), Connaught Place (Delhi), Okhla Phase 3 (Delhi), Sector 62 (Noida), Sector 18 (Noida).
- **10 Dishes:** Paneer Butter Masala, Palak Paneer, Paneer Tikka, Kadai Paneer, Butter Chicken, Chicken Biryani, Dal Makhani, Garlic Naan, Kadhai Chaap, Lassi.
- **10 Batches:** Paneer (`BATCH-PANEER-001`), Fresh Cream (`BATCH-CREAM-001` pre-flagged `YELLOW`), Milk, Chicken, Spices.
- **12 Customers & 21 Orders:** Realistic ordering timeline across lunch and dinner services around the contamination event timestamp (`2025-09-10 14:00 IST`).

---

## 12. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `Docker pull fails: x509: certificate signed by unknown authority` | Corporate firewall (e.g. FortiGate) SSL inspection | Use mirror: `docker pull mirror.gcr.io/library/neo4j:5.20 && docker tag mirror.gcr.io/library/neo4j:5.20 neo4j:5.20` |
| `pip SSL verification error` | Corporate proxy interception | `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
| `Unauthorized: client is unauthorized` | Password mismatch with `.env` | Ensure `.env` has `NEO4J_PASSWORD=tracegraph` matching `docker-compose.yml`. |
| `Port 8000 already in use` | Another process listening on port 8000 | Run: `uvicorn web_app:app --reload --port 8001` |
| `Impact counts unexpected after testing` | State mutations persist in Neo4j | Reset database: `python cli.py reset && python ps_migrate.py` (or click *Reset Network* in UI). |
| `Cypher query returns 501 in Demo Mode` | Direct Cypher console requires live Neo4j | Switch query console mode to `⌘ Commands` or start Docker Neo4j engine. |

---

## 13. Running Automated Tests

Run the full pytest suite:
```bash
pytest -v
```
Output:
```text
============================= test session starts ==============================
collected 32 items

tests/test_api.py::test_api_health PASSED                                [  3%]
tests/test_api.py::test_api_kpis PASSED                                  [  6%]
tests/test_api.py::test_api_filters PASSED                               [  9%]
tests/test_api.py::test_api_network PASSED                               [ 12%]
tests/test_api.py::test_api_node_details PASSED                          [ 15%]
tests/test_api.py::test_api_trace PASSED                                 [ 18%]
tests/test_api.py::test_api_expand PASSED                                [ 21%]
tests/test_api.py::test_api_blast PASSED                                 [ 25%]
tests/test_api.py::test_api_blast_supplier PASSED                        [ 28%]
tests/test_api.py::test_api_pull_list PASSED                             [ 31%]
tests/test_api.py::test_api_timeline PASSED                              [ 34%]
tests/test_api.py::test_api_report PASSED                                [ 37%]
tests/test_api.py::test_api_reverse PASSED                               [ 40%]
tests/test_api.py::test_api_supplier_intel PASSED                        [ 43%]
tests/test_api.py::test_api_contamination PASSED                         [ 46%]
tests/test_api.py::test_api_query_cypher PASSED                          [ 50%]
tests/test_api.py::test_demo_server_contamination_and_cypher PASSED      [ 53%]
tests/test_risk.py::test_green_to_yellow_allowed PASSED                  [ 56%]
tests/test_risk.py::test_yellow_to_red_allowed PASSED                    [ 59%]
tests/test_risk.py::test_yellow_back_to_green_allowed PASSED             [ 62%]
tests/test_risk.py::test_green_to_red_blocked PASSED                     [ 65%]
tests/test_risk.py::test_red_is_terminal PASSED                          [ 68%]
tests/test_seed_data.py::test_demo_batch_exists PASSED                   [ 71%]
tests/test_seed_data.py::test_usages_reference_existing_entities PASSED  [ 75%]
tests/test_seed_data.py::test_orders_reference_existing_entities PASSED  [ 78%]
tests/test_traceability.py::test_impact_report_forward_trace PASSED      [ 81%]
tests/test_traceability.py::test_reverse_trace PASSED                    [ 84%]
tests/test_traceability.py::test_pull_list_format PASSED                 [ 87%]
tests/test_traceability.py::test_supplier_intelligence PASSED            [ 90%]
tests/test_traceability.py::test_batch_timeline PASSED                   [ 93%]
tests/test_traceability.py::test_recall_report_structure PASSED          [ 96%]
tests/test_traceability.py::test_menu_blocked_and_restore_cycle PASSED   [100%]

============================== 32 passed in 1.74s ==============================
```

---

## 14. Tech Stack

- **Graph Database:** [Neo4j 5.20 Community](https://neo4j.com/)
- **Query Language:** Cypher
- **Backend Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Driver:** Official `neo4j` Python Bolt Driver
- **Frontend Visualization:** [Cytoscape.js](https://js.cytoscape.org/) (Vanilla JS SPA, zero build step)
- **Deployment & Hosting:** [Render](https://render.com/) (Docker / Blueprint)
- **Compliance Alignment:** FSSAI FoSCoS Digital Recall Procedure structure

---

## 15. License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

```text
================================================================================
Built for the Neo4j Hackathon — Logistics & Supply Chain Transparency.
One Flagged Batch. One Cypher Query. Every Kitchen, Dish, and Consumer it Reaches.
================================================================================
```
