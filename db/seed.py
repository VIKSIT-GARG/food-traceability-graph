"""Deterministic Delhi-NCR cloud-kitchen demo dataset.

Timeline is anchored around a paneer contamination event on
10 Sep 2025, 14:00 IST (matches the spec's section-21 example).
"""
from datetime import datetime

from config import IST
from db import schema
from db.connection import run_query


def D(*args):
    """Build a timezone-aware IST datetime."""
    return datetime(*args, tzinfo=IST)


CONTAMINATION_EVENT = D(2025, 9, 10, 14, 0)
DEMO_NOW = D(2025, 9, 12, 12, 0)

SUPPLIERS = [
    {"id": "SUP-001", "name": "FreshFoods Pvt Ltd", "location": "Azadpur Mandi, Delhi"},
    {"id": "SUP-002", "name": "Gopal Dairy", "location": "Sector 18, Noida"},
    {"id": "SUP-003", "name": "GreenLeaf Farms", "location": "Manesar, Gurugram"},
    {"id": "SUP-004", "name": "Spice Route Traders", "location": "Khari Baoli, Delhi"},
    {"id": "SUP-005", "name": "Yamuna Poultry", "location": "Ghaziabad"},
]

FACILITIES = [
    {"id": "FAC-001", "name": "Central Processing Hub", "location": "Gurugram", "stepType": "Cleaning & Cutting"},
    {"id": "FAC-002", "name": "Cold Storage Unit 1", "location": "Noida", "stepType": "Cold Storage"},
    {"id": "FAC-003", "name": "Quality Testing Lab", "location": "Delhi", "stepType": "QC Testing"},
    {"id": "FAC-004", "name": "Packaging Unit", "location": "Manesar", "stepType": "Packaging"},
]

KITCHENS = [
    {"id": "CK-001", "name": "Spice Hub Kitchen", "location": "Cyber Hub, Gurugram"},
    {"id": "CK-002", "name": "Delhi Biryani Co.", "location": "Connaught Place, Delhi"},
    {"id": "CK-003", "name": "Urban Tiffin", "location": "Sector 62, Noida"},
    {"id": "CK-004", "name": "Curry Cloud", "location": "Saket, Delhi"},
    {"id": "CK-005", "name": "Tandoori Nights", "location": "DLF Phase 3, Gurugram"},
    {"id": "CK-006", "name": "Wok This Way", "location": "Sector 29, Noida"},
]

DISHES = [
    {"id": "DSH-001", "name": "Paneer Butter Masala", "price": 320.0},
    {"id": "DSH-002", "name": "Palak Paneer", "price": 290.0},
    {"id": "DSH-003", "name": "Paneer Tikka", "price": 340.0},
    {"id": "DSH-004", "name": "Chicken Biryani", "price": 380.0},
    {"id": "DSH-005", "name": "Butter Chicken", "price": 420.0},
    {"id": "DSH-006", "name": "Dal Makhani", "price": 240.0},
    {"id": "DSH-007", "name": "Chole Bhature", "price": 180.0},
    {"id": "DSH-008", "name": "Veg Hakka Noodles", "price": 220.0},
    {"id": "DSH-009", "name": "Chicken Tikka", "price": 360.0},
    {"id": "DSH-010", "name": "Paneer Kathi Roll", "price": 260.0},
]

