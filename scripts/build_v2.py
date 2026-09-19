#!/usr/bin/env python3
"""v2: aligns everything to the official problem statement.

Model:  (Supplier)-[:SUPPLIES]->(Batch)-[:DELIVERED_TO]->(CloudKitchen)
        (CloudKitchen)-[:USED_IN {batchId,timestamp,qtyKg}]->(Dish)
        (Order)-[:PLACED_AT]->(CloudKitchen)
        (CloudKitchen)-[:MENU_BLOCKED]->(Dish)          <- recall write action

Run:    python build_v2.py
        python cli.py reset && python ps_migrate.py
        uvicorn web_app:app --reload     -> http://localhost:8000
"""
import ast
from pathlib import Path

F = {}

# ============================================================ ps_migrate.py
F["ps_migrate.py"] = '''
"""Transform the seeded graph to the problem-statement model. Idempotent.
Run AFTER every  python cli.py reset  (or ingest_online.py)."""
from db.connection import run_query

STEPS = [
    ("SUPPLIED -> SUPPLIES", """
        MATCH (s:Supplier)-[r:SUPPLIED]->(b:Batch)
        CREATE (s)-[:SUPPLIES]->(b) DELETE r"""),
    ("batch usage -> kitchen USED_IN events", """
        MATCH (b:Batch)-[u:USED_IN_DISH]->(d:Dish)
        MATCH (b)-[:DELIVERED_TO]->(k:CloudKitchen)
        CREATE (k)-[:USED_IN {batchId: b.id, timestamp: u.timestamp, qtyKg: u.quantity}]->(d)
        DELETE u"""),
    ("drop leftover usage edges", "MATCH ()-[r:USED_IN_DISH]->() DELETE r"),
    ("attribute each order to a kitchen (PLACED_AT)", """
        MATCH (o:Order)-[:CONTAINS_DISH]->(d:Dish)
        MATCH (k:CloudKitchen)-[:USED_IN]->(d)
        WITH o, k, rand() AS r ORDER BY o.id, r
        WITH o, collect(k)[0] AS kitchen
        MERGE (o)-[:PLACED_AT]->(kitchen)"""),
    ("supplier risk fields", "MATCH (s:Supplier) WHERE s.status IS NULL SET s.status = 'GREEN'"),
    ("index USED_IN.batchId",
     "CREATE INDEX usedin_batch IF NOT EXISTS FOR ()-[u:USED_IN]-() ON (u.batchId)"),
]

if __name__ == "__main__":
    for name, q in STEPS:
        run_query(q)
        print("  ok:", name)
    rels = run_query("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC")
    print("Relationships now:", {r["t"]: r["c"] for r in rels})
'''

# ============================================================ core/risk.py
F["core/risk.py"] = '''
"""GREEN -> YELLOW -> RED state machine for Batch AND Supplier, with audit trail."""
from config import IST
from db.connection import run_query

ALLOWED_TRANSITIONS = {"GREEN": {"YELLOW"}, "YELLOW": {"RED", "GREEN"}, "RED": set()}
STATUS_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}


class RiskTransitionError(ValueError):
    pass


def as_ist(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt.astimezone(IST)


def validate_transition(current, new):
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise RiskTransitionError(
            "Invalid transition " + current + " -> " + new +
            ". Allowed from " + current + ": " + str(sorted(allowed) or ["none (terminal)"]))


def get_batch(batch_id):
    rows = run_query("""
        MATCH (s:Supplier)-[:SUPPLIES]->(b:Batch {id: $id})
        RETURN b{.*} AS batch, s{.*} AS supplier
    """, {"id": batch_id})
    if not rows:
        raise KeyError("Batch '" + batch_id + "' not found")
    return {**rows[0]["batch"], "supplier": rows[0]["supplier"]}


def get_supplier(supplier_id):
    rows = run_query("""
        MATCH (s:Supplier {id: $id})
        OPTIONAL MATCH (s)-[:SUPPLIES]->(b:Batch)
        RETURN s{.*} AS supplier, count(b) AS total_batches,
               sum(CASE WHEN b.status='GREEN' THEN 1 ELSE 0 END) AS green,
               sum(CASE WHEN b.status='YELLOW' THEN 1 ELSE 0 END) AS yellow,
               sum(CASE WHEN b.status='RED' THEN 1 ELSE 0 END) AS red
    """, {"id": supplier_id})
    if not rows or not rows[0]["supplier"]:
        raise KeyError("Supplier '" + supplier_id + "' not found")
    s = rows[0]
    return {**s["supplier"], "total_batches": s["total_batches"],
            "green": s["green"], "yellow": s["yellow"], "red": s["red"]}


def flag_batch(batch_id, new_status, reason, actor="operator", contamination_date=None):
    batch = get_batch(batch_id)
    validate_transition(batch["status"], new_status)
    if not (reason or "").strip():
        raise ValueError("A reason is required for every risk transition (audit trail).")
    if new_status == "YELLOW" and contamination_date is None \\
            and batch.get("contaminationDate") is None:
        raise ValueError("contamination_date is required when flagging YELLOW.")
    rows = run_query("""
        MATCH (b:Batch {id: $bid})
        SET b.status = $new, b.statusReason = $reason, b.statusTimestamp = datetime(),
            b.contaminationDate = coalesce($cd, b.contaminationDate)
        CREATE (e:AuditEvent {id: 'EVT-' + randomUUID(), type: 'STATUS_TRANSITION',
                fromStatus: $cur, toStatus: $new, reason: $reason, actor: $actor,
                timestamp: datetime()})
        CREATE (b)-[:HAS_EVENT]->(e)
        RETURN b{.*} AS batch
    """, {"bid": batch_id, "cur": batch["status"], "new": new_status,
          "reason": reason.strip(), "actor": actor, "cd": as_ist(contamination_date)})
    return rows[0]["batch"]


def flag_supplier(supplier_id, new_status, reason, actor="operator", contamination_date=None):
    """Flag a supplier; cascade the status onto every not-yet-flagged batch."""
    sup = get_supplier(supplier_id)
    validate_transition(sup["status"], new_status)
    if not (reason or "").strip():
        raise ValueError("A reason is required for every risk transition (audit trail).")
    cd = as_ist(contamination_date)
    run_query("""
        MATCH (s:Supplier {id: $sid})
        SET s.status = $new, s.statusReason = $reason, s.statusTimestamp = datetime(),
            s.contaminationDate = coalesce($cd, s.contaminationDate)
        CREATE (e:AuditEvent {id: 'EVT-' + randomUUID(), type: 'STATUS_TRANSITION',
                fromStatus: $cur, toStatus: $new, reason: $reason, actor: $actor,
                timestamp: datetime()})
        CREATE (s)-[:HAS_EVENT]->(e)
    """, {"sid": supplier_id, "cur": sup["status"], "new": new_status,
          "reason": reason.strip(), "actor": actor, "cd": cd})
    where = "b.status = 'GREEN'" if new_status == "YELLOW" else "b.status IN ['GREEN','YELLOW']"
    rows = run_query("""
        MATCH (s:Supplier {id: $sid})-[:SUPPLIES]->(b:Batch)
        WHERE """ + where + """
        SET b.status = $new,
            b.statusReason = 'Supplier ' + $sid + ' flagged ' + $new + ': ' + $reason,
            b.statusTimestamp = datetime(),
            b.contaminationDate = coalesce(b.contaminationDate, $cd)
        WITH b CREATE (e:AuditEvent {id: 'EVT-' + randomUUID(), type: 'SUPPLIER_CASCADE',
                toStatus: $new, reason: 'Cascade from supplier ' + $sid, actor: $actor,
                timestamp: datetime()})
        CREATE (b)-[:HAS_EVENT]->(e)
        RETURN collect(b.id) AS batches
    """, {"sid": supplier_id, "new": new_status, "reason": reason.strip(),
          "actor": actor, "cd": cd})
    return {"id": supplier_id, "name": sup.get("name"), "status": new_status,
            "reason": reason.strip(), "cascaded_batches": rows[0]["batches"]}


def audit_trail(batch_id):
    return run_query("""
        MATCH (b:Batch {id: $id})-[:HAS_EVENT]->(e:AuditEvent)
        RETURN e.id AS id, e.type AS type, e.fromStatus AS fromStatus,
               e.toStatus AS toStatus, e.reason AS reason, e.detail AS detail,
               e.actor AS actor, e.timestamp AS timestamp
        ORDER BY e.timestamp
    """, {"id": batch_id})
'''

