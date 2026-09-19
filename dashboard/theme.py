"""Design system, custom styling, and UI components for Food Traceability Graph.
Bespoke visual identity for Delhi-NCR Cloud Kitchen Recall & Traceability Operations.
"""

import html
import streamlit as st

# ---------------------------------------------------------------- Palette tokens
PALETTE = {
    "bg_page": "#f8fafc",          # Cool zinc background
    "bg_card": "#ffffff",          # Pure surface
    "border_subtle": "#e2e8f0",    # Hairline divider
    "border_medium": "#cbd5e1",    # Input & card borders
    "ink_primary": "#0f172a",      # Authoritative dark slate text
    "ink_muted": "#475569",        # Metadata / secondary text
    "ink_faint": "#94a3b8",        # Subtle hints
    "brand_primary": "#0369a1",    # Oceanic cold-chain blue
    "brand_dark": "#0c4a6e",       # Deep navy
    "brand_light": "#e0f2fe",      # Ice blue highlight
    "status_green": "#15803d",     # Safe / cleared green
    "status_green_bg": "#f0fdf4",
    "status_green_border": "#bbf7d0",
    "status_yellow": "#b45309",    # Suspected / quarantine amber
    "status_yellow_bg": "#fffbeb",
    "status_yellow_border": "#fde68a",
    "status_red": "#b91c1c",       # Confirmed recall red
    "status_red_bg": "#fef2f2",
    "status_red_border": "#fecaca",
}

# Graph visualization tokens
GRAPH_COLORS = {
    "Supplier": "#4338ca",     # Deep indigo
    "Batch": "#ea580c",        # Amber orange
    "Facility": "#64748b",     # Industrial slate
    "CloudKitchen": "#0284c7", # Hub blue
    "Dish": "#d97706",         # Culinary gold
    "Order": "#0d9488",        # Dispatch teal
    "Customer": "#e11d48",     # Rose red
}

STATUS_COLORS = {
    "GREEN": "#15803d",
    "YELLOW": "#b45309",
    "RED": "#b91c1c",
}

# ---------------------------------------------------------------- Global CSS Theme

THEME_CSS = """
<style>
/* Modern typography and base reset */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #0f172a;
}

/* Background refinement */
.stApp {
    background-color: #f8fafc;
}

/* Header & title styling */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    color: #0f172a !important;
    letter-spacing: -0.02em !important;
}

h1 {
    font-size: 1.75rem !important;
    margin-bottom: 0.5rem !important;
}

h2 {
    font-size: 1.25rem !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.75rem !important;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid #e2e8f0;
}

h3 {
    font-size: 1.05rem !important;
    margin-top: 1rem !important;
}

/* Streamlit container padding */
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3rem !important;
    max-width: 1380px !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
}

/* Primary command header banner */
.command-header {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.command-header-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.command-header-meta {
    font-size: 0.8rem;
    color: #475569;
    margin-top: 0.15rem;
}

/* Status Pill Indicators */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0.01em;
}

.status-pill-green {
    background-color: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
}

.status-pill-yellow {
    background-color: #fffbeb;
    color: #b45309;
    border: 1px solid #fde68a;
}

.status-pill-red {
    background-color: #fef2f2;
    color: #b91c1c;
    border: 1px solid #fecaca;
}

/* Dossier Card Container */
.dossier-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin: 0.75rem 0 1.25rem 0;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.dossier-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.35rem;
}

.dossier-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #f1f5f9;
}

.dossier-cell-label {
    font-size: 0.72rem;
    color: #64748b;
    margin-bottom: 0.15rem;
}

.dossier-cell-value {
    font-size: 0.88rem;
    font-weight: 600;
    color: #0f172a;
}

/* Metric summary cards */
[data-testid="stMetric"] {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.85rem 1rem !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    color: #475569 !important;
    font-weight: 500 !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.25rem;
}

.stTabs [data-baseweb="tab"] {
    height: 2.25rem;
    padding: 0 0.85rem;
    background-color: transparent;
    border-radius: 6px;
    color: #475569;
    font-size: 0.82rem;
    font-weight: 500;
    border: none !important;
    transition: all 0.15s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    background-color: #f1f5f9;
    color: #0f172a;
}

.stTabs [aria-selected="true"] {
    background-color: #e0f2fe !important;
    color: #0369a1 !important;
    font-weight: 600 !important;
}

/* Button enhancements */
.stButton > button {
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    padding: 0.35rem 0.85rem !important;
    border: 1px solid #cbd5e1 !important;
    background-color: #ffffff !important;
    color: #0f172a !important;
    transition: all 0.15s ease !important;
}

.stButton > button:hover {
    border-color: #94a3b8 !important;
    background-color: #f8fafc !important;
    color: #0369a1 !important;
}

.stButton > button[kind="primary"] {
    background-color: #0f172a !important;
    border-color: #0f172a !important;
    color: #ffffff !important;
}

.stButton > button[kind="primary"]:hover {
    background-color: #1e293b !important;
    border-color: #1e293b !important;
    color: #ffffff !important;
}

/* Download button */
.stDownloadButton > button {
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    border: 1px solid #cbd5e1 !important;
    background-color: #ffffff !important;
    color: #0f172a !important;
}

/* Dataframe & Tables */
[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

/* Notice and Alert boxes */
.alert-box {
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.82rem;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.alert-warning {
    background-color: #fffbeb;
    border: 1px solid #fde68a;
    color: #92400e;
}

.alert-danger {
    background-color: #fef2f2;
    border: 1px solid #fecaca;
    color: #991b1b;
}

.alert-info {
    background-color: #f0f9ff;
    border: 1px solid #bae6fd;
    color: #0369a1;
}

/* Code and identifiers */
code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82em !important;
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
    padding: 0.15rem 0.35rem !important;
    border-radius: 4px !important;
    border: 1px solid #e2e8f0;
}
</style>
"""


