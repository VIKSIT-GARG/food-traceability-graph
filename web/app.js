'use strict';

/**
 * TRACE-NCR // RECALL MISSION CONTROL
 * Tactical Supply-Chain Graph Explorer & Recall Engine
 */

const $ = (id) => document.getElementById(id);

// Topological Layout Hierarchy & Palette
const LAYERS = ['Supplier', 'Facility', 'Batch', 'CloudKitchen', 'Dish', 'Order', 'Customer'];
const LX = Object.fromEntries(LAYERS.map((l, i) => [l, i]));

const NODE_COLORS = {
  Supplier: '#8b5cf6',      // Hyper Violet
  Facility: '#64748b',      // Industrial Slate
  CloudKitchen: '#0ea5e9',  // Hub Cyan
  Dish: '#f59e0b',          // Culinary Gold
  Order: '#14b8a6',         // Dispatch Teal
  Customer: '#f43f5e',      // Consumer Rose
};

const STATUS_COLORS = {
  GREEN: '#10b981',
  YELLOW: '#f59e0b',
  RED: '#ff2d55',
};

const STATUS_EMOJI = {
  GREEN: '🟢',
  YELLOW: '🟡',
  RED: '🔴',
};

const TRANSITIONS = {
  GREEN: ['YELLOW'],
  YELLOW: ['RED', 'GREEN'],
  RED: [],
};

// Application State
let cy = null;
let selected = null;
let blast = null;
let hlNodes = new Set();
let hlEdgeKeys = new Set();
let activeDrawerTab = 'timeline';

/* --------------------------------------------------------------------------
   API & Helper Functions
   -------------------------------------------------------------------------- */
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let m = r.statusText;
    try {
      const err = await r.json();
      m = err.detail || m;
    } catch (e) {}
    throw new Error(m);
  }
  return r.json();
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
}[c]));

const r1 = (n) => Math.round(n * 10) / 10;

function fmtDate(s) {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d)) return String(s);
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }) + ' IST';
}

function fmtVal(v) {
  return (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) ? fmtDate(v) : String(v);
}

