#!/usr/bin/env python3
"""Zero-install demo backend: the SAME API contract as web_app.py, but the graph
lives in Python memory (built from db/seed.py demo data, v2 PS model).
Run:  python demo_server.py    ->  http://localhost:8000   (no Neo4j, no Docker)
Writes are live but in-memory; restart or POST /api/demo/reset rewinds."""
import os
import random
import threading
from datetime import date, datetime
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import IST
from db import seed as S

WEB_DIR = Path(__file__).resolve().parent / "web"
WIN = {"auto": None, "on": True, "off": False}
ALLOWED = {"GREEN": {"YELLOW"}, "YELLOW": {"RED", "GREEN"}, "RED": set()}
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


class RiskTransitionError(ValueError):
    pass


def validate_transition(cur, new):
    if new not in ALLOWED.get(cur, set()):
        raise RiskTransitionError(
            f"Invalid transition {cur} -> {new}. Allowed from {cur}: "
            f"{sorted(ALLOWED.get(cur, set())) or ['none (terminal)']}")


def as_ist(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt.astimezone(IST)


def resolve_window(ent, apply_window=None):
    cd = ent.get("contaminationDate")
    if apply_window is None:
        return cd if ent["status"] == "YELLOW" and cd else None
    if apply_window:
        if not cd:
            raise ValueError("No contaminationDate recorded; cannot apply temporal window.")
        return cd
    return None


def J(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): J(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [J(v) for v in o]
    return o


class Mem:
    """In-memory supply-chain graph in the v2 problem-statement model."""

    def __init__(self):
        self.lock = threading.RLock()
        self.build()

    # ------------------------------------------------------------- build / reset
    def build(self):
        rng = random.Random(42)
        S._normalize_batches()
        self.N, self.E = {}, []
        self.bsup = {x["id"]: x["supplier"] for x in S.BATCHES}

        def n(label, props):
            self.N[props["id"]] = {"label": label, "props": dict(props)}

        def e(t, s, d, p=None):
            self.E.append({"type": t, "src": s, "dst": d, "props": dict(p or {})})

        for x in S.SUPPLIERS:
            n("Supplier", {**x, "status": "GREEN", "statusReason": None,
                           "statusTimestamp": None, "contaminationDate": None})
        for x in S.FACILITIES:
            n("Facility", x)
        for x in S.KITCHENS:
            n("CloudKitchen", {**x, "containmentStatus": None})
        for x in S.DISHES:
            n("Dish", {**x, "blocked": False})
        for x in S.BATCHES:
            n("Batch", {k: v for k, v in x.items() if k != "supplier"})
        for x in S.CUSTOMERS:
            n("Customer", x)
        for oid, cid, ts, items in S.ORDERS:
            n("Order", {"id": oid, "timestamp": ts})

        for x in S.BATCHES:
            e("SUPPLIES", x["supplier"], x["id"])
        for b, f, ts in S.PROCESSED_AT:
            e("PROCESSED_AT", b, f, {"timestamp": ts})
        for b, k, d, q in S.DELIVERED_TO:
            e("DELIVERED_TO", b, k, {"deliveryDate": d, "qtyKg": q})
        for b, dsh, ts, q in S.USED_IN_DISH:
            for bb, k, _, _ in S.DELIVERED_TO:          # same expansion ps_migrate.py does
                if bb == b:
                    e("USED_IN", k, dsh, {"batchId": b, "timestamp": ts, "qtyKg": q})
        for oid, cid, ts, items in S.ORDERS:
            e("PLACED_ORDER", cid, oid)
            for dsh, q in items:
                e("CONTAINS_DISH", oid, dsh, {"quantity": q})
        kuse = {}
        for x in self.E:
            if x["type"] == "USED_IN":
                kuse.setdefault(x["dst"], set()).add(x["src"])
        for oid, cid, ts, items in S.ORDERS:
            cands = sorted(set().union(*[kuse.get(d, set()) for d, _ in items]))
            if cands:
                e("PLACED_AT", oid, cands[rng.randrange(len(cands))])
        for i, ev in enumerate(S.AUDIT_EVENTS):
            eid = f"SEED-{i}-{ev['batch']}"
            n("AuditEvent", {"id": eid, "type": ev["type"], "fromStatus": ev["fromStatus"],
                             "toStatus": ev["toStatus"], "reason": ev["reason"],
                             "detail": ev["detail"], "actor": ev["actor"],
                             "timestamp": ev["timestamp"]})
            e("HAS_EVENT", ev["batch"], eid)

    # ------------------------------------------------------------------ helpers
    def lab(self, nid):
        return self.N[nid]["label"]

    def props(self, nid):
        return self.N[nid]["props"]

    def outs(self, nid, t=None):
        return [x for x in self.E if x["src"] == nid and (t is None or x["type"] == t)]

    def ins(self, nid, t=None):
        return [x for x in self.E if x["dst"] == nid and (t is None or x["type"] == t)]

    def batch(self, bid):
        if bid not in self.N or self.lab(bid) != "Batch":
            raise KeyError(f"Batch '{bid}' not found")
        p = dict(self.props(bid))
        p["supplier"] = dict(self.props(self.bsup[bid]))
        return p

    def supplier(self, sid):
        if sid not in self.N or self.lab(sid) != "Supplier":
            raise KeyError(f"Supplier '{sid}' not found")
        p = dict(self.props(sid))
        bs = [x["dst"] for x in self.outs(sid, "SUPPLIES")]
        p["total_batches"] = len(bs)
        p["green"] = sum(self.props(b)["status"] == "GREEN" for b in bs)
        p["yellow"] = sum(self.props(b)["status"] == "YELLOW" for b in bs)
        p["red"] = sum(self.props(b)["status"] == "RED" for b in bs)
        return p

    def audit(self, host_id, fields):
        eid = "EVT-" + datetime.now(IST).strftime("%H%M%S%f")
        self.N[eid] = {"label": "AuditEvent",
                       "props": {"id": eid, "timestamp": datetime.now(IST), **fields}}
        self.E.append({"type": "HAS_EVENT", "src": host_id, "dst": eid, "props": {}})

    def audit_trail(self, bid):
        rows = [{"id": x["props"]["id"], "type": x["props"].get("type"),
                 "fromStatus": x["props"].get("fromStatus"),
                 "toStatus": x["props"].get("toStatus"),
                 "reason": x["props"].get("reason"), "detail": x["props"].get("detail"),
                 "actor": x["props"].get("actor"), "timestamp": x["props"]["timestamp"]}
                for x in self.ins(bid, "HAS_EVENT")]
        return sorted(rows, key=lambda r: r["timestamp"])

    def store_json(self, nodes=None, edges=None):
        ns = self.N if nodes is None else {i: self.N[i] for i in nodes}
        es = self.E if edges is None else edges
        groups = {}
        for x in es:
            groups.setdefault((x["type"], x["src"], x["dst"]), []).append(x["props"])
        return {"nodes": [{"id": i, "label": self.N[i]["label"], "props": J(self.N[i]["props"])}
                          for i in ns],
                "edges": [{"type": t, "source": s, "target": d, "props": [J(p) for p in ps]}
                          for (t, s, d), ps in groups.items()]}

    def neighborhood(self, nid):
        nodes, edges = {nid}, []
        for x in self.E:
            if x["src"] == nid or x["dst"] == nid:
                nodes.update({x["src"], x["dst"]})
                edges.append(x)
        return nodes, edges

    def trace(self, label, nid, direction="down", max_depth=6):
        rules = DOWN_RULES if direction == "down" else UP_RULES
        seen, nodes, edges = {(label, nid)}, {nid}, []
        frontier = [(label, nid, 0)]
        while frontier:
            cl, cid, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            hop_n, hop_e = self.neighborhood(cid)
            for x in hop_e:
                if x not in edges:
                    edges.append(x)
            for rel, side, tgt in rules.get(cl, []):
                for x in hop_e:
                    if x["type"] != rel:
                        continue
                    m = (x["dst"] if (side == "dst" and x["src"] == cid)
                         else x["src"] if (side == "src" and x["dst"] == cid) else None)
                    if m is None or self.lab(m) != tgt or (tgt, m) in seen:
                        continue
                    seen.add((tgt, m))
                    nodes.add(m)
                    frontier.append((tgt, m, depth + 1))
        return nodes, edges

    def _orders_for(self, k, d, cd):
        """Orders placed at kitchen k containing dish d (temporal filter applied)."""
        found = []
        for cr in self.ins(d, "CONTAINS_DISH"):
            o = cr["src"]
            pa = self.outs(o, "PLACED_AT")
            if not pa or pa[0]["dst"] != k:
                continue
            ot = self.props(o).get("timestamp")
            if cd and (ot is None or ot < cd):
                continue
            found.append((o, cr))
        return found

    def fetch_subgraph(self, q=None, supplier=None, kitchen=None, ingredient=None,
                       location=None, statuses=None, date_from=None, date_to=None,
                       include_orders=False, include_facility=False):
        ql = (q or "").lower() or None
        loc = (location or "").lower() or None
        nodes, edges = set(), []

        for bid in [i for i, x in self.N.items() if x["label"] == "Batch"]:
            bp, sid, sp = self.props(bid), self.bsup[bid], self.props(self.bsup[bid])
            dels = self.outs(bid, "DELIVERED_TO")
            ks = [x["dst"] for x in dels if (kitchen is None or x["dst"] == kitchen)]
            if kitchen and not ks:
                continue
            if ingredient and bp["ingredientName"] != ingredient:
                continue
            if supplier and sid != supplier:
                continue
            if statuses and bp["status"] not in statuses:
                continue
            if ql and not (ql in bid.lower() or ql in bp["ingredientName"].lower()
                           or ql in sp["name"].lower()
                           or any(ql in self.props(k)["name"].lower() for k in ks)):
                continue
            facs = [x["dst"] for x in self.outs(bid, "PROCESSED_AT")]
            if loc and not any(loc in (self.props(v).get("location") or "").lower()
                               for v in [sid] + ks + facs):
                continue
            nodes.update({bid, sid})
            for x in self.ins(bid, "SUPPLIES"):
                edges.append(x)
            if include_facility:
                for f, x in [(x["dst"], x) for x in self.outs(bid, "PROCESSED_AT")]:
                    nodes.add(f)
                    edges.append(x)
            for x in dels:
                k = x["dst"]
                nodes.add(k)
                edges.append(x)
                for u in self.outs(k, "USED_IN"):
                    d = u["dst"]
                    nodes.add(d)
                    edges.append(u)
                    if include_orders:
                        for o, cr in self._orders_for(k, d, None):
                            nodes.add(o)
                            edges.append(cr)
                            edges.extend(self.outs(o, "PLACED_AT"))
                            edges.extend(self.ins(o, "PLACED_ORDER"))
                            for po in self.ins(o, "PLACED_ORDER"):
                                nodes.add(po["src"])

        if date_from or date_to:
            lo = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=IST) if date_from else None
            hi = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=IST) if date_to else None

            def inr(t):
                return (lo is None or (t is not None and t >= lo)) and \
                       (hi is None or (t is not None and t <= hi))

            kept = []
            for x in edges:
                t = x["type"]
                if t == "DELIVERED_TO":
                    ok = inr(x["props"].get("deliveryDate"))
                elif t == "USED_IN":
                    ok = inr(x["props"].get("timestamp"))
                elif t == "CONTAINS_DISH":
                    ok = inr(self.props(x["src"]).get("timestamp"))
                elif t == "PLACED_ORDER":
                    ok = inr(self.props(x["dst"]).get("timestamp"))
                else:
                    ok = True
                if ok:
                    kept.append(x)
            edges = kept
            linked = {x["src"] for x in edges} | {x["dst"] for x in edges}
            nodes = {i for i in nodes if i in linked or self.lab(i) in ("Batch", "Supplier")}
        return nodes, edges

    # ------------------------------------------------------------- impact logic
    def blast(self, bid, apply_window=None):
        b = self.batch(bid)
        cd = resolve_window(b, apply_window)
        nodes, edges = {bid}, []
        ks, ds, os_, cs = set(), set(), set(), set()
        for dl in self.outs(bid, "DELIVERED_TO"):
            dd = dl["props"].get("deliveryDate")
            if cd and (dd is None or dd < cd):
                continue
            k = dl["dst"]
            ks.add(k)
            nodes.add(k)
            edges.append(dl)
            for u in self.outs(k, "USED_IN"):
                if u["props"].get("batchId") != bid:
                    continue
                ut = u["props"].get("timestamp")
                if cd and (ut is None or ut < cd):
                    continue
                d = u["dst"]
                ds.add(d)
                nodes.add(d)
                edges.append(u)
                for o, cr in self._orders_for(k, d, cd):
                    os_.add(o)
                    nodes.add(o)
                    edges.append(cr)
                    edges.extend(self.outs(o, "PLACED_AT"))
                    for po in self.ins(o, "PLACED_ORDER"):
                        cs.add(po["src"])
                        nodes.add(po["src"])
                        edges.append(po)
        counts = {"kitchens": len(ks), "dishes": len(ds),
                  "orders": len(os_), "customers": len(cs)}
        return {"batch": bid, "window": cd, "nodes": nodes, "edges": edges, "counts": counts}

    def supplier_blast(self, sid, apply_window=None):
        sup = self.supplier(sid)
        cd = resolve_window(sup, apply_window)
        nodes, edges = {sid}, []
        totals = {"kitchens": 0, "dishes": 0, "orders": 0, "customers": 0}
        for x in self.outs(sid, "SUPPLIES"):
            res = self.blast(x["dst"], apply_window)
            nodes |= res["nodes"]
            edges.extend(res["edges"])
            edges.append(x)
            for kk in totals:
                totals[kk] += res["counts"][kk]
        return {"batch": sid, "window": cd, "nodes": nodes, "edges": edges, "counts": totals}

    def affected_usage(self, bid, cd):
        rows = {}
        for dl in self.outs(bid, "DELIVERED_TO"):
            dd = dl["props"].get("deliveryDate")
            if cd and (dd is None or dd < cd):
                continue
            k = dl["dst"]
            for u in self.outs(k, "USED_IN"):
                if u["props"].get("batchId") != bid:
                    continue
                ut = u["props"].get("timestamp")
                if cd and (ut is None or ut < cd):
                    continue
                key = (k, u["dst"])
                r = rows.setdefault(key, {"kitchen_id": k, "kitchen": self.props(k)["name"],
                                          "dish_id": u["dst"], "dish": self.props(u["dst"])["name"],
                                          "used_at": [], "qty_kg": 0.0})
                r["used_at"].append(ut)
                r["qty_kg"] += u["props"].get("qtyKg") or 0
        for r in rows.values():
            r["used_at"].sort()
            r["qty_kg"] = round(r["qty_kg"] * 10) / 10
        return list(rows.values())

    def pull_list(self, bid, cd=None):
        if cd is None:
            cd = resolve_window(self.batch(bid), None)
        out = {}
        for dl in self.outs(bid, "DELIVERED_TO"):
            dd = dl["props"].get("deliveryDate")
            if cd and (dd is None or dd < cd):
                continue
            k = dl["dst"]
            dishes = {u["dst"]: {"id": u["dst"], "name": self.props(u["dst"])["name"]}
                      for u in self.outs(k, "USED_IN")
                      if u["props"].get("batchId") == bid and
                      (cd is None or (u["props"].get("timestamp") is not None
                                      and u["props"]["timestamp"] >= cd))}
            if dishes:
                out[k] = {"kitchen_id": k, "kitchen": self.props(k)["name"],
                          "location": self.props(k).get("location"),
                          "pull_dishes": sorted(dishes.values(), key=lambda x: x["name"])}
        blocked = {(x["src"], x["dst"]) for x in self.E
                   if x["type"] == "MENU_BLOCKED" and x["props"].get("batchId") == bid}
        for r in out.values():
            r["pulled"] = bool(r["pull_dishes"]) and all(
                (r["kitchen_id"], d["id"]) in blocked for d in r["pull_dishes"])
        return sorted(out.values(), key=lambda x: x["kitchen"])

    def affected_orders(self, bid, cd):
        recs = {}
        for u in self.affected_usage(bid, cd):
            for o, cr in self._orders_for(u["kitchen_id"], u["dish_id"], cd):
                r = recs.setdefault(o, {"order_id": o, "order_time": self.props(o)["timestamp"],
                                        "kitchen": u["kitchen"], "dishes": set()})
                r["dishes"].add(u["dish"])
        out = []
        for o, r in recs.items():
            po = self.ins(o, "PLACED_ORDER")
            c = po[0]["src"] if po else None
            ntf = [x for x in self.ins(o, "NOTIFIED_FOR") if c and x["src"] == c]
            out.append({"order_id": o, "order_time": r["order_time"], "kitchen": r["kitchen"],
                        "customer_id": c,
                        "customer": self.props(c)["name"] if c else None,
                        "phone": self.props(c).get("phone") if c else None,
                        "email": self.props(c).get("email") if c else None,
                        "dishes": sorted(r["dishes"]),
                        "notification_status": ntf[0]["props"].get("status", "PENDING") if ntf else "PENDING"})
        return sorted(out, key=lambda x: x["order_time"])

    def impact(self, bid, apply_window=None):
        b = self.batch(bid)
        cd = resolve_window(b, apply_window)
        dels = [{"kitchen_id": x["dst"], "kitchen": self.props(x["dst"])["name"],
                 "location": self.props(x["dst"]).get("location"),
                 "delivery_date": x["props"].get("deliveryDate"),
                 "qty_kg": x["props"].get("qtyKg"),
                 "containment": self.props(x["dst"]).get("containmentStatus") or "NONE",
                 "in_window": cd is None or (x["props"].get("deliveryDate") is not None
                                             and x["props"]["deliveryDate"] >= cd)}
                for x in self.outs(bid, "DELIVERED_TO")]
        kin = dels if cd is None else [d for d in dels if d["in_window"]]
        orders = self.affected_orders(bid, cd)
        return {"batch": b, "scope": "windowed" if cd else "full", "window_start": cd,
                "counts": {"kitchens": len(kin),
                           "dishes": len({u["dish_id"] for u in self.affected_usage(bid, cd)}),
                           "orders": len({o["order_id"] for o in orders}),
                           "customers": len({o["customer_id"] for o in orders})},
                "kitchens": dels, "usage": self.affected_usage(bid, cd),
                "pull_list": self.pull_list(bid, cd), "orders": orders}

    # ------------------------------------------------------------ write actions
    def flag_batch(self, bid, new_status, reason, actor="web", contamination_date=None):
        b = self.batch(bid)
        cur = b["status"]
        validate_transition(cur, new_status)
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("A reason is required for every risk transition (audit trail).")
        if new_status == "YELLOW" and contamination_date is None \
                and b.get("contaminationDate") is None:
            raise ValueError("contamination_date is required when flagging YELLOW.")
        with self.lock:
            p = self.props(bid)
            p.update({"status": new_status, "statusReason": reason,
                      "statusTimestamp": datetime.now(IST)})
            if contamination_date:
                p["contaminationDate"] = as_ist(contamination_date)
            self.audit(bid, {"type": "STATUS_TRANSITION", "fromStatus": cur,
                             "toStatus": new_status, "reason": reason, "actor": actor})
            return dict(p)

    def flag_supplier(self, sid, new_status, reason, actor="web", contamination_date=None):
        sup = self.supplier(sid)
        cur = sup["status"]
        validate_transition(cur, new_status)
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("A reason is required for every risk transition (audit trail).")
        cd = as_ist(contamination_date)
        with self.lock:
            p = self.props(sid)
            p.update({"status": new_status, "statusReason": reason,
                      "statusTimestamp": datetime.now(IST)})
            if cd:
                p["contaminationDate"] = cd
            self.audit(sid, {"type": "STATUS_TRANSITION", "fromStatus": cur,
                             "toStatus": new_status, "reason": reason, "actor": actor})
            allowed_from = {"GREEN"} if new_status == "YELLOW" else {"GREEN", "YELLOW"}
            cascaded = []
            for x in self.outs(sid, "SUPPLIES"):
                b = x["dst"]
                if self.props(b)["status"] in allowed_from:
                    bp = self.props(b)
                    bp.update({"status": new_status,
                               "statusReason": f"Supplier {sid} flagged {new_status}: {reason}",
                               "statusTimestamp": datetime.now(IST)})
                    if cd and bp.get("contaminationDate") is None:
                        bp["contaminationDate"] = cd
                    self.audit(b, {"type": "SUPPLIER_CASCADE", "toStatus": new_status,
                                   "reason": f"Cascade from supplier {sid}", "actor": actor})
                    cascaded.append(b)
            return {"id": sid, "name": sup.get("name"), "status": new_status,
                    "reason": reason, "cascaded_batches": cascaded}

    def contain(self, bid, status, actor="web"):
        if status not in {"HOLD", "RELEASED", "DESTROYED"}:
            raise ValueError("status must be HOLD, RELEASED or DESTROYED")
        cd = resolve_window(self.batch(bid), None)
        with self.lock:
            touched = []
            for dl in self.outs(bid, "DELIVERED_TO"):
                dd = dl["props"].get("deliveryDate")
                if cd and (dd is None or dd < cd):
                    continue
                self.props(dl["dst"])["containmentStatus"] = status
                touched.append(dl["dst"])
            self.audit(bid, {"type": "KITCHEN_CONTAINMENT",
                             "detail": f"Containment '{status}': " + ", ".join(touched),
                             "actor": actor})
            return touched

    def pull_menu(self, bid, actor="web"):
        cd = resolve_window(self.batch(bid), None)
        with self.lock:
            pulled = []
            for row in self.pull_list(bid, cd):
                k = row["kitchen_id"]
                for d in row["pull_dishes"]:
                    exists = any(x["type"] == "MENU_BLOCKED" and x["src"] == k
                                 and x["dst"] == d["id"] for x in self.E)
                    if not exists:
                        self.E.append({"type": "MENU_BLOCKED", "src": k, "dst": d["id"],
                                       "props": {"reason": f"Recall: batch {bid}",
                                                 "batchId": bid, "at": datetime.now(IST)}})
                    self.props(d["id"])["blocked"] = True
                    pulled.append(f"{row['kitchen']} -> {d['name']}")
            self.audit(bid, {"type": "MENU_PULL",
                             "detail": "Pulled from menus: " + ", ".join(pulled), "actor": actor})
            return pulled

    def restore_menu(self, bid, actor="web"):
        with self.lock:
            keep, removed = [], 0
            for x in self.E:
                if x["type"] == "MENU_BLOCKED" and x["props"].get("batchId") == bid:
                    removed += 1
                    self.props(x["dst"])["blocked"] = False
                else:
                    keep.append(x)
            self.E = keep
            self.audit(bid, {"type": "MENU_RESTORE",
                             "detail": f"Restored {removed} menu items", "actor": actor})
            return removed

    def notify(self, bid, channel="SMS", actor="web"):
        cd = resolve_window(self.batch(bid), None)
        with self.lock:
            orders = {o["order_id"]: o for o in self.affected_orders(bid, cd)}
            for oid, o in orders.items():
                c, src = o["customer_id"], o["customer_id"]
                exist = [x for x in self.E if x["type"] == "NOTIFIED_FOR"
                         and x["src"] == src and x["dst"] == oid]
                props = {"status": "NOTIFIED", "channel": channel,
                         "notifiedAt": datetime.now(IST)}
                if exist:
                    exist[0]["props"].update(props)
                else:
                    self.E.append({"type": "NOTIFIED_FOR", "src": src, "dst": oid,
                                   "props": props})
            self.audit(bid, {"type": "CUSTOMER_NOTIFICATION",
                             "detail": f"{channel} notifications for {len(orders)} orders",
                             "actor": actor})
            return len(orders)

    # ------------------------------------------------------------------ report
    def timeline(self, bid):
        b = self.batch(bid)
        ev = [{"ts": b.get("manufactureDate"), "label": "Batch manufactured",
               "kind": "MANUFACTURE"}]
        for x in self.outs(bid, "PROCESSED_AT"):
            ev.append({"ts": x["props"].get("timestamp"),
                       "label": "Processed at " + self.props(x["dst"])["name"],
                       "kind": "PROCESSING"})
        for x in self.outs(bid, "DELIVERED_TO"):
            ev.append({"ts": x["props"].get("deliveryDate"),
                       "label": "Delivered to " + self.props(x["dst"])["name"],
                       "kind": "DELIVERY"})
        for u in self.affected_usage(bid, None):
            for t in u["used_at"]:
                ev.append({"ts": t, "label": f"Used in {u['dish']} @ {u['kitchen']}",
                           "kind": "USAGE"})
        for a in self.audit_trail(bid):
            ev.append({"ts": a["timestamp"],
                       "label": a.get("reason") or a.get("detail") or a.get("type"),
                       "kind": "AUDIT"})
        ev = [x for x in ev if x["ts"] is not None]
        ev.sort(key=lambda x: x["ts"])
        return {"batch": bid, "ingredient": b["ingredientName"], "status": b["status"],
                "contamination_date": b.get("contaminationDate"),
                "supplier": b["supplier"].get("name"), "events": ev}

    def report(self, bid):
        b = self.batch(bid)
        imp = self.impact(bid, None)
        events = self.audit_trail(bid)
        notes = []
        for o in imp["orders"]:
            when = o["order_time"].strftime("%d %b %Y %H:%M") if o["order_time"] else ""
            notes.append({"customer_id": o["customer_id"], "customer_name": o["customer"],
                          "phone": o["phone"], "email": o["email"], "order_id": o["order_id"],
                          "kitchen": o["kitchen"], "notification_status": o["notification_status"],
                          "message": (f"Food safety alert: your order {o['order_id']} placed on "
                                      f"{when} at {o['kitchen']} included {', '.join(o['dishes'])}, "
                                      f"prepared with batch {bid} ({b['ingredientName']}) under "
                                      f"recall (status {b['status']}). Discard the item; contact "
                                      f"support for a refund.")})

        def S2(o):
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, dict):
                return {k: S2(v) for k, v in o.items()}
            if isinstance(o, list):
                return [S2(v) for v in o]
            return o

        return S2({
            "reportType": "Food Recall Traceability Report (FSSAI-aligned draft) [demo]",
            "generatedAt": datetime.now(IST).isoformat(),
            "product": {"batchId": bid, "ingredient": b["ingredientName"],
                        "supplier": b["supplier"], "riskStatus": b["status"],
                        "statusReason": b.get("statusReason"),
                        "contaminationWindowStart": (b.get("contaminationDate").isoformat()
                                                     if b.get("contaminationDate") else None)},
            "impactSummary": imp["counts"], "kitchenPullLists": imp["pull_list"],
            "ordersAffected": imp["orders"], "consumerNotificationList": notes,
            "statusHistory": [e for e in events if e["type"] == "STATUS_TRANSITION"],
            "actionsTaken": [e for e in events if e["type"] != "STATUS_TRANSITION"],
            "complianceNote": "Supports FSSAI digital recall / FoSCoS logging structure; "
                              "validate before operational use."})


