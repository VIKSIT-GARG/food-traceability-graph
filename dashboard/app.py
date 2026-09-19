"""Streamlit dashboard for the Food Traceability Graph.
Bespoke incident command & cold-chain traceability for Delhi-NCR cloud kitchens.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config                     # noqa: E402
from core import risk             # noqa: E402
from core import traceability as tr  # noqa: E402
from core.viz import network_figure, timeline_figure  # noqa: E402
from dashboard import theme       # noqa: E402

st.set_page_config(
    page_title="SafeTrace NCR — Food Traceability Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.inject_theme()

TRANSITION_LABELS = {
    "YELLOW": "Quarantine (Yellow) — contamination suspected",
    "RED": "Immediate Recall (Red) — contamination confirmed",
    "GREEN": "Clear (Green) — cleared after laboratory verification",
}


def fmt_dt(value):
    if value is None:
        return "—"
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kolkata").tz_localize(None)
    return ts.strftime("%d %b %Y, %H:%M IST")


# ---------------------------------------------------------------- Sidebar navigation
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.25rem 0 0.85rem 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 1rem;">
            <div style="font-size: 1.15rem; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 0.45rem;">
                <span style="color: #0369a1; font-size: 1.25rem;">🛡️</span> SafeTrace NCR
            </div>
            <div style="font-size: 0.78rem; color: #475569; margin-top: 0.2rem; line-height: 1.3;">
                Delhi-NCR Cloud Kitchen Recall & Traceability Engine
            </div>
            <div style="margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.2rem 0.55rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; font-size: 0.7rem; color: #15803d; font-weight: 600;">
                <span>●</span> FSSAI / FoSCoS Aligned
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["Risk Dashboard", "Graph Explorer", "Reverse Trace", "Supplier Intelligence", "Graph Architecture"],
        label_visibility="collapsed",
    )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    with st.expander("Database seed & incident baseline"):
        st.caption("Baseline data is anchored to the Delhi-NCR paneer contamination incident (10 Sep 2025, 14:00 IST).")
        if st.button("Reset demo dataset", use_container_width=True):
            from db import seed
            seed.seed(clear=True)
            st.success("Demo dataset reseeded.")
            st.rerun()

try:
    tr.list_ingredients()
except Exception as e:
    st.error(f"Cannot reach Neo4j at {config.NEO4J_URI}. Verify the database is active (`docker compose up -d`).\n\n{e}")
    st.stop()


# ================================================================ Risk Dashboard
if page == "Risk Dashboard":
    theme.render_command_header(
        title="Incident Command & Risk Dashboard",
        subtitle="Delhi-NCR Central Kitchen Operations · Active surveillance & recall management",
        right_badge_html=theme.status_badge_html("GREEN", "Surveillance Mode"),
    )

    st.subheader("Batch surveillance query")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Search inventory", placeholder="Search by batch ID, ingredient name or supplier...")
    with c2:
        ing = st.selectbox("Filter ingredient", ["All ingredients"] + tr.list_ingredients())
    with c3:
        sup_list = [f"{s['id']} · {s['name']}" for s in tr.list_suppliers()]
        sup = st.selectbox("Filter supplier", ["All suppliers"] + sup_list)

    results = tr.search_batches(
        text=q or None,
        ingredient=None if ing == "All ingredients" else ing,
        supplier_id=None if sup == "All suppliers" else sup.split(" · ")[0],
    )

    if not results:
        st.info("No ingredient batches match the current query. Try expanding the search or reseed the demo dataset.")
        st.stop()

    df = pd.DataFrame(results)
    df["status"] = df["status"].map(lambda s: f"{risk.STATUS_EMOJI[s]} {s}")
    df["manufactured"] = df["manufactured"].map(fmt_dt)
    st.dataframe(
        df.rename(columns={
            "id": "Batch ID", "ingredientName": "Ingredient", "supplier": "Supplier",
            "manufactured": "Manufactured", "status": "Triage Status", "reason": "Audit Reason"
        }),
        use_container_width=True,
        hide_index=True,
    )

    batch_ids = [r["id"] for r in results]
    selected_batch_id = st.selectbox("Inspect batch dossier", batch_ids)
    batch = risk.get_batch(selected_batch_id)

    st.subheader("Batch inspection dossier")
    theme.render_batch_dossier(
        batch,
        window_dt_str=fmt_dt(batch.get("contaminationDate")),
        mfg_dt_str=fmt_dt(batch.get("manufactureDate")),
    )

    # Audited risk state transition
    with st.expander("Audited risk transition (state machine)"):
        current_status = batch["status"]
        allowed = sorted(risk.ALLOWED_TRANSITIONS[current_status])
        if not allowed:
            st.warning(f"Batch {selected_batch_id} is in terminal status RED (Confirmed Contamination). Proceed with recall containment actions below.")
        else:
            with st.form("triage_transition_form"):
                st.markdown(f"**Current state:** `{current_status}` &rarr; Select verified target state:")
                new_status = st.selectbox("Target state", allowed, format_func=lambda s: TRANSITION_LABELS[s])
                reason = st.text_input("Operational reason (mandatory, permanently logged to AuditEvent)")
                contamination_date = None
                if new_status == "YELLOW":
                    st.caption("Specify the estimated moment of temperature abuse / contamination:")
                    dcol, tcol = st.columns(2)
                    d = dcol.date_input("Contamination event date", value=datetime(2025, 9, 10).date())
                    t = tcol.time_input("Contamination event time (IST)", value=datetime(2025, 9, 10, 14, 0).time())
                    contamination_date = datetime.combine(d, t)

                if st.form_submit_button("Commit state transition", type="primary"):
                    if not reason.strip():
                        st.error("Audit trail requirement: A documented reason is required to transition states.")
                    else:
                        try:
                            risk.flag_batch(
                                selected_batch_id,
                                new_status,
                                reason.strip(),
                                actor="dashboard-operator",
                                contamination_date=risk.as_ist(contamination_date) if new_status == "YELLOW" else None,
                            )
                            st.success(f"Batch {selected_batch_id} successfully updated to {new_status}.")
                            st.rerun()
                        except (risk.RiskTransitionError, ValueError) as e:
                            st.error(str(e))

    st.subheader("Downstream containment & blast radius")
    has_cd = batch.get("contaminationDate") is not None
    apply_window = st.checkbox(
        "Apply temporal contamination window",
        value=(batch["status"] == "YELLOW"),
        disabled=not has_cd,
        help="When enabled, only kitchen prep, dish cooking, and customer orders on or after the contamination timestamp count as affected.",
    )
    aw = apply_window if has_cd else None
    impact = tr.impact_report(selected_batch_id, apply_window=aw)

    if impact["scope"] == "windowed":
        st.markdown(
            f"""
            <div class="alert-box alert-warning">
                ⏱ <strong>Temporal window active:</strong> Isolating only kitchen prep, dishes, and orders dispatched on or after <strong>{fmt_dt(impact['window_start'])}</strong>. Earlier shipments cleared safe.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="alert-box alert-info">
                🌐 <strong>Full scope assessment:</strong> Evaluating all downstream usage across Delhi-NCR facilities regardless of timestamp.
            </div>
            """,
            unsafe_allow_html=True,
        )

    m = impact["counts"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Impacted kitchen hubs", m["kitchens"], help="Central preparation facilities that received this lot")
    k2.metric("Affected menu items", m["dishes"], help="Recipes and menu items incorporating this batch")
    k3.metric("Customer orders placed", m["orders"], help="Orders containing affected recipes")
    k4.metric("End consumers exposed", m["customers"], help="Unique customers requiring safety contact")

    tab_k, tab_d, tab_c, tab_t, tab_g, tab_a, tab_r = st.tabs([
        "Central Kitchens",
        "Menu Items",
        "Consumer Outreach",
        "Incident Timeline",
        "Topology Network",
        "Audit Log",
        "FSSAI Regulatory Filing",
    ])

    with tab_k:
        kdf = pd.DataFrame(impact["kitchens"])
        if kdf.empty:
            st.info("No kitchen deliveries recorded for this batch.")
        else:
            kdf["delivery_date"] = kdf["delivery_date"].map(fmt_dt)
            kdf["in_window"] = kdf["in_window"].map(lambda b: "In Window (Quarantined)" if b else "Pre-Incident (Clear)")
            kdf = kdf.rename(columns={
                "kitchen_id": "Kitchen ID", "kitchen": "Hub Name", "location": "NCR Location",
                "delivery_date": "Delivered", "qty_kg": "Volume (kg)",
                "containment": "Quarantine Status", "in_window": "Temporal Risk"
            })
            st.dataframe(kdf, hide_index=True, use_container_width=True)

            b1, b2 = st.columns(2)
            if b1.button("Place quarantine HOLD on affected kitchens", type="primary", use_container_width=True):
                ids = tr.set_kitchen_containment(selected_batch_id, "HOLD")
                st.success(f"Quarantine HOLD active on hubs: {', '.join(ids)}")
                st.rerun()
            if b2.button("Release quarantine holds", use_container_width=True):
                ids = tr.set_kitchen_containment(selected_batch_id, "RELEASED")
                st.success(f"Quarantine released for hubs: {', '.join(ids)}")
                st.rerun()

    with tab_d:
        ddf = pd.DataFrame(impact["dishes"])
        if ddf.empty:
            st.info("No menu items prepared with this batch.")
        else:
            ddf["usage_times"] = ddf["usage_times"].map(lambda l: ", ".join(sorted(fmt_dt(t) for t in l)))
            ddf["blocked"] = ddf["blocked"].map(lambda b: "Blocked (86'd)" if b else "Live on Menu")
            ddf = ddf.rename(columns={
                "dish_id": "Dish ID", "dish": "Recipe Name", "price": "Price (₹)",
                "usage_times": "Preparation Timestamps", "qty_used_kg": "Quantity Used (kg)",
                "blocked": "Online Status"
            })
            st.dataframe(ddf, hide_index=True, use_container_width=True)

            c1, c2 = st.columns(2)
            if c1.button("Block affected dishes (86 from Swiggy/Zomato)", type="primary", use_container_width=True):
                ids = tr.block_affected_dishes(selected_batch_id)
                st.success(f"Blocked dishes from online menus: {', '.join(ids)}")
                st.rerun()
            if c2.button("Unblock dishes (restore to menu)", use_container_width=True):
                ids = tr.unblock_affected_dishes(selected_batch_id)
                st.success(f"Restored dishes to online menus: {', '.join(ids)}")
                st.rerun()

    with tab_c:
        odf = pd.DataFrame(impact["orders"])
        if odf.empty:
            st.info("No customer orders placed within the incident scope.")
        else:
            odf["order_time"] = odf["order_time"].map(fmt_dt)
            st.markdown("##### Consumer safety communication roster")
            st.dataframe(
                odf.rename(columns={
                    "order_id": "Order Ref", "order_time": "Dispatched", "customer_id": "Customer ID",
                    "customer": "Customer Name", "phone": "Contact Phone", "email": "Email Address",
                    "dishes": "Ordered Recipes", "notification_status": "Safety Notice Status"
                }),
                hide_index=True,
                use_container_width=True,
            )
            if st.button("Dispatch emergency safety notice (SMS)", type="primary"):
                n = tr.mark_customers_notified(selected_batch_id, channel="SMS")
                st.success(f"Safety alerts dispatched to {n} customer orders.")
                st.rerun()

    with tab_t:
        tl = tr.batch_timeline(selected_batch_id)
        fig = timeline_figure(tl["events"], tl["contamination_date"])
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No operational events logged for this batch.")

    with tab_g:
        g = tr.network_graph_data(selected_batch_id, apply_window=aw)
        st.plotly_chart(network_figure(g), use_container_width=True)
        if g["truncated"]:
            st.caption("Visualization display capped to the 30 most recent downstream orders.")

    with tab_a:
        rows = risk.audit_trail(selected_batch_id)
        if not rows:
            st.info("No audit entries logged for this batch.")
        else:
            adf = pd.DataFrame(rows)
            adf["timestamp"] = adf["timestamp"].map(fmt_dt)
            st.dataframe(
                adf.rename(columns={
                    "timestamp": "Timestamp", "action": "Action", "actor": "Authorized Actor",
                    "reason": "Audit Justification", "status": "Resulting Status"
                }),
                hide_index=True,
                use_container_width=True,
            )

    with tab_r:
        report = tr.recall_report(selected_batch_id)
        st.markdown(
            """
            <div class="alert-box alert-info">
                📄 <strong>FSSAI statutory recall documentation:</strong> Structured compliance export following Food Safety and Standards (Food Recall Procedure) Regulations.
            </div>
            """,
            unsafe_allow_html=True,
        )

        dcol1, dcol2, dcol3 = st.columns(3)
        dcol1.download_button(
            "Download complete filing (JSON)",
            data=json.dumps(report, indent=2),
            file_name=f"fssai-recall-{selected_batch_id}.json",
            mime="application/json",
            use_container_width=True,
        )
        dcol2.download_button(
            "Download affected hubs (CSV)",
            data=pd.DataFrame(report["distributionAffected"]).to_csv(index=False),
            file_name=f"recall-{selected_batch_id}-kitchens.csv",
            mime="text/csv",
            use_container_width=True,
        )
        dcol3.download_button(
            "Download outreach list (CSV)",
            data=pd.DataFrame(report["consumerNotificationList"]).to_csv(index=False),
            file_name=f"recall-{selected_batch_id}-consumers.csv",
            mime="text/csv",
            use_container_width=True,
        )

        with st.expander("Preview structured statutory payload"):
            st.json(report)

# ================================================================ Graph Explorer (lite)
elif page == "Graph Explorer":
    theme.render_command_header(
        title="Network Topology Explorer",
        subtitle="Multi-echelon supply chain network from live Cypher graph queries",
    )
    st.caption("For full interactive physics canvas (node inspection, blast radius simulation, hop expansion), navigate to Graph Explorer in the main sidebar.")
    batch_list = [r["id"] for r in tr.search_batches()]
    batch_id = st.selectbox("Select focal batch", batch_list)
    aw = st.checkbox("Apply temporal window (if established)", value=False)
    g = tr.network_graph_data(batch_id, apply_window=aw if aw else None)
    st.plotly_chart(network_figure(g), use_container_width=True)
    if g["truncated"]:
        st.caption("Visualization display capped to the 30 most recent downstream orders.")

# ================================================================ Reverse Trace
elif page == "Reverse Trace":
    theme.render_command_header(
        title="Reverse Traceability Investigation",
        subtitle="Forensic upstream inquiry: Trace consumer complaints back to raw ingredient lots and source suppliers",
    )
    mode = st.radio("Trace origin point", ["Customer complaint", "Dispatched order", "Prepared recipe"], horizontal=True)
    result = None

    if mode == "Customer complaint":
        cus = st.selectbox(
            "Select customer",
            tr.list_customers(),
            format_func=lambda c: f"{c['id']} — {c['name']} ({c['phone']})",
        )
        if st.button("Execute upstream trace", type="primary"):
            result = tr.reverse_trace(customer_id=cus["id"])
    elif mode == "Dispatched order":
        oid = st.text_input("Enter order reference", placeholder="e.g. ORD-1007")
        if st.button("Execute upstream trace", type="primary") and oid.strip():
            result = tr.reverse_trace(order_id=oid.strip())
    else:
        dish = st.selectbox(
            "Select prepared recipe",
            tr.list_dishes(),
            format_func=lambda d: f"{d['id']} — {d['name']} (₹{d.get('price', 0)})",
        )
        if st.button("Execute upstream trace", type="primary"):
            result = tr.reverse_trace(dish_id=dish["id"])

    if result:
        if result["flagged_batch_used"]:
            st.markdown(
                """
                <div class="alert-box alert-danger">
                    🚨 <strong>Critical safety alert:</strong> This supply trail contains at least one quarantined or recalled (YELLOW/RED) ingredient batch!
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="alert-box alert-info">
                    ✅ <strong>Clear:</strong> No flagged batches identified on this upstream supply chain path.
                </div>
                """,
                unsafe_allow_html=True,
            )

        bdf = pd.DataFrame(result["batches"])
        if not bdf.empty:
            bdf["used_at"] = bdf["used_at"].map(fmt_dt)
            bdf["status"] = bdf["status"].map(lambda s: f"{risk.STATUS_EMOJI.get(s, '')} {s}")
            st.subheader("Ingredient batches involved")
            st.dataframe(
                bdf.rename(columns={"id": "Batch ID", "ingredient": "Ingredient", "status": "Triage Status", "used_at": "Prep Timestamp"}),
                hide_index=True,
                use_container_width=True,
            )

        sdf = pd.DataFrame(result["suppliers"])
        if not sdf.empty:
            st.subheader("Source suppliers involved")
            st.dataframe(
                sdf.rename(columns={"id": "Supplier Ref", "name": "Vendor Name"}),
                hide_index=True,
                use_container_width=True,
            )

        if result["rows"]:
            rdf = pd.DataFrame([{
                **r,
                "batches": ", ".join(b["id"] for b in r["batches"]),
                "suppliers": ", ".join(s["name"] for s in r["suppliers"]),
            } for r in result["rows"]])
            rdf["order_time"] = rdf["order_time"].map(fmt_dt)
            st.subheader("Order-by-order audit trail")
            st.dataframe(
                rdf.rename(columns={
                    "order_id": "Order", "order_time": "Placed", "kitchen": "Kitchen Hub",
                    "dish": "Dish", "batches": "Batches", "suppliers": "Suppliers"
                }),
                hide_index=True,
                use_container_width=True,
            )

# ================================================================ Supplier Intelligence
elif page == "Supplier Intelligence":
    theme.render_command_header(
        title="Supplier Risk & Quality Intelligence",
        subtitle="Vendor performance, historical batch compliance, and downstream exposure across Delhi-NCR",
    )
    sup = st.selectbox(
        "Select vendor",
        tr.list_suppliers(),
        format_func=lambda s: f"{s['id']} — {s['name']} ({s.get('location', 'Delhi-NCR')})",
    )
    intel = tr.supplier_intelligence(sup["id"])
    s = intel["summary"]

    st.subheader(f"{s['supplier']['name']} — {s['supplier']['location']}")
    row1 = st.columns(4)
    row1[0].metric("Total lots supplied", s["total_batches"])
    row1[1].metric("Active lots in circulation", s["active_batches"])
    row1[2].metric("Clear lots (GREEN)", s["green"])
    row1[3].metric("Suspected lots (YELLOW)", s["yellow"])

    row2 = st.columns(4)
    row2[0].metric("Recalled lots (RED)", s["red"])
    row2[1].metric("Statutory recall events", intel["recall_events"])
    row2[2].metric("Kitchen hubs impacted", intel["network_impact"]["kitchens"])
    row2[3].metric("Consumers exposed", intel["network_impact"]["customers"])

    st.caption(f"Orders currently exposed to flagged batches from this supplier: {intel['network_impact']['orders']}")

    st.subheader("Batch inventory ledger")
    bdf = pd.DataFrame(intel["batches"])
    bdf["status"] = bdf["status"].map(lambda x: f"{risk.STATUS_EMOJI.get(x, '')} {x}")
    bdf["manufactured"] = bdf["manufactured"].map(fmt_dt)
    bdf["active"] = bdf["active"].map(lambda b: "In circulation" if b else "Depleted / archived")
    st.dataframe(
        bdf.rename(columns={
            "id": "Batch ID", "ingredient": "Ingredient", "manufactured": "Manufacture Timestamp",
            "status": "Current Status", "active": "Lifecycle State"
        }),
        hide_index=True,
        use_container_width=True,
    )

# ================================================================ Graph Architecture
else:
    theme.render_command_header(
        title="Graph Architecture & Compliance Schema",
        subtitle="Neo4j labeled property graph schema for cloud kitchen supply chain traceability",
    )

    st.subheader("Entity relationship schema")
    st.code(
        """(Supplier)-[:SUPPLIED]->(Batch)
