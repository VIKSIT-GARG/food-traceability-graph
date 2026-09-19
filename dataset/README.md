# 📦 Food Traceability Graph — Dataset Documentation & CSV Exports

This directory contains the complete deterministic Delhi-NCR cloud kitchen supply chain dataset exported from the live Neo4j knowledge graph.

---

## 📂 Directory Layout

```text
dataset/
├── food_traceability_end_to_end.csv  # Complete denormalized multi-hop traceability master table
├── all_nodes.csv                     # Unified flat catalog of all graph nodes (97 nodes)
├── all_relationships.csv             # Unified flat catalog of all graph edges (232 relationships)
├── nodes/                            # Entity tables (Domain Nodes)
│   ├── suppliers.csv                 # Raw food suppliers & dairy farms (5 records)
│   ├── batches.csv                   # Raw ingredient batches with safety status (10 records)
│   ├── facilities.csv                # Processing facilities, chilling units, testing labs (4 records)
│   ├── cloud_kitchens.csv            # Cloud kitchen preparation hubs across NCR (6 records)
│   ├── dishes.csv                    # Menu items and recipe catalog (10 records)
│   ├── orders.csv                    # Consumer order records (21 records)
│   ├── customers.csv                 # Consumer contact and safety outreach profiles (12 records)
│   └── audit_events.csv              # Immutable food-safety audit log entries (29 records)
└── relationships/                    # Topology tables (Graph Edges)
    ├── supplies.csv                  # (:Supplier)-[:SUPPLIES]->(:Batch)
    ├── processed_at.csv              # (:Batch)-[:PROCESSED_AT]->(:Facility)
    ├── delivered_to.csv              # (:Batch)-[:DELIVERED_TO]->(:CloudKitchen)
    ├── used_in.csv                   # (:CloudKitchen)-[:USED_IN]->(:Dish)
    ├── contains_dish.csv             # (:Order)-[:CONTAINS_DISH]->(:Dish)
    ├── order_placed_at.csv           # (:Order)-[:PLACED_AT]->(:CloudKitchen)
    ├── placed_order.csv              # (:Customer)-[:PLACED_ORDER]->(:Order)
    ├── audit_has_event.csv           # (:Batch|Supplier)-[:HAS_EVENT]->(:AuditEvent)
    └── customer_notified_for.csv     # (:Customer)-[:NOTIFIED_FOR]->(:Order)
```

---

## 🌟 Master Denormalized File
### `food_traceability_end_to_end.csv`
A flattened multi-hop audit trail (289 rows) mapping the complete supply chain:
```text
(Supplier) ➔ (Batch) ➔ (CloudKitchen) ➔ (Dish) ➔ (Order) ➔ (Customer)
```

### Key Columns:
- `supplier_id`, `supplier_name`, `supplier_location`
- `batch_id`, `ingredient`, `batch_status`, `batch_manufacture_date`, `contamination_date`
- `kitchen_id`, `kitchen_name`, `kitchen_location`, `delivery_date`, `delivery_qty_kg`
- `dish_id`, `dish_name`, `dish_price`, `dish_blocked`
- `kitchen_cooking_timestamp`, `usage_qty_kg`
- `order_id`, `order_timestamp`
- `customer_id`, `customer_name`, `customer_phone`, `customer_email`

---

## 📋 Entity Node Schemas (`nodes/`)

### 1. `suppliers.csv` (5 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Unique Supplier ID | `SUP-002` |
| `name` | String | Commercial entity name | `Gopal Dairy` |
| `location` | String | Operational mandi/hub | `Sector 18, Noida` |
| `status` | String | Current risk level (`GREEN`, `YELLOW`, `RED`) | `GREEN` |

### 2. `batches.csv` (10 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Batch Lot ID | `BATCH-PANEER-001` |
| `ingredientName` | String | Primary ingredient | `Paneer` |
| `status` | String | Safety status | `GREEN` / `YELLOW` / `RED` |
| `manufactureDate` | ISO 8601 | Production timestamp | `2025-09-08T06:00:00+05:30` |
| `expiryDate` | ISO 8601 | Expiration timestamp | `2025-09-12T06:00:00+05:30` |
| `contaminationDate`| ISO 8601 | Suspected incident timestamp | `2025-09-10T14:00:00+05:30` |
| `statusReason` | String | Audit reason code | `Customer complaints` |

### 3. `facilities.csv` (4 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Processing Facility ID | `FAC-001` |
| `name` | String | Processing unit name | `Central Processing Hub` |
| `location` | String | Hub location | `Gurugram` |
| `stepType` | String | Processing capability | `Cleaning & Cutting` |

### 4. `cloud_kitchens.csv` (6 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Cloud Kitchen ID | `CK-001` |
| `name` | String | Prep kitchen brand name | `Spice Hub Kitchen` |
| `location` | String | Metro zone | `Cyber Hub, Gurugram` |
| `containmentStatus` | String | Facility containment | `NORMAL` / `HOLD` |

### 5. `dishes.csv` (10 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Menu Item ID | `DSH-001` |
| `name` | String | Recipe / Dish Name | `Paneer Butter Masala` |
| `price` | Float | Menu price (INR ₹) | `320.0` |
| `blocked` | Boolean | Immediate menu quarantine | `true` / `false` |

### 6. `orders.csv` (21 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | POS Order ID | `ORD-1001` |
| `timestamp` | ISO 8601 | Order creation time | `2025-09-09T12:30:00+05:30` |

### 7. `customers.csv` (12 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Consumer profile ID | `CUS-001` |
| `name` | String | Consumer name | `Aarav Sharma` |
| `phone` | String | Contact for safety outreach | `+91-98110-11201` |
| `email` | String | Email notification address | `aarav.sharma@example.com` |

### 8. `audit_events.csv` (29 records)
| Column | Type | Description | Example |
|---|---|---|---|
| `id` | String | Unique Audit Event ID | `EVT-483a91...` |
| `type` | String | Event classification | `STATUS_CHANGE`, `MENU_PULL` |
| `timestamp` | ISO 8601 | Event commit time | `2025-09-10T14:15:00+05:30` |
| `actor` | String | Originating operator ID | `operator` |
| `detail` | String | Audit narrative | `Containment 'HOLD': CK-001` |

---

## 🔗 Graph Relationship Schemas (`relationships/`)

1. **`supplies.csv`**: `source_id` (Supplier) ➔ `target_id` (Batch)
2. **`processed_at.csv`**: `source_id` (Batch) ➔ `target_id` (Facility), `timestamp`
3. **`delivered_to.csv`**: `source_id` (Batch) ➔ `target_id` (CloudKitchen), `delivery_date`, `qty_kg`
4. **`used_in.csv`**: `source_id` (CloudKitchen) ➔ `target_id` (Dish), `batch_id`, `timestamp`, `qty_kg`
5. **`contains_dish.csv`**: `source_id` (Order) ➔ `target_id` (Dish), `quantity`
6. **`order_placed_at.csv`**: `source_id` (Order) ➔ `target_id` (CloudKitchen)
7. **`placed_order.csv`**: `source_id` (Customer) ➔ `target_id` (Order)
8. **`audit_has_event.csv`**: `source_id` (Batch/Supplier), `source_label`, `target_id` (AuditEvent)
9. **`customer_notified_for.csv`**: `source_id` (Customer) ➔ `target_id` (Order), `status`, `channel`, `notified_at`

---

## 🔄 How to Re-Export
To re-export this dataset after applying updates or graph mutations:
```bash
python cli.py export-csv
# or directly:
python scripts/export_dataset_csv.py
```
