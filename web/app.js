/**
 * Food Traceability Graph — Recall Mission Control
 * Frontend Application Engine (Graph View + Operations Dashboard + Command Bar)
 */

'use strict';

// -----------------------------------------------------------------------------
// DOM Selectors & Utilities
// -----------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

const LAYERS = ['Supplier', 'Batch', 'Facility', 'CloudKitchen', 'Dish', 'Order', 'Customer'];
const LAYER_INDEX = Object.fromEntries(LAYERS.map((l, i) => [l, i]));

const NODE_PALETTE = {
  Supplier: '#a78bfa',      // Soft Lavender / Violet
  Batch: {
    GREEN: '#10b981',       // Emerald
    YELLOW: '#f59e0b',      // Warm Amber
    RED: '#ef4444',         // Vivid Crimson
  },
  Facility: '#64748b',      // Slate
  CloudKitchen: '#38bdf8',  // Sky Cyan
  Dish: '#fbbf24',          // Culinary Gold
  Order: '#14b8a6',         // Dispatch Teal
  Customer: '#f43f5e',      // Rose Red
};

const EDGE_COLORS = {
  SUPPLIES: '#a78bfa',
  DELIVERED_TO: '#38bdf8',
  USED_IN: '#fbbf24',
  CONTAINS_DISH: '#14b8a6',
  PLACED_AT: '#60a5fa',
  PLACED_ORDER: '#f43f5e',
  PROCESSED_AT: '#64748b',
  MENU_BLOCKED: '#ef4444',
  HAS_EVENT: '#e2e8f0',
  NOTIFIED_FOR: '#10b981',
};

// -----------------------------------------------------------------------------
// Application State
// -----------------------------------------------------------------------------
let cy = null;
let currentView = 'graph';      // 'graph' | 'dash'
let cmdMode = 'cmd';           // 'cmd' | 'cy'
let selectedNode = null;       // { id, label, props }
let blastState = null;         // { batch, counts, nodes: Set, edges: Set }
let activeTrace = null;        // { nodes: Set, edges: Set, direction }
let activeWatchBatch = null;   // Active batch ID focused in dashboard
let rawGraphData = { nodes: [], edges: [] };