G = Mem()
app = FastAPI(title="Food Traceability Graph - Recall Mission Control [demo mode]")


class FlagReq(BaseModel):
    new_status: str
    reason: str
    actor: str = "web"
    contamination_date: Optional[datetime] = None


def _blast_payload(res):
    return {"batch": res["batch"], "window": J(res["window"]), "counts": res["counts"],
            "node_ids": list(res["nodes"]),
            "edges": [{"type": x["type"], "source": x["src"], "target": x["dst"]}
                      for x in res["edges"]],
            "graph": G.store_json(res["nodes"], res["edges"])}


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "demo (in-memory)"}


@app.post("/api/demo/reset")
def demo_reset():
    with G.lock:
        G.build()
    return {"status": "reset to fresh demo state"}


@app.get("/api/kpis")
def kpis():
    counts = {}
    for x in G.N.values():
        counts[x["label"]] = counts.get(x["label"], 0) + 1
    flagged = [{"id": i, "status": x["props"]["status"], "kind": x["label"],
                "reason": x["props"].get("statusReason")}
               for i, x in G.N.items()
               if x["label"] in ("Batch", "Supplier")
               and x["props"].get("status") in ("YELLOW", "RED")]
    flagged.sort(key=lambda f: (0 if f["status"] == "YELLOW" else 1, f["id"]))
    blocked = sum(1 for x in G.E if x["type"] == "MENU_BLOCKED")
    holds = sum(1 for i in G.N if G.lab(i) == "CloudKitchen"
                and G.props(i).get("containmentStatus") == "HOLD")
    return {"counts": counts, "flagged": flagged, "blocked_menu_items": blocked,
            "kitchen_holds": holds}


