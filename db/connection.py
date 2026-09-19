"""Neo4j driver singleton + tiny query helpers."""
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship

import config

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
    return _driver


def close():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def _to_native(value):
    """Convert driver types (nodes, temporal) to plain Python."""
    if isinstance(value, Node):
        d = dict(value)
        d["_labels"] = sorted(value.labels)
        return d
    if isinstance(value, Relationship):
        d = dict(value)
        d["_type"] = value.type
        return d
    if hasattr(value, "to_native"):  # neo4j temporal types
        return value.to_native()
    if isinstance(value, list):
        return [_to_native(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}
    return value


def run_query(cypher, params=None, database=None):
    """Run a query and return a list of plain-Python record dicts."""
    with get_driver().session(database=database or config.NEO4J_DATABASE) as session:
        result = session.run(cypher, params or {})
        return [_to_native(dict(zip(r.keys(), r.values()))) for r in result]
