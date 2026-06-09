'use strict';

// ─── Grid constants ────────────────────────────────────────────────────────────
let ROWS = 60, COLS = 60; const CELL = 9;
const EMPTY = 0, WALL = 1, SHELF = 2, CASHIER = 3, ENTRANCE = 4;

const CELL_COLOR = ['#e8e8e8', '#334155', '#3b82f6', '#22c55e', '#f97316'];
const GRID_LINE  = '#d4d4d4';

// ─── State ─────────────────────────────────────────────────────────────────────
let grid      = mkGrid();
let tool      = WALL;
let drawing   = false;
let lastCell       = null;
let _jobs          = [];   // cached for modal
let currentPreset  = 1;
const _expandedInfoRows = new Set();

// ─── Canvas setup ──────────────────────────────────────────────────────────────
const canvas = document.getElementById('grid-canvas');
const ctx    = canvas.getContext('2d');
canvas.width  = COLS * CELL;
canvas.height = ROWS * CELL;

function mkGrid() {
  return Array.from({length: ROWS}, () => new Int8Array(COLS));
}

// ─── Drawing ───────────────────────────────────────────────────────────────────
function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS; c++)
      paintCell(r, c);
}

function paintCell(r, c) {
  const x = c * CELL, y = r * CELL;
  ctx.fillStyle = CELL_COLOR[grid[r][c]];
  ctx.fillRect(x, y, CELL, CELL);
  ctx.strokeStyle = GRID_LINE;
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x + 0.25, y + 0.25, CELL - 0.5, CELL - 0.5);
}

function setCell(r, c, v) {
  if (grid[r][c] === v) return;
  grid[r][c] = v;
  paintCell(r, c);
  syncSubmitInfo();
}

// ─── Pointer events ────────────────────────────────────────────────────────────
function evCell(e) {
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width  / rect.width;
  const sy = canvas.height / rect.height;
  const c  = Math.floor((e.clientX - rect.left) * sx / CELL);
  const r  = Math.floor((e.clientY - rect.top)  * sy / CELL);
  return (r >= 0 && r < ROWS && c >= 0 && c < COLS) ? {r, c} : null;
}

canvas.addEventListener('mousedown', e => {
  drawing = true;
  const cell = evCell(e);
  if (cell) { setCell(cell.r, cell.c, e.button === 2 ? EMPTY : tool); lastCell = cell; }
});
canvas.addEventListener('mousemove', e => {
  if (!drawing) return;
  const cell = evCell(e);
  if (!cell || (lastCell && lastCell.r === cell.r && lastCell.c === cell.c)) return;
  setCell(cell.r, cell.c, e.buttons === 2 ? EMPTY : tool);
  lastCell = cell;
});
canvas.addEventListener('mouseup',    () => { drawing = false; lastCell = null; });
canvas.addEventListener('mouseleave', () => { drawing = false; lastCell = null; });
canvas.addEventListener('contextmenu', e => { e.preventDefault(); });