@app.get("/api/filters")
def filters():
    return {"suppliers": [{"id": i, "name": x["props"]["name"],
                           "status": x["props"].get("status")}
                          for i, x in G.N.items() if x["label"] == "Supplier"],
            "kitchens": [{"id": i, "name": x["props"]["name"]}
                         for i, x in G.N.items() if x["label"] == "CloudKitchen"],
            "ingredients": sorted({x["props"]["ingredientName"] for x in G.N.values()
                                   if x["label"] == "Batch"}),
            "locations": sorted({x["props"]["location"] for x in G.N.values()
                                 if x["props"].get("location")})}


@app.get("/api/network")
def network(q: Optional[str] = None, supplier: Optional[str] = None,
            kitchen: Optional[str] = None, ingredient: Optional[str] = None,
            location: Optional[str] = None, statuses: Optional[List[str]] = Query(None),
            date_from: Optional[date] = None, date_to: Optional[date] = None,
            include_orders: bool = False, include_facility: bool = False):
    nodes, edges = G.fetch_subgraph(q=q, supplier=supplier, kitchen=kitchen,
                                    ingredient=ingredient, location=location,
                                    statuses=statuses, date_from=date_from, date_to=date_to,
                                    include_orders=include_orders,
                                    include_facility=include_facility)
    return G.store_json(nodes, edges)


