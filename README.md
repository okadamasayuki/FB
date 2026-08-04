# FB

会社と個人の端末のあいだでファイルを受け渡すための、小さな静的サイトです。GitHub Pages で動きます。

URL: **https://okadamasayuki.github.io/FB/**

## 考え方

ファイルの実体を **このリポジトリの `files/` に置き、サイト自身が配ります**。
`raw.githubusercontent.com` や `api.github.com` といった別のホストは一切参照しません。
このページが開ける環境なら、どんなネットワークでも必ずダウンロードできます。
ダウンロードボタンも素の `<a download>` で、JavaScript も fetch も挟みません。

## できること

- ファイル名と日付の一覧（開いた時点でそのまま並びます）
- 1 クリックでダウンロード
- 削除：行の削除ボタン、**左スワイプ**、選択して一括削除、全削除
- 削除した直後は「元に戻す」で復活できます

削除はその端末で見えなくするだけで、`files/` からは消えません。
すべて戻したいときは設定（⚙）→「削除したものを元に戻す」。

## ファイルを追加する

置きたいファイルの場所を伝えてください。形式はこれで足ります。

```
owner/repo/フォルダ/ファイル名
```

`data/sync.json` に追加され、以降は **1 時間おきに自動で取りに行き、更新されていれば差し替えます**。
一度伝えれば、あとは手をかける必要はありません。

現在の取得元は設定（⚙）→「取得元」で確認できます。

## 自動同期のしくみ

`.github/workflows/sync-files.yml` が毎時 15 分に動きます。

1. `data/sync.json` に書かれた場所からファイルを取得
2. 中身が変わっていれば `files/` を更新し、`data/files.json` の日付を書き換え
3. コミットして、そのまま公開まで実行

- 中身が同じファイルは書き換えません。日付は**実際に更新された日**を指します
- `ref` を空にしておくと、取得元のデフォルトブランチを自動で解決します
- 取得元が非公開リポジトリの場合は、Contents: Read-only の PAT を `SYNC_TOKEN` シークレットに登録してください
- すぐ反映したいときは Actions タブから *Sync files from source repos* を手動実行

Actions が push したコミットでは通常の push トリガーが発火しないため、
同期ジョブから `pages.yml` を `workflow_call` で直接呼んでいます。

## 構成

```
index.html                        画面
assets/style.css                  スタイル（ライト／ダーク対応）
assets/app.js                     ロジック（依存ライブラリなし）
files/                            配布するファイルの実体
data/files.json                   一覧に出すファイルと日付
data/sync.json                    自動同期の取得元
scripts/sync-files.mjs            同期スクリプト
.github/workflows/sync-files.yml  定期同期
.github/workflows/pages.yml       GitHub Pages への公開
```

ビルド不要です。ローカルで確認するときは、リポジトリ直下で次を実行して `http://localhost:8000/` を開きます。

```sh
python3 -m http.server 8000
```

（`file://` で直接開くと `data/files.json` の読み込みがブロックされます）