BATCHES = [
    dict(id="BATCH-PANEER-001", ingredientName="Paneer", supplier="SUP-002",
         manufactureDate=D(2025, 9, 8, 6, 0), expiryDate=D(2025, 9, 12, 6, 0), status="GREEN"),
    dict(id="BATCH-PANEER-002", ingredientName="Paneer", supplier="SUP-002",
         manufactureDate=D(2025, 9, 11, 6, 0), expiryDate=D(2025, 9, 15, 6, 0), status="GREEN"),
    dict(id="BATCH-SPINACH-001", ingredientName="Spinach", supplier="SUP-003",
         manufactureDate=D(2025, 9, 8, 5, 0), expiryDate=D(2025, 9, 11, 5, 0), status="GREEN"),
    dict(id="BATCH-CHICKEN-001", ingredientName="Chicken", supplier="SUP-005",
         manufactureDate=D(2025, 9, 9, 4, 0), expiryDate=D(2025, 9, 12, 4, 0), status="GREEN"),
    dict(id="BATCH-RICE-001", ingredientName="Basmati Rice", supplier="SUP-001",
         manufactureDate=D(2025, 8, 20, 10, 0), expiryDate=D(2026, 8, 20, 10, 0), status="GREEN"),
    dict(id="BATCH-TOMATO-001", ingredientName="Tomato", supplier="SUP-001",
         manufactureDate=D(2025, 9, 9, 7, 0), expiryDate=D(2025, 9, 14, 7, 0), status="GREEN"),
    dict(id="BATCH-BUTTER-001", ingredientName="Butter", supplier="SUP-002",
         manufactureDate=D(2025, 9, 5, 9, 0), expiryDate=D(2025, 10, 5, 9, 0), status="GREEN"),
    dict(id="BATCH-SPICE-001", ingredientName="Garam Masala", supplier="SUP-004",
         manufactureDate=D(2025, 8, 25, 11, 0), expiryDate=D(2026, 2, 25, 11, 0), status="GREEN"),
    dict(id="BATCH-CHICKPEA-001", ingredientName="Chickpeas", supplier="SUP-001",
         manufactureDate=D(2025, 8, 22, 10, 0), expiryDate=D(2026, 2, 22, 10, 0), status="GREEN"),
    dict(id="BATCH-CREAM-001", ingredientName="Fresh Cream", supplier="SUP-002",
         manufactureDate=D(2025, 9, 6, 8, 0), expiryDate=D(2025, 9, 13, 8, 0), status="YELLOW",
         statusReason="Cold-chain temperature excursion reported during transit",
         statusTimestamp=D(2025, 9, 9, 20, 0), contaminationDate=D(2025, 9, 9, 18, 0)),
]

PROCESSED_AT = [
    ("BATCH-PANEER-001", "FAC-001", D(2025, 9, 9, 10, 0)),
    ("BATCH-PANEER-001", "FAC-002", D(2025, 9, 9, 14, 0)),
    ("BATCH-PANEER-001", "FAC-003", D(2025, 9, 9, 16, 0)),
    ("BATCH-PANEER-002", "FAC-001", D(2025, 9, 11, 9, 0)),
    ("BATCH-SPINACH-001", "FAC-001", D(2025, 9, 8, 12, 0)),
    ("BATCH-CHICKEN-001", "FAC-001", D(2025, 9, 9, 8, 0)),
    ("BATCH-CHICKEN-001", "FAC-002", D(2025, 9, 9, 12, 0)),
    ("BATCH-TOMATO-001", "FAC-004", D(2025, 9, 9, 15, 0)),
    ("BATCH-CREAM-001", "FAC-002", D(2025, 9, 6, 14, 0)),
    ("BATCH-RICE-001", "FAC-004", D(2025, 8, 21, 10, 0)),
]

DELIVERED_TO = [
    ("BATCH-PANEER-001", "CK-001", D(2025, 9, 10, 9, 0), 25.0),
    ("BATCH-PANEER-001", "CK-002", D(2025, 9, 10, 13, 0), 18.0),
    ("BATCH-PANEER-001", "CK-003", D(2025, 9, 10, 16, 30), 20.0),
    ("BATCH-PANEER-001", "CK-005", D(2025, 9, 11, 8, 0), 12.0),
    ("BATCH-PANEER-002", "CK-001", D(2025, 9, 11, 10, 0), 22.0),
    ("BATCH-PANEER-002", "CK-004", D(2025, 9, 11, 11, 0), 15.0),
    ("BATCH-SPINACH-001", "CK-001", D(2025, 9, 8, 18, 0), 10.0),
    ("BATCH-CHICKEN-001", "CK-002", D(2025, 9, 9, 20, 0), 30.0),
    ("BATCH-CHICKEN-001", "CK-005", D(2025, 9, 9, 21, 0), 20.0),
    ("BATCH-RICE-001", "CK-001", D(2025, 8, 22, 9, 0), 100.0),
    ("BATCH-RICE-001", "CK-003", D(2025, 8, 22, 10, 0), 80.0),
    ("BATCH-TOMATO-001", "CK-002", D(2025, 9, 9, 19, 0), 40.0),
    ("BATCH-TOMATO-001", "CK-004", D(2025, 9, 10, 10, 0), 25.0),
    ("BATCH-BUTTER-001", "CK-001", D(2025, 9, 6, 9, 0), 15.0),
    ("BATCH-BUTTER-001", "CK-002", D(2025, 9, 6, 10, 0), 15.0),
    ("BATCH-SPICE-001", "CK-001", D(2025, 8, 26, 9, 0), 5.0),
    ("BATCH-SPICE-001", "CK-004", D(2025, 8, 26, 9, 0), 5.0),
    ("BATCH-CHICKPEA-001", "CK-004", D(2025, 8, 23, 9, 0), 50.0),
    ("BATCH-CREAM-001", "CK-001", D(2025, 9, 7, 9, 0), 10.0),
    ("BATCH-CREAM-001", "CK-004", D(2025, 9, 7, 10, 0), 8.0),
]

