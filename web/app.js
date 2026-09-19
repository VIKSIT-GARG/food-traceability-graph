'use strict';
const $ = (id) => document.getElementById(id);
const LAYERS = ['Supplier','Facility','Batch','CloudKitchen','Dish','Order','Customer'];
const LX = Object.fromEntries(LAYERS.map((l,i)=>[l,i]));
const NODE_COLORS = {Supplier:'#a78bfa',Facility:'#71717a',CloudKitchen:'#38bdf8',
                     Dish:'#fbbf24',Order:'#14b8a6',Customer:'#fb7185'};
const STATUS_COLORS = {GREEN:'#10b981',YELLOW:'#f59e0b',RED:'#ef4444'};
const STATUS_EMOJI = {GREEN:'🟢',YELLOW:'🟡',RED:'🔴'};
const TRANSITIONS = {GREEN:['YELLOW'],YELLOW:['RED','GREEN'],RED:[]};

let cy = null, selected = null, blast = null;
let hlNodes = new Set(), hlEdgeKeys = new Set();

/* ---------------- helpers ---------------- */
async function api(path, opts={}){
  const r = await fetch(path, opts);
  if(!r.ok){ let m = r.statusText; try{ m = (await r.json()).detail || m; }catch(e){}
    throw new Error(m); }
  return r.json();
}
const esc = (s)=> String(s??'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const r1 = (n)=> Math.round(n*10)/10;
function fmtDate(s){ if(!s) return '—'; const d=new Date(s); if(isNaN(d)) return String(s);
  return d.toLocaleString('en-IN',{day:'2-digit',month:'short',year:'numeric',
    hour:'2-digit',minute:'2-digit',hour12:false}); }
function fmtVal(v){ return (typeof v==='string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) ? fmtDate(v) : String(v); }
function toast(msg, kind='info'){ const t=document.createElement('div');
  t.className='toast '+kind; t.textContent=msg; document.body.appendChild(t);
  setTimeout(()=>t.remove(), 3400); }
function errBox(m){ return `<div class="errbox">⚠️ ${esc(m)}</div>`; }

function edgeLabel(type, props){
  if(type==='DELIVERED_TO'){ const q=props.reduce((a,p)=>a+(p.qtyKg||0),0);
    const t=props.find(p=>p.deliveryDate)?.deliveryDate;
    return `${r1(q)} kg${t?' · '+fmtDate(t):''}`; }
  if(type==='USED_IN_DISH'){ const q=props.reduce((a,p)=>a+(p.quantity||0),0);
    const ts=props.map(p=>p.timestamp).filter(Boolean).sort();
    return ts.length?`${r1(q)} kg @ ${fmtDate(ts[ts.length-1])}${ts.length>1?' ×'+ts.length:''}`:''; }
  if(type==='CONTAINS_DISH'){ return `×${r1(props.reduce((a,p)=>a+(p.quantity||0),0))}`; }
  if(type==='PROCESSED_AT'){ const t=props.find(p=>p.timestamp)?.timestamp;
    return t?fmtDate(t):''; }
  if(type==='SUPPLIED') return 'SUPPLIED';
  return '';
}
function nodeColor(label, props){
  return label==='Batch' ? (STATUS_COLORS[props.status]||'#64748b') : (NODE_COLORS[label]||'#64748b');
}
function nodeLabelText(label, props){
  return label==='Batch'
    ? `${props.id}\n${props.ingredientName||''} ${STATUS_EMOJI[props.status]||''}`
    : (props.name || props.id);
}

/* ---------------- cytoscape ---------------- */
function initCy(){
  cy = cytoscape({ container: $('cy'), elements: [], layout:{name:'preset'},
    wheelSensitivity: 0.2, minZoom: 0.05, maxZoom: 3,
    style: [
      {selector:'node', style:{'background-color':'data(color)', label:'data(ltext)',
        color:'#dbe4f0','text-valign':'bottom','text-margin-y':7,'font-size':10.5,
        'font-family':'Inter','text-wrap':'wrap','text-max-width':130,
        width:24,height:24,'border-width':2,'border-color':'data(border)',
        'overlay-padding':3}},
      {selector:'node[label="Batch"]', style:{width:38,height:38,'font-size':11.5}},
      {selector:'edge', style:{width:1.5,'line-color':'#334155','target-arrow-color':'#334155',
        'target-arrow-shape':'triangle','curve-style':'bezier',label:'data(label)',
        'font-size':8.5,color:'#8fa3bf','text-rotation':'autorotate',
        'text-background-color':'#070d1a','text-background-opacity':.9,
        'text-background-padding':2}},
      {selector:'node.sel', style:{'border-color':'#38bdf8','border-width':4}},
      {selector:'node.traced', style:{'border-color':'#fbbf24','border-width':4}},
      {selector:'edge.traced-e', style:{'line-color':'#fbbf24','target-arrow-color':'#fbbf24',width:2.4}},
      {selector:'node.blast', style:{'border-color':'#ef4444','border-width':4}},
      {selector:'edge.blast-e', style:{'line-color':'#ef4444','target-arrow-color':'#ef4444',width:2.4}},
      {selector:'node.dim', style:{opacity:.14}},
      {selector:'edge.dim', style:{opacity:.06}},
    ]});
  cy.on('tap','node', ev=> selectNode(ev.target));
  cy.on('tap', ev=>{ if(ev.target===cy) clearSelection(); });
  const tip=$('tip');
  cy.on('mouseover','node', ev=>{ tip.textContent = ev.target.data('label')+' · '+ev.target.id()
    +'\n'+Object.entries(ev.target.data('props')||{}).slice(0,6).map(([k,v])=>k+': '+fmtVal(v)).join('\n');
    tip.style.opacity=1; });
  cy.on('mousemove', ev=>{ if(ev.renderedPosition){
    tip.style.left=(ev.renderedPosition.x+16)+'px'; tip.style.top=(ev.renderedPosition.y+12)+'px';}});
  cy.on('mouseout','node', ()=> tip.style.opacity=0);
}

function applyLayeredLayout(fit=true){
  const byLayer={};
  cy.nodes().forEach(n=>{ const l=n.data('label'); (byLayer[l]=byLayer[l]||[]).push(n); });
  for(const [l,nodes] of Object.entries(byLayer)){
    const x=(LX[l] ?? 3.5)*250;
    nodes.forEach((n,i)=> n.position({x, y:(i-(nodes.length-1)/2)*95}));
  }
  if(fit) cy.fit(undefined,45);
}

function addStore(data){
  const els=[];
  for(const n of data.nodes||[]){
    const color=nodeColor(n.label,n.props);
    const border=n.label==='Batch'?color:'rgba(255,255,255,.25)';
    const ex=cy.getElementById(n.id);
    if(ex.length){ ex.data({ltext:nodeLabelText(n.label,n.props),color,border,props:n.props}); }
    else els.push({group:'nodes',data:{id:n.id,label:n.label,ltext:nodeLabelText(n.label,n.props),
      color,border,props:n.props}});
  }
  for(const e of data.edges||[]){
    const key=`${e.type}|${e.source}|${e.target}`;
    if(cy.getElementById(key).length) continue;
    els.push({group:'edges',data:{id:key,key,source:e.source,target:e.target,
      label:edgeLabel(e.type,e.props||[]),etype:e.type}});
  }
  if(els.length) cy.add(els);
  applyLayeredLayout(false);
}

/* ---------------- highlights & blast ---------------- */
function applyHighlights(){
  cy.elements().removeClass('traced traced-e');
  if(hlNodes.size) cy.nodes().filter(n=>hlNodes.has(n.id())).addClass('traced');
  if(hlEdgeKeys.size) cy.edges().filter(e=>hlEdgeKeys.has(e.data('key'))).addClass('traced-e');
}
function applyBlast(){
  cy.nodes().removeClass('blast dim'); cy.edges().removeClass('blast-e dim');
  if(!blast) return;
  cy.nodes().forEach(n=> n.addClass(blast.nodeIds.has(n.id())?'blast':'dim'));
  cy.edges().forEach(e=> e.addClass(blast.edgeKeys.has(e.data('key'))?'blast-e':'dim'));
  cy.fit(undefined,45);
}
function showBanner(){
  const b=$('recallbanner');
  if(!blast){ b.classList.add('hidden'); return; }
  const c=blast.counts;
  b.className='banner '+(blast.simulateOnly?'sim':'');
  b.innerHTML=`<span class="b-title">${blast.simulateOnly?'🚨 RECALL SIMULATION':'🚨 RECALL ACTIVE'}</span>
    <span class="mono">${esc(blast.batch)}</span>
    <span>${c.kitchens} kitchens · ${c.dishes} dishes · ${c.orders} orders · ${c.customers} customers</span>
    <span class="muted">${blast.window?'window ≥ '+fmtDate(blast.window):'full scope'}</span>
    <button class="btn" id="banner-clear">Clear</button>`;
  $('banner-clear').onclick=clearBlast;
}
function clearBlast(){ blast=null; applyBlast(); showBanner(); updateToolbar(); }
async function runBlast(batchId, simulateOnly){
  const d=await api(`/api/blast/${encodeURIComponent(batchId)}`);
  addStore(d.graph);
  blast={nodeIds:new Set(d.node_ids),
         edgeKeys:new Set(d.edges.map(e=>`${e.type}|${e.source}|${e.target}`)),
         counts:d.counts, window:d.window, batch:d.batch, simulateOnly};
  applyBlast(); showBanner(); updateToolbar();
}

/* ---------------- selection / inspector ---------------- */
function clearSelection(clearHl=true){
  if(selected) cy.getElementById(selected.id).removeClass('sel');
  selected=null;
  if(clearHl){ hlNodes.clear(); hlEdgeKeys.clear(); applyHighlights(); }
  $('insp-body').innerHTML=`<div class="empty">👆 Click any node to inspect it.<br><br>
    Trace upstream/downstream · expand or collapse branches ·<br>
    select a <b>Batch</b> to simulate or activate a recall.</div>`;
  updateToolbar();
}
async function selectNode(node){
  if(selected) cy.getElementById(selected.id).removeClass('sel');
  selected={id:node.id(), label:node.data('label')};
  node.addClass('sel'); updateToolbar();
  $('insp-body').innerHTML='<div class="empty">loading…</div>';
  try{
    const d=await api(`/api/node/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}`);
    renderInspector(d);
  }catch(e){ $('insp-body').innerHTML=errBox(e.message); }
}
const selectNodeById=(id,label)=>{ const n=cy.getElementById(id); if(n.length) selectNode(n); };

function propsTable(p){
  const rows=Object.entries(p).filter(([k,v])=>v!==null&&!k.startsWith('_'))
    .map(([k,v])=>`<tr><td>${esc(k)}</td><td class="mono">${esc(fmtVal(v))}</td></tr>`).join('');
  return `<table class="kv"><tbody>${rows||'<tr><td class="muted">none</td></tr>'}</tbody></table>`;
}
function metaStr(m){ if(!m||!Object.keys(m).length) return '—';
  return Object.entries(m).map(([k,v])=>`${k}: ${fmtVal(v)}`).join(' · '); }
function relTable(rels){
  if(!rels||!rels.length) return '<p class="muted small">No relationships.</p>';
  return `<table class="rels"><tbody>${rels.map(r=>`<tr>
    <td class="mono rel">${r.outbound?'→':'←'} ${esc(r.rel)}</td>
    <td>${esc(r.other_label)} <span class="mono">${esc(r.other||'')}</span></td>
    <td class="muted small">${esc(metaStr(r.meta))}</td></tr>`).join('')}</tbody></table>`;
}
function flagFormHtml(status){
  const opts=TRANSITIONS[status]||[];
  if(!opts.length) return `<p class="muted small">🔴 RED is terminal — recall is active. Use the quick actions below.</p>`;
  return `<h3>🚩 Flag batch (audited)</h3><form id="ff">
    <label>Transition</label>
    <select id="ff-status">${opts.map(o=>`<option value="${o}">${status} → ${o}</option>`).join('')}</select>
    <div id="ff-when-wrap" class="${opts[0]==='YELLOW'?'':'hidden'}">
      <label>Contamination from (starts temporal window)</label>
      <input type="datetime-local" id="ff-when" value="2025-09-10T14:00"/></div>
    <label>Reason (stored on AuditEvent)</label>
    <input id="ff-reason" placeholder="e.g. lab sample dispatched"/>
    <button type="submit" class="btn primary wide">Apply transition</button></form>`;
}
function renderInspector(d){
  const p=d.props, label=selected.label, isBatch=label==='Batch';
  const chip=isBatch?`<span class="badge st-${(p.status||'').toLowerCase()}">${STATUS_EMOJI[p.status]||''} ${p.status||''}</span>`
                    :`<span class="chip">${esc(label)}</span>`;
  let html=`<div class="insp-head">${chip}<h2>${esc(p.id)}</h2></div>`;
  if(isBatch){
    html+=`<div class="batchline"><span class="muted small">${esc(p.ingredientName||'')}</span>
      ${p.isActive===false?'<span class="muted small">· expired</span>':''}</div>
      ${p.statusReason?`<p class="reason">${esc(p.statusReason)}</p>`:''}`;
  }
  html+=`<h3>Properties</h3>${propsTable(p)}
    <h3>Relationships <span class="muted">(${d.relationships.length})</span></h3>
    ${relTable(d.relationships)}`;
  if(isBatch){
    html+=flagFormHtml(p.status);
    html+=`<h3>Recall actions</h3><div style="display:grid;gap:7px">
      <button class="btn wide" id="qa-contain">🧊 Hold kitchens (containment)</button>
      <button class="btn wide" id="qa-block">🚫 Block affected dishes</button>
      <button class="btn wide" id="qa-notify">📨 Mark customers notified</button>
      <a class="btn wide" style="text-align:center" href="/api/report/${encodeURIComponent(p.id)}"
         target="_blank">⬇️ FSSAI recall report (JSON)</a></div>`;
  }
  $('insp-body').innerHTML=html;
  const ff=$('ff');
  if(ff){
    $('ff-status').addEventListener('change',e=>
      $('ff-when-wrap').classList.toggle('hidden',e.target.value!=='YELLOW'));
    ff.addEventListener('submit',doFlag);
  }
  [['qa-contain','contain'],['qa-block','block'],['qa-notify','notify']].forEach(([id,k])=>{
    const el=$(id); if(el) el.onclick=()=>quickAction(k);
  });
}
async function doFlag(ev){
  ev.preventDefault();
  const status=$('ff-status').value, reason=$('ff-reason').value.trim();
  if(!reason) return toast('Reason is required (audit trail)','warn');
  let contamination_date=null;
  if(status==='YELLOW'){ const v=$('ff-when').value;
    if(!v) return toast('Contamination datetime required for YELLOW','warn');
    contamination_date=new Date(v).toISOString(); }
  try{
    await api(`/api/flag/${encodeURIComponent(selected.id)}`,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({new_status:status,reason,actor:'web',contamination_date})});
    toast(`${selected.id} → ${status}`,'ok');
    loadKpis(); await runBlast(selected.id,false);
    selectNodeById(selected.id,'Batch');
  }catch(e){ toast(e.message,'err'); }
}
async function quickAction(kind){
  const id=selected.id;
  const paths={contain:`/api/actions/contain/${encodeURIComponent(id)}?status=HOLD`,
               block:`/api/actions/block/${encodeURIComponent(id)}`,
               notify:`/api/actions/notify/${encodeURIComponent(id)}`};
  try{
    const r=await api(paths[kind],{method:'POST'});
    if(kind==='contain') toast('HOLD applied: '+r.kitchens.join(', '),'ok');
    if(kind==='block') toast('Blocked: '+r.dishes.join(', '),'ok');
    if(kind==='notify') toast(r.orders_notified+' orders marked notified','ok');
    loadKpis();
  }catch(e){ toast(e.message,'err'); }
}

/* ---------------- toolbar / traces ---------------- */
function updateToolbar(){
  const has=!!selected, isBatch=has&&selected.label==='Batch';
  $('btn-up').disabled=!has; $('btn-down').disabled=!has;
  $('btn-expand').disabled=!has; $('btn-collapse').disabled=!has;
  $('btn-blast').disabled=!isBatch; $('btn-timeline').disabled=!isBatch;
  $('btn-clearblast').disabled=!blast;
}
async function doTrace(dir){
  if(!selected) return;
  try{
    const d=await api(`/api/trace/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}?direction=${dir}`);
    addStore(d);
    hlNodes=new Set(d.nodes.map(n=>n.id));
    hlEdgeKeys=new Set(d.edges.map(e=>`${e.type}|${e.source}|${e.target}`));
    applyHighlights();
    toast(`Traced ${dir}: ${d.nodes.length} nodes`,'ok');
  }catch(e){ toast(e.message,'err'); }
}
function collapseBranch(){
  if(!selected) return;
  const desc=cy.getElementById(selected.id).successors().nodes();
  cy.remove(desc); applyLayeredLayout(true);
  toast(`Collapsed ${desc.length} downstream nodes (visual)`,'ok');
}

/* ---------------- timeline drawer ---------------- */
async function showTimeline(){
  if(!selected||selected.label!=='Batch') return;
  try{
    const d=await api(`/api/timeline/${encodeURIComponent(selected.id)}`);
    const win=d.contamination_date?new Date(d.contamination_date):null;
    let html=`<p class="muted small">${esc(d.batch)} · ${esc(d.ingredient||'')} ·
      ${STATUS_EMOJI[d.status]||''} ${esc(d.status||'')} · supplier: ${esc(d.supplier||'')}</p>`;
    let markerDone=!win;
    for(const ev of d.events){
      const ts=new Date(ev.ts);
      if(!markerDone && ts>=win){
        html+=`<div class="tl-event">⛔ Contamination event — ${fmtDate(d.contamination_date)}<br>
          <span class="muted small">usage below is CLEAR · above is IN WINDOW</span></div>`;
        markerDone=true;
      }
      const cls=ev.kind==='AUDIT'?'tl-audit':(win&&ts>=win?'tl-in':'tl-clear');
      html+=`<div class="tl-row ${cls}"><span class="tl-time mono">${fmtDate(ev.ts)}</span>
        <span class="tl-chip">${esc(ev.kind)}</span><span>${esc(ev.label)}</span></div>`;
    }
    $('drawer-title').textContent='🕰 '+d.batch;
    $('drawer-body').innerHTML=html;
    $('drawer').classList.remove('hidden');
  }catch(e){ toast(e.message,'err'); }
}

/* ---------------- data loading ---------------- */
async function loadFilters(){
  const o=await api('/api/filters');
  const fill=(id,arr)=>{ const s=$(id);
    arr.forEach(v=>{ const op=document.createElement('option'); op.value=v; op.textContent=v; s.appendChild(op); }); };
  fill('f-supplier',o.suppliers.map(s=>`${s.id} — ${s.name}`));
  fill('f-kitchen',o.kitchens.map(k=>`${k.id} — ${k.name}`));
  fill('f-ingredient',o.ingredients);
  fill('f-location',o.locations);
}
async function loadKpis(){
  const k=await api('/api/kpis'); const c=k.counts;
  const chip=(l,v)=>`<span class="kchip">${l}<b>${v??0}</b></span>`;
  $('kpis').innerHTML=[chip('Suppliers',c.Supplier),chip('Batches',c.Batch),
    chip('Kitchens',c.CloudKitchen),chip('Dishes',c.Dish),chip('Orders',c.Order),
    chip('Customers',c.Customer),chip('Blocked 🚫',k.blocked_dishes),chip('Holds 🧊',k.kitchen_holds)]
    .join('')
    +k.flagged.map(f=>`<span class="kchip flag ${f.status.toLowerCase()}">
      ${STATUS_EMOJI[f.status]} ${esc(f.id)}</span>`).join('');
  const anyRed=k.flagged.some(f=>f.status==='RED');
  const pill=$('statuspill');
  pill.className='pill '+(anyRed?'bad':(k.flagged.length?'warn':'ok'));
  pill.textContent=anyRed?'● RECALL ACTIVE':(k.flagged.length?'● INVESTIGATING':'● ALL CLEAR');
}
async function loadNetwork(){
  const p=new URLSearchParams();
  const q=$('f-q').value.trim(); if(q) p.set('q',q);
  [['f-supplier','supplier'],['f-kitchen','kitchen'],['f-ingredient','ingredient'],
   ['f-location','location']].forEach(([id,param])=>{
    const v=$(id).value; if(v&&v!=='(any)') p.set(param,v.split(' — ')[0]); });
  const st=[]; if($('f-green').checked)st.push('GREEN');
  if($('f-yellow').checked)st.push('YELLOW'); if($('f-red').checked)st.push('RED');
  if(st.length&&st.length<3) st.forEach(s=>p.append('statuses',s));
  if($('f-from').value) p.set('date_from',$('f-from').value);
  if($('f-to').value) p.set('date_to',$('f-to').value);
  const data=await api('/api/network?'+p.toString());
  blast=null; hlNodes.clear(); hlEdgeKeys.clear(); selected=null;
  cy.elements().remove(); addStore(data);
  $('nodecount').textContent=`${data.nodes.length} nodes · ${data.edges.length} relationships — live from Neo4j`;
  showBanner(); clearSelection(false); updateToolbar();
}

/* ---------------- boot ---------------- */
window.addEventListener('DOMContentLoaded', async ()=>{
  if(!window.cytoscape){
    document.body.innerHTML=`<div class="cdn-error"><b>Cytoscape.js failed to load from the CDN.</b><br>
      Your network blocks cdn.jsdelivr.net. Download
      <span class="mono">https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js</span>
      in your browser, save it as <span class="mono">web/cytoscape.min.js</span>, and change the
      script tag in <span class="mono">web/index.html</span> to
      <span class="mono">&lt;script src="/cytoscape.min.js"&gt;&lt;/script&gt;</span>, then refresh.</div>`;
    return;
  }
  initCy(); clearSelection(false);
  try{
    await loadFilters(); await loadKpis(); await loadNetwork();
  }catch(e){
    document.body.innerHTML=`<div class="boot-error"><b>Cannot reach the backend.</b><br>
      ${esc(e.message)}<br><br>Start it from the project root:<br>
      <span class="mono">uvicorn web_app:app --reload</span><br>
      then open <span class="mono">http://localhost:8000</span></div>`;
    return;
  }
  $('btn-apply').onclick=()=>loadNetwork().catch(e=>toast(e.message,'err'));
  $('btn-resetnet').onclick=()=>{ ['f-q'].forEach(i=>$(i).value='');
    ['f-supplier','f-kitchen','f-ingredient','f-location'].forEach(i=>$(i).value='(any)');
    ['f-from','f-to'].forEach(i=>$(i).value='');
    ['f-green','f-yellow','f-red'].forEach(i=>$(i).checked=true);
    loadNetwork().then(()=>toast('Network reset','ok')).catch(e=>toast(e.message,'err')); };
  $('btn-up').onclick=()=>doTrace('up');
  $('btn-down').onclick=()=>doTrace('down');
  $('btn-expand').onclick=async()=>{ if(!selected)return;
    try{ addStore(await api(`/api/expand/${encodeURIComponent(selected.label)}/${encodeURIComponent(selected.id)}`));
      applyLayeredLayout(true); }catch(e){ toast(e.message,'err'); } };
  $('btn-collapse').onclick=collapseBranch;
  $('btn-blast').onclick=()=>{ if(selected&&selected.label==='Batch')
    runBlast(selected.id,true).catch(e=>toast(e.message,'err')); };
  $('btn-clearblast').onclick=clearBlast;
  $('btn-timeline').onclick=showTimeline;
  $('drawer-close').onclick=()=>$('drawer').classList.add('hidden');
  $('btn-layered').onclick=()=>applyLayeredLayout(true);
  $('btn-force').onclick=()=>cy.layout({name:'cose',animate:true,idealEdgeLength:110,
    nodeOverlap:18}).run();
  $('btn-fit').onclick=()=>cy.fit(undefined,45);
  document.addEventListener('keydown',e=>{ if(e.key==='Escape'){ clearBlast(); clearSelection(); }});
});