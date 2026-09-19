"""Unit and integration tests for FastAPI route handlers."""
import pytest
from api import main


def test_api_health():
    res = main.health()
    assert res == {"status": "ok"}


def test_api_kpis():
    res = main.kpis()
    assert "counts" in res
    assert "Supplier" in res["counts"]
    assert "Batch" in res["counts"]
    assert "CloudKitchen" in res["counts"]
    assert "flagged" in res
    assert "blocked_dishes" in res
    assert "blocked_menu_items" in res
    assert "kitchen_holds" in res


def test_api_filters():
    res = main.filters()
    assert "suppliers" in res
    assert "kitchens" in res
    assert "ingredients" in res
    assert "locations" in res
    assert len(res["suppliers"]) > 0
    assert len(res["kitchens"]) > 0


def test_api_network():
    res = main.network()
    assert "nodes" in res
    assert "edges" in res
    assert len(res["nodes"]) > 0
    assert len(res["edges"]) > 0


def test_api_node_details():
    res = main.node_details("Batch", "BATCH-PANEER-001")
    assert "props" in res
    assert "relationships" in res
    assert res["props"]["id"] == "BATCH-PANEER-001"


def test_api_trace():
    res = main.trace("Batch", "BATCH-PANEER-001", direction="down")
    assert "nodes" in res
    assert "edges" in res
    assert len(res["nodes"]) > 0


def test_api_expand():
    res = main.expand("Batch", "BATCH-PANEER-001")
    assert "nodes" in res
    assert "edges" in res
    assert len(res["nodes"]) > 0


def test_api_blast():
    res = main.blast("BATCH-PANEER-001", window="off")
    assert res["batch"] == "BATCH-PANEER-001"
    assert "counts" in res
    assert res["counts"]["kitchens"] > 0
    assert res["counts"]["orders"] > 0


def test_api_blast_supplier():
    res = main.blast_supplier("SUP-002", window="off")
    assert res["batch"] == "SUP-002"
    assert "counts" in res
    assert res["counts"]["kitchens"] > 0


def test_api_pull_list():
    res = main.pull_list("BATCH-PANEER-001", window="off")
    assert res["batch"] == "BATCH-PANEER-001"
    assert "pull_list" in res
    assert len(res["pull_list"]) > 0


def test_api_timeline():
    res = main.timeline("BATCH-PANEER-001")
    assert res["batch"] == "BATCH-PANEER-001"
    assert "events" in res
    assert len(res["events"]) > 0


def test_api_report():
    res = main.report("BATCH-PANEER-001")
    assert res["product"]["batchId"] == "BATCH-PANEER-001"
    assert "kitchenPullLists" in res
    assert "consumerNotificationList" in res


def test_api_reverse():
    res = main.reverse(customer="CUS-001")
    assert len(res["rows"]) > 0
    assert len(res["batches"]) > 0


def test_api_supplier_intel():
    res = main.supplier_intel("SUP-002")
    assert res["summary"]["supplier"]["id"] == "SUP-002"
    assert len(res["batches"]) > 0


def test_api_contamination():
    res = main.contamination()
    assert res["batch"] == "ALL FLAGGED"
    assert "counts" in res
    assert "node_ids" in res


def test_api_query_cypher():
    from core.query_agent import CypherRejected
    # Valid read query
    req = main.CypherReq(query="MATCH (b:Batch) RETURN b.id, b.status LIMIT 2")
    res = main.query_cypher(req)
    assert "rows" in res
    assert "columns" in res
    assert len(res["rows"]) <= 2

    # Blocked write query
    with pytest.raises(main.HTTPException) as exc:
        main.query_cypher(main.CypherReq(query="MATCH (b:Batch) DELETE b"))
    assert exc.value.status_code == 400


def test_demo_server_contamination_and_cypher():
    import demo_server
    res = demo_server.contamination()
    assert res["batch"] == "ALL FLAGGED"
    assert "counts" in res

    with pytest.raises(demo_server.HTTPException) as exc:
        demo_server.query_cypher(demo_server.CypherReq(query="MATCH (b:Batch) RETURN b"))
    assert exc.value.status_code == 501

