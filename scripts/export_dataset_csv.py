#!/usr/bin/env python3
"""Export all dataset entities and graph relationships to CSV files.

Supports both live Neo4j database extraction and fallback to deterministic
seed data (db/seed.py).
"""
import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

EXPORT_DIR = PROJECT_ROOT / "dataset"
NODES_DIR = EXPORT_DIR / "nodes"
RELS_DIR = EXPORT_DIR / "relationships"


def serialize_val(val):
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if hasattr(val, "to_native"):
        return val.to_native().isoformat()
    return str(val)


def write_csv(filepath, fieldnames, rows):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            clean_row = {k: serialize_val(r.get(k)) for k in fieldnames}
            writer.writerow(clean_row)
    print(f"  ✓ Written: {filepath.relative_to(PROJECT_ROOT)} ({len(rows)} records)")


def export_from_neo4j():
    from db.connection import run_query

    print("Connecting to live Neo4j database...")

    # --- 1. Nodes ---
    node_configs = [
        ("Supplier", NODES_DIR / "suppliers.csv", ["id", "name", "location", "status"]),
        (
            "Batch",
            NODES_DIR / "batches.csv",
            [
                "id",
                "ingredientName",
                "status",
                "manufactureDate",
                "expiryDate",
                "contaminationDate",
                "statusTimestamp",
                "statusReason",
                "isActive",
            ],
        ),
        ("Facility", NODES_DIR / "facilities.csv", ["id", "name", "location", "stepType"]),
        ("CloudKitchen", NODES_DIR / "cloud_kitchens.csv", ["id", "name", "location", "containmentStatus"]),
        ("Dish", NODES_DIR / "dishes.csv", ["id", "name", "price", "blocked"]),
        ("Order", NODES_DIR / "orders.csv", ["id", "timestamp"]),
        ("Customer", NODES_DIR / "customers.csv", ["id", "name", "phone", "email"]),
        ("AuditEvent", NODES_DIR / "audit_events.csv", ["id", "type", "timestamp", "actor", "detail"]),
    ]

    all_nodes = []
    for label, path, fields in node_configs:
        rows = run_query(f"""
            MATCH (n:{label})
            RETURN properties(n) AS p
            ORDER BY n.id
        """)
        data = [r["p"] for r in rows]
        write_csv(path, fields, data)
        for d in data:
            all_nodes.append({
                "id": d.get("id"),
                "label": label,
                "name": d.get("name") or d.get("ingredientName") or d.get("id"),
                "status": d.get("status") or d.get("containmentStatus") or ("BLOCKED" if d.get("blocked") else "ACTIVE"),
                "location": d.get("location") or "",
                "timestamp": d.get("manufactureDate") or d.get("timestamp") or "",
            })

    # --- 2. Relationships ---
    rel_configs = [
        (
            "SUPPLIES",
            RELS_DIR / "supplies.csv",
            "MATCH (s:Supplier)-[r:SUPPLIES]->(b:Batch) RETURN s.id AS source_id, b.id AS target_id",
            ["source_id", "target_id"],
        ),
        (
            "PROCESSED_AT",
            RELS_DIR / "processed_at.csv",
            "MATCH (b:Batch)-[r:PROCESSED_AT]->(f:Facility) RETURN b.id AS source_id, f.id AS target_id, r.timestamp AS timestamp",
            ["source_id", "target_id", "timestamp"],
        ),
        (
            "DELIVERED_TO",
            RELS_DIR / "delivered_to.csv",
            "MATCH (b:Batch)-[r:DELIVERED_TO]->(k:CloudKitchen) RETURN b.id AS source_id, k.id AS target_id, r.deliveryDate AS delivery_date, r.qtyKg AS qty_kg",
            ["source_id", "target_id", "delivery_date", "qty_kg"],
        ),
        (
            "USED_IN",
            RELS_DIR / "used_in.csv",
            "MATCH (k:CloudKitchen)-[r:USED_IN]->(d:Dish) RETURN k.id AS source_id, d.id AS target_id, r.batchId AS batch_id, r.timestamp AS timestamp, r.qtyKg AS qty_kg",
            ["source_id", "target_id", "batch_id", "timestamp", "qty_kg"],
        ),
        (
            "CONTAINS_DISH",
            RELS_DIR / "contains_dish.csv",
            "MATCH (o:Order)-[r:CONTAINS_DISH]->(d:Dish) RETURN o.id AS source_id, d.id AS target_id, r.quantity AS quantity",
            ["source_id", "target_id", "quantity"],
        ),
        (
            "PLACED_AT",
            RELS_DIR / "order_placed_at.csv",
            "MATCH (o:Order)-[r:PLACED_AT]->(k:CloudKitchen) RETURN o.id AS source_id, k.id AS target_id",
            ["source_id", "target_id"],
        ),
        (
            "PLACED_ORDER",
            RELS_DIR / "placed_order.csv",
            "MATCH (c:Customer)-[r:PLACED_ORDER]->(o:Order) RETURN c.id AS source_id, o.id AS target_id",
            ["source_id", "target_id"],
        ),
        (
            "HAS_EVENT",
            RELS_DIR / "audit_has_event.csv",
            "MATCH (x)-[r:HAS_EVENT]->(e:AuditEvent) RETURN x.id AS source_id, labels(x)[0] AS source_label, e.id AS target_id",
            ["source_id", "source_label", "target_id"],
        ),
        (
            "NOTIFIED_FOR",
            RELS_DIR / "customer_notified_for.csv",
            "MATCH (c:Customer)-[r:NOTIFIED_FOR]->(o:Order) RETURN c.id AS source_id, o.id AS target_id, r.status AS status, r.channel AS channel, r.notifiedAt AS notified_at",
            ["source_id", "target_id", "status", "channel", "notified_at"],
        ),
    ]

    all_relationships = []
    for rel_type, path, query, fields in rel_configs:
        rows = run_query(query)
        write_csv(path, fields, rows)
        for r in rows:
            all_relationships.append({
                "source_id": r["source_id"],
                "relationship_type": rel_type,
                "target_id": r["target_id"],
                "properties": {k: serialize_val(v) for k, v in r.items() if k not in ("source_id", "target_id")},
            })

    # --- 3. Unified All Nodes & All Relationships ---
    write_csv(
        EXPORT_DIR / "all_nodes.csv",
        ["id", "label", "name", "status", "location", "timestamp"],
        all_nodes,
    )
    write_csv(
        EXPORT_DIR / "all_relationships.csv",
        ["source_id", "relationship_type", "target_id", "properties"],
        all_relationships,
    )

    # --- 4. Master Denormalized Trace Table ---
    # Multi-hop traversal: Supplier -> Batch -> Kitchen -> Dish -> Order -> Customer
    end_to_end_rows = run_query("""
        MATCH (s:Supplier)-[:SUPPLIES]->(b:Batch)
        OPTIONAL MATCH (b)-[dl:DELIVERED_TO]->(k:CloudKitchen)
        OPTIONAL MATCH (k)-[u:USED_IN]->(d:Dish) WHERE u.batchId = b.id
        OPTIONAL MATCH (o:Order)-[:CONTAINS_DISH]->(d)
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
        RETURN s.id AS supplier_id,
               s.name AS supplier_name,
               s.location AS supplier_location,
               b.id AS batch_id,
               b.ingredientName AS ingredient,
               b.status AS batch_status,
               b.manufactureDate AS batch_manufacture_date,
               b.contaminationDate AS contamination_date,
               k.id AS kitchen_id,
               k.name AS kitchen_name,
               k.location AS kitchen_location,
               dl.deliveryDate AS delivery_date,
               dl.qtyKg AS delivery_qty_kg,
               d.id AS dish_id,
               d.name AS dish_name,
               d.price AS dish_price,
               d.blocked AS dish_blocked,
               u.timestamp AS kitchen_cooking_timestamp,
               u.qtyKg AS usage_qty_kg,
               o.id AS order_id,
               o.timestamp AS order_timestamp,
               c.id AS customer_id,
               c.name AS customer_name,
               c.phone AS customer_phone,
               c.email AS customer_email
        ORDER BY b.id, k.id, d.id, o.id
    """)

    write_csv(
        EXPORT_DIR / "food_traceability_end_to_end.csv",
        [
            "supplier_id",
            "supplier_name",
            "supplier_location",
            "batch_id",
            "ingredient",
            "batch_status",
            "batch_manufacture_date",
            "contamination_date",
            "kitchen_id",
            "kitchen_name",
            "kitchen_location",
            "delivery_date",
            "delivery_qty_kg",
            "dish_id",
            "dish_name",
            "dish_price",
            "dish_blocked",
            "kitchen_cooking_timestamp",
            "usage_qty_kg",
            "order_id",
            "order_timestamp",
            "customer_id",
            "customer_name",
            "customer_phone",
            "customer_email",
        ],
        end_to_end_rows,
    )


