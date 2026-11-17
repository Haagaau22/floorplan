const DEFAULT_STATE = {
  settings: {
    wallHeight: 2.4,
    wasteRate: 10,
    grossScope: 1400,
    corridorLength: 96,
    corridorWidth: 1.5,
    corridorCenter: 1.2
  },
  rooms: [
    [1,26.00,2.20,false,0,6.0,4.0],[2,24.00,2.20,false,0,6.0,4.0],
    [3,32.50,2.40,false,0,6.2,4.2],[4,36.00,2.60,false,0,6.5,4.4],
    [5,43.56,3.20,false,0,7.2,4.8],[6,29.53,2.40,false,0,6.2,4.2],
    [7,29.19,2.40,false,0,6.2,4.2],[8,30.64,2.40,false,0,6.2,3.8],
    [9,25.40,2.50,true,4.2,6.4,6.8],[10,21.80,2.20,true,3.8,6.0,6.5],
    [11,25.80,2.40,false,0,6.2,4.0],[12,29.28,2.40,false,0,6.2,3.8],
    [13,28.96,2.40,false,0,6.2,3.8],[14,30.76,2.60,false,0,6.5,4.2],
    [15,27.70,2.30,false,0,6.1,3.8],[16,34.30,2.80,false,0,6.8,4.5],
    [17,25.63,2.30,false,0,6.1,3.8],[18,25.76,2.30,false,0,6.1,3.8],
    [19,26.14,2.30,false,0,6.1,3.8],[20,26.56,2.30,false,0,6.1,3.8],
    [21,27.90,2.40,false,0,6.2,4.0],[22,34.47,2.80,false,0,6.8,4.4],
    [23,29.65,2.50,false,0,6.4,4.0],[24,29.50,2.50,false,0,6.4,4.0],
    [25,26.00,2.40,false,0,6.2,4.0],[26,26.00,2.40,false,0,6.2,4.0],
    [27,32.56,2.70,false,0,6.6,4.2],[28,25.00,2.40,true,4.0,6.2,6.6],
    [29,24.00,2.30,false,0,6.1,3.8],[30,25.00,2.40,false,0,6.2,3.8],
    [31,26.00,2.40,false,0,6.2,3.8],[32,26.00,2.50,false,0,6.4,4.0]
  ].map(([number,totalFloor,bathFloor,closedKitchen,kitchenFloor,bathPerimeter,kitchenWallLength]) => ({
    number,totalFloor,bathFloor,closedKitchen,kitchenFloor,bathPerimeter,kitchenWallLength
  }))
};

const STORAGE_KEY = 'apartment-tile-estimate-v1';
const TILES = [
  { key: 'floor80', size: '80×80cm', use: '房间及开放厨房地面', unitArea: .64 },
  { key: 'floor40', size: '40×40cm', use: '卫生间及封闭厨房地面', unitArea: .16 },
  { key: 'wall40x80', size: '40×80cm', use: '卫生间、厨房墙面', unitArea: .32 },
  { key: 'corridor', size: '60×120cm', use: '房间外公共走廊', unitArea: .72 }
];

let state = loadState();
let toastTimer;
let saveTimer;

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function safeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
function format(value, digits = 2) {
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}
function formatInt(value) { return new Intl.NumberFormat('zh-CN').format(Math.ceil(value)); }
function readHash() {
  if (!location.hash.startsWith('#data=')) return null;
  try {
    const encoded = location.hash.slice(6).replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(Array.from(atob(encoded), c => `%${c.charCodeAt(0).toString(16).padStart(2,'0')}`).join(''));
    return JSON.parse(json);
  } catch { return null; }
}
function normalizeState(candidate) {
  const base = clone(DEFAULT_STATE);
  if (!candidate || !candidate.settings || !Array.isArray(candidate.rooms) || candidate.rooms.length !== 32) return base;
  base.settings = { ...base.settings, ...candidate.settings };
  base.rooms = base.rooms.map((room, index) => ({ ...room, ...candidate.rooms[index], number: index + 1 }));
  return base;
}
function loadState() {
  const shared = readHash();
  if (shared) return normalizeState(shared);
  try { return normalizeState(JSON.parse(localStorage.getItem(STORAGE_KEY))); }
  catch { return clone(DEFAULT_STATE); }
}
function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  const label = document.getElementById('saveState');
  if (label) label.textContent = '已保存到本机';
}
function scheduleSave() {
  const label = document.getElementById('saveState');
  if (label) label.textContent = '正在保存…';
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveState, 250);
}
function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