(Batch)-[:PROCESSED_AT {timestamp}]->(Facility)
(Batch)-[:DELIVERED_TO {deliveryDate, qtyKg}]->(CloudKitchen)
(Batch)-[:USED_IN_DISH {timestamp, quantity}]->(Dish)
(Order)-[:CONTAINS_DISH {quantity}]->(Dish)
(Customer)-[:PLACED_ORDER]->(Order)
(Batch)-[:HAS_EVENT]->(AuditEvent)
(Customer)-[:NOTIFIED_FOR {status, channel}]->(Order)""",
        language="cypher",
    )

    st.subheader("Core downstream traversal pattern")
    st.code(
        """MATCH (b:Batch {id: $batch_id})
OPTIONAL MATCH (b)-[:DELIVERED_TO]->(k:CloudKitchen)
OPTIONAL MATCH (b)-[:USED_IN_DISH]->(d:Dish)
OPTIONAL MATCH (o:Order)-[:CONTAINS_DISH]->(d)
OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(o)
RETURN b,
       collect(DISTINCT k) AS affected_kitchens,
       collect(DISTINCT d) AS affected_dishes,
       collect(DISTINCT o) AS affected_orders,
       collect(DISTINCT c) AS affected_customers;""",
        language="cypher",
    )

    st.subheader("Audited state machine")
    st.markdown(
        """
        ```
        [ GREEN: Clear ] ────(contamination suspected)────> [ YELLOW: Quarantine Hold ]
               │                                                      │
               │                                                      │ (confirmed)
               └────────────────(direct recall confirmation)──────────> [ RED: Full Recall ]
        ```
        - **Temporal isolation window:** When transitioning to `YELLOW`, an ISO timestamp marks the beginning of the contamination window. Upstream activities prior to this threshold are verified safe.
        - **Audit trail permanence:** Every status shift, containment hold, dish block, and customer notice creates a distinct `AuditEvent` node with actor attribution, timestamp, and justification.
        """
    )