function toast(msg, kind = 'ok') {
  const existing = document.querySelectorAll('.toast');
  existing.forEach((t) => t.remove());
  const t = document.createElement('div');
  t.className = 'toast ' + kind;
  const icon = kind === 'ok' ? '✓' : kind === 'err' ? '✕' : '⚠';
  t.innerHTML = `<span>${icon}</span> ${esc(msg)}`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

function edgeLabel(type, props) {
  if (type === 'DELIVERED_TO') {
    const q = props.reduce((a, p) => a + (p.qtyKg || 0), 0);
    const t = props.find((p) => p.deliveryDate)?.deliveryDate;
    return `${r1(q)} kg${t ? ' · ' + fmtDate(t) : ''}`;
  }
  if (type === 'USED_IN') {
    const q = props.reduce((a, p) => a + (p.qtyKg || p.quantity || 0), 0);
    const ts = props.map((p) => p.timestamp).filter(Boolean).sort();
    return ts.length ? `${r1(q)} kg @ ${fmtDate(ts[ts.length - 1])}` : `${r1(q)} kg`;
  }
  if (type === 'CONTAINS_DISH') {
    return `×${r1(props.reduce((a, p) => a + (p.quantity || 0), 0))}`;
  }
  if (type === 'PROCESSED_AT') {
    const t = props.find((p) => p.timestamp)?.timestamp;
    return t ? fmtDate(t) : 'PROCESSED';
  }
  if (type === 'SUPPLIES' || type === 'SUPPLIED') return 'SUPPLIES';
  if (type === 'PLACED_AT') return 'DISPATCHED_AT';
  if (type === 'PLACED_ORDER') return 'ORDERED';
  return type;
}

function nodeColor(label, props) {
  return label === 'Batch'
    ? (STATUS_COLORS[props.status] || '#64748b')
    : (NODE_COLORS[label] || '#64748b');
}

function nodeLabelText(label, props) {
  if (label === 'Batch') {
    return `${props.id}\n${props.ingredientName || ''} ${STATUS_EMOJI[props.status] || ''}`;
  }
  if (label === 'Supplier' || label === 'CloudKitchen') {
    return `${props.name || props.id}\n(${props.location ? props.location.split(',')[0] : ''})`;
  }
  return props.name || props.id;
}

/* --------------------------------------------------------------------------
   Cytoscape Topological Engine
   -------------------------------------------------------------------------- */
function initCy() {
  cy = cytoscape({
    container: $('cy'),
    elements: [],
    layout: { name: 'preset' },
    wheelSensitivity: 0.25,
    minZoom: 0.05,
    maxZoom: 3.5,
    boxSelectionEnabled: false,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          label: 'data(ltext)',
          color: '#e2e8f0',
          'text-valign': 'bottom',
          'text-margin-y': 7,
          'font-size': 10,
          'font-family': 'Inter, sans-serif',
          'font-weight': 600,
          'text-wrap': 'wrap',
          'text-max-width': 120,
          width: 26,
          height: 26,
          'border-width': 2,
          'border-color': 'data(border)',
          'overlay-padding': 4,
          'transition-property': 'background-color, border-color, width, height, opacity',
          'transition-duration': '0.2s',
        },
      },
      {
        selector: 'node[label="Batch"]',
        style: {
          width: 40,
          height: 40,
          'font-size': 11,
          'font-family': 'JetBrains Mono, monospace',
          'font-weight': 700,
          'border-width': 3,
        },
      },
      {
        selector: 'node[label="Supplier"]',
        style: {
          width: 34,
          height: 34,
          'border-width': 2,
          shape: 'diamond',
        },
      },
      {
        selector: 'node[label="CloudKitchen"]',
        style: {
          width: 32,
          height: 32,
          'border-width': 2,
          shape: 'round-rectangle',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': 'rgba(56, 189, 248, 0.25)',
          'target-arrow-color': 'rgba(56, 189, 248, 0.45)',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.9,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 8.5,
          'font-family': 'JetBrains Mono, monospace',
          color: '#94a3b8',
          'text-rotation': 'autorotate',
          'text-background-color': '#030712',
          'text-background-opacity': 0.9,
          'text-background-padding': 2,
          'text-background-shape': 'roundrectangle',
        },
      },
      // State Classes
      {
        selector: 'node.sel',
        style: {
          'border-color': '#00f2fe',
          'border-width': 4,
          'shadow-blur': 18,
          'shadow-color': '#00f2fe',
          'shadow-opacity': 0.8,
        },
      },
      {
        selector: 'node.traced',
        style: {
          'border-color': '#f59e0b',
          'border-width': 4,
          'shadow-blur': 14,
          'shadow-color': '#f59e0b',
          'shadow-opacity': 0.7,
        },
      },
      {
        selector: 'edge.traced-e',
        style: {
          'line-color': '#f59e0b',
          'target-arrow-color': '#f59e0b',
          width: 2.8,
        },
      },
      {
        selector: 'node.blast',
        style: {
          'border-color': '#ff2d55',
          'border-width': 4,
          'shadow-blur': 22,
          'shadow-color': '#ff2d55',
          'shadow-opacity': 0.85,
        },
      },
      {
        selector: 'edge.blast-e',
        style: {
          'line-color': '#ff2d55',
          'target-arrow-color': '#ff2d55',
          width: 2.8,
        },
      },
      {
        selector: 'node.dim',
        style: {
          opacity: 0.12,
        },
      },
      {
        selector: 'edge.dim',
        style: {
          opacity: 0.05,
        },
      },
    ],
  });

  // Tap & Hover Events
  cy.on('tap', 'node', (ev) => selectNode(ev.target));
  cy.on('tap', (ev) => {
    if (ev.target === cy) clearSelection();
  });

  const tip = $('tip');
  cy.on('mouseover', 'node', (ev) => {
    const d = ev.target.data();
    const props = d.props || {};
    tip.textContent = `${d.label} // ${ev.target.id()}\n` +
      Object.entries(props).slice(0, 5).map(([k, v]) => `${k}: ${fmtVal(v)}`).join('\n');
    tip.style.opacity = 1;
  });

  cy.on('mousemove', (ev) => {
    if (ev.renderedPosition) {
      tip.style.left = (ev.renderedPosition.x + 18) + 'px';
      tip.style.top = (ev.renderedPosition.y + 14) + 'px';
    }
  });

  cy.on('mouseout', 'node', () => {
    tip.style.opacity = 0;
  });
}

function applyLayeredLayout(fit = true) {
  const byLayer = {};
  cy.nodes().forEach((n) => {
    const l = n.data('label');
    (byLayer[l] = byLayer[l] || []).push(n);
  });
  for (const [l, nodes] of Object.entries(byLayer)) {
    const x = (LX[l] ?? 3.5) * 260;
    nodes.forEach((n, i) => {
      n.position({ x, y: (i - (nodes.length - 1) / 2) * 105 });
    });
  }
  if (fit) cy.fit(undefined, 50);
}

function addStore(data) {
  const els = [];
  for (const n of data.nodes || []) {
    const color = nodeColor(n.label, n.props);
    const border = n.label === 'Batch' ? color : 'rgba(255,255,255,.25)';
    const ex = cy.getElementById(n.id);
    if (ex.length) {
      ex.data({
        ltext: nodeLabelText(n.label, n.props),
        color,
        border,
        props: n.props,
      });
    } else {
      els.push({
        group: 'nodes',
        data: {
          id: n.id,
          label: n.label,
          ltext: nodeLabelText(n.label, n.props),
          color,
          border,
          props: n.props,
        },
      });
    }
  }

  for (const e of data.edges || []) {
    const key = `${e.type}|${e.source}|${e.target}`;
    if (cy.getElementById(key).length) continue;
    els.push({
      group: 'edges',
      data: {
        id: key,
        key,
        source: e.source,
        target: e.target,
        label: edgeLabel(e.type, e.props || []),
        etype: e.type,
      },
    });
  }

  if (els.length) cy.add(els);
  applyLayeredLayout(false);
}

