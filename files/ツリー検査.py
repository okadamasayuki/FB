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

## ツリーの記法

    ├─ / └─ ……… 枝。インデント1段 = 半角スペース4つ分(「│   」または「    」)
    ◆ ……………… 最終的に出力されるラベル(これ以上分かれない)。※省略されている場合は「配下が無い行」が最終ラベル
    ★ ……………… その段で判定が紛れたときの受け皿。※省略されている場合もある(後続の処理が自動で決めます)
    🔒 ……………… 名称変更禁止(システムがこの名前を参照している)
    ✏ rules_xxx … その段の判定基準を外部設定で管理している印
    ラベル: 定義 … コロンの後ろはそのラベルの定義文
    [1234567] …… 勘定科目コード(7桁=共通、3桁=会社別)

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
- ラベル名・定義文・記号(◆ ★ 🔒 ✏)・コード [1234567] は、移動しても**そのまま維持**してください
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
            content = content.split(': ', 1)[0]
        mc = re.search(r' \[(\d+)\]', content)
        if mc:
            n.code = mc.group(1)
            content = content.replace(mc.group(0), '', 1)
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
        # 前方一致の衝突(分岐を持つ選択肢の名前が、他の葉ラベルの先頭と一致すると誤動作する)
        for b in [c for c in n.children if c.is_branch]:
            for c in n.children:
                if c is not b and not c.is_branch and c.label.startswith(b.label):
                    problems.append('「%s」の配下で名前が衝突します: 分岐「%s」と葉「%s」'
                                    % (n.label, b.label, c.label))
        for c in n.children:
            if c.leaf and c.children:
                problems.append('◆ の行に配下があります: %s' % c.path())

            if c.label.startswith('質問'):
                problems.append('「質問」で始まるラベルは使えません: %s' % c.path())
            if c.is_branch:
                if c.label in branch_names:
                    problems.append('分岐名が重複しています(一意にしてください): %s' % c.label)
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


def main():
    ap = argparse.ArgumentParser(description='分類ツリーの検算(AIが返したツリーが壊れていないか確かめる)')
    ap.add_argument('tree', help='検算するツリーのファイル(AIの返事を保存したもので可)')
    ap.add_argument('-b', '--before', help='比較したい元のツリー(指定すると何がどこへ動いたかを表示)')
    args = ap.parse_args()

    text = open(args.tree, encoding='utf-8').read()
    root, errors = parse(text)
    n_leaf = len(leaves(root))
    print('■ 読み取り結果: 最終ラベル %d個 / 判定の段 %d個'
          % (n_leaf, sum(1 for _ in _branches(root))))

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
        pb, pa = positions(before), positions(root)
        moved, added, removed = [], [], []
        for label, parents in pa.items():
            if label not in pb:
                added.append(label)
            elif sorted(parents) != sorted(pb[label]):
                moved.append((label, pb[label], parents))
        for label in pb:
            if label not in pa:
                removed.append(label)
        print('')
        print('■ 元のツリーとの違い')
        if not (moved or added or removed):
            print('  変更なし')
        for label, old, new in moved:
            print('  → %s: 「%s」の配下 から 「%s」の配下 へ'
                  % (label, '」「'.join(old), '」「'.join(new)))
        for label in added:
            print('  + 増えた: %s' % label)
        for label in removed:
            print('  - 消えた: %s  ← 意図した削除か確認してください' % label)

    sys.exit(1 if problems else 0)


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
