#!/usr/bin/env node
/*
 * data/sync.json に書かれた元リポジトリからファイルを取り直し、
 * files/ と data/files.json を更新する。
 *
 * - 中身が変わっていないファイルは書き換えない（uploadedAt も据え置き）
 * - files.json に手で足したエントリは消さない
 * - 元ファイルが取れなかったときは、既存のコピーを残して警告するだけ
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

// 非公開リポジトリを読むときだけ使う。公開リポジトリなら未設定でよい。
// Actions が自動で持たせる GITHUB_TOKEN は他リポジトリを読めないので使わない。
const token = process.env.SYNC_TOKEN || '';

function apiHeaders(accept = 'application/vnd.github+json') {
  return {
    Accept: accept,
    'X-GitHub-Api-Version': '2022-11-28',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

let changed = false;
const warnings = [];

/** 実行時刻を JST の ISO 8601 で返す（表示用なので秒まで） */
function nowJst() {
  const shifted = new Date(Date.now() + 9 * 60 * 60 * 1000);
  return `${shifted.toISOString().slice(0, 19)}+09:00`;
}

async function resolveRef(repo, ref) {
  if (ref) return ref;
  const res = await fetch(`https://api.github.com/repos/${repo}`, { headers: apiHeaders() });
  if (!res.ok) throw new Error(`デフォルトブランチを取得できません（${res.status}）`);
  const info = await res.json();
  return info.default_branch;
}

/**
 * トークンがあれば API 経由（非公開リポジトリも読める）、無ければ raw を直接。
 * raw は認証ヘッダを受け付けないので、トークンを付けて投げると 404 になる。
 */
async function download(repo, ref, from) {
  const url = token
    ? `https://api.github.com/repos/${repo}/contents/${encodeURI(from)}?ref=${encodeURIComponent(ref)}`
    : `https://raw.githubusercontent.com/${repo}/${encodeURI(ref)}/${encodeURI(from)}`;
  const res = await fetch(url, token ? { headers: apiHeaders('application/vnd.github.raw') } : undefined);
  if (!res.ok) throw new Error(`取得できません（${res.status}） ${url}`);
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
      warnings.push(`${source.repo}: ${err.message}`);
      continue;
    }
    console.log(`--- ${source.repo} @ ${ref}`);

    for (const spec of source.files || []) {
      const dest = path.join(ROOT, spec.to);
      let bytes;
      try {
        bytes = await download(source.repo, ref, spec.from);
      } catch (err) {
        warnings.push(`${source.repo}/${spec.from}: ${err.message}`);
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

      // マニフェストを更新する。既存の並びは崩さない。
      const name = path.basename(spec.to);
      const existing = entries.find((e) => e.path === spec.to);
      const row = {
        path: spec.to,
        name,
        size: bytes.length,
        uploadedAt: isSame && existing?.uploadedAt ? existing.uploadedAt : nowJst(),
        note: spec.note || existing?.note || '',
      };
      if (!row.note) delete row.note;

      if (existing) {
        if (JSON.stringify(existing) !== JSON.stringify(row)) changed = true;
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

  manifest.files = kept;
  await writeFile(FILES_MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);

  for (const w of warnings) console.warn(`警告: ${w}`);
  console.log(changed ? '変更あり' : '変更なし');

  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `changed=${changed}\n`);
  }
  if (process.env.GITHUB_STEP_SUMMARY) {
    const lines = warnings.length
      ? [`### 同期できなかったファイル`, '', ...warnings.map((w) => `- ${w}`)]
      : [`同期完了（${changed ? '変更あり' : '変更なし'}）`];
    await appendFile(process.env.GITHUB_STEP_SUMMARY, `${lines.join('\n')}\n`);
  }

  // 1 つも取れなかったときだけ失敗させる。
  // 一部だけ落ちた場合は、取れたぶんを反映させたいので失敗にしない。
  if (warnings.length && !changed) process.exitCode = 1;
}

await main();
