/*
 * data/files.json に並んでいるファイルを一覧にして、1 クリックで保存できるようにする。
 *
 * ファイルの実体はこのサイト自身が配っている（files/ 配下）。
 * 外部のホストは一切参照しないので、このページが開ける環境なら必ず落とせる。
 */
'use strict';

const FILES_URL = './data/files.json';
const SOURCES_URL = './data/sync.json';

const LS = {
  removed: 'fb.removed.v1',   // この端末で非表示にしたファイル
};

/* ============================================================
 * ユーティリティ
 * ========================================================== */

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  return node;
};

/**
 * 要素が見つからなくても、そこで初期化全体を止めない。
 * HTML と JS の版がずれたときに、ページごと無反応になるのを防ぐ。
 */
function on(selector, type, handler) {
  const node = $(selector);
  if (!node) {
    console.warn(`${selector} が見つかりません`);
    return;
  }
  node.addEventListener(type, handler);
}

const SVG_NS = 'http://www.w3.org/2000/svg';

/** currentColor で描く線画アイコン。ライト／ダークどちらでもボタン色に追従する */
function icon(paths) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '19');
  svg.setAttribute('height', '19');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  for (const d of paths) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  return svg;
}

const ICON_DOWNLOAD = ['M12 3v12', 'M7 10l5 5 5-5', 'M4 19h16'];
const ICON_TRASH = ['M4 7h16', 'M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2', 'M18 7l-.8 12a2 2 0 0 1-2 1.9H8.8a2 2 0 0 1-2-1.9L6 7', 'M10 11.5v5', 'M14 11.5v5'];

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    toast('この端末に保存できませんでした', 'error');
  }
}

const dateFmt = new Intl.DateTimeFormat('ja-JP', {
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit',
});

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : dateFmt.format(d);
}

/* ============================================================
 * 状態
 * ========================================================== */

const state = {
  files: [],
  removed: new Set(readJSON(LS.removed, [])),
  selected: new Set(),
};

const visibleFiles = () => state.files.filter((f) => !state.removed.has(f.path));

/* ============================================================
 * 通知
 * ========================================================== */

function toast(message, kind = '', action = null) {
  const node = el('div', `toast ${kind}`.trim());
  const msg = el('span', 'msg');
  msg.textContent = message;
  node.appendChild(msg);

  if (action) {
    const btn = el('button', 'small');
    btn.type = 'button';
    btn.textContent = action.label;
    btn.addEventListener('click', () => {
      action.onClick();
      node.remove();
    });
    node.appendChild(btn);
  }

  const host = $('#toasts');
  if (!host) return node;
  host.appendChild(node);
  setTimeout(() => node.remove(), action ? 7000 : 3500);
  return node;
}

/* ============================================================
 * 描画
 * ========================================================== */

function render() {
  const list = $('#files');
  if (!list) return;

  const files = visibleFiles();

  // 一覧をいちばん先に描く。以降の付随要素が欠けていても、ここは残る。
  list.textContent = '';
  for (const file of files) list.appendChild(renderRow(file));

  renderEmptyState(files.length);

  // 消えたファイルの選択状態を掃除する
  const paths = new Set(files.map((f) => f.path));
  for (const p of [...state.selected]) if (!paths.has(p)) state.selected.delete(p);

  const bar = $('#bulk-bar');
  if (bar) bar.hidden = files.length === 0;

  const selectAll = $('#select-all');
  if (selectAll) {
    selectAll.checked = files.length > 0 && state.selected.size === files.length;
    selectAll.indeterminate = state.selected.size > 0 && state.selected.size < files.length;
  }

  const count = $('#sel-count');
  if (count) count.textContent = state.selected.size ? `${state.selected.size} 件選択中` : '';

  const delSelected = $('#btn-del-selected');
  if (delSelected) delSelected.disabled = state.selected.size === 0;
}

/**
 * 0 件のときの案内。削除して 0 件になった場合は、
 * 設定を開かなくてもその場で戻せるようにする。
 */
function renderEmptyState(visibleCount) {
  const box = $('#empty-state');
  if (!box) return;
  box.hidden = visibleCount > 0;
  if (visibleCount > 0) return;

  box.textContent = '';
  const hiddenCount = state.files.filter((f) => state.removed.has(f.path)).length;

  const msg = el('p', 'empty-msg');
  msg.textContent = hiddenCount
    ? `${hiddenCount} 件すべてを削除しています`
    : 'ファイルがありません';
  box.appendChild(msg);

  if (hiddenCount) {
    const restore = el('button', 'small');
    restore.type = 'button';
    restore.textContent = '元に戻す';
    restore.addEventListener('click', () => {
      state.removed = new Set();
      persistRemoved();
      render();
    });
    box.appendChild(restore);
  }
}

