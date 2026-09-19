# Food Traceability Graph
## Graph-Based Food Supply Chain Traceability & Recall Engine

### 1. Project Overview

The rapid expansion of cloud kitchens across Delhi NCR (Gurugram, Noida, and Delhi) creates a food-safety challenge: when a specific ingredient batch is found to be spoiled or contaminated, operators need to quickly determine where that batch went, which dishes used it, and which customers may have received those dishes.

A flat database makes this kind of multi-hop impact analysis difficult. This project uses **Neo4j** to represent the supply chain as a connected graph and uses **Cypher** to perform downstream traceability and recall analysis.

The core graph is:

**Supplier → Batch → Processing Facility → Cloud Kitchen → Dish → Order → Customer**

The system is designed to let an operator flag a Supplier or Batch as contaminated and immediately generate an affected-kitchen, affected-dish, and affected-customer list.

---

## 2. Problem Statement

### Theme
**Logistics & Supply Chain Transparency**

### Problem

With the growth of cloud kitchens across Gurugram, Noida, and Delhi, ingredient provenance is important for health safety and quality control.

If a particular supplier batch—for example, a batch of paneer—is flagged as spoiled, the system should be able to identify:

1. Every cloud kitchen that received the batch.
2. The dishes in which the batch was used.
3. Orders containing those dishes.
4. Customers associated with those orders.

The application therefore needs a graph-based traceability engine capable of performing fast multi-hop traversal.

---

## 3. Core Objective

Build a **Food Traceability Graph** that tracks ingredient movement and usage through the supply chain:

```text
(Farm/Supplier)
      |
   SUPPLIED
      |
    (Batch)
      |
  PROCESSED_AT
      |
(Facility / Processing Step)
      |
 DELIVERED_TO
      |
(Cloud Kitchen)
      |
  USED_IN_DISH
      |
    (Dish)
      |
 CONTAINS_DISH
      |
   (Order)
      |
 PLACED_ORDER
      |
  (Customer)
```

The application should support a contamination workflow in which a user selects a Supplier or Batch, flags it, and receives a downstream impact report.

---

# 4. Risk Model

The system uses a temporal, three-level risk model to avoid unnecessarily recalling all inventory.

| Status | Meaning | Expected Action |
|---|---|---|
| 🟢 GREEN | Clear; batch was processed before the contamination window or verified safe by testing | Normal operation |
| 🟡 YELLOW | Suspected / under investigation; batch was present at a relevant facility or step during/after the suspected contamination timestamp | Hold affected inventory and mark relevant dishes pending verification |
| 🔴 RED | Confirmed contaminated | Destroy/isolate affected inventory, block affected menu items, and initiate customer safety notification |

### Risk progression

```text
GREEN
  |
  | contamination suspected
  v
YELLOW
  |
  | contamination confirmed
  v
RED
```

The system should retain the reason and relevant timestamp for a risk transition.

---

# 5. Neo4j Data Model

## Node Labels

### Supplier

```text
Supplier
- id
- name
- location
```

### Batch

```text
Batch
- id
- ingredientName
- manufactureDate
- status
```

Allowed status values:

```text
GREEN | YELLOW | RED
```

### Facility / ProcessingStep

```text
Facility
- id
- name
- stepType
```

### CloudKitchen

```text
CloudKitchen
- id
- name
- location
```

### Dish

```text
Dish
- id
- name
- price
```

### Order

```text
Order
- id
- timestamp
```

### Customer

```text
Customer
- id
- name
- phone
- email
```

---

# 6. Relationships

```text
(:Supplier)-[:SUPPLIED]->(:Batch)

(:Batch)-[:PROCESSED_AT {
    timestamp
}]->(:Facility)

(:Batch)-[:DELIVERED_TO {
    deliveryDate,
    qtyKg
}]->(:CloudKitchen)

(:Batch)-[:USED_IN_DISH]->(:Dish)

(:Order)-[:CONTAINS_DISH {
    quantity
}]->(:Dish)

(:Customer)-[:PLACED_ORDER]->(:Order)
```

These relationships allow the application to traverse from an affected ingredient batch to downstream operational and customer impact.

---

# 7. Core Traceability Workflow

## Step 1 — Select a Batch

The operator selects a batch ID, for example:

```text
BATCH-PANEER-001
```

## Step 2 — Flag the Batch

The batch can be moved from:

```text
GREEN → YELLOW
```

when contamination is suspected.

