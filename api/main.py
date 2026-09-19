"""FastAPI application for Food Traceability Graph & Recall Mission Control.

Provides graph exploration APIs, risk management endpoints, blast-radius calculation,
per-kitchen pull-lists, customer notification actions, and serves the Cytoscape SPA.
"""
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core import graph_api as gx          # noqa: E402
from core import risk                     # noqa: E402
from core import traceability as tr       # noqa: E402
from core.query_agent import CypherRejected, run_readonly_cypher  # noqa: E402
from db.connection import run_query       # noqa: E402

app = FastAPI(
    title="Food Traceability Graph — Recall Mission Control",
    version="2.0.0",
    description="Neo4j-powered supply-chain traceability & recall intelligence engine",
)
WEB_DIR = BASE_DIR / "web"
WIN = {"auto": None, "on": True, "off": False}


def _jsonify(o):
    if isinstance(o, dict):
        return {str(k): _jsonify(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_jsonify(v) for v in o]
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return o


def store_json(store):
    return {
        "nodes": [
            {"id": n, "label": d["label"], "props": _jsonify(d["props"])}
            for n, d in store["nodes"].items()
        ],
        "edges": [
            {
                "type": e["type"],
                "source": e["src"],
                "target": e["dst"],
                "props": _jsonify(e["props"]),
            }
            for e in store["edges"].values()
        ],
    }


def _blast_payload(res):
    return _jsonify({
        "batch": res["batch"],
        "window": res["window"],
        "counts": res["counts"],
        "node_ids": list(res["nodes"]),
        "edges": [
            {"type": t, "source": s, "target": d} for t, s, d in res["edges"]
        ],
        "graph": store_json(res["store"]),
    })


# ---------------------------------------------------------------- Models
class FlagReq(BaseModel):
    new_status: str
    reason: str
    actor: str = "web"
    contamination_date: Optional[datetime] = None


# ================================================================ /api/* Endpoints
@app.get("/api/health")
def health():
    run_query("RETURN 1")
    return {"status": "ok"}


@app.get("/api/kpis")
def kpis():
    counts = {
        r["label"]: r["c"]
        for r in run_query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c")
    }
    flagged = run_query("""
        MATCH (n) WHERE (n:Batch OR n:Supplier)
        AND n.status IN ['YELLOW','RED']
        RETURN n.id AS id, n.status AS status, labels(n)[0] AS kind,
               n.statusReason AS reason
        ORDER BY n.status DESC, n.id
    """)
    blocked = run_query(
        "MATCH (:CloudKitchen)-[m:MENU_BLOCKED]->() RETURN count(m) AS n"
    )[0]["n"]
    holds = run_query(
        "MATCH (k:CloudKitchen {containmentStatus:'HOLD'}) RETURN count(k) AS n"
    )[0]["n"]
    return _jsonify({
        "counts": counts,
        "flagged": flagged,
        "blocked_menu_items": blocked,
        "blocked_dishes": blocked,
        "kitchen_holds": holds,
    })


@app.get("/api/filters")
def filters():
    return _jsonify(gx.filter_options())


@app.get("/api/network")
def network(
    q: Optional[str] = None,
    supplier: Optional[str] = None,
    kitchen: Optional[str] = None,
    ingredient: Optional[str] = None,
    location: Optional[str] = None,
    statuses: Optional[List[str]] = Query(None),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_orders: bool = False,
    include_facility: bool = False,
):
    clean_statuses = statuses if isinstance(statuses, list) else None
    return store_json(
        gx.fetch_subgraph(
            q=q,
            supplier=supplier,
            kitchen=kitchen,
            ingredient=ingredient,
            location=location,
            statuses=clean_statuses,
            date_from=date_from,
            date_to=date_to,
            include_orders=include_orders,
            include_facility=include_facility,
        )
    )


@app.get("/api/node/{label}/{node_id}")
def node_details(label: str, node_id: str):
    try:
        props, rels = gx.node_details(label, node_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if props is None:
        raise HTTPException(404, f"{label} '{node_id}' not found")
    return _jsonify({"props": props, "relationships": rels})


@app.get("/api/trace/{label}/{node_id}")
def trace(label: str, node_id: str, direction: Literal["up", "down"] = "down"):
    try:
        return store_json(gx.trace(label, node_id, direction))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/expand/{label}/{node_id}")
def expand(label: str, node_id: str):
    try:
        return store_json(gx.neighborhood(label, node_id))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/blast/{batch_id}")
def blast(batch_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        return _blast_payload(gx.blast_radius(batch_id, WIN[window]))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/blast-supplier/{supplier_id}")
def blast_supplier(supplier_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        return _blast_payload(gx.supplier_blast(supplier_id, WIN[window]))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/contamination")
def contamination():
    return _blast_payload(gx.contamination_map())


class CypherReq(BaseModel):
    query: str


@app.post("/api/query/cypher")
def query_cypher(req: CypherReq):
    try:
        return run_readonly_cypher(req.query)
    except CypherRejected as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(422, f"Query error: {e}")


@app.get("/api/pull-list/{batch_id}")
def pull_list(batch_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        cd = tr.resolve_window(risk.get_batch(batch_id), WIN[window])
        return _jsonify({
            "batch": batch_id,
            "window": cd,
            "pull_list": tr.pull_list(batch_id, cd),
        })
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/timeline/{batch_id}")
def timeline(batch_id: str):
    try:
        return _jsonify(tr.batch_timeline(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/flag/{batch_id}")
def flag(batch_id: str, req: FlagReq):
    try:
        return _jsonify(
            risk.flag_batch(
                batch_id,
                req.new_status,
                req.reason,
                req.actor,
                risk.as_ist(req.contamination_date) if req.contamination_date else None,
            )
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except risk.RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/flag-supplier/{supplier_id}")
def flag_supplier(supplier_id: str, req: FlagReq):
    try:
        return _jsonify(
            risk.flag_supplier(
                supplier_id,
                req.new_status,
                req.reason,
                req.actor,
                risk.as_ist(req.contamination_date) if req.contamination_date else None,
            )
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except risk.RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/actions/contain/{batch_id}")
def contain(batch_id: str, status: str = "HOLD"):
    try:
        return _jsonify({"kitchens": tr.set_kitchen_containment(batch_id, status, "web")})
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/actions/pull-menu/{batch_id}")
@app.post("/api/actions/block/{batch_id}")
def pull_menu(batch_id: str):
    try:
        pulled = tr.pull_from_menu(batch_id, "web")
        return _jsonify({"pulled": pulled, "dishes": pulled})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/actions/restore-menu/{batch_id}")
def restore_menu(batch_id: str):
    try:
        return _jsonify({"restored": tr.restore_menu(batch_id, "web")})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/actions/notify/{batch_id}")
def notify(batch_id: str, channel: str = "SMS"):
    try:
        return _jsonify({
            "orders_notified": tr.mark_customers_notified(batch_id, channel, "web")
        })
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/report/{batch_id}")
def report(batch_id: str):
    try:
        return _jsonify(tr.recall_report(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


# ================================================================ Direct & Legacy Routes
@app.get("/health")
def v1_health():
    return health()


@app.get("/batches")
def list_batches(
    text: Optional[str] = None,
    ingredient: Optional[str] = None,
    supplier: Optional[str] = None,
):
    return _jsonify(tr.search_batches(text=text, ingredient=ingredient, supplier_id=supplier))


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    try:
        return _jsonify(risk.get_batch(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/batches/{batch_id}/flag")
def v1_flag_batch(batch_id: str, req: FlagReq):
    return flag(batch_id, req)


@app.get("/batches/{batch_id}/impact")
def v1_impact(batch_id: str, apply_window: Optional[bool] = Query(None)):
    try:
        return _jsonify(tr.impact_report(batch_id, apply_window=apply_window))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/batches/{batch_id}/timeline")
def v1_timeline(batch_id: str):
    return timeline(batch_id)


@app.get("/api/audit")
@app.get("/api/audit/{batch_id}")
def get_audit(batch_id: Optional[str] = None, limit: int = 50):
    if batch_id:
        return _jsonify(risk.audit_trail(batch_id))
    rows = run_query("""
        MATCH (e:AuditEvent)
        OPTIONAL MATCH (n)-[:HAS_EVENT]->(e)
        RETURN e.id AS id, e.type AS type, e.detail AS detail, e.actor AS actor,
               e.timestamp AS timestamp, coalesce(e.fromStatus, '') AS fromStatus,
               coalesce(e.toStatus, '') AS toStatus, coalesce(e.reason, '') AS reason,
               coalesce(n.id, '') AS entity
        ORDER BY e.timestamp DESC
        LIMIT $lim
    """, {"lim": limit})
    return _jsonify(rows)


@app.get("/batches/{batch_id}/audit")
def audit(batch_id: str):
    return _jsonify(risk.audit_trail(batch_id))


@app.get("/batches/{batch_id}/recall-report")
def v1_recall_report(batch_id: str):
    return report(batch_id)


@app.post("/recall/{batch_id}/contain-kitchens")
def v1_contain(batch_id: str, status: str = "HOLD", actor: str = "api"):
    try:
        return _jsonify({"kitchens": tr.set_kitchen_containment(batch_id, status, actor)})
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/recall/{batch_id}/block-dishes")
def v1_block(batch_id: str, actor: str = "api"):
    try:
        dishes = tr.pull_from_menu(batch_id, actor)
        return _jsonify({"dishes": dishes, "pulled": dishes})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/recall/{batch_id}/notify-customers")
def v1_notify(batch_id: str, channel: str = "SMS", actor: str = "api"):
    try:
        return _jsonify({
            "orders_notified": tr.mark_customers_notified(batch_id, channel, actor)
        })
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/trace/reverse")
def reverse(
    customer: Optional[str] = None,
    order: Optional[str] = None,
    dish: Optional[str] = None,
):
    try:
        return _jsonify(tr.reverse_trace(customer_id=customer, order_id=order, dish_id=dish))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/suppliers/{supplier_id}/intelligence")
def supplier_intel(supplier_id: str):
    try:
        return _jsonify(tr.supplier_intelligence(supplier_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


# Mount the SPA web directory
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