/* --------------------------------------------------------------------------
   Highlights & Blast Radius Visualization
   -------------------------------------------------------------------------- */
function applyHighlights() {
  cy.elements().removeClass('traced traced-e');
  if (hlNodes.size) {
    cy.nodes().filter((n) => hlNodes.has(n.id())).addClass('traced');
  }
  if (hlEdgeKeys.size) {
    cy.edges().filter((e) => hlEdgeKeys.has(e.data('key'))).addClass('traced-e');
  }
}

function applyBlast() {
  cy.nodes().removeClass('blast dim');
  cy.edges().removeClass('blast-e dim');
  if (!blast) return;

  cy.nodes().forEach((n) => {
    n.addClass(blast.nodeIds.has(n.id()) ? 'blast' : 'dim');
  });
  cy.edges().forEach((e) => {
    e.addClass(blast.edgeKeys.has(e.data('key')) ? 'blast-e' : 'dim');
  });
  cy.fit(undefined, 50);
}

function showBanner() {
  const b = $('recallbanner');
  if (!blast) {
    b.classList.add('hidden');
    return;
  }
  const c = blast.counts;
  b.className = 'banner ' + (blast.simulateOnly ? 'sim' : '');
  b.innerHTML = `
    <span class="b-title">${blast.simulateOnly ? 'SIMULATION' : 'RECALL ACTIVE'}</span>
    <span class="mono-meta" style="color:#fff;font-size:13px;font-weight:700">${esc(blast.batch)}</span>
    <span>💥 Affected: <b>${c.kitchens}</b> kitchens · <b>${c.dishes}</b> dishes · <b>${c.orders}</b> orders · <b>${c.customers}</b> consumers</span>
    <span class="mono-meta" style="margin-left:auto">${blast.window ? 'TEMPORAL WINDOW ≥ ' + fmtDate(blast.window) : 'SCOPE: FULL BATCH'}</span>
    <button class="hud-btn secondary" id="banner-clear" style="padding:4px 10px;font-size:11px">✕ Clear</button>
  `;
  $('banner-clear').onclick = clearBlast;
}

function clearBlast() {
  blast = null;
  applyBlast();
  showBanner();
  updateToolbar();
}

async function runBlast(batchId, simulateOnly) {
  try {
    const d = await api(`/api/blast/${encodeURIComponent(batchId)}`);
    addStore(d.graph);
    blast = {
      nodeIds: new Set(d.node_ids),
      edgeKeys: new Set(d.edges.map((e) => `${e.type}|${e.source}|${e.target}`)),
      counts: d.counts,
      window: d.window,
      batch: d.batch,
      simulateOnly,
    };
    applyBlast();
    showBanner();
    updateToolbar();
    toast(`Blast radius calculated: ${d.counts.kitchens} kitchens, ${d.counts.orders} orders`, 'warn');
  } catch (e) {
    toast(e.message, 'err');
  }
}

/* --------------------------------------------------------------------------
   Selection & Inspector Console
   -------------------------------------------------------------------------- */
function clearSelection(clearHl = true) {
  if (selected) cy.getElementById(selected.id).removeClass('sel');
  selected = null;
  if (clearHl) {
    hlNodes.clear();
    hlEdgeKeys.clear();
    applyHighlights();
  }
  $('insp-body').innerHTML = `
    <div class="insp-empty-state">
      <div class="empty-crosshair">✛</div>
      <h3>Select Any Node</h3>
      <p>Click any Supplier, Batch, Kitchen, Dish, or Order to inspect real-time properties, detonate recall simulations, or enforce containment.</p>
      <div class="shortcut-hints">
        <span><kbd>Space</kbd> Fit</span>
        <span><kbd>B</kbd> Blast</span>
        <span><kbd>T</kbd> Timeline</span>
        <span><kbd>Esc</kbd> Clear</span>
      </div>
    </div>
  `;
  updateToolbar();
}

async function selectNode(node) {
  if (selected) cy.getElementById(selected.id).removeClass('sel');
  selected = { id: node.id(), label: node.data('label') };
  node.addClass('sel');
  updateToolbar();

  // Smooth pan/zoom to center
  cy.animate({
    center: { eles: node },
    zoom: Math.max(cy.zoom(), 0.9),
    duration: 250,
  });

  $('insp-body').innerHTML = `
    <div class="insp-empty-state">
      <div class="empty-crosshair" style="animation:spin 1s linear infinite">◌</div>
      <h3>Querying Neo4j...</h3>
      <p class="mono-meta">MATCH (n:${esc(selected.label)} {id: '${esc(selected.id)}'})</p>
    </div>
  `;

  try {
    const d = await api(`/api/node/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}`);
    renderInspector(d);
  } catch (e) {
    $('insp-body').innerHTML = `<div class="panel-section" style="border-color:var(--crimson-crit)">⚠️ ${esc(e.message)}</div>`;
  }
}

