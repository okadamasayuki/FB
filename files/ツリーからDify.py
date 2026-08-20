#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  分類ツリー → Dify ワークフロー(YAML)変換ツール
  ※ このファイルは「AIへの指示書」と「変換プログラム」が一体になっています
==============================================================================

■ 使い方(Copilot などのチャットAIで)

    1. このファイルの中身を全部コピーして、チャットAIに貼る
    2. 分類ツリーのファイル(分類ツリー_10桁.md など)を添付する、または中身を貼る
    3. AIが Dify にインポートできる YAML を出力します

■ 手元のPCで直接動かす場合(Python 3だけで動きます。これが最も確実です)

    python3 ツリーからDify.py 分類ツリー_10桁.md -o contract-account-classification.yml

==============================================================================
【AIへの指示】 ここから下は、このファイルがチャットに貼られた場合の指示です。
==============================================================================

あなたの役割は、渡された「分類ツリー」から Dify ワークフローの YAML を作ることです。

## 大原則

1. **この変換に判断は要りません。** プログラムの通りに機械的に変換するだけです。
   自分で考えて内容を足したり削ったりしないでください。
2. **エラーで止めない。** 分からないことがあれば、利用者に日本語で質問してください。
3. **YAMLは必ず全体を出力する。** 「以下同様」「省略」は絶対に使わないこと。
   長い場合は分割して出し、分割したことを伝えてください。

## 手順

1. ツリーを読み込んで、**必ず先に次の数字を報告**してください。
   - 最終ラベルの数 / 判定の段の数 / コードの数
2. プログラムを実行して YAML を作ります。
3. 出来上がった YAML について、**必ず次の数字を報告**してください。
   - ノード数 / エッジ数 / 環境変数の数
   - LLMノードの数(= 判定の段の数 + 3 になるはずです)
4. YAML をそのままファイルに保存できる形で出力します。

## 変換できないときによくある原因(質問の例)

- 「ツリーの1行目が `区分判定(1段目)` になっていません。ツリー全体を貼っていただけますか?」
- 「同じ名前の中間段階が複数の場所にあります(例:「その他」)。
   Difyでは分岐の名前が重複できないので、**どちらかの名前を変えて**いただけますか?」
- 「インデントが半角スペース4つ分になっていない行があります。ツリーを貼り直していただけますか?」

## Pythonを実行できない環境の場合

**まず最初に「このコードを実行できません」とはっきり伝えてください。**
そのうえで、YAML を手作業で作るのは現実的ではない(数千行になる)ため、
「手元のPCで `python3 ツリーからDify.py 分類ツリー.md` を実行してください」と案内してください。

## できあがったYAMLの使い方(利用者への案内)

Dify の「アプリを作成 → DSLファイルをインポート」で取り込みます。
取り込むと、契約書を読んで段階的に分類し、金額なしの仕訳と勘定科目コードを出すワークフローになります。

==============================================================================
  ここから下はプログラムです(チャットAIは読み飛ばして構いません)
