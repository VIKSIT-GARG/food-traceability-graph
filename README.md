# Food Traceability Graph — Recall Mission Control

Graph-based food supply-chain traceability and recall intelligence engine for cloud-kitchen networks across Delhi-NCR (Gurugram, Noida, and Delhi).

Driven entirely by live Cypher queries on **Neo4j** as the single source of truth (no static or duplicate graph representations).

---

## 1. Project Architecture

```text
               ┌───────────────────────────────────────────────┐
               │         Cytoscape.js SPA / Streamlit         │
               └───────────────────────┬───────────────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   FastAPI API / Web App   │
                         │   (api/main.py, web_app)  │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │      Core Logic Layer     │
                         │  traceability · risk · gx │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │       db/connection       │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │       Neo4j Database      │
                         └───────────────────────────┘
```

The canonical supply-chain graph model:
```text
(Supplier)-[:SUPPLIES]->(Batch)-[:DELIVERED_TO]->(CloudKitchen)-[:USED_IN]->(Dish)
                                                        ▲
                                                        │ PLACED_AT
                                                     (Order)-[:CONTAINS_DISH]->(Dish)
                                                        ▲
                                                        │ PLACED_ORDER
                                                    (Customer)
```

---

## 2. Directory Structure

```text
food-traceability-graph/
├── AGENTS.md                  # Project specification and problem statement source of truth
├── AGENT2.md                 # Implementation, validation, and architecture guidelines
├── api/                      # FastAPI REST application
│   ├── __init__.py
│   └── main.py               # All /api/* endpoints + static file mount
├── core/                     # Core business and graph logic
│   ├── __init__.py
│   ├── graph_api.py          # Cytoscape graph converters, filters, blast radius
│   ├── risk.py               # Traffic-light risk state machine (GREEN/YELLOW/RED) & audit trail
│   ├── traceability.py       # Forward/reverse trace, pull-list, notifications, supplier intel
│   └── viz.py                # Visualizations for Streamlit
├── dashboard/                # Streamlit Operations & Explorer App
│   ├── app.py                # Command Center & Supplier Intelligence
│   ├── theme.py              # Visual design and CSS styling
│   └── pages/
│       └── 1_Graph_Explorer.py # Interactive graph explorer (streamlit-agraph)
├── db/                       # Database access and schema management
│   ├── __init__.py
│   ├── connection.py         # Thread-safe Neo4j driver gateway
│   ├── schema.py             # Constraints and indexes
│   └── seed.py               # Demo Delhi-NCR data seed
├── scripts/                  # Migration and utility scripts
│   ├── build_v2.py           # Historical build script
│   └── build_v2_web.py       # Historical frontend builder
├── tests/                    # Pytest test suite
│   ├── __init__.py
│   ├── test_api.py           # FastAPI endpoints validation
│   ├── test_risk.py          # State machine transitions and rules
│   ├── test_seed_data.py     # Database seed integrity
│   └── test_traceability.py  # Forward/reverse trace, pull list, supplier intel
├── web/                      # Cytoscape.js SPA Frontend
│   ├── index.html            # Main UI layout
│   ├── styles.css            # Dark command-center theme
│   └── app.js                # Cytoscape interactive graph & recall actions
├── cli.py                    # Command-line interface
├── ps_migrate.py             # Idempotent problem-statement graph migration
├── web_app.py                # Web application entrypoint for uvicorn
├── config.py                 # Environment and IST timezone settings
├── docker-compose.yml        # Neo4j 5 container definition
└── requirements.txt          # Python dependencies
```

---

## 3. Quick Start

### 1. Launch Neo4j
```bash
docker compose up -d
```

### 2. Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # if needed, default: bolt://localhost:7687, neo4j/tracegraph
```

### 3. Reset & Migrate Graph
```bash
python cli.py reset --migrate
# or alternatively:
# python cli.py reset && python ps_migrate.py
```

### 4. Run Applications

**Cytoscape SPA Mission Control (Primary):**
```bash
uvicorn web_app:app --reload
# Open http://localhost:8000
```

**Streamlit Dashboard (Operations & Vendor Intel):**
```bash
streamlit run dashboard/app.py
# Open http://localhost:8501
```

---

## 4. CLI Commands

```bash
# Initialize Neo4j constraints and indexes
python cli.py init-schema

# Reset database to demo state and run migration
python cli.py reset --migrate

# Check blast radius and pull list for a batch
python cli.py impact BATCH-PANEER-001

# Flag batch contamination (audited transition)
python cli.py flag BATCH-PANEER-001 YELLOW --reason "Suspected microbial contamination" --at "2025-09-10 14:00"

# Reverse trace from customer, order, or dish
python cli.py reverse --customer CUS-001

# Supplier risk intelligence & network impact
python cli.py supplier SUP-001

# Generate FSSAI-aligned recall report JSON
python cli.py report BATCH-PANEER-001 --out recall_report.json
```

---

## 5. Running Tests

```bash
pytest
```
All 29 tests covering risk transitions, forward/reverse traceability, pull lists, supplier intelligence, and FastAPI endpoints run and validate against the live graph.
