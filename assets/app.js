/*
 * GitHub パス ダウンローダー
 *
 * 登録された「owner/repo/パス」を GitHub API で読んで一覧表示し、
 * ファイルを 1 クリック / まとめて ZIP でダウンロードする静的サイト。
 *
 * 登録の保存先は 2 つ:
 *   1. data/registry.json ... リポジトリにコミットされる共有の登録リスト（Claude が更新）
 *   2. localStorage       ... この端末だけの追加・削除
 */
'use strict';

const REGISTRY_URL = './data/registry.json';
const FILES_URL = './data/files.json';
const API_ROOT = 'https://api.github.com';
const STORE_ID = 'store:local';

const LS = {
  local: 'ghdl.local.v1',      // この端末で追加したエントリ
  removed: 'ghdl.removed.v1',  // 非表示にした registry.json 由来のエントリ ID
  token: 'ghdl.token.v1',
};

const MAX_DIR_REQUESTS = 60;   // サブフォルダ探索の上限（暴走よけ）
const MAX_FILES = 500;
const DL_CONCURRENCY = 4;

/* ============================================================
 * 小さいユーティリティ
 * ========================================================== */

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  return n;
};

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
    toast('この端末に保存できませんでした（ストレージ制限）', 'error');
  }
}

const dtFmt = new Intl.DateTimeFormat('ja-JP', {
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit',
});

function formatDate(iso) {
  if (!iso) return '日時不明';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '日時不明' : dtFmt.format(d);
}