@app.get("/api/node/{label}/{node_id}")
def node_details(label: str, node_id: str):
    if node_id not in G.N or G.lab(node_id) != label:
        raise HTTPException(404, f"{label} '{node_id}' not found")
    with G.lock:
        p, rels = dict(G.props(node_id)), []
        for x in G.E:
            if x["src"] == node_id:
                other = x["dst"]
                rels.append({"rel": x["type"], "outbound": True,
                             "other_label": G.lab(other),
                             "other": G.props(other).get("id") or G.props(other).get("name"),
                             "meta": x["props"]})
            elif x["dst"] == node_id:
                other = x["src"]
                rels.append({"rel": x["type"], "outbound": False,
                             "other_label": G.lab(other),
                             "other": G.props(other).get("id") or G.props(other).get("name"),
                             "meta": x["props"]})
    rels.sort(key=lambda r: (r["rel"], r["other"] or ""))
    return {"props": J(p), "relationships": [{"**": r["**"]} if False else
            {"rel": r["rel"], "outbound": r["outbound"], "other_label": r["other_label"],
             "other": r["other"], "meta": J(r["meta"])} for r in rels]}


@app.get("/api/trace/{label}/{node_id}")
def trace(label: str, node_id: str, direction: Literal["up", "down"] = "down"):
    if node_id not in G.N or G.lab(node_id) != label:
        raise HTTPException(404, f"{label} '{node_id}' not found")
    nodes, edges = G.trace(label, node_id, direction)
    return G.store_json(nodes, edges)