function selectNodeById(id, label) {
  const n = cy.getElementById(id);
  if (n.length) selectNode(n);
}

function renderInspector(d) {
  const p = d.props;
  const label = selected.label;
  const isBatch = label === 'Batch';
  const isSupplier = label === 'Supplier';

  let html = `
    <div class="insp-header">
      <div class="insp-id-group">
        <span class="entity-chip ${label}">${esc(label)}</span>
        <h2>${esc(p.id || p.name)}</h2>
      </div>
      ${isBatch || isSupplier ? `
        <span class="status-badge ${p.status || 'GREEN'}">
          ${STATUS_EMOJI[p.status] || '●'} ${esc(p.status || 'GREEN')}
        </span>
      ` : ''}
    </div>
  `;

  // Batch-specific incident metadata
  if (isBatch) {
    html += `
      <div class="intervention-card" style="border-color:rgba(245,158,11,0.3)">
        <h3>Incident Telemetry</h3>
        <p style="font-size:12px;margin-bottom:4px">
          <b>Ingredient:</b> ${esc(p.ingredientName || '—')} · 
          <b>Status Reason:</b> ${esc(p.statusReason || 'Normal production')}
        </p>
        ${p.contaminationDate ? `
          <p class="mono-meta" style="color:#fde047">
            ⚠ Contamination Window: ≥ ${fmtDate(p.contaminationDate)}
          </p>
        ` : ''}
      </div>
    `;
  }

  // Quick State Transition Controls for Batches & Suppliers
  if (isBatch || isSupplier) {
    const curStatus = p.status || 'GREEN';
    const allowed = TRANSITIONS[curStatus] || [];
    html += `
      <div class="intervention-card">
        <h3>Risk State Machine Transition</h3>
        ${allowed.length ? `
          <div class="transition-grid">
            ${allowed.map((s) => `
              <button class="hud-btn ${s === 'RED' ? 'danger' : 'primary'}" style="font-size:11px" onclick="promptTransition('${s}')">
                → Set ${s}
              </button>
            `).join('')}
          </div>
        ` : `
          <p class="mono-meta" style="color:var(--txt-muted)">Status is terminal (RED). Downstream recall active.</p>
        `}
      </div>
    `;
  }

  // Immediate Recall & Containment Actions for Batches
  if (isBatch) {
    html += `
      <div class="intervention-card" style="border-color:rgba(255,45,85,0.4)">
        <h3>Intervention &amp; Recall Protocol</h3>
        <div class="action-pill-row">
          <button class="hud-btn danger" onclick="quickAction('contain')" title="Apply HOLD status to all receiving cloud kitchen hubs">
            🧊 Hold Kitchens
          </button>
          <button class="hud-btn danger" onclick="quickAction('block')" title="Remove contaminated dishes from cloud kitchen menus">
            🚫 Pull Menus
          </button>
        </div>
        <div class="action-pill-row">
          <button class="hud-btn primary" onclick="quickAction('notify')" title="Send safety notification to all affected consumers">
            📱 Alert Users
          </button>
          <button class="hud-btn primary" onclick="openDrawer('fssai')" title="View and download FSSAI Digital Recall Dossier">
            📑 FSSAI Dossier
          </button>
        </div>
      </div>
    `;
  }

  // Properties Ledger
  const propRows = Object.entries(p)
    .filter(([k, v]) => v !== null && !k.startsWith('_'))
    .map(([k, v]) => `
      <tr>
        <td class="prop-key">${esc(k)}</td>
        <td class="prop-val mono-meta">${esc(fmtVal(v))}</td>
      </tr>
    `).join('');

  html += `
    <div class="panel-section">
      <div class="section-hdr">
        <h2>Entity Properties</h2>
        <span class="mono-meta">${Object.keys(p).length} fields</span>
      </div>
      <table class="cyber-table"><tbody>${propRows}</tbody></table>
    </div>
  `;

  // Connected Graph Traversal Edges
  if (d.relationships && d.relationships.length) {
    const relRows = d.relationships.map((r) => `
      <tr>
        <td class="prop-key" style="white-space:nowrap">
          <span class="rel-badge">${r.outbound ? '→' : '←'} ${esc(r.rel)}</span>
        </td>
        <td class="prop-val">
          <a href="javascript:void(0)" onclick="selectNodeById('${esc(r.other)}', '${esc(r.other_label)}')" style="color:var(--cyan-neon);text-decoration:none">
            ${esc(r.other_label)}: <b>${esc(r.other)}</b>
          </a>
        </td>
      </tr>
    `).join('');

    html += `
      <div class="panel-section">
        <div class="section-hdr">
          <h2>Connected Nodes</h2>
          <span class="mono-meta">${d.relationships.length} edges</span>
        </div>
        <table class="cyber-table"><tbody>${relRows}</tbody></table>
      </div>
    `;
  }

  $('insp-body').innerHTML = html;
}