function renderRow(file) {
  const row = el('div', 'file');
  row.dataset.path = file.path;

  const bg = el('div', 'swipe-bg');
  bg.textContent = '削除';
  row.appendChild(bg);

  const inner = el('div', 'file-inner');
  row.appendChild(inner);

  const check = el('input', 'file-check');
  check.type = 'checkbox';
  check.checked = state.selected.has(file.path);
  check.setAttribute('aria-label', `${file.name} を選択`);
  check.addEventListener('change', () => {
    if (check.checked) state.selected.add(file.path);
    else state.selected.delete(file.path);
    render();
  });
  inner.appendChild(check);

  const main = el('div', 'file-main');
  const name = el('div', 'file-name');
  name.textContent = file.name;
  main.appendChild(name);
  const when = formatDate(file.uploadedAt);
  if (when) {
    const date = el('div', 'file-date');
    date.textContent = when;
    main.appendChild(date);
  }
  inner.appendChild(main);

  const actions = el('div', 'file-actions');

  // 同一サーバのファイルなので、素のリンクで落とせる（JS も fetch も挟まない）
  const link = el('a', 'dl-btn');
  link.href = file.downloadUrl;
  link.setAttribute('download', file.name);
  link.title = `${file.name} をダウンロード`;
  link.setAttribute('aria-label', `${file.name} をダウンロード`);
  link.appendChild(icon(ICON_DOWNLOAD));
  actions.appendChild(link);

  const del = el('button', 'del-btn');
  del.type = 'button';
  del.title = `${file.name} を削除`;
  del.setAttribute('aria-label', `${file.name} を削除`);
  del.appendChild(icon(ICON_TRASH));
  del.addEventListener('click', () => removeFiles([file.path]));
  actions.appendChild(del);

  inner.appendChild(actions);

  attachSwipe(row, inner, file);
  return row;
}

/* ============================================================
 * スワイプで削除
 * ========================================================== */

function attachSwipe(row, inner, file) {
  let startX = 0;
  let startY = 0;
  let dx = 0;
  let active = false;
  let decided = false;

  row.addEventListener('touchstart', (ev) => {
    if (ev.touches.length !== 1 || ev.target.closest('button, a, input, label')) return;
    startX = ev.touches[0].clientX;
    startY = ev.touches[0].clientY;
    dx = 0;
    active = true;
    decided = false;
  }, { passive: true });

  row.addEventListener('touchmove', (ev) => {
    if (!active) return;
    const x = ev.touches[0].clientX - startX;
    const y = ev.touches[0].clientY - startY;

    if (!decided) {
      if (Math.abs(x) < 10 && Math.abs(y) < 10) return;
      if (Math.abs(y) > Math.abs(x)) { active = false; return; }   // 縦スクロール優先
      decided = true;
      row.classList.add('swiping');
    }

    dx = Math.min(0, x);
    inner.style.transform = `translateX(${dx}px)`;
  }, { passive: true });

  const finish = () => {
    if (!active) return;
    active = false;
    row.classList.remove('swiping');
    inner.style.transform = '';
    if (dx < -90) removeFiles([file.path]);
    dx = 0;
  };

  row.addEventListener('touchend', finish);
  row.addEventListener('touchcancel', finish);
}

/* ============================================================
 * 削除（この端末で非表示にするだけ）
 * ========================================================== */

function removeFiles(paths) {
  const added = paths.filter((p) => !state.removed.has(p));
  if (!added.length) return;

  for (const p of added) {
    state.removed.add(p);
    state.selected.delete(p);
  }
  persistRemoved();
  render();

  toast(`${added.length} 件を削除しました`, '', {
    label: '元に戻す',
    onClick: () => {
      for (const p of added) state.removed.delete(p);
      persistRemoved();
      render();
    },
  });
}

function persistRemoved() {
  writeJSON(LS.removed, [...state.removed]);
}

/* ============================================================
 * 読み込み
 * ========================================================== */

async function loadFiles() {
  const status = $('#load-status');
  let data;
  try {
    const res = await fetch(`${FILES_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    data = await res.json();
  } catch {
    state.files = [];
    status.classList.add('error');
    status.textContent = '一覧を読み込めませんでした';
    render();
    return;
  }

  const rows = Array.isArray(data) ? data : (data.files || []);
  state.files = rows
    .filter((row) => row && row.path)
    .map((row) => ({
      name: row.name || String(row.path).split('/').pop(),
      path: row.path,
      uploadedAt: row.uploadedAt || row.addedAt || null,
      downloadUrl: `./${String(row.path).replace(/^\.?\//, '')}`,
    }));

  status.classList.remove('error');
  status.textContent = '';
  render();
}

/** 設定画面に出す「取得元」を data/sync.json から組み立てる */
async function loadSources() {
  try {
    const res = await fetch(`${SOURCES_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const lines = [];
    for (const source of data.sources || []) {
      for (const spec of source.files || []) lines.push(`${source.repo}/${spec.from}`);
    }
    return lines.join('\n');
  } catch {
    return '';
  }
}

/* ============================================================
 * 起動
 * ========================================================== */

function wireUp() {
  on('#btn-settings', 'click', async () => {
    $('#sources').value = await loadSources() || '（取得元が読み込めませんでした）';
    $('#reset-state').textContent = state.removed.size
      ? `${state.removed.size} 件を非表示中`
      : '非表示のものはありません';
    $('#settings-dialog').showModal();
  });

  on('#select-all', 'change', (ev) => {
    state.selected = ev.target.checked ? new Set(visibleFiles().map((f) => f.path)) : new Set();
    render();
  });

  on('#btn-del-selected', 'click', () => {
    const paths = [...state.selected];
    if (!paths.length) return;
    if (!confirm(`選択した ${paths.length} 件を削除します。よろしいですか？`)) return;
    removeFiles(paths);
  });

  on('#btn-copy-sources', 'click', async () => {
    try {
      await navigator.clipboard.writeText($('#sources').value);
      toast('コピーしました');
    } catch {
      $('#sources').select();
      toast('コピーできませんでした。手動で選択してください', 'error');
    }
  });

  on('#btn-reset', 'click', () => {
    state.removed = new Set();
    persistRemoved();
    render();
    $('#reset-state').textContent = '非表示のものはありません';
    toast('すべて表示しました');
  });
}

function init() {
  // 旧版が残した設定を片付ける
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('ghdl.')) localStorage.removeItem(key);
    }
  } catch { /* noop */ }

  wireUp();
  render();
  loadFiles();
}

init();
