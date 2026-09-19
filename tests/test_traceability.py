"""Integration tests for traceability, reverse trace, pull list, and supplier intelligence."""
from datetime import datetime
import pytest

from config import IST
from core import risk, traceability as tr
from db.connection import run_query


def test_impact_report_forward_trace():
    """Verify forward trace: Batch -> Kitchens -> Dishes -> Orders -> Customers."""
    res = tr.impact_report("BATCH-PANEER-001")
    assert res["batch"]["id"] == "BATCH-PANEER-001"
    assert res["counts"]["kitchens"] > 0
    assert res["counts"]["dishes"] > 0
    assert res["counts"]["orders"] > 0
    assert res["counts"]["customers"] > 0
    assert len(res["pull_list"]) > 0


def test_reverse_trace():
    """Verify reverse trace: Customer -> Order -> Dish -> Batch -> Supplier."""
    res = tr.reverse_trace(customer_id="CUS-001")
    assert "rows" in res
    assert len(res["rows"]) > 0
    assert len(res["batches"]) > 0
    assert len(res["suppliers"]) > 0
    assert any(b["ingredient"] == "Paneer" for b in res["batches"])


def test_pull_list_format():
    """Verify pull list format is per-kitchen with dish IDs and names."""
    pl = tr.pull_list("BATCH-PANEER-001")
    assert len(pl) > 0
    first_kitchen = pl[0]
    assert "kitchen_id" in first_kitchen
    assert "kitchen" in first_kitchen
    assert "pull_dishes" in first_kitchen
    assert len(first_kitchen["pull_dishes"]) > 0
    assert "id" in first_kitchen["pull_dishes"][0]
    assert "name" in first_kitchen["pull_dishes"][0]


def test_supplier_intelligence():
    """Verify supplier intelligence aggregates batches and network impact."""
    sup_intel = tr.supplier_intelligence("SUP-002")
    assert "summary" in sup_intel
    assert sup_intel["summary"]["supplier"]["id"] == "SUP-002"
    assert sup_intel["summary"]["total_batches"] >= 1
    assert "network_impact" in sup_intel
    assert sup_intel["network_impact"]["kitchens"] >= 1
    assert sup_intel["network_impact"]["orders"] >= 1
    assert len(sup_intel["batches"]) >= 1


def test_batch_timeline():
    """Verify timeline contains sequential chronological events."""
    tl = tr.batch_timeline("BATCH-PANEER-001")
    assert tl["batch"] == "BATCH-PANEER-001"
    assert "events" in tl
    assert len(tl["events"]) > 0
    kinds = {e["kind"] for e in tl["events"]}
    assert "MANUFACTURE" in kinds


def test_recall_report_structure():
    """Verify recall report produces complete FSSAI-aligned audit structure."""
    rep = tr.recall_report("BATCH-PANEER-001")
    assert rep["reportType"] == "Food Recall Traceability Report (FSSAI-aligned draft)"
    assert rep["product"]["batchId"] == "BATCH-PANEER-001"
    assert len(rep["consumerNotificationList"]) > 0
    assert "message" in rep["consumerNotificationList"][0]


def test_menu_blocked_and_restore_cycle():
    """Verify MENU_BLOCKED creation and subsequent restoration."""
    bid = "BATCH-PANEER-001"
    # Pull menu
    pulled = tr.pull_from_menu(bid, actor="test_runner")
    assert len(pulled) > 0

    # Verify relationship exists in Neo4j
    blocked_count = run_query(
        "MATCH (:CloudKitchen)-[mb:MENU_BLOCKED {batchId: $bid}]->() RETURN count(mb) AS c",
        {"bid": bid}
    )[0]["c"]
    assert blocked_count > 0

    # Restore menu
    restored = tr.restore_menu(bid, actor="test_runner")
    assert restored == blocked_count

    # Verify relationships deleted
    remaining = run_query(
        "MATCH (:CloudKitchen)-[mb:MENU_BLOCKED {batchId: $bid}]->() RETURN count(mb) AS c",
        {"bid": bid}
    )[0]["c"]
    assert remaining == 0
