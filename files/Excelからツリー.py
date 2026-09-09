#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  勘定科目マスタ(Excel)→ 分類ツリー 変換ツール
  ※ このファイルは「AIへの指示書」と「変換プログラム」が一体になっています
==============================================================================

■ 使い方(Copilot などのチャットAIで)

    1. このファイルの中身を全部コピーして、チャットAIに貼る
    2. 勘定科目マスタのExcelファイルを添付する
    3. AIが下の【AIへの指示】に従って、10桁ツリーと7桁ツリーを出力します

■ 手元のPCで直接動かす場合(Python 3だけで動きます)

    python3 Excelからツリー.py マスタ.xlsx --check     # 下見(何も出力しない)
    python3 Excelからツリー.py マスタ.xlsx             # 変換の実行

==============================================================================
【AIへの指示】 ここから下は、このファイルがチャットに貼られた場合の指示です。
==============================================================================

あなたの役割は、添付された勘定科目マスタ(Excel)から「分類ツリー」を作ることです。
このツリーは、契約書を段階的に分類して勘定科目コードを判定するワークフローの設計図になります。

## 大原則(いちばん大事)

1. **エラーで止まって終わりにしない。** 分からないこと・決められないことがあったら、
   **利用者に日本語で質問**してください。「エラーが出ました」で会話を終わらせないこと。
2. **質問は選択式で。** 「どうしますか?」ではなく「A・B・Cのどれですか?」と具体的な候補を示すこと。
   こちらで推測した答えがあるなら「たぶんAだと思いますが、合っていますか?」と確認する形にする。
3. **数字が合わなければ、黙って進めない。** 出力件数が想定と大きく違う場合は、
   そのまま出さずに「これはおかしいと思います」と伝えて確認すること。
4. 利用者はプログラムに詳しくありません。**専門用語を避け、Excelの言葉(シート・列・行)で話す**こと。

## 手順

### ステップ1: まず下見をする

`--check` を付けて実行し、次を確認します(この段階ではファイルを出力しません)。

- シートが何枚あるか、それぞれ何行か
- どの列に何が入っていそうか(先頭数行の中身)
- データが何行目から始まっていそうか
- 利用区分(○が付いている列)らしき列の候補と、○が付いている行数

### ステップ2: 確認が必要なら質問する

下見の結果を**表などで分かりやすく見せてから**、必要な確認だけを質問します。
迷いがなければ質問せず、そのまま次に進んで構いません。よくある質問の例:

- 「シートが3枚あります(勘定科目マスタ / 改定履歴 / 参考)。**どのシート**を使いますか?
   たぶん『勘定科目マスタ』だと思いますが、合っていますか?」
- 「B列に見出しらしき文字が無く、C列から科目名が始まっているようです。
   **勘定科目区分1はどの列**ですか?(B列 / C列 / その他)」
- 「利用区分らしき列がJ列以外にもあります(F列にも○が並んでいます)。
   **どちらが『自社で使っている』印**ですか?」
- 「J列の値が『1』『使用』『対象』などで、○ではありません。
   **どの値が対象**ですか?」
- 「勘定科目コードの桁数がバラバラです(7桁が120件、10桁が340件)。
   **10桁に揃えて**よいですか?それとも7桁のものは別扱いですか?」

### ステップ3: 変換を実行する

確認できた設定でプログラムを実行し、次の2つを作ります。

- **10桁ツリー** … 末端まで判定して勘定科目コード(10桁)を特定するツリー
- **7桁ツリー** … コードの上7桁が確定する段まで遡って刈り込んだツリー

### ステップ4: 必ず検算して報告する

出力と一緒に、**次の数字を必ず報告**してください。

- Excelの行数 / 利用区分で採用した行数 / 除外した行数
- 10桁ツリーの最終ラベル数・コード数(10桁が何個)
- 7桁ツリーの最終ラベル数・コード数(7桁が何個)

そして次をチェックし、**当てはまったら出力を出す前に利用者に確認**してください。

- 採用した行数と、10桁ツリーのコード数が**一致しない** → 取りこぼしの可能性。
  「〇〇行を採用したのにコードが△△個しかありません。〇〇な行が除外されている可能性があります」と伝える
- 最終ラベルが**極端に少ない**(例: 数百行あるのに10〜20個しかない)
  → 「明らかに少なすぎます。列の指定か、利用区分の値が違うかもしれません」と伝えて確認する
- 1段目(いちばん上の分類)が**1個しかない、または30個以上ある**
  → 列の指定違いの可能性が高いので確認する
- **同じコードが複数の場所**にある → その一覧を見せて確認する
- 1つの段の選択肢が20個を超える → 判定の精度が落ちやすいので、参考情報として伝える

### ステップ5: 出力する

問題がなければ、2つのツリーを**そのままコピーできる形**(コードブロック)で出力してください。

**7桁ツリーも、10桁ツリーとまったく同じ「罫線つきのツリー」の形で出してください。**

### 正しい出力の形(7桁ツリー)

