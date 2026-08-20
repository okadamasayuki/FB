/*
 * data/files.json に並んでいるファイルを一覧にして、1 クリックで保存できるようにする。
 *
 * ファイルの実体はこのサイト自身が配っている（files/ 配下）。
 * 外部のホストは一切参照しないので、このページが開ける環境なら必ず落とせる。
 *
 * 増やす・減らす・差し替えるのは、すべてリポジトリ側を直して行う。
 * 画面には操作を持たせない。
 */
'use strict';

const FILES_URL = './data/files.json';

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  return node;
};

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

function render(files) {
  const list = $('#files');
  if (!list) return;

  list.textContent = '';
  for (const file of files) list.appendChild(renderRow(file));

  const empty = $('#empty-state');
  if (empty) empty.hidden = files.length > 0;
}

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

function init() {
  // 旧版が端末に残した設定を片付ける
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('ghdl.') || key.startsWith('fb.')) localStorage.removeItem(key);
    }
  } catch { /* noop */ }

  loadFiles();
}

init();