@app.get("/api/expand/{label}/{node_id}")
def expand(label: str, node_id: str):
    if node_id not in G.N or G.lab(node_id) != label:
        raise HTTPException(404, f"{label} '{node_id}' not found")
    nodes, edges = G.neighborhood(node_id)
    return G.store_json(nodes, edges)


@app.get("/api/blast/{batch_id}")
def blast(batch_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        return _blast_payload(G.blast(batch_id, WIN[window]))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/blast-supplier/{supplier_id}")
def blast_supplier(supplier_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        return _blast_payload(G.supplier_blast(supplier_id, WIN[window]))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/contamination")
def contamination():
    with G.lock:
        flagged = [(i, x["label"]) for i, x in G.N.items()
                   if x["label"] in ("Batch", "Supplier")
                   and x["props"].get("status") in ("YELLOW", "RED")]
        nodes, edge_list = set(), []
        counts = {"kitchens": 0, "dishes": 0, "orders": 0, "customers": 0}
        for nid, kind in flagged:
            res = G.supplier_blast(nid) if kind == "Supplier" else G.blast(nid)
            nodes |= res["nodes"]
            edge_list.extend(res["edges"])
            for k in counts:
                counts[k] += res["counts"][k]
        dedup = {(x["type"], x["src"], x["dst"]): x for x in edge_list}
        return _blast_payload({"batch": "ALL FLAGGED", "window": None, "nodes": nodes,
                               "edges": list(dedup.values()), "counts": counts})


class CypherReq(BaseModel):
    query: str


@app.post("/api/query/cypher")
def query_cypher(req: CypherReq):
    raise HTTPException(501, "Cypher console requires Neo4j mode (web_app.py). "
                             "Command mode works in demo mode.")


@app.get("/api/pull-list/{batch_id}")
def pull_list(batch_id: str, window: Literal["auto", "on", "off"] = "auto"):
    try:
        cd = resolve_window(G.batch(batch_id), WIN[window])
        return {"batch": batch_id, "window": J(cd), "pull_list": G.pull_list(batch_id, cd)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/timeline/{batch_id}")
def timeline(batch_id: str):
    try:
        return J(G.timeline(batch_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/flag/{batch_id}")
def flag(batch_id: str, req: FlagReq):
    try:
        return J(G.flag_batch(batch_id, req.new_status, req.reason, req.actor,
                              as_ist(req.contamination_date) if req.contamination_date else None))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/flag-supplier/{supplier_id}")
def flag_supplier(supplier_id: str, req: FlagReq):
    try:
        return J(G.flag_supplier(supplier_id, req.new_status, req.reason, req.actor,
                                 as_ist(req.contamination_date) if req.contamination_date else None))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/actions/contain/{batch_id}")
def contain(batch_id: str, status: str = "HOLD"):
    try:
        return {"kitchens": G.contain(batch_id, status)}
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/actions/pull-menu/{batch_id}")
def pull_menu(batch_id: str):
    try:
        return {"pulled": G.pull_menu(batch_id)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/actions/restore-menu/{batch_id}")
def restore_menu(batch_id: str):
    try:
        return {"restored": G.restore_menu(batch_id)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/actions/notify/{batch_id}")
def notify(batch_id: str, channel: str = "SMS"):
    try:
        return {"orders_notified": G.notify(batch_id, channel)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/report/{batch_id}")
def report(batch_id: str):
    try:
        return G.report(batch_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))