# ============================================================ core/traceability.py
F["core/traceability.py"] = '''
"""PS-aligned traceability. Path: Supplier-SUPPLIES->Batch-DELIVERED_TO->Kitchen-USED_IN->Dish.
Orders attributed per kitchen via PLACED_AT. Core output: per-kitchen PULL LISTS."""
from datetime import datetime
from core.risk import as_ist, audit_trail, get_batch, get_supplier
from db.connection import run_query


def resolve_window(entity, apply_window=None):
    cd = entity.get("contaminationDate")
    if apply_window is None:
        return as_ist(cd) if entity["status"] == "YELLOW" and cd else None
    if apply_window:
        if not cd:
            raise ValueError("No contaminationDate recorded; cannot apply temporal window.")
        return as_ist(cd)
    return None


def search_batches(text=None, ingredient=None, supplier_id=None, limit=100):
    text = text.lower().strip() if text else None
    return run_query("""
        MATCH (s:Supplier)-[:SUPPLIES]->(b:Batch)
        WHERE ($text IS NULL OR toLower(b.id) CONTAINS $text
               OR toLower(b.ingredientName) CONTAINS $text OR toLower(s.name) CONTAINS $text)
          AND ($ingredient IS NULL OR b.ingredientName = $ingredient)
          AND ($supplier IS NULL OR s.id = $supplier)
        RETURN b.id AS id, b.ingredientName AS ingredient, b.status AS status,
               b.manufactureDate AS manufactured, b.statusReason AS reason,
               s.id AS supplier_id, s.name AS supplier
        ORDER BY b.id LIMIT $limit
    """, {"text": text, "ingredient": ingredient, "supplier": supplier_id, "limit": limit})


def list_ingredients():
    return [r["name"] for r in run_query(
        "MATCH (b:Batch) RETURN DISTINCT b.ingredientName AS name ORDER BY name")]


def list_suppliers():
    return run_query("MATCH (s:Supplier) RETURN s.id AS id, s.name AS name, "
                     "s.status AS status ORDER BY s.name")


def list_customers():
    return run_query("MATCH (c:Customer) RETURN c.id AS id, c.name AS name ORDER BY c.name")


def list_dishes():
    return run_query("MATCH (d:Dish) RETURN d.id AS id, d.name AS name ORDER BY d.name")


def affected_deliveries(batch_id, cd):
    return run_query("""
        MATCH (b:Batch {id: $bid})-[dl:DELIVERED_TO]->(k:CloudKitchen)
        RETURN k.id AS kitchen_id, k.name AS kitchen, k.location AS location,
               dl.deliveryDate AS delivery_date, dl.qtyKg AS qty_kg,
               coalesce(k.containmentStatus, 'NONE') AS containment,
               CASE WHEN $cd IS NULL OR dl.deliveryDate >= $cd THEN true ELSE false END AS in_window
        ORDER BY dl.deliveryDate
    """, {"bid": batch_id, "cd": cd})


def affected_usage(batch_id, cd):
    """Kitchen-scoped consumption events for this batch."""
    return run_query("""
        MATCH (b:Batch {id: $bid})-[:DELIVERED_TO]->(k:CloudKitchen)
        MATCH (k)-[u:USED_IN]->(d:Dish)
        WHERE u.batchId = b.id AND ($cd IS NULL OR u.timestamp >= $cd)
        RETURN k.id AS kitchen_id, k.name AS kitchen, d.id AS dish_id, d.name AS dish,
               collect(u.timestamp) AS used_at, round(sum(u.qtyKg) * 10) / 10.0 AS qty_kg
        ORDER BY k.name, d.name
    """, {"bid": batch_id, "cd": cd})


def pull_list(batch_id, cd=None):
    """THE problem-statement output: per kitchen, which dishes to pull from the menu."""
    if cd is None:
        cd = resolve_window(get_batch(batch_id), None)
    return run_query("""
        MATCH (b:Batch {id: $bid})-[:DELIVERED_TO]->(k:CloudKitchen)
        MATCH (k)-[u:USED_IN]->(d:Dish)
        WHERE u.batchId = b.id AND ($cd IS NULL OR u.timestamp >= $cd)
        RETURN k.id AS kitchen_id, k.name AS kitchen, k.location AS location,
               collect(DISTINCT {id: d.id, name: d.name}) AS pull_dishes
        ORDER BY k.name
    """, {"bid": batch_id, "cd": cd})


def affected_order_records(batch_id, cd):
    return run_query("""
        MATCH (b:Batch {id: $bid})-[:DELIVERED_TO]->(k:CloudKitchen)
        MATCH (k)-[u:USED_IN]->(d:Dish)
        WHERE u.batchId = b.id AND ($cd IS NULL OR u.timestamp >= $cd)
        MATCH (o:Order)-[:PLACED_AT]->(k)
        WHERE $cd IS NULL OR o.timestamp >= $cd
        MATCH (o)-[cr:CONTAINS_DISH]->(d)
        MATCH (c:Customer)-[:PLACED_ORDER]->(o)
        OPTIONAL MATCH (c)-[n:NOTIFIED_FOR]->(o)
        RETURN o.id AS order_id, o.timestamp AS order_time, k.name AS kitchen,
               c.id AS customer_id, c.name AS customer, c.phone AS phone, c.email AS email,
               collect(DISTINCT d.name) AS dishes,
               coalesce(n.status, 'PENDING') AS notification_status
        ORDER BY o.timestamp
    """, {"bid": batch_id, "cd": cd})


def impact_report(batch_id, apply_window=None):
    batch = get_batch(batch_id)
    cd = resolve_window(batch, apply_window)
    deliveries = affected_deliveries(batch_id, cd)
    usage = affected_usage(batch_id, cd)
    orders = affected_order_records(batch_id, cd)
    kin = deliveries if cd is None else [k for k in deliveries if k["in_window"]]
    return {
        "batch": batch, "scope": "windowed" if cd else "full", "window_start": cd,
        "counts": {"kitchens": len(kin),
                   "dishes": len({u["dish_id"] for u in usage}),
                   "orders": len({o["order_id"] for o in orders}),
                   "customers": len({o["customer_id"] for o in orders})},
        "kitchens": deliveries, "usage": usage,
        "pull_list": pull_list(batch_id, cd), "orders": orders,
    }


def supplier_impact(supplier_id, apply_window=None):
    sup = get_supplier(supplier_id)
    cd = resolve_window(sup, apply_window)
    kitchens, usage, orders = {}, {}, {}
    for r in run_query("MATCH (:Supplier {id: $sid})-[:SUPPLIES]->(b:Batch) RETURN b.id AS id",
                       {"sid": supplier_id}):
        for k in affected_deliveries(r["id"], cd):
            if cd is None or k["in_window"]:
                kitchens[k["kitchen_id"]] = k
        for u in affected_usage(r["id"], cd):
            usage[(u["kitchen_id"], u["dish_id"])] = u
        for o in affected_order_records(r["id"], cd):
            orders[o["order_id"]] = o
    return {"supplier": sup, "scope": "windowed" if cd else "full", "window_start": cd,
            "counts": {"batches": sup["total_batches"], "kitchens": len(kitchens),
                       "dishes": len({v["dish_id"] for v in usage.values()}),
                       "orders": len(orders),
                       "customers": len({o["customer_id"] for o in orders.values()})},
            "kitchens": list(kitchens.values()), "usage": list(usage.values()),
            "orders": list(orders.values())}


def set_kitchen_containment(batch_id, status, actor="operator"):
    if status not in {"HOLD", "RELEASED", "DESTROYED"}:
        raise ValueError("status must be HOLD, RELEASED or DESTROYED")
    cd = resolve_window(get_batch(batch_id), None)
    rows = run_query("""
        MATCH (b:Batch {id: $bid})-[dl:DELIVERED_TO]->(k:CloudKitchen)
        WHERE $cd IS NULL OR dl.deliveryDate >= $cd
        SET k.containmentStatus = $status
        RETURN collect(k.id) AS kitchens
    """, {"bid": batch_id, "cd": cd, "status": status})
    _action_event(batch_id, "KITCHEN_CONTAINMENT",
                  "Containment '" + status + "': " + ", ".join(rows[0]["kitchens"]), actor)
    return rows[0]["kitchens"]


def pull_from_menu(batch_id, actor="operator"):
    """Write the recall action: (Kitchen)-[:MENU_BLOCKED]->(Dish) per affected pair."""
    cd = resolve_window(get_batch(batch_id), None)
    rows = run_query("""
        MATCH (b:Batch {id: $bid})-[:DELIVERED_TO]->(k:CloudKitchen)
        MATCH (k)-[u:USED_IN]->(d:Dish)
        WHERE u.batchId = b.id AND ($cd IS NULL OR u.timestamp >= $cd)
        MERGE (k)-[mb:MENU_BLOCKED]->(d)
        ON CREATE SET mb.reason = 'Recall: batch ' + $bid, mb.batchId = $bid,
                      mb.at = datetime()
        SET d.blocked = true
        RETURN collect(DISTINCT k.name + ' -> ' + d.name) AS pulled
    """, {"bid": batch_id, "cd": cd})
    _action_event(batch_id, "MENU_PULL",
                  "Pulled from menus: " + ", ".join(rows[0]["pulled"]), actor)
    return rows[0]["pulled"]


def restore_menu(batch_id, actor="operator"):
    rows = run_query("""
        MATCH (k:CloudKitchen)-[mb:MENU_BLOCKED]->(d:Dish) WHERE mb.batchId = $bid
        DELETE mb
        RETURN count(mb) AS n
    """, {"bid": batch_id})
    _action_event(batch_id, "MENU_RESTORE", "Restored " + str(rows[0]["n"]) + " menu items", actor)
    return rows[0]["n"]


def mark_customers_notified(batch_id, channel="SMS", actor="operator"):
    cd = resolve_window(get_batch(batch_id), None)
    rows = run_query("""
        MATCH (b:Batch {id: $bid})-[:DELIVERED_TO]->(k:CloudKitchen)
        MATCH (k)-[u:USED_IN]->(d:Dish)
        WHERE u.batchId = b.id AND ($cd IS NULL OR u.timestamp >= $cd)
        MATCH (o:Order)-[:PLACED_AT]->(k)
        WHERE $cd IS NULL OR o.timestamp >= $cd
        MATCH (o)-[:CONTAINS_DISH]->(d)
        MATCH (c:Customer)-[:PLACED_ORDER]->(o)
        MERGE (c)-[n:NOTIFIED_FOR]->(o)
        SET n.status = 'NOTIFIED', n.channel = $channel, n.notifiedAt = datetime()
        RETURN count(DISTINCT o) AS orders
    """, {"bid": batch_id, "cd": cd, "channel": channel})
    _action_event(batch_id, "CUSTOMER_NOTIFICATION",
                  channel + " notifications for " + str(rows[0]["orders"]) + " orders", actor)
    return rows[0]["orders"]


def _action_event(batch_id, etype, detail, actor):
    run_query("""
        MATCH (b:Batch {id: $bid})
        CREATE (e:AuditEvent {id: 'EVT-' + randomUUID(), type: $t, detail: $d,
                actor: $a, timestamp: datetime()})
        CREATE (b)-[:HAS_EVENT]->(e)
    """, {"bid": batch_id, "t": etype, "d": detail, "a": actor})


def reverse_trace(customer_id=None, order_id=None, dish_id=None):
    if not (customer_id or order_id or dish_id):
        raise ValueError("Provide a customer, order or dish identifier.")
    rows = run_query("""
        MATCH (c:Customer)-[:PLACED_ORDER]->(o:Order)
        WHERE ($customer IS NULL OR c.id = $customer) AND ($order IS NULL OR o.id = $order)
        MATCH (o)-[:PLACED_AT]->(k:CloudKitchen)
        MATCH (o)-[cr:CONTAINS_DISH]->(d:Dish) WHERE $dish IS NULL OR d.id = $dish
        MATCH (k)-[u:USED_IN]->(d)
        MATCH (b:Batch) WHERE b.id = u.batchId AND u.timestamp <= o.timestamp
        MATCH (s:Supplier)-[:SUPPLIES]->(b)
        RETURN o.id AS order_id, o.timestamp AS order_time, k.name AS kitchen,
               c.id AS customer_id, c.name AS customer, d.id AS dish_id, d.name AS dish,
               collect(DISTINCT {id: b.id, ingredient: b.ingredientName,
                                 status: b.status, used_at: u.timestamp}) AS batches,
               collect(DISTINCT {id: s.id, name: s.name}) AS suppliers
        ORDER BY o.timestamp DESC
    """, {"customer": customer_id, "order": order_id, "dish": dish_id})
    batches, suppliers, flagged = {}, {}, False
    for r in rows:
        for b in r["batches"]:
            batches[b["id"]] = b
            if b["status"] in ("YELLOW", "RED"):
                flagged = True
        for s in r["suppliers"]:
            suppliers[s["id"]] = s
    return {"rows": rows, "batches": list(batches.values()),
            "suppliers": list(suppliers.values()), "flagged_batch_used": flagged}


def batch_timeline(batch_id):
    b = get_batch(batch_id)
    events = [{"ts": b.get("manufactureDate"), "label": "Batch manufactured",
               "kind": "MANUFACTURE"}]
    for r in run_query("MATCH (b:Batch {id:$b})-[p:PROCESSED_AT]->(f:Facility) "
                       "RETURN p.timestamp AS ts, 'Processed at ' + f.name AS label",
                       {"b": batch_id}):
        events.append({**r, "kind": "PROCESSING"})
    for r in run_query("MATCH (b:Batch {id:$b})-[dl:DELIVERED_TO]->(k:CloudKitchen) "
                       "RETURN dl.deliveryDate AS ts, 'Delivered to ' + k.name AS label",
                       {"b": batch_id}):
        events.append({**r, "kind": "DELIVERY"})
    for r in run_query("""MATCH (b:Batch {id:$b})-[:DELIVERED_TO]->(k)-[u:USED_IN]->(d:Dish)
                          WHERE u.batchId = $b
                          RETURN u.timestamp AS ts,
                                 'Used in ' + d.name + ' @ ' + k.name AS label""",
                       {"b": batch_id}):
        events.append({**r, "kind": "USAGE"})
    for r in run_query("MATCH (b:Batch {id:$b})-[:HAS_EVENT]->(e:AuditEvent) "
                       "RETURN e.timestamp AS ts, coalesce(e.reason, e.detail, e.type) AS label",
                       {"b": batch_id}):
        events.append({**r, "kind": "AUDIT"})
    events = [e for e in events if e["ts"] is not None]
    events.sort(key=lambda e: e["ts"])
    return {"batch": batch_id, "ingredient": b["ingredientName"], "status": b["status"],
            "contamination_date": b.get("contaminationDate"),
            "supplier": b["supplier"].get("name"), "events": events}


def _stringify(o):
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_stringify(v) for v in o]
    if isinstance(o, datetime):
        return o.isoformat()
    return o


def recall_report(batch_id):
    batch = get_batch(batch_id)
    impact = impact_report(batch_id, None)
    events = audit_trail(batch_id)
    notifications = []
    for o in impact["orders"]:
        when = o["order_time"].strftime("%d %b %Y %H:%M") if o["order_time"] else ""
        notifications.append({
            "customer_id": o["customer_id"], "customer_name": o["customer"],
            "phone": o["phone"], "email": o["email"], "order_id": o["order_id"],
            "kitchen": o["kitchen"], "notification_status": o["notification_status"],
            "message": ("Food safety alert: your order " + o["order_id"] + " placed on " + when +
                        " at " + o["kitchen"] + " included " + ", ".join(o["dishes"]) +
                        ", prepared with batch " + batch_id + " (" + batch["ingredientName"] +
                        ") under recall (status " + batch["status"] +
                        "). Discard the item; contact support for a refund.")})
    return _stringify({
        "reportType": "Food Recall Traceability Report (FSSAI-aligned draft)",
        "generatedAt": datetime.now().astimezone().isoformat(),
        "product": {"batchId": batch_id, "ingredient": batch["ingredientName"],
                    "supplier": batch["supplier"], "riskStatus": batch["status"],
                    "statusReason": batch.get("statusReason"),
                    "contaminationWindowStart": _iso_or_none(batch.get("contaminationDate"))},
        "impactSummary": impact["counts"],
        "kitchenPullLists": impact["pull_list"],
        "ordersAffected": impact["orders"],
        "consumerNotificationList": notifications,
        "statusHistory": [e for e in events if e["type"] == "STATUS_TRANSITION"],
        "actionsTaken": [e for e in events if e["type"] != "STATUS_TRANSITION"],
        "complianceNote": "Supports FSSAI digital recall / FoSCoS logging structure; "
                          "validate before operational use."})


def _iso_or_none(dt):
    return dt.isoformat() if dt is not None else None
'''

