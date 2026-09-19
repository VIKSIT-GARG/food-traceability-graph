"""Graph-first explorer: pan/zoom, click-to-inspect, path tracing, filters,
expand/collapse, recall blast-radius — all rendered from live Cypher results.
"""
import sys
from datetime import date, datetime, time as dtime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from streamlit_agraph import Config, Edge, Node, agraph

from core import graph_api as gx
from core import risk
from core.risk import ALLOWED_TRANSITIONS, STATUS_EMOJI, RiskTransitionError
from dashboard import theme

st.set_page_config(
    page_title="Graph Explorer — SafeTrace NCR",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.inject_theme()

NODE_COLOR = {
    "Supplier": "#4338ca",     # Deep indigo
    "Facility": "#64748b",     # Cool industrial slate
    "CloudKitchen": "#0284c7", # Hub blue
    "Dish": "#d97706",         # Culinary gold
    "Order": "#0d9488",        # Dispatch teal
    "Customer": "#e11d48",     # Consumer rose
}
STATUS_COLOR = {
    "GREEN": "#15803d",
    "YELLOW": "#b45309",
    "RED": "#b91c1c",
}
NODE_SIZE = {
    "Supplier": 24,
    "Batch": 30,
    "Facility": 16,
    "CloudKitchen": 22,
    "Dish": 16,
    "Order": 14,
    "Customer": 14,
}
BLAST = "#dc2626"
HL_EDGE, BLAST_EDGE, PLAIN_EDGE = "#f59e0b", "#dc2626", "#cbd5e1"

ss = st.session_state
for k, v in {"g_nodes": {}, "g_edges": {}, "selected": None, "hl_nodes": set(),
             "hl_edges": set(), "sim": None, "loaded": False}.items():
    ss.setdefault(k, v)


# ---------------------------------------------------------------- formatting helpers

def fmt_dt(v, pattern="%d %b %Y, %H:%M IST"):
    if isinstance(v, datetime):
        return v.strftime(pattern)
    return str(v)


def meta_str(props):
    return "; ".join(f"{k}: {fmt_dt(v)}" for k, v in (props or {}).items()) or "—"


def node_text(label, p):
    if label == "Batch":
        return f"{p.get('id')}\n{p.get('ingredientName', '')} {STATUS_EMOJI.get(p.get('status'), '')}"
    return p.get("name") or p.get("id")


def edge_view(e):
    typ, props = e["type"], e["props"]
    if typ == "DELIVERED_TO":
        qty = sum(p.get("qtyKg") or 0 for p in props)
        title = "Delivered: " + "; ".join(
            f"{fmt_dt(p['deliveryDate'])} · {p.get('qtyKg')} kg"
            for p in props if p.get("deliveryDate"))
        return f"{qty:g} kg", title
    if typ == "USED_IN_DISH":
        times = sorted(p["timestamp"] for p in props if p.get("timestamp"))
        qty = sum(p.get("quantity") or 0 for p in props)
        label = fmt_dt(times[-1], "%d %b %H:%M") + (f" ×{len(times)}" if len(times) > 1 else "")
        return label, f"Used {qty:g} kg total · " + "; ".join(fmt_dt(t) for t in times)
    if typ == "PROCESSED_AT":
        t = next((p.get("timestamp") for p in props if p.get("timestamp")), None)
        return (fmt_dt(t, "%d %b %H:%M") if t else "processed"), "Processing step · " + meta_str(props[0])
    if typ == "CONTAINS_DISH":
        q = sum(p.get("quantity") or 0 for p in props)
        return f"×{q:g}", f"Order contains {q:g} unit(s)"
    if typ == "SUPPLIED":
        return "SUPPLIED", "Supplier provided this batch"
    if typ == "PLACED_ORDER":
        return "", "Customer placed this order"
    return typ, typ


# ---------------------------------------------------------------- rendering

def build_agraph(selected):
    nodes, edges = [], []
    sim = ss.sim
    for nid, nd in ss.g_nodes.items():
        label, p = nd["label"], nd["props"]
        color = STATUS_COLOR.get(p.get("status"), "#455a64") if label == "Batch" \
            else NODE_COLOR.get(label, "#455a64")
        size = NODE_SIZE.get(label, 14)
        text = node_text(label, p)
        if sim:
            if nid in sim["nodes"]:
                text = "💥 " + text
                size += 6
                if label != "Batch":
                    color = BLAST
            elif label != "Batch":
                color = "#e2e8f0"           # dim nodes outside the blast radius
        if nid in ss.hl_nodes:
            size += 3
        if nid == selected:
            size += 7
        nodes.append(Node(id=nid, label=text, size=size, color=color, shape="dot",
                          title=f"{label} · {p.get('id')}"))
    for key, e in ss.g_edges.items():
        if e["src"] not in ss.g_nodes or e["dst"] not in ss.g_nodes:
            continue
        label, title = edge_view(e)
        color = HL_EDGE if key in ss.hl_edges else \
            (BLAST_EDGE if sim and key in sim["edges"] else PLAIN_EDGE)
        edges.append(Edge(source=e["src"], target=e["dst"], label=label, title=title, color=color))

    cfg = Config(width=1180, height=600, directed=True, physics=True,
                 nodeHighlightBehavior=True, highlightColor="#fda4af", collapsible=False,
                 node={"labelProperty": "label"},
                 link={"labelProperty": "label", "renderLabel": True})
    return agraph(nodes=nodes, edges=edges, config=cfg)


def merge_store(store):
    for nid, nd in store["nodes"].items():
        cur = ss.g_nodes.get(nid)
        if cur is None:
            ss.g_nodes[nid] = nd
        else:
            cur["props"] = {**cur["props"], **nd["props"]}
    for key, e in store["edges"].items():
        ss.g_edges.setdefault(key, e)


# ---------------------------------------------------------------- sidebar: search & filters

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.25rem 0 0.85rem 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 1rem;">
            <div style="font-size: 1.15rem; font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 0.45rem;">
                <span style="color: #0369a1; font-size: 1.25rem;">🧭</span> Graph Explorer
            </div>
            <div style="font-size: 0.78rem; color: #475569; margin-top: 0.2rem;">
                Live Cypher Multi-Echelon Network
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    opts = gx.filter_options()
    with st.form("filters"):
        st.markdown("**Network query filters**")
        q = st.text_input("Search entity", placeholder="Batch / ingredient / supplier / hub")
        sup = st.selectbox("Supplier", ["All suppliers"] + [f"{s['id']} — {s['name']}" for s in opts["suppliers"]])
        kit = st.selectbox("Cloud kitchen hub", ["All kitchens"] + [f"{k['id']} — {k['name']}" for k in opts["kitchens"]])
        ing = st.selectbox("Ingredient", ["All ingredients"] + opts["ingredients"])
        loc = st.selectbox("NCR Location", ["All locations"] + opts["locations"])
        c1, c2 = st.columns(2)
        dfrom = c1.date_input("Activity from", value=None)
        dto = c2.date_input("Activity to", value=None)

        st.caption("Batch risk grade")
        cg, cy, cr = st.columns(3)
        f_g = cg.checkbox("🟢 Clear", True)
        f_y = cy.checkbox("🟡 Hold", True)
        f_r = cr.checkbox("🔴 Recall", True)

        do_apply = st.form_submit_button("Apply filters", type="primary", use_container_width=True)
        do_reset = st.form_submit_button("Reset network view", use_container_width=True)


def current_filters():
    statuses = [s for s, on in (("GREEN", f_g), ("YELLOW", f_y), ("RED", f_r)) if on]
    return {
        "q": q or None,
        "supplier": None if sup == "All suppliers" else sup.split(" — ")[0],
        "kitchen": None if kit == "All kitchens" else kit.split(" — ")[0],
        "ingredient": None if ing == "All ingredients" else ing,
        "location": None if loc == "All locations" else loc,
        "statuses": None if len(statuses) == 3 else statuses,
        "date_from": dfrom,
        "date_to": dto,
    }


def load_network():
    store = gx.fetch_subgraph(**current_filters())
    ss.g_nodes, ss.g_edges = store["nodes"], store["edges"]
    ss.hl_nodes, ss.hl_edges, ss.sim = set(), set(), None
    if ss.selected not in ss.g_nodes:
        ss.selected = None


if do_reset or not ss.loaded or do_apply:
    load_network()
    ss.loaded = True

# ---------------------------------------------------------------- header + recall banner

if ss.sim:
    c = ss.sim["counts"]
    theme.render_command_header(
        title="Interactive Graph Explorer · Recall Simulation Active",
        subtitle=f"Batch {ss.sim['batch']} · Blast radius: {c['kitchens']} kitchens, {c['dishes']} recipes, {c['orders']} orders, {c['customers']} consumers",
        right_badge_html=theme.status_badge_html("RED", "Blast Radius Simulated"),
    )
else:
    theme.render_command_header(
        title="Interactive Graph Explorer",
        subtitle="Full supply network topology: Pan, zoom, inspect nodes, and simulate contamination blast radius",
        right_badge_html=theme.status_badge_html("GREEN", "Network Stable"),
    )

if not ss.g_nodes:
    st.warning("No nodes match the selected filter criteria. Widen your parameters or select 'Reset network view'.")
    st.stop()

# ---------------------------------------------------------------- graph canvas

sel_click = build_agraph(ss.selected)
if sel_click:
    ss.selected = sel_click

st.markdown(
    f"""
    <div style="font-size: 0.78rem; color: #475569; margin-top: 0.25rem; display: flex; flex-wrap: wrap; gap: 0.85rem; align-items: center; background: #ffffff; padding: 0.5rem 0.85rem; border: 1px solid #e2e8f0; border-radius: 6px;">
        <span><strong>Live Cypher:</strong> {len(ss.g_nodes)} nodes · {len(ss.g_edges)} relationships</span>
        <span><span style="color: #4338ca;">●</span> Supplier</span>
        <span><span style="color: #ea580c;">●</span> Batch (🟢 Safe / 🟡 Hold / 🔴 Recall)</span>
        <span><span style="color: #64748b;">●</span> Facility</span>
        <span><span style="color: #0284c7;">●</span> Cloud Kitchen</span>
        <span><span style="color: #d97706;">●</span> Dish</span>
        <span><span style="color: #0d9488;">●</span> Order</span>
        <span><span style="color: #e11d48;">●</span> Customer</span>
        <span><span style="color: #dc2626; font-weight: 700;">💥</span> Blast radius</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- selected-node panel

st.divider()
sel = ss.selected
sel_label = ss.g_nodes[sel]["label"] if sel in ss.g_nodes else None

if sel and sel_label:
    p = ss.g_nodes[sel]["props"]
    st.markdown(f"### Node dossier: `{sel}` ({sel_label})")

    if sel_label == "Batch":
        try:
            b = risk.get_batch(sel)
            theme.render_batch_dossier(
                b,
                window_dt_str=fmt_dt(b.get("contaminationDate")),
                mfg_dt_str=fmt_dt(b.get("manufactureDate")),
            )
        except Exception:
            pass

    props, rels = gx.node_details(sel_label, sel)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("**Node properties**")
        if props:
            st.dataframe(
                pd.DataFrame([{"Field": k, "Value": fmt_dt(v)} for k, v in props.items() if k != "_labels"]),
                hide_index=True,
                use_container_width=True,
            )
    with c2:
        st.markdown("**Connected relationships & metadata**")
        if rels:
            st.dataframe(
                pd.DataFrame([{
                    "Relationship": r["rel"],
                    "Direction": "&rarr;" if r["outbound"] else "&larr;",
                    "Target": f"{r['other_label']} {r['other']}",
                    "Metadata": meta_str(r["meta"]),
                } for r in rels]),
                hide_index=True,
                use_container_width=True,
            )

    # ------------------------------------------------------------ action bar
    st.markdown("##### Operational actions")
    a1, a2, a3, a4, a5, a6 = st.columns(6)
    if a1.button("Trace upstream", disabled=sel is None, use_container_width=True):
        res = gx.trace(sel_label, sel, "up")
        merge_store(res)
        ss.hl_nodes, ss.hl_edges = set(res["nodes"]), set(res["edges"])
        st.rerun()
    if a2.button("Trace downstream", disabled=sel is None, use_container_width=True):
        res = gx.trace(sel_label, sel, "down")
        merge_store(res)
        ss.hl_nodes, ss.hl_edges = set(res["nodes"]), set(res["edges"])
        st.rerun()
    if a3.button("Expand +1 hop", disabled=sel is None, use_container_width=True):
        merge_store(gx.neighborhood(sel_label, sel))
        st.rerun()
    if a4.button("Collapse branch", disabled=sel is None, use_container_width=True):
        desc = gx.descendants(sel_label, sel, {"nodes": ss.g_nodes, "edges": ss.g_edges})
        for nid in desc:
            ss.g_nodes.pop(nid, None)
        ss.g_edges = {k: e for k, e in ss.g_edges.items() if e["src"] not in desc and e["dst"] not in desc}
        ss.hl_nodes -= desc
        ss.sim = None
        st.rerun()
    if a5.button("Simulate recall blast radius", disabled=sel_label != "Batch", type="primary", use_container_width=True):
        res = gx.blast_radius(sel)
        merge_store(res["store"])
        ss.sim = {"batch": sel, "nodes": res["nodes"], "counts": res["counts"]}
        st.rerun()
    if a6.button("Clear simulation", disabled=not ss.sim, use_container_width=True):
        ss.sim = None
        st.rerun()

    # ------------------------------------------------------------ activate recall (writes)
    if sel_label == "Batch":
        with st.expander("Commit statutory recall transition (Neo4j audited)"):
            nxt = sorted(ALLOWED_TRANSITIONS.get(p.get("status"), set()))
            if not nxt:
                st.info("Batch is in terminal RED state — recall active. Use Risk Dashboard for kitchen holds and dish blocking.")
            else:
                with st.form("activate_recall_form"):
                    st.caption(f"Transition follows the audited state machine: {p.get('status')} &rarr; {' / '.join(nxt)}")
                    target = st.selectbox("Set triage state to", nxt)
                    reason = st.text_input("Operational reason (stored on AuditEvent)")
                    cd = None
                    if target == "YELLOW":
                        dc, tc = st.columns(2)
                        dd = dc.date_input("Contamination from", value=date(2025, 9, 10))
                        tt = tc.time_input("Time (IST)", value=dtime(14, 0))
                        cd = datetime.combine(dd, tt)
                    if st.form_submit_button("Commit & render blast radius", type="primary"):
                        try:
                            risk.flag_batch(
                                sel,
                                target,
                                reason or "Operational recall flag from Graph Explorer",
                                actor="graph-explorer",
                                contamination_date=risk.as_ist(cd) if target == "YELLOW" else None,
                            )
                            res = gx.blast_radius(sel)
                            merge_store(res["store"])
                            fresh, _ = gx.node_details("Batch", sel)
                            if fresh:
                                ss.g_nodes[sel]["props"] = fresh
                            ss.sim = {"batch": sel, "nodes": res["nodes"], "counts": res["counts"]}
                            st.rerun()
                        except (RiskTransitionError, ValueError) as ex:
                            st.error(str(ex))
else:
    st.info("Select any node on the graph canvas to inspect properties, trace upstream/downstream paths, expand neighborhoods, or simulate recall blast radius.")