# Usage mirrors the spec timeline: 09 Sep 11:00 CLEAR, 10 Sep 12:00 CLEAR,
# 10 Sep 15:30 SUSPECT, 11 Sep 09:00 AFFECTED.
USED_IN_DISH = [
    ("BATCH-PANEER-001", "DSH-001", D(2025, 9, 9, 11, 0), 4.0),
    ("BATCH-PANEER-001", "DSH-001", D(2025, 9, 10, 12, 0), 5.0),
    ("BATCH-PANEER-001", "DSH-001", D(2025, 9, 10, 15, 30), 6.0),
    ("BATCH-PANEER-001", "DSH-001", D(2025, 9, 11, 9, 0), 6.0),
    ("BATCH-PANEER-001", "DSH-002", D(2025, 9, 10, 12, 30), 4.0),
    ("BATCH-PANEER-001", "DSH-002", D(2025, 9, 11, 9, 30), 5.0),
    ("BATCH-PANEER-001", "DSH-003", D(2025, 9, 10, 15, 45), 5.0),
    ("BATCH-PANEER-001", "DSH-003", D(2025, 9, 11, 10, 0), 5.0),
    ("BATCH-PANEER-001", "DSH-010", D(2025, 9, 10, 19, 30), 3.0),
    ("BATCH-PANEER-001", "DSH-010", D(2025, 9, 11, 9, 15), 3.0),
    ("BATCH-PANEER-002", "DSH-001", D(2025, 9, 11, 19, 0), 5.0),
    ("BATCH-PANEER-002", "DSH-003", D(2025, 9, 11, 19, 30), 4.0),
    ("BATCH-SPINACH-001", "DSH-002", D(2025, 9, 9, 12, 0), 3.0),
    ("BATCH-CHICKEN-001", "DSH-004", D(2025, 9, 10, 11, 30), 8.0),
    ("BATCH-CHICKEN-001", "DSH-005", D(2025, 9, 10, 13, 0), 7.0),
    ("BATCH-CHICKEN-001", "DSH-009", D(2025, 9, 10, 14, 0), 6.0),
    ("BATCH-RICE-001", "DSH-004", D(2025, 9, 10, 11, 45), 10.0),
    ("BATCH-RICE-001", "DSH-008", D(2025, 9, 10, 12, 15), 4.0),
    ("BATCH-TOMATO-001", "DSH-001", D(2025, 9, 10, 13, 0), 6.0),
    ("BATCH-TOMATO-001", "DSH-006", D(2025, 9, 10, 12, 45), 5.0),
    ("BATCH-TOMATO-001", "DSH-007", D(2025, 9, 11, 10, 30), 6.0),
    ("BATCH-BUTTER-001", "DSH-001", D(2025, 9, 10, 12, 0), 3.0),
    ("BATCH-BUTTER-001", "DSH-005", D(2025, 9, 10, 13, 0), 4.0),
    ("BATCH-BUTTER-001", "DSH-006", D(2025, 9, 10, 12, 50), 3.0),
    ("BATCH-SPICE-001", "DSH-004", D(2025, 9, 10, 11, 45), 1.0),
    ("BATCH-SPICE-001", "DSH-007", D(2025, 9, 11, 10, 15), 1.0),
    ("BATCH-CHICKPEA-001", "DSH-007", D(2025, 9, 10, 12, 30), 8.0),
    ("BATCH-CREAM-001", "DSH-001", D(2025, 9, 10, 12, 10), 2.0),
    ("BATCH-CREAM-001", "DSH-006", D(2025, 9, 10, 12, 55), 2.0),
]