# ============================================================ core/graph_api.py
F["core/graph_api.py"] = '''
"""Live-Cypher graph service for the frontend. Neo4j is the only source of truth."""
from datetime import datetime, time as dtime
from core.risk import as_ist, get_batch, get_supplier
from core.traceability import resolve_window
from db.connection import run_query

LABELS = ("Supplier", "Batch", "Facility", "CloudKitchen", "Dish", "Order", "Customer")

DOWN_RULES = {
    "Supplier":     [("SUPPLIES", "dst", "Batch")],
    "Batch":        [("PROCESSED_AT", "dst", "Facility"),
                     ("DELIVERED_TO", "dst", "CloudKitchen")],
    "Facility":     [],
    "CloudKitchen": [("USED_IN", "dst", "Dish")],
    "Dish":         [("CONTAINS_DISH", "src", "Order")],
    "Order":        [("PLACED_ORDER", "src", "Customer")],
    "Customer":     [],
}
UP_RULES = {
    "Supplier":     [],
    "Batch":        [("SUPPLIES", "src", "Supplier")],
    "Facility":     [("PROCESSED_AT", "src", "Batch")],
    "CloudKitchen": [("DELIVERED_TO", "src", "Batch"), ("PLACED_AT", "src", "Order")],
    "Dish":         [("USED_IN", "src", "CloudKitchen"), ("CONTAINS_DISH", "src", "Order")],
    "Order":        [("CONTAINS_DISH", "dst", "Dish"), ("PLACED_ORDER", "src", "Customer")],
    "Customer":     [("PLACED_ORDER", "dst", "Order")],
}


def _safe(label):
    if label not in LABELS:
        raise ValueError("Unknown label '" + label + "'")


def _store():
    return {"nodes": {}, "edges": {}}


def upsert_node(store, label, props):
    if not props or props.get("id") is None:
        return
    cur = store["nodes"].get(props["id"])
    if cur is None:
        store["nodes"][props["id"]] = {"label": label, "props": dict(props)}
    else:
        cur["props"] = {**cur["props"], **dict(props)}


def upsert_edge(store, rel, src, dst, props):
    key = (rel, src, dst)
    if key not in store["edges"]:
        store["edges"][key] = {"type": rel, "src": src, "dst": dst, "props": []}
    store["edges"][key]["props"].append(dict(props or {}))


def merge_stores(dst, src):
    for nid, nd in src["nodes"].items():
        upsert_node(dst, nd["label"], nd["props"])
    for key, e in src["edges"].items():
        if key in dst["edges"]:
            dst["edges"][key]["props"] += e["props"]
        else:
            dst["edges"][key] = e
    return dst


def neighborhood(label, node_id):
    _safe(label)
    rows = run_query("""
        MATCH (n:`""" + label + """` {id: $id})-[r]-(m)
        RETURN labels(n)[0] AS n_label, properties(n) AS n_props, type(r) AS rel,
               startNode(r) = n AS outbound, properties(r) AS r_props,
               labels(m)[0] AS m_label, properties(m) AS m_props
    """, {"id": node_id})
    store = _store()
    for r in rows:
        upsert_node(store, r["n_label"], r["n_props"])
        upsert_node(store, r["m_label"], r["m_props"])
        if r["outbound"]:
            upsert_edge(store, r["rel"], r["n_props"]["id"], r["m_props"]["id"], r["r_props"])
        else:
            upsert_edge(store, r["rel"], r["m_props"]["id"], r["n_props"]["id"], r["r_props"])
    return store


def trace(label, node_id, direction="down", max_depth=6):
    rules = DOWN_RULES if direction == "down" else UP_RULES
    store = _store()
    seen = {(label, node_id)}
    frontier = [(label, node_id, 0)]
    while frontier:
        cl, cid, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        hop = neighborhood(cl, cid)
        merge_stores(store, hop)
        for rel, side, tgt in rules.get(cl, []):
            for e in hop["edges"].values():
                if e["type"] != rel:
                    continue
                nid = e["dst"] if (side == "dst" and e["src"] == cid) else \\
                      e["src"] if (side == "src" and e["dst"] == cid) else None
                if nid is None or hop["nodes"].get(nid, {}).get("label") != tgt:
                    continue
                if (tgt, nid) not in seen:
                    seen.add((tgt, nid))
                    frontier.append((tgt, nid, depth + 1))
    return store


def descendants(label, node_id, store):
    out, seen = set(), {node_id}
    frontier = [(label, node_id)]
    while frontier:
        cl, cid = frontier.pop()
        for rel, side, tgt in DOWN_RULES.get(cl, []):
            for e in store["edges"].values():
                if e["type"] != rel:
                    continue
                nid = e["dst"] if (side == "dst" and e["src"] == cid) else \\
                      e["src"] if (side == "src" and e["dst"] == cid) else None
                nd = store["nodes"].get(nid) if nid else None
                if nd is None or nd["label"] != tgt or nid in seen:
                    continue
                seen.add(nid)
                out.add(nid)
                frontier.append((tgt, nid))
    return out


def fetch_subgraph(*, q=None, supplier=None, kitchen=None, ingredient=None,
                   location=None, statuses=None, date_from=None, date_to=None):
    p = {"q": (q or "").lower() or None, "supplier": supplier, "kitchen": kitchen,
         "ingredient": ingredient, "location": (location or "").lower() or None,
         "statuses": statuses or None}
    rows = run_query("""
        MATCH (s:Supplier)-[:SUPPLIES]->(b:Batch)
        OPTIONAL MATCH (b)-[pr:PROCESSED_AT]->(f:Facility)
        OPTIONAL MATCH (b)-[dl:DELIVERED_TO]->(k:CloudKitchen)
        OPTIONAL MATCH (k)-[u:USED_IN]->(d:Dish)
        OPTIONAL MATCH (o:Order)-[:PLACED_AT]->(k)
        OPTIONAL MATCH (o)-[cr:CONTAINS_DISH]->(d)
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
        WHERE ($q IS NULL OR toLower(b.id) CONTAINS $q OR toLower(b.ingredientName) CONTAINS $q
               OR toLower(s.name) CONTAINS $q OR toLower(k.name) CONTAINS $q)
          AND ($supplier IS NULL OR s.id = $supplier)
          AND ($kitchen IS NULL OR k.id = $kitchen)
          AND ($ingredient IS NULL OR b.ingredientName = $ingredient)
          AND ($location IS NULL OR toLower(s.location) CONTAINS $location
               OR toLower(k.location) CONTAINS $location OR toLower(f.location) CONTAINS $location)
          AND ($statuses IS NULL OR b.status IN $statuses)
        RETURN s, b, pr, f, dl, k, u, d, o, cr, c
    """, p)
    store = _store()
    for r in rows:
        s, b, f, k, d, o, c = r["s"], r["b"], r["f"], r["k"], r["d"], r["o"], r["c"]
        upsert_node(store, "Supplier", s)
        upsert_node(store, "Batch", b)
        if f:
            upsert_node(store, "Facility", f)
            upsert_edge(store, "PROCESSED_AT", b["id"], f["id"], r["pr"])
        if k:
            upsert_node(store, "CloudKitchen", k)
            upsert_edge(store, "DELIVERED_TO", b["id"], k["id"], r["dl"])
            if d and r["u"] is not None:
                upsert_node(store, "Dish", d)
                upsert_edge(store, "USED_IN", k["id"], d["id"], r["u"])
                if o:
                    upsert_node(store, "Order", o)
                    upsert_edge(store, "PLACED_AT", o["id"], k["id"], {})
                    upsert_edge(store, "CONTAINS_DISH", o["id"], d["id"], r["cr"])
                    if c:
                        upsert_node(store, "Customer", c)
                        upsert_edge(store, "PLACED_ORDER", c["id"], o["id"], {})
    if date_from or date_to:
        from datetime import date as _date
        lo = as_ist(datetime.combine(date_from, dtime.min)) if date_from else None
        hi = as_ist(datetime.combine(date_to, dtime.max)) if date_to else None

        def inr(t):
            return (lo is None or (t is not None and t >= lo)) and \\
                   (hi is None or (t is not None and t <= hi))

        kept = {}
        for key, e in store["edges"].items():
            if e["type"] == "DELIVERED_TO":
                props = [pp for pp in e["props"] if inr(pp.get("deliveryDate"))]
            elif e["type"] == "USED_IN":
                props = [pp for pp in e["props"] if inr(pp.get("timestamp"))]
            elif e["type"] == "CONTAINS_DISH":
                o = store["nodes"].get(e["src"], {}).get("props", {})
                props = e["props"] if inr(o.get("timestamp")) else []
            else:
                props = e["props"]
            if props:
                kept[key] = {**e, "props": props}
        store["edges"] = kept
        linked = ({e["src"] for e in store["edges"].values()} |
                  {e["dst"] for e in store["edges"].values()})
        store["nodes"] = {n: nd for n, nd in store["nodes"].items()
                          if n in linked or nd["label"] in ("Batch", "Supplier")}
    return store


_BLAST_Q = """
MATCH (b:Batch {id: $bid})-[dl:DELIVERED_TO]->(k:CloudKitchen)
OPTIONAL MATCH (k)-[u:USED_IN]->(d:Dish)
OPTIONAL MATCH (o:Order)-[:PLACED_AT]->(k)
OPTIONAL MATCH (o)-[cr:CONTAINS_DISH]->(d)
OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
RETURN dl, k, u, d, o, cr, c
"""


def blast_radius(batch_id, apply_window=None):
    batch = get_batch(batch_id)
    cd = resolve_window(batch, apply_window)
    store = _store()
    upsert_node(store, "Batch", {k: v for k, v in batch.items() if k != "supplier"})
    node_ids, edge_keys = {batch_id}, set()
    ks, ds, os_, cs = set(), set(), set(), set()
    for r in run_query(_BLAST_Q, {"bid": batch_id}):
        dl, u, d, o, c, k = r["dl"], r["u"], r["d"], r["o"], r["c"], r["k"]
        kin = cd is None or (dl and dl.get("deliveryDate") and dl["deliveryDate"] >= cd)
        if not (kin and k):
            continue
        upsert_node(store, "CloudKitchen", k)
        upsert_edge(store, "DELIVERED_TO", batch_id, k["id"], dl)
        ks.add(k["id"])
        uin = bool(u) and u.get("batchId") == batch_id and \\
            (cd is None or (u.get("timestamp") and u["timestamp"] >= cd))
        if not (uin and d):
            continue
        upsert_node(store, "Dish", d)
        upsert_edge(store, "USED_IN", k["id"], d["id"], u)
        ds.add(d["id"])
        if not (o and (cd is None or (o.get("timestamp") and o["timestamp"] >= cd))):
            continue
        upsert_node(store, "Order", o)
        upsert_edge(store, "PLACED_AT", o["id"], k["id"], {})
        upsert_edge(store, "CONTAINS_DISH", o["id"], d["id"], r["cr"])
        os_.add(o["id"])
        if c:
            upsert_node(store, "Customer", c)
            upsert_edge(store, "PLACED_ORDER", c["id"], o["id"], {})
            cs.add(c["id"])
    for kid in ks:
        node_ids.add(kid)
        edge_keys.add(("DELIVERED_TO", batch_id, kid))
    for e in store["edges"].values():
        if e["type"] in ("USED_IN", "PLACED_AT", "CONTAINS_DISH", "PLACED_ORDER"):
            edge_keys.add((e["type"], e["src"], e["dst"]))
            node_ids.update({e["src"], e["dst"]})
    counts = {"kitchens": len(ks), "dishes": len(ds),
              "orders": len(os_), "customers": len(cs)}
    return {"batch": batch_id, "window": cd, "store": store, "nodes": node_ids,
            "edges": edge_keys, "counts": counts}


def supplier_blast(supplier_id, apply_window=None):
    sup = get_supplier(supplier_id)
    cd = resolve_window(sup, apply_window)
    store = _store()
    upsert_node(store, "Supplier", {k: v for k, v in sup.items()
                                    if k not in ("total_batches", "green", "yellow", "red")})
    node_ids, edge_keys = {supplier_id}, set()
    totals = {"kitchens": 0, "dishes": 0, "orders": 0, "customers": 0}
    for r in run_query("MATCH (:Supplier {id:$sid})-[:SUPPLIES]->(b:Batch) RETURN b.id AS id",
                       {"sid": supplier_id}):
        res = blast_radius(r["id"], apply_window)
        merge_stores(store, res["store"])
        upsert_edge(store, "SUPPLIES", supplier_id, r["id"], {})
        node_ids |= res["nodes"]
        edge_keys |= res["edges"]
        edge_keys.add(("SUPPLIES", supplier_id, r["id"]))
        for k in totals:
            totals[k] += res["counts"][k]
    return {"batch": supplier_id, "window": cd, "store": store, "nodes": node_ids,
            "edges": edge_keys, "counts": totals}


def node_details(label, node_id):
    _safe(label)
    rows = run_query("MATCH (n:`" + label + "` {id:$id}) RETURN properties(n) AS p",
                     {"id": node_id})
    if not rows:
        return None, []
    rels = run_query("""
        MATCH (n:`""" + label + """` {id:$id})-[r]-(m)
        RETURN type(r) AS rel, startNode(r) = n AS outbound,
               labels(m)[0] AS other_label, coalesce(m.id, m.name) AS other,
               properties(r) AS meta
        ORDER BY rel, other
    """, {"id": node_id})
    return rows[0]["p"], rels


def filter_options():
    return {
        "suppliers": run_query("MATCH (s:Supplier) RETURN s.id AS id, s.name AS name, "
                               "s.status AS status ORDER BY s.name"),
        "kitchens": run_query("MATCH (k:CloudKitchen) RETURN k.id AS id, k.name AS name "
                              "ORDER BY k.name"),
        "ingredients": [r["v"] for r in run_query(
            "MATCH (b:Batch) RETURN DISTINCT b.ingredientName AS v ORDER BY v")],
        "locations": [r["v"] for r in run_query(
            "MATCH (n) WHERE n.location IS NOT NULL RETURN DISTINCT n.location AS v ORDER BY v")],
    }
'''

