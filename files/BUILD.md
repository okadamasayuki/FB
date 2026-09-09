# 元データとビルド手順(社内で編集する人向けのメモ)

このフォルダ一式が「勘定科目 分類ツール」の元データです。公開ページ(GitHub Pages)の実体は
`勘定科目分類ツール.html` 1ファイル(まとめ版)で、ここにある元データから機械的に組み立てます。

## 1. 公開の仕組み

- 公開先: https://okadamasayuki.github.io/kanjo-tool/ (リポジトリ `okadamasayuki/kanjo-tool`)
- kanjo-tool にあるのは `index.html` と `kanjo-tool.html`(どちらも `勘定科目分類ツール.html` のコピー)と
  `.github/workflows/pages.yml`(main に push すると GitHub Actions が Pages に配置する)だけ
- 更新のしかた: 元データを直す → 下の順でビルド → `勘定科目分類ツール.html` を kanjo-tool の
  `index.html` と `kanjo-tool.html` に上書きコピー → main に push(Actions が成功すれば反映)
- 元データの正本は `okadamasayuki/dify-west`(非公開リポジトリ)。この一式はそのスナップショットです

## 2. 手で編集する元データ(直すのはここ)

| 画面 | 編集するファイル |
|---|---|
| ① Excelからツリー | `Excelからツリー.html`(コマンド版は `Excelからツリー.py`) |
| ② ツリー検査 | `ツリー検査.html`(本体)、`ツリー検査.md`(AI用の手順書。`tools/build_check.py` で埋め込む)、`ツリー検査.py` |
| ②-2 十桁の定義 | `十桁定義.html` |
| ③ ツリーからDify | `ツリーからDify.html`(画面+JS側のDSL生成器)、`tools/generate_workflow.py`(Python側の生成器。JSと同じYAMLを出す=パリティを保つ)、`tools/workflow_extras.yml`(プロンプト・ノードの素材。`tools/build_html.py` でHTMLに埋め込む)、`tools/tree_demo_script.js`(動画の台本) |
| ④ 採点 | `tools/build_eval_page.py`(ページのHTML本体)、`tools/eval_common.js`(採点コア。⑤と共用)、`tools/eval_page_runner.js`(④「ブラウザで採点」のUI)、`tools/eval_demo_scripts.js`(動画台本)、`tools/build_eval.py`(Dify版採点DSL)、`契約書判定の採点.py`(PC用スクリプト)、`tools/build_notebook.py`(Snowflakeノートブック) |
| ⑤ 自動学習 | `tools/build_learn_page.py`(ページ本体)、`tools/learn_page_runner.js`(学習ループのUI)、`tools/learn_demo_scripts.js`(動画台本) |
| まとめ版 | `tools/build_bundle.py`(タブ・ヘッダ・「このツールについて」の文章・全消しボタン) |
| 共通部品 | `tools/state_store.js`(ブラウザ内の自動保存)、`tools/sheet_reader.js`(Excel/CSV/古い.xls などの読み込み)、`tools/demo_player.js` / `tools/demo_player.css`(動画エンジン)、`tools/miniyaml.py`(YAML出力)、`tools/build_standalone.py`(コマンド版 `ツリーからDify.py` の組み立て) |
| 分類ツリー・説明 | `分類ツリー.md`(サンプルのツリー)、`README.md`(全体の説明書)、`docs/`、`tools/tree_review_guide.md` |

共通部品(state_store.js / sheet_reader.js / demo_player.js)は各HTMLに「コピーを埋め込む」方式です。
直したら必ず sync スクリプト(下記)を実行してからビルドしてください。HTML側の埋め込み部分
(`// STATE_STORE_BEGIN` 〜 `// STATE_STORE_END` など)を直接編集しても、次の sync で上書きされます。

## 3. 生成物(手で編集しない。ビルドで作り直す)