function formatSize(bytes) {
  if (typeof bytes !== 'number' || bytes < 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function sanitizeFilename(name) {
  return (name || 'download').replace(/[\\/:*?"<>|]/g, '_').slice(0, 120) || 'download';
}

/* ============================================================
 * パスのパース
 *   受け付ける形:
 *     https://github.com/owner/repo/tree/main/docs
 *     https://github.com/owner/repo/blob/main/docs/a.pdf
 *     https://raw.githubusercontent.com/owner/repo/main/docs/a.pdf
 *     owner/repo
 *     owner/repo/docs/files
 *     owner/repo/docs#develop      ← # のうしろはブランチ
 * ========================================================== */
function parseTarget(input) {
  let raw = String(input || '').trim();
  if (!raw) throw new Error('パスを入力してください');

  let ref = null;
  const hash = raw.indexOf('#');
  if (hash >= 0) {
    ref = raw.slice(hash + 1).trim() || null;
    raw = raw.slice(0, hash).trim();
  }

  let segments;
  if (/^https?:\/\//i.test(raw)) {
    let url;
    try {
      url = new URL(raw);
    } catch {
      throw new Error('URL として読めませんでした');
    }
    const host = url.hostname.toLowerCase();
    const parts = url.pathname.split('/').filter(Boolean).map(decodeURIComponent);
    if (host === 'raw.githubusercontent.com') {
      // owner / repo / ref / path...
      if (parts.length < 3) throw new Error('raw の URL が短すぎます');
      return {
        owner: parts[0],
        repo: parts[1],
        ref: ref || parts[2],
        path: parts.slice(3).join('/'),
      };
    }
    if (host !== 'github.com' && host !== 'www.github.com') {
      throw new Error('github.com の URL を指定してください');
    }
    segments = parts;
  } else {
    segments = raw.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
  }

  if (segments.length < 2) {
    throw new Error('owner/repo の形式が必要です（例: octocat/Hello-World/docs）');
  }

  const owner = segments[0];
  const repo = segments[1].replace(/\.git$/i, '');
  let path = '';

  if (segments.length > 2) {
    const kind = segments[2];
    if ((kind === 'tree' || kind === 'blob') && segments.length >= 4) {
      ref = ref || segments[3];
      path = segments.slice(4).join('/');
    } else {
      path = segments.slice(2).join('/');
    }
  }

  return { owner, repo, ref: ref || null, path: path.replace(/^\/+|\/+$/g, '') };
}

function targetKey(t) {
  return `${t.owner}/${t.repo}@${t.ref || 'default'}:${t.path}`;
}

function githubUrl(entry, ref) {
  const t = entry.target;
  const base = `https://github.com/${t.owner}/${t.repo}`;
  if (!t.path) return base;
  return `${base}/tree/${encodeURIComponent(ref || t.ref || 'HEAD')}/${t.path}`;
}

/* ============================================================
 * GitHub API
 * ========================================================== */

function getToken() {
  try {
    return localStorage.getItem(LS.token) || '';
  } catch {
    return '';
  }
}

let rateRemaining = null;

async function ghFetch(url, accept = 'application/vnd.github+json') {
  const headers = { Accept: accept, 'X-GitHub-Api-Version': '2022-11-28' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(url, { headers });
  } catch {
    throw new Error('ネットワークに繋がりませんでした');
  }

  const remaining = res.headers.get('x-ratelimit-remaining');
  if (remaining !== null) {
    rateRemaining = Number(remaining);
    renderRateInfo();
  }

  if (res.ok) return res;

  if (res.status === 401) throw new Error('トークンが無効です（設定を確認してください）');
  if (res.status === 404) {
    throw new Error(getToken()
      ? 'パスが見つかりません（リポジトリ名・ブランチ・パスを確認してください）'
      : 'パスが見つかりません。非公開リポジトリなら設定でトークンを登録してください');
  }
  if (res.status === 403 || res.status === 429) {
    if (rateRemaining === 0) {
      throw new Error('GitHub API の回数制限に達しました。設定でトークンを登録すると上限が上がります');
    }
    throw new Error('GitHub にアクセスを拒否されました（403）');
  }
  throw new Error(`GitHub API エラー（${res.status}）`);
}

const defaultBranchCache = new Map();

async function resolveRef(target) {
  if (target.ref) return target.ref;
  const key = `${target.owner}/${target.repo}`;
  if (defaultBranchCache.has(key)) return defaultBranchCache.get(key);
  const res = await ghFetch(`${API_ROOT}/repos/${encodeURIComponent(target.owner)}/${encodeURIComponent(target.repo)}`);
  const info = await res.json();
  const branch = info.default_branch || 'main';
  defaultBranchCache.set(key, branch);
  return branch;
}

function contentsUrl(target, path, ref) {
  const segs = String(path || '').split('/').filter(Boolean).map(encodeURIComponent).join('/');
  const base = `${API_ROOT}/repos/${encodeURIComponent(target.owner)}/${encodeURIComponent(target.repo)}/contents/${segs}`;
  return `${base}?ref=${encodeURIComponent(ref)}`;
}

/**
 * 登録パス配下のファイルを列挙する。
 * パスがファイルを直接指している場合は、その 1 件だけを返す。
 */
async function listFiles(entry) {
  // ファイル置き場はマニフェストがそのまま一覧になる
  if (entry.source === 'store') {
    return { ref: null, files: entry.storeFiles, truncated: false };
  }

  const target = entry.target;
  const ref = await resolveRef(target);

  const res = await ghFetch(contentsUrl(target, target.path, ref));
  const body = await res.json();

  const rootPrefix = target.path ? `${target.path}/` : '';
  const toFile = (item) => ({
    name: item.name,
    path: item.path,
    relPath: item.path.startsWith(rootPrefix) ? item.path.slice(rootPrefix.length) : item.name,
    size: item.size,
    sha: item.sha,
    downloadUrl: item.download_url || null,
  });

  if (!Array.isArray(body)) {
    // 単一ファイルを登録したケース
    if (body.type !== 'file') throw new Error('ファイルでもフォルダでもないパスです');
    return { ref, files: [{ ...toFile(body), relPath: body.name }], truncated: false };
  }

  const files = [];
  const queue = [];
  let truncated = false;

  const consume = (items) => {
    for (const item of items) {
      if (item.type === 'file') {
        if (files.length >= MAX_FILES) { truncated = true; continue; }
        files.push(toFile(item));
      } else if (item.type === 'dir' && entry.recursive) {
        queue.push(item.path);
      }
    }
  };

  consume(body);

  let requests = 0;
  while (queue.length) {
    if (requests >= MAX_DIR_REQUESTS || files.length >= MAX_FILES) { truncated = true; break; }
    const dir = queue.shift();
    requests++;
    const sub = await ghFetch(contentsUrl(target, dir, ref));
    const subBody = await sub.json();
    if (Array.isArray(subBody)) consume(subBody);
  }

  files.sort((a, b) => a.relPath.localeCompare(b.relPath, 'ja'));
  return { ref, files, truncated };
}

// 社内プロキシなどで raw.githubusercontent.com が塞がれている環境では、
// 一度失敗したら以降は毎回待たされないように API 経由へ切り替える。
let rawUnavailable = false;

function base64ToBytes(base64) {
  const binary = atob(String(base64).replace(/\s/g, ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/**
 * API 経由でファイルの中身を取る。
 * contents API は 1MB までなら base64 を JSON に直接入れて返すので、
 * 別ホストへのリダイレクトが起きない＝一覧が取れる環境なら必ず取れる。
 * 1MB を超えると content が空になるので、その場合だけ Blobs API を使う。
 */
async function fetchViaApi(entry, file) {
  const ref = state.files.get(entry.id)?.ref || entry.target.ref || 'HEAD';
  const res = await ghFetch(contentsUrl(entry.target, file.path, ref));
  const body = await res.json();
  if (body.encoding === 'base64' && body.content) return base64ToBytes(body.content);

  const sha = body.sha || file.sha;
  if (!sha) throw new Error('ファイルの中身を取得できませんでした');
  const { owner, repo } = entry.target;
  const blobRes = await ghFetch(
    `${API_ROOT}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/git/blobs/${sha}`,
  );
  const blob = await blobRes.json();
  if (blob.encoding !== 'base64' || !blob.content) {
    throw new Error('ファイルの中身を取得できませんでした');
  }
  return base64ToBytes(blob.content);
}

async function fetchFileBytes(entry, file) {
  // このサイト自身が配っているファイル。別ホストを一切経由しない。
  if (file.sameOrigin) {
    let res;
    try {
      res = await fetch(file.downloadUrl);
    } catch {
      throw new Error('ネットワークに繋がりませんでした');
    }
    if (!res.ok) throw new Error(`ファイルが見つかりません（${res.status}）`);
    return new Uint8Array(await res.arrayBuffer());
  }

  // まず raw を試す（速く、API の回数制限も使わない）。
  // 落ちたら理由を問わず API 経由へ回すので、ここで諦めない。
  if (file.downloadUrl && !rawUnavailable) {
    try {
      const res = await fetch(file.downloadUrl);
      if (res.ok) return new Uint8Array(await res.arrayBuffer());
    } catch {
      rawUnavailable = true;
    }
  }
  return fetchViaApi(entry, file);
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = el('a');
  a.href = url;
  a.download = sanitizeFilename(filename);
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/* ============================================================
 * ZIP 生成（無圧縮 / store のみ・依存ライブラリなし）
 * ========================================================== */

let crcTable = null;

function crc32(bytes) {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      crcTable[i] = c >>> 0;
    }
  }
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) {
    crc = crcTable[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function dosDateTime(d) {
  const year = Math.max(1980, d.getFullYear());
  return {
    time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    date: ((year - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
  };
}

function buildZip(files) {
  const enc = new TextEncoder();
  const { time, date } = dosDateTime(new Date());
  const parts = [];
  const central = [];
  let offset = 0;

  for (const f of files) {
    const nameBytes = enc.encode(f.name);
    const data = f.data;
    const crc = crc32(data);

    const local = new Uint8Array(30 + nameBytes.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);       // version needed
    lv.setUint16(6, 0x0800, true);   // flags: ファイル名 UTF-8
    lv.setUint16(8, 0, true);        // method: store
    lv.setUint16(10, time, true);
    lv.setUint16(12, date, true);
    lv.setUint32(14, crc, true);
    lv.setUint32(18, data.length, true);
    lv.setUint32(22, data.length, true);
    lv.setUint16(26, nameBytes.length, true);
    local.set(nameBytes, 30);
    parts.push(local, data);

    const dir = new Uint8Array(46 + nameBytes.length);
    const dv = new DataView(dir.buffer);
    dv.setUint32(0, 0x02014b50, true);
    dv.setUint16(4, 20, true);       // version made by
    dv.setUint16(6, 20, true);       // version needed
    dv.setUint16(8, 0x0800, true);
    dv.setUint16(10, 0, true);
    dv.setUint16(12, time, true);
    dv.setUint16(14, date, true);
    dv.setUint32(16, crc, true);
    dv.setUint32(20, data.length, true);
    dv.setUint32(24, data.length, true);
    dv.setUint16(28, nameBytes.length, true);
    dv.setUint32(42, offset, true);  // ローカルヘッダの位置
    dir.set(nameBytes, 46);
    central.push(dir);

    offset += local.length + data.length;
  }

  const centralSize = central.reduce((sum, c) => sum + c.length, 0);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, central.length, true);
  ev.setUint16(10, central.length, true);
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, offset, true);

  return new Blob([...parts, ...central, end], { type: 'application/zip' });
}

function uniqueZipNames(files) {
  const seen = new Map();
  return files.map((f) => {
    let name = f.relPath || f.name;
    if (seen.has(name)) {
      const n = seen.get(name) + 1;
      seen.set(name, n);
      const dot = name.lastIndexOf('.');
      name = dot > 0 ? `${name.slice(0, dot)} (${n})${name.slice(dot)}` : `${name} (${n})`;
    } else {
      seen.set(name, 0);
    }
    return { ...f, zipName: name };
  });
}

/* ============================================================
 * 画面の状態
 * ========================================================== */

const state = {
  store: null,               // files.json 由来のファイル置き場（1 エントリぶん）
  seed: [],
  local: [],
  removed: new Set(readJSON(LS.removed, [])),
  files: new Map(),          // entryId -> { status, ref, files, truncated, error }
  open: new Set(),
  selected: new Set(),       // 一括操作用に選択されたエントリ ID
  fileSelected: new Map(),   // entryId -> Set(relPath)
  busy: false,
};

function normalizeEntry(rec, source) {
  const target = parseTarget(rec.path ?? rec.url ?? `${rec.owner || ''}/${rec.repo || ''}/${rec.dir || ''}`);
  if (rec.ref) target.ref = rec.ref;
  const key = targetKey(target);
  return {
    id: rec.id || `${source}:${key}`,
    label: (rec.label || '').trim() || (target.path ? target.path.split('/').pop() : `${target.owner}/${target.repo}`),
    note: rec.note || '',
    addedAt: rec.addedAt || rec.added_at || null,
    recursive: Boolean(rec.recursive),
    source,
    target,
  };
}

function visibleEntries() {
  const list = [];
  const seenKeys = new Set();
  for (const e of state.local) {
    list.push(e);
    seenKeys.add(targetKey(e.target));
  }
  for (const e of state.seed) {
    if (state.removed.has(e.id)) continue;
    if (seenKeys.has(targetKey(e.target))) continue; // 端末側の登録を優先
    list.push(e);
  }
  list.sort((a, b) => String(b.addedAt || '').localeCompare(String(a.addedAt || '')));

  // ファイル置き場はいちばん確実に落とせるので常に先頭に置く
  if (state.store && !state.removed.has(STORE_ID)) list.unshift(state.store);
  return list;
}

function entryById(id) {
  return visibleEntries().find((e) => e.id === id) || null;
}

/* ============================================================
 * 通知・進捗
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

  $('#toasts').appendChild(node);
  setTimeout(() => node.remove(), action ? 7000 : 4000);
  return node;
}

function showProgress(text, done, total) {
  const box = $('#progress');
  box.hidden = false;
  $('#progress-text').textContent = text;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  $('#progress-bar').style.width = `${pct}%`;
}

function hideProgress() {
  $('#progress').hidden = true;
  $('#progress-bar').style.width = '0';
}

function renderRateInfo() {
  const node = $('#rate-info');
  if (rateRemaining === null) { node.textContent = ''; return; }
  node.textContent = `API 残り ${rateRemaining} 回${getToken() ? '' : '（未認証）'}`;
}

/* ============================================================
 * 描画
 * ========================================================== */

function render() {
  const container = $('#entries');
  const entries = visibleEntries();

  container.textContent = '';
  for (const entry of entries) container.appendChild(renderEntry(entry));

  $('#empty-state').hidden = entries.length > 0;
  $('#bulk-bar').hidden = entries.length === 0;

  // 消えたエントリの選択状態を掃除する
  const ids = new Set(entries.map((e) => e.id));
  for (const id of [...state.selected]) if (!ids.has(id)) state.selected.delete(id);

  const selectAll = $('#select-all');
  selectAll.checked = entries.length > 0 && state.selected.size === entries.length;
  selectAll.indeterminate = state.selected.size > 0 && state.selected.size < entries.length;
  $('#sel-count').textContent = `${state.selected.size} 件選択中 / 全 ${entries.length} 件`;

  const hasSelection = state.selected.size > 0;
  $('#btn-zip-selected').disabled = !hasSelection;
  $('#btn-del-selected').disabled = !hasSelection;
}

function renderEntry(entry) {
  const card = el('article', 'entry');
  card.dataset.id = entry.id;
  if (state.open.has(entry.id)) card.classList.add('open');

  const bg = el('div', 'swipe-bg');
  bg.textContent = '削除';
  card.appendChild(bg);

  const inner = el('div', 'entry-inner');
  card.appendChild(inner);

  /* --- 見出し --- */
  const head = el('div', 'entry-head');

  const check = el('input', 'entry-check');
  check.type = 'checkbox';
  check.checked = state.selected.has(entry.id);
  check.setAttribute('aria-label', `${entry.label} を選択`);
  check.addEventListener('change', () => {
    if (check.checked) state.selected.add(entry.id);
    else state.selected.delete(entry.id);
    render();
  });
  head.appendChild(check);

  const title = el('button', 'entry-title');
  title.type = 'button';
  const label = el('span', 'label');
  label.textContent = entry.label;
  const repo = el('span', 'repo');
  repo.textContent = entry.target
    ? `${entry.target.owner}/${entry.target.repo}${entry.target.path ? ` / ${entry.target.path}` : ''}`
    : 'このサイトが配っているファイル';
  title.append(label, repo);
  title.addEventListener('click', () => toggleEntry(entry));
  head.appendChild(title);

  const chev = el('span', 'chev');
  chev.textContent = '▸';
  head.appendChild(chev);
  inner.appendChild(head);

  /* --- メタ情報 --- */
  const meta = el('div', 'entry-meta');
  const loaded = state.files.get(entry.id);

  if (entry.target) {
    const branch = el('span', 'badge');
    branch.textContent = loaded?.ref || entry.target.ref || 'デフォルトブランチ';
    meta.appendChild(branch);
  }

  const added = el('span');
  added.textContent = entry.source === 'store'
    ? `最終更新 ${formatDate(entry.addedAt)}`
    : `登録 ${formatDate(entry.addedAt)}`;
  meta.appendChild(added);

  if (loaded?.status === 'ready') {
    const count = el('span');
    count.textContent = `${loaded.files.length} ファイル`;
    meta.appendChild(count);
  }

  if (entry.recursive) {
    const rec = el('span', 'badge');
    rec.textContent = 'サブフォルダ込み';
    meta.appendChild(rec);
  }

  const SOURCE_LABEL = { store: 'このサイト内', local: 'この端末', seed: '共有リスト' };
  const src = el('span', 'badge' + (entry.source === 'seed' ? '' : ' local'));
  src.textContent = SOURCE_LABEL[entry.source] || '共有リスト';
  meta.appendChild(src);

  if (entry.note) {
    const note = el('span');
    note.textContent = entry.note;
    meta.appendChild(note);
  }
  inner.appendChild(meta);

  /* --- 操作ボタン --- */
  const actions = el('div', 'entry-actions');

  // ファイルが 1 つだけなら ZIP にせず、そのまま落とす。
  // 件数が分かる前は素直に「ダウンロード」と出しておく。
  const count = loaded?.status === 'ready' ? loaded.files.length : null;
  const allBtn = el('button', 'small primary');
  allBtn.type = 'button';
  allBtn.textContent = count > 1 ? '⬇ まとめてZIP保存' : '⬇ ダウンロード';
  allBtn.addEventListener('click', () => downloadEntryAll(entry));
  actions.appendChild(allBtn);

  const refreshBtn = el('button', 'small');
  refreshBtn.type = 'button';
  refreshBtn.textContent = '再取得';
  refreshBtn.addEventListener('click', () => {
    state.files.delete(entry.id);
    state.open.add(entry.id);
    render();
    loadEntryFiles(entry);
  });
  actions.appendChild(refreshBtn);

  if (entry.target) {
    const link = el('a', 'small');
    link.href = githubUrl(entry, loaded?.ref);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'GitHubで開く';
    actions.appendChild(link);
  }

  const delBtn = el('button', 'small danger');
  delBtn.type = 'button';
  delBtn.textContent = '削除';
  delBtn.addEventListener('click', () => deleteEntries([entry.id]));
  actions.appendChild(delBtn);

  inner.appendChild(actions);

  /* --- ファイル一覧 --- */
  inner.appendChild(renderFiles(entry));

  attachSwipe(card, inner, entry);
  return card;
}

function renderFiles(entry) {
  const wrap = el('div', 'files');
  const loaded = state.files.get(entry.id);

  if (!loaded || loaded.status === 'loading') {
    const state_ = el('div', 'state');
    state_.textContent = 'ファイルを読み込み中…';
    wrap.appendChild(state_);
    return wrap;
  }

  if (loaded.status === 'error') {
    const err = el('div', 'state error');
    err.textContent = loaded.error;
    wrap.appendChild(err);
    return wrap;
  }

  if (!loaded.files.length) {
    const none = el('div', 'state');
    none.textContent = 'このパスにファイルがありません' + (entry.recursive ? '' : '（サブフォルダは対象外です）');
    wrap.appendChild(none);
    return wrap;
  }

  const selected = state.fileSelected.get(entry.id) || new Set();

  const bar = el('div', 'files-bar');
  const allLabel = el('label', 'check compact');
  const allCheck = el('input');
  allCheck.type = 'checkbox';
  allCheck.checked = selected.size === loaded.files.length;
  allCheck.indeterminate = selected.size > 0 && selected.size < loaded.files.length;
  allCheck.addEventListener('change', () => {
    const next = new Set(allCheck.checked ? loaded.files.map((f) => f.relPath) : []);
    state.fileSelected.set(entry.id, next);
    render();
  });
  const allText = el('span');
  allText.textContent = 'ファイルを全選択';
  allLabel.append(allCheck, allText);
  bar.appendChild(allLabel);

  const zipSel = el('button', 'small');
  zipSel.type = 'button';
  zipSel.textContent = selected.size === 1
    ? '選択した 1 件をダウンロード'
    : `選択した ${selected.size} 件をZIP`;
  zipSel.disabled = selected.size === 0;
  zipSel.addEventListener('click', () => {
    const picked = loaded.files.filter((f) => selected.has(f.relPath));
    downloadFiles(entry, picked);
  });
  bar.appendChild(zipSel);

  if (loaded.truncated) {
    const warn = el('span', 'hint');
    warn.textContent = `※ 表示は ${loaded.files.length} 件までです`;
    bar.appendChild(warn);
  }

  wrap.appendChild(bar);

  const list = el('div', 'file-list');
  for (const file of loaded.files) {
    const row = el('div', 'file');

    const check = el('input', 'file-check');
    check.type = 'checkbox';
    check.checked = selected.has(file.relPath);
    check.setAttribute('aria-label', `${file.name} を選択`);
    check.addEventListener('change', () => {
      const set = state.fileSelected.get(entry.id) || new Set();
      if (check.checked) set.add(file.relPath);
      else set.delete(file.relPath);
      state.fileSelected.set(entry.id, set);
      render();
    });
    row.appendChild(check);

    const main = el('div', 'file-main');
    const name = el('div', 'file-name');
    name.textContent = file.name;
    const sub = el('div', 'file-sub');
    const when = file.uploadedAt || entry.addedAt;
    const bits = [
      formatSize(file.size),
      `${file.uploadedAt ? 'アップロード' : '登録'} ${formatDate(when)}`,
    ];
    if (file.note) bits.push(file.note);
    if (file.relPath !== file.name) bits.push(file.relPath);
    sub.textContent = bits.filter(Boolean).join(' ・ ');
    main.append(name, sub);
    row.appendChild(main);

    // 同一サーバのファイルは素の <a download> が最も確実（JS も fetch も挟まない）
    if (file.sameOrigin) {
      const link = el('a', 'dl-btn');
      link.href = file.downloadUrl;
      link.setAttribute('download', file.name);
      link.textContent = '⬇ ダウンロード';
      link.title = `${file.name} をダウンロード`;
      row.appendChild(link);
      list.appendChild(row);
      continue;
    }

    const dl = el('button', 'dl-btn');
    dl.type = 'button';
    dl.title = `${file.name} をダウンロード`;
    dl.setAttribute('aria-label', `${file.name} をダウンロード`);
    dl.textContent = '⬇ ダウンロード';
    dl.addEventListener('click', async () => {
      dl.disabled = true;
      dl.textContent = '取得中…';
      try {
        const bytes = await fetchFileBytes(entry, file);
        saveBlob(new Blob([bytes]), file.name);
        dl.classList.add('done');
        dl.textContent = '✓ 保存しました';
        setTimeout(() => { dl.classList.remove('done'); dl.textContent = '⬇ ダウンロード'; }, 2500);
      } catch (err) {
        dl.textContent = '⬇ ダウンロード';
        toast(`${file.name}: ${err.message}`, 'error', file.downloadUrl ? {
          label: '直接開く',
          onClick: () => window.open(file.downloadUrl, '_blank', 'noopener'),
        } : null);
      } finally {
        dl.disabled = false;
      }
    });
    row.appendChild(dl);

    list.appendChild(row);
  }
  wrap.appendChild(list);
  return wrap;
}

/* ============================================================
 * スワイプで削除
 * ========================================================== */

function attachSwipe(card, inner, entry) {
  let startX = 0;
  let startY = 0;
  let dx = 0;
  let active = false;
  let decided = false;

  const isControl = (target) => target.closest('button, a, input, label, summary');

  card.addEventListener('touchstart', (ev) => {
    if (ev.touches.length !== 1 || isControl(ev.target)) return;
    startX = ev.touches[0].clientX;
    startY = ev.touches[0].clientY;
    dx = 0;
    active = true;
    decided = false;
  }, { passive: true });

  card.addEventListener('touchmove', (ev) => {
    if (!active) return;
    const x = ev.touches[0].clientX - startX;
    const y = ev.touches[0].clientY - startY;

    if (!decided) {
      if (Math.abs(x) < 10 && Math.abs(y) < 10) return;
      // 縦スクロールが優勢ならスワイプ扱いにしない
      if (Math.abs(y) > Math.abs(x)) { active = false; return; }
      decided = true;
      card.classList.add('swiping');
    }

    dx = Math.min(0, x);
    inner.style.transform = `translateX(${dx}px)`;
  }, { passive: true });

  const finish = () => {
    if (!active) return;
    active = false;
    card.classList.remove('swiping');
    inner.style.transform = '';
    if (dx < -90) deleteEntries([entry.id]);
    dx = 0;
  };

  card.addEventListener('touchend', finish);
  card.addEventListener('touchcancel', finish);
}

/* ============================================================
 * 読み込み・登録・削除
 * ========================================================== */

/**
 * data/files.json を読んで「ファイル置き場」エントリを組み立てる。
 * ファイルはこのサイト自身が配っているので、GitHub の API も raw も使わない。
 */
async function loadStore() {
  let data;
  try {
    const res = await fetch(`${FILES_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    data = await res.json();
  } catch {
    state.store = null;   // マニフェストが無ければ置き場は出さない
    return;
  }

  const rows = Array.isArray(data) ? data : (data.files || []);
  const files = rows
    .filter((row) => row && row.path)
    .map((row) => {
      const name = row.name || String(row.path).split('/').pop();
      return {
        name,
        path: row.path,
        relPath: name,
        size: typeof row.size === 'number' ? row.size : null,
        uploadedAt: row.uploadedAt || row.addedAt || null,
        note: row.note || '',
        downloadUrl: `./${String(row.path).replace(/^\.?\//, '')}`,
        sameOrigin: true,
      };
    });

  if (!files.length) {
    state.store = null;
    return;
  }

  const newest = files
    .map((f) => f.uploadedAt)
    .filter(Boolean)
    .sort()
    .pop() || null;

  state.store = {
    id: STORE_ID,
    label: data.label || 'ファイル置き場',
    note: data.note || 'このサイトから直接ダウンロードできます',
    addedAt: newest,
    recursive: false,
    source: 'store',
    target: null,
    storeFiles: files,
  };
  state.files.set(STORE_ID, { status: 'ready', ref: null, files, truncated: false });
}

async function loadRegistry() {
  const status = $('#registry-status');
  try {
    const res = await fetch(`${REGISTRY_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const rows = Array.isArray(data) ? data : (data.entries || []);
    const parsed = [];
    for (const row of rows) {
      try {
        parsed.push(normalizeEntry(row, 'seed'));
      } catch (err) {
        console.warn('registry.json の項目を読み飛ばしました', row, err);
      }
    }
    state.seed = parsed;
    status.classList.remove('error');
    status.textContent = parsed.length
      ? `共有リスト（data/registry.json）から ${parsed.length} 件を読み込みました`
      : '共有リスト（data/registry.json）はまだ空です';
  } catch {
    state.seed = [];
    status.classList.add('error');
    status.textContent = 'data/registry.json を読み込めませんでした（この端末の登録のみ表示しています）';
  }
  render();
}

function loadLocal() {
  const rows = readJSON(LS.local, []);
  const parsed = [];
  for (const row of rows) {
    try {
      parsed.push(normalizeEntry(row, 'local'));
    } catch (err) {
      console.warn('端末の登録を読み飛ばしました', row, err);
    }
  }
  state.local = parsed;
}

function persistLocal() {
  writeJSON(LS.local, state.local.map((e) => ({
    id: e.id,
    label: e.label,
    path: `${e.target.owner}/${e.target.repo}${e.target.path ? `/${e.target.path}` : ''}`,
    ref: e.target.ref,
    recursive: e.recursive,
    addedAt: e.addedAt,
    note: e.note,
  })));
}

function persistRemoved() {
  writeJSON(LS.removed, [...state.removed]);
}

async function toggleEntry(entry) {
  if (state.open.has(entry.id)) {
    state.open.delete(entry.id);
    render();
    return;
  }
  state.open.add(entry.id);
  render();
  if (!state.files.has(entry.id)) await loadEntryFiles(entry);
}

async function loadEntryFiles(entry) {
  state.files.set(entry.id, { status: 'loading' });
  render();
  try {
    const result = await listFiles(entry);
    state.files.set(entry.id, { status: 'ready', ...result });
  } catch (err) {
    state.files.set(entry.id, { status: 'error', error: err.message, files: [] });
  }
  render();
}

async function ensureFiles(entry) {
  const cached = state.files.get(entry.id);
  if (cached?.status === 'ready') return cached;
  await loadEntryFiles(entry);
  const loaded = state.files.get(entry.id);
  if (loaded?.status !== 'ready') throw new Error(loaded?.error || '読み込みに失敗しました');
  return loaded;
}

function addEntry({ path, label, recursive }) {
  const target = parseTarget(path);
  const entry = {
    id: `local:${targetKey(target)}`,
    label: (label || '').trim() || (target.path ? target.path.split('/').pop() : `${target.owner}/${target.repo}`),
    note: '',
    addedAt: new Date().toISOString(),
    recursive: Boolean(recursive),
    source: 'local',
    target,
  };

  const key = targetKey(target);
  if (state.local.some((e) => targetKey(e.target) === key)) {
    throw new Error('このパスはすでに登録されています');
  }

  // 共有リストで消していたものを再登録した場合は、非表示を解除する
  for (const seed of state.seed) {
    if (targetKey(seed.target) === key) state.removed.delete(seed.id);
  }
  persistRemoved();

  state.local.unshift(entry);
  persistLocal();
  state.open.add(entry.id);
  render();
  loadEntryFiles(entry);
  return entry;
}

function deleteEntries(ids) {
  const undo = { local: [], removed: [] };

  for (const id of ids) {
    const idx = state.local.findIndex((e) => e.id === id);
    if (idx >= 0) {
      undo.local.push({ index: idx, entry: state.local[idx] });
      state.local.splice(idx, 1);
      continue;
    }
    if (!state.removed.has(id)) {
      state.removed.add(id);
      undo.removed.push(id);
    }
  }

  if (!undo.local.length && !undo.removed.length) return;

  for (const id of ids) {
    state.selected.delete(id);
    state.open.delete(id);
    state.files.delete(id);
    state.fileSelected.delete(id);
  }

  persistLocal();
  persistRemoved();
  render();

  const count = undo.local.length + undo.removed.length;
  toast(`${count} 件を削除しました`, '', {
    label: '元に戻す',
    onClick: () => {
      // 削除したのと逆順に戻すと、元の並びが復元できる
      for (const { index, entry } of [...undo.local].reverse()) state.local.splice(index, 0, entry);
      for (const id of undo.removed) state.removed.delete(id);
      persistLocal();
      persistRemoved();
      render();
    },
  });
}

/* ============================================================
 * ダウンロード
 * ========================================================== */

async function withBusy(fn) {
  if (state.busy) {
    toast('いま別のダウンロードを処理中です', 'error');
    return;
  }
  state.busy = true;
  try {
    await fn();
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    state.busy = false;
    hideProgress();
  }
}

/** 並列数を絞ってファイルを取得する */
async function fetchAll(jobs, onProgress) {
  const results = new Array(jobs.length);
  let done = 0;
  let cursor = 0;
  const errors = [];

  const worker = async () => {
    while (cursor < jobs.length) {
      const i = cursor++;
      const job = jobs[i];
      try {
        results[i] = { name: job.zipName, data: await fetchFileBytes(job.entry, job.file) };
      } catch (err) {
        errors.push(`${job.file.name}: ${err.message}`);
        results[i] = null;
      }
      done++;
      onProgress(done, jobs.length, job.file.name);
    }
  };

  await Promise.all(Array.from({ length: Math.min(DL_CONCURRENCY, jobs.length) }, worker));
  return { files: results.filter(Boolean), errors };
}

/** 1 ファイルをそのまま保存する（busy ガードは呼び出し側で） */
async function saveSingleFile(entry, file) {
  showProgress(`${file.name} を取得中…`, 0, 1);
  const bytes = await fetchFileBytes(entry, file);
  showProgress(`${file.name} を取得中…`, 1, 1);
  saveBlob(new Blob([bytes]), file.name);
  toast(`${file.name} を保存しました`);
}

/** 取得して ZIP にまとめ、保存する（busy ガードは呼び出し側で） */
async function zipAndSave(entry, files, zipLabel) {
  const jobs = uniqueZipNames(files).map((f) => ({ entry, file: f, zipName: f.zipName }));
  showProgress(`0 / ${jobs.length} 取得中…`, 0, jobs.length);
  const { files: fetched, errors } = await fetchAll(jobs, (done, total, name) => {
    showProgress(`${done} / ${total} 取得中… ${name}`, done, total);
  });

  if (!fetched.length) throw new Error(errors[0] || 'ダウンロードに失敗しました');

  showProgress('ZIP を作成中…', 1, 1);
  const stamp = new Date().toISOString().slice(0, 10);
  saveBlob(buildZip(fetched), `${sanitizeFilename(zipLabel || entry.label)}_${stamp}.zip`);

  toast(errors.length
    ? `${fetched.length} 件をZIPにしました（${errors.length} 件は失敗）`
    : `${fetched.length} 件をZIPにしました`, errors.length ? 'error' : '');
}

/** 1 件ならそのまま、複数なら ZIP でまとめて保存する */
async function downloadFiles(entry, files, zipLabel) {
  if (!files.length) {
    toast('ダウンロードするファイルがありません', 'error');
    return;
  }
  await withBusy(() => (files.length === 1
    ? saveSingleFile(entry, files[0])
    : zipAndSave(entry, files, zipLabel)));
}

async function downloadEntryAll(entry) {
  await withBusy(async () => {
    showProgress('ファイル一覧を取得中…', 0, 1);
    const loaded = await ensureFiles(entry);
    if (!loaded.files.length) throw new Error('このパスにファイルがありません');
    if (loaded.files.length === 1) {
      await saveSingleFile(entry, loaded.files[0]);
      return;
    }
    await zipAndSave(entry, loaded.files);
  });
}

async function downloadSelectedZip() {
  const ids = [...state.selected];
  if (!ids.length) return;

  await withBusy(async () => {
    const jobs = [];
    for (const [i, id] of ids.entries()) {
      const entry = entryById(id);
      if (!entry) continue;
      showProgress(`一覧を取得中… (${i + 1}/${ids.length}) ${entry.label}`, i, ids.length);
      let loaded;
      try {
        loaded = await ensureFiles(entry);
      } catch (err) {
        toast(`${entry.label}: ${err.message}`, 'error');
        continue;
      }
      const prefix = ids.length > 1 ? `${sanitizeFilename(entry.label)}/` : '';
      for (const f of uniqueZipNames(loaded.files)) {
        jobs.push({ entry, file: f, zipName: `${prefix}${f.zipName}` });
      }
    }

    if (!jobs.length) throw new Error('ダウンロードできるファイルがありませんでした');

    // 結局 1 ファイルなら ZIP にせずそのまま落とす
    if (jobs.length === 1) {
      await saveSingleFile(jobs[0].entry, jobs[0].file);
      return;
    }

    showProgress(`0 / ${jobs.length} 取得中…`, 0, jobs.length);
    const { files, errors } = await fetchAll(jobs, (done, total, name) => {
      showProgress(`${done} / ${total} 取得中… ${name}`, done, total);
    });

    if (!files.length) throw new Error(errors[0] || 'ダウンロードに失敗しました');

    showProgress('ZIP を作成中…', 1, 1);
    const stamp = new Date().toISOString().slice(0, 10);
    saveBlob(buildZip(files), `github-files_${stamp}.zip`);
    toast(errors.length
      ? `${files.length} 件をZIPにしました（${errors.length} 件は失敗）`
      : `${files.length} 件をZIPにしました`, errors.length ? 'error' : '');
  });
}

/* ============================================================
 * 設定ダイアログ
 * ========================================================== */

function currentRegistryJSON() {
  // ファイル置き場は registry.json ではなく files.json 側の管理なので外す
  const entries = visibleEntries().filter((e) => e.target).map((e) => ({
    id: e.id.startsWith('local:') ? `seed:${targetKey(e.target)}` : e.id,
    label: e.label,
    path: `${e.target.owner}/${e.target.repo}${e.target.path ? `/${e.target.path}` : ''}`,
    ref: e.target.ref,
    recursive: e.recursive,
    addedAt: e.addedAt,
    ...(e.note ? { note: e.note } : {}),
  }));
  return JSON.stringify({ entries }, null, 2);
}

function openSettings() {
  $('#token-input').value = getToken();
  $('#token-state').textContent = getToken() ? 'トークン設定済み' : 'トークン未設定';
  $('#export-area').value = currentRegistryJSON();
  $('#settings-dialog').showModal();
}

/* ============================================================
 * 起動
 * ========================================================== */

function wireUp() {
  $('#add-form').addEventListener('submit', (ev) => {
    ev.preventDefault();
    try {
      const entry = addEntry({
        path: $('#add-path').value,
        label: $('#add-label').value,
        recursive: $('#add-recursive').checked,
      });
      $('#add-path').value = '';
      $('#add-label').value = '';
      $('#add-recursive').checked = false;
      $('#add-details').open = false;
      toast(`「${entry.label}」を登録しました`);
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('#btn-reload').addEventListener('click', async () => {
    state.files.clear();
    defaultBranchCache.clear();
    await loadStore();
    await loadRegistry();
    for (const id of state.open) {
      if (id === STORE_ID) continue;   // 置き場はマニフェスト読み込みで揃っている
      const entry = entryById(id);
      if (entry) loadEntryFiles(entry);
    }
    toast('再読み込みしました');
  });

  $('#btn-settings').addEventListener('click', openSettings);

  $('#select-all').addEventListener('change', (ev) => {
    state.selected = ev.target.checked ? new Set(visibleEntries().map((e) => e.id)) : new Set();
    render();
  });

  $('#btn-zip-selected').addEventListener('click', downloadSelectedZip);

  $('#btn-del-selected').addEventListener('click', () => {
    const ids = [...state.selected];
    if (!ids.length) return;
    if (!confirm(`選択した ${ids.length} 件を削除します。よろしいですか？`)) return;
    deleteEntries(ids);
  });

  $('#btn-del-all').addEventListener('click', () => {
    const ids = visibleEntries().map((e) => e.id);
    if (!ids.length) return;
    if (!confirm(`登録 ${ids.length} 件をすべて削除します。よろしいですか？`)) return;
    deleteEntries(ids);
  });

  $('#btn-save-token').addEventListener('click', () => {
    const value = $('#token-input').value.trim();
    try {
      if (value) localStorage.setItem(LS.token, value);
      else localStorage.removeItem(LS.token);
    } catch {
      toast('トークンを保存できませんでした', 'error');
      return;
    }
    $('#token-state').textContent = value ? 'トークン設定済み' : 'トークン未設定';
    state.files.clear();
    render();
    for (const id of state.open) {
      const entry = entryById(id);
      if (entry) loadEntryFiles(entry);
    }
    toast(value ? 'トークンを保存しました' : 'トークンを削除しました');
  });

  $('#btn-clear-token').addEventListener('click', () => {
    try { localStorage.removeItem(LS.token); } catch { /* noop */ }
    $('#token-input').value = '';
    $('#token-state').textContent = 'トークン未設定';
    renderRateInfo();
    toast('トークンを削除しました');
  });

  $('#btn-copy-export').addEventListener('click', async () => {
    const text = $('#export-area').value;
    try {
      await navigator.clipboard.writeText(text);
      toast('コピーしました');
    } catch {
      $('#export-area').select();
      toast('コピーできませんでした。手動で選択してください', 'error');
    }
  });

  $('#btn-import').addEventListener('click', () => {
    let data;
    try {
      data = JSON.parse($('#export-area').value);
    } catch {
      toast('JSON として読めませんでした', 'error');
      return;
    }
    const rows = Array.isArray(data) ? data : (data.entries || []);
    let added = 0;
    for (const row of rows) {
      try {
        addEntry({ path: row.path ?? row.url, label: row.label, recursive: row.recursive });
        added++;
      } catch { /* 重複や不正な行は飛ばす */ }
    }
    toast(`${added} 件を取り込みました`);
    $('#export-area').value = currentRegistryJSON();
  });

  $('#btn-reset-local').addEventListener('click', () => {
    if (!confirm('この端末での追加・削除をすべて取り消し、共有リストの状態に戻します。よろしいですか？')) return;
    try {
      localStorage.removeItem(LS.local);
      localStorage.removeItem(LS.removed);
    } catch { /* noop */ }
    state.local = [];
    state.removed = new Set();
    state.files.clear();
    render();
    $('#export-area').value = currentRegistryJSON();
    toast('この端末の変更をリセットしました');
  });
}

async function init() {
  loadLocal();
  wireUp();
  render();
  renderRateInfo();
  await loadStore();
  render();
  await loadRegistry();
}

init();
