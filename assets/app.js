/*
 * data/files.json に並んでいるファイルを一覧にして、1 クリックで保存できるようにする。
 *
 * ファイルの実体はこのサイト自身が配っている（files/ 配下）。
 * 外部のホストは一切参照しないので、このページが開ける環境なら必ず落とせる。
 *
 * 画面から消す操作は持たない。減らすときはリポジトリ側から実体ごと消す。
 */
'use strict';

const FILES_URL = './data/files.json';
const SOURCES_URL = './data/sync.json';

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
 * 通知
 * ========================================================== */

function toast(message, kind = '') {
  const node = el('div', `toast ${kind}`.trim());
  const msg = el('span', 'msg');
  msg.textContent = message;
  node.appendChild(msg);

  const host = $('#toasts');
  if (!host) return;
  host.appendChild(node);
  setTimeout(() => node.remove(), 3500);
}

/* ============================================================
 * 描画
 * ========================================================== */

function render(files) {
  const list = $('#files');
  if (!list) return;

  list.textContent = '';
  for (const file of files) list.appendChild(renderRow(file));

  const empty = $('#empty-state');
  if (empty) empty.hidden = files.length > 0;
}

function renderRow(file) {
  const row = el('div', 'file');

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
  row.appendChild(main);

  // 同一サーバのファイルなので、素のリンクで落とせる（JS も fetch も挟まない）
  const link = el('a', 'dl-btn');
  link.href = file.downloadUrl;
  link.setAttribute('download', file.name);
  link.title = `${file.name} をダウンロード`;
  link.setAttribute('aria-label', `${file.name} をダウンロード`);
  link.appendChild(icon(ICON_DOWNLOAD));
  row.appendChild(link);

  return row;
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
    if (status) {
      status.classList.add('error');
      status.textContent = '一覧を読み込めませんでした';
    }
    render([]);
    return;
  }

  const rows = Array.isArray(data) ? data : (data.files || []);
  const files = rows
    .filter((row) => row && row.path)
    .map((row) => ({
      name: row.name || String(row.path).split('/').pop(),
      uploadedAt: row.uploadedAt || row.addedAt || null,
      downloadUrl: `./${String(row.path).replace(/^\.?\//, '')}`,
    }));

  if (status) {
    status.classList.remove('error');
    status.textContent = '';
  }
  render(files);
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
    const box = $('#sources');
    if (box) box.value = await loadSources() || '（取得元が読み込めませんでした）';
    $('#settings-dialog')?.showModal();
  });

  on('#btn-copy-sources', 'click', async () => {
    const box = $('#sources');
    if (!box) return;
    try {
      await navigator.clipboard.writeText(box.value);
      toast('コピーしました');
    } catch {
      box.select();
      toast('コピーできませんでした。手動で選択してください', 'error');
    }
  });
}

function init() {
  // 旧版が端末に残した設定を片付ける
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('ghdl.') || key.startsWith('fb.')) localStorage.removeItem(key);
    }
  } catch { /* noop */ }

  wireUp();
  loadFiles();
}

init();
