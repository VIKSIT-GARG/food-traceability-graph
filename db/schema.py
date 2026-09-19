"""Constraints, indexes and graph reset."""
from db.connection import run_query

CONSTRAINTS = [
    "CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (s:Supplier) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT batch_id IF NOT EXISTS FOR (b:Batch) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT kitchen_id IF NOT EXISTS FOR (k:CloudKitchen) REQUIRE k.id IS UNIQUE",
    "CREATE CONSTRAINT dish_id IF NOT EXISTS FOR (d:Dish) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT audit_id IF NOT EXISTS FOR (e:AuditEvent) REQUIRE e.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX batch_status IF NOT EXISTS FOR (b:Batch) ON (b.status)",
    "CREATE INDEX batch_ingredient IF NOT EXISTS FOR (b:Batch) ON (b.ingredientName)",
    "CREATE INDEX order_ts IF NOT EXISTS FOR (o:Order) ON (o.timestamp)",
]


def init_schema():
    for stmt in CONSTRAINTS + INDEXES:
        run_query(stmt)


def clear_graph():
    run_query("MATCH (n) DETACH DELETE n")