function roomDerived(room) {
  const kitchenFloor = room.closedKitchen ? Math.max(0, safeNumber(room.kitchenFloor)) : 0;
  const floor40 = Math.max(0, safeNumber(room.bathFloor)) + kitchenFloor;
  const floor80 = Math.max(0, safeNumber(room.totalFloor) - floor40);
  const bathWall = Math.max(0, safeNumber(room.bathPerimeter)) * state.settings.wallHeight;
  const kitchenWall = Math.max(0, safeNumber(room.kitchenWallLength)) * state.settings.wallHeight;
  return { floor80, floor40, bathWall, kitchenWall, wallTotal: bathWall + kitchenWall };
}

function totals() {
  const roomTotals = state.rooms.reduce((sum, room) => {
    const d = roomDerived(room);
    sum.roomFloor += safeNumber(room.totalFloor);
    sum.floor80 += d.floor80;
    sum.floor40 += d.floor40;
    sum.bathWall += d.bathWall;
    sum.kitchenWall += d.kitchenWall;
    return sum;
  }, { roomFloor: 0, floor80: 0, floor40: 0, bathWall: 0, kitchenWall: 0 });
  roomTotals.wall40x80 = roomTotals.bathWall + roomTotals.kitchenWall;
  roomTotals.corridor = state.settings.corridorLength * state.settings.corridorWidth;
  roomTotals.totalFloor = roomTotals.roomFloor + roomTotals.corridor;
  return roomTotals;
}

function inputCell(roomIndex, field, value, options = {}) {
  const td = document.createElement('td');
  td.className = 'input-cell';
  td.dataset.print = options.checkbox ? (value ? '是' : '否') : format(value, 2);
  if (options.checkbox) {
    td.classList.add('checkbox-cell');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = Boolean(value);
    input.addEventListener('change', () => {
      state.rooms[roomIndex][field] = input.checked;
      if (!input.checked) state.rooms[roomIndex].kitchenFloor = 0;
      renderRooms(); renderSummary(); scheduleSave();
    });
    td.appendChild(input);
  } else {
    const input = document.createElement('input');
    input.type = 'number';
    input.min = '0';
    input.step = options.step || '0.1';
    input.value = value;
    input.disabled = Boolean(options.disabled);
    input.addEventListener('input', () => {
      state.rooms[roomIndex][field] = safeNumber(input.value);
      td.dataset.print = format(state.rooms[roomIndex][field], 2);
      renderDerivedRow(td.parentElement, roomIndex);
      renderFoot(); renderSummary(); scheduleSave();
    });
    td.appendChild(input);
  }
  return td;
}

function renderRooms() {
  const body = document.getElementById('roomsBody');
  body.replaceChildren();
  state.rooms.forEach((room, index) => {
    const tr = document.createElement('tr');
    tr.dataset.roomIndex = index;
    const number = document.createElement('td'); number.textContent = room.number; tr.appendChild(number);
    tr.appendChild(inputCell(index, 'totalFloor', room.totalFloor));
    tr.appendChild(inputCell(index, 'bathFloor', room.bathFloor));
    tr.appendChild(inputCell(index, 'closedKitchen', room.closedKitchen, { checkbox: true }));
    tr.appendChild(inputCell(index, 'kitchenFloor', room.closedKitchen ? room.kitchenFloor : 0, { disabled: !room.closedKitchen }));
    tr.appendChild(inputCell(index, 'bathPerimeter', room.bathPerimeter));
    tr.appendChild(inputCell(index, 'kitchenWallLength', room.kitchenWallLength));
    for (let i = 0; i < 5; i++) { const td = document.createElement('td'); td.className = 'derived'; tr.appendChild(td); }
    body.appendChild(tr);
    renderDerivedRow(tr, index);
  });
  renderFoot();
}

function renderDerivedRow(tr, index) {
  const d = roomDerived(state.rooms[index]);
  const cells = tr.querySelectorAll('.derived');
  [d.floor80, d.floor40, d.bathWall, d.kitchenWall, d.wallTotal].forEach((value, i) => cells[i].textContent = format(value));
}

function renderFoot() {
  const t = totals();
  const foot = document.getElementById('roomsFoot');
  foot.innerHTML = `<tr><td>合计</td><td>${format(t.roomFloor)}</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>${format(t.floor80)}</td><td>${format(t.floor40)}</td><td>${format(t.bathWall)}</td><td>${format(t.kitchenWall)}</td><td>${format(t.wall40x80)}</td></tr>`;
}

