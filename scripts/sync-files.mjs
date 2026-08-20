#!/usr/bin/env node
/*
 * data/sync.json に書かれた元リポジトリからファイルを取り直し、
 * files/ と data/files.json を更新する。
 *
 * 取得は「まずツリーを 1 回引いて、変わったファイルだけ落とす」方式。
 * 毎時動かしても、変更が無ければリクエストは 2 回で済む。
 * 以前は毎回 10 件を raw から落としていて、共有 IP のレート制限（429）に
 * 引っかかってジョブごと失敗していた。
 *
 * - 中身が変わっていないファイルは書き換えない（uploadedAt も据え置き）
 * - files.json に手で足したエントリは消さない
 * - 並びは sync.json の順に揃える
 * - 429 や 5xx は待って数回やり直す。それでも駄目なら次回に回す（失敗にしない）
 * - 404 だけは設定の誤りなので失敗させる
 *
 * 依存ライブラリなし。GitHub Actions から実行する。
 */
import { readFile, writeFile, mkdir, appendFile } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SYNC_CONFIG = path.join(ROOT, 'data', 'sync.json');
const FILES_MANIFEST = path.join(ROOT, 'data', 'files.json');

// 非公開リポジトリを読むときは SYNC_TOKEN が要る。
// 公開リポジトリなら Actions が配る GITHUB_TOKEN で十分（未認証より上限が高い）。
const token = process.env.SYNC_TOKEN || process.env.GITHUB_TOKEN || '';

