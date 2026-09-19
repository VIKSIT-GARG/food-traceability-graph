"""Read-only Cypher console with layered guardrails (WS-E mode 2).
Layer 1: regex denylist (write clauses)  Layer 2: structure checks (single stmt,
RETURN required, label/rel-type whitelist)  Layer 3: Neo4j READ session — the DB
itself refuses writes even if a check is bypassed. Plus a hard timeout & auto-LIMIT."""
import re
from neo4j import READ_ACCESS
from neo4j.graph import Node, Relationship, Path as NeoPath
from db.connection import get_driver

WRITE_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD\s+CSV|FOREACH)\b", re.I)
TOKEN_RE = re.compile(r":`?([A-Za-z_][A-Za-z0-9_]*)`?")
ALLOWED_TOKENS = {
    "Supplier", "Batch", "Facility", "CloudKitchen", "Dish", "Order", "Customer",
    "AuditEvent",
    "SUPPLIES", "DELIVERED_TO", "USED_IN", "PLACED_AT", "PLACED_ORDER",
    "CONTAINS_DISH", "PROCESSED_AT", "MENU_BLOCKED", "HAS_EVENT", "NOTIFIED_FOR",
}
MAX_ROWS = 200
TIMEOUT_S = 5.0


class CypherRejected(ValueError):
    pass


def _stringify(v):
    if isinstance(v, Node):
        return str(v.get("id") or v.get("name") or v.element_id)
    if isinstance(v, Relationship):
        return v.type
    if isinstance(v, NeoPath):
        return " -> ".join(n.get("id") or n.get("name") or "?" for n in v.nodes)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_stringify(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_stringify(x)}" for k, x in v.items()) + "}"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def run_readonly_cypher(query):
    q = (query or "").strip()
    if not q:
        raise CypherRejected("Empty query.")
    if ";" in q:
        raise CypherRejected("Rejected: multiple statements (';') are not allowed.")
    if WRITE_RE.search(q):
        raise CypherRejected("Rejected: only READ queries — "
                             "CREATE/MERGE/DELETE/SET/DROP/CALL are blocked.")
    if not re.search(r"\bRETURN\b", q, re.I):
        raise CypherRejected("Rejected: query must contain RETURN.")
    bad = {t for t in TOKEN_RE.findall(q) if t not in ALLOWED_TOKENS}
    if bad:
        raise CypherRejected("Rejected: unknown labels/relationship types: "
                             + ", ".join(sorted(bad))
                             + ". Allowed: " + ", ".join(sorted(ALLOWED_TOKENS)))
    if not re.search(r"\bLIMIT\b", q, re.I):
        q += f" LIMIT {MAX_ROWS}"

    with get_driver().session(default_access_mode=READ_ACCESS, fetch_size=500) as session:
        result = session.run(q, timeout=TIMEOUT_S)
        keys = list(result.keys())
        records = [list(r.values()) for r in result]   # consume inside session

    nodes, edges = {}, []
    def walk(v):
        if isinstance(v, Node):
            nid = v.get("id") or v.element_id
            if nid not in nodes:
                nodes[nid] = {"label": sorted(v.labels)[0] if v.labels else "Node",
                              "props": dict(v)}
        elif isinstance(v, Relationship):
            walk(v.start_node)
            walk(v.end_node)
            edges.append({"type": v.type,
                          "source": v.start_node.get("id") or v.start_node.element_id,
                          "target": v.end_node.get("id") or v.end_node.element_id,
                          "props": [dict(v)]})
        elif isinstance(v, NeoPath):
            for n in v.nodes:
                walk(n)
            for r in v.relationships:
                walk(r)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)

    for row in records:
        for v in row:
            walk(v)

    from datetime import datetime as _dt, date as _date
    def J(o):
        if isinstance(o, (_dt, _date)):
            return o.isoformat()
        if isinstance(o, dict):
            return {str(k): J(x) for k, x in o.items()}
        if isinstance(o, (list, tuple)):
            return [J(x) for x in o]
        return o

    return {"nodes": [{"id": i, "label": d["label"], "props": J(d["props"])}
                      for i, d in nodes.items()],
            "edges": edges,
            "columns": keys,
            "rows": [[_stringify(v) for v in row] for row in records[:MAX_ROWS]],
            "query": q}