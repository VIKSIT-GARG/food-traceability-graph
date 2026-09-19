
"""Live-Cypher graph service for the frontend. Neo4j is the only source of truth."""
from datetime import datetime, time as dtime
from core.risk import as_ist, get_batch, get_supplier
from core.traceability import resolve_window
from db.connection import run_query

LABELS = ("Supplier", "Batch", "Facility", "CloudKitchen", "Dish", "Order", "Customer")

DOWN_RULES = {
    "Supplier":     [("SUPPLIES", "dst", "Batch")],
    "Batch":        [("DELIVERED_TO", "dst", "CloudKitchen")],
    "Facility":     [],
    "CloudKitchen": [("USED_IN", "dst", "Dish")],
    "Dish":         [("CONTAINS_DISH", "src", "Order")],
    "Order":        [("PLACED_ORDER", "src", "Customer")],
    "Customer":     [],
}
UP_RULES = {
    "Supplier":     [],
    "Batch":        [("SUPPLIES", "src", "Supplier")],
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
                nid = e["dst"] if (side == "dst" and e["src"] == cid) else \
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
                nid = e["dst"] if (side == "dst" and e["src"] == cid) else \
                      e["src"] if (side == "src" and e["dst"] == cid) else None
                nd = store["nodes"].get(nid) if nid else None
                if nd is None or nd["label"] != tgt or nid in seen:
                    continue
                seen.add(nid)
                out.add(nid)
                frontier.append((tgt, nid))
    return out


def fetch_subgraph(*, q=None, supplier=None, kitchen=None, ingredient=None,
                   location=None, statuses=None, date_from=None, date_to=None,
                   include_orders=False, include_facility=False):
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
        if f and include_facility:
            upsert_node(store, "Facility", f)
            upsert_edge(store, "PROCESSED_AT", b["id"], f["id"], r["pr"])
        if k:
            upsert_node(store, "CloudKitchen", k)
            upsert_edge(store, "DELIVERED_TO", b["id"], k["id"], r["dl"])
            if d and r["u"] is not None:
                upsert_node(store, "Dish", d)
                upsert_edge(store, "USED_IN", k["id"], d["id"], r["u"])
                if o and include_orders:
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
            return (lo is None or (t is not None and t >= lo)) and \
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
        uin = bool(u) and u.get("batchId") == batch_id and \
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


def contamination_map():
    """Every flagged (YELLOW/RED) Supplier+Batch and their unioned downstream."""
    flagged = run_query("""
        MATCH (n) WHERE (n:Batch OR n:Supplier) AND n.status IN ['YELLOW','RED']
        RETURN n.id AS id, labels(n)[0] AS kind ORDER BY n.status DESC, n.id""")
    store, node_ids, edge_keys = _store(), set(), set()
    counts = {"kitchens": 0, "dishes": 0, "orders": 0, "customers": 0}
    for f in flagged:
        res = supplier_blast(f["id"]) if f["kind"] == "Supplier" else blast_radius(f["id"])
        merge_stores(store, res["store"])
        node_ids |= res["nodes"]
        edge_keys |= res["edges"]
        for k in counts:
            counts[k] += res["counts"][k]
    return {"batch": "ALL FLAGGED", "window": None, "store": store, "nodes": node_ids,
            "edges": edge_keys, "counts": counts, "flagged": flagged}

