#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  分類ツリー検査 — 指示書 兼 検算プログラム(このファイル1つで完結します)
==============================================================================

■ 使い方A: チャットAIに検査してもらう(社内パイロットなど。これだけでOK)

    1. このファイルの中身を全部コピーして、チャットAIに貼る
    2. 続けて「分類ツリー.md」の中身を貼る
    3. AIが下の【AIへの指示】に従って検査し、修正後のツリー全体を返します

■ 使い方B: 返ってきたツリーを機械で検算する(任意・Python 3だけで動きます)

    python3 ツリー検査.py 修正後のツリー.md
    python3 ツリー検査.py 修正後のツリー.md -b 元のツリー.md   # 何がどこへ動いたかも表示

==============================================================================
【AIへの指示】 ここから下は、このファイルがチャットに貼られた場合の指示です。
==============================================================================

あなたは日本の企業会計に精通した経理・会計の専門家です。
一緒に貼られた「分類ツリー」を検査し、誤って配置されているラベルを直してください。

このツリーは「10桁まで特定するツリー」でも「7桁まで特定するツリー」でも構いません。
どちらも同じやり方で検査できます(コードの桁数は判定に影響しません)。

## このツリーの性質(重要)

契約書を上の段から順に「選択肢を1つ選んで下りていく」構造です。
そのため、**浅い段で選択肢を間違えると、下流では絶対に正解にたどり着けません**。
ラベルが誤った親の配下にあると、正しい経路自体が存在しないことになります。
だから「各選択肢が、その親の意味範囲に本当に含まれるか」が最重要です。

## ツリーの読み方

    区分判定(1段目)
    ├─ 流動資産
    │   ├─ 現預金・有価証券・貸付金
    │   │   ├─ 現金・預金
    │   │   │   ├─ 現金       [1101001001]
    │   │   │   └─ 預金       [1101001002]
    │   │   └─ 有価証券        [1101002001]
    └─ 営業費用
        └─ ...

    ├─ / └─ … 枝。インデント1段 = 半角スペース4つ分(「│   」または「    」)
    配下が無い行 … 最終ラベル(そこで判定が終わる)
    [1101001001] … 勘定科目コード(その最終ラベルに対応する番号)

次の記号が付いていることもありますが、**付いていなくても構いません**:

    ★ … その段で判定が紛れたときの受け皿(付いていなければ後続の処理が自動で決めます)
    ◆ … 最終ラベルの印(付いていなければ「配下が無い行」が最終ラベルです)
    🔒 … 名称変更禁止 / ✏ rules_xxx … 判定基準を外部設定で管理している印
    ラベル: 定義 … コロンの後ろはそのラベルの定義文

## やること

**最も深い段から順に**、1段ずつ次を判定してください。

1. **所属判定(これが本題)**
   その段の各選択肢は、親ラベル(とその定義)の意味範囲に本当に含まれますか?
   含まれないものがあれば、**1階層上へ「昇格」**させてください。
   例: 「現金・預金」の配下に「有価証券」がある → 有価証券は現金でも預金でもないので、
       1つ上の「現預金・有価証券・貸付金」の直下へ移動する

2. **昇格したら、その新しい階層でもう一度判定**してください。
   まだ範囲外なら、さらに1階層上へ。**範囲内に収まるまで繰り返します**(積み上げ式)。
   例: 「デリバティブ資産」は現金・預金の範囲外 → 現預金・有価証券・貸付金へ →
       そこも範囲外 → さらに上の「流動資産」の直下へ

3. **兄弟間の紛れ**(同じ段に意味が重なる選択肢がある)や、
   **定義の曖昧さ**に気づいたら、移動はせずに「指摘」として書き出してください。

## 守ってほしいルール

- 動かしてよいのは**1階層上への昇格だけ**です。別の枝への付け替えは、指摘に留めてください
- 昇格先に**似た項目や同名の項目があっても、統合してはいけません**。別項目として並べてください
- **確信が持てないものは動かさない**でください(指摘に留める)
- ★ が付いている場合、各段にちょうど1つです。★の付いた選択肢を昇格させたら、**その段の別の選択肢に★を付け直して**ください
  (元のツリーに★が無い場合は、こちらでも付けなくて構いません)
- **コード `[...]` は、そのラベルにくっついて動きます。**ラベルを移動したら、コードも一緒に移動させてください
  (コードの数字を書き換えたり、消したりしないこと)
- ラベル名・定義文・記号(◆ ★ 🔒 ✏)も、移動しても**そのまま維持**してください
- **行を勝手に減らさないでください。**最終ラベルの数は、検査の前後で変わらないはずです
  (昇格は「場所を移す」だけで、削除ではありません)
- 🔒 の付いたラベルは名称を変更しないでください

## 返事の書き方

次の3つを、この順で出してください。

**1. 変更した点**
   ・どのラベルを、どこから、どこへ動かしたか
   ・その理由(1行)

**2. 指摘(動かしていないもの)**
   ・兄弟間の紛れ、定義の曖昧さ、別の枝に移した方がよさそうなもの

**3. 修正後のツリー全体**
   ・コードブロックで、**ツリー全体を省略せずに**出力してください
   ・「以下同様」「変更なし」などの省略は使わないでください(そのままファイルに貼れる形で)
   ・枝の記号とインデントは、元のツリーと同じ書式を保ってください
   ・**コード `[...]` も元のまま残してください**

### 出力する前の自己チェック(必ず行う)

1つでも当てはまらなければ**間違いなので作り直す**こと。

- [ ] 1行目が `区分判定(1段目)` になっている
- [ ] `├─` `└─` `│` の罫線が使われている
- [ ] **最終ラベルの数が、元のツリーと同じ**(勝手に減っていない)
- [ ] **コード `[...]` が元と同じ個数だけある**(消えていない・数字が変わっていない)
- [ ] 途中で省略していない(最後の行まで出し切っている)

もし直すところが無ければ、「1. 変更した点」に「なし」と書き、
3 では元のツリーをそのまま出力してください。

==============================================================================
  ここから下はプログラムです(チャットAIは読み飛ばして構いません)