function renderSummary() {
  const t = totals();
  const wasteMultiplier = 1 + state.settings.wasteRate / 100;
  const body = document.getElementById('summaryBody');
  body.replaceChildren();
  let pieceTotal = 0;
  TILES.forEach(tile => {
    const area = t[tile.key];
    const netPieces = Math.ceil(area / tile.unitArea - 1e-9);
    const purchasePieces = Math.ceil(area * wasteMultiplier / tile.unitArea - 1e-9);
    pieceTotal += purchasePieces;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${tile.size}</td><td>${tile.use}</td><td>${format(area)}</td><td>${format(tile.unitArea)}</td><td>${formatInt(netPieces)}</td><td>${formatInt(purchasePieces)}</td><td>${format(purchasePieces * tile.unitArea)}</td>`;
    body.appendChild(tr);
  });
  document.getElementById('wasteBadge').textContent = `含${format(state.settings.wasteRate, 0)}%损耗`;
  document.getElementById('metricFloor').textContent = format(t.totalFloor);
  document.getElementById('metricWall').textContent = format(t.wall40x80);
  document.getElementById('metricPieces').textContent = formatInt(pieceTotal);
  document.getElementById('metricGap').textContent = format(state.settings.grossScope - t.totalFloor);
  renderCorridor(t);
}

function renderCorridor(t) {
  const centerWidth = Math.min(state.settings.corridorCenter, state.settings.corridorWidth);
  const centerArea = state.settings.corridorLength * centerWidth;
  const edgeArea = Math.max(0, t.corridor - centerArea);
  document.getElementById('corridorArea').textContent = `${format(t.corridor)}㎡`;
  document.getElementById('corridorCenterArea').textContent = `${format(centerArea)}㎡`;
  document.getElementById('corridorEdgeArea').textContent = `${format(edgeArea)}㎡`;
  document.getElementById('corridorOneEdge').textContent = `${format(edgeArea / 2)}㎡`;
  const visual = document.querySelector('.corridor-visual');
  const edge = Math.max(.02, (state.settings.corridorWidth - centerWidth) / 2);
  visual.style.gridTemplateColumns = `${edge}fr ${Math.max(.02, centerWidth)}fr ${edge}fr`;
}

function bindSettings() {
  const mapping = {
    wallHeight: 'wallHeight', wasteRate: 'wasteRate', grossScope: 'grossScope',
    corridorLength: 'corridorLength', corridorWidth: 'corridorWidth', corridorCenter: 'corridorCenter'
  };
  Object.entries(mapping).forEach(([id, key]) => {
    const input = document.getElementById(id);
    input.value = state.settings[key];
    input.addEventListener('input', () => {
      state.settings[key] = Math.max(0, safeNumber(input.value));
      renderRooms(); renderSummary(); scheduleSave();
    });
  });
}

function shareState() {
  const json = JSON.stringify(state);
  const encoded = btoa(unescape(encodeURIComponent(json))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const url = `${location.origin}${location.pathname}#data=${encoded}`;
  navigator.clipboard.writeText(url).then(() => showToast('当前版本链接已复制，可直接发给其他人。'))
    .catch(() => { prompt('复制下面的链接：', url); });
}

function csvEscape(value) { return `"${String(value).replace(/"/g, '""')}"`; }
function exportCsv() {
  const header = ['房号','套内地面㎡','卫生间地面㎡','封闭厨房','封闭厨房地面㎡','卫生间周长m','厨房贴墙长度m','80×80地面㎡','40×40地面㎡','卫生间墙砖㎡','厨房墙砖㎡','墙砖合计㎡'];
  const rows = state.rooms.map(room => {
    const d = roomDerived(room);
    return [room.number,room.totalFloor,room.bathFloor,room.closedKitchen?'是':'否',room.closedKitchen?room.kitchenFloor:0,room.bathPerimeter,room.kitchenWallLength,d.floor80,d.floor40,d.bathWall,d.kitchenWall,d.wallTotal];
  });
  const csv = '\ufeff' + [header, ...rows].map(row => row.map(csvEscape).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '公寓瓷砖逐房明细.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

document.getElementById('shareButton').addEventListener('click', shareState);
document.getElementById('printButton').addEventListener('click', () => window.print());
document.getElementById('csvButton').addEventListener('click', exportCsv);
document.getElementById('resetButton').addEventListener('click', () => {
  if (!confirm('确认恢复最初的CAD估算数据吗？当前浏览器中的修改将被清除。')) return;
  state = clone(DEFAULT_STATE);
  history.replaceState(null, '', location.pathname);
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
});

bindSettings();
renderRooms();
renderSummary();
saveState();
document.getElementById('updatedAt').textContent = '2026-11-17 · CAD估算版';