If contamination is confirmed:

```text
YELLOW → RED
```

## Step 3 — Apply the Contamination Time Window

Processing and downstream records are evaluated relative to:

```text
contamination_date
```

The temporal filtering rule includes:

```cypher
PROCESSED_AT.timestamp >= $contamination_date
```

This prevents the system from automatically treating every historical use of an ingredient as affected.

## Step 4 — Traverse the Graph

The system identifies:

```text
Affected Batch
    ↓
Affected Kitchens
    ↓
Affected Dishes
    ↓
Affected Orders
    ↓
Affected Customers
```

## Step 5 — Generate Recall Actions

The dashboard should produce actionable outputs such as:

- Kitchens where affected inventory must be isolated.
- Dishes that should be removed or temporarily blocked.
- Orders potentially containing affected dishes.
- Customers requiring safety outreach.
- Current risk status of the affected batch.

---

# 8. Example Cypher Traversal

A basic downstream traversal can follow the connected graph:

```cypher
MATCH (b:Batch {id: $batch_id})
OPTIONAL MATCH (b)-[:DELIVERED_TO]->(k:CloudKitchen)
OPTIONAL MATCH (b)-[:USED_IN_DISH]->(d:Dish)
OPTIONAL MATCH (o:Order)-[:CONTAINS_DISH]->(d)
OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
RETURN
    b,
    collect(DISTINCT k) AS affected_kitchens,
    collect(DISTINCT d) AS affected_dishes,
    collect(DISTINCT o) AS affected_orders,
    collect(DISTINCT c) AS affected_customers;
```

For temporal filtering, processing relationships can be constrained using the contamination timestamp:

```cypher
MATCH (b:Batch {id: $batch_id})
MATCH (b)-[p:PROCESSED_AT]->(f:Facility)
WHERE p.timestamp >= $contamination_date
RETURN b, f, p.timestamp;
```

The exact production query should be adapted to the application's data-ingestion and traceability rules.

---

# 9. Application Architecture

The application uses a **graph-first frontend**. The interactive supply-chain graph is a core product interface, not merely an optional visualization.

```text
                         ┌──────────────────────────┐
                         │       User / Admin        │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────┐
                  │      GRAPH-FIRST FRONTEND           │
                  │                                    │
                  │  Interactive Supply-Chain Graph   │
                  │  Search / Filters / Node Details  │
                  │  Risk Visualization               │
                  │  Recall & Blast-Radius Controls   │
                  └──────────────────┬─────────────────┘
                                     │
                                     ▼
                         ┌─────────────────────┐
                         │    Python Backend    │
                         │  FastAPI / Python    │
                         └──────────┬──────────┘
                                    │
                              Neo4j Driver
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Cypher Engine     │
                         │                     │
                         │ Traceability        │
                         │ Temporal Filtering  │
                         │ Risk Propagation    │
                         │ Recall Analysis     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Neo4j Database    │
                         │                     │
                         │ Supplier            │
                         │ Batch               │
                         │ Facility            │
                         │ CloudKitchen        │
                         │ Dish                │
                         │ Order               │
                         │ Customer            │
                         └─────────────────────┘
```

### Recommended stack

- **Database:** Neo4j
- **Query language:** Cypher
- **Backend:** Python 3.x
- **Neo4j integration:** `neo4j` Python Driver
- **API:** FastAPI
- **Frontend:** Graph-first web interface
- **Graph visualization:** Interactive Neo4j-backed graph component
- **Optional dashboard layer:** Streamlit for rapid prototyping/admin views

---

# 10. Graph-First Frontend Requirement

The frontend must provide an **interactive graph-based interface** for exploring the food supply chain.

The graph is the primary interface through which users understand contamination propagation.

## 10.1 Main Graph View

The application should visualize:

```text
Supplier
   │
   ▼
 Batch 🔴
   │
   ├──────────────┐
   ▼              ▼
Kitchen A      Kitchen B
   │              │
   ▼              ▼
 Dish A         Dish B
   │              │
   ▼              ▼
Orders         Orders
   │              │
   ▼              ▼
Customers      Customers
```

Nodes and relationships should be loaded dynamically from Neo4j rather than being static frontend data.

## 10.2 Graph Interactions

The user should be able to:

- Pan and zoom around the graph.
- Click any node to inspect its properties.
- Expand connected nodes.
- Collapse graph branches.
- Highlight an entire upstream or downstream path.
- Search by Batch ID, Supplier, Kitchen, Dish, Order, or Customer.
- Filter nodes by GREEN / YELLOW / RED status.
- Filter the graph by date or contamination window.
- Display relationship metadata such as quantity, delivery date, and timestamps.
- Trace from a contaminated batch to every downstream dependency.
- Trace backwards from a customer/order to the originating batch and supplier.

## 10.3 Risk Visualization

The graph should visually distinguish risk states:

```text
🟢 GREEN  → Clear
🟡 YELLOW → Suspected / Under Investigation
🔴 RED    → Confirmed Contaminated
```

When a batch becomes RED, its affected downstream paths should be highlighted so that the operator can immediately see the recall blast radius.

## 10.4 Selected Node Panel

Clicking a node should open a details panel.

Example:

```text
┌───────────────────────────────────────┐
│ BATCH-PANEER-001                      │
│                                       │
│ Ingredient: Paneer                    │
│ Status: 🔴 RED                        │
│ Manufacture: 08 Sept                  │
│                                       │
│ Affected Kitchens: 12                 │
│ Affected Dishes: 31                   │
│ Affected Orders: 487                  │
│ Affected Customers: 421               │
│                                       │
│ [Trace Upstream] [Trace Downstream]   │
│ [Simulate Recall]                     │
└───────────────────────────────────────┘
```

## 10.5 Frontend Layout

The primary application screen should follow a graph-first structure:

```text
┌───────────────────────────────────────────────────────────────┐
│ TRACE-NCR                    FOOD RECALL / TRACEABILITY       │
├───────────────┬───────────────────────────────────────────────┤
│ SEARCH        │                                               │
│               │                                               │
│ Batch ID      │                                               │
│ Supplier      │             INTERACTIVE GRAPH                 │
│ Kitchen       │                                               │
│ Ingredient    │       Supplier → Batch → Kitchen              │
│               │            → Dish → Order → Customer           │
│ FILTERS       │                                               │
│ 🟢 Green      │                                               │
│ 🟡 Yellow     │                                               │
│ 🔴 Red        │                                               │
│               │                                               │
├───────────────┴───────────────────────────────────────────────┤
│ SELECTED NODE / TRACE RESULTS                                 │
│ Batch: PANEER-001   Status: 🔴 RED                           │
│ Kitchens: 12 | Dishes: 31 | Orders: 487 | Customers: 421   │
├───────────────────────────────────────────────────────────────┤
│ [TRACE UPSTREAM] [TRACE DOWNSTREAM] [SIMULATE RECALL]         │
└───────────────────────────────────────────────────────────────┘
```

## 10.6 Graph as Source of Truth

The frontend must not maintain a separate static representation of the supply chain.

The intended data flow is:

```text
User Action
    ↓
Frontend
    ↓
FastAPI Backend
    ↓
Cypher Query
    ↓
Neo4j
    ↓
Graph Result
    ↓
Frontend Visualization
```

This ensures that the graph shown to the operator reflects the current database state.

---

# 11. Frontend Traceability Modes

The graph interface should support two primary exploration modes.

## Forward Trace

```text
Supplier
   ↓
Batch
   ↓
Kitchen
   ↓
Dish
   ↓
Order
   ↓
Customer
```

Question answered:

> "This batch is contaminated. What is affected?"

## Reverse Trace

```text
Customer
   ↓
Order
   ↓
Dish
   ↓
Batch
   ↓
Supplier
```

Question answered:

> "This customer/order was affected. Where did the ingredient originate?"

Both modes should be visually represented in the same graph interface.


---

# 10. Dashboard

The interface should expose the traceability workflow directly.

## Dashboard sections

### A. Batch Search

Allow the operator to search by:

```text
Batch ID
Supplier ID
Ingredient
```

### B. Risk State

Display:

```text
GREEN
YELLOW
RED
```

along with the reason for the current status.

### C. Impact Summary

Example:

```text
Batch: BATCH-PANEER-001
Ingredient: Paneer
Risk: RED

Affected Kitchens: 4
Affected Dishes: 7
Affected Orders: 31
Affected Customers: 28
```

### D. Affected Kitchens

Show:

```text
Kitchen
Location
Delivery Date
Quantity Received
Containment Status
```

Example locations can include:

```text
Connaught Place
Cyber Hub
Noida
```

### E. Affected Dishes

Show dishes that used the affected batch and mark them for menu blocking or investigation.

### F. Customer Safety Outreach