==============================================================================
"""
import argparse
import re
import sys

LINE_RE = re.compile(r'^((?:│   |    )*)(?:├─|└─) (.+)$')


class Node(object):
    def __init__(self, label=''):
        self.label = label
        self.leaf = False
        self.star = False
        self.lock = False
        self.code = None
        self.definition = ''
        self.children = []
        self.parent = None

    @property
    def is_branch(self):
        return bool(self.children)

    def path(self):
        out, n = [], self
        while n.parent is not None:
            out.append(n.label)
            n = n.parent
        return '/'.join(reversed(out))


def pull_code(definition):
    """定義文の前後に紛れ込んだコードを取り出す。
    「ラベル: 定義 [1234]」「ラベル: [1234] 定義」と書かれてもコードを失わないため。"""
    if not definition:
        return None, definition
    m = re.search(r'\s*\[(\d+)\]\s*$', definition)
    if m:
        return m.group(1), definition[:m.start()].strip()
    m = re.match(r'^\[(\d+)\]\s*', definition)
    if m:
        return m.group(1), definition[m.end():].strip()
    return None, definition


def parse(text):
    """ファイル全文(またはツリー部分)から木を組み立てる"""
    if '```' in text:
        blocks = text.split('```')
        # 枝行がいちばん多いブロックをツリーとみなす(AIの返事に説明文が混ざっていても拾える)
        tree = max(blocks, key=lambda b: sum(1 for l in b.split('\n') if LINE_RE.match(l.rstrip())))
    else:
        tree = text
    root = Node('(最上位)')
    stack = [root]
    errors = []
    for lineno, raw in enumerate(tree.split('\n'), 1):
        raw = raw.rstrip()
        if not raw or not raw.lstrip().startswith(('├─', '└─', '│')):
            continue
        m = LINE_RE.match(raw)
        if not m:
            errors.append('行の書式が読めません(インデントは半角スペース4つ単位): %r' % raw)
            continue
        depth = len(m.group(1)) // 4
        if depth >= len(stack):
            errors.append('インデントが飛んでいます: %r' % raw)
            continue
        content = m.group(2)
        n = Node()
        n.leaf = content.startswith('◆ ')
        if n.leaf:
            content = content[2:]
        i = content.find(' …')
        if i >= 0:
            content = content[:i]
        if ': ' in content:
            content, n.definition = content.split(': ', 1)[0], content.split(': ', 1)[1].strip()
        mc = re.search(r' \[(\d+)\]', content)
        if mc:
            n.code = mc.group(1)
            content = content.replace(mc.group(0), '', 1)
        else:
            n.code, n.definition = pull_code(n.definition)
        if '🔒' in content:
            n.lock = True
            content = content.replace('🔒', '')
        j = content.find('★')
        if j >= 0:
            n.star = True
            content = content[:j]
        n.label = content.strip()
        if not n.label:
            errors.append('ラベルが空の行があります: %r' % raw)
            continue
        n.parent = stack[depth]
        stack[depth].children.append(n)
        del stack[depth + 1:]
        stack.append(n)
    return root, errors


def check(root):
    """構造の検算。問題のリストを返す"""
    problems = []
    branch_names = []

    def walk(n, seven):
        stars = [c for c in n.children if c.star]
        if n.children and len(stars) > 1:
            problems.append('「%s」の配下の ★(受け皿)が %d個あります。1つにしてください'
                            % (n.label, len(stars)))
        for c in n.children:
            if c.leaf and c.children:
                problems.append('◆ の行に配下があります: %s' % c.path())

            if c.label.startswith('質問'):
                problems.append('「質問」で始まるラベルは使えません: %s' % c.path())
            if c.is_branch:
                branch_names.append(c.label)
            s = seven
            if c.code is not None:
                if len(c.code) == 7:
                    if s:
                        problems.append('[7桁]の配下に再度[7桁]があります: %s' % c.path())
                    s = c.code
                elif len(c.code) == 3:
                    if not s:
                        problems.append('[3桁]の上位に[7桁]がありません: %s' % c.path())
                elif s and not c.code.startswith(s):
                    problems.append('[7桁]の配下のコードは、[3桁]か、その7桁で始まるフルコードにしてください: %s [%s]'
                                    % (c.path(), c.code))
                elif c.children:
                    problems.append('途中の段に付けるコードは[7桁]にしてください: %s [%s]' % (c.path(), c.code))
            walk(c, s)
    walk(root, None)
    return problems


def leaves(root):
    """最終ラベル(配下が無い行)。◆ が書かれていなくても数えられる"""
    out = []

    def walk(n):
        for c in n.children:
            (out.append(c.path()) if not c.children else walk(c))
    walk(root)
    return out


def positions(root):
    """ラベル -> 親のパス(移動の検出用)"""
    out = {}

    def walk(n):
        for c in n.children:
            out.setdefault(c.label, []).append(n.path() or '(最上位)')
            walk(c)
    walk(root)
    return out


def code_positions(root):
    """コード -> そのコードが付いているノード(修正前後の突き合わせ用)"""
    out = {}
    for n in _all(root):
        if n.code:
            out.setdefault(n.code, []).append(n)
    return out


def _lev(a, b):
    """編集距離(名前の書き換えを見つけるため。長すぎるものは比べない)"""
    if a == b:
        return 0
    if len(a) > 40 or len(b) > 40:
        return abs(len(a) - len(b)) + 99
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i]
        for j in range(1, len(b) + 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1)))
        prev = cur
    return prev[len(b)]


def _similar(a, b):
    if a in b or b in a:
        return True
    return _lev(a, b) <= max(1, int(max(len(a), len(b)) * 0.34))


def compare_trees(before, after):
    """修正前後を突き合わせて (重大, 注意, 参考) を返す。各要素は (見出し, 明細のリスト)"""
    bad, warn, info = [], [], []

    # ---- コードの照合(いちばん大事)
    ca, cb = code_positions(before), code_positions(after)
    lost, added_codes, relabeled = [], [], []
    for code, ns in ca.items():
        if code not in cb:
            lost.append('[%s] %s  (元の位置: %s)' % (code, ns[0].label, ns[0].path()))
            continue
        a = '・'.join(n.label for n in ns)
        b = '・'.join(n.label for n in cb[code])
        if a != b:
            relabeled.append('[%s] 「%s」 → 「%s」' % (code, a, b))
    for code, ns in cb.items():
        if code not in ca:
            added_codes.append('[%s] %s  (位置: %s)' % (code, ns[0].label, ns[0].path()))
    if lost:
        bad.append(('勘定科目コードが %d個 消えています(検査でコードを消してはいけません)' % len(lost), lost))
    if relabeled:
        bad.append(('同じコードなのにラベル名が変わっています %d件(コードとラベルの対応が崩れます)'
                    % len(relabeled), relabeled))
    if added_codes:
        warn.append(('元のツリーに無いコードが %d個 増えています(AIが数字を作った可能性)'
                     % len(added_codes), added_codes))
    # ---- ラベルの照合
    pb, pa = positions(before), positions(after)
    removed_labels, added_labels, moved = [], [], []
    for label, parents in pa.items():
        if label not in pb:
            added_labels.append(label)
        elif sorted(parents) != sorted(pb[label]):
            moved.append((label, pb[label], parents))
    for label in pb:
        if label not in pa:
            removed_labels.append(label)

    # 消えたラベルと増えたラベルが似ていれば「名前の書き換え」とみなす
    used, renamed, truly_removed = set(), [], []
    for r in removed_labels:
        hit = None
        for a in added_labels:
            if a not in used and _similar(r, a):
                hit = a
                break
        if hit:
            used.add(hit)
            renamed.append('「%s」 → 「%s」' % (r, hit))
        else:
            truly_removed.append(r)
    truly_added = [a for a in added_labels if a not in used]

    if truly_removed:
        bad.append(('ラベルが %d個 消えています(検査で行を減らしてはいけません)' % len(truly_removed),
                    ['「%s」  (元の位置: %s の配下)' % (r, '」「'.join(pb[r])) for r in truly_removed]))
    if renamed:
        warn.append(('ラベル名が書き換えられています %d件(名前は変えない約束です)' % len(renamed), renamed))
    if truly_added:
        warn.append(('元のツリーに無いラベルが %d個 増えています' % len(truly_added),
                     ['「%s」  (位置: %s の配下)' % (a, '」「'.join(pa[a])) for a in truly_added]))

    # 統合の疑い(統合は禁止。似た項目に吸収されていないか)
    merged = []
    for r in truly_removed:
        for a in pa:
            if a != r and r in a:
                merged.append('「%s」 が 「%s」 に吸収されている可能性' % (r, a))
                break
    if merged:
        bad.append(('似た項目に統合された疑いがあります %d件(統合は禁止・別項目のまま残してください)'
                    % len(merged), merged))

    # ---- 定義文の増減(検査の主目的のひとつ)
    da = dict((n.path(), n.definition) for n in _all(before))
    db = dict((n.path(), n.definition) for n in _all(after))
    def_added, def_lost, def_changed = 0, [], []
    for path_str, d in db.items():
        if path_str not in da:
            continue
        was = da[path_str]
        if not was and d:
            def_added += 1
        elif was and not d:
            def_lost.append(path_str)
        elif was and d and was != d:
            def_changed.append(path_str)
    if def_lost:
        warn.append(('定義文が %d件 消えています(元からあった定義は残してください)' % len(def_lost), def_lost))
    if def_changed:
        info.append(('定義文が書き換えられたラベル %d件(意図した書き分けか確認してください)'
                     % len(def_changed), def_changed))
    if def_added:
        info.append(('定義文が %d件 追記されました(この手順では定義文は使いません)' % def_added, []))

    if moved:
        info.append(('位置が変わったラベル %d件(これが検査の成果です。意図どおりか確認してください)' % len(moved),
                     ['「%s」: 「%s」の配下 → 「%s」の配下'
                      % (l, '」「'.join(o), '」「'.join(n)) for l, o, n in moved]))
    return bad, warn, info


# --- AIの回答を読むための下ごしらえ ---------------------------------------
# AIは全角コロン「昇格:」や全角カッコ「[1101002]」、箇条書き記号や番号を付けて
# 返してくることがある。どれで返ってきても同じに読めるようにする。
OP_KINDS = '除外|削除|昇格|移動|付け替え|指摘|メモ|指示'
OP_COLON = '[::\uff1a\u2236\ua789]'
OP_LINE = re.compile('^(' + OP_KINDS + ')\\s*' + OP_COLON + '\\s*(.+)$')
# コードのカッコは半角[]・全角[]・()・()・[]のどれでもよい。全角数字も読む
CODE_RE = re.compile('[\\[\uff3b(\uff08\u3010]\\s*([0-9\uff10-\uff19]+)\\s*[\\]\uff3d)\uff09\u3011]')
# 行頭のかざり(箇条書き・引用符・太字の残骸)と番号を落とす
LEAD_RE = re.compile('^[\\s\\-*\uff0a\u30fb\u2022\u2023\u25aa\u25e6>\uff1e#\u300c\u300e"\'(\uff08]+')
NUM_RE = re.compile('^[0-9\uff10-\uff19]+[.\uff0e)\uff09\u3001]\\s*|^[\u2460-\u2473]\\s*')
# 行末のかざり(読点・区切り記号)を落とす
TAIL_RE = re.compile('[\\s\u3001\u3002,.\\-*\uff0a\u30fb\u2022|\uff5c\u300d\u300f"\')\uff09]+$')
ZEN_DIGITS = dict(zip(range(0xff10, 0xff1a), '0123456789'))
# 「×2」「2回」「2階層」= 何段上げるか。コードの前・後ろどちらに書かれてもよい
_TIMES = ('(?:[\u00d7xX\u2715]\\s*([0-9\uff10-\uff19]+)'
          '|([0-9\uff10-\uff19]+)\\s*(?:\u56de|\u968e\u5c64|\u6bb5))')
TIMES_HEAD = re.compile('\\s*' + _TIMES)
TIMES_TAIL = re.compile(_TIMES + '\\s*$')


def _ascii_digits(text):
    """全角数字を半角にそろえる"""
    return text.translate(ZEN_DIGITS)


def _strip_decor(line):
    """行頭・行末のかざりを落とす(「1. ・**昇格: A**」のような重ねがけにも対応)"""
    prev = None
    while prev != line:
        prev = line
        line = LEAD_RE.sub('', line)
        line = NUM_RE.sub('', line)
    return line.strip()


def dwidth(text):
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in text)


def parse_ops(text):
    """AIの回答から指示リストを読む。
    形式: 「昇格: ラベル [コード] ×2」「指摘: …」
    廃止された指示(除外・移動など)は bad として返す(黙って捨てない)。
    箇条書き記号・番号は無視。指示の形をした読めない行も bad として返す。"""
    ops, notes, bad = [], [], []
    # 改行が失われて1行に連結された回答や、太字(**)付きの回答も読めるようにする
    text = text.replace('**', '').replace('\u3000', ' ')
    # 1行に連結された回答を、指示語の直前で折り返して1行1指示に戻す
    text = re.sub('[ \t]*(?=(?:' + OP_KINDS + ')\\s*' + OP_COLON + ')', '\n', text)
    for raw in text.split('\n'):
        line = _strip_decor(raw.strip())
        if not line:
            continue
        m = OP_LINE.match(line)
        if not m:
            continue
        kind, body = m.group(1), m.group(2).strip()
        if kind == '指示':
            if body in ('なし', 'ありません'):
                notes.append('(この段は変更不要との回答)')
            continue
        if kind in ('指摘', 'メモ'):
            notes.append(body)
            continue
        if kind in ('移動', '付け替え'):
            bad.append('%s ← この指示は廃止されました(別の枝へ動かす指示はできません。'
                       '昇格で1階層上へ出してください)' % raw.strip())
            continue
        if kind == '削除':
            kind = '除外'
        if body in ('なし', 'ありません'):
            continue
        # コードが書かれていれば、ラベルはその手前まで。コードより後ろは
        # (1行に連結された回答の場合)次の指示の番号や区切り記号なので捨てる。
        code, times = None, 1
        mc = CODE_RE.search(body)
        if mc:
            code = _ascii_digits(mc.group(1))
            before, after = body[:mc.start()], body[mc.end():]
            mt = TIMES_HEAD.match(after) or TIMES_TAIL.search(before)
            if mt:
                times = int(_ascii_digits(next(g for g in mt.groups() if g)))
                if mt.re is TIMES_TAIL:
                    before = before[:mt.start()]
            body = before
        else:
            mt = TIMES_TAIL.search(body)
            if mt:
                times = int(_ascii_digits(next(g for g in mt.groups() if g)))
                body = body[:mt.start()]
        body = _strip_decor(TAIL_RE.sub('', body.strip()))
        label_path = [x for x in re.split(r'[/／]', body) if x.strip()]
        if not label_path and not code:
            bad.append(raw.strip())
            continue
        ops.append({'kind': kind, 'path': label_path, 'code': code, 'times': times,
                    'raw': line})
    return ops, notes, bad


def split_replies(text):
    """複数セッションの回答をまとめて貼れるように、「----」だけの行や「回答2」見出しで区切る"""
    blocks, cur = [], []
    for line in text.split('\n'):
        if re.match(r'^\s*[-=―ー─]{4,}\s*$', line) or re.match(r'^\s*[#■]*\s*回答\s*\d+\s*[::]?\s*$', line):
            if cur:
                blocks.append('\n'.join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append('\n'.join(cur))
    return blocks


def _op_key(op):
    return (op['kind'], op['code'] or '/'.join(op['path']), op['times'])


def vote_ops(text):
    """回答が複数貼られていれば多数決を取る。
    (採用した指示, 指摘, 読めない行, 回答数, 見送った指示の一覧) を返す。"""
    blocks = split_replies(text)
    parsed = [parse_ops(b) for b in blocks]
    eff = [(o, n, bd) for (o, n, bd) in parsed if o or n or bd]
    if len(eff) <= 1:
        o, n, bd = parse_ops(text)
        return o, n, bd, 1, []
    need = len(eff) // 2 + 1
    seen = {}
    order = []
    for o, _, _ in eff:
        keys = set()
        for op in o:
            k = _op_key(op)
            if k in keys:
                continue
            keys.add(k)
            if k not in seen:
                seen[k] = [op, 0]
                order.append(k)
            seen[k][1] += 1
    ops, minority = [], []
    for k in order:
        op, cnt = seen[k]
        if cnt >= need:
            ops.append(op)
        else:
            minority.append('%s(%d/%d件の回答)' % (op['raw'], cnt, len(eff)))
    notes, bad = [], []
    for _, n, bd in eff:
        for x in n:
            if x not in notes:
                notes.append(x)
        bad.extend(bd)
    return ops, notes, bad, len(eff), minority


def _resolve(root, label_path, code):
    """指示の対象ノードを特定する。コード優先、次にラベル(パスの末尾一致)"""
    if code:
        hits = [n for n in _all(root) if n.code == code]
        if len(hits) == 1:
            return hits[0], None
        if not hits:
            # 枝: 配下のコードが全部そのコードで始まる最上位ノード
            def sub_codes(n):
                out = []

                def w(x):
                    if x.code:
                        out.append(x.code)
                    for c in x.children:
                        w(c)
                w(n)
                return out
            cands = []
            for n in _all(root):
                cs = sub_codes(n)
                if cs and all(c.startswith(code) for c in cs):
                    if not (n.parent and n.parent.parent is not None and
                            all(c.startswith(code) for c in sub_codes(n.parent))):
                        cands.append(n)
            if len(cands) == 1:
                return cands[0], None
    if label_path:
        hits = []
        for n in _all(root):
            lp = _label_path(n)
            if len(lp) >= len(label_path) and lp[-len(label_path):] == label_path:
                hits.append(n)
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            return None, ('「%s」が%d箇所にあります(%s)。コード[…]か「親/ラベル」の形で特定してください'
                          % ('/'.join(label_path), len(hits),
                             ' / '.join('/'.join(_label_path(h)) for h in hits[:4])))
    name = '/'.join(label_path) if label_path else ('[%s]' % code)
    return None, '「%s」がツリーに見つかりません(名前とコードを確認してください)' % name


def find_empty_branches(root):
    """昇格の結果、配下が空になってしまった分類(枝)を探す。

    もともと配下があった枝から中身が全部出ていくと、選ぶ意味のない行き止まりが残る。
    コードも付いていないので、そのままだと「コード未登録」の袋小路になる。"""
    out = []

    def walk(n):
        for c in list(n.children):
            if not c.children and not c.code:
                out.append(c)
            else:
                walk(c)
    walk(root)
    return out


def drop_nodes(nodes):
    """指定のノードをツリーから取り除く。取り除いたあと空になった親も続けて取り除く。
    (取り除いた説明の一覧, 取り除いた数) を返す"""
    removed = []
    queue = list(nodes)
    while queue:
        n = queue.pop(0)
        p = n.parent
        if p is None or n not in p.children:
            continue
        if n.children or n.code:      # 念のため: 中身のあるものは消さない
            continue
        p.children.remove(n)
        removed.append('/'.join(_label_path(n)))
        if p.parent is not None and not p.children and not p.code:
            queue.append(p)
    return removed


def apply_ops(root, ops, allow_exclude=False):
    """指示リストをツリーへ機械的に適用する。
    (適用結果の報告, エラー, 除外した科目 [(ラベル, コード)]) を返す。
    「除外:」は絞り込みの条件が指定されたとき(allow_exclude=True)だけ適用する。"""
    applied, errors, excluded = [], [], []
    for op in ops:
        node, err = _resolve(root, op['path'], op['code'])
        if err:
            errors.append('%s: %s' % (op['raw'], err))
            continue
        if op['kind'] == '除外':
            if not allow_exclude:
                errors.append('%s: 除外は「絞り込みの条件」を入れたときだけ使えます'
                              '(条件が空のまま除外の指示が返ってきました)' % op['raw'])
                continue
            leaves_in = [(n.label, n.code) for n in [node] + list(_all(node)) if n.code]
            if not leaves_in:
                errors.append('%s: この行にはコードが無いため除外できません' % op['raw'])
                continue
            node.parent.children.remove(node)
            excluded.extend(leaves_in)
            if len(leaves_in) == 1 and node.code:
                applied.append('除外: %s [%s](条件による)' % (node.label, node.code))
            else:
                applied.append('除外: %s(配下の %d科目ごと・条件による)'
                               % (node.label, len(leaves_in)))
            continue
        if op['kind'] == '昇格':
            moved = 0
            for _ in range(op['times']):
                if node.parent is None or node.parent.parent is None:
                    errors.append('%s: 「%s」はこれ以上、上の階層へ動かせません(%d回目)'
                                  % (op['raw'], node.label, moved + 1))
                    break
                gp = node.parent.parent
                pos = gp.children.index(node.parent) + 1
                node.parent.children.remove(node)
                gp.children.insert(pos, node)
                node.parent = gp
                moved += 1
            if moved:
                applied.append('昇格: %s を %d階層上げました(→ %s の配下)'
                               % (node.label, moved,
                                  '/'.join(_label_path(node)[:-1]) or '最上位'))
    return applied, errors, excluded


def code_rows(root):
    """コードの付いた行を (コード, ラベル, 親の経路) で全部返す"""
    out = []
    for n in _all(root):
        if n.code:
            out.append((n.code, n.label, '/'.join(_label_path(n)[:-1]) or '(最上位)'))
    return out


def verify_tree(before, after, excluded_codes=None):
    """検査の前後を全数照合する。数だけでなく、
    (1) コードの集合が一致するか (2) 同じコードに付く末端の名前が変わっていないか
    (3) 桁数の内訳 まで見る。(問題なしか, 問題の明細, 要約の行) を返す。
    excluded_codes: 絞り込みの条件で除外したコード。この分の「欠け」は正常とみなし、
    代わりに「元 = 適用後 + 除外」の全数一致を確かめる。"""
    ex = set(excluded_codes or [])
    rb, ra = code_rows(before), code_rows(after)
    mb, ma = {}, {}
    for c, l, _ in rb:
        mb.setdefault(c, []).append(l)
    for c, l, _ in ra:
        ma.setdefault(c, []).append(l)
    ex_ok = sorted(c for c in mb if c not in ma and c in ex)
    ex_ghost = sorted(c for c in ex if c not in mb)          # 除外リスト側にしか無いコード
    ex_alive = sorted(c for c in ex if c in ma)              # 除外したはずなのに残っている
    missing = sorted(c for c in mb if c not in ma and c not in ex)
    added = sorted(c for c in ma if c not in mb)
    changed = sorted(c for c in mb if c in ma and sorted(mb[c]) != sorted(ma[c]))
    dup = sorted(c for c in ma if len(ma[c]) > 1)
    by_len = {}
    for c, _, _ in ra:
        by_len[len(c)] = by_len.get(len(c), 0) + 1

    bad = []
    for c in missing:
        bad.append('[%s]「%s」が検査後に見つかりません(コードが消えています)' % (c, '・'.join(mb[c])))
    for c in added:
        bad.append('[%s]「%s」は元のツリーにありません(コードが増えています)' % (c, '・'.join(ma[c])))
    for c in changed:
        bad.append('[%s] 末端の名前が変わっています(「%s」→「%s」)'
                   % (c, '・'.join(mb[c]), '・'.join(ma[c])))
    for c in ex_ghost:
        bad.append('[%s] 除外の指示にありますが、元のツリーに存在しません' % c)
    for c in ex_alive:
        bad.append('[%s] 除外したはずのコードがツリーに残っています' % c)
    summary = [
        'コードの数: %d個 → %d個%s(%s)'
        % (len(rb), len(ra),
           ' + 除外 %d個' % len(ex_ok) if ex_ok else '',
           '一致' if len(rb) == len(ra) + len(ex_ok) else
           ('一致' if not ex and len(rb) == len(ra) else '不一致')),
        ('コードの全数照合: %s(欠け %d件・増え %d件)'
         % ('元 = 適用後 + 除外 で全数一致' if ex_ok and not (missing or added)
            else ('元のコードがすべて残っています' if not (missing or added) else '食い違いあり'),
            len(missing), len(added))),
        'コードと末端名の対応: %s'
        % ('%d組すべて一致(名前の変わったコード 0件)' % len(ma) if not changed
           else '%d件のコードで名前が変わっています' % len(changed)),
        '桁数の内訳: %s' % ('、'.join('%d桁 %d個' % (k, v) for k, v in sorted(by_len.items()))
                        or '(コードなし)'),
    ]
    if dup:
        summary.append('同じコードが複数の場所にあります: %d種類(例: %s)'
                       % (len(dup), '、'.join('[%s]' % c for c in dup[:3])))
    return (not bad), bad, summary


def leaf_table(before, after, title='末端とコードの一覧'):
    """末端(コードの付いた行)を、コード順に全部書き出す。
    検査で位置が変わったものには ★ と元の位置を付ける(目視確認用)。"""
    pos_b = {}
    for c, _, p in code_rows(before):
        pos_b.setdefault(c, []).append(p)
    rows = sorted(code_rows(after))
    wc = max([len(c) for c, _, _ in rows] or [0])
    wl = max([dwidth(l) for _, l, _ in rows] or [0])
    out = ['# %s(%d件)' % (title, len(rows)),
           '# コード / 末端の名前 / 位置(★ = 検査で位置が変わったもの)', '']
    moved = 0
    for c, l, p in rows:
        old = (pos_b.get(c) or [None])[0]
        mark = ''
        if old is not None and old != p:
            mark = '   ★ 元: %s' % old
            moved += 1
        out.append('%s%s  %s%s  %s%s'
                   % (c, ' ' * (wc - len(c)), l, ' ' * (wl - dwidth(l)), p, mark))
    out.append('')
    out.append('# 合計 %d件 / 位置が変わったもの %d件(名前とコードの対応は変わりません)'
               % (len(rows), moved))
    return '\n'.join(out) + '\n'


def render_like_source(root, title_line):
    """①の出力と同じ体裁(コードを右端で縦に揃える)で書き出す。
    定義文や記号が付いている場合は揃えず素直に出す。"""
    if any(n.definition or n.star or n.lock for n in _all(root)):
        return render_tree(root, title_line)
    rows = []

    def walk(n, prefix):
        for i, c in enumerate(n.children):
            last = i == len(n.children) - 1
            rows.append((prefix + ('└─ ' if last else '├─ ') + c.label, c.code or ''))
            walk(c, prefix + ('    ' if last else '│   '))
    walk(root, '')
    width = max([dwidth(t) for t, c in rows if c] or [0])
    lines = [title_line]
    for t, c in rows:
        lines.append(t + ' ' * (width - dwidth(t) + 1) + '[%s]' % c if c else t)
    return '\n'.join(lines) + '\n'


def make_cards(root, title='検査カード', condition=None):
    """全段を深い順に書き出した検査カードを作る。
    各カードは「一つ上の段の選択肢から選ぶとき、この科目なら親が選ばれるか」を
    1科目ずつ確認させる、単独で貼れる質問文になっている。"""
    stages = []
    order = [0]

    def walk(n, depth):
        for c in n.children:
            if c.children:
                order[0] += 1
                stages.append((depth + 1, order[0], c))
                walk(c, depth + 1)
    walk(root, 0)
    stages.sort(key=lambda t: (-t[0], t[1]))

    total = len(stages)
    out = []
    out.append('# %s(全%d段・深い段から順)' % (title, total))
    out.append('')
    out.append('これは、②の検査でAIが確認すべき「段」を、プログラムが機械的に全部書き出したものです。')
    out.append('- AIの回答と見比べて、検討が抜けている段がないかを監視するチェックリストとして使えます')
    out.append('- 1枚ずつチャットAIに貼って回すこともできます(各カードが単独の質問になっています)')
    out.append('- どのやり方でも、たまった指示行をまとめてツリー検査の右の欄に貼れば一括で適用されます')
    out.append('')
    for i, (depth, _, n) in enumerate(stages, 1):
        path = '/'.join(_label_path(n))
        parent = n.parent
        sibs = [c.label for c in parent.children] if parent is not None else [n.label]
        sib_line = ' / '.join(sibs)
        # 昇格させた科目は「一つ上の段の選択肢」に並ぶので、
        # 次はその段(=親の兄弟)で親が選ばれるかを確かめることになる
        gp = parent.parent if parent is not None else None
        next_sibs = [c.label for c in gp.children] if gp is not None else None
        out.append('─' * 46)
        out.append('カード %d/%d  場所: %s(対象%d個)' % (i, total, path, len(n.children)))
        out.append('')
        out.append('一つ上の段の選択肢: %s' % sib_line)
        out.append('')
        out.append('確認してほしいこと(下の科目を1つずつ、必ず全部):')
        out.append('  契約書を読んだ人が、上の選択肢から1つ選ぶとします。')
        out.append('  その科目の契約なら「%s」が選ばれますか?' % n.label)
        out.append('  ・「%s」が選ばれる可能性が高い → そのまま(何も書かない)' % n.label)
        out.append('  ・別の選択肢が選ばれそう、または紛れる → 「昇格: ラベル [コード]」で1階層上へ')
        out.append('    (直し方は昇格だけ。科目を減らす・別の枝へ動かす指示はできず、考えは「指摘:」に)')
        out.append('')
        out.append('昇格させる場合は、そこで終わりにせず、次も必ず確かめてください:')
        if next_sibs:
            out.append('  昇格させると、その科目は「%s」の直下に並びます。' % parent.label)
            out.append('  すると次に選ぶ段は → %s' % ' / '.join(next_sibs))
            out.append('  その科目の契約なら「%s」が選ばれますか?' % parent.label)
            out.append('  ・選ばれる → 「昇格: ラベル [コード]」(1段だけ)')
            out.append('  ・選ばれない → 「昇格: ラベル [コード] ×2」(収まるまで ×3 …)')
        else:
            out.append('  この段の科目を昇格させると、1段目(いちばん上)の選択肢に並びます。')
            out.append('  これ以上は上げられないので「×2」以上は書かないでください。')
        out.append('')
        out.append('対象の科目(%d個):' % len(n.children))
        for c in n.children:
            if c.code:
                out.append('  ・%s [%s]' % (c.label, c.code))
            else:
                out.append('  ・%s(枝・配下%d個)' % (c.label, len(c.children)))
        out.append('')
        out.append('指示で直せない気づき(紛らわしい名前など)は「指摘: 一言」と書いてください。')
        if condition:
            out.append('あわせて: 利用者が指定した絞り込みの条件があります。')
            out.append('  【条件】%s' % condition)
            out.append('  どう考えてもこの条件を満たさない科目は「除外: ラベル [コード]」と書いてください。')
            out.append('  少しでも満たす可能性がある科目は除外しないでください(迷ったら「指摘:」に)。')
            out.append('回答は「除外:」「昇格:」「指摘:」の行だけ')
        else:
            out.append('回答は「昇格:」「指摘:」の行だけ')
        out.append('(コードの無い選択肢は「%s/ラベル」の形で書く)。' % n.label)
        out.append('すべてそのままで良ければ「指示: なし」とだけ書いてください。')
        out.append('')
    return '\n'.join(out) + '\n'


def tree_title(text):
    """出力の1行目(「区分判定(1段目)」)を入力から引き継ぐ"""
    for line in text.split('\n'):
        line = line.strip()
        if re.match(r'^.+(1段目)$', line):
            return line
    return '区分判定(1段目)'


def _copy_subtree(n):
    new = Node(n.label)
    new.leaf, new.star, new.lock = n.leaf, n.star, n.lock
    new.code, new.definition = n.code, n.definition
    for c in n.children:
        cc = _copy_subtree(c)
        cc.parent = new
        new.children.append(cc)
    return new


def _label_path(n):
    out = []
    while n is not None and n.parent is not None:
        out.append(n.label)
        n = n.parent
    return list(reversed(out))


def merge_apply(b_root, a_root, excluded_codes=None):
    """検査後のツリー b(通常は7桁)の構造・定義を、元の10桁ツリー a に反映した新しい木を返す。

    仕組み: b の葉の [コード] は a では「そのコードで始まる枝」に対応する。
    b の骨組みどおりに新しい木を組み立て、b の葉が来るべき場所に a の枝(10桁の内部構造ごと)を移植する。
    定義文は b から写し、a のコードと葉はすべて保存される。
    excluded_codes(絞り込みの条件で7桁側から除外したコード)を渡すと、その枝は
    復活させずに落とし、落とした10桁コードを report['dropped'] に入れる。"""
    ex = set(excluded_codes or [])
    # 元ツリーの全コード
    a_codes = []

    def collect(n):
        if n.code:
            a_codes.append((n, n.code))
        for c in n.children:
            collect(c)
    collect(a_root)
    if not a_codes:
        raise ValueError('元のツリーにコードがありません(反映には ①が出力した10桁ツリーを使ってください)')

    b_lens = set()

    def blens(n):
        if n.code:
            b_lens.add(len(n.code))
        for c in n.children:
            blens(c)
    blens(b_root)
    if not b_lens:
        raise ValueError('検査後のツリーにコードがありません(反映には [コード] 付きのツリーが必要です)')
    if any(len(code) < max(b_lens) for _, code in a_codes):
        raise ValueError('元のツリー側にコードの短い行があります。反映機能は「葉に完全なコード」を持つツリー'
                         '(①の出力する10桁ツリー)を元にしてください')

    # 長さLごとの接頭辞集合と、接頭辞→最上位の枝(アンカー)
    memo = {}

    def prefset(n, L):
        key = (id(n), L)
        if key in memo:
            return memo[key]
        out = set()
        if n.code and len(n.code) >= L:
            out.add(n.code[:L])
        for c in n.children:
            out |= prefset(c, L)
        memo[key] = out
        return out

    def anchors_for(L):
        out = {}

        def walk(n, covered):
            here = covered
            if not covered:
                ps = prefset(n, L)
                if len(ps) == 1:
                    out.setdefault(next(iter(ps)), []).append(n)
                    here = True
            for c in n.children:
                walk(c, here)
        for c in a_root.children:
            walk(c, False)
        return out
    anchor_maps = dict((L, anchors_for(L)) for L in b_lens)

    # 元ツリーの枝の定義(bに定義が無い場合の温存用)
    a_defs = {}

    def cdefs(n, path):
        for c in n.children:
            p = path + (c.label,)
            if c.definition:
                a_defs[p] = c.definition
            cdefs(c, p)
    cdefs(a_root, ())

    report = {'defs': 0, 'moves': [], 'notes': [], 'multi': [], 'dropped': []}
    used = set()
    new_root = Node(a_root.label)

    def conv(bnode, parent_new, bpath):
        if bnode.code and not bnode.children:
            amap = anchor_maps.get(len(bnode.code), {})
            targets = [t for t in amap.get(bnode.code, []) if id(t) not in used]
            if not targets:
                report['notes'].append('コード [%s](%s)に対応する枝が元のツリーに見つかりません'
                                       '(そのまま新しい葉として置きます)' % (bnode.code, bnode.label))
                nn = _copy_subtree(bnode)
                nn.parent = parent_new
                parent_new.children.append(nn)
                return
            if len(targets) > 1:
                report['multi'].append('[%s] %s … 同じコードの枝が%d箇所あり、全部を同じ場所へ移します'
                                       % (bnode.code, bnode.label, len(targets)))
            for t in targets:
                used.add(id(t))
                old_parent = _label_path(t)[:-1]
                if old_parent != bpath:
                    report['moves'].append('「%s」: 「%s」の配下 → 「%s」の配下'
                                           % (t.label, '/'.join(old_parent) or '(最上位)',
                                              '/'.join(bpath) or '(最上位)'))
                nn = _copy_subtree(t)
                if bnode.definition:
                    nn.definition = bnode.definition
                    report['defs'] += 1
                if bnode.star:
                    nn.star = True
                nn.parent = parent_new
                parent_new.children.append(nn)
            return
        if bnode.code and bnode.children:
            report['notes'].append('「%s」はコードと配下の両方を持つため、枝として扱いコードは配下から引き継ぎます'
                                   % bnode.label)
        nn = Node(bnode.label)
        nn.star, nn.lock = bnode.star, bnode.lock
        nn.definition = bnode.definition or a_defs.get(tuple(bpath + [bnode.label]))
        if bnode.definition:
            report['defs'] += 1
        nn.parent = parent_new
        parent_new.children.append(nn)
        for c in bnode.children:
            conv(c, nn, bpath + [bnode.label])

    for c in b_root.children:
        conv(c, new_root, [])

    # bに現れなかった枝は、元の位置(に一番近い場所)へ残す。
    # ただし絞り込みの条件で除外されたコードの枝は復活させず、落として報告する
    for L, amap in sorted(anchor_maps.items()):
        for P in sorted(amap):
            for t in amap[P]:
                if id(t) in used:
                    continue
                used.add(id(t))
                if P in ex:
                    for n in [t] + list(_all(t)):
                        if n.code:
                            report['dropped'].append((n.code, n.label))
                    continue
                chain = _label_path(t)[:-1]
                cur = new_root
                for lab in chain:
                    nxt = next((c for c in cur.children if c.label == lab), None)
                    if nxt is None:
                        break
                    cur = nxt
                nn = _copy_subtree(t)
                nn.parent = cur
                cur.children.append(nn)
                report['notes'].append('「%s」は検査後のツリーに無かったため、元の位置(%s)に残しました'
                                       % (t.label, '/'.join(chain) or '最上位'))
    return new_root, report


def render_tree(root, title_line):
    """反映結果のツリーを書き出す(定義文があるため桁揃えはしない)"""
    lines = [title_line]

    def fmt(n):
        s = n.label
        if n.lock:
            s += ' 🔒'
        if n.star:
            s += ' ★'
        if n.code:
            s += ' [%s]' % n.code
        if n.definition:
            s += ': %s' % n.definition
        return s

    def walk(n, prefix):
        for i, c in enumerate(n.children):
            last = i == len(n.children) - 1
            lines.append(prefix + ('└─ ' if last else '├─ ') + fmt(c))
            walk(c, prefix + ('    ' if last else '│   '))
    walk(root, '')
    return '\n'.join(lines) + '\n'


def all_codes_sorted(root):
    out = []
    for n in _all(root):
        if n.code:
            out.append(n.code)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description='分類ツリーの検算(AIが返したツリーが壊れていないか確かめる)')
    ap.add_argument('tree', help='検算するツリーのファイル(AIの返事を保存したもので可)')
    ap.add_argument('-b', '--before', help='比較したい元のツリー(指定すると何がどこへ動いたかを表示)')
    ap.add_argument('--cards', action='store_true',
                    help='検査カード(全段の一覧)を書き出す。位置引数は「元の7桁ツリー」')
    ap.add_argument('--cards-out', default='検査カード.txt')
    ap.add_argument('--apply-ops', help='AIの回答(指示リスト)のファイル。このとき位置引数は「元の7桁ツリー」')
    ap.add_argument('--ops-out', default='分類ツリー_7桁_修正済み.md', help='--apply-ops の出力先')
    ap.add_argument('--drop-empty', action='store_true',
                    help='昇格で配下が空になった分類を削除する(既定は残して警告だけ)')
    ap.add_argument('--condition', default='',
                    help='絞り込みの条件(例:「相手勘定が現金になる科目だけを残す」)。'
                         '指定すると回答内の「除外:」指示を適用する(未指定なら除外はエラー)')
    ap.add_argument('--excluded-out', default='除外した科目.txt',
                    help='絞り込みで除外した科目の一覧の出力先')
    ap.add_argument('--leaves-out', default='末端とコードの一覧.txt',
                    help='--apply-ops が書き出す「末端とコードの一覧」(目視確認用)')
    ap.add_argument('--leaves10-out', default='末端とコードの一覧_10桁.txt',
                    help='反映後の「末端とコードの一覧」(目視確認用)')
    ap.add_argument('--apply-to', help='検査結果(7桁)を反映する、元の10桁ツリー')
    ap.add_argument('-o', '--output', default='分類ツリー_10桁_反映済み.md',
                    help='--apply-to の出力先')
    args = ap.parse_args()

    text = open(args.tree, encoding='utf-8').read()

    if args.cards:
        root0, err0 = parse(text)
        cards = make_cards(root0)
        with open(args.cards_out, 'w', encoding='utf-8') as f:
            f.write(cards)
        n_stage = cards.split('(全')[1].split('段')[0]
        print('■ 検査カード %s段分を書き出しました → %s' % (n_stage, args.cards_out))
        sys.exit(0)

    if args.apply_ops:
        base_root, base_err = parse(text)
        orig_root, _ = parse(text)          # 照合用の控え(適用前の姿)
        ops, notes, bad, n_replies, minority = vote_ops(open(args.apply_ops, encoding='utf-8-sig').read())
        if n_replies > 1:
            print('■ 多数決: 回答 %d件のうち過半数が一致した指示 %d件を適用します' % (n_replies, len(ops)))
            for m in minority:
                print('  (見送り) ' + m)
        else:
            print('■ 指示の適用: %d件の指示を読み取りました' % len(ops))
        applied, errs, excluded = apply_ops(base_root, ops,
                                            allow_exclude=bool(args.condition.strip()))
        for m in applied:
            print('  ・' + m)
        for m in notes:
            print('  (指摘) ' + m)
        problems = list(base_err)
        for m in bad:
            problems.append('指示の形をしていますが読めませんでした: %s' % m)
        for m in errs:
            problems.append(m)
        ex_codes = [c for _, c in excluded]
        if excluded:
            print('')
            print('■ 絞り込みの条件で除外: %d科目(条件: %s)' % (len(excluded), args.condition))
            for l, c in excluded[:20]:
                print('  ・%s [%s]' % (l, c))
            if len(excluded) > 20:
                print('  …ほか %d科目' % (len(excluded) - 20))
            with open(args.excluded_out, 'w', encoding='utf-8') as f:
                f.write('# 絞り込みの条件: %s\n' % args.condition)
                for l, c in excluded:
                    f.write('%s [%s]\n' % (l, c))
            print('  → %s' % args.excluded_out)
        ok, vbad, vsum = verify_tree(orig_root, base_root, excluded_codes=ex_codes)
        print('')
        print('■ 検算(元 → 適用後の全数照合)')
        for m in vsum:
            print('  ・' + m)
        if not ok:
            for m in vbad[:30]:
                problems.append(m)
            if len(vbad) > 30:
                problems.append('…ほか %d件の食い違い' % (len(vbad) - 30))
        empties = find_empty_branches(base_root)
        if empties:
            print('')
            if args.drop_empty:
                removed = drop_nodes(empties)
                print('■ 配下が空になった分類を削除しました(%d件)' % len(removed))
                for m in removed:
                    print('  ・' + m)
                ok, vbad, vsum = verify_tree(orig_root, base_root)
                print('  (削除後の検算) ' + ' / '.join(vsum[:2]))
                if not ok:
                    problems.extend(vbad[:30])
            else:
                print('■ 配下が空になった分類が %d件あります' % len(empties))
                for n in empties:
                    print('  ・' + '/'.join(_label_path(n)))
                print('  昇格で中身がすべて出ていったため、選んでも何も無い行き止まりです。')
                print('  コードも付いていないので、--drop-empty を付けて実行すると削除できます。')
        out_text = render_like_source(base_root, tree_title(text))
        with open(args.ops_out, 'w', encoding='utf-8') as f:
            f.write(out_text)
        print('  → %s' % args.ops_out)
        with open(args.leaves_out, 'w', encoding='utf-8') as f:
            f.write(leaf_table(orig_root, base_root))
        print('  → %s(末端とコードの一覧)' % args.leaves_out)
        if problems:
            print('')
            print('■ 対応が必要な指示が %d件あります(AIに聞き直すか、行を直して再実行):' % len(problems))
            for m in problems:
                print('  × ' + m)
        if args.apply_to:
            a_text = open(args.apply_to, encoding='utf-8').read()
            a_root, _ = parse(a_text)
            merged, rep = merge_apply(base_root, a_root, excluded_codes=ex_codes)
            if rep['dropped']:
                print('')
                print('■ 反映: 除外された7桁に対応する10桁 %d科目を落としました' % len(rep['dropped']))
                for c, l in rep['dropped'][:10]:
                    print('  ・%s [%s]' % (l, c))
                if len(rep['dropped']) > 10:
                    print('  …ほか %d科目' % (len(rep['dropped']) - 10))
            mok, mbad, msum = verify_tree(a_root, merged,
                                          excluded_codes=[c for c, _ in rep['dropped']])
            print('')
            print('■ 反映(10桁)の検算(元の10桁 → 反映後の全数照合)')
            for m in msum:
                print('  ・' + m)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(render_tree(merged, tree_title(a_text)))
            print('  → %s' % args.output)
            with open(args.leaves10_out, 'w', encoding='utf-8') as f:
                f.write(leaf_table(a_root, merged, '末端とコードの一覧(10桁)'))
            print('  → %s(末端とコードの一覧・10桁)' % args.leaves10_out)
            if not mok:
                for m in mbad[:30]:
                    problems.append('反映: ' + m)
        sys.exit(1 if problems else 0)

    root, errors = parse(text)
    n_leaf = len(leaves(root))
    n_code = sum(1 for n in _all(root) if n.code)
    print('■ 読み取り結果: 最終ラベル %d個 / 判定の段 %d個 / コード %d個'
          % (n_leaf, sum(1 for _ in _branches(root)), n_code))

    problems = errors + check(root)
    if problems:
        print('')
        print('■ 問題が %d件 見つかりました' % len(problems))
        for p in problems:
            print('  × ' + p)
    else:
        print('■ 構造チェック: 問題なし(このツリーはそのまま使えます)')

    if args.before:
        before, _ = parse(open(args.before, encoding='utf-8').read())
        nb_leaf = len(leaves(before))
        nb_code = sum(1 for n in _all(before) if n.code)
        bad, warn, info = compare_trees(before, root)
        print('')
        print('■ 数の比較(元 → 修正後)')
        print('  最終ラベル %d → %d / コード %d → %d' % (nb_leaf, n_leaf, nb_code, n_code))
        for kind, group in (('重大', bad), ('注意', warn), ('参考', info)):
            for title, items in group:
                print('')
                print('【%s】%s' % (kind, title))
                for it in items[:30]:
                    print('  ・' + it)
                if len(items) > 30:
                    print('  …ほか %d件' % (len(items) - 30))
        if not (bad or warn or info):
            print('')
            print('■ 違いはありません(記号や定義文を除いて同じ内容です)')
        elif bad:
            problems = problems + ['修正後のツリーに重大な差分があります(上記【重大】)']
            print('')
            print('■ 判定: そのまま使わないでください(重大な指摘 %d件)' % len(bad))
        elif warn:
            print('')
            print('■ 判定: 確認してから使ってください(注意 %d件)' % len(warn))
        else:
            print('')
            print('■ 判定: そのまま使えます(位置の変更のみ)')

    if args.apply_to:
        a_text = open(args.apply_to, encoding='utf-8').read()
        a_root, a_err = parse(a_text)
        print('')
        print('■ 反映: 検査後のツリーを %s に反映します' % args.apply_to)
        try:
            merged, rep = merge_apply(root, a_root)
        except ValueError as e:
            print('  × ' + str(e))
            sys.exit(1)
        if rep['defs']:
            print('  ・定義文を %d件 反映しました' % rep['defs'])
        for m in rep['moves']:
            print('  → ' + m)
        for m in rep['multi']:
            print('  ・' + m)
        for m in rep['notes']:
            print('  ! ' + m)
        mok, mbad, msum = verify_tree(a_root, merged)
        print('  ・検算(元の10桁 → 反映後の全数照合)')
        for m in msum:
            print('    - ' + m)
        if not mok:
            for m in mbad[:30]:
                problems.append('反映: ' + m)
                print('    × ' + m)
            print('  × 反映結果は使わないでください')
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(render_tree(merged, tree_title(a_text)))
        print('  → %s' % args.output)

    sys.exit(1 if problems else 0)


def _all(n):
    for c in n.children:
        yield c
        for x in _all(c):
            yield x


def _branches(root):
    def walk(n):
        for c in n.children:
            if c.is_branch:
                yield c
                for x in walk(c):
                    yield x
    return walk(root)


if __name__ == '__main__':
    main()
