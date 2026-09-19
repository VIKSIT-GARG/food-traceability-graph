
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
    if new_status == "YELLOW" and contamination_date is None \
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
