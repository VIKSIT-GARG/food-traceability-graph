"""FastAPI wrapper around the traceability core (optional; dashboard runs standalone)."""
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from core import risk, traceability as tr

app = FastAPI(title="Food Traceability Graph API", version="1.0.0",
              description="Neo4j-powered supply-chain traceability & recall engine")


class FlagRequest(BaseModel):
    new_status: str
    reason: str
    actor: str = "api"
    contamination_date: Optional[datetime] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/batches")
def list_batches(text: Optional[str] = None, ingredient: Optional[str] = None,
                 supplier: Optional[str] = None):
    return tr.search_batches(text=text, ingredient=ingredient, supplier_id=supplier)


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    try:
        return risk.get_batch(batch_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/batches/{batch_id}/flag")
def flag_batch(batch_id: str, req: FlagRequest):
    try:
        return risk.flag_batch(batch_id, req.new_status, req.reason, req.actor,
                               risk.as_ist(req.contamination_date) if req.contamination_date else None)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except risk.RiskTransitionError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/batches/{batch_id}/impact")
def impact(batch_id: str, apply_window: Optional[bool] = Query(None)):
    try:
        return tr.impact_report(batch_id, apply_window=apply_window)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/batches/{batch_id}/timeline")
def timeline(batch_id: str):
    try:
        return tr.batch_timeline(batch_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/batches/{batch_id}/audit")
def audit(batch_id: str):
    return risk.audit_trail(batch_id)


@app.get("/batches/{batch_id}/recall-report")
def recall_report(batch_id: str):
    try:
        return tr.recall_report(batch_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/recall/{batch_id}/contain-kitchens")
def contain(batch_id: str, status: str = "HOLD", actor: str = "api"):
    try:
        return {"kitchens": tr.set_kitchen_containment(batch_id, status, actor)}
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/recall/{batch_id}/block-dishes")
def block(batch_id: str, actor: str = "api"):
    try:
        return {"dishes": tr.block_affected_dishes(batch_id, actor)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/recall/{batch_id}/notify-customers")
def notify(batch_id: str, channel: str = "SMS", actor: str = "api"):
    try:
        return {"orders_notified": tr.mark_customers_notified(batch_id, channel, actor)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/trace/reverse")
def reverse(customer: Optional[str] = None, order: Optional[str] = None,
            dish: Optional[str] = None):
    try:
        return tr.reverse_trace(customer_id=customer, order_id=order, dish_id=dish)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/suppliers/{supplier_id}/intelligence")
def supplier_intel(supplier_id: str):
    try:
        return tr.supplier_intelligence(supplier_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