let changed = false;
const softWarnings = [];   // 一時的な失敗。次回に回す
const hardWarnings = [];   // 設定の誤り。気づけるように失敗させる

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function apiHeaders(accept = 'application/vnd.github+json') {
  return {
    Accept: accept,
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'fb-sync-files',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** 実行時刻を JST の ISO 8601 で返す（表示用なので秒まで） */
function nowJst() {
  const shifted = new Date(Date.now() + 9 * 60 * 60 * 1000);
  return `${shifted.toISOString().slice(0, 19)}+09:00`;
}

class HttpError extends Error {
  constructor(status, url) {
    super(`取得できません（${status}） ${url}`);
    this.status = status;
    this.transient = status === 429 || status === 408 || status >= 500;
  }
}

/** 429 や 5xx は一時的なものとして待ってやり直す */
async function fetchWithRetry(url, headers, attempts = 4) {
  let last;
  for (let i = 0; i < attempts; i++) {
    let res;
    try {
      res = await fetch(url, { headers });
    } catch (err) {
      last = new HttpError(0, url);
      last.transient = true;
    }
    if (res) {
      if (res.ok) return res;
      last = new HttpError(res.status, url);
      if (!last.transient) throw last;
      const retryAfter = Number(res.headers.get('retry-after'));
      if (Number.isFinite(retryAfter) && retryAfter > 0) {
        await sleep(Math.min(retryAfter, 30) * 1000);
        continue;
      }
    }
    if (i < attempts - 1) await sleep(2000 * 2 ** i);   // 2s, 4s, 8s
  }
  throw last;
}

async function resolveRef(repo, ref) {
  if (ref) return ref;
  const res = await fetchWithRetry(`https://api.github.com/repos/${repo}`, apiHeaders());
  return (await res.json()).default_branch;
}

/**
 * リポジトリ全体のファイル一覧（パス → blob SHA）を 1 リクエストで取る。
 * これと手元の SHA を比べれば、変わっていないファイルは落とさずに済む。
 * 巨大リポジトリでは切り詰められることがあるので、その場合は null を返す。
 */
async function listTree(repo, ref) {
  try {
    const url = `https://api.github.com/repos/${repo}/git/trees/${encodeURIComponent(ref)}?recursive=1`;
    const body = await (await fetchWithRetry(url, apiHeaders())).json();
    if (body.truncated) return null;
    return new Map(body.tree.filter((n) => n.type === 'blob').map((n) => [n.path, n.sha]));
  } catch {
    return null;   // 取れなければ従来どおり全部落とす
  }
}

/**
 * ファイルの中身を取る。
 * トークンがあれば API 経由（非公開リポジトリも読める・上限が高い）、
 * 無ければ raw。raw は認証ヘッダを受け付けないので付けない。
 */
async function download(repo, ref, from) {
  if (token) {
    const url = `https://api.github.com/repos/${repo}/contents/${encodeURI(from)}?ref=${encodeURIComponent(ref)}`;
    const res = await fetchWithRetry(url, apiHeaders('application/vnd.github.raw'));
    return Buffer.from(await res.arrayBuffer());
  }
  const url = `https://raw.githubusercontent.com/${repo}/${encodeURI(ref)}/${encodeURI(from)}`;
  const res = await fetchWithRetry(url, { 'User-Agent': 'fb-sync-files' });
  return Buffer.from(await res.arrayBuffer());
}

async function main() {
  const config = JSON.parse(await readFile(SYNC_CONFIG, 'utf8'));
  const manifest = JSON.parse(await readFile(FILES_MANIFEST, 'utf8'));
  const entries = Array.isArray(manifest.files) ? manifest.files : [];

  for (const source of config.sources || []) {
    let ref;
    try {
      ref = await resolveRef(source.repo, source.ref);
    } catch (err) {
      (err.transient ? softWarnings : hardWarnings).push(`${source.repo}: ${err.message}`);
      continue;
    }
    const tree = await listTree(source.repo, ref);
    console.log(`--- ${source.repo} @ ${ref}${tree ? '' : '（一覧が取れないので全件確認）'}`);

    for (const spec of source.files || []) {
      const dest = path.join(ROOT, spec.to);
      const existing = entries.find((e) => e.path === spec.to);
      const sourceSha = tree?.get(spec.from);

      // 元の SHA が前回と同じで、手元にも実体があるなら落とさない
      if (sourceSha && existing?.sourceSha === sourceSha && existsSync(dest)) {
        console.log(`  変更なし ${spec.to}`);
        if (spec.note && existing.note !== spec.note) {
          existing.note = spec.note;
          changed = true;
        }
        continue;
      }

      if (tree && !sourceSha) {
        hardWarnings.push(`${source.repo}/${spec.from}: 元リポジトリに見つかりません`);
        continue;
      }

      let bytes;
      try {
        bytes = await download(source.repo, ref, spec.from);
      } catch (err) {
        (err.transient ? softWarnings : hardWarnings).push(`${source.repo}/${spec.from}: ${err.message}`);
        continue;
      }

      const before = existsSync(dest) ? readFileSync(dest) : null;
      const isSame = before && before.equals(bytes);

      if (!isSame) {
        await mkdir(path.dirname(dest), { recursive: true });
        await writeFile(dest, bytes);
        changed = true;
      }
      console.log(`${isSame ? '  変更なし' : '  更新    '} ${spec.to} (${bytes.length} bytes)`);

      const row = {
        path: spec.to,
        name: path.basename(spec.to),
        size: bytes.length,
        uploadedAt: isSame && existing?.uploadedAt ? existing.uploadedAt : nowJst(),
        note: spec.note || existing?.note || '',
        ...(sourceSha ? { sourceSha } : {}),
      };
      if (!row.note) delete row.note;

      if (existing) {
        if (JSON.stringify(existing) !== JSON.stringify(row)) changed = true;
        for (const k of Object.keys(existing)) delete existing[k];
        Object.assign(existing, row);
      } else {
        entries.push(row);
        changed = true;
      }
    }
  }

  // sync.json から外されたファイルは一覧からも消す（実体は別途削除する）
  const managed = new Set(
    (config.sources || []).flatMap((s) => (s.files || []).map((f) => f.to)),
  );
  const kept = entries.filter((e) => {
    if (managed.has(e.path)) return true;
    if (!existsSync(path.join(ROOT, e.path))) {
      console.log(`  一覧から除外 ${e.path}（実体なし）`);
      changed = true;
      return false;
    }
    return true;   // 手で置いたファイルは残す
  });

  // 一覧の並びは sync.json の順に揃える。サイトはこの順で表示するので、
  // 読ませたい順を設定ファイル側で決められるようにしておく。
  const order = new Map([...managed].map((p, i) => [p, i]));
  const before = kept.map((e) => e.path).join('\n');
  kept.sort((a, b) => (order.get(a.path) ?? Number.MAX_SAFE_INTEGER)
    - (order.get(b.path) ?? Number.MAX_SAFE_INTEGER));
  if (kept.map((e) => e.path).join('\n') !== before) changed = true;

  manifest.files = kept;
  await writeFile(FILES_MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);

  for (const w of hardWarnings) console.error(`::error::${w}`);
  for (const w of softWarnings) console.warn(`::warning::一時的に取得できず、次回に回します: ${w}`);
  console.log(changed ? '変更あり' : '変更なし');

  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `changed=${changed}\n`);
  }
  if (process.env.GITHUB_STEP_SUMMARY) {
    const lines = [`同期${changed ? '（変更あり）' : '（変更なし）'}`];
    if (softWarnings.length) lines.push('', '### 次回に回したもの', ...softWarnings.map((w) => `- ${w}`));
    if (hardWarnings.length) lines.push('', '### 設定を直す必要があるもの', ...hardWarnings.map((w) => `- ${w}`));
    await appendFile(process.env.GITHUB_STEP_SUMMARY, `${lines.join('\n')}\n`);
  }

  // レート制限や一時的な障害では失敗させない（次回の実行で拾える）。
  // 設定の誤りだけは気づけるように失敗させる。
  if (hardWarnings.length) process.exitCode = 1;
}

await main();
