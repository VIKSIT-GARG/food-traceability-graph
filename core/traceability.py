
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


def supplier_intelligence(supplier_id):
    """Aggregates supplier-level risk intelligence and downstream network impact."""
    sup = get_supplier(supplier_id)
    batches = run_query("""
        MATCH (s:Supplier {id: $sid})-[:SUPPLIES]->(b:Batch)
        OPTIONAL MATCH (b)-[dl:DELIVERED_TO]->(k:CloudKitchen)
        RETURN b.id AS id, b.ingredientName AS ingredient, b.manufactureDate AS manufactured,
               b.status AS status, count(dl) > 0 AS active
        ORDER BY b.manufactureDate DESC
    """, {"sid": supplier_id})
    recalls = run_query("""
        MATCH (s:Supplier {id: $sid})-[:SUPPLIES]->(b:Batch)
        OPTIONAL MATCH (b)-[:HAS_EVENT]->(e:AuditEvent)
        RETURN count(DISTINCT e) AS n
    """, {"sid": supplier_id})[0]["n"]
    net = run_query("""
        MATCH (s:Supplier {id: $sid})-[:SUPPLIES]->(b:Batch)
        OPTIONAL MATCH (b)-[:DELIVERED_TO]->(k:CloudKitchen)
        OPTIONAL MATCH (k)-[u:USED_IN]->(d:Dish) WHERE u.batchId = b.id
        OPTIONAL MATCH (o:Order)-[:PLACED_AT]->(k)
        OPTIONAL MATCH (o)-[:CONTAINS_DISH]->(d)
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
        RETURN count(DISTINCT k) AS kitchens,
               count(DISTINCT d) AS dishes,
               count(DISTINCT o) AS orders,
               count(DISTINCT c) AS customers
    """, {"sid": supplier_id})[0]
    return {
        "summary": {
            "supplier": sup,
            "total_batches": sup.get("total_batches", len(batches)),
            "active_batches": sum(1 for b in batches if b["active"]),
            "green": sup.get("green", 0),
            "yellow": sup.get("yellow", 0),
            "red": sup.get("red", 0),
        },
        "recall_events": recalls,
        "network_impact": {
            "kitchens": net["kitchens"],
            "dishes": net["dishes"],
            "orders": net["orders"],
            "customers": net["customers"],
        },
        "batches": batches,
    }


# Backwards compatibility alias
block_affected_dishes = pull_from_menu