def main():
    print("=" * 70)
    print("  FOOD TRACEABILITY GRAPH — DATASET CSV EXPORTER")
    print("=" * 70)
    try:
        export_from_neo4j()
        print("\nAll dataset files successfully exported to /dataset directory!")
    except Exception as e:
        print(f"Error connecting to Neo4j ({e}). Falling back to in-memory seed dataset...")
        export_from_seed()


def export_from_seed():
    from db import seed as S

    S._normalize_batches()

    # Nodes
    write_csv(NODES_DIR / "suppliers.csv", ["id", "name", "location"], S.SUPPLIERS)
    write_csv(NODES_DIR / "facilities.csv", ["id", "name", "location", "stepType"], S.FACILITIES)
    write_csv(NODES_DIR / "cloud_kitchens.csv", ["id", "name", "location"], S.KITCHENS)
    write_csv(NODES_DIR / "dishes.csv", ["id", "name", "price"], S.DISHES)
    write_csv(
        NODES_DIR / "batches.csv",
        ["id", "ingredientName", "supplier", "manufactureDate", "expiryDate", "status", "statusReason", "statusTimestamp", "contaminationDate"],
        S.BATCHES,
    )
    write_csv(NODES_DIR / "customers.csv", ["id", "name", "phone", "email"], S.CUSTOMERS)

    # Orders
    order_rows = [{"id": o[0], "customer_id": o[1], "timestamp": o[2]} for o in S.ORDERS]
    write_csv(NODES_DIR / "orders.csv", ["id", "customer_id", "timestamp"], order_rows)

    # Relationships
    supplies = [{"source_id": b["supplier"], "target_id": b["id"]} for b in S.BATCHES]
    write_csv(RELS_DIR / "supplies.csv", ["source_id", "target_id"], supplies)

    processed = [{"source_id": p[0], "target_id": p[1], "timestamp": p[2]} for p in S.PROCESSED_AT]
    write_csv(RELS_DIR / "processed_at.csv", ["source_id", "target_id", "timestamp"], processed)

    delivered = [{"source_id": d[0], "target_id": d[1], "delivery_date": d[2], "qty_kg": d[3]} for d in S.DELIVERED_TO]
    write_csv(RELS_DIR / "delivered_to.csv", ["source_id", "target_id", "delivery_date", "qty_kg"], delivered)

    used_in = [{"source_id": u[0], "target_id": u[1], "timestamp": u[2], "qty_kg": u[3]} for u in S.USED_IN_DISH]
    write_csv(RELS_DIR / "used_in.csv", ["source_id", "target_id", "timestamp", "qty_kg"], used_in)

    contains_dish = []
    placed_order = []
    for o in S.ORDERS:
        oid, cid, _, items = o
        placed_order.append({"source_id": cid, "target_id": oid})
        for item in items:
            contains_dish.append({"source_id": oid, "target_id": item[0], "quantity": item[1]})

    write_csv(RELS_DIR / "contains_dish.csv", ["source_id", "target_id", "quantity"], contains_dish)
    write_csv(RELS_DIR / "placed_order.csv", ["source_id", "target_id"], placed_order)
    print("\nFallback seed dataset exported successfully!")


if __name__ == "__main__":
    main()