```
区分判定(1段目)
├─ 流動資産
│   ├─ 現預金・有価証券・貸付金
│   │   ├─ 現金・預金   [1101001]
│   │   └─ 有価証券     [1101002]
│   └─ 営業債権・その他の債権
│       ├─ 受取手形     [1102001]
│       └─ 売掛金       [1102002]
└─ 営業費用
    └─ 経費
        ├─ 交際費       [5102002]
        └─ 会議費       [5102003]
```

### 間違った出力の形(絶対にこうしないこと)

```
1101001
1101002
1102001
1102002
...
```

7桁コードだけを並べた一覧は**完全な誤り**です。7桁ツリーは
「10桁ツリーから、コードの上7桁が同じになる段まで枝を刈り込んだもの」であり、
**枝分かれの形は10桁ツリーと同じ**です(末端が浅くなるだけです)。

### 出力する前の自己チェック(必ず行う)

出力しようとしている7桁ツリーについて、次を確認してください。
1つでも当てはまらなければ**間違いなので作り直す**こと。

- [ ] 1行目が `区分判定(1段目)` になっている
- [ ] `├─` `└─` `│` の罫線が使われている
- [ ] **各行に日本語の科目名(ラベル)がある**(数字だけの行が1つもない)
- [ ] 10桁ツリーと**同じ枝分かれ**になっている(上の方の階層が一致する)
- [ ] 最終ラベルの数が、10桁ツリーの最終ラベル数**以下**になっている

ツリーの見方も一言添えてください:

- 配下が無い行が最終ラベル(そこで判定が終わる)
- 右側の `[...]` が勘定科目コード

## Pythonを実行できない環境の場合

コードを実行できないときは、**まず最初に「このコードを実行できないので、手作業で同じ処理を行います」と
はっきり伝えてください**(黙って手作業に切り替えないこと)。

手作業で行う場合も、**出力の形は上の「正しい出力の形」と完全に同じ**にしてください。
罫線つきのツリーであること、各行に科目名があることを必ず守り、
上記の自己チェックと件数の報告も必ず行ってください。
行数が多くて一度に扱えない場合は、「〇〇行あるので分割して進めます」と伝えてから進めること。

## 変換のルール(プログラムが行っている処理)

- 既定の列: **B列=勘定科目区分1 / C列=勘定科目区分2 / D列=勘定科目明細 / E列=勘定科目コード / J列=利用区分**
  (見出しの文言では判断せず、**列の位置**で読む)
- **利用区分が「まる」の行だけ**を採用(○ ◯ 〇 のどれでも同じ扱い)。この絞り込みを最初に行う
- **勘定科目明細に入っているスラッシュ(／ や /)は階層に展開**する
  例: 「現金・預金／現金」→ 2段、「貸付金／短期貸付金／3ヶ月以内」→ 3段、「売上」→ 1段
- 同じ名前が続く階層は1段に畳む(「受取手形／受取手形」→ 1段)
- 区分1・区分2が空欄の行は、直前の行の値を引き継ぐ(結合セル対策)
- 合計行・空行は飛ばす。前後の空白(全角含む)は削る
- コードは10桁に揃える(Excelで数値になって先頭の0が落ちた場合の救済)

==============================================================================
  ここから下はプログラムです(チャットAIは読み飛ばして構いません)