CUSTOMERS = [
    {"id": "CUS-001", "name": "Aarav Sharma", "phone": "+91-98110-11201", "email": "aarav.sharma@example.com"},
    {"id": "CUS-002", "name": "Diya Patel", "phone": "+91-98110-11202", "email": "diya.patel@example.com"},
    {"id": "CUS-003", "name": "Rohan Mehta", "phone": "+91-98110-11203", "email": "rohan.mehta@example.com"},
    {"id": "CUS-004", "name": "Ananya Iyer", "phone": "+91-98110-11204", "email": "ananya.iyer@example.com"},
    {"id": "CUS-005", "name": "Kabir Singh", "phone": "+91-98110-11205", "email": "kabir.singh@example.com"},
    {"id": "CUS-006", "name": "Ishita Verma", "phone": "+91-98110-11206", "email": "ishita.verma@example.com"},
    {"id": "CUS-007", "name": "Advait Nair", "phone": "+91-98110-11207", "email": "advait.nair@example.com"},
    {"id": "CUS-008", "name": "Myra Gupta", "phone": "+91-98110-11208", "email": "myra.gupta@example.com"},
    {"id": "CUS-009", "name": "Vihaan Malhotra", "phone": "+91-98110-11209", "email": "vihaan.malhotra@example.com"},
    {"id": "CUS-010", "name": "Saanvi Rao", "phone": "+91-98110-11210", "email": "saanvi.rao@example.com"},
    {"id": "CUS-011", "name": "Arjun Khanna", "phone": "+91-98110-11211", "email": "arjun.khanna@example.com"},
    {"id": "CUS-012", "name": "Zara Siddiqui", "phone": "+91-98110-11212", "email": "zara.siddiqui@example.com"},
]

# (order_id, customer_id, timestamp, [(dish_id, qty), ...])
ORDERS = [
    ("ORD-1001", "CUS-001", D(2025, 9, 9, 12, 30), [("DSH-001", 1)]),
    ("ORD-1002", "CUS-002", D(2025, 9, 9, 19, 45), [("DSH-002", 1), ("DSH-006", 1)]),
    ("ORD-1003", "CUS-003", D(2025, 9, 10, 12, 15), [("DSH-001", 2)]),
    ("ORD-1004", "CUS-004", D(2025, 9, 10, 12, 50), [("DSH-004", 1), ("DSH-008", 1)]),
    ("ORD-1005", "CUS-005", D(2025, 9, 10, 13, 20), [("DSH-002", 1)]),
    ("ORD-1006", "CUS-006", D(2025, 9, 10, 13, 40), [("DSH-005", 1), ("DSH-007", 1)]),
    ("ORD-1007", "CUS-007", D(2025, 9, 10, 16, 5), [("DSH-001", 1)]),
    ("ORD-1008", "CUS-008", D(2025, 9, 10, 16, 40), [("DSH-003", 2)]),
    ("ORD-1009", "CUS-009", D(2025, 9, 10, 20, 15), [("DSH-010", 2), ("DSH-008", 1)]),
    ("ORD-1010", "CUS-010", D(2025, 9, 10, 21, 0), [("DSH-002", 1), ("DSH-009", 1)]),
    ("ORD-1011", "CUS-011", D(2025, 9, 11, 9, 45), [("DSH-001", 1), ("DSH-004", 1)]),
    ("ORD-1012", "CUS-012", D(2025, 9, 11, 10, 5), [("DSH-003", 1)]),
    ("ORD-1013", "CUS-001", D(2025, 9, 11, 10, 30), [("DSH-010", 1), ("DSH-006", 1)]),
    ("ORD-1014", "CUS-003", D(2025, 9, 11, 12, 10), [("DSH-002", 2)]),
    ("ORD-1015", "CUS-005", D(2025, 9, 11, 12, 45), [("DSH-007", 1), ("DSH-008", 1)]),
    ("ORD-1016", "CUS-002", D(2025, 9, 11, 19, 30), [("DSH-001", 1)]),
    ("ORD-1017", "CUS-004", D(2025, 9, 11, 20, 0), [("DSH-005", 1)]),
    ("ORD-1018", "CUS-006", D(2025, 9, 12, 12, 30), [("DSH-001", 1), ("DSH-007", 1)]),
    ("ORD-1019", "CUS-008", D(2025, 9, 12, 13, 0), [("DSH-009", 1)]),
    ("ORD-1020", "CUS-010", D(2025, 9, 12, 13, 20), [("DSH-004", 1)]),
    ("ORD-1021", "CUS-007", D(2025, 9, 12, 19, 45), [("DSH-003", 1)]),
]

