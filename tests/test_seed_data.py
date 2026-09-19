from db import seed


def test_demo_batch_exists():
    assert any(b["id"] == "BATCH-PANEER-001" for b in seed.BATCHES)


def test_usages_reference_existing_entities():
    batches = {b["id"] for b in seed.BATCHES}
    dishes = {d["id"] for d in seed.DISHES}
    for batch_id, dish_id, ts, qty in seed.USED_IN_DISH:
        assert batch_id in batches, f"unknown batch {batch_id}"
        assert dish_id in dishes, f"unknown dish {dish_id}"


def test_orders_reference_existing_entities():
    customers = {c["id"] for c in seed.CUSTOMERS}
    dishes = {d["id"] for d in seed.DISHES}
    for oid, cid, ts, items in seed.ORDERS:
        assert cid in customers, f"unknown customer on {oid}"
        assert items, f"order {oid} has no items"
        for dish_id, qty in items:
            assert dish_id in dishes, f"unknown dish on {oid}"
