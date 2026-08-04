# GitHub パス ダウンローダー

登録しておいた GitHub のパス（フォルダ）にあるファイルを、一覧からワンクリックでダウンロードするための小さな静的サイトです。GitHub Pages でそのまま動きます。

公開 URL: **https://okadamasayuki.github.io/FB/**

## できること

- 登録したパスを一覧表示（表示名・リポジトリ・ブランチ・登録日時）
- パス配下のファイル一覧（ファイル名・サイズ・登録日時）
- 各ファイル行の **⬇ ダウンロード** で、そのファイルをそのまま保存（ZIP にはしません）
- パス配下を **まとめて ZIP** でダウンロード（ファイルを選んで ZIP も可）
- 対象が 1 ファイルのときは、まとめて保存でも ZIP にせずそのまま落とします
- 削除：ボタン、**左スワイプ**（スマホ）、選択して一括削除、全削除
- 削除した直後は「元に戻す」で復活できます
- 非公開リポジトリ向けに、GitHub トークンを設定する画面あり

## パスの登録方法

登録先は 2 か所あります。

### 1. 共有リスト（`data/registry.json`）

リポジトリにコミットされるので、**どの端末で開いても同じものが見えます**。
Claude に次のように伝えると、ここに追記してくれます。

```
このパス登録しといて: https://github.com/owner/repo/tree/main/docs/invoices
```

`data/registry.json` の中身はこんな形です。

```json
{
  "entries": [
    {
      "label": "請求書 2026",
      "path": "owner/repo/docs/invoices",
      "ref": "main",
      "recursive": false,
      "addedAt": "2026-08-04T10:00:00+09:00"
    }
  ]
}
```

| キー | 必須 | 意味 |
| --- | --- | --- |
| `path` | ○ | `owner/repo/フォルダ` または GitHub の URL（`/tree/`・`/blob/` 付きも可） |
| `label` | | 一覧での表示名（省略時はフォルダ名） |
| `ref` | | ブランチ／タグ／コミット（省略時はデフォルトブランチ） |
| `recursive` | | `true` でサブフォルダの中も一覧に含める |
| `addedAt` | | 登録日時（ISO 8601）。並び順と「登録日」表示に使用 |
| `note` | | 一覧に出るひとことメモ |
| `id` | | 省略可。省略時は `path` から自動生成 |

### 2. サイト上の「パスを追加する」

その場で追加できますが、保存先はブラウザの localStorage なので **その端末だけ** に残ります。
共有リストに移したいときは、設定（⚙）→「登録データ」の JSON をコピーして Claude に渡してください。

## 削除の挙動

| 対象 | 削除すると |
| --- | --- |
| この端末で追加したもの | localStorage から消えます |
| 共有リスト由来のもの | その端末で非表示になるだけで、`data/registry.json` は変わりません |

共有リストから完全に消したいときは、Claude に「あれ消しといて」と伝えて `data/registry.json` を更新してもらってください。
設定（⚙）→「この端末の変更をリセット」で、共有リストそのままの状態に戻せます。

## GitHub トークン（任意）

- 未設定でも公開リポジトリなら動きます（GitHub API の上限は 1 時間あたり 60 回）
- 非公開リポジトリを扱う場合、または上限を上げたい場合は設定（⚙）から登録します
- 推奨は **fine-grained personal access token / Repository permissions → Contents: Read-only**
- トークンはそのブラウザの localStorage にだけ保存され、リポジトリには一切保存されません。共用端末では使わないでください

## 構成

```
index.html                     画面
assets/style.css               スタイル（ライト／ダーク対応）
assets/app.js                  ロジック（依存ライブラリなし。ZIP 生成も自前）
data/registry.json             共有の登録リスト
.github/workflows/pages.yml    GitHub Pages への自動デプロイ
```

ビルド不要です。ローカルで確認するときは、リポジトリ直下で次を実行して `http://localhost:8000/` を開きます。

```sh
python3 -m http.server 8000
```

（`file://` で直接開くと `data/registry.json` の読み込みがブロックされます）

## デプロイ

公開されるまでに、リポジトリ設定を 1 回だけ変更する必要があります（API では変更できない箇所です）。
どちらか片方でかまいません。

### A. ブランチから直接公開する（いちばん手軽）

**Settings → Pages → Build and deployment**

- Source: **Deploy from a branch**
- Branch: **`claude/github-path-file-downloader-x0oo8c`** / **`/ (root)`** → Save

1 分ほどで公開されます。GitHub Actions は不要です。

### B. GitHub Actions で公開する

**Settings → Pages → Build and deployment → Source: GitHub Actions**

これで `github-pages` 環境が正しく作られ、`.github/workflows/pages.yml` が
`main` / `master` / `claude/**` への push のたびにサイト全体を公開します。
設定後は Actions タブから最新のワークフローを **Re-run** してください。

> 設定前は、`build` ジョブ（Pages の有効化とアーティファクトのアップロード）は成功しますが、
> `github-pages` 環境を参照する `deploy` ジョブが開始前に拒否されて失敗します。

### 補足

このリポジトリは `claude/github-path-file-downloader-x0oo8c` が現在のデフォルトブランチです。
`main` に整理したい場合は Settings → Branches からリネームしてください
（ワークフローは `main` への push にも対応しています）。