// ─── Tool selection ────────────────────────────────────────────────────────────
function selectTool(t, btn) {
  tool = t;
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// ─── Grid utilities ────────────────────────────────────────────────────────────
function clearGrid() {
  grid = mkGrid();
  redraw();
  syncSubmitInfo();
}

// ─── Map preset generators ─────────────────────────────────────────────────────

function _walls() {
  for (let c = 0; c < COLS; c++) { grid[0][c] = WALL; grid[ROWS-1][c] = WALL; }
  for (let r = 0; r < ROWS; r++) { grid[r][0] = WALL; grid[r][COLS-1] = WALL; }
}

function _block(sr, sc, h, w) {
  for (let dr = 0; dr < h; dr++)
    for (let dc = 0; dc < w; dc++) {
      const r = sr+dr, c = sc+dc;
      if (r > 0 && r < ROWS-1 && c > 0 && c < COLS-1) grid[r][c] = SHELF;
    }
}

// 小小超市: 2 排貨架, 3 組, 20×20 格, 演算法展示用
function genTiny() {
  grid = mkGrid(); _walls();
  for (const sr of [3, 8])
    for (let sc = 3; sc <= 15; sc += 6) _block(sr, sc, 2, 2);
  for (let c = 3; c <= 15; c += 6) {
    if (c + 1 < COLS - 1) { grid[16][c] = CASHIER;  grid[16][c + 1] = CASHIER;  }
    if (c + 1 < COLS - 1) { grid[15][c] = ENTRANCE; grid[15][c + 1] = ENTRANCE; }
  }
  redraw(); syncSubmitInfo();
}

// 小超市: 3 排貨架, 2×2 格, 寬走道
function genSmall() {
  grid = mkGrid(); _walls();
  for (const sr of [7, 16, 25])
    for (let sc = 4; sc <= 53; sc += 7) _block(sr, sc, 2, 2);
  // 收銀台 row 42
  for (let c = 4; c <= 53; c += 7)
    if (c+1 < COLS-1) { grid[42][c] = CASHIER; grid[42][c+1] = CASHIER; }
  // 入口 row 41（收銀台正上方）
  for (let c = 4; c <= 53; c += 7)
    if (c+1 < COLS-1) { grid[41][c] = ENTRANCE; grid[41][c+1] = ENTRANCE; }
  redraw(); syncSubmitInfo();
}

// 中型商場: 7 排貨架, 2×2 格
function genMedium() {
  grid = mkGrid(); _walls();
  for (const sr of [4, 11, 18, 25, 32, 39, 46])
    for (const sc of [3, 8, 13, 18, 23, 28, 33, 38, 43, 48, 53]) _block(sr, sc, 2, 2);
  // 收銀台 row 53
  for (let c = 3; c <= 55; c += 5)
    if (c+1 < COLS-1) { grid[53][c] = CASHIER; grid[53][c+1] = CASHIER; }
  // 入口 row 52（收銀台正上方）
  for (let c = 3; c <= 55; c += 5)
    if (c+1 < COLS-1) { grid[52][c] = ENTRANCE; grid[52][c+1] = ENTRANCE; }
  redraw(); syncSubmitInfo();
}

// 大型賣場: 兩翼佈局, 3 寬貨架, 雙排收銀台
function genLarge() {
  grid = mkGrid(); _walls();
  for (const sr of [3, 8, 13, 18, 23, 28, 33, 38, 43]) {
    for (const sc of [2, 6, 10, 14, 18, 22])    _block(sr, sc, 2, 3);
    for (const sc of [34, 38, 42, 46, 50, 54])  _block(sr, sc, 2, 3);
  }
  // 雙排收銀台 rows 51-52
  for (let c = 2; c <= 57; c += 4) {
    if (c+1 < COLS-1) {
      grid[51][c] = CASHIER; grid[51][c+1] = CASHIER;
      grid[52][c] = CASHIER; grid[52][c+1] = CASHIER;
    }
  }
  // 入口 row 50（收銀台正上方）
  for (let c = 2; c <= 57; c += 4)
    if (c+1 < COLS-1) { grid[50][c] = ENTRANCE; grid[50][c+1] = ENTRANCE; }
  redraw(); syncSubmitInfo();
}

// ─── Preset definitions ────────────────────────────────────────────────────────
const PRESETS = [
  { name: '小小超市', params: { agents:  3, listSize: 2, maxSteps:  80, seed: 42, spawnInterval: 0, goalReserve:  10, minTFloor: 20 }, gen: genTiny,   rows: 20, cols: 20 },
  { name: '小超市',   params: { agents: 10, listSize: 3, maxSteps: 300, seed: 42, spawnInterval: 0, goalReserve: 200, minTFloor: 50 }, gen: genSmall,  rows: 60, cols: 60 },
  { name: '中型商場', params: { agents: 20, listSize: 4, maxSteps: 500, seed: 42, spawnInterval: 0, goalReserve: 200, minTFloor: 50 }, gen: genMedium, rows: 60, cols: 60 },
  { name: '大型賣場', params: { agents: 35, listSize: 5, maxSteps: 800, seed: 99, spawnInterval: 0, goalReserve: 200, minTFloor: 50 }, gen: genLarge,  rows: 60, cols: 60 },
];

function selectPreset(i) {
  currentPreset = i;
  document.querySelectorAll('.preset-btn').forEach((b, j) => b.classList.toggle('active', j === i));
  const p = PRESETS[i];
  ROWS = p.rows ?? 60;
  COLS = p.cols ?? 60;
  canvas.width  = COLS * CELL;
  canvas.height = ROWS * CELL;
  p.gen();
  applyParams(p.params);
}

function applyParams(p) {
  document.getElementById('f-agents').value         = p.agents;
  document.getElementById('f-listsize').value       = p.listSize;
  document.getElementById('f-maxsteps').value       = p.maxSteps;
  document.getElementById('f-seed').value           = p.seed;
  document.getElementById('f-spawn-interval').value = p.spawnInterval ?? 0;
  document.getElementById('f-goal-reserve').value   = p.goalReserve   ?? 200;
  document.getElementById('f-min-t-floor').value    = p.minTFloor     ?? 50;
}

function resetParams() {
  applyParams(PRESETS[currentPreset].params);
  toast(`已重置為「${PRESETS[currentPreset].name}」預設值`, '');
}

function toggleAdv() {
  const row = document.getElementById('adv-row');
  const div = document.getElementById('adv-divider');
  const btn = document.getElementById('adv-toggle');
  const open = row.style.display !== 'none';
  row.style.display = open ? 'none' : '';
  div.style.display = open ? 'none' : '';
  btn.textContent   = open ? '進階 ▾' : '進階 ▴';
}

function countType(t) {
  let n = 0;
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS; c++)
      if (grid[r][c] === t) n++;
  return n;
}