// -----------------------------------------------------------------------------
// API Client
// -----------------------------------------------------------------------------
async function api(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

function toast(msg, type = 'info') {
  let container = $('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed; top: 78px; right: 24px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px; pointer-events: none;
    `;
    document.body.appendChild(container);
  }

  const el = document.createElement('div');
  const bg = type === 'err' ? 'rgba(239, 68, 68, 0.92)' :
             type === 'warn' ? 'rgba(245, 158, 11, 0.92)' :
             type === 'ok' ? 'rgba(16, 185, 129, 0.92)' : 'rgba(15, 23, 42, 0.92)';

  el.style.cssText = `
    background: ${bg}; color: #ffffff; padding: 10px 16px; border-radius: 8px;
    font-family: var(--font-sans, sans-serif); font-size: 12.5px; font-weight: 600;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5); pointer-events: auto;
    border: 1px solid rgba(255,255,255,0.15); animation: toast-in 0.2s ease-out;
  `;
  el.textContent = msg;
  container.appendChild(el);

  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(-6px)';
    el.style.transition = 'all 0.25s ease';
    setTimeout(() => el.remove(), 250);
  }, 4000);
}

function fmtDate(d) {
  if (!d) return '—';
  try {
    const dt = new Date(d);
    if (isNaN(dt.getTime())) return String(d);
    return dt.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false
    });
  } catch (e) {
    return String(d);
  }
}

// -----------------------------------------------------------------------------
// View Switching
// -----------------------------------------------------------------------------
function setView(viewName) {
  currentView = viewName;
  document.body.setAttribute('data-view', viewName);

  $$('.viewbtn').forEach(btn => {
    btn.classList.toggle('on', btn.getAttribute('data-v') === viewName);
  });

  if (viewName === 'dash') {
    renderDashboard().catch(e => toast(e.message, 'err'));
  } else if (viewName === 'graph' && cy) {
    setTimeout(() => {
      cy.resize();
      cy.fit(undefined, 40);
    }, 50);
  }
}

// -----------------------------------------------------------------------------
// KPIs & Header Telemetry
// -----------------------------------------------------------------------------
async function refreshTelemetry() {
  try {
    const kpis = await api('/api/kpis');
    const counts = kpis.counts || {};
    const flagged = kpis.flagged || [];
    const blocked = kpis.blocked_menu_items || kpis.blocked_dishes || 0;
    const holds = kpis.kitchen_holds || 0;

    let redCount = 0;
    let yellowCount = 0;
    flagged.forEach(f => {
      if (f.status === 'RED') redCount++;
      else if (f.status === 'YELLOW') yellowCount++;
    });

    const kpisEl = $('kpis');
    if (kpisEl) {
      kpisEl.innerHTML = `
        <span class="kchip" title="Total active batches">Batches <b>${counts.Batch || 0}</b></span>
        <span class="kchip" title="Cloud kitchens in NCR">Kitchens <b>${counts.CloudKitchen || 0}</b></span>
        <span class="kchip" title="Dishes across menus">Dishes <b>${counts.Dish || 0}</b></span>
        ${redCount > 0 ? `<span class="kchip flag" title="Critical Contaminated Batches">🔴 <b>${redCount} RED</b></span>` : ''}
        ${yellowCount > 0 ? `<span class="kchip flag yellow" title="Batches Under Investigation">🟡 <b>${yellowCount} YELLOW</b></span>` : ''}
        ${blocked > 0 ? `<span class="kchip flag" title="Dishes pulled from menus">🚫 <b>${blocked} pulled</b></span>` : ''}
        ${holds > 0 ? `<span class="kchip flag yellow" title="Kitchen inventory on hold">⚠️ <b>${holds} holds</b></span>` : ''}
      `;
    }

    const pill = $('statuspill');
    if (pill) {
      if (redCount > 0) {
        pill.className = 'pill bad';
        pill.textContent = `● RECALL ACTIVE (${redCount})`;
      } else if (yellowCount > 0) {
        pill.className = 'pill warn';
        pill.textContent = `● INVESTIGATION (${yellowCount})`;
      } else {
        pill.className = 'pill ok';
        pill.textContent = '● ALL SYSTEMS CLEAR';
      }
    }

    const banner = $('recallbanner');
    if (banner) {
      if (redCount > 0 || yellowCount > 0) {
        banner.className = 'banner';
        banner.innerHTML = `
          <div style="display:flex;align-items:center;gap:12px;flex:1">
            <span style="font-size:18px">🚨</span>
            <div>
              <b>CONTAMINATION EVENT DETECTED</b> —
              <span>${redCount} Confirmed Contaminated (RED), ${yellowCount} Suspect (YELLOW) item(s).</span>
            </div>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <button class="btn danger" id="banner-blast">💥 Recall Impact</button>
            <button class="btn" id="banner-dash">📋 Open Dashboard</button>
            <button class="btn" id="banner-dismiss" style="padding:4px 8px">✕</button>
          </div>
        `;
        $('banner-blast').onclick = () => runContaminationMap();
        $('banner-dash').onclick = () => setView('dash');
        $('banner-dismiss').onclick = () => banner.classList.add('hidden');
      } else {
        banner.className = 'banner hidden';
        banner.innerHTML = '';
      }
    }

    return { counts, flagged, blocked, holds, redCount, yellowCount };
  } catch (e) {
    console.error('Failed to refresh telemetry:', e);
  }
}

// -----------------------------------------------------------------------------
// Filter Dock & Network Loading
// -----------------------------------------------------------------------------
async function initFilters() {
  try {
    const opts = await api('/api/filters');
    populateSelect('f-supplier', opts.suppliers, 'id', 'name');
    populateSelect('f-kitchen', opts.kitchens, 'id', 'name');
    populateSelect('f-ingredient', opts.ingredients);
    populateSelect('f-location', opts.locations);
  } catch (e) {
    console.error('Filters init error:', e);
  }
}

function populateSelect(id, items, valKey, labelKey) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = '<option value="(any)">(any)</option>';
  (items || []).forEach(item => {
    const opt = document.createElement('option');
    if (typeof item === 'string') {
      opt.value = item;
      opt.textContent = item;
    } else {
      opt.value = item[valKey];
      opt.textContent = item[labelKey] || item[valKey];
    }
    el.appendChild(opt);
  });
}

function getFilterParams() {
  const params = new URLSearchParams();
  const q = $('f-q')?.value.trim();
  if (q) params.set('q', q);

  const sup = $('f-supplier')?.value;
  if (sup && sup !== '(any)') params.set('supplier', sup);

  const kit = $('f-kitchen')?.value;
  if (kit && kit !== '(any)') params.set('kitchen', kit);

  const ing = $('f-ingredient')?.value;
  if (ing && ing !== '(any)') params.set('ingredient', ing);

  const loc = $('f-location')?.value;
  if (loc && loc !== '(any)') params.set('location', loc);

  const dFrom = $('f-from')?.value;
  if (dFrom) params.set('date_from', dFrom);

  const dTo = $('f-to')?.value;
  if (dTo) params.set('date_to', dTo);

  const statuses = [];
  if ($('f-green')?.checked) statuses.push('GREEN');
  if ($('f-yellow')?.checked) statuses.push('YELLOW');
  if ($('f-red')?.checked) statuses.push('RED');

  statuses.forEach(s => params.append('statuses', s));

  if ($('f-orders')?.checked) {
    params.set('include_orders', 'true');
  }

  return params;
}

async function loadNetwork() {
  const params = getFilterParams();
  const url = `/api/network?${params.toString()}`;
  const data = await api(url);
  rawGraphData = data;
  renderCytoscape(data);

  const countEl = $('nodecount');
  if (countEl) {
    countEl.textContent = `${data.nodes?.length || 0} nodes · ${data.edges?.length || 0} relationships`;
  }
}

function resetNetwork() {
  if ($('f-q')) $('f-q').value = '';
  if ($('f-supplier')) $('f-supplier').value = '(any)';
  if ($('f-kitchen')) $('f-kitchen').value = '(any)';
  if ($('f-ingredient')) $('f-ingredient').value = '(any)';
  if ($('f-location')) $('f-location').value = '(any)';
  if ($('f-from')) $('f-from').value = '';
  if ($('f-to')) $('f-to').value = '';
  if ($('f-green')) $('f-green').checked = true;
  if ($('f-yellow')) $('f-yellow').checked = true;
  if ($('f-red')) $('f-red').checked = true;
  if ($('f-orders')) $('f-orders').checked = false;

  clearSelection();
  clearBlast();
  loadNetwork().catch(e => toast(e.message, 'err'));
}

// -----------------------------------------------------------------------------
// Cytoscape Initialization & Graph Rendering
// -----------------------------------------------------------------------------
function getNodeColor(label, props = {}) {
  if (label === 'Batch') {
    return NODE_PALETTE.Batch[props.status] || '#10b981';
  }
  return NODE_PALETTE[label] || '#94a3b8';
}

function getNodeLabel(label, props = {}) {
  if (label === 'Batch') {
    const icon = props.status === 'RED' ? '🔴' : props.status === 'YELLOW' ? '🟡' : '🟢';
    return `${icon} ${props.id || 'Batch'}\n${props.ingredientName || ''}`;
  }
  if (label === 'Supplier') return `🏢 ${props.name || props.id}`;
  if (label === 'CloudKitchen') return `🍳 ${props.name || props.id}`;
  if (label === 'Dish') return `🍲 ${props.name || props.id}`;
  if (label === 'Order') return `📦 ${props.id}`;
  if (label === 'Customer') return `👤 ${props.name || props.id}`;
  if (label === 'Facility') return `🏭 ${props.name || props.id}`;
  return props.name || props.id || label;
}

function initCytoscape() {
  const container = $('cy');
  if (!container) return;

  cy = cytoscape({
    container,
    boxSelectionEnabled: false,
    autounselectify: false,
    wheelSensitivity: 0.25,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(labelText)',
          'color': '#ffffff',
          'font-family': 'Inter, sans-serif',
          'font-size': '10px',
          'font-weight': 600,
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'text-wrap': 'wrap',
          'text-max-width': '90px',
          'background-color': 'data(bg)',
          'border-width': 2,
          'border-color': 'rgba(255, 255, 255, 0.25)',
          'width': 'data(size)',
          'height': 'data(size)',
          'transition-property': 'background-color, border-color, border-width, opacity, width, height',
          'transition-duration': '0.2s',
        }
      },
      {
        selector: 'edge',
        style: {
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': 'data(edgeColor)',
          'line-color': 'data(edgeColor)',
          'line-opacity': 0.65,
          'width': 1.8,
          'arrow-scale': 0.85,
          'label': 'data(type)',
          'font-family': 'JetBrains Mono, monospace',
          'font-size': '8px',
          'color': '#94a3b8',
          'text-rotation': 'autorotate',
          'text-background-opacity': 0.85,
          'text-background-color': '#030712',
          'text-background-padding': 2,
          'text-background-shape': 'roundrectangle',
          'transition-property': 'line-color, target-arrow-color, width, opacity',
          'transition-duration': '0.2s',
        }
      },
      {
        selector: 'edge[type = "MENU_BLOCKED"]',
        style: {
          'line-style': 'dashed',
          'line-color': '#ef4444',
          'target-arrow-color': '#ef4444',
          'width': 2.5,
        }
      },
      // Selected State
      {
        selector: 'node:selected, node.selected',
        style: {
          'border-width': 4,
          'border-color': '#00f2fe',
          'shadow-blur': 18,
          'shadow-color': '#00f2fe',
          'shadow-opacity': 0.8,
        }
      },
      // Traced Path Highlighting
      {
        selector: 'node.traced',
        style: {
          'border-width': 4,
          'border-color': '#f59e0b',
          'shadow-blur': 16,
          'shadow-color': '#f59e0b',
          'shadow-opacity': 0.8,
          'opacity': 1,
        }
      },
      {
        selector: 'edge.traced',
        style: {
          'line-color': '#f59e0b',
          'target-arrow-color': '#f59e0b',
          'width': 3.5,
          'opacity': 1,
        }
      },
      // Recall Blast Radius Highlighting
      {
        selector: 'node.blast-zone',
        style: {
          'border-width': 4,
          'border-color': '#ef4444',
          'shadow-blur': 22,
          'shadow-color': '#ef4444',
          'shadow-opacity': 0.9,
          'opacity': 1,
        }
      },
      {
        selector: 'edge.blast-zone',
        style: {
          'line-color': '#ef4444',
          'target-arrow-color': '#ef4444',
          'width': 3.8,
          'opacity': 1,
        }
      },
      // Dimmed Background Nodes & Edges
      {
        selector: 'node.dimmed',
        style: {
          'opacity': 0.15,
        }
      },
      {
        selector: 'edge.dimmed',
        style: {
          'opacity': 0.08,
        }
      }
    ]
  });

  // Node Click -> Immediate Downstream Trace (Shift+Click -> Upstream)
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    const nid = node.id();
    const label = node.data('label');
    const props = node.data('props') || {};

    selectedNode = { id: nid, label, props };
    updateToolbarState();
    renderInspector(selectedNode);

    if (e.originalEvent && e.originalEvent.shiftKey) {
      traceCorridor(label, nid, 'up');
    } else {
      traceCorridor(label, nid, 'down');
    }
  });

  // Edge Click
  cy.on('tap', 'edge', (e) => {
    const edge = e.target;
    const tip = $('tip');
    if (tip) {
      const type = edge.data('type');
      const props = edge.data('props') || [];
      const pStr = props.map(p => Object.entries(p).map(([k, v]) => `${k}: ${v}`).join(', ')).join('\n');
      showTip(`Relationship: ${type}\n${pStr}`, e.renderedPosition);
    }
  });

  // Tap Background -> Clear
  cy.on('tap', (e) => {
    if (e.target === cy) {
      clearSelection();
      clearBlast();
      hideTip();
    }
  });

  // Tooltip Hover Handlers
  cy.on('mouseover', 'node', (e) => {
    const d = e.target.data();
    const p = d.props || {};
    let text = `[${d.label}] ${p.id || d.id}`;
    if (p.name) text += `\nName: ${p.name}`;
    if (p.ingredientName) text += `\nIngredient: ${p.ingredientName}`;
    if (p.status) text += `\nRisk Status: ${p.status}`;
    if (p.location) text += `\nLocation: ${p.location}`;
    if (p.price) text += `\nPrice: ₹${p.price}`;
    if (p.phone) text += `\nPhone: ${p.phone}`;
    showTip(text, e.renderedPosition);
  });

  cy.on('mouseout', 'node', () => hideTip());
  cy.on('mouseout', 'edge', () => hideTip());
}

function renderCytoscape(data) {
  if (!cy) return;

  const elements = [];
  const nodeIds = new Set();

  (data.nodes || []).forEach(n => {
    nodeIds.add(n.id);
    const size = n.label === 'Supplier' ? 42 :
                 n.label === 'Batch' ? 38 :
                 n.label === 'CloudKitchen' ? 36 :
                 n.label === 'Dish' ? 32 : 28;

    elements.push({
      group: 'nodes',
      data: {
        id: n.id,
        label: n.label,
        labelText: getNodeLabel(n.label, n.props),
        bg: getNodeColor(n.label, n.props),
        size,
        props: n.props || {}
      }
    });
  });

  (data.edges || []).forEach(e => {
    if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
      elements.push({
        group: 'edges',
        data: {
          id: `${e.source}_${e.type}_${e.target}`,
          source: e.source,
          target: e.target,
          type: e.type,
          edgeColor: EDGE_COLORS[e.type] || 'rgba(148, 163, 184, 0.4)',
          props: e.props || []
        }
      });
    }
  });

  cy.elements().remove();
  cy.add(elements);
  applyTopologicalLayout(true);
}

// -----------------------------------------------------------------------------
// Topological Tiered Layout
// -----------------------------------------------------------------------------
function applyTopologicalLayout(fit = true) {
  if (!cy || cy.nodes().length === 0) return;

  const layers = {};
  LAYERS.forEach(l => { layers[l] = []; });

  cy.nodes().forEach(node => {
    const label = node.data('label') || 'Other';
    if (!layers[label]) layers[label] = [];
    layers[label].push(node);
  });

  // Sort nodes in each layer alphabetically
  Object.keys(layers).forEach(k => {
    layers[k].sort((a, b) => a.id().localeCompare(b.id()));
  });

  const X_SPACING = 210;
  const Y_SPACING = 85;

  let maxTierHeight = 0;
  Object.values(layers).forEach(arr => {
    if (arr.length > maxTierHeight) maxTierHeight = arr.length;
  });

  const activeTiers = LAYERS.filter(l => layers[l] && layers[l].length > 0);

  activeTiers.forEach((tierName, tierIdx) => {
    const nodesInTier = layers[tierName];
    const totalNodes = nodesInTier.length;
    const startY = -((totalNodes - 1) * Y_SPACING) / 2;

    nodesInTier.forEach((node, nodeIdx) => {
      const posX = tierIdx * X_SPACING;
      const posY = startY + nodeIdx * Y_SPACING;
      node.position({ x: posX, y: posY });
    });
  });

  if (fit) {
    cy.fit(undefined, 50);
  }
}

// -----------------------------------------------------------------------------
// Click-to-Trace (Upstream & Downstream)
// -----------------------------------------------------------------------------
async function traceCorridor(label, nodeId, direction = 'down') {
  try {
    const res = await api(`/api/trace/${encodeURIComponent(label)}/${encodeURIComponent(nodeId)}?direction=${direction}`);
    const tracedNodeIds = new Set((res.nodes || []).map(n => n.id));
    const tracedEdgeKeys = new Set((res.edges || []).map(e => `${e.source}_${e.type}_${e.target}`));

    activeTrace = { nodes: tracedNodeIds, edges: tracedEdgeKeys, direction };

    cy.batch(() => {
      cy.nodes().forEach(n => {
        if (tracedNodeIds.has(n.id())) {
          n.addClass('traced').removeClass('dimmed');
        } else {
          n.removeClass('traced').addClass('dimmed');
        }
      });

      cy.edges().forEach(e => {
        const key = `${e.source().id()}_${e.data('type')}_${e.target().id()}`;
        if (tracedEdgeKeys.has(key)) {
          e.addClass('traced').removeClass('dimmed');
        } else {
          e.removeClass('traced').addClass('dimmed');
        }
      });
    });

    toast(`Traced ${direction.toUpperCase()}: ${tracedNodeIds.size} nodes highlighted`, 'info');
  } catch (e) {
    console.error('Trace error:', e);
    toast(e.message, 'err');
  }
}

function clearSelection() {
  selectedNode = null;
  activeTrace = null;
  if (cy) {
    cy.batch(() => {
      cy.elements().removeClass('selected traced dimmed');
      if (blastState) {
        applyBlastVisuals();
      }
    });
  }
  updateToolbarState();
  renderInspector(null);
}

// -----------------------------------------------------------------------------
// Blast Radius & Contamination Map
// -----------------------------------------------------------------------------
async function runBlast(batchOrSupplierId) {
  try {
    const isSupplier = selectedNode && selectedNode.label === 'Supplier';
    const endpoint = isSupplier ? `/api/blast-supplier/${encodeURIComponent(batchOrSupplierId)}` :
                                  `/api/blast/${encodeURIComponent(batchOrSupplierId)}`;

    const res = await api(endpoint);
    blastState = {
      batch: res.batch,
      counts: res.counts,
      nodes: new Set(res.node_ids || []),
      edges: new Set((res.edges || []).map(e => `${e.source}_${e.type}_${e.target}`))
    };

    applyBlastVisuals();
    updateToolbarState();

    const c = res.counts || {};
    toast(`💥 Blast radius calculated: ${c.kitchens || 0} kitchens, ${c.dishes || 0} dishes, ${c.orders || 0} orders affected.`, 'warn');
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function runContaminationMap() {
  try {
    const res = await api('/api/contamination');
    blastState = {
      batch: 'ALL FLAGGED',
      counts: res.counts,
      nodes: new Set(res.node_ids || []),
      edges: new Set((res.edges || []).map(e => `${e.source}_${e.type}_${e.target}`))
    };

    applyBlastVisuals();
    updateToolbarState();

    const c = res.counts || {};
    toast(`🚨 System-wide recall blast: ${c.kitchens || 0} kitchens, ${c.dishes || 0} dishes, ${c.orders || 0} orders exposed.`, 'err');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function applyBlastVisuals() {
  if (!cy || !blastState) return;

  cy.batch(() => {
    cy.nodes().forEach(n => {
      if (blastState.nodes.has(n.id())) {
        n.addClass('blast-zone').removeClass('dimmed');
      } else {
        n.removeClass('blast-zone').addClass('dimmed');
      }
    });

    cy.edges().forEach(e => {
      const key = `${e.source().id()}_${e.data('type')}_${e.target().id()}`;
      if (blastState.edges.has(key)) {
        e.addClass('blast-zone').removeClass('dimmed');
      } else {
        e.removeClass('blast-zone').addClass('dimmed');
      }
    });
  });
}

function clearBlast() {
  blastState = null;
  if (cy) {
    cy.batch(() => {
      cy.elements().removeClass('blast-zone dimmed');
      if (activeTrace) {
        cy.nodes().forEach(n => {
          if (activeTrace.nodes.has(n.id())) n.addClass('traced');
          else n.addClass('dimmed');
        });
        cy.edges().forEach(e => {
          const key = `${e.source().id()}_${e.data('type')}_${e.target().id()}`;
          if (activeTrace.edges.has(key)) e.addClass('traced');
          else e.addClass('dimmed');
        });
      }
    });
  }
  updateToolbarState();
}

// -----------------------------------------------------------------------------
// Tooltip & Floating Info
// -----------------------------------------------------------------------------
function showTip(text, pos) {
  const tip = $('tip');
  if (!tip || !pos) return;
  tip.textContent = text;
  tip.style.left = `${pos.x + 14}px`;
  tip.style.top = `${pos.y + 14}px`;
  tip.style.opacity = '1';
}

function hideTip() {
  const tip = $('tip');
  if (tip) tip.style.opacity = '0';
}

// -----------------------------------------------------------------------------
// Toolbar Management
// -----------------------------------------------------------------------------
function updateToolbarState() {
  const hasSelection = !!selectedNode;
  const isBatchOrSup = selectedNode && (selectedNode.label === 'Batch' || selectedNode.label === 'Supplier');
  const isBatch = selectedNode && selectedNode.label === 'Batch';

  $('btn-up').disabled = !hasSelection;
  $('btn-expand').disabled = !hasSelection;
  $('btn-collapse').disabled = !hasSelection;
  $('btn-blast').disabled = !isBatchOrSup;
  $('btn-clearblast').disabled = !blastState;
  $('btn-timeline').disabled = !isBatch;
  $('btn-pulllist').disabled = !isBatch;
}

// -----------------------------------------------------------------------------
// Inspector Panel (Live Node Telemetry & Recall Controls)
// -----------------------------------------------------------------------------
async function renderInspector(node) {
  const body = $('insp-body');
  if (!body) return;

  if (!node) {
    body.innerHTML = `
      <div style="text-align:center;padding:40px 10px;color:var(--txt-muted)">
        <div style="font-size:28px;margin-bottom:12px;opacity:0.6">🕸</div>
        <h3 style="font-size:14px;font-weight:700;color:var(--txt-bright);margin-bottom:6px">No Node Selected</h3>
        <p style="font-size:12px;line-height:1.5">
          Click any <b>Supplier</b>, <b>Batch</b>, <b>Kitchen</b>, or <b>Dish</b> to inspect telemetry,
          run instant click-to-trace, detonate recall simulations, and enforce containment.
        </p>
        <div style="margin-top:20px;display:flex;flex-direction:column;gap:6px;font-size:11px;font-family:var(--font-mono)">
          <span><kbd style="padding:2px 6px;background:rgba(255,255,255,0.1);border-radius:4px">Click</kbd> Downstream trace</span>
          <span><kbd style="padding:2px 6px;background:rgba(255,255,255,0.1);border-radius:4px">Shift+Click</kbd> Upstream trace</span>
          <span><kbd style="padding:2px 6px;background:rgba(255,255,255,0.1);border-radius:4px">Space</kbd> Fit viewport</span>
        </div>
      </div>
    `;
    return;
  }

  const { id, label, props } = node;
  let html = `
    <div style="border-bottom:1px solid var(--panel-border);padding-bottom:12px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--txt-muted);font-weight:700">${label}</span>
        ${props.status ? `<span class="tag ${props.status.toLowerCase()}">${props.status}</span>` : ''}
      </div>
      <h2 style="font-size:16px;font-weight:800;font-family:var(--font-mono);color:var(--txt-bright)">${id}</h2>
      ${props.name ? `<p style="font-size:12.5px;color:var(--txt-base);margin-top:2px">${props.name}</p>` : ''}
    </div>
  `;

  // Risk Flagging Controls for Batch / Supplier
  if (label === 'Batch' || label === 'Supplier') {
    const curStatus = props.status || 'GREEN';
    html += `
      <div class="panel">
        <h2>Risk State Management</h2>
        <p style="font-size:11.5px;color:var(--txt-muted)">Current status: <b>${curStatus}</b></p>
        ${props.statusReason ? `<p style="font-size:11px;color:#fcd34d">Reason: ${props.statusReason}</p>` : ''}
        <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
          ${curStatus === 'GREEN' ? `
            <button class="btn warn" onclick="promptFlag('${label}', '${id}', 'YELLOW')">Flag 🟡 Suspect</button>
          ` : ''}
          ${curStatus === 'YELLOW' ? `
            <button class="btn danger" onclick="promptFlag('${label}', '${id}', 'RED')">Confirm 🔴 Contaminated</button>
            <button class="btn primary" onclick="promptFlag('${label}', '${id}', 'GREEN')">Clear 🟢 Safe</button>
          ` : ''}
          ${curStatus === 'RED' ? `
            <button class="btn warn" onclick="promptFlag('${label}', '${id}', 'YELLOW')">Downgrade 🟡 Suspect</button>
            <button class="btn primary" onclick="promptFlag('${label}', '${id}', 'GREEN')">Clear 🟢 Safe</button>
          ` : ''}
        </div>
      </div>
    `;
  }

  // Kitchen Menu Pulls & Recall Execution (for Batch)
  if (label === 'Batch') {
    try {
      const pullData = await api(`/api/pull-list/${encodeURIComponent(id)}`);
      const list = pullData.pull_list || [];

      html += `
        <div class="panel">
          <h2>Affected Kitchen Status</h2>
          <div class="kchips" style="margin-bottom:10px">
            ${list.length === 0 ? '<span style="font-size:11px;color:var(--txt-muted)">No kitchens affected in window</span>' :
              list.map(k => `
                <span class="kchip-state ${k.pulled ? 'pulled' : 'live'}">
                  ${k.kitchen} [${k.pulled ? 'PULLED' : 'ACTIVE'}]
                </span>
              `).join('')}
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <button class="btn danger wide" onclick="pullBatchMenu('${id}')">🚫 Pull Dishes from Menus</button>
            <button class="btn wide" onclick="restoreBatchMenu('${id}')">↺ Restore Menus</button>
            <button class="btn primary wide" onclick="notifyBatchCustomers('${id}')">📱 Send Customer Outreach</button>
          </div>
        </div>
      `;
    } catch (e) {
      console.warn('Failed to load pull list preview:', e);
    }
  }

  // Quick Action Buttons
  html += `
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      ${label === 'Batch' ? `
        <button class="btn wide" onclick="openBatchTimeline('${id}')">⏱ Incident Timeline</button>
        <button class="btn wide" onclick="openRecallReport('${id}')">📜 FSSAI Compliance Report</button>
      ` : ''}
      <button class="btn wide" onclick="expandNodeNeighborhood('${label}', '${id}')">➕ Expand Connections</button>
    </div>
  `;

  // Raw Properties Table
  html += `
    <div class="panel">
      <h2>Node Properties</h2>
      <table style="width:100%;font-size:11px;border-collapse:collapse">
        ${Object.entries(props).map(([k, v]) => `
          <tr>
            <td style="padding:4px 0;color:var(--txt-muted);font-family:var(--font-mono)">${k}</td>
            <td style="padding:4px 0;text-align:right;color:var(--txt-bright);font-weight:600">${typeof v === 'object' ? JSON.stringify(v) : v}</td>
          </tr>
        `).join('')}
      </table>
    </div>
  `;

  body.innerHTML = html;
}

// -----------------------------------------------------------------------------
// Interventions & Actions
// -----------------------------------------------------------------------------
async function promptFlag(label, id, newStatus) {
  const reason = prompt(`Enter reason for transitioning ${id} to ${newStatus}:`,
    newStatus === 'RED' ? 'Confirmed microbial contamination via laboratory test' :
    newStatus === 'YELLOW' ? 'Cold-chain temperature deviation during transit' :
    'Batch verified safe by FSSAI quality audit');

  if (!reason) return;

  try {
    const endpoint = label === 'Supplier' ? `/api/flag-supplier/${encodeURIComponent(id)}` :
                                            `/api/flag/${encodeURIComponent(id)}`;

    await api(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_status: newStatus, reason, actor: 'mission_control' })
    });

    toast(`Successfully updated ${id} to ${newStatus}`, 'ok');
    await refreshTelemetry();
    await loadNetwork();

    if (selectedNode && selectedNode.id === id) {
      selectedNode.props.status = newStatus;
      selectedNode.props.statusReason = reason;
      renderInspector(selectedNode);
    }
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function pullBatchMenu(batchId) {
  try {
    const res = await api(`/api/actions/pull-menu/${encodeURIComponent(batchId)}`, { method: 'POST' });
    toast(`Pulled ${(res.pulled || []).length} dish-kitchen pairs from active menus`, 'ok');
    await refreshTelemetry();
    if (selectedNode) renderInspector(selectedNode);
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function restoreBatchMenu(batchId) {
  try {
    const res = await api(`/api/actions/restore-menu/${encodeURIComponent(batchId)}`, { method: 'POST' });
    toast(`Restored ${res.restored || 0} menu items back to active service`, 'ok');
    await refreshTelemetry();
    if (selectedNode) renderInspector(selectedNode);
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function notifyBatchCustomers(batchId) {
  try {
    const res = await api(`/api/actions/notify/${encodeURIComponent(batchId)}`, { method: 'POST' });
    toast(`Dispatched safety notifications for ${res.orders_notified || 0} customer orders`, 'ok');
    await refreshTelemetry();
    if (selectedNode) renderInspector(selectedNode);
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function expandNodeNeighborhood(label, id) {
  try {
    const res = await api(`/api/expand/${encodeURIComponent(label)}/${encodeURIComponent(id)}`);
    if (!cy) return;

    const existingIds = new Set(cy.nodes().map(n => n.id()));
    const newElements = [];

    (res.nodes || []).forEach(n => {
      if (!existingIds.has(n.id)) {
        newElements.push({
          group: 'nodes',
          data: {
            id: n.id,
            label: n.label,
            labelText: getNodeLabel(n.label, n.props),
            bg: getNodeColor(n.label, n.props),
            size: 32,
            props: n.props || {}
          }
        });
      }
    });

    (res.edges || []).forEach(e => {
      const edgeId = `${e.source}_${e.type}_${e.target}`;
      if (!cy.getElementById(edgeId).length) {
        newElements.push({
          group: 'edges',
          data: {
            id: edgeId,
            source: e.source,
            target: e.target,
            type: e.type,
            edgeColor: EDGE_COLORS[e.type] || '#94a3b8',
            props: e.props || []
          }
        });
      }
    });

    if (newElements.length > 0) {
      cy.add(newElements);
      applyTopologicalLayout(false);
      toast(`Expanded ${newElements.length} connected entities`, 'info');
    } else {
      toast('All neighboring connections are already displayed', 'info');
    }
  } catch (e) {
    toast(e.message, 'err');
  }
}

// -----------------------------------------------------------------------------
// Operations Dashboard (Live Operational Face)
// -----------------------------------------------------------------------------
async function renderDashboard() {
  const heroEl = $('d-hero');
  const watchEl = $('d-watch');
  const pullEl = $('d-pull');
  const focusEl = $('d-focus');
  const auditEl = $('d-audit');
  const outreachEl = $('d-outreach');

  const telemetry = await refreshTelemetry();
  const counts = telemetry?.counts || {};
  const flagged = telemetry?.flagged || [];

  // 1. Hero Telemetry Cards
  if (heroEl) {
    heroEl.innerHTML = `
      <div class="hcard">
        <div class="n">${counts.Batch || 0}</div>
        <div class="l">Total Batches</div>
      </div>
      <div class="hcard">
        <div class="n" style="color:#10b981">${(counts.Batch || 0) - (telemetry.redCount + telemetry.yellowCount)}</div>
        <div class="l">🟢 Safe Batches</div>
      </div>
      <div class="hcard ${telemetry.yellowCount > 0 ? 'warn' : ''}">
        <div class="n" style="color:#f59e0b">${telemetry.yellowCount}</div>
        <div class="l">🟡 Suspect Batches</div>
      </div>
      <div class="hcard ${telemetry.redCount > 0 ? 'alert' : ''}">
        <div class="n" style="color:#ef4444">${telemetry.redCount}</div>
        <div class="l">🔴 Recalls Active</div>
      </div>
      <div class="hcard">
        <div class="n" style="color:#38bdf8">${counts.CloudKitchen || 0}</div>
        <div class="l">Cloud Kitchens</div>
      </div>
      <div class="hcard">
        <div class="n" style="color:#f43f5e">${counts.Customer || 0}</div>
        <div class="l">Customers</div>
      </div>
    `;
  }

  // 2. Contamination Watchlist
  if (watchEl) {
    if (flagged.length === 0) {
      watchEl.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 24px; text-align: center; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; color: var(--muted);">
          ✨ All batches and suppliers are currently GREEN. No active contaminations or recalls.
        </div>
      `;
    } else {
      watchEl.innerHTML = flagged.map(f => `
        <div class="wcard ${f.status.toLowerCase()}">
          <div class="wtop">
            <span class="tag ${f.status.toLowerCase()}">${f.status}</span>
            <span class="wid">${f.id}</span>
            <span class="wkind">${f.kind}</span>
          </div>
          <div class="wreason">${f.reason || 'Flagged under recall investigation'}</div>
          <div class="wacts">
            <button class="btn" onclick="focusOnGraph('${f.kind}', '${f.id}')">🕸 View Graph</button>
            <button class="btn danger" onclick="triggerBlastAndSwitch('${f.id}')">💥 Blast</button>
            <button class="btn" onclick="focusPullList('${f.id}')">📋 Pull List</button>
            <button class="btn" onclick="promptFlag('${f.kind}', '${f.id}', '${f.status === 'RED' ? 'GREEN' : 'RED'}')">⚡ Change</button>
          </div>
        </div>
      `).join('');
    }
  }

  // Active Batch Focus
  if (!activeWatchBatch && flagged.length > 0) {
    activeWatchBatch = flagged[0].id;
  }

  if (focusEl) {
    focusEl.textContent = activeWatchBatch ? `(${activeWatchBatch})` : '';
  }

  // 3. Kitchen Pull List Table
  if (pullEl && activeWatchBatch) {
    try {
      const pullRes = await api(`/api/pull-list/${encodeURIComponent(activeWatchBatch)}`);
      const rows = pullRes.pull_list || [];

      if (rows.length === 0) {
        pullEl.innerHTML = '<p class="muted small" style="padding:12px">No affected kitchens for this batch window.</p>';
      } else {
        pullEl.innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Kitchen</th>
                <th>Location</th>
                <th>Dishes to Pull</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(r => `
                <tr>
                  <td><b>${r.kitchen}</b></td>
                  <td class="muted">${r.location || 'NCR'}</td>
                  <td>${(r.pull_dishes || []).map(d => d.name).join(', ') || '—'}</td>
                  <td>
                    <span class="tag ${r.pulled ? 'pulled' : 'pending'}">${r.pulled ? 'PULLED' : 'ACTION REQ'}</span>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div style="margin-top:10px;display:flex;gap:8px">
            <button class="btn danger" onclick="pullBatchMenu('${activeWatchBatch}')">🚫 Pull All Dishes</button>
            <button class="btn" onclick="restoreBatchMenu('${activeWatchBatch}')">↺ Restore</button>
          </div>
        `;
      }
    } catch (e) {
      pullEl.innerHTML = `<p class="muted small" style="color:#ef4444">Error loading pull list: ${e.message}</p>`;
    }
  }

  // 4. Audit Trail Table
  if (auditEl) {
    try {
      const auditRows = await api('/api/audit?limit=20');
      if (auditRows.length === 0) {
        auditEl.innerHTML = '<p class="muted small" style="padding:12px">No audit events recorded yet.</p>';
      } else {
        auditEl.innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Detail</th>
                <th>Actor</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              ${auditRows.slice(0, 8).map(e => `
                <tr>
                  <td><span class="tag ${e.type === 'STATUS_TRANSITION' ? 'pending' : e.type === 'MENU_PULL' ? 'pulled' : 'live'}">${e.type}</span></td>
                  <td>${e.detail || (e.fromStatus ? `${e.fromStatus} → ${e.toStatus}: ${e.reason || ''}` : '—')}</td>
                  <td class="muted">${e.actor || 'system'}</td>
                  <td class="muted" style="font-family:var(--font-mono);font-size:11px">${fmtDate(e.timestamp)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    } catch (e) {
      auditEl.innerHTML = `<p class="muted small" style="color:#ef4444">Error loading audit: ${e.message}</p>`;
    }
  }

  // 5. Customer Outreach Table
  if (outreachEl && activeWatchBatch) {
    try {
      const impact = await api(`/batches/${encodeURIComponent(activeWatchBatch)}/impact`);
      const orders = impact.orders || [];

      if (orders.length === 0) {
        outreachEl.innerHTML = '<p class="muted small" style="padding:12px">No customer orders fall within the contamination window.</p>';
      } else {
        outreachEl.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <span class="muted small">${orders.length} affected customer orders identified</span>
            <button class="btn primary" onclick="notifyBatchCustomers('${activeWatchBatch}')">📱 Notify All (${orders.length})</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Phone / Email</th>
                <th>Dishes Ordered</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${orders.slice(0, 12).map(o => `
                <tr>
                  <td><b>${o.customer || o.customer_id}</b></td>
                  <td class="muted" style="font-family:var(--font-mono);font-size:11px">${o.phone || o.email || '—'}</td>
                  <td>${(o.dishes || []).join(', ')}</td>
                  <td>
                    <span class="tag ${o.notification_status === 'NOTIFIED' ? 'notified' : 'pending'}">${o.notification_status || 'PENDING'}</span>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    } catch (e) {
      outreachEl.innerHTML = `<p class="muted small" style="color:#ef4444">Error loading customer outreach: ${e.message}</p>`;
    }
  }
}

function focusPullList(batchId) {
  activeWatchBatch = batchId;
  renderDashboard();
}

function focusOnGraph(label, id) {
  setView('graph');
  setTimeout(() => {
    const node = cy.getElementById(id);
    if (node.length) {
      cy.elements().removeClass('selected');
      node.addClass('selected');
      selectedNode = { id, label, props: node.data('props') || {} };
      renderInspector(selectedNode);
      traceCorridor(label, id, 'down');
      cy.animate({ center: { eles: node }, zoom: 1.4, duration: 400 });
    }
  }, 100);
}

function triggerBlastAndSwitch(batchId) {
  setView('graph');
  setTimeout(() => {
    runBlast(batchId);
    const node = cy.getElementById(batchId);
    if (node.length) {
      cy.animate({ center: { eles: node }, zoom: 1.2, duration: 400 });
    }
  }, 100);
}

// -----------------------------------------------------------------------------
// Command Bar (⌘ Commands + >_ Cypher Console)
// -----------------------------------------------------------------------------
function initCommandBar() {
  const mCmd = $('m-cmd');
  const mCy = $('m-cy');
  const cmdInput = $('cmd');
  const cmdGo = $('cmd-go');
  const cmdChips = $('cmdchips');

  if (mCmd && mCy) {
    mCmd.onclick = () => {
      cmdMode = 'cmd';
      mCmd.classList.add('on');
      mCy.classList.remove('on');
      cmdInput.placeholder = 'contaminated · trace BATCH-PANEER-001 · pull list · supplier Gopal · paneer · clear';
      renderCommandChips();
    };

    mCy.onclick = () => {
      cmdMode = 'cy';
      mCy.classList.add('on');
      mCmd.classList.remove('on');
      cmdInput.placeholder = 'MATCH (b:Batch)-[:DELIVERED_TO]->(k) RETURN b.id, k.name LIMIT 20';
      renderCommandChips();
    };
  }

  if (cmdGo && cmdInput) {
    cmdGo.onclick = () => executeCommand(cmdInput.value.trim());
    cmdInput.onkeydown = (e) => {
      if (e.key === 'Enter') {
        executeCommand(cmdInput.value.trim());
      }
    };
  }

  renderCommandChips();
}

function renderCommandChips() {
  const chipsEl = $('cmdchips');
  if (!chipsEl) return;

  const chips = cmdMode === 'cmd' ? [
    'contaminated',
    'trace BATCH-PANEER-001',
    'pull list',
    'supplier Gopal',
    'paneer',
    'orders on',
    'clear',
    'reset'
  ] : [
    'MATCH (b:Batch) RETURN b.id, b.status LIMIT 10',
    'MATCH (s:Supplier)-[:SUPPLIES]->(b) RETURN s.name, b.id',
    'MATCH (k:CloudKitchen)-[:USED_IN]->(d:Dish) RETURN k.name, d.name LIMIT 10'
  ];

  chipsEl.innerHTML = chips.map(c => `
    <span class="cchip" onclick="setAndRunCommand('${c.replace(/'/g, "\\'")}')">${c}</span>
  `).join('');
}

function setAndRunCommand(str) {
  const input = $('cmd');
  if (input) {
    input.value = str;
    executeCommand(str);
  }
}

async function executeCommand(cmd) {
  if (!cmd) return;

  if (cmdMode === 'cy') {
    // Cypher Console Mode
    try {
      toast('Executing Cypher query...', 'info');
      const res = await api('/api/query/cypher', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: cmd })
      });

      if (res.nodes && res.nodes.length > 0) {
        // Merge nodes/edges into cytoscape
        cy.add(res.nodes.map(n => ({
          group: 'nodes',
          data: {
            id: n.id,
            label: n.label,
            labelText: getNodeLabel(n.label, n.props),
            bg: getNodeColor(n.label, n.props),
            size: 32,
            props: n.props || {}
          }
        })));
        applyTopologicalLayout(false);
      }

      openDrawer(`>_ Cypher Results (${res.rows?.length || 0} rows)`, renderCypherTable(res));
      toast(`Query executed successfully (${res.rows?.length || 0} rows)`, 'ok');
    } catch (e) {
      toast(e.message, 'err');
    }
    return;
  }

  // Commands Mode
  const parts = cmd.split(' ');
  const verb = parts[0].toLowerCase();
  const arg = parts.slice(1).join(' ').trim();

  if (verb === 'contaminated' || verb === 'watchlist' || verb === 'recall') {
    runContaminationMap();
  } else if (verb === 'trace') {
    if (parts[1] && parts[1].toLowerCase() === 'up') {
      const targetId = parts[2] || (selectedNode ? selectedNode.id : null);
      if (targetId) traceCorridor('Batch', targetId, 'up');
      else toast('Specify node ID: trace up <ID>', 'warn');
    } else {
      const targetId = arg || (selectedNode ? selectedNode.id : null);
      if (targetId) traceCorridor('Batch', targetId, 'down');
      else toast('Specify node ID: trace <ID>', 'warn');
    }
  } else if (verb === 'blast' || verb === 'impact') {
    const targetId = arg || (selectedNode ? selectedNode.id : 'BATCH-PANEER-001');
    runBlast(targetId);
  } else if (verb === 'pull' || verb === 'pulllist') {
    const targetId = arg || (selectedNode ? selectedNode.id : (activeWatchBatch || 'BATCH-PANEER-001'));
    openDrawer(`Kitchen Pull List (${targetId})`, await fetchPullListHtml(targetId));
  } else if (verb === 'timeline') {
    const targetId = arg || (selectedNode ? selectedNode.id : 'BATCH-PANEER-001');
    openBatchTimeline(targetId);
  } else if (verb === 'report' || verb === 'fssai') {
    const targetId = arg || (selectedNode ? selectedNode.id : 'BATCH-PANEER-001');
    openRecallReport(targetId);
  } else if (verb === 'clear') {
    clearSelection();
    clearBlast();
    toast('Simulation cleared', 'info');
  } else if (verb === 'reset') {
    resetNetwork();
  } else if (verb === 'supplier') {
    $('f-supplier').value = arg || '(any)';
    loadNetwork().catch(e => toast(e.message, 'err'));
  } else if (verb === 'kitchen') {
    $('f-kitchen').value = arg || '(any)';
    loadNetwork().catch(e => toast(e.message, 'err'));
  } else if (verb === 'orders') {
    $('f-orders').checked = arg.toLowerCase() === 'on';
    loadNetwork().catch(e => toast(e.message, 'err'));
  } else {
    // Default search in f-q
    $('f-q').value = cmd;
    loadNetwork().catch(e => toast(e.message, 'err'));
  }
}