AUDIT_EVENTS = [
    dict(batch="BATCH-CREAM-001", type="STATUS_TRANSITION", fromStatus="GREEN", toStatus="YELLOW",
         reason="Cold-chain temperature excursion reported during transit", detail=None,
         actor="ops@freshchain", timestamp=D(2025, 9, 9, 20, 0)),
]


def _normalize_batches():
    for b in BATCHES:
        for key in ("statusReason", "statusTimestamp", "contaminationDate"):
            b.setdefault(key, None)
        b["isActive"] = b["expiryDate"] >= DEMO_NOW


def seed(clear=True):
    if clear:
        schema.clear_graph()
    schema.init_schema()
    _normalize_batches()

    run_query("UNWIND $rows AS r CREATE (:Supplier {id: r.id, name: r.name, location: r.location})",
              {"rows": SUPPLIERS})
    run_query("UNWIND $rows AS r CREATE (:Facility {id: r.id, name: r.name, "
              "location: r.location, stepType: r.stepType})", {"rows": FACILITIES})
    run_query("UNWIND $rows AS r CREATE (:CloudKitchen {id: r.id, name: r.name, location: r.location})",
              {"rows": KITCHENS})
    run_query("UNWIND $rows AS r CREATE (:Dish {id: r.id, name: r.name, price: r.price, blocked: false})",
              {"rows": DISHES})
    run_query("""
        UNWIND $rows AS r
        CREATE (b:Batch {id: r.id, ingredientName: r.ingredientName,
                         manufactureDate: r.manufactureDate, expiryDate: r.expiryDate,
                         isActive: r.isActive, status: r.status,
                         statusReason: r.statusReason, statusTimestamp: r.statusTimestamp,
                         contaminationDate: r.contaminationDate})
        WITH b, r MATCH (s:Supplier {id: r.supplier})
        CREATE (s)-[:SUPPLIED]->(b)
    """, {"rows": BATCHES})

    run_query("""
        UNWIND $rows AS r
        MATCH (b:Batch {id: r.batch}), (f:Facility {id: r.facility})
        CREATE (b)-[:PROCESSED_AT {timestamp: r.timestamp}]->(f)
    """, {"rows": [{"batch": b, "facility": f, "timestamp": ts} for b, f, ts in PROCESSED_AT]})

    run_query("""
        UNWIND $rows AS r
        MATCH (b:Batch {id: r.batch}), (k:CloudKitchen {id: r.kitchen})
        CREATE (b)-[:DELIVERED_TO {deliveryDate: r.date, qtyKg: r.qty}]->(k)
    """, {"rows": [{"batch": b, "kitchen": k, "date": d, "qty": q} for b, k, d, q in DELIVERED_TO]})

    run_query("""
        UNWIND $rows AS r
        MATCH (b:Batch {id: r.batch}), (d:Dish {id: r.dish})
        CREATE (b)-[:USED_IN_DISH {timestamp: r.ts, quantity: r.qty}]->(d)
    """, {"rows": [{"batch": b, "dish": d, "ts": ts, "qty": q} for b, d, ts, q in USED_IN_DISH]})

    run_query("UNWIND $rows AS r CREATE (:Customer {id: r.id, name: r.name, phone: r.phone, email: r.email})",
              {"rows": CUSTOMERS})

    run_query("""
        UNWIND $orders AS o
        MATCH (c:Customer {id: o.customer})
        CREATE (ord:Order {id: o.id, timestamp: o.ts})
        CREATE (c)-[:PLACED_ORDER]->(ord)
        WITH ord, o
        UNWIND o.items AS item
        MATCH (d:Dish {id: item.dish})
        CREATE (ord)-[:CONTAINS_DISH {quantity: item.qty}]->(d)
    """, {"orders": [{"id": oid, "customer": cid, "ts": ts,
                      "items": [{"dish": d, "qty": q} for d, q in items]}
                     for oid, cid, ts, items in ORDERS]})

    run_query("""
        UNWIND $rows AS r
        MATCH (b:Batch {id: r.batch})
        CREATE (e:AuditEvent {id: 'SEED-' + r.type + '-' + r.batch, type: r.type,
                fromStatus: r.fromStatus, toStatus: r.toStatus, reason: r.reason,
                detail: r.detail, actor: r.actor, timestamp: r.timestamp})
        CREATE (b)-[:HAS_EVENT]->(e)
    """, {"rows": AUDIT_EVENTS})

    nodes = run_query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC")
    rels = run_query("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC")
    return {"nodes": nodes, "relationships": rels}