function syncSubmitInfo() {
  const shelves   = countType(SHELF);
  const cashiers  = countType(CASHIER);
  const entrances = countType(ENTRANCE);
  const el  = document.getElementById('submit-info');
  const btn = document.getElementById('submit-btn');

  let warn = '';
  if (entrances < 1) warn = '缺少入口（橘色格），至少放置 1 個後再提交';
  else if (cashiers < 1) warn = '缺少收銀台（綠色格），至少放置 1 個後再提交';

  el.textContent = warn || `貨架 ${shelves} 格 · 收銀台 ${cashiers} 格 · 入口 ${entrances} 格`;
  el.style.color = warn ? '#dc2626' : '#94a3b8';
  btn.disabled   = !!warn;

  buildLegend();
}

// Build products dict: "row,col" → {name, stock:3}
function buildProducts() {
  const ABC = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const out = {};
  let i = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      if (grid[r][c] === SHELF) {
        const name = `商品-${ABC[i % 26]}${i >= 26 ? Math.floor(i / 26) : ''}`;
        out[`${r},${c}`] = {name, stock: 3};
        i++;
      }
    }
  }
  return out;
}

// Convert Int8Array rows → plain Array for JSON
function gridToArray() {
  return Array.from(grid, row => Array.from(row));
}

// ─── Legend ────────────────────────────────────────────────────────────────────
function buildLegend() {
  const content = document.getElementById('legend-content');
  if (!content) return;

  const groups = {S: [], C: [], E: []};
  let si = 0, ci = 0, ei = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      if (grid[r][c] === SHELF)    groups.S.push({label:`S${++si}`, r, c});
      if (grid[r][c] === CASHIER)  groups.C.push({label:`C${++ci}`, r, c});
      if (grid[r][c] === ENTRANCE) groups.E.push({label:`E${++ei}`, r, c});
    }
  }

  if (!si && !ci && !ei) {
    content.innerHTML = '<div class="leg-empty">地圖尚無可編號格子</div>';
    return;
  }

  function renderGroup(items, color, title) {
    if (!items.length) return '';
    return `<div class="leg-group">
      <span class="leg-group-lbl" style="color:${color}">${title}</span>
      ${items.map(e =>
        `<button class="leg-chip" style="border-color:${color};color:${color}"
           onclick="highlightCell(${e.r},${e.c})" title="(${e.r},${e.c})">${esc(e.label)}</button>`
      ).join('')}
    </div>`;
  }

  content.innerHTML =
    renderGroup(groups.S, CELL_COLOR[SHELF],    '貨架') +
    renderGroup(groups.C, CELL_COLOR[CASHIER],  '收銀台') +
    renderGroup(groups.E, CELL_COLOR[ENTRANCE], '入口');
}