def inject_theme():
    """Injects the cohesive design system CSS into the current Streamlit view."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def status_badge_html(status: str, detail: str = "") -> str:
    """Returns accessible HTML for an official food safety status badge."""
    s = (status or "GREEN").upper()
    if s == "GREEN":
        cls = "status-pill-green"
        text = "Clear (Green)"
    elif s == "YELLOW":
        cls = "status-pill-yellow"
        text = "Quarantine / Suspected (Yellow)"
    else:
        cls = "status-pill-red"
        text = "Recall Active (Red)"

    detail_str = f" &mdash; <span style='font-weight: 400; opacity: 0.9;'>{html.escape(detail)}</span>" if detail else ""
    return f'<span class="status-pill {cls}">● {text}{detail_str}</span>'


def render_command_header(
    title: str = "Food Traceability & Recall Platform",
    subtitle: str = "Delhi-NCR Cloud Kitchen Network · FSSAI / FoSCoS Aligned",
    right_badge_html: str = "",
):
    """Renders the top incident command deck."""
    st.markdown(
        f"""
        <div class="command-header">
            <div>
                <div class="command-header-title">
                    <span style="color: #0369a1;">🛡️</span> {html.escape(title)}
                </div>
                <div class="command-header-meta">
                    {html.escape(subtitle)}
                </div>
            </div>
            <div>
                {right_badge_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_batch_dossier(batch: dict, window_dt_str: str = "—", mfg_dt_str: str = "—"):
    """Renders a structured batch inspection dossier card."""
    bid = html.escape(str(batch.get("id", "")))
    ing = html.escape(str(batch.get("ingredientName", "")))
    sup = html.escape(str(batch.get("supplier", {}).get("name", "—")))
    status = batch.get("status", "GREEN")
    reason = html.escape(str(batch.get("statusReason") or "Routine surveillance"))

    st.markdown(
        f"""
        <div class="dossier-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div style="font-size: 0.72rem; color: #64748b; margin-bottom: 0.2rem;">INSPECTION DOSSIER</div>
                    <div class="dossier-title"><code>{bid}</code> &bull; {ing}</div>
                </div>
                <div>
                    {status_badge_html(status)}
                </div>
            </div>
            <div class="dossier-grid">
                <div>
                    <div class="dossier-cell-label">Supplier origin</div>
                    <div class="dossier-cell-value">{sup}</div>
                </div>
                <div>
                    <div class="dossier-cell-label">Manufacture timestamp</div>
                    <div class="dossier-cell-value">{html.escape(mfg_dt_str)}</div>
                </div>
                <div>
                    <div class="dossier-cell-label">Contamination window start</div>
                    <div class="dossier-cell-value">{html.escape(window_dt_str)}</div>
                </div>
                <div>
                    <div class="dossier-cell-label">Audit reason</div>
                    <div class="dossier-cell-value" style="font-weight: 500;">{reason}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