function renderCypherTable(res) {
  const cols = res.columns || [];
  const rows = res.rows || [];

  return `
    <div style="font-family:var(--font-mono);font-size:12px">
      <div style="background:rgba(0,0,0,0.3);padding:8px 12px;border-radius:6px;margin-bottom:12px;color:var(--txt-muted)">
        ${res.query}
      </div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr>
            ${cols.map(c => `<th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--panel-border);color:var(--cyan-neon)">${c}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr>
              ${row.map(cell => `<td style="padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.05)">${cell}</td>`).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// -----------------------------------------------------------------------------
// Drawer Modules (Timeline, FSSAI Report, Pull List)
// -----------------------------------------------------------------------------
function openDrawer(title, contentHtml) {
  const drawer = $('drawer');
  const titleEl = $('drawer-title');
  const bodyEl = $('drawer-body');

  if (!drawer) return;

  if (titleEl) titleEl.textContent = title;
  if (bodyEl) bodyEl.innerHTML = contentHtml;

  drawer.classList.remove('hidden');
}

function closeDrawer() {
  const drawer = $('drawer');
  if (drawer) drawer.classList.add('hidden');
}

async function openBatchTimeline(batchId) {
  try {
    const data = await api(`/api/timeline/${encodeURIComponent(batchId)}`);
    const events = data.events || [];

    const html = `
      <div style="max-width:720px;margin:0 auto">
        <div style="margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--panel-border)">
          <h3 style="font-size:15px;color:var(--txt-bright);font-weight:700">Audit & Consumption Timeline: ${batchId}</h3>
          <p class="muted small">${data.ingredient || ''} · Supplied by ${data.supplier?.name || ''} · Status: <b>${data.status}</b></p>
        </div>
        <div class="tl-stream">
          ${events.map(ev => `
            <div class="tl-row" style="display:flex;gap:14px;padding:8px 0;border-bottom:1px dashed rgba(255,255,255,0.08)">
              <span class="tl-time" style="font-family:var(--font-mono);font-size:11px;color:var(--txt-muted);min-width:130px">${fmtDate(ev.time)}</span>
              <span class="tl-marker" style="color:${ev.type.includes('RED') ? '#ef4444' : ev.type.includes('YELLOW') ? '#f59e0b' : '#38bdf8'}">●</span>
              <div class="tl-detail" style="flex:1">
                <b>${ev.event}</b>
                ${ev.detail ? `<div class="muted small" style="margin-top:2px">${ev.detail}</div>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    openDrawer(`🕰 Incident Timeline (${batchId})`, html);
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function openRecallReport(batchId) {
  try {
    const r = await api(`/api/report/${encodeURIComponent(batchId)}`);
    const p = r.product || {};
    const imp = r.impactSummary || {};

    const html = `
      <div style="max-width:800px;margin:0 auto;font-family:var(--font-sans)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--panel-border);padding-bottom:14px;margin-bottom:16px">
          <div>
            <span class="tag" style="background:rgba(56,189,248,0.2);color:#7dd3fc;border:1px solid rgba(56,189,248,0.4)">FSSAI FoSCoS Aligned</span>
            <h2 style="font-size:18px;font-weight:800;color:var(--txt-bright);margin-top:6px">${r.reportType}</h2>
            <p class="muted small">Generated: ${fmtDate(r.generatedAt)}</p>
          </div>
          <button class="btn primary" onclick="window.print()">🖨 Print / Export PDF</button>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px">
          <div class="panel">
            <h2>Product & Batch Identification</h2>
            <p><b>Batch ID:</b> ${p.batchId}</p>
            <p><b>Ingredient:</b> ${p.ingredient}</p>
            <p><b>Supplier:</b> ${p.supplier}</p>
            <p><b>Risk Level:</b> <span class="tag ${String(p.riskStatus).toLowerCase()}">${p.riskStatus}</span></p>
            <p><b>Contamination Reason:</b> ${p.statusReason || '—'}</p>
          </div>
          <div class="panel">
            <h2>Downstream Exposure Blast</h2>
            <p><b>Affected Cloud Kitchens:</b> ${imp.kitchens || 0}</p>
            <p><b>Affected Dishes:</b> ${imp.dishes || 0}</p>
            <p><b>Orders Impacted:</b> ${imp.orders || 0}</p>
            <p><b>Consumers Impacted:</b> ${imp.customers || 0}</p>
          </div>
        </div>

        <div class="panel" style="margin-bottom:16px">
          <h2>Kitchen Containment & Isolation Status</h2>
          <table>
            <thead>
              <tr><th>Kitchen</th><th>Location</th><th>Dishes to Quarantine</th><th>Action Status</th></tr>
            </thead>
            <tbody>
              ${(r.kitchenPullLists || []).map(k => `
                <tr>
                  <td><b>${k.kitchen}</b></td>
                  <td>${k.location || 'NCR'}</td>
                  <td>${(k.pull_dishes || []).map(d => d.name).join(', ')}</td>
                  <td><span class="tag ${k.pulled ? 'pulled' : 'pending'}">${k.pulled ? 'QUARANTINED' : 'PENDING'}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <div class="panel">
          <h2>Regulatory Notice</h2>
          <p class="muted small">${r.complianceNote}</p>
        </div>
      </div>
    `;

    openDrawer(`📜 Recall Dossier (${batchId})`, html);
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function fetchPullListHtml(batchId) {
  const pullData = await api(`/api/pull-list/${encodeURIComponent(batchId)}`);
  const list = pullData.pull_list || [];

  return `
    <div style="max-width:760px;margin:0 auto">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr>
            <th style="text-align:left;padding:8px">Kitchen</th>
            <th style="text-align:left;padding:8px">Location</th>
            <th style="text-align:left;padding:8px">Affected Dishes</th>
            <th style="text-align:left;padding:8px">Status</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(k => `
            <tr>
              <td style="padding:8px"><b>${k.kitchen}</b></td>
              <td style="padding:8px" class="muted">${k.location || 'NCR'}</td>
              <td style="padding:8px">${(k.pull_dishes || []).map(d => d.name).join(', ')}</td>
              <td style="padding:8px"><span class="tag ${k.pulled ? 'pulled' : 'pending'}">${k.pulled ? 'PULLED' : 'ACTIVE'}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// -----------------------------------------------------------------------------
// App Initialization & Event Listeners
// -----------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', async () => {
  initCytoscape();
  await initFilters();
  initCommandBar();

  // View Switching Buttons
  $$('.viewbtn').forEach(btn => {
    btn.onclick = () => setView(btn.getAttribute('data-v'));
  });

  // Filter Buttons
  const btnApply = $('btn-apply');
  if (btnApply) {
    btnApply.onclick = () => loadNetwork().catch(e => toast(e.message, 'err'));
  }

  const btnReset = $('btn-resetnet');
  if (btnReset) {
    btnReset.onclick = () => resetNetwork();
  }

  // Toolbar Actions
  $('btn-up').onclick = () => {
    if (selectedNode) traceCorridor(selectedNode.label, selectedNode.id, 'up');
  };

  $('btn-expand').onclick = () => {
    if (selectedNode) expandNodeNeighborhood(selectedNode.label, selectedNode.id);
  };

  $('btn-collapse').onclick = () => {
    if (selectedNode) {
      toast('Collapsed node neighborhood', 'info');
      clearSelection();
    }
  };

  $('btn-blast').onclick = () => {
    if (selectedNode) runBlast(selectedNode.id);
  };

  $('btn-clearblast').onclick = () => clearBlast();

  $('btn-timeline').onclick = () => {
    if (selectedNode && selectedNode.label === 'Batch') openBatchTimeline(selectedNode.id);
  };

  $('btn-pulllist').onclick = () => {
    if (selectedNode && selectedNode.label === 'Batch') {
      fetchPullListHtml(selectedNode.id).then(h => openDrawer(`Kitchen Pull List (${selectedNode.id})`, h));
    }
  };

  $('btn-layered').onclick = () => applyTopologicalLayout(true);
  $('btn-fit').onclick = () => cy && cy.fit(undefined, 50);

  // Drawer Close
  $('drawer-close').onclick = () => closeDrawer();

  // Global Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

    if (e.key === 'Escape') {
      closeDrawer();
      clearBlast();
      clearSelection();
    } else if (e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      if (cy) cy.fit(undefined, 50);
    } else if (e.key === '1') {
      applyTopologicalLayout(true);
    } else if ((e.key === 'b' || e.key === 'B') && selectedNode) {
      runBlast(selectedNode.id);
    } else if ((e.key === 't' || e.key === 'T') && selectedNode && selectedNode.label === 'Batch') {
      openBatchTimeline(selectedNode.id);
    }
  });

  // Initial Load
  await refreshTelemetry();
  await loadNetwork();
  renderInspector(null);
});

// Explicit window bindings for inline HTML onclick handlers
window.promptFlag = promptFlag;
window.pullBatchMenu = pullBatchMenu;
window.restoreBatchMenu = restoreBatchMenu;
window.notifyBatchCustomers = notifyBatchCustomers;
window.openBatchTimeline = openBatchTimeline;
window.openRecallReport = openRecallReport;
window.expandNodeNeighborhood = expandNodeNeighborhood;
window.focusPullList = focusPullList;
window.focusOnGraph = focusOnGraph;
window.triggerBlastAndSwitch = triggerBlastAndSwitch;
window.setAndRunCommand = setAndRunCommand;