function highlightCell(r, c) {
  const x = c * CELL, y = r * CELL;
  let count = 0;
  function flash() {
    count++;
    if (count % 2 === 1) {
      ctx.fillStyle = '#fbbf24';
      ctx.fillRect(x, y, CELL, CELL);
    } else {
      paintCell(r, c);
    }
    if (count < 6) setTimeout(flash, 160);
    else paintCell(r, c);
  }
  flash();
}

// ─── Job submission ────────────────────────────────────────────────────────────
async function submitJob() {
  if (countType(ENTRANCE) < 1) { toast('地圖缺少入口（橘色格），請至少放置一個', 'err'); return; }
  if (countType(CASHIER)  < 1) { toast('地圖缺少收銀台（綠色格），請至少放置一個', 'err'); return; }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = '提交中…';

  const payload = {
    map_grid:       gridToArray(),
    products:       buildProducts(),
    num_agents:     int('f-agents',         20),
    list_size:      int('f-listsize',        4),
    max_steps:      int('f-maxsteps',      200),
    algorithm:      'PBS',
    seed:           int('f-seed',           42),
    spawn_interval: int('f-spawn-interval',  0),
    goal_reserve:   int('f-goal-reserve',  200),
    min_t_floor:    int('f-min-t-floor',    50),
  };

  try {
    const r = await fetch('/api/jobs', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify(payload),
    });
    const d = await r.json();
    if (r.ok && d.success) {
      toast(`任務已提交 ${d.data.job_id.slice(0,8)}`, 'ok');
      poll();
    } else {
      toast(d.error?.message || '提交失敗', 'err');
    }
  } catch (e) {
    toast('網路錯誤: ' + e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = '提交任務';
    syncSubmitInfo();  // re-evaluate disabled state
  }
}

function int(id, def) {
  return parseInt(document.getElementById(id).value) || def;
}

// ─── Polling ───────────────────────────────────────────────────────────────────
async function poll() {
  try {
    const [jr, nr] = await Promise.all([fetch('/api/jobs'), fetch('/api/nodes')]);
    if (jr.ok) { const d = await jr.json(); _jobs = d.data || []; renderJobs(_jobs); }
    if (nr.ok) { const d = await nr.json(); renderNodes(d.data || []); }
    document.getElementById('last-poll').textContent =
      '更新 ' + new Date().toLocaleTimeString('zh-TW');
  } catch (_) {}
}

// ─── Render nodes ──────────────────────────────────────────────────────────────
function renderNodes(nodes) {
  const root = document.getElementById('nodes-root');
  if (!nodes.length) {
    root.innerHTML = '<div class="no-nodes">等待節點連線…</div>';
    return;
  }
  const now = Date.now() / 1000;
  root.innerHTML = nodes.map(n => {
    const cls   = {idle:'s-idle', busy:'s-busy', offline:'s-offline'}[n.status] || 's-offline';
    const label = {idle:'閒置',   busy:'計算中', offline:'離線'}[n.status] || n.status;
    let detail;
    if (n.status === 'busy' && n.current_job_id) {
      detail = `任務: ${n.current_job_id.slice(0,8)}…`;
    } else if (n.last_heartbeat) {
      const ago = Math.floor(now - n.last_heartbeat);
      detail = `${ago}s 前心跳`;
    } else {
      detail = '無心跳';
    }
    const cpu = (n.cpu_percent ?? 0).toFixed(1);
    const mem = (n.mem_percent ?? 0).toFixed(1);
    return `<div class="node-card">
      <div class="node-head">
        <span class="node-name">${esc(n.node_id)}</span>
        <span class="badge-status ${cls}">${label}</span>
      </div>
      <div class="node-detail">${detail}</div>
      <div class="node-metrics">CPU ${cpu}%　MEM ${mem}%</div>
    </div>`;
  }).join('');
}