window.promptTransition = async function(targetStatus) {
  if (!selected) return;
  const reason = prompt(`Enter mandatory audit trail reason for transitioning ${selected.id} to ${targetStatus}:`);
  if (!reason || !reason.trim()) {
    toast('Audit reason is required for every risk transition', 'warn');
    return;
  }

  let contamination_date = null;
  if (targetStatus === 'YELLOW') {
    const dt = prompt('Contamination start datetime (YYYY-MM-DD HH:MM in IST):', '2025-09-10 14:00');
    if (dt) contamination_date = new Date(dt.replace(' ', 'T') + ':00+05:30').toISOString();
  }

  try {
    const endpoint = selected.label === 'Supplier'
      ? `/api/flag-supplier/${encodeURIComponent(selected.id)}`
      : `/api/flag/${encodeURIComponent(selected.id)}`;

    await api(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_status: targetStatus,
        reason: reason.trim(),
        actor: 'mission_control_ui',
        contamination_date,
      }),
    });

    toast(`${selected.id} transitioned to ${targetStatus}`, 'ok');
    loadKpis();
    if (selected.label === 'Batch') {
      await runBlast(selected.id, false);
    }
    selectNodeById(selected.id, selected.label);
  } catch (e) {
    toast(e.message, 'err');
  }
};

window.quickAction = async function(kind) {
  if (!selected || selected.label !== 'Batch') return;
  const id = selected.id;
  const paths = {
    contain: `/api/actions/contain/${encodeURIComponent(id)}?status=HOLD`,
    block: `/api/actions/pull-menu/${encodeURIComponent(id)}`,
    notify: `/api/actions/notify/${encodeURIComponent(id)}`,
  };

  try {
    const r = await api(paths[kind], { method: 'POST' });
    if (kind === 'contain') toast(`Kitchen HOLD applied: ${(r.kitchens || []).join(', ')}`, 'ok');
    if (kind === 'block') toast(`Dishes pulled from menus: ${(r.pulled || r.dishes || []).join(', ')}`, 'ok');
    if (kind === 'notify') toast(`${r.orders_notified || 0} customer orders flagged for outreach`, 'ok');
    loadKpis();
  } catch (e) {
    toast(e.message, 'err');
  }
};

/* --------------------------------------------------------------------------
   Toolbar Controls & Graph Traversal
   -------------------------------------------------------------------------- */
function updateToolbar() {
  const has = !!selected;
  const isBatch = has && selected.label === 'Batch';
  $('btn-up').disabled = !has;
  $('btn-down').disabled = !has;
  $('btn-expand').disabled = !has;
  $('btn-collapse').disabled = !has;
  $('btn-blast').disabled = !isBatch;
  $('btn-timeline').disabled = !isBatch;
  $('btn-pulllist').disabled = !isBatch;
  $('btn-clearblast').disabled = !blast;
}

