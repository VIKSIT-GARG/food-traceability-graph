
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

def run_migration():
    for name, q in STEPS:
        run_query(q)
        print("  ok:", name)
    rels = run_query("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC")
    rel_counts = {r["t"]: r["c"] for r in rels}
    print("Relationships now:", rel_counts)
    return rel_counts


if __name__ == "__main__":
    run_migration()
