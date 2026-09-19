#!/usr/bin/env python3
"""v2 frontend: writes web/index.html + web/app.js, appends pull-list CSS.
Run from the project root:  python build_v2_web.py"""
import ast
from pathlib import Path

INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Food Traceability Graph — Recall Mission Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/styles.css"/>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
</head>
<body>
<header id="topbar">
  <div class="brand">
    <div class="logo">FG</div>
    <div><h1>Food Traceability Graph</h1>
    <p class="sub">Supplier → Batch → Kitchen → Dish · live Neo4j</p></div>
  </div>
  <div id="kpis" class="kpis"></div>
  <div id="statuspill" class="pill ok">● BOOTING</div>
</header>
<div id="recallbanner" class="banner hidden"></div>
<main id="layout">
  <aside id="sidebar">
    <div class="panel">
      <h2>Search &amp; filters</h2>
      <input id="f-q" placeholder="🔍 batch / ingredient / supplier / kitchen"/>
      <label>Supplier</label><select id="f-supplier"><option value="(any)">(any)</option></select>
      <label>Cloud kitchen</label><select id="f-kitchen"><option value="(any)">(any)</option></select>
      <label>Ingredient</label><select id="f-ingredient"><option value="(any)">(any)</option></select>
      <label>Location</label><select id="f-location"><option value="(any)">(any)</option></select>
      <div class="row2">
        <div><label>Activity from</label><input type="date" id="f-from"/></div>
        <div><label>to</label><input type="date" id="f-to"/></div>
      </div>
      <label class="lbl-top">Batch risk</label>
      <div class="statusrow">
        <label class="chk"><input type="checkbox" id="f-green" checked/> 🟢 Green</label>
        <label class="chk"><input type="checkbox" id="f-yellow" checked/> 🟡 Yellow</label>
        <label class="chk"><input type="checkbox" id="f-red" checked/> 🔴 Red</label>
      </div>
      <button id="btn-apply" class="btn primary wide">Apply filters</button>
      <button id="btn-resetnet" class="btn wide">Reset network</button>
      <p id="nodecount" class="muted small"></p>
    </div>
    <div class="panel">
      <h2>Model</h2>
      <p class="muted small">(Supplier)-[:SUPPLIES]->(Batch)-[:DELIVERED_TO]->(Kitchen)-[:USED_IN]->(Dish)<br><br>
      Orders carry <span class="mono">PLACED_AT → Kitchen</span>, so impact is kitchen-accurate.
      Click a <b>Supplier</b> or <b>Batch</b> to flag contamination, trace the full downstream
      blast radius, and generate per-kitchen pull lists.</p>
    </div>
  </aside>
  <section id="stage">
    <div id="toolbar">
      <button id="btn-up" class="btn" disabled>⬆ Upstream</button>
      <button id="btn-down" class="btn" disabled>⬇ Downstream</button>
      <button id="btn-expand" class="btn" disabled>➕ Expand +1</button>
      <button id="btn-collapse" class="btn" disabled>➖ Collapse</button>
      <span class="sep"></span>
      <button id="btn-blast" class="btn danger" disabled>💥 Recall impact</button>
      <button id="btn-clearblast" class="btn" disabled>✖ Clear sim</button>
      <button id="btn-timeline" class="btn" disabled>🕰 Timeline</button>
      <button id="btn-pulllist" class="btn" disabled>📋 Pull list</button>
      <span class="sep"></span>
      <button id="btn-layered" class="btn">▤ Layered</button>
      <button id="btn-force" class="btn">✳ Force</button>
      <button id="btn-fit" class="btn">⤢ Fit</button>
    </div>
    <div id="cy"><div id="tip"></div></div>
    <div id="legend">
      <span><i class="dot" style="background:#a78bfa"></i>Supplier</span>
      <span><i class="dot" style="background:#71717a"></i>Facility</span>
      <span><i class="dot" style="background:#10b981"></i>Batch 🟢</span>
      <span><i class="dot" style="background:#f59e0b"></i>Batch 🟡</span>
      <span><i class="dot" style="background:#ef4444"></i>Batch 🔴</span>
      <span><i class="dot" style="background:#38bdf8"></i>Kitchen</span>
      <span><i class="dot" style="background:#fbbf24"></i>Dish</span>
      <span><i class="dot" style="background:#14b8a6"></i>Order</span>
      <span><i class="dot" style="background:#fb7185"></i>Customer</span>
      <span><i class="dot blastdot"></i>💥 blast radius</span>
      <span><i class="dot tracedot"></i>traced path</span>
    </div>
  </section>
  <aside id="inspector"><div id="insp-body"></div></aside>
</main>
<div id="drawer" class="hidden">
  <div class="drawer-head">
    <h2 id="drawer-title">🕰 Timeline</h2>
    <button id="drawer-close" class="btn">✕ Close</button>
  </div>
  <div id="drawer-body"></div>
</div>
<script src="/app.js"></script>
</body>
</html>
'''

APP_JS = r'''\'USE-STRICT-MARKER\'
'''

print("placeholder")