# ============================================================ web_app.py
F["web_app.py"] = '''
"""Recall Mission Control: FastAPI graph API + Cytoscape SPA.
Run:  uvicorn web_app:app --reload   ->  http://localhost:8000"""
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import graph_api as gx          # noqa: E402
from core import risk                     # noqa: E402
from core import traceability as tr       # noqa: E402
from db.connection import run_query       # noqa: E402

app = FastAPI(title="Food Traceability Graph - Recall Mission Control")
WEB_DIR = Path(__file__).resolve().parent / "web"
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
    return {"nodes": [{"id": n, "label": d["label"], "props": _jsonify(d["props"])}
                      for n, d in store["nodes"].items()],
            "edges": [{"type": e["type"], "source": e["src"], "target": e["dst"],
                       "props": _jsonify(e["props"])} for e in store["edges"].values()]}


@app.get("/api/health")
def health():
    run_query("RETURN 1")
    return {"status": "ok"}


@app.get("/api/kpis")
def kpis():
    counts = {r["label"]: r["c"] for r in
              run_query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c")}
    flagged = run_query("""MATCH (n) WHERE (n:Batch OR n:Supplier)
        AND n.status IN ['YELLOW','RED']
        RETURN n.id AS id, n.status AS status, labels(n)[0] AS kind
        ORDER BY n.status DESC, n.id""")
    blocked = run_query(
        "MATCH (:CloudKitchen)-[m:MENU_BLOCKED]->() RETURN count(m) AS n")[0]["n"]
    holds = run_query(
        "MATCH (k:CloudKitchen {containmentStatus:'HOLD'}) RETURN count(k) AS n")[0]["n"]
    return _jsonify({"counts": counts, "flagged": flagged,
                     "blocked_menu_items": blocked, "kitchen_holds": holds})


@app.get("/api/filters")
def filters():
    return _jsonify(gx.filter_options())


@app.get("/api/network")
def network(q: Optional[str] = None, supplier: Optional[str] = None,
            kitchen: Optional[str] = None, ingredient: Optional[str] = None,
            location: Optional[str] = None, statuses: Optional[List[str]] = Query(None),
            date_from: Optional[date] = None, date_to: Optional[date] = None):
    return store_json(gx.fetch_subgraph(q=q, supplier=supplier, kitchen=kitchen,
                                        ingredient=ingredient, location=location,
                                        statuses=statuss(statuses),
                                        date_from=date_from, date_to=date_to))


def statuss(xs):
    return xs


@app.get("/api/node/{label}/{node_id}")
def node_details(label: str, node_id: str):
    try:
        props, rels = gx.node_details(label, node_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if props is None:
        raise HTTPException(404, label + " '" + node_id + "' not found")
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


def _blast_payload(res):
    return _jsonify({"batch": res["batch"], "window": res["window"],
                     "counts": res["counts"], "node_ids": list(res["nodes"]),
                     "edges": [{"type": t, "source": s, "target": d}
                               for t, s, d in res["edges"]],
                     "graph": store_json(res["store"])})


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


@app.get("/api/pull-list/{batch_id}")
def pull_list(batch_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        cd = tr.resolve_window(risk.get_batch(batch_id), WIN[window])
        return _jsonify({"batch": batch_id, "window": cd,
                         "pull_list": tr.pull_list(batch_id, cd)})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/timeline/{batch_id}")
def timeline(batch_id: str):
    try:
        return _jsonify(tr.batch_timeline(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


class FlagReq(BaseModel):
    new_status: str
    reason: str
    actor: str = "web"
    contamination_date: Optional[datetime] = None


@app.post("/api/flag/{batch_id}")
def flag(batch_id: str, req: FlagReq):
    try:
        return _jsonify(risk.flag_batch(
            batch_id, req.new_status, req.reason, req.actor,
            risk.as_ist(req.contamination_date) if req.contamination_date else None))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except risk.RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/flag-supplier/{supplier_id}")
def flag_supplier(supplier_id: str, req: FlagReq):
    try:
        return _jsonify(risk.flag_supplier(
            supplier_id, req.new_status, req.reason, req.actor,
            risk.as_ist(req.contamination_date) if req.contamination_date else None))
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
def pull_menu(batch_id: str):
    try:
        return _jsonify({"pulled": tr.pull_from_menu(batch_id, "web")})
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
        return _jsonify({"orders_notified":
                         tr.mark_customers_notified(batch_id, channel, "web")})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/report/{batch_id}")
def report(batch_id: str):
    try:
        return _jsonify(tr.recall_report(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
'''

# ============================================================ write + validate
def main():
    errs = []
    for rel, content in F.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.lstrip("\\n"), encoding="utf-8")
        if rel.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                errs.append(rel + ": " + str(e))
    if errs:
        print("SYNTAX ERRORS:")
        for e in errs:
            print("  " + e)
        raise SystemExit(1)
    print("wrote " + str(len(F)) + " files, all Python files parse OK")
    print("next:  python cli.py reset && python ps_migrate.py")
    print("       uvicorn web_app:app --reload   ->  http://localhost:8000")


if __name__ == "__main__":
    main()