| 生成物 | 作るスクリプト |
|---|---|
| `勘定科目分類ツール.html`(まとめ版=公開ページ) | `tools/build_bundle.py` |
| `判定の採点.html`(④) | `tools/build_eval_page.py` |
| `自動学習.html`(⑤) | `tools/build_learn_page.py` |
| `ツリーからDify.py`(③のコマンド版) | `tools/build_standalone.py` |
| `contract-account-eval.yml`(Dify版の採点DSL) | `tools/build_eval.py` |
| `契約書判定の採点.ipynb` | `tools/build_notebook.py` |
| `contract-account-classification*.yml`(DSLのサンプル出力) | `python3 ツリーからDify.py 分類ツリー.md --all` など |
| `ツリーからDify.html` の `<<EXTRAS>>` 部分 / `ツリー検査.html` の `<<GUIDE>>` 部分 | `tools/build_html.py` / `tools/build_check.py` |

## 4. ビルド手順(Python 3 だけで動きます。追加ライブラリは不要)

```
python3 tools/sync_sheet_reader.py     # sheet_reader.js → ①・②-2 に埋め込み
python3 tools/sync_state_store.py      # state_store.js → ①②②-2③ に埋め込み
python3 tools/sync_demo_player.py      # demo_player.js/css → ③(④⑤はビルド時に取り込む)
python3 tools/build_html.py            # workflow_extras.yml → ツリーからDify.html
python3 tools/build_check.py           # ツリー検査.md → ツリー検査.html
python3 tools/build_standalone.py      # ツリーからDify.py
python3 tools/build_eval.py            # contract-account-eval.yml
python3 tools/build_notebook.py        # 契約書判定の採点.ipynb
python3 tools/build_eval_page.py       # 判定の採点.html
python3 tools/build_learn_page.py      # 自動学習.html
python3 tools/build_bundle.py          # 勘定科目分類ツール.html(いちばん最後)
```

直したファイルに関係あるものだけでもよいですが、迷ったら上から全部実行してください(数秒で終わります)。

## 5. テスト(`tests_e2e/`)

- Playwright(Chromium)で画面を動かすテスト(`test_*.js`)と、Python生成器のテスト(`test_*.py`)。
  `fixtures/` にテスト用のExcel・CSV・古い.xls などが入っています
- 準備: Node.js 18以上で `npm i playwright` と `npx playwright install chromium`
  (ブラウザを別に用意する場合は環境変数 `CHROMIUM_PATH` にその実行ファイルのパス)
- 実行例:

```
cd tests_e2e && export SCRATCH=$PWD
python3 test_variants.py                              # Python生成器(3形式×自己学習)
node dump_js.js && python3 test_variants_parity.py    # JSとPythonのDSLが1バイトも違わないこと
node test_ui_v5.js                                    # ③の画面(形式切替・自己学習・zip保存)
node test_tendigit_excel.js; node test_rmwords.js; node test_preamble.js; node test_xls_pages.js   # ②-2
node test_xls_reader.js; node test_excel_tree_read.js # 表ファイル読み込み・①
node test_browser_eval.js; node test_learn_page.js    # ④⑤(モックDifyを内蔵。実Difyには通信しない)
node test_state_store.js; node test_layout.js; node test_kb_demo.js; node test_learn_demo.js; node test_eval_page.js
```

- `tools/tests/` には生成器の細かい単体テスト(Python)もあります(`python3 tools/tests/test_chat_same.py` など)

## 6. 設計上の約束(壊さないでほしいこと)

- 通信するのは④「ブラウザで採点」と⑤「自動学習」だけ。通信先は利用者がその場で入力した自社DifyのURLのみ。
  それ以外のページは一切通信しない(外部CDN・外部フォント・外部APIを使わない)
- ブラウザ内の自動保存(IndexedDB/localStorage)はそのPCの中だけ。外部のDBやサービスにデータを送らない
- ③のJS生成器とPython生成器は同じYAMLを出す(パリティテストで確認)。片方だけ直さない
- DSLの構造を変えたときは、実際のDifyでインポート→公開→プレビューまで確認する(この開発環境ではDify実機は未検証)