// ─── Render jobs ───────────────────────────────────────────────────────────────
function renderJobs(jobs) {
  document.getElementById('jobs-count').textContent = `共 ${jobs.length} 筆`;
  const tbody = document.getElementById('jobs-root');
  if (!jobs.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="no-jobs">尚無任務</td></tr>';
    return;
  }
  const now = Date.now() / 1000;
  tbody.innerHTML = jobs.map(j => {
    const badgeCls  = {queued:'j-queued', running:'j-running', done:'j-done', failed:'j-failed', cancelled:'j-cancelled'}[j.status] || 'j-queued';
    const statusTxt = {queued:'佇列中', running:'計算中', done:'完成', failed:'失敗', cancelled:'已取消'}[j.status] || j.status;
    const age       = j.submitted_at ? fmtAge(now - j.submitted_at) : '—';
    const node      = j.node_id || '—';
    const elapsed   = j.elapsed_sec != null ? j.elapsed_sec.toFixed(1) + 's' : '—';
    const actions   = buildActions(j);
    const mainRow = `<tr>
      <td class="job-id" title="${esc(j.id)}">${esc(j.id.slice(0,8))}…</td>
      <td><span class="badge-job ${badgeCls}">${statusTxt}</span></td>
      <td>${age}</td>
      <td>${esc(node)}</td>
      <td>${elapsed}</td>
      <td>${actions}</td>
    </tr>`;
    const hasInfo = j.status === 'done' && j.stats && j.stats.agent_plans;
    const infoRow = hasInfo
      ? `<tr class="info-row" id="irow-${j.id}" style="${_expandedInfoRows.has(j.id) ? '' : 'display:none'}">
           <td colspan="6">${buildInfoPanel(j)}</td>
         </tr>`
      : '';
    return mainRow + infoRow;
  }).join('');
}

function buildActions(j) {
  const parts = [];
  if (j.status === 'queued') {
    parts.push(`<button class="btn-xs btn-cancel" onclick="cancelJob('${j.id}')">取消</button>`);
  }
  if (j.status === 'done' && j.result_gif_path) {
    parts.push(`<button class="btn-xs btn-view" onclick="showGif('${j.id}')">查看動畫</button>`);
  }
  if (j.status === 'done' && j.stats && j.stats.agent_plans) {
    parts.push(`<button class="btn-xs btn-info" onclick="toggleInfo('${j.id}')">查看資訊</button>`);
  }
  return parts.join(' ') || '—';
}

function toggleInfo(jobId) {
  const row = document.getElementById(`irow-${jobId}`);
  if (!row) return;
  const isOpen = row.style.display !== 'none';
  row.style.display = isOpen ? 'none' : '';
  if (isOpen) _expandedInfoRows.delete(jobId);
  else _expandedInfoRows.add(jobId);
}