Generate notification-ready records containing:

```text
Customer ID
Customer Name
Contact
Affected Order
Affected Dish
Order Timestamp
Notification Status
```

---

# 11. Recall / Containment Workflow

When a batch becomes **YELLOW**:

```text
1. Flag batch
2. Identify potentially affected kitchens
3. Place relevant inventory on hold
4. Mark affected dishes as pending verification
5. Continue investigation / lab verification
```

When a batch becomes **RED**:

```text
1. Confirm contamination
2. Isolate or destroy affected inventory
3. Block affected menu items
4. Identify affected orders
5. Generate customer safety notifications
6. Record the recall/containment action
```

The system should produce a clear audit trail of the state change and resulting actions.

---

# 12. FSSAI / Recall Alignment

The system is intended to align its recall outputs with the supplied requirement of **FSSAI digital recall procedure / FoSCoS compliance logging**.

The application should therefore structure recall information so that an operator can identify:

- Affected ingredient/batch.
- Supplier.
- Relevant processing or delivery path.
- Affected kitchens.
- Affected menu items.
- Affected orders/customers.
- Containment actions.
- Notification actions.
- Risk status and timestamps.

This project specification does not claim formal regulatory certification; compliance workflows should be validated against the applicable FSSAI/FoSCoS requirements during implementation.

---

# 13. Demonstration Scenario

## Scenario

A supplier provides a paneer batch:

```text
Batch ID: BATCH-PANEER-001
Ingredient: Paneer
Status: GREEN
```

The batch is delivered to multiple cloud kitchens and is subsequently used in several dishes.

A contamination event is reported.

### Stage 1 — Investigation

The operator flags:

```text
BATCH-PANEER-001 → YELLOW
```

The system traverses the graph and identifies kitchens and dishes associated with the batch.

### Stage 2 — Confirmation

Laboratory or operational verification confirms contamination.

The operator changes:

```text
BATCH-PANEER-001 → RED
```

### Stage 3 — Impact Analysis

The graph engine returns:

```text
Batch
 ↓
Kitchens
 ↓
Dishes
 ↓
Orders
 ↓
Customers
```

### Stage 4 — Recall Actions

The dashboard generates:

```text
Affected kitchen containment list
Affected menu/dish list
Affected order list
Customer notification payloads
Recall audit information
```

The key demonstration point is that the operator does not have to manually search separate tables for every downstream dependency.

---

# 14. What the Project Demonstrates

The prototype demonstrates five core capabilities:

### 1. Graph-based supply-chain modeling

Supply-chain entities are represented as connected nodes and relationships rather than isolated records.

### 2. Multi-hop impact analysis

A single flagged batch can be traced through multiple downstream entities.

### 3. Temporal reasoning

Contamination timestamps can be used to distinguish potentially affected paths from historical activity.

### 4. Dynamic risk states

A batch can move through:

```text
GREEN → YELLOW → RED
```

with downstream containment and recall implications.

### 5. Actionable recall output

The final result is not just a graph query. It is an operational list of:

```text
Kitchens
Dishes
Orders
Customers
```

that can be acted upon.

---

# 15. Minimum Viable Product

The MVP should contain:

- Neo4j database.
- Complete graph schema.
- Sample Delhi NCR cloud-kitchen dataset.
- Batch search.
- Batch contamination flagging.
- GREEN/YELLOW/RED status.
- Temporal contamination filtering.
- Downstream Cypher traversal.
- Affected kitchen list.
- Affected dish list.
- Affected order/customer list.
- Basic graph visualization.
- Streamlit dashboard or CLI.
- Recall report generation.

---


---

# 21. Advanced Traceability Extensions

The following extensions are part of the final system design and build on the core Neo4j traceability requirements.

## 20.1 Two-Way Traceability

The system will support both **forward** and **reverse** traceability.

### Forward Traceability

Starting from an ingredient batch:

```text
Supplier
   ↓
Batch
   ↓
Cloud Kitchen
   ↓
Dish
   ↓
Order
   ↓
Customer
```

This answers:

> "A batch is contaminated. Who and what could be affected?"

### Reverse Traceability

Starting from a customer, order, or dish:

```text
Customer
   ↓
Order
   ↓
Dish
   ↓
Batch
   ↓
Supplier
```

This answers:

> "A customer reported a problem. Which ingredient batches and suppliers were involved?"

This creates a bidirectional traceability system rather than a one-way recall lookup.

### Example Reverse Cypher

