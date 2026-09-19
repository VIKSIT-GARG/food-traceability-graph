# Food Traceability Graph

Neo4j-powered food supply-chain traceability & recall engine for Delhi-NCR
cloud kitchens. Graph-first: an interactive graph explorer plus a risk
dashboard, both driven entirely by live Cypher queries — Neo4j is the single
source of truth (no static graph JSON).

## Stack
Neo4j 5 (Docker) · Python 3.x · neo4j driver · Cypher · Streamlit
(Risk Dashboard + Graph Explorer via streamlit-agraph) · FastAPI (optional) · pytest

## Run
    docker compose up -d                                 # Neo4j (neo4j / tracegraph)
    python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env
    python cli.py reset                                  # schema + demo data
    streamlit run dashboard/app.py                       # open Graph Explorer in nav

    # optional REST API:  uvicorn api.main:app --reload  (docs: localhost:8000/docs)
    # tests:              pytest -q

## Risk model
GREEN -> YELLOW (suspected; temporal window starts at contaminationDate)
      -> RED    (confirmed; full-scope recall). Every transition and recall
action writes an audited AuditEvent with reason, actor and timestamp.

## Demo script (5 min)
1. Graph Explorer: search PANEER, click BATCH-PANEER-001 (GREEN).
2. Flag YELLOW (contamination 10 Sep 2025 14:00 IST) -> windowed impact.
3. Simulate recall -> blast radius: kitchens/dishes/orders/customers glow.
4. Apply HOLDs, block dishes, mark customers notified (all audited).
5. Confirm RED -> full scope; download FSSAI-aligned JSON/CSV recall report.
6. Reverse trace: Customer -> Order -> Dish -> Batch -> Supplier.
7. Supplier Intelligence: risk aggregates + network-wide impact.

Note: dataset anchored to the spec example — paneer contamination event,
10 Sep 2025 14:00 IST. FSSAI/FoSCoS alignment is structural only; validate
before operational use.