==============================================================================
"""
import argparse
import csv
import io
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NSR = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ROLES = ['l1', 'l2', 'l3', 'code', 'use']
ROLE_JP = {'l1': '勘定科目区分1', 'l2': '勘定科目区分2', 'l3': '勘定科目明細',
           'code': '勘定科目コード', 'use': '利用区分'}
DEFAULT_COLS = 'B,C,D,E,J'
CIRCLES = '○◯〇'
SKIP_WORDS = ('合計', '小計', '総計', '計', '※', '備考', '以上')


def norm(text):
    return text.replace('　', ' ').strip()


ZEN2HAN = dict(zip(range(0xff10, 0xff1a), '0123456789'))


def norm_code(text):
    """コード欄の値をそろえる(全角数字→半角、空白・カンマ除去)"""
    return norm(text).translate(ZEN2HAN).replace(' ', '').replace(',', '').replace('\u3000', '')


def parse_count(text):
    """データ件数の値を整数にする。読めなければ None(見出し行など)"""
    c = norm(text).translate(ZEN2HAN).replace(',', '').replace(' ', '')
    if not c:
        return None
    try:
        return int(float(c))
    except ValueError:
        return None


def read_freq_rows(rows):
    """「よく使う勘定科目リスト」(A=勘定科目コード / B=科目名 / C=データ件数)を読む。
    コードが数字でない行・件数が読めない行(見出しなど)は飛ばす。"""
    entries = []
    for row in rows:
        code = norm_code(row[0] if len(row) > 0 else '')
        label = norm(row[1]) if len(row) > 1 else ''
        cnt = parse_count(row[2] if len(row) > 2 else '')
        if not code or not code.isdigit() or cnt is None:
            continue
        entries.append((code, label, cnt))
    return entries


def freq_select(entries, fmin, ftop, digits):
    """条件(件数fmin以上 / 件数の多い順に上位ftop)に該当するコードを選ぶ。
    返り値は {コード: (件数, 科目名)}。同じコードが複数行あれば件数の大きい方を採る。"""
    best = {}
    order = []
    for code, label, cnt in entries:
        c = code.zfill(digits) if (digits and len(code) < digits) else code
        if c not in best:
            order.append(c)
            best[c] = (cnt, label)
        elif cnt > best[c][0]:
            best[c] = (cnt, label)
    items = [(c, best[c][0], best[c][1]) for c in order]
    if fmin:
        items = [x for x in items if x[1] >= fmin]
    if ftop:
        items = sorted(items, key=lambda x: -x[1])[:ftop]
    return dict((c, (cnt, label)) for c, cnt, label in items)


def same_mark(a, b):
    a, b = norm(a), norm(b)
    if len(a) == 1 and len(b) == 1 and a in CIRCLES and b in CIRCLES:
        return True
    return a == b


def dwidth(text):
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in text)


def col_index(ref):
    m = re.match(r'([A-Z]+)', ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def letter(idx):
    s, n = '', idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx(path, sheet_name=None):
    """xlsxを標準ライブラリだけで読む。(シート名, 行のリスト, 全シートの一覧) を返す"""
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall(NS + 'si'):
                shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = {r.get('Id'): r.get('Target') for r in rels}
        sheets = []
        for sh in wb.find(NS + 'sheets'):
            t = target.get(sh.get(NSR + 'id'), '')
            t = t[1:] if t.startswith('/') else (t if t.startswith('xl/') else 'xl/' + t)
            sheets.append((sh.get('name'), t))
        if not sheets:
            raise ToolError('シートが1枚もありません。別のファイルか確認してください。')
        if sheet_name:
            hit = [s for s in sheets if s[0] == sheet_name]
            if not hit:
                raise ToolError('シート「%s」がありません。このファイルのシートは %s です。'
                                'どれを使うか利用者に確認してください。'
                                % (sheet_name, '、'.join('「%s」' % s[0] for s in sheets)))
            name, part = hit[0]
        else:
            name, part = sheets[0]

        def rows_of(part):
            ws = ET.fromstring(z.read(part))
            out = []
            for row in ws.iter(NS + 'row'):
                cells = {}
                for c in row.findall(NS + 'c'):
                    ref, ctype = c.get('r'), c.get('t')
                    v = c.find(NS + 'v')
                    if ctype == 's' and v is not None:
                        val = shared[int(v.text)]
                    elif ctype == 'inlineStr':
                        is_ = c.find(NS + 'is')
                        val = ''.join(t.text or '' for t in is_.iter(NS + 't')) if is_ is not None else ''
                    elif v is not None:
                        val = v.text or ''
                    else:
                        val = ''
                    cells[col_index(ref)] = val.strip()
                out.append([cells.get(i, '') for i in range(max(cells) + 1)] if cells else [])
            return out

        allsheets = [(nm, len(rows_of(pt))) for nm, pt in sheets]
        return name, rows_of(part), allsheets


class ToolError(Exception):
    """利用者への説明つきのエラー(そのまま質問に使える文面)"""


def read_table(path, sheet_name=None):
    if not os.path.exists(path):
        raise ToolError('ファイルが見つかりません: %s' % path)
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.csv', '.tsv', '.txt'):
        delim = '\t' if ext == '.tsv' else ','
        with io.open(path, encoding='utf-8-sig', newline='') as f:
            rows = [[c.strip() for c in r] for r in csv.reader(f, delimiter=delim)]
        return os.path.basename(path), rows, [(os.path.basename(path), len(rows))]
    if ext != '.xlsx':
        raise ToolError('.xlsx か .csv を渡してください(渡されたのは %s)。'
                        '.xls の場合はExcelで .xlsx として保存し直してもらってください。' % (ext or '拡張子なし'))
    return read_xlsx(path, sheet_name)


def parse_cols(spec):
    parts = [p.strip().upper() for p in spec.split(',')]
    if len(parts) != len(ROLES):
        raise ToolError('--cols は「区分1,区分2,明細,コード,利用区分」の5列を指定してください(既定: %s)' % DEFAULT_COLS)
    out = {}
    for role, lt in zip(ROLES, parts):
        if not re.match(r'^[A-Z]+$', lt):
            raise ToolError('列の指定が不正です: %r(A, B, AA のような形式で指定してください)' % lt)
        n = 0
        for ch in lt:
            n = n * 26 + (ord(ch) - 64)
        out[role] = n - 1
    return out


def find_start_row(rows, cols):
    ci, li = cols['code'], cols['l1']
    for i, row in enumerate(rows):
        code = norm(row[ci]) if ci < len(row) else ''
        l1 = norm(row[li]) if li < len(row) else ''
        if l1 and code and re.match(r'^[0-9]+$', code):
            return i
    return None


# ---------------------------------------------------------------- ツリー

class Node(object):
    def __init__(self, label):
        self.label = label
        self.children = []
        self.index = {}
        self.code = None
        self.full = None
        self.parent = None

    def child(self, label):
        if label not in self.index:
            n = Node(label)
            n.parent = self
            self.index[label] = n
            self.children.append(n)
        return self.index[label]

    @property
    def leaf(self):
        return not self.children

    def path(self):
        out, n = [], self
        while n.parent is not None:
            out.append(n.label)
            n = n.parent
        return list(reversed(out))


def iter_all(n):
    for c in n.children:
        yield c
        for x in iter_all(c):
            yield x


def build(records):
    root = Node('(root)')
    seen, dup, conflict = {}, 0, []
    for path, code in records:
        n = root
        for label in path:
            n = n.child(label)
        key = tuple(path)
        if key in seen:
            dup += 1
            if code and seen[key] and code != seen[key]:
                conflict.append((key, seen[key], code))
            continue
        seen[key] = code
        n.full = code or None
    return root, dup, conflict


def add_self_leaves(root):
    """自分にもコードがあり、かつ配下も持つ節に「自分を表す葉」を足す"""
    added = []

    def walk(n):
        for c in list(n.children):
            walk(c)
        if n.parent is not None and n.full and n.children:
            leaf = Node(n.label)
            leaf.full = n.full
            leaf.parent = n
            n.children.insert(0, leaf)
            n.index[leaf.label] = leaf
            n.full = None
            added.append('/'.join(n.path()))
    walk(root)
    return added


def assign_codes(root):
    for n in iter_all(root):
        if n.leaf and n.full:
            n.code = n.full


def prune_to_prefix(root, split):
    """コードの上N桁が確定する段まで遡って刈り込む"""

    def prefixes(n):
        if n.leaf:
            return set([n.full[:split]]) if (n.full and len(n.full) >= split) else set()
        out = set()
        for c in n.children:
            out |= prefixes(c)
        return out

    def copy_pruned(n):
        new = Node(n.label)
        ps = prefixes(n)
        if len(ps) == 1:
            new.code = list(ps)[0]
            return new
        for c in n.children:
            cp = copy_pruned(c)
            if cp is None:
                continue
            cp.parent = new
            new.children.append(cp)
            new.index[cp.label] = cp
        return new if new.children else None

    out = copy_pruned(root)
    if out is not None:
        out.parent = None
    return out


def duplicate_branch_names(root):
    """同じ名前の「分岐」が別の場所にもある場合を検出する
    (Difyワークフローを作る段階で、分岐名は全体で一意である必要があるため)"""
    seen = {}
    for n in iter_all(root):
        if not n.leaf:
            seen.setdefault(n.label, []).append('/'.join(n.path()))
    return [(k, v) for k, v in seen.items() if len(v) > 1]


def depth_stats(root):
    """最終ラベルの深さの分布(1=最上段の直下)"""
    out = {}

    def walk(n, d):
        for c in n.children:
            if c.leaf:
                out[d] = out.get(d, 0) + 1
            else:
                walk(c, d + 1)
    walk(root, 1)
    return out


def merge_same_code(n):
    """7桁ツリーの整理: 同じコードになる兄弟をまとめ、全部同じなら親を葉にする"""
    for c in list(n.children):
        merge_same_code(c)
    if n.children and all(c.leaf and c.code for c in n.children) \
            and len(set(c.code for c in n.children)) == 1:
        n.code = n.children[0].code      # 配下が全部同じコード → この段で確定
        n.children = []
        n.index = {}
        return
    out, group = [], {}
    for c in n.children:
        if c.leaf and c.code and c.code in group:
            group[c.code].append(c.label)   # 同じコードの兄弟は先頭にまとめる
            continue
        out.append(c)
        if c.leaf and c.code:
            group[c.code] = [c.label]
    for c in out:
        names = group.get(c.code or '', [])
        if len(names) > 1:
            c.label = '・'.join(names[:5]) + ('' if len(names) <= 5 else ' ほか%d件' % (len(names) - 5))
    n.children = out
    n.index = dict((c.label, c) for c in out)


def count_codes(root):
    codes = [n.code for n in iter_all(root) if n.code]
    by_len = {}
    for c in codes:
        by_len[len(c)] = by_len.get(len(c), 0) + 1
    seen, dup = set(), []
    for c in codes:
        if c in seen and c not in dup:
            dup.append(c)
        seen.add(c)
    return len(codes), by_len, dup


def render(root, root_label):
    rows = []

    def walk(n, prefix):
        for i, c in enumerate(n.children):
            last = i == len(n.children) - 1
            rows.append((prefix + ('└─ ' if last else '├─ ') + c.label, c.code or ''))
            walk(c, prefix + ('    ' if last else '│   '))
    walk(root, '')
    width = max([dwidth(t) for t, c in rows if c] or [0])
    lines = [root_label + '(1段目)']
    for text, code in rows:
        lines.append(text + ' ' * (width - dwidth(text) + 1) + '[%s]' % code if code else text)
    return '\n'.join(lines)


def leaves(root):
    return [n for n in iter_all(root) if n.leaf]


def branches(root):
    return [n for n in iter_all(root) if not n.leaf]


# ---------------------------------------------------------------- 下見

def preview(path, args):
    sheet, rows, allsheets = read_table(path, args.sheet)
    print('■ ファイル: %s' % os.path.basename(path))
    print('■ シート: %d枚' % len(allsheets))
    for nm, cnt in allsheets:
        mark = ' ← 今回読む' if nm == sheet else ''
        print('   ・「%s」 %d行%s' % (nm, cnt, mark))
    if len(allsheets) > 1 and not args.sheet:
        print('   ※ シートが複数あります。これでよいか利用者に確認してください(--sheet で指定できます)')

    cols = parse_cols(args.cols)
    print('')
    print('■ 読む列(既定): ' + ' / '.join('%s=%s列' % (ROLE_JP[r], letter(cols[r])) for r in ROLES))
    width = max([len(r) for r in rows[:20]] or [0])
    print('■ 先頭の中身(A〜%s列):' % letter(max(width - 1, 9)))
    for i, row in enumerate(rows[:8]):
        cells = [(row[j] if j < len(row) else '') for j in range(min(max(width, 10), 12))]
        print('   %2d行目: %s' % (i + 1, ' | '.join(c[:14] or '-' for c in cells)))

    start = find_start_row(rows, cols)
    print('')
    if start is None:
        print('■ データの開始行: 見つかりませんでした')
        print('   ※ 「区分1の列に文字があり、コードの列が数字だけ」の行が見つかりません。')
        print('     列の指定が違う可能性が高いです。上の中身を見て、利用者に列を確認してください。')
    else:
        print('■ データの開始行: %d行目(それより上は見出しとみなします)' % (start + 1))

    # 「まる」が並んでいる列を探す
    print('')
    print('■ 「まる」が入っている列の候補:')
    found = False
    scan = rows[start:] if start is not None else rows
    for j in range(min(max([len(r) for r in scan] or [0]), 30)):
        vals = [norm(r[j]) for r in scan if j < len(r) and norm(r[j])]
        circ = [v for v in vals if len(v) == 1 and v in CIRCLES]
        if vals and len(circ) >= max(3, len(vals) * 0.3):
            found = True
            note = ' ← 既定で使う列' if j == cols['use'] else ''
            print('   ・%s列: まる %d個 / 値あり %d行%s' % (letter(j), len(circ), len(vals), note))
    if not found:
        print('   ・見つかりませんでした')
        if start is not None:
            j = cols['use']
            vals = {}
            for r in scan:
                v = norm(r[j]) if j < len(r) else ''
                vals[v] = vals.get(v, 0) + 1
            print('   ※ %s列の値の内訳: %s' % (letter(j),
                  '、'.join('%s:%d件' % (k or '(空)', v) for k, v in sorted(vals.items(), key=lambda x: -x[1])[:6])))
            print('     ○ではない印で管理している可能性があります。どの値が対象か利用者に確認してください。')

    print('')
    print('次: 問題なければ --check を外して実行してください。'
          '列やシートを変える場合は --sheet / --cols / --use を付けます。')


# ---------------------------------------------------------------- 実行

def convert_rows(rows, cols, o):
    """行データ(2次元配列)と列マップから、ツリー・対応表・検算結果を作る。

    ファイルを読む処理から切り離してあるので、CSVやテーブルなど
    Excel以外の入力からも同じ結果を得られる。
    o は use / detail_sep / code_digits / split / sep / root / start_row を持つオブジェクト。
    """
    start = (getattr(o, 'start_row', 0) - 1) if getattr(o, 'start_row', 0) else find_start_row(rows, cols)
    if start is None:
        raise ToolError('データの開始行が見つかりませんでした。'
                        '「区分1の列に文字があり、コードの列が数字だけ」の行がありません。\n'
                        '→ 利用者に「勘定科目区分1・勘定科目コードはそれぞれ何列ですか?」と確認してください'
                        '(--check を付けて実行すると各列の中身を確認できます)。')

    exclude = [norm(x) for x in (getattr(o, 'exclude', None) or []) if norm(x)]
    ex_hits = dict((e, 0) for e in exclude)
    freq_entries = getattr(o, 'freq_entries', None)
    freq_allowed = None
    if freq_entries:
        freq_allowed = freq_select(freq_entries, getattr(o, 'freq_min', 0) or 0,
                                   getattr(o, 'freq_top', 0) or 0, o.code_digits or 0)
    freq_hits, freq_dropped = set(), 0
    records, skipped, blank, junk, collapsed, split_rows, excluded = [], 0, 0, 0, 0, 0, 0
    carry = {'l1': '', 'l2': ''}
    for row in rows[start:]:
        def get(role):
            j = cols[role]
            return norm(row[j]) if j < len(row) else ''
        if o.use and not same_mark(get('use'), o.use):
            skipped += 1
            continue
        l1, l2, l3, code = get('l1'), get('l2'), get('l3'), get('code')
        if l1:
            carry['l1'] = l1
            if not l2:
                carry['l2'] = ''
        else:
            l1 = carry['l1']
        if l2:
            carry['l2'] = l2
        else:
            l2 = carry['l2']
        if not (l1 or l2 or l3):
            blank += 1
            continue
        if not l1 or (not l3 and not l2):
            junk += 1
            continue
        if any(w == l3 or l3.startswith(w) for w in SKIP_WORDS):
            junk += 1
            continue
        details = [norm(x) for x in re.split('[' + re.escape(o.detail_sep) + ']', l3) if norm(x)]
        if len(details) > 1:
            split_rows += 1
        parts = [l1, l2] + details
        path_parts = []
        for part in parts:
            if part and (not path_parts or path_parts[-1] != part):
                path_parts.append(part)
        if len(path_parts) < len([p for p in parts if p]):
            collapsed += 1
        if exclude:
            padded_code = code.zfill(o.code_digits) if (code.isdigit() and o.code_digits
                                                        and len(code) < o.code_digits) else code
            hit = next((e for e in exclude if e == code or e == padded_code), None) \
                or next((e for e in exclude if e in path_parts), None)
            if hit is not None:
                ex_hits[hit] += 1
                excluded += 1
                continue
        if freq_allowed is not None:
            cc = norm_code(code)
            padded = cc.zfill(o.code_digits) if (o.code_digits and cc.isdigit()
                                                 and len(cc) < o.code_digits) else cc
            key = padded if padded in freq_allowed else (cc if cc in freq_allowed else None)
            if key is None:
                freq_dropped += 1
                continue
            freq_hits.add(key)
        records.append((path_parts, code))

    total_data = len(rows) - start
    if not records and freq_allowed is not None:
        raise ToolError('よく使う科目リストの条件に一致する行が1行もありませんでした'
                        '(リスト %d科目のうち条件該当 %d科目、マスタとの一致 0件)。\n'
                        '→ コードの桁数がマスタと合っているか、条件が厳しすぎないかを確認してください。'
                        % (len(freq_entries), len(freq_allowed)))
    if not records:
        raise ToolError('使える行が1行もありませんでした(%d行を見て、利用区分「%s」に一致する行がありません)。\n'
                        '→ 利用者に「自社で使っている印は何ですか?(○ / 1 / 使用 など)」'
                        'または「利用区分は何列ですか?」と確認してください。' % (total_data, o.use))

    # コードの桁揃え
    digits = o.code_digits
    padded = 0
    if digits:
        fixed = []
        for p, c in records:
            if c and c.isdigit() and len(c) < digits:
                c = c.zfill(digits)
                padded += 1
            fixed.append((p, c))
        records = fixed

    root, dup, conflict = build(records)
    root2, _, _ = build(records)
    self_leaves = add_self_leaves(root)
    add_self_leaves(root2)
    assign_codes(root)

    root7 = prune_to_prefix(root2, o.split) if o.split else None
    if root7 is not None:
        merge_same_code(root7)

    # ---- 異常の検出(利用者への確認が必要なもの)
    warn = []
    t10, by10, dup10 = count_codes(root)
    lv10 = len(leaves(root))
    if root7 is not None:
        t7, by7, dup7 = count_codes(root7)
        d7 = depth_stats(root7)
        if not d7:
            warn.append('%d桁ツリーが作れませんでした(全コードの上%d桁が同じ値です)。'
                        'コードの列か、--split の桁数を確認してください' % (o.split, o.split))
        elif max(d7) <= 1:
            warn.append('%d桁ツリーが階層構造になっていません(すべて1段目)。'
                        'ツリーではなく一覧になっているので、列の指定かコードの体系を確認してください' % o.split)
        if dup7:
            warn.append('%d桁ツリーで同じコードが複数の場所にあります(%d種類。例: %s)'
                        % (o.split, len(dup7), '、'.join(dup7[:3])))
    if t10 != len(records):
        warn.append('採用した %d行に対してコードが %d個しかありません(コードが空の行がある可能性)'
                    % (len(records), t10))
    if len(by10) > 1:
        warn.append('コードの桁数がそろっていません(%s)。--code-digits で桁を指定できます'
                    % '、'.join('%d桁 %d個' % (k, v) for k, v in sorted(by10.items())))
    if dup10:
        warn.append('同じコードが複数の場所にあります(%d種類。例: %s)' % (len(dup10), '、'.join(dup10[:3])))
    if len(root.children) <= 1:
        warn.append('1段目(いちばん上の分類)が %d個しかありません。列の指定が違う可能性があります'
                    % len(root.children))
    if len(root.children) >= 30:
        warn.append('1段目が %d個もあります。区分1ではなく別の列を読んでいる可能性があります'
                    % len(root.children))
    if exclude:
        miss = [e for e, k in ex_hits.items() if k == 0]
        if miss:
            warn.append('除外リストの %s に一致する行がありません(書き間違いの可能性)'
                        % '、'.join('「%s」' % e for e in miss[:5]))
    if freq_allowed is not None:
        fmiss = [c for c in freq_allowed if c not in freq_hits]
        if fmiss:
            warn.append('よく使う科目リストの %d科目がマスタに見つかりません(例: %s)。'
                        'コードの桁数や体系が合っているか確認してください'
                        % (len(fmiss), '、'.join('%s %s' % (c, freq_allowed[c][1]) for c in fmiss[:3])))
    if total_data >= 50 and lv10 < total_data * 0.2:
        warn.append('データ %d行に対して最終ラベルが %d個しかありません(明らかに少なすぎます)。'
                    '利用区分の値か、列の指定が違う可能性があります' % (total_data, lv10))
    for k, v in conflict[:3]:
        warn.append('経路「%s」に別のコードが付いています(%s と %s)' % (o.sep.join(k), v[0], v[1]))

    tree10 = header('10桁(勘定科目コードを最後まで特定する)') + '```\n' + render(root, o.root) + '\n```\n'
    tree7 = None
    if root7 is not None:
        tree7 = (header('%d桁(共通部分だけを特定する)' % o.split)
                 + '```\n' + render(root7, o.root) + '\n```\n')

    return {'records': records, 'root': root, 'root7': root7,
            'tree10': tree10, 'tree7': tree7,
            'map_rows': [(o.sep.join(p), c) for p, c in records],
            'warn': warn, 'start': start, 'total_data': total_data,
            'skipped': skipped, 'blank': blank, 'junk': junk, 'collapsed': collapsed,
            'split_rows': split_rows, 'self_leaves': self_leaves, 'padded': padded,
            'digits': digits, 'dup': dup, 'conflict': conflict,
            'excluded': excluded, 'ex_miss': [e for e, k in ex_hits.items() if k == 0],
            'freq_total': len(freq_entries) if freq_entries else 0,
            'freq_selected': len(freq_allowed) if freq_allowed is not None else 0,
            'freq_used': len(freq_hits), 'freq_dropped': freq_dropped,
            'freq_active': freq_allowed is not None,
            'dupname': duplicate_branch_names(root)}


def report_lines(res, o, paths=None):
    """検算レポートの行を組み立てる(CLIでもHTML版でも同じ文面を使う)"""
    paths = paths or {}
    out = []
    out.append('■ 読み取り: %d行を採用 / 利用区分で対象外 %d行 / 除外リスト %d行 / 空行 %d行 / 合計・注記など %d行'
               % (len(res['records']), res['skipped'], res.get('excluded', 0),
                  res['blank'], res['junk']))
    if res['split_rows']:
        out.append('  ・%d行で、明細のスラッシュを階層に展開しました' % res['split_rows'])
    if res['collapsed']:
        out.append('  ・%d行で、同じ名前が続く階層を1段に畳みました' % res['collapsed'])
    if res['self_leaves']:
        out.append('  ・%d箇所で「自分を表す葉」を足しました(例: %s)'
                   % (len(res['self_leaves']), '、'.join(res['self_leaves'][:2])))
    if res['padded']:
        out.append('  ・コード %d件を %d桁に揃えました(先頭の0を補完)' % (res['padded'], res['digits']))
    if res['dup']:
        out.append('  ・同じ経路の重複 %d件(先に出てきた行を採用)' % res['dup'])
    if res.get('excluded'):
        out.append('  ・除外リストで %d行を除外しました' % res['excluded'])
    if res.get('freq_active'):
        cond = []
        if getattr(o, 'freq_min', 0):
            cond.append('データ件数 %d件以上' % o.freq_min)
        if getattr(o, 'freq_top', 0):
            cond.append('件数の多い順に上位 %d科目' % o.freq_top)
        out.append('■ よく使う科目リストで絞り込み: リスト %d科目 → 条件該当 %d科目(%s)'
                   % (res['freq_total'], res['freq_selected'], ' / '.join(cond) or '条件なし=リスト全部'))
        out.append('  ・マスタと一致してツリーに採用: %d科目 / リスト外のため対象外: %d行'
                   % (res['freq_used'], res['freq_dropped']))

    root, root7 = res['root'], res['root7']
    t10, by10, _ = count_codes(root)
    fmt = lambda by: '、'.join('%d桁 %d個' % (k, v) for k, v in sorted(by.items()))
    out.append('')
    out.append('■ 10桁ツリー: 最終ラベル %d個 / 判定の段 %d個 / 1段目 %d個'
               % (len(leaves(root)), len(branches(root)), len(root.children)))
    out.append('  コード %d個(%s)' % (t10, fmt(by10)))
    if paths.get('tree10'):
        out.append('  → %s' % paths['tree10'])
    if root7 is not None:
        t7, by7, _ = count_codes(root7)
        d7 = depth_stats(root7)
        out.append('■ %d桁ツリー: 最終ラベル %d個 / 判定の段 %d個'
                   % (o.split, len(leaves(root7)), len(branches(root7))))
        out.append('  コード %d個(%s)' % (t7, fmt(by7)))
        out.append('  最終ラベルの深さ: %s'
                   % '、'.join('%d段目 %d個' % (k, v) for k, v in sorted(d7.items())))
        if paths.get('tree7'):
            out.append('  → %s' % paths['tree7'])
    if paths.get('map'):
        out.append('■ 対応表: %s' % paths['map'])

    if res.get('dupname'):
        dn = res['dupname']
        out.append('')
        out.append('■ 参考: 同じ名前の中間段階が %d件あります(別のものとして扱うので問題ありません)' % len(dn))
        for label, paths in dn[:5]:
            out.append('   ・%s … %s' % (label, ' / '.join(paths[:3])))

    wide = sorted(((len(b.children), '/'.join(b.path())) for b in branches(root)), reverse=True)
    if wide and wide[0][0] > 20:
        out.append('')
        out.append('■ 参考: 選択肢が20を超える段があります(1回の判定で選ぶ数が多いと精度が落ちやすい)')
        for cnt, p in wide[:5]:
            if cnt > 20:
                out.append('   ・%s … %d択' % (p, cnt))

    out.append('')
    if res['warn']:
        out.append('■ 確認してほしいこと(このまま進めず、利用者に聞いてください):')
        for w in res['warn']:
            out.append('   ! ' + w)
    else:
        out.append('■ 検算: 数字に不自然な点はありません(採用行数とコード数が一致しています)')
    return out


def convert(path, args):
    sheet, rows, allsheets = read_table(path, args.sheet)
    cols = parse_cols(args.cols)
    ex = [x for x in (args.exclude or '').split(',') if norm(x)]
    if getattr(args, 'exclude_file', None):
        for line in io.open(args.exclude_file, encoding='utf-8-sig'):
            line = norm(line)
            if line and not line.startswith('#'):
                ex.append(line)
    args.exclude = ex
    args.freq_entries = None
    if getattr(args, 'freq', None):
        _, frows, _ = read_table(args.freq)
        args.freq_entries = read_freq_rows(frows)
        if not args.freq_entries:
            raise ToolError('よく使う科目リスト %s から科目を読めませんでした。\n'
                            'A列=勘定科目コード / B列=科目名 / C列=データ件数 の並びか確認してください。'
                            % args.freq)
    res = convert_rows(rows, cols, args)

    print('■ シート「%s」/ データ %d行目から' % (sheet, res['start'] + 1))
    print('  読む列: ' + ' / '.join('%s=%s列' % (ROLE_JP[r], letter(cols[r])) for r in ROLES))

    with io.open(args.output, 'w', encoding='utf-8') as f:
        f.write(res['tree10'])
    if res['tree7'] is not None:
        with io.open(args.tree7, 'w', encoding='utf-8') as f:
            f.write(res['tree7'])
    with io.open(args.mapfile, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['経路', '勘定科目コード'])
        for p, c in res['map_rows']:
            w.writerow([p, c])

    print('')
    paths = {'tree10': args.output, 'map': args.mapfile}
    if res['tree7'] is not None:
        paths['tree7'] = args.tree7
    for line in report_lines(res, args, paths):
        print(line)


def header(kind):
    return ('''# 分類ツリー — %s

このツリーは勘定科目マスタ(Excel)から自動生成したものです。

見方:
- **配下が無い行が最終ラベル**です(そこで判定が終わります)
- 右側の `[...]` が勘定科目コードです

''' % kind)


def main():
    ap = argparse.ArgumentParser(description='勘定科目マスタのExcelから分類ツリーを作る')
    ap.add_argument('excel', help='Excelファイル(.xlsx)または CSV')
    ap.add_argument('--check', action='store_true', help='下見だけする(ファイルを出力しない)')
    ap.add_argument('--sheet', help='シート名(既定: 最初のシート)')
    ap.add_argument('--cols', default=DEFAULT_COLS, help='区分1,区分2,明細,コード,利用区分 の列(既定: %s)' % DEFAULT_COLS)
    ap.add_argument('--start-row', type=int, default=0, help='データが始まる行(1始まり。既定: 自動判定)')
    ap.add_argument('--use', default='○', help="利用区分がこの値の行だけ使う(既定: ○。--use '' で全行)")
    ap.add_argument('--exclude', default='', help='除外する科目(科目名かコードを「,」区切りで)')
    ap.add_argument('--exclude-file', help='除外する科目の一覧ファイル(1行に1つ。#で始まる行は無視)')
    ap.add_argument('--freq', help='よく使う勘定科目リスト(.xlsx/.csv。A=コード/B=科目名/C=データ件数)。'
                                   '指定するとリストに該当する科目だけでツリーを作る')
    ap.add_argument('--freq-min', type=int, default=0, help='データ件数がこの値以上の科目だけ使う')
    ap.add_argument('--freq-top', type=int, default=0, help='件数の多い順に上位この数の科目だけ使う')
    ap.add_argument('--sep', default='／', help='対応表で経路をつなぐ区切り')
    ap.add_argument('--detail-sep', default='／/', help='勘定科目明細を階層に分ける区切り文字')
    ap.add_argument('--split', type=int, default=7, help='7桁ツリーの桁数(0で作らない)')
    ap.add_argument('--code-digits', type=int, default=10, help='コードの桁数(0で桁揃えしない)')
    ap.add_argument('--root', default='区分判定', help='ツリー最上段の名前')
    ap.add_argument('-o', '--output', default='分類ツリー_10桁.md')
    ap.add_argument('--tree7', default='分類ツリー_7桁.md')
    ap.add_argument('--map', dest='mapfile', default='対応表.csv')
    args = ap.parse_args()
    try:
        if args.check:
            preview(args.excel, args)
        else:
            convert(args.excel, args)
    except ToolError as e:
        print('')
        print('■ 処理を続けられませんでした')
        print(str(e))
        print('')
        print('※ このメッセージをそのまま利用者に伝えず、内容をかみくだいて質問してください。')
        sys.exit(1)
    except zipfile.BadZipFile:
        print('■ Excelファイルとして開けませんでした。'
              'ファイルが壊れているか、.xls 形式の可能性があります。'
              '利用者に「Excelで開いて .xlsx として保存し直してもらえますか?」と伝えてください。')
        sys.exit(1)


if __name__ == '__main__':
    main()