```cypher
MATCH (c:Customer {id: $customer_id})
MATCH (c)-[:PLACED_ORDER]->(o:Order)
MATCH (o)-[:CONTAINS_DISH]->(d:Dish)
MATCH (b:Batch)-[:USED_IN_DISH]->(d)
MATCH (s:Supplier)-[:SUPPLIED]->(b)
RETURN
    c,
    o,
    d,
    collect(DISTINCT b) AS batches,
    collect(DISTINCT s) AS suppliers;
```

---

# 22. Ingredient Consumption Timeline

The system will add a temporal layer to ingredient usage so that contamination impact is determined by **when** an ingredient was processed, delivered, and consumed.

Instead of storing only:

```text
Batch → USED_IN_DISH → Dish
```

the relationship can include consumption metadata:

```text
(:Batch)-[:USED_IN_DISH {
    timestamp,
    quantity
}]->(:Dish)
```

The traceability timeline becomes:

```text
Manufactured
     ↓
Processed
     ↓
Delivered
     ↓
Consumed
     ↓
Order Created
```

### Example

```text
Contamination reported:
10 Sept, 14:00

Batch usage:

09 Sept, 11:00  → CLEAR
10 Sept, 12:00  → CLEAR
10 Sept, 15:30  → SUSPECT
11 Sept, 09:00  → AFFECTED
```

This allows the system to distinguish historical safe usage from usage that falls within the contamination window.

### Timeline View

The dashboard should show:

```text
BATCH-PANEER-001

09 Sep ─────── Processing ─────── GREEN
10 Sep 14:00 ─ Contamination Event
10 Sep 15:30 ─ Kitchen Usage ──── YELLOW
11 Sep ─────── Confirmed ───────── RED
```

The temporal engine should use timestamps associated with processing, delivery, and consumption when determining affected paths.

---

# 23. Supplier Risk Intelligence

The graph will also provide a supplier-level intelligence layer.

For every supplier, the dashboard can aggregate:

```text
Supplier
├── Total batches supplied
├── Active batches
├── GREEN batches
├── YELLOW batches
├── RED batches
├── Recall events
├── Affected kitchens
└── Affected customers
```

### Example Supplier Dashboard

```text
Supplier: FreshFoods Pvt Ltd

Total Batches:          124
Active Batches:          38
YELLOW Batches:           2
RED Batches:              1
Recall Events:            2
Affected Kitchens:       17
Affected Customers:     421
```

### Supplier → Network Impact

The graph can also identify how widely a supplier's batches propagate:

```text
                 Supplier
                    │
          ┌─────────┼─────────┐
          ↓         ↓         ↓
       Batch A   Batch B    Batch C
          │         │         │
       Kitchen   Kitchen    Kitchen
          │         │         │
        Dishes   Dishes    Dishes
```

This allows operators to understand supplier dependency and quickly determine the potential network-wide impact of a supplier-level contamination event.

### Supplier-Level Investigation

An operator should be able to select a supplier and ask:

- Which active batches originated from this supplier?
- Which kitchens received those batches?
- Which dishes use those ingredients?
- How many orders/customers could be affected?
- Which batches are currently YELLOW or RED?

This extends the original batch-centric recall workflow into a broader **supplier-to-network traceability view**.

# 16. Final Project Definition

**TRACE-NCR (Graph-Based Food Traceability & Recall Intelligence)** is a Neo4j-powered food supply-chain traceability and recall engine for cloud-kitchen networks in Delhi NCR.

It models the relationship between suppliers, ingredient batches, processing facilities, cloud kitchens, dishes, orders, and customers. When an ingredient batch is suspected or confirmed to be contaminated, the system uses temporal filtering and multi-hop Cypher traversal to determine the downstream impact.

The central output is an actionable recall graph:

```text
CONTAMINATED BATCH
        │
        ├──► AFFECTED KITCHENS
        │
        ├──► AFFECTED DISHES
        │
        ├──► AFFECTED ORDERS
        │
        └──► AFFECTED CUSTOMERS
```

The project combines **Neo4j graph modeling, Cypher traversal, temporal risk analysis, and an operational dashboard** to turn food-contamination tracing into a fast, structured recall workflow.

---

## Source Basis

This final specification consolidates the supplied project specification and the photographed problem statement. The project specification defines the Neo4j graph model, temporal traffic-light risk model, traversal requirements, recall outputs, and Python/Streamlit/FastAPI stack. 