==============================================================================
"""
import argparse
import copy
import json
import os
import re
import sys

import io

# --- YAML書き出し(tools/miniyaml.py 由来)---

# ---------------------------------------------------------------- 書き出し

_NUM_RE = re.compile(r'^[-+]?(\d+\.?\d*([eE][-+]?\d+)?|\.\d+|0x[0-9a-fA-F]+|0o?[0-7]+)$')
_SEXAGESIMAL_RE = re.compile(r'^[-+]?\d[\d_]*(:[0-5]?\d)+')
_BOOLNULL = {'true', 'false', 'null', 'yes', 'no', 'on', 'off', '~', 'none'}
_FIRST_UNSAFE = set("-?:,[]{}#&*!|>'\"%@` \t")


def _plain_ok(s):
    if s == '' or s.lower() in _BOOLNULL or _NUM_RE.match(s) or _SEXAGESIMAL_RE.match(s):
        return False
    if s[0] in _FIRST_UNSAFE or s[-1] in ' \t:':
        return False
    if ': ' in s or ' #' in s or '\n' in s or '\t' in s or '\r' in s:
        return False
    if any(ord(c) < 0x20 for c in s):
        return False
    return True


def _dq(s):
    out = ['"']
    for c in s:
        if c == '\\':
            out.append('\\\\')
        elif c == '"':
            out.append('\\"')
        elif c == '\n':
            out.append('\\n')
        elif c == '\t':
            out.append('\\t')
        elif c == '\r':
            out.append('\\r')
        elif ord(c) < 0x20:
            out.append('\\x%02x' % ord(c))
        else:
            out.append(c)
    out.append('"')
    return ''.join(out)


def _scalar_inline(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return v if _plain_ok(v) else _dq(v)
    raise TypeError('unsupported scalar: %r' % (v,))


def _literal_ok(s):
    if '\n' not in s or s.endswith('\n') or s.startswith((' ', '\n', '\t')) or '\r' in s:
        return False
    for ln in s.split('\n'):
        if ln != ln.rstrip() or any(ord(c) < 0x20 for c in ln):
            return False
    return True


def _emit(obj, ind, lines):
    pad = '  ' * ind
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError('dict keys must be str: %r' % (k,))
            key = _scalar_inline(k)
            if isinstance(v, dict):
                if v:
                    lines.append('%s%s:' % (pad, key))
                    _emit(v, ind + 1, lines)
                else:
                    lines.append('%s%s: {}' % (pad, key))
            elif isinstance(v, list):
                if v:
                    lines.append('%s%s:' % (pad, key))
                    _emit(v, ind + 1, lines)
                else:
                    lines.append('%s%s: []' % (pad, key))
            elif isinstance(v, str) and _literal_ok(v):
                lines.append('%s%s: |-' % (pad, key))
                for ln in v.split('\n'):
                    lines.append(('%s  %s' % (pad, ln)) if ln else '')
            else:
                lines.append('%s%s: %s' % (pad, key, _scalar_inline(v)))
    elif isinstance(obj, list):
        for it in obj:
            if isinstance(it, (dict, list)) and it:
                sub = []
                _emit(it, 0, sub)
                lines.append('%s- %s' % (pad, sub[0]))
                lines.extend((pad + '  ' + l) if l else '' for l in sub[1:])
            elif isinstance(it, dict):
                lines.append('%s- {}' % pad)
            elif isinstance(it, list):
                lines.append('%s- []' % pad)
            elif isinstance(it, str) and _literal_ok(it):
                lines.append('%s- |-' % pad)
                for ln in it.split('\n'):
                    lines.append(('%s  %s' % (pad, ln)) if ln else '')
            else:
                lines.append('%s- %s' % (pad, _scalar_inline(it)))
    else:
        lines.append(pad + _scalar_inline(obj))


def dump(obj):
    lines = []
    _emit(obj, 0, lines)
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- 読み込み

class YamlError(Exception):
    pass

_UNSUPPORTED = ('この形式のYAMLには対応していません(PyYAMLをインストールすれば読めます): ')


class _Parser(object):
    def __init__(self, text):
        self.lines = text.split('\n')
        self.i = 0

    def _peek(self):
        while self.i < len(self.lines):
            l = self.lines[self.i]
            st = l.strip()
            if st == '' or st.startswith('#') or st == '---':
                self.i += 1
                continue
            return len(l) - len(l.lstrip(' ')), st
        return None

    def parse(self):
        val = self._block(-1)
        if self._peek() is not None:
            raise YamlError('複数ドキュメント、またはインデント不整合があります(行 %d)' % (self.i + 1))
        return val

    def _block(self, parent_indent):
        p = self._peek()
        if p is None or p[0] <= parent_indent:
            return None
        indent, content = p
        if content == '-' or content.startswith('- '):
            return self._seq(indent)
        try:
            self._split_key(content)
        except YamlError:
            # キーの無い1行 = スカラー(シーケンス項目の中身など)
            self.i += 1
            return self._value(content, parent_indent)
        return self._map(indent)

    def _value_block(self, key_indent):
        """「key:」の値。シーケンスはキーと同じインデントで始まってもよい(PyYAMLの既定出力)"""
        p = self._peek()
        if p is None or p[0] < key_indent:
            return None
        if p[0] == key_indent:
            if p[1] == '-' or p[1].startswith('- '):
                return self._seq(key_indent)
            return None
        return self._block(key_indent)

    def _seq(self, indent):
        out = []
        while True:
            p = self._peek()
            if p is None or p[0] != indent or not (p[1] == '-' or p[1].startswith('- ')):
                break
            raw = self.lines[self.i]
            rest = raw[indent + 1:]
            if rest.strip() == '':
                self.i += 1
                out.append(self._block(indent))
            else:
                # 「- 」を空白に置き換えて、この行から始まる子ノードとして読む
                self.lines[self.i] = raw[:indent] + ' ' + rest
                out.append(self._block(indent))
        return out

    def _map(self, indent):
        out = {}
        while True:
            p = self._peek()
            if p is None or p[0] != indent or p[1] == '-' or p[1].startswith('- '):
                break
            content = p[1]
            key, rest = self._split_key(content)
            self.i += 1
            if rest == '':
                out[key] = self._value_block(indent)
            else:
                out[key] = self._value(rest, indent)
        if not out:
            raise YamlError('マッピングを読めません(行 %d 付近)' % (self.i + 1))
        return out

    def _split_key(self, content):
        if content.startswith('"'):
            m = re.match(r'^("(?:[^"\\]|\\.)*")\s*:(?:\s+(.*))?$', content)
            if not m:
                raise YamlError(_UNSUPPORTED + content)
            return self._value(m.group(1), 0), (m.group(2) or '').strip()
        if content.startswith("'"):
            m = re.match(r"^('(?:[^']|'')*')\s*:(?:\s+(.*))?$", content)
            if not m:
                raise YamlError(_UNSUPPORTED + content)
            return self._value(m.group(1), 0), (m.group(2) or '').strip()
        if content.endswith(':') and ': ' not in content:
            return content[:-1].strip(), ''
        idx = content.find(': ')
        if idx < 0:
            raise YamlError(_UNSUPPORTED + content)
        return content[:idx].strip(), content[idx + 2:].strip()

    def _value(self, s, parent_indent):
        if s in ('|', '|-', '|+'):
            return self._literal(s, parent_indent)
        if s and s[0] in '>&*!':
            raise YamlError(_UNSUPPORTED + s)
        if s.startswith('"'):
            if not re.match(r'^"(?:[^"\\]|\\.)*"$', s):
                raise YamlError(_UNSUPPORTED + s)
            return self._unescape(s[1:-1])
        if s.startswith("'"):
            if re.match(r"^'(?:[^']|'')*'$", s):
                return s[1:-1].replace("''", "'")
            return self._folded_single(s)
        if s == '[]':
            return []
        if s == '{}':
            return {}
        if s.startswith('[') or s.startswith('{'):
            return self._flow(s)
        if s.lower() in ('null', '~', 'none', ''):
            return None
        if s.lower() == 'true':
            return True
        if s.lower() == 'false':
            return False
        if re.match(r'^[-+]?\d+$', s):
            return int(s)
        if re.match(r'^[-+]?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?$', s):
            return float(s)
        return s

    def _flow(self, s):
        # 単純なフロー形式([a, b, c] など。入れ子・引用符入りカンマは非対応)
        if s.startswith('[') and s.endswith(']'):
            inner = s[1:-1].strip()
            if inner == '':
                return []
            if '[' in inner or '{' in inner:
                raise YamlError(_UNSUPPORTED + s)
            return [self._value(x.strip(), 0) for x in inner.split(',')]
        raise YamlError(_UNSUPPORTED + s)

    def _scan_sq(self, line):
        """単一引用符スカラーの1行分を読む。(本文, 閉じたか) を返す"""
        out = []
        i = 0
        while i < len(line):
            c = line[i]
            if c == "'":
                if i + 1 < len(line) and line[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                if line[i + 1:].strip():
                    raise YamlError(_UNSUPPORTED + line)
                return ''.join(out), True
            out.append(c)
            i += 1
        return ''.join(out), False

    def _folded_single(self, s):
        """複数行に折り返された単一引用符スカラー(PyYAMLが改行入り文字列で出す形式)。
        折り返し = 空白1つ、空行n個 = 改行n個。"""
        result, done = self._scan_sq(s[1:])
        blanks = 0
        while not done:
            if self.i >= len(self.lines):
                raise YamlError('単一引用符が閉じていません')
            stripped = self.lines[self.i].strip()
            self.i += 1
            if stripped == '':
                blanks += 1
                continue
            seg, done = self._scan_sq(stripped)
            result += ('\n' * blanks) if blanks else ' '
            blanks = 0
            result += seg
        return result

    def _literal(self, header, parent_indent):
        body = []
        block_indent = None
        while self.i < len(self.lines):
            raw = self.lines[self.i]
            if raw.strip() == '':
                body.append('')
                self.i += 1
                continue
            ind = len(raw) - len(raw.lstrip(' '))
            if block_indent is None:
                if ind <= parent_indent:
                    break
                block_indent = ind
            if ind < block_indent:
                break
            body.append(raw[block_indent:])
            self.i += 1
        while body and body[-1] == '':
            body.pop()
        text = '\n'.join(body)
        if header == '|':
            text += '\n'
        return text

    def _unescape(self, s):
        out = []
        i = 0
        while i < len(s):
            c = s[i]
            if c != '\\':
                out.append(c)
                i += 1
                continue
            n = s[i + 1]
            if n == 'n':
                out.append('\n')
            elif n == 't':
                out.append('\t')
            elif n == 'r':
                out.append('\r')
            elif n == '"':
                out.append('"')
            elif n == '\\':
                out.append('\\')
            elif n == 'x':
                out.append(chr(int(s[i + 2:i + 4], 16)))
                i += 4
                continue
            elif n == 'u':
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            else:
                raise YamlError(_UNSUPPORTED + '\\' + n)
            i += 2
        return ''.join(out)


def load(text):
    return _Parser(text).parse()


# --- ワークフロー生成(tools/generate_workflow.py 由来)---


ROOT_LABEL = '区分判定'

MODEL = {'completion_params': {'temperature': 0.1}, 'mode': 'chat', 'name': 'gpt-4o', 'provider': 'openai'}

USER_BODY = ('\n\n<契約書本文>\n{{#doc-extractor.text#}}\n</契約書本文>\n\n'
             '<補足情報>\n{{#start.additional_info#}}\n</補足情報>\n'
             '(補足情報は、過去の質問への回答です。空の場合もあります。)')

SUPPLEMENT_SECTION = [
    '【補足情報の扱い】',
    '- ユーザー入力の<補足情報>には、過去にあなたが出力した質問への回答が入っていることがある。契約書本文と合わせて判定に使うこと。',
]

QUESTION_SECTION_HEAD = [
    '【更問い(判定に必要な情報が無い場合)】',
    '- 契約書本文と補足情報を読んでも判定に必要な情報が不足している場合は、ラベルを出力する代わりに、次の2行の形式で質問を出力する。',
    '  質問: (このノードの判定に必要な点を1つだけ、選択式で答えられるように聞く)',
    '  回答例: (ユーザーがそのまま使える回答の文例を「 / 」区切りで2〜3個示す)',
    '- 質問は1回の出力につき1つだけとし、判定を最も左右する点を聞くこと。',
    '- このノードでの質問の例:',
]


# ---------------------------------------------------------------- ツリーのパース

class Node(object):
    def __init__(self, label):
        self.label = label
        self.leaf = False
        self.star = False
        self.lock = False
        self.definition = None
        self.env = None
        self.note = None
        self.code = None       # [7桁] または [3桁] の勘定科目コード
        self.children = []
        self.parent = None

    @property
    def is_branch(self):
        return bool(self.children)


LINE_RE = re.compile(r'^((?:│   |    )*)(?:├─|└─) (.+)$')


def parse_tree(text):
    if '```' in text:
        blocks = text.split('```')
        tree = next((b for b in blocks if ROOT_LABEL + '(1段目)' in b), None)
        if tree is None:
            raise SystemExit('ツリーのコードブロック(「%s(1段目)」を含む)が見つかりません' % ROOT_LABEL)
    else:
        tree = text
    root = Node(ROOT_LABEL)
    stack = [root]
    for raw in tree.split('\n'):
        raw = raw.rstrip()
        if not raw or raw.startswith(ROOT_LABEL):
            continue
        m = LINE_RE.match(raw)
        if not m:
            raise SystemExit('ツリーの行を解釈できません: %r' % raw)
        depth = len(m.group(1)) // 4
        if depth + 1 > len(stack):
            raise SystemExit('インデントが飛んでいます: %r' % raw)
        node = parse_line(m.group(2))
        parent = stack[depth]
        node.parent = parent
        parent.children.append(node)
        del stack[depth + 1:]
        stack.append(node)
    finalize(root)
    return root


def parse_line(content):
    leaf = content.startswith('◆ ')
    if leaf:
        content = content[2:]
    ann = ''
    i = content.find(' …')
    if i >= 0:
        content, ann = content[:i], content[i:]
    node_env = None
    m = re.search(r'✏ (rules_[A-Za-z0-9_]+)', ann)
    if m:
        node_env = m.group(1)
    definition = None
    if ': ' in content:
        content, definition = content.split(': ', 1)
    node = Node('')
    node.leaf = leaf
    node.env = node_env
    node.definition = definition
    m = re.search(r' \[(\d+)\]', content)
    if m:
        node.code = m.group(1)
        content = content.replace(m.group(0), '', 1)
    if '🔒' in content:
        node.lock = True
        content = content.replace('🔒', '')
    j = content.find('★')
    if j >= 0:
        node.star = True
        after = content[j + 1:].strip()
        if after:
            node.note = after.strip('()')
        content = content[:j]
    node.label = content.strip()
    if not node.label:
        raise SystemExit('ラベルが空の行があります: %r' % content)
    return node


def finalize(root):
    """整合性チェック。◆(最終ラベル)と★(受け皿)はツリーに書かれていなければ自動で補う"""
    auto_star = []

    def walk(n):
        if n.leaf and n.children:
            raise SystemExit('◆ の行に子があります: %s' % n.label)
        if not n.leaf and n is not root and not n.children:
            n.leaf = True          # 子が無い＝最終ラベル(◆ は省略可)
        stars = [c for c in n.children if c.star]
        if n.children and len(stars) > 1:
            raise SystemExit('「%s」の配下の ★(フォールバック先)が %d個あります。1つにしてください'
                             % (n.label, len(stars)))
        if n.children and not stars:
            # ★が書かれていなければ「その他」を含むものを優先、無ければ最後の選択肢を受け皿にする
            cands = [c for c in n.children if 'その他' in c.label] or [c for c in n.children if '分類不能' in c.label]
            target = cands[-1] if cands else n.children[-1]
            target.star = True
            auto_star.append((n.label if n is not root else ROOT_LABEL, target.label))
        for c in n.children:
            walk(c)
    walk(root)
    if auto_star:
        sys.stderr.write('★(判定が紛れたときの受け皿)をツリーから読み取れなかったため、%d箇所を自動で決めました:\n'
                         % len(auto_star))
        for parent, label in auto_star[:10]:
            sys.stderr.write('  ・%s → %s\n' % (parent, label))
        if len(auto_star) > 10:
            sys.stderr.write('  …ほか %d箇所\n' % (len(auto_star) - 10))
    labels = [ROOT_LABEL]

    def collect(n):
        for c in n.children:
            if c.is_branch:
                if c.label in labels:
                    raise SystemExit('分岐名が重複しています(細分判定を持つ行の名前は一意にしてください): %s' % c.label)
                labels.append(c.label)
            collect(c)
    collect(root)

    def check_codes(n, seven):
        if n.code is not None:
            if len(n.code) == 7:
                if seven:
                    raise SystemExit('[7桁]の配下に再度[7桁]があります: %s' % n.label)
                seven = n.code
            elif len(n.code) == 3:
                if not seven:
                    raise SystemExit('[3桁]の上位に[7桁]がありません: %s' % n.label)
            elif seven and n.code.startswith(seven):
                pass          # 上位の[7桁]と先頭が一致するフルコード(そのまま採用)
            elif seven:
                raise SystemExit('[7桁]の配下のコードは、[3桁]か、その7桁で始まるフルコードにしてください: %s [%s]'
                                 % (n.label, n.code))
            elif n.children:
                raise SystemExit('途中の段に付けるコードは[7桁]にしてください: %s [%s]' % (n.label, n.code))
        for c in n.children:
            check_codes(c, seven)
    check_codes(root, None)


# ---------------------------------------------------------------- ステージ構築

class Stage(object):
    """細分判定を1回行う単位(=LLMノード1つ。分岐する子があれば if-else も持つ)"""

    def __init__(self, node, extras, used_ids):
        self.node = node
        self.label = node.label
        self.env = node.env
        self.is_root = node.parent is None
        self.is_sub = node.parent is not None and node.parent.parent is None
        ex = extras.get('stages', {}).get(self.label, {})
        self.ex = ex
        self.id = ex.get('id') or self._new_id(used_ids)
        used_ids.add(self.id)
        self.ifelse_id = None
        if self.branch_children():
            self.ifelse_id = (ex.get('ifelse') or {}).get('id') or self._new_ifelse_id(used_ids)
            used_ids.add(self.ifelse_id)

    def _new_id(self, used_ids):
        if self.env:
            base = 'llm-sub-' + self.env[len('rules_'):].replace('_', '-')
        else:
            base = 'llm-sub-x'
        cand, k = base, 2
        while cand in used_ids:
            cand, k = '%s%d' % (base, k), k + 1
        return cand

    def _new_ifelse_id(self, used_ids):
        base = 'if-else-' + self.id.replace('llm-sub-', '').replace('llm-', '')
        cand, k = base, 2
        while cand in used_ids:
            cand, k = '%s%d' % (base, k), k + 1
        return cand

    def branch_children(self):
        return [c for c in self.node.children if c.is_branch]

    def fallback(self):
        return next(c for c in self.node.children if c.star)

    def top_category(self):
        n = self.node
        while n.parent is not None and n.parent.parent is not None:
            n = n.parent
        return n.label

    def parent_phrase(self):
        if 'parent_phrase' in self.ex:
            return self.ex['parent_phrase']
        # 3段目は区分名、4段目以降は直上の段階名
        if self.node.parent is not None and self.node.parent.parent is not None \
                and self.node.parent.parent.parent is not None:
            return self.node.parent.label
        return self.top_category()


def build_stages(root, extras):
    used_ids = set()
    for st in extras.get('stages', {}).values():
        used_ids.add(st.get('id'))
        if st.get('ifelse'):
            used_ids.add(st['ifelse'].get('id'))
    stages = {}

    def walk(node):
        stage = Stage(node, extras, used_ids)
        stages[node.label] = stage
        for c in stage.branch_children():
            walk(c)
    walk(root)
    return stages


def postorder(root, stages):
    """集約は「子孫のステージが先」の順(最深の実行結果が勝つ)"""
    out = []

    def walk(node):
        for c in node.children:
            if c.is_branch:
                walk(c)
        out.append(stages[node.label])
    walk(root)
    return out


# ---------------------------------------------------------------- プロンプト生成

def numbered_defs(children, defs):
    lines = []
    for i, c in enumerate(children, 1):
        d = c.definition or defs.get(c.label, '')
        lines.append('%d. %s(例: %s)' % (i, c.label, d) if d else '%d. %s' % (i, c.label))
    return lines


def system_prompt(stage):
    node, ex = stage.node, stage.ex
    children = [c for c in node.children if not (stage.is_root and c.note)]
    n = len(children)
    lines = ['あなたは日本の企業会計に精通した経理・会計の専門家です。']
    if stage.is_root:
        lines.append('与えられた契約書の本文を読み、その契約が主として関係する勘定科目区分を1つだけ判定し、区分名のラベルのみを出力してください。')
    else:
        if stage.is_sub:
            lines.append('この契約書は、前段の判定で勘定科目区分「%s」に該当すると判定されています。' % stage.label)
        else:
            lines.append('この契約書は、前段の判定で%sのうち「%s」に該当すると判定されています。'
                         % (stage.parent_phrase(), stage.label))
        if stage.env:
            lines.append('下記の【分類基準】に従い、最も適切な細分を1つだけ判定し、ラベルのみを出力してください。')
        elif stage.is_sub:
            lines.append('契約書の本文を読み、次の%dの小区分のうち最も適切なものを1つだけ判定し、小区分名のラベルのみを出力してください。' % n)
        else:
            lines.append('契約書の本文を読み、次の%dつの細分のうち最も適切なものを1つだけ判定し、ラベルのみを出力してください。' % n)
    lines.append('')
    defs = ex.get('defs', {})
    if stage.env:
        lines += ['【分類基準】', '{{#env.%s#}}' % stage.env]
    elif stage.is_root:
        lines += ['【勘定科目区分】'] + numbered_defs(children, defs)
    elif stage.is_sub:
        lines += ['【%sの小区分】' % stage.label] + numbered_defs(children, defs)
    else:
        lines += ['【%sの細分】' % stage.label] + numbered_defs(children, defs)
    lines.append('')
    lines.append('【出力ルール】')
    if stage.is_root:
        lines.append('- 出力はラベル1つのみ・1行のみ。説明文・理由・記号・引用符・改行・前後の空白は一切付けない。')
        allowed = [c.label for c in node.children]
        lines.append('- 出力してよいラベルは次の%d種類のみ。一字一句そのまま使うこと。' % len(allowed))
        lines.append('  ' + '、'.join(allowed))
    else:
        lines.append('- 出力はラベル1つのみ・1行のみ。説明文・理由・記号・引用符・番号・改行・前後の空白は一切付けない。')
        if stage.env:
            lines.append('- 出力してよいラベルは【分類基準】に列挙された細分名のみ(行頭の番号や「: 」以降の定義は付けない)。一字一句そのまま使うこと。')
        elif stage.is_sub:
            lines.append('- 出力してよいラベルは上記%d種類の小区分名のみ。一字一句そのまま使うこと。' % n)
        else:
            lines.append('- 出力してよいラベルは上記%d種類のみ。一字一句そのまま使うこと。' % n)
    extra_rules = ex.get('extra_rules')
    if extra_rules is None:
        extra_rules = ['- 「%s」の行は後段の条件分岐が名称を参照しているため、ラベル名を変更しないこと。' % c.label
                       for c in stage.branch_children()] if stage.env else []
    lines += extra_rules
    if stage.is_root:
        fb = next(c for c in node.children if c.star)
        lines.append('- 判定材料はあるがどの区分にも当てはまらない場合のみ「%s」と出力する(情報不足の場合は下記の更問いを優先する)。' % fb.label)
    else:
        lines.append('- 判定材料はあるがどれに当たるか紛れる場合は、最も近いものとして「%s」を出力する(情報不足の場合は下記の更問いを優先する)。'
                     % stage.fallback().label)
    examples = stage.ex.get('examples')
    if examples:
        lines += [''] + ['【出力例】'] + examples
    lines += [''] + SUPPLEMENT_SECTION
    lines += [''] + QUESTION_SECTION_HEAD
    question = stage.ex.get('question')
    if not question:
        opts = [c.label for c in node.children[:3]]
        question = ['質問: この契約は次のどれに最も近いですか?(%s)' % ' / '.join(opts),
                    '回答例: %s' % ' / '.join('%sです' % o for o in opts[:2])]
    lines += ['  ' + q for q in question]
    return '\n'.join(lines)


def user_prompt(stage):
    intro = stage.ex.get('user_intro')
    if not intro:
        if stage.is_root:
            intro = '以下は契約書の本文です。この契約の勘定科目区分を判定し、ラベル名のみを出力してください。'
        elif stage.is_sub:
            intro = '以下は契約書の本文です。%sの小区分を判定し、ラベル名のみを出力してください。' % stage.label
        else:
            intro = '以下は契約書の本文です。この%sの細分を判定し、ラベル名のみを出力してください。' % stage.label
    return intro + USER_BODY


# ---------------------------------------------------------------- レイアウト

ROW = 140          # バンド内の行間
SCAF_Y = 190       # メインの横ライン(開始〜区分判定)
TOP_Y = 40         # 上部レーン(確認要求)
AGG_Y = 410        # 右側の集約〜終了ライン
BANDS_Y0 = 700     # 最初のグループバンドの開始y
BAND_GAP = 180     # バンド間の余白


def colx(c):
    return 80 + 304 * c


def stage_depth(stage):
    d, n = 0, stage.node
    while n.parent is not None:
        d += 1
        n = n.parent
    return d


def compute_layout(root, stages, gagg_ids):
    """全ノードの座標を決定的に計算する。
    線の交差を減らすため、区分ごとに横バンドを分け、集約は2段構え
    (グループ別集約→全体集約)にして各バンド内で線を完結させる。"""
    pos = {}
    max_depth = max(stage_depth(st) for st in stages.values())
    ga_col = max(7, 5 + 2 * max_depth)

    # スキャフォールド(メインの横ライン+上部レーン)
    pos['start'] = (colx(0), SCAF_Y)
    pos['doc-extractor'] = (colx(1), SCAF_Y)
    pos['llm-summary'] = (colx(2), SCAF_Y)
    pos['if-else-confirm'] = (colx(3), SCAF_Y)
    pos[stages[ROOT_LABEL].id] = (colx(4), SCAF_Y)
    if stages[ROOT_LABEL].ifelse_id:
        pos[stages[ROOT_LABEL].ifelse_id] = (colx(5), SCAF_Y)
    pos['template-confirm'] = (colx(4), TOP_Y)
    pos['aggregator'] = (colx(ga_col + 1), AGG_Y + 150)
    pos['template-path'] = (colx(ga_col + 2), AGG_Y + 150)
    pos['template-code'] = (colx(ga_col + 3), AGG_Y + 150)
    pos['if-else-q'] = (colx(ga_col + 4), AGG_Y + 370)
    pos['llm-journal'] = (colx(ga_col + 5), AGG_Y + 590)
    pos['aggregator-out'] = (colx(ga_col + 6), AGG_Y)
    pos['end'] = (colx(ga_col + 7), AGG_Y)

    # 区分ごとのバンド。行0 = 小区分判定+深い段(4段目)の行、行1〜 = 細分判定、
    # 最下行の下 = グループ集約(合流レーン)。合流の線がバンドの下側を通り、交差しない。
    band_y = BANDS_Y0
    for cat in root.children:
        if not cat.is_branch:
            continue
        head = stages[cat.label]
        sub_stages = [stages[c.label] for c in cat.children if c.is_branch]
        rows = 1 + len(sub_stages)
        pos[head.id] = (colx(6), band_y)
        if head.ifelse_id:
            pos[head.ifelse_id] = (colx(7), band_y)
        for i, st in enumerate(sub_stages):
            y = band_y + ROW * (1 + i)
            pos[st.id] = (colx(4 + 2 * stage_depth(st)), y)
            if st.ifelse_id:
                pos[st.ifelse_id] = (colx(5 + 2 * stage_depth(st)), y)

            def deeper(node):
                for c in node.children:
                    if not c.is_branch:
                        continue
                    dst = stages[c.label]
                    pos[dst.id] = (colx(4 + 2 * stage_depth(dst)), y)
                    if dst.ifelse_id:
                        pos[dst.ifelse_id] = (colx(5 + 2 * stage_depth(dst)), y)
                    deeper(c)
            deeper(st.node)
        gy = band_y + rows * ROW + 70
        pos[gagg_ids[cat.label]] = (colx(ga_col), gy)
        band_y = gy + 116 + BAND_GAP
    return pos


def place(pos, nid):
    x, y = pos[nid]
    return {'x': x, 'y': y}


def node_shell(nid, data, pos, height=116):
    return {'data': data, 'height': height, 'id': nid,
            'position': pos, 'positionAbsolute': dict(pos), 'selected': False,
            'sourcePosition': 'right', 'targetPosition': 'left', 'type': 'custom', 'width': 244}


def llm_node(stage, pos):
    if stage.env:
        desc = stage.ex.get('desc') or '%sを環境変数 %s の分類基準に従って細分判定します。' % (stage.label, stage.env)
    elif stage.is_root:
        desc = stage.ex.get('desc') or '契約書の主たる勘定科目区分を判定します。'
    else:
        desc = stage.ex.get('desc') or '%sの細分を判定します(基準はプロンプト内固定)。' % stage.label
    suffix = stage.id.replace('llm-', '')
    data = {
        'context': {'enabled': False, 'variable_selector': []},
        'desc': desc,
        'model': copy.deepcopy(MODEL),
        'prompt_template': [
            {'id': 'system-prompt-%s' % suffix, 'role': 'system', 'text': system_prompt(stage)},
            {'id': 'user-prompt-%s' % suffix, 'role': 'user', 'text': user_prompt(stage)},
        ],
        'selected': False,
        'title': stage.ex.get('title') or ('%s 細分判定' % stage.label),
        'type': 'llm',
        'variables': [],
        'vision': {'enabled': False},
    }
    return node_shell(stage.id, data, place(pos, stage.id))


def case_id_for(child_stage):
    return (child_stage.ex.get('case_id')
            or ('case-' + child_stage.id.replace('llm-sub-', '').replace('llm-', '')))


def make_case(stage, child_stage):
    ex = child_stage.ex
    value = ex.get('case_value') or child_stage.label
    cid = case_id_for(child_stage)
    cond = ex.get('cond_id') or cid.replace('case-', 'cond-')
    return {
        'case_id': cid,
        'conditions': [{
            'comparison_operator': 'start with',
            'id': cond,
            'value': value,
            'varType': 'string',
            'variable_selector': [stage.id, 'text'],
        }],
        'id': cid,
        'logical_operator': 'and',
    }, value


def ifelse_node(stage, stages, pos):
    branch = stage.branch_children()
    cases, values = [], []
    for c in branch:
        case, value = make_case(stage, stages[c.label])
        cases.append(case)
        values.append(value)
    # ケースは値の長い順に並べる(Difyは上から順に評価するため、
    # 「その他」と「その他の◯◆」のような前方一致の包含関係があっても正しく振り分けられる)
    pairs = sorted(zip(cases, values, branch), key=lambda t: -len(t[1]))
    cases = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    # 前方一致の衝突チェック: 分岐同士の包含は上記の並びで解決するが、
    # ケースを持たない葉ラベルがケース値に飲み込まれる場合はエラー
    for c in stage.node.children:
        for _, v, bc in pairs:
            if c.label == bc.label:
                continue
            if c.label.startswith(v) and not c.is_branch:
                raise SystemExit('条件分岐の前方一致が衝突: 値「%s」(%s行き)が葉ラベル「%s」にもマッチします。'
                                 'ラベル名を変えるか extras の case_value を調整してください。' % (v, bc.label, c.label))
        if c.label.startswith('質問'):
            raise SystemExit('「質問」で始まるラベルは使えません: %s' % c.label)
    if len(set(values)) != len(values):
        raise SystemExit('条件分岐のケース値が重複しています: %s' % values)
    ex_if = stage.ex.get('ifelse') or {}
    if stage.is_root:
        default_title, default_desc = '条件分岐', '細分を持つ区分の場合のみ小区分判定へ分岐します。'
    else:
        default_title = '条件分岐(%s細分)' % stage.label
        default_desc = '%sの細分のうち、さらに細分を持つものを対応する判定へ分岐します。' % stage.label
    data = {
        'cases': cases,
        'desc': ex_if.get('desc') or default_desc,
        'selected': False,
        'title': ex_if.get('title') or default_title,
        'type': 'if-else',
    }
    return node_shell(stage.ifelse_id, data, place(pos, stage.ifelse_id),
                      height=ex_if.get('height', 126))


def make_edge(nodes_by_id, src, handle, tgt):
    return {
        'data': {'isInIteration': False,
                 'sourceType': nodes_by_id[src]['data']['type'],
                 'targetType': nodes_by_id[tgt]['data']['type']},
        'id': '%s-%s-%s-target' % (src, handle, tgt),
        'source': src, 'sourceHandle': handle,
        'target': tgt, 'targetHandle': 'target',
        'type': 'custom', 'zIndex': 0,
    }


# ---------------------------------------------------------------- 環境変数生成

def code_map_lines(root):
    """コードが解決できる全ノードの「経路,コード」行(中間段階も含む=更問い停止時も7桁が出る)"""
    lines = []

    def walk(n, seven, three, path):
        if n.parent is not None:
            path = path + [n.label]
            full = None
            if n.code is not None:
                if len(n.code) == 7 and not seven:
                    seven, three = n.code, None
                elif len(n.code) == 3:
                    three = n.code
                else:
                    full = n.code   # フルコード(上位の[7桁]の有無によらずそのまま使う)
            if full:
                lines.append('%s,%s' % ('/'.join(path), full))
            elif seven:
                lines.append('%s,%s' % ('/'.join(path), seven + (three or '')))
        for c in n.children:
            walk(c, seven, three, path)
    walk(root, None, None, [])
    return lines


def env_vars(root, stages, extras):
    out = []

    def walk(node):
        stage = stages[node.label]
        if stage.env:
            lines = []
            for i, c in enumerate(node.children, 1):
                lines.append('%d. %s: %s' % (i, c.label, c.definition) if c.definition
                             else '%d. %s' % (i, c.label))
            desc = extras.get('env_descriptions', {}).get(stage.env)
            if not desc:
                desc = ('%sの細分の分類基準。行を追記・編集すると判定に反映される'
                        '(ラベル名: 定義 または ラベル名のみ の形式。名前から分かるものは定義省略可)。' % stage.label)
                for bc in stage.branch_children():
                    desc += ' ※「%s」の行は条件分岐が名称を参照しているため名称変更不可。' % bc.label
            ids = extras.get('env_ids', {}).get(stage.env, {})
            out.append({
                'description': desc,
                'id': ids.get('id', 'env-' + stage.env.replace('_', '-')),
                'name': stage.env,
                'value': '\n'.join(lines),
                'value_type': ids.get('value_type', 'string'),
            })
        for c in stage.branch_children():
            walk(c)
    walk(root)
    return out


# ---------------------------------------------------------------- 全体組み立て

def postorder_sub(node, stages):
    """このノード配下(自身含む)のステージを「子孫が先」の順で返す"""
    out = []

    def walk(n):
        for c in n.children:
            if c.is_branch:
                walk(c)
        out.append(stages[n.label])
    walk(node)
    return out


def generate(tree_text, extras):
    root = parse_tree(tree_text)
    stages = build_stages(root, extras)

    # グループ別集約ノードのID(区分ごと)。線が各バンド内で完結するように2段集約にする
    used = {st.id for st in stages.values()} | {st.ifelse_id for st in stages.values() if st.ifelse_id}
    gagg_ids = {}
    for cat in root.children:
        if not cat.is_branch:
            continue
        suffix = stages[cat.label].id.replace('llm-sub-', '').replace('llm-', '')
        gid = 'aggregator-' + suffix
        k = 2
        while gid in used:
            gid, k = 'aggregator-%s%d' % (suffix, k), k + 1
        used.add(gid)
        gagg_ids[cat.label] = gid

    pos = compute_layout(root, stages, gagg_ids)

    nodes = [copy.deepcopy(n) for n in extras['scaffold_nodes']]
    for n in nodes:
        if n['id'] in pos:
            n['position'] = place(pos, n['id'])
            n['positionAbsolute'] = place(pos, n['id'])
    order = postorder(root, stages)

    stage_nodes = []
    def emit(node):
        stage = stages[node.label]
        stage_nodes.append(llm_node(stage, pos))
        if stage.ifelse_id:
            stage_nodes.append(ifelse_node(stage, stages, pos))
        for c in stage.branch_children():
            emit(c)
    emit(root)
    nodes += stage_nodes

    # グループ別集約ノード
    for cat in root.children:
        if not cat.is_branch:
            continue
        gid = gagg_ids[cat.label]
        data = {
            'desc': '%s系の判定結果を1つに集約します(最も深い判定が優先)。' % cat.label,
            'output_type': 'string',
            'selected': False,
            'title': '変数集約(%s)' % cat.label,
            'type': 'variable-aggregator',
            'variables': [[st.id, 'text'] for st in postorder_sub(cat, stages)],
        }
        nodes.append(node_shell(gid, data, place(pos, gid)))

    # 経路組み立て: 実行された段の出力を浅い順に「/」で連結する
    # (未実行の段は空、更問い(「質問」で始まる出力)は経路に含めない)
    path_order = sorted(stages.values(), key=lambda st: stage_depth(st))
    tp_parts = []
    for st in path_order:
        v = st.id.replace('-', '_')
        tp_parts.append("{%% if %s and %s[:2] != '質問' %%}%s{{ %s }}{%% endif %%}"
                        % (v, v, '' if st.is_root else '/', v))
    nodes.append(node_shell('template-path', {
        'desc': '判定で通ってきた経路を「流動資産/現預金・有価証券・貸付金/現金・預金/現金」のように「/」で連結します。',
        'selected': False,
        'template': ''.join(tp_parts),
        'title': '経路組み立て',
        'type': 'template-transform',
        'variables': [{'value_selector': [st.id, 'text'], 'variable': st.id.replace('-', '_')}
                      for st in path_order],
    }, place(pos, 'template-path')))

    # コード確定: 経路 → 勘定科目コード(共通7桁+会社別3桁)。対応表 code_map の最長一致で決定的に引く
    code_tmpl = (
        "{% set ns = namespace(code='', p=path) %}"
        "{% for _ in range(12) %}{% if ns.code == '' and ns.p %}"
        "{% for line in map.split('\\n') %}"
        "{% if line and line.split(',')[0] == ns.p %}{% set ns.code = line.split(',')[1] %}{% endif %}"
        "{% endfor %}"
        "{% if ns.code == '' %}{% set ns.p = ns.p.rsplit('/', 1)[0] if '/' in ns.p else '' %}{% endif %}"
        "{% endif %}{% endfor %}"
        "{{ ns.code if ns.code else 'コード未登録' }}")
    nodes.append(node_shell('template-code', {
        'desc': '経路から勘定科目コード(共通7桁、下3桁まで確定していれば10桁)を対応表 code_map で決定的に確定します。未登録は「コード未登録」。',
        'selected': False,
        'template': code_tmpl,
        'title': 'コード確定',
        'type': 'template-transform',
        'variables': [{'value_selector': ['template-path', 'output'], 'variable': 'path'},
                      {'value_selector': ['env', 'code_map'], 'variable': 'map'}],
    }, place(pos, 'template-code')))

    nodes_by_id = {n['id']: n for n in nodes}
    if len(nodes_by_id) != len(nodes):
        raise SystemExit('ノードIDが重複しています')

    # 全体集約: グループ別集約の結果(実行された1つだけが値を持つ)+ 区分判定
    agg = nodes_by_id['aggregator']
    agg['data']['variables'] = ([[gagg_ids[c.label], 'output'] for c in root.children if c.is_branch]
                                + [[stages[ROOT_LABEL].id, 'text']])

    # 終了ノード: main_account は経路(スラッシュ連結)、account_code は勘定科目コード
    end_node = nodes_by_id['end']
    for o in end_node['data']['outputs']:
        if o['variable'] == 'main_account':
            o['value_selector'] = ['template-path', 'output']
    if not any(o['variable'] == 'account_code' for o in end_node['data']['outputs']):
        end_node['data']['outputs'].append({'value_selector': ['template-code', 'output'],
                                            'variable': 'account_code'})
    end_node['data']['desc'] = '契約内容サマリー(認識確認用)、仕訳または更問い、判定経路(/区切り)、勘定科目コードを出力します。'

    # エッジ
    edges = []
    def E(src, handle, tgt):
        edges.append(make_edge(nodes_by_id, src, handle, tgt))
    E('start', 'source', 'doc-extractor')
    E('doc-extractor', 'source', 'llm-summary')
    E('llm-summary', 'source', 'if-else-confirm')
    E('if-else-confirm', 'case-unconfirmed', 'template-confirm')
    E('if-else-confirm', 'false', stages[ROOT_LABEL].id)
    E('template-confirm', 'source', 'aggregator-out')
    def wire(node, sink):
        stage = stages[node.label]
        if stage.ifelse_id:
            E(stage.id, 'source', stage.ifelse_id)
            for c in stage.branch_children():
                E(stage.ifelse_id, case_id_for(stages[c.label]), stages[c.label].id)
                # 区分の直下に入るときはグループ別集約に切り替える
                wire(c, gagg_ids[c.label] if node is root else sink)
            E(stage.ifelse_id, 'false', sink)
        else:
            E(stage.id, 'source', sink)
    wire(root, 'aggregator')
    for cat in root.children:
        if cat.is_branch:
            E(gagg_ids[cat.label], 'source', 'aggregator')
    E('aggregator', 'source', 'template-path')
    E('template-path', 'source', 'template-code')
    E('template-code', 'source', 'if-else-q')
    E('if-else-q', 'case-question', 'aggregator-out')
    E('if-else-q', 'false', 'llm-journal')
    E('llm-journal', 'source', 'aggregator-out')
    E('aggregator-out', 'source', 'end')

    # app 説明文
    leaves = []
    def count_leaves(n):
        for c in n.children:
            (leaves.append(c.label) if c.leaf else count_leaves(c))
    count_leaves(root)
    app = copy.deepcopy(extras['app'])
    app['description'] = (
        '契約書ファイルを読み込み、契約の主たる勘定科目を段階的に判定して、金額なしの仕訳(借方/貸方)と'
        '確信度・誤分類時の影響度を出力するワークフロー。初回実行は契約内容の認識確認で停止し、'
        '情報不足時は更問い(質問+回答例)を返す。分類は%dステージの段階判定で、最終ラベルは%d種類。'
        '細分の分類基準は環境変数 rules_*(%d個)で編集できる。'
        'このDSLはREADMEの分類ツリーから tools/generate_workflow.py で自動生成したもの。'
        % (len(order), len(leaves), sum(1 for st in stages.values() if st.env)))

    envs = env_vars(root, stages, extras)
    envs.append({
        'description': '経路→勘定科目コードの対応表(ツリーの[7桁][3桁]から自動生成。1行=「経路,コード」。'
                       '修正はツリー側が正で、ここでの編集は再生成までの応急対応)。',
        'id': 'env-code-map',
        'name': 'code_map',
        'value': '\n'.join(code_map_lines(root)),
        'value_type': 'string',
    })

    return {
        'app': app,
        'kind': 'app',
        'version': '0.1.5',
        'workflow': {
            'conversation_variables': extras.get('conversation_variables', []),
            'environment_variables': envs,
            'features': copy.deepcopy(extras['features']),
            'graph': {'edges': edges, 'nodes': nodes, 'viewport': {'x': 0, 'y': 0, 'zoom': 0.7}},
        },
    }



# --- ひな形(開始・サマリー・仕訳生成などの共通ノード)---
EXTRAS_JSON = "{\"app\":{\"description\":\"契約書ファイルを読み込み、契約の主たる勘定科目を段階的に判定して、金額なしの仕訳(借方/貸方)と確信度・誤分類時の影響度を出力するワークフロー。初回実行は契約内容の認識確認で停止し、情報不足時は更問い(質問+回答例)を返す。分類は19ステージの段階判定で、最終ラベルは82種類。細分の分類基準は環境変数 rules_*(14個)で編集できる。このDSLはREADMEの分類ツリーから tools/generate_workflow.py で自動生成したもの。\",\"icon\":\"📑\",\"icon_background\":\"#FFEAD5\",\"mode\":\"workflow\",\"name\":\"契約書 勘定科目区分分類\",\"use_icon_as_answer_icon\":false},\"features\":{\"file_upload\":{\"allowed_file_extensions\":[\".PDF\",\".DOC\",\".DOCX\",\".TXT\",\".MD\"],\"allowed_file_types\":[\"document\"],\"allowed_file_upload_methods\":[\"local_file\",\"remote_url\"],\"enabled\":true,\"fileUploadConfig\":{\"audio_file_size_limit\":50,\"batch_count_limit\":5,\"file_size_limit\":15,\"image_file_size_limit\":10,\"video_file_size_limit\":100,\"workflow_file_upload_limit\":10},\"image\":{\"enabled\":false,\"number_limits\":3,\"transfer_methods\":[\"local_file\",\"remote_url\"]},\"number_limits\":3},\"opening_statement\":\"\",\"retriever_resource\":{\"enabled\":true},\"sensitive_word_avoidance\":{\"enabled\":false},\"speech_to_text\":{\"enabled\":false},\"suggested_questions\":[],\"suggested_questions_after_answer\":{\"enabled\":false},\"text_to_speech\":{\"enabled\":false,\"language\":\"\",\"voice\":\"\"}},\"conversation_variables\":[],\"scaffold_nodes\":[{\"data\":{\"desc\":\"契約書ファイルをアップロードします。\",\"selected\":false,\"title\":\"開始\",\"type\":\"start\",\"variables\":[{\"allowed_file_extensions\":[],\"allowed_file_types\":[\"document\"],\"allowed_file_upload_methods\":[\"local_file\",\"remote_url\"],\"label\":\"契約書ファイル\",\"max_length\":48,\"options\":[],\"required\":true,\"type\":\"file\",\"variable\":\"contract_file\"},{\"label\":\"補足情報(更問いへの回答)\",\"max_length\":2000,\"options\":[],\"required\":false,\"type\":\"paragraph\",\"variable\":\"additional_info\"}]},\"height\":116,\"id\":\"start\",\"position\":{\"x\":80,\"y\":690},\"positionAbsolute\":{\"x\":80,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約書ファイルからテキストを抽出します。\",\"is_array_file\":false,\"selected\":false,\"title\":\"テキスト抽出\",\"type\":\"document-extractor\",\"variable_selector\":[\"start\",\"contract_file\"]},\"height\":116,\"id\":\"doc-extractor\",\"position\":{\"x\":384,\"y\":690},\"positionAbsolute\":{\"x\":384,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"契約書の読み取り内容(契約名・当事者・主目的・主要条件)を認識確認用に出力します。補足情報の訂正を反映します。\",\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-summary\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n与えられた契約書の本文から、勘定科目分類の前提となる要点を読み取り、次の形式で出力してください。\\nこの出力は「契約書の読み取りに認識間違いがないか」をユーザーが確認するために提示されます。\\n\\n【出力形式】(この形式のみを出力する。前置き・後書きは付けない)\\n契約名: <契約書の題名>\\n当事者: <当事者名と、読み取れる場合は自社の立場(貸主/借主、受託者/委託者、買主/売主 など)。読み取れない場合は「不明」と書く>\\n契約の主目的: <1行で>\\n主要条件: <期間・金額・支払条件など分類に影響する重要な条件を2〜3点、「 / 」区切りで>\\n特記事項: <分類に影響しそうな点があれば1行、なければ「なし」>\\n※ この認識に誤りがある場合は、「補足情報」欄で訂正して再実行してください。\\n\\n【ルール】\\n- 契約書に書かれていることだけを書き、推測で断定しない。読み取れない項目は「不明」とする。\\n- <補足情報>に訂正や回答が入っている場合は、その内容を事実として反映し、該当箇所に「(補足情報より)」と付記する。\\n- 最終行の「※ …」の注意書きは毎回そのまま出力する。\"},{\"id\":\"user-prompt-summary\",\"role\":\"user\",\"text\":\"以下は契約書の本文です。読み取り内容の要点を出力してください。\\n\\n<契約書本文>\\n{{#doc-extractor.text#}}\\n</契約書本文>\\n\\n<補足情報>\\n{{#start.additional_info#}}\\n</補足情報>\\n(補足情報は、過去の質問への回答や認識の訂正です。空の場合もあります。)\"}],\"selected\":false,\"title\":\"契約内容サマリー\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"enabled\":false}},\"height\":116,\"id\":\"llm-summary\",\"position\":{\"x\":688,\"y\":690},\"positionAbsolute\":{\"x\":688,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-unconfirmed\",\"conditions\":[{\"comparison_operator\":\"empty\",\"id\":\"cond-unconfirmed\",\"value\":\"\",\"varType\":\"string\",\"variable_selector\":[\"start\",\"additional_info\"]}],\"id\":\"case-unconfirmed\",\"logical_operator\":\"and\"}],\"desc\":\"補足情報が空(=認識結果が未確認)の場合は分類に進まず、確認要求を出力します。\",\"selected\":false,\"title\":\"条件分岐(認識確認)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-confirm\",\"position\":{\"x\":1296,\"y\":690},\"positionAbsolute\":{\"x\":1296,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"認識結果の確認を求めるメッセージを出力します(初回実行時)。\",\"selected\":false,\"template\":\"質問: 契約内容の認識結果(contract_summary)は合っていますか?内容を確認して、補足情報欄に回答を入力し、再実行してください。\\n回答例: 正しいです / 当社は借主です(誤りがある場合は、このように訂正内容を記入)\",\"title\":\"確認要求\",\"type\":\"template-transform\",\"variables\":[]},\"height\":116,\"id\":\"template-confirm\",\"position\":{\"x\":1296,\"y\":990},\"positionAbsolute\":{\"x\":1296,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"実行された分岐の判定結果を1つに集約します。\",\"output_type\":\"string\",\"selected\":false,\"title\":\"変数集約\",\"type\":\"variable-aggregator\",\"variables\":[[\"llm-sub-cash2\",\"text\"],[\"llm-sub-cash\",\"text\"],[\"llm-sub-rcv\",\"text\"],[\"llm-sub-pe\",\"text\"],[\"llm-sub-oca\",\"text\"],[\"llm-sub-ca\",\"text\"],[\"llm-sub-stb\",\"text\"],[\"llm-sub-pay\",\"text\"],[\"llm-sub-upc\",\"text\"],[\"llm-sub-utx\",\"text\"],[\"llm-sub-ocl\",\"text\"],[\"llm-sub-cl\",\"text\"],[\"llm-sub-pc\",\"text\"],[\"llm-sub-ent\",\"text\"],[\"llm-sub-ke\",\"text\"],[\"llm-sub-dep\",\"text\"],[\"llm-sub-pub\",\"text\"],[\"llm-sub-oe\",\"text\"],[\"llm-classify\",\"text\"]]},\"height\":150,\"id\":\"aggregator\",\"position\":{\"x\":3424,\"y\":860},\"positionAbsolute\":{\"x\":3424,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-question\",\"conditions\":[{\"comparison_operator\":\"start with\",\"id\":\"cond-question\",\"value\":\"質問\",\"varType\":\"string\",\"variable_selector\":[\"aggregator\",\"output\"]}],\"id\":\"case-question\",\"logical_operator\":\"and\"}],\"desc\":\"更問い(質問)の場合は仕訳を作らず、質問をそのまま出力へ流します。\",\"selected\":false,\"title\":\"条件分岐(更問いチェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-q\",\"position\":{\"x\":3728,\"y\":860},\"positionAbsolute\":{\"x\":3728,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"判定済みの主科目から、金額なしの仕訳(借方/貸方)と確信度・誤分類時の影響度を生成します。\",\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-journal\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n前段までの判定で、この契約書の主たる勘定科目(主科目)は「{{#aggregator.output#}}」と判定されています。\\n契約書の本文を読み、この契約の典型的な取引について仕訳を1本、金額なしで出力してください。\\n\\n【仕訳の作り方】\\n- 主科目を、会計原則に従って借方・貸方の正しい側に置く(資産の増加・費用の発生=借方、負債・純資産・収益の発生=貸方)。\\n- 相手科目は契約内容から最も典型的なものを1つ選ぶ。可能な限り本ワークフローの分類ラベル(預金、売掛金、未払金、営業収入 など)を使い、該当がなければ一般的な勘定科目名でよい。\\n- 継続的な契約(毎月の賃料・給与など)は、発生時点の典型仕訳を1本とする。\\n- この段階では質問(更問い)はしない。不明点は典型形を仮定したうえで、確信度を下げて表現する。\\n\\n【確信度の基準】\\n- 高: 契約書(と補足情報)に明確な根拠がある\\n- 中: 一部を推定で補っている\\n- 低: 情報が乏しく、典型形を仮定した\\n\\n【誤分類時の影響(リスク)の基準】\\n- 高: 貸借対照表と損益計算書をまたぐ誤り(資産計上か費用計上か等)や、税務(交際費の損金算入・少額判定、資産計上の要否等)に影響しうる\\n- 中: 流動・固定の区分や表示区分に影響する\\n- 低: 同一区分内の細分の違いにとどまり、損益や税額への影響がない\\n\\n【出力形式】(この5行のみを出力する。金額・前置き・後書きは付けない)\\n借方: <科目名>\\n貸方: <科目名>\\n確信度: 借方=高|中|低 / 貸方=高|中|低\\n確信度の補足: <根拠と推定箇所を1行で>\\n誤分類時の影響: 高|中|低 — <理由を1行で>\\n\\n【出力例】\\n借方: 賃借料\\n貸方: 預金\\n確信度: 借方=高 / 貸方=中\\n確信度の補足: 賃料の定めは契約条項に明確。支払方法は振込と推定。\\n誤分類時の影響: 低 — 経費内の細分違いにとどまり、損益や税額への影響はない。\"},{\"id\":\"user-prompt-journal\",\"role\":\"user\",\"text\":\"以下は契約書の本文です。判定済みの主科目「{{#aggregator.output#}}」を用いて、金額なしの仕訳と確信度・影響度を出力してください。\\n\\n<契約書本文>\\n{{#doc-extractor.text#}}\\n</契約書本文>\\n\\n<補足情報>\\n{{#start.additional_info#}}\\n</補足情報>\\n(補足情報は、過去の質問への回答です。空の場合もあります。)\"}],\"selected\":false,\"title\":\"仕訳生成\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"enabled\":false}},\"height\":116,\"id\":\"llm-journal\",\"position\":{\"x\":4032,\"y\":760},\"positionAbsolute\":{\"x\":4032,\"y\":760},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"仕訳または更問い(質問)を1つに集約します。\",\"output_type\":\"string\",\"selected\":false,\"title\":\"出力集約\",\"type\":\"variable-aggregator\",\"variables\":[[\"llm-journal\",\"text\"],[\"template-confirm\",\"output\"],[\"aggregator\",\"output\"]]},\"height\":116,\"id\":\"aggregator-out\",\"position\":{\"x\":4336,\"y\":860},\"positionAbsolute\":{\"x\":4336,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約内容サマリー(認識確認用)、仕訳または更問い、主科目ラベルを出力します。\",\"outputs\":[{\"value_selector\":[\"llm-summary\",\"text\"],\"variable\":\"contract_summary\"},{\"value_selector\":[\"aggregator-out\",\"output\"],\"variable\":\"classification_result\"},{\"value_selector\":[\"aggregator\",\"output\"],\"variable\":\"main_account\"}],\"selected\":false,\"title\":\"終了\",\"type\":\"end\"},\"height\":116,\"id\":\"end\",\"position\":{\"x\":4640,\"y\":860},\"positionAbsolute\":{\"x\":4640,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244}]}"


# ---------------------------------------------------------------- 実行

def main():
    ap = argparse.ArgumentParser(description='分類ツリーから Dify ワークフローYAMLを作る')
    ap.add_argument('tree', help='分類ツリーのファイル(.md)')
    ap.add_argument('-o', '--output', default='contract-account-classification.yml')
    args = ap.parse_args()

    if not os.path.exists(args.tree):
        print('■ ファイルが見つかりません: %s' % args.tree)
        sys.exit(1)
    text = io.open(args.tree, encoding='utf-8').read()
    extras = json.loads(EXTRAS_JSON)
    try:
        d = generate(text, extras)
    except SystemExit as e:
        print('')
        print('■ 変換できませんでした')
        print(str(e))
        print('')
        print('※ このメッセージをそのまま伝えず、内容をかみくだいて利用者に質問してください。')
        sys.exit(1)

    with io.open(args.output, 'w', encoding='utf-8') as f:
        f.write(dump(d))

    g = d['workflow']['graph']
    kinds = {}
    for n in g['nodes']:
        t = n['data']['type']
        kinds[t] = kinds.get(t, 0) + 1
    print('■ 変換しました: %s' % args.output)
    print('  ノード %d個 / エッジ %d個 / 環境変数 %d個'
          % (len(g['nodes']), len(g['edges']), len(d['workflow']['environment_variables'])))
    print('  内訳: ' + ' / '.join('%s %d' % (k, v) for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
    print('')
    print('次: Dify の「アプリを作成 → DSLファイルをインポート」で取り込んでください。')


if __name__ == '__main__':
    main()