async function doTrace(dir) {
  if (!selected) return;
  try {
    const d = await api(`/api/trace/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}?direction=${dir}`);
    addStore(d);
    hlNodes = new Set(d.nodes.map((n) => n.id));
    hlEdgeKeys = new Set(d.edges.map((e) => `${e.type}|${e.source}|${e.target}`));
    applyHighlights();
    toast(`Traced ${dir}: ${d.nodes.length} nodes highlighted`, 'ok');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function collapseBranch() {
  if (!selected) return;
  const node = cy.getElementById(selected.id);
  const desc = node.successors().nodes();
  cy.remove(desc);
  applyLayeredLayout(true);
  toast(`Collapsed ${desc.length} downstream nodes`, 'ok');
}

/* --------------------------------------------------------------------------
   Dockable Multi-Tab Drawer (Timeline, Pull List, FSSAI Dossier)
   -------------------------------------------------------------------------- */
function openDrawer(tabName = 'timeline') {
  if (!selected || selected.label !== 'Batch') {
    toast('Select a Batch to inspect its incident dossier', 'warn');
    return;
  }
  activeDrawerTab = tabName;
  $('drawer').classList.remove('hidden');

  // Update active tab buttons
  document.querySelectorAll('.dtab-btn').forEach((b) => b.classList.remove('active'));
  const btn = $(`tab-${tabName}`);
  if (btn) btn.classList.add('active');

  if (tabName === 'timeline') renderDrawerTimeline();
  else if (tabName === 'pulllist') renderDrawerPullList();
  else if (tabName === 'fssai') renderDrawerFssai();
}

async function renderDrawerTimeline() {
  $('drawer-icon').textContent = '⏱';
  $('drawer-title').textContent = `Incident Timeline // ${selected.id}`;
  $('drawer-body').innerHTML = '<p class="mono-meta">Loading timeline events from Neo4j...</p>';

  try {
    const d = await api(`/api/timeline/${encodeURIComponent(selected.id)}`);
    const win = d.contamination_date ? new Date(d.contamination_date) : null;
    let html = `
      <p class="mono-meta" style="margin-bottom:12px;color:var(--txt-bright)">
        <b>Batch:</b> ${esc(d.batch)} · <b>Ingredient:</b> ${esc(d.ingredient || '')} · 
        <b>Status:</b> ${STATUS_EMOJI[d.status] || ''} ${esc(d.status || '')} · <b>Supplier:</b> ${esc(d.supplier || '')}
      </p>
    `;

    let markerDone = !win;
    for (const ev of d.events) {
      const ts = new Date(ev.ts);
      if (!markerDone && ts >= win) {
        html += `
          <div class="tl-event">
            ⛔ Contamination Event Demarcation — ${fmtDate(d.contamination_date)}<br>
            <span class="mono-meta" style="color:#fee2e2">Upstream events are safe · downstream events require active recall</span>
          </div>
        `;
        markerDone = true;
      }
      const cls = ev.kind === 'AUDIT' ? 'tl-audit' : (win && ts >= win ? 'tl-in' : 'tl-clear');
      html += `
        <div class="tl-row ${cls}">
          <span class="tl-time">${fmtDate(ev.ts)}</span>
          <span class="tl-chip">${esc(ev.kind)}</span>
          <span style="font-weight:500">${esc(ev.label)}</span>
        </div>
      `;
    }

    $('drawer-body').innerHTML = html;
  } catch (e) {
    $('drawer-body').innerHTML = `<p style="color:var(--crimson-crit)">⚠️ ${esc(e.message)}</p>`;
  }
}

async function renderDrawerPullList() {
  $('drawer-icon').textContent = '📋';
  $('drawer-title').textContent = `Kitchen Menu Pull Matrix // ${selected.id}`;
  $('drawer-body').innerHTML = '<p class="mono-meta">Calculating affected kitchen menus...</p>';

  try {
    const d = await api(`/api/pull-list/${encodeURIComponent(selected.id)}`);
    if (!d.pull_list || !d.pull_list.length) {
      $('drawer-body').innerHTML = '<p class="mono-meta" style="color:var(--emerald-safe)">✓ No kitchens or dishes currently flagged for recall under the selected scope.</p>';
      return;
    }

    let html = `
      <p class="mono-meta" style="margin-bottom:14px">
        Mandatory Menu Deactivations for <b>${esc(d.batch)}</b> across Delhi NCR cloud kitchens:
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">
    `;

    for (const k of d.pull_list) {
      html += `
        <div class="panel-section" style="border-color:rgba(255,45,85,0.3)">
          <div style="font-weight:700;color:var(--cyan-neon);font-size:13px">${esc(k.kitchen)}</div>
          <div class="mono-meta" style="margin-bottom:8px">${esc(k.location || 'Delhi NCR')}</div>
          <p style="font-size:11px;font-weight:600;color:#fecaca;margin-bottom:4px">Dishes to remove from menu:</p>
          <ul style="padding-left:18px;font-size:12px;color:var(--txt-bright)">
            ${k.pull_dishes.map((dp) => `<li><b>${esc(dp.name)}</b> <span class="mono-meta">(${esc(dp.id)})</span></li>`).join('')}
          </ul>
        </div>
      `;
    }

    html += `</div>`;
    $('drawer-body').innerHTML = html;
  } catch (e) {
    $('drawer-body').innerHTML = `<p style="color:var(--crimson-crit)">⚠️ ${esc(e.message)}</p>`;
  }
}

async function renderDrawerFssai() {
  $('drawer-icon').textContent = '📑';
  $('drawer-title').textContent = `FSSAI Digital Recall Dossier // ${selected.id}`;
  $('drawer-body').innerHTML = '<p class="mono-meta">Compiling regulatory report from live audit events...</p>';

  try {
    const rep = await api(`/api/report/${encodeURIComponent(selected.id)}`);
    const jsonStr = JSON.stringify(rep, null, 2);

    let html = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div>
          <span class="status-badge RED">${esc(rep.product.riskStatus)}</span>
          <span class="mono-meta" style="margin-left:8px">Generated: ${fmtDate(rep.generatedAt)}</span>
        </div>
        <div>
          <button class="hud-btn primary" id="btn-dl-report" style="font-size:11px">⬇ Download JSON</button>
          <button class="hud-btn secondary" id="btn-copy-report" style="font-size:11px">⧉ Copy JSON</button>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">
        <div class="panel-section" style="text-align:center"><div class="mono-meta">Kitchens</div><b style="font-size:18px;color:var(--cyan-neon)">${rep.impactSummary.kitchens}</b></div>
        <div class="panel-section" style="text-align:center"><div class="mono-meta">Dishes</div><b style="font-size:18px;color:var(--amber-warn)">${rep.impactSummary.dishes}</b></div>
        <div class="panel-section" style="text-align:center"><div class="mono-meta">Orders</div><b style="font-size:18px;color:var(--teal-dispatch)">${rep.impactSummary.orders}</b></div>
        <div class="panel-section" style="text-align:center"><div class="mono-meta">Consumers</div><b style="font-size:18px;color:var(--crimson-crit)">${rep.impactSummary.customers}</b></div>
      </div>
      <pre class="cyber-input mono-meta" style="max-height:220px;overflow-y:auto;white-space:pre-wrap;font-size:11px;background:#030712;padding:12px">${esc(jsonStr)}</pre>
    `;

    $('drawer-body').innerHTML = html;

    $('btn-dl-report').onclick = () => {
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `recall_report_${selected.id}.json`;
      a.click();
      toast('Recall report downloaded', 'ok');
    };

    $('btn-copy-report').onclick = () => {
      navigator.clipboard.writeText(jsonStr);
      toast('Report copied to clipboard', 'ok');
    };
  } catch (e) {
    $('drawer-body').innerHTML = `<p style="color:var(--crimson-crit)">⚠️ ${esc(e.message)}</p>`;
  }
}

/* --------------------------------------------------------------------------
   Data Loading: Telemetry, Filters, Network
   -------------------------------------------------------------------------- */
async function loadFilters() {
  const o = await api('/api/filters');
  const fill = (id, arr) => {
    const s = $(id);
    s.innerHTML = s.children[0].outerHTML;
    arr.forEach((v) => {
      const op = document.createElement('option');
      op.value = v;
      op.textContent = v;
      s.appendChild(op);
    });
  };

  fill('f-supplier', o.suppliers.map((s) => `${s.id} — ${s.name}`));
  fill('f-kitchen', o.kitchens.map((k) => `${k.id} — ${k.name}`));
  fill('f-ingredient', o.ingredients);
  fill('f-location', o.locations);
}

async function loadKpis() {
  const k = await api('/api/kpis');
  const c = k.counts;
  const chip = (l, v) => `<span class="kchip">${l} <b>${v ?? 0}</b></span>`;

  $('kpis').innerHTML = [
    chip('Suppliers', c.Supplier),
    chip('Batches', c.Batch),
    chip('Kitchens', c.CloudKitchen),
    chip('Dishes', c.Dish),
    chip('Orders', c.Order),
    chip('Consumers', c.Customer),
    chip('🚫 Blocked', k.blocked_dishes ?? k.blocked_menu_items ?? 0),
    chip('🧊 Holds', k.kitchen_holds ?? 0),
  ].join('') +
  k.flagged.map((f) => `
    <span class="kchip flag ${f.status.toLowerCase()}">
      ${STATUS_EMOJI[f.status]} ${esc(f.id)}
    </span>
  `).join('');

  const anyRed = k.flagged.some((f) => f.status === 'RED');
  const pill = $('statuspill');
  pill.className = 'status-pill ' + (anyRed ? 'bad' : (k.flagged.length ? 'warn' : 'ok'));
  $('statuspill-text').textContent = anyRed
    ? '● CRITICAL RECALL ACTIVE'
    : (k.flagged.length ? '● INVESTIGATION WINDOW' : '● ALL SYSTEMS NOMINAL');
}

async function loadNetwork() {
  const p = new URLSearchParams();
  const q = $('f-q').value.trim();
  if (q) p.set('q', q);

  [['f-supplier', 'supplier'], ['f-kitchen', 'kitchen'], ['f-ingredient', 'ingredient'], ['f-location', 'location']]
    .forEach(([id, param]) => {
      const v = $(id).value;
      if (v && v !== '(any)' && !v.startsWith('(All')) {
        p.set(param, v.split(' — ')[0]);
      }
    });

  const st = [];
  if ($('f-green').checked) st.push('GREEN');
  if ($('f-yellow').checked) st.push('YELLOW');
  if ($('f-red').checked) st.push('RED');
  if (st.length && st.length < 3) st.forEach((s) => p.append('statuses', s));

  if ($('f-from').value) p.set('date_from', $('f-from').value);
  if ($('f-to').value) p.set('date_to', $('f-to').value);

  const data = await api('/api/network?' + p.toString());
  blast = null;
  hlNodes.clear();
  hlEdgeKeys.clear();
  selected = null;

  cy.elements().remove();
  addStore(data);

  $('nodecount').textContent = `Topology: ${data.nodes.length} nodes · ${data.edges.length} relationships live from Neo4j`;
  showBanner();
  clearSelection(false);
  updateToolbar();
}

/* --------------------------------------------------------------------------
   Quick Scenario Presets
   -------------------------------------------------------------------------- */
function setupScenarios() {
  // Scenario 1: Paneer Contamination Recall
  $('scen-paneer').onclick = async () => {
    toast('Triggering Scenario: BATCH-PANEER-001 Incident', 'warn');
    await loadNetwork();
    selectNodeById('BATCH-PANEER-001', 'Batch');
    await runBlast('BATCH-PANEER-001', false);
    openDrawer('pulllist');
  };

  // Scenario 2: Cream Suspect Window
  $('scen-cream').onclick = async () => {
    toast('Triggering Scenario: BATCH-CREAM-001 Investigation', 'warn');
    await loadNetwork();
    selectNodeById('BATCH-CREAM-001', 'Batch');
    await runBlast('BATCH-CREAM-001', true);
    openDrawer('timeline');
  };

  // Scenario 3: Gopal Dairy Network Blast
  $('scen-gopal').onclick = async () => {
    toast('Triggering Scenario: Gopal Dairy Vendor Exposure', 'ok');
    await loadNetwork();
    selectNodeById('SUP-002', 'Supplier');
    try {
      const d = await api('/api/blast-supplier/SUP-002');
      addStore(d.graph);
      blast = {
        nodeIds: new Set(d.node_ids),
        edgeKeys: new Set(d.edges.map((e) => `${e.type}|${e.source}|${e.target}`)),
        counts: d.counts,
        window: d.window,
        batch: d.batch,
        simulateOnly: true,
      };
      applyBlast();
      showBanner();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  // Reset Network
  $('scen-reset').onclick = async () => {
    $('f-q').value = '';
    ['f-supplier', 'f-kitchen', 'f-ingredient', 'f-location'].forEach((i) => $(i).selectedIndex = 0);
    ['f-from', 'f-to'].forEach((i) => $(i).value = '');
    ['f-green', 'f-yellow', 'f-red'].forEach((i) => $(i).checked = true);
    await loadNetwork();
    toast('Full network overview restored', 'ok');
  };
}

/* --------------------------------------------------------------------------
   Boot & Lifecycle Initialization
   -------------------------------------------------------------------------- */
window.addEventListener('DOMContentLoaded', async () => {
  if (!window.cytoscape) {
    document.body.innerHTML = `
      <div style="margin:80px auto;max-width:540px;padding:24px;border:1px solid #ff2d55;border-radius:12px;background:#030712;color:#fecaca">
        <h3>Network Error</h3>
        <p>Cytoscape.js failed to load from CDN. Verify network access to cdn.jsdelivr.net.</p>
      </div>
    `;
    return;
  }

  initCy();
  clearSelection(false);

  try {
    await loadFilters();
    await loadKpis();
    await loadNetwork();
  } catch (e) {
    document.body.innerHTML = `
      <div style="margin:80px auto;max-width:540px;padding:24px;border:1px solid #ff2d55;border-radius:12px;background:#030712;color:#fecaca">
        <h3>Backend Disconnected</h3>
        <p>${esc(e.message)}</p>
        <p style="margin-top:12px;font-size:12px;color:#94a3b8">Run: <code>uvicorn web_app:app --reload</code></p>
      </div>
    `;
    return;
  }

  setupScenarios();

  // Sidebar Filter Actions
  $('btn-apply').onclick = () => loadNetwork().catch((e) => toast(e.message, 'err'));
  $('btn-resetnet').onclick = () => $('scen-reset').click();

  // Toolbar Actions
  $('btn-up').onclick = () => doTrace('up');
  $('btn-down').onclick = () => doTrace('down');
  $('btn-expand').onclick = async () => {
    if (!selected) return;
    try {
      const data = await api(`/api/expand/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}`);
      addStore(data);
      applyLayeredLayout(true);
    } catch (e) {
      toast(e.message, 'err');
    }
  };
  $('btn-collapse').onclick = collapseBranch;
  $('btn-blast').onclick = () => {
    if (selected && selected.label === 'Batch') runBlast(selected.id, true);
  };
  $('btn-clearblast').onclick = clearBlast;
  $('btn-pulllist').onclick = () => openDrawer('pulllist');
  $('btn-timeline').onclick = () => openDrawer('timeline');

  // Layout Buttons
  $('btn-layered').onclick = () => {
    $('btn-layered').classList.add('active');
    $('btn-force').classList.remove('active');
    applyLayeredLayout(true);
  };
  $('btn-force').onclick = () => {
    $('btn-force').classList.add('active');
    $('btn-layered').classList.remove('active');
    cy.layout({
      name: 'cose',
      animate: true,
      animationDuration: 600,
      idealEdgeLength: 120,
      nodeOverlap: 20,
    }).run();
  };
  $('btn-fit').onclick = () => cy.fit(undefined, 50);

  // Drawer Tabs & Close
  $('drawer-close').onclick = () => $('drawer').classList.add('hidden');
  $('tab-timeline').onclick = () => openDrawer('timeline');
  $('tab-pulllist').onclick = () => openDrawer('pulllist');
  $('tab-fssai').onclick = () => openDrawer('fssai');

  // Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.key === 'Escape') {
      clearBlast();
      clearSelection();
      $('drawer').classList.add('hidden');
    } else if (e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      cy.fit(undefined, 50);
    } else if (e.key === '1') {
      $('btn-layered').click();
    } else if (e.key === '2') {
      $('btn-force').click();
    } else if ((e.key === 'b' || e.key === 'B') && selected && selected.label === 'Batch') {
      runBlast(selected.id, true);
    } else if ((e.key === 't' || e.key === 'T') && selected && selected.label === 'Batch') {
      openDrawer('timeline');
    } else if ((e.key === 'p' || e.key === 'P') && selected && selected.label === 'Batch') {
      openDrawer('pulllist');
    }
  });
});