function buildInfoPanel(j) {
  const s = j.stats;
  if (!s || !s.agent_plans) return '<p class="ip-empty">無詳細資料</p>';

  const agentRows = s.agent_plans.map((p, i) => {
    const list = p.shopping_list.length
      ? p.shopping_list.map(lbl =>
          p.skipped_shelves.includes(lbl)
            ? `<s class="sold-out-lbl">${esc(lbl)}</s>`
            : esc(lbl)
        ).join(' → ')
      : '（無購物清單）';
    const note = p.note
      ? `<span class="ip-warn">${esc(p.note)}</span>`
      : (p.skipped_shelves.length ? `${p.skipped_shelves.length} 項售罄` : '全數完成');
    return `<tr>
      <td>顧客 ${i+1}</td>
      <td>${esc(p.start_label)}</td>
      <td class="ip-list">${list}</td>
      <td>${esc(p.assigned_cashier)}</td>
      <td>${note}</td>
    </tr>`;
  }).join('');

  const shelfRows = s.shelf_stock
    ? Object.entries(s.shelf_stock).map(([lbl, info]) => {
        const status = info.sold_out
          ? '<span class="ip-warn">售罄</span>'
          : '<span class="ip-ok">正常</span>';
        return `<tr>
          <td>${esc(lbl)}</td>
          <td>${info.initial}</td>
          <td>${info.final}</td>
          <td>${status}</td>
        </tr>`;
      }).join('')
    : '';

  return `<div class="info-panel">
    <div class="ip-section">
      <div class="ip-title">顧客購物計畫</div>
      <div class="ip-scroll">
        <table class="ip-table">
          <thead><tr><th>顧客</th><th>起點</th><th>購物清單</th><th>收銀台</th><th>結果</th></tr></thead>
          <tbody>${agentRows}</tbody>
        </table>
      </div>
    </div>
    ${shelfRows ? `<div class="ip-section">
      <div class="ip-title">貨架庫存</div>
      <div class="ip-scroll">
        <table class="ip-table">
          <thead><tr><th>貨架</th><th>初始</th><th>最終</th><th>狀態</th></tr></thead>
          <tbody>${shelfRows}</tbody>
        </table>
      </div>
    </div>` : ''}
  </div>`;
}

function fmtAge(sec) {
  if (sec < 60)   return `${Math.floor(sec)}秒前`;
  if (sec < 3600) return `${Math.floor(sec / 60)}分鐘前`;
  return `${Math.floor(sec / 3600)}小時前`;
}

// ─── Actions ───────────────────────────────────────────────────────────────────
async function cancelJob(jobId) {
  try {
    const r = await fetch(`/api/jobs/${jobId}`, {method: 'DELETE'});
    const d = await r.json();
    if (r.ok) { toast('任務已取消', 'ok'); poll(); }
    else toast(d.error?.message || '取消失敗', 'err');
  } catch (_) { toast('網路錯誤', 'err'); }
}

// ─── GIF modal ─────────────────────────────────────────────────────────────────
function showGif(jobId) {
  const job = _jobs.find(j => j.id === jobId);
  document.getElementById('modal-title').textContent = `任務 ${jobId.slice(0,8)}… 結果`;
  document.getElementById('modal-gif').src = `/api/jobs/${jobId}/image?_=${Date.now()}`;
  document.getElementById('modal-overlay').classList.add('open');

  const statsEl = document.getElementById('modal-stats');
  if (job && job.stats) {
    const s = job.stats;
    const rows = [
      ['顧客人數',  s.agents        ?? '—'],
      ['完成時步',  s.makespan       ?? '—'],
      ['總代價',    s.sum_of_costs   ?? '—'],
      ['演算法',    job.algorithm    || 'PBS'],
    ];
    if (s.agents_done != null) rows.push(['完成顧客', `${s.agents_done} / ${s.agents}`]);
    if (s.stub) rows.push(['模式', 'Stub 測試']);
    if (s.error) rows.push(['錯誤', s.error]);
    statsEl.innerHTML = rows.map(([l, v]) =>
      `<div class="stat-card"><div class="stat-label">${l}</div><div class="stat-val">${esc(String(v))}</div></div>`
    ).join('');
  } else {
    statsEl.innerHTML = '';
  }

  const infoEl = document.getElementById('modal-info');
  if (job && job.stats && job.stats.agent_plans) {
    infoEl.innerHTML = buildInfoPanel(job);
    infoEl.style.display = '';
  } else {
    infoEl.innerHTML = '';
    infoEl.style.display = 'none';
  }
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.getElementById('modal-gif').src = '';
}

function onOverlayClick(e) {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
}

// ─── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast ${type || ''}`;
  el.textContent = msg;
  document.getElementById('toast-root').appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 320);
  }, 2800);
}

// ─── XSS helper ────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Init ──────────────────────────────────────────────────────────────────────
selectPreset(2);   // 預設載入中型商場
poll();
setInterval(poll, 3000);
