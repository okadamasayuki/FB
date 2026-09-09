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

    python3 ツリーからDify.py 分類ツリー_10桁.md
      → contract-account-classification-pick.yml(コード一発選択形式)ができます
      → どの形式も、まず契約の一般的な仕訳の流れ(3〜5行)を整理してキャッシュ(現金・預金)の
        相手勘定を1つ特定し、その科目の勘定科目コードを確定します。違いはコードの決め方だけ:
        10桁/7桁の候補を横並びで1回で選ぶ既定の --pick、分類ツリーを1段ずつ下りる --tree、
        7桁を横並びで選び紐付く10桁を書き分けの定義で絞り込む --flat、3形式ぜんぶは --all
      → 従来のフォーム入力(入力欄で実行するworkflow)は --form、一発選択+フォームは --both
      → --learn を付けると自己学習つき(チャットで「正解: ◯◯」と返信すると判定事例カードを返し、
        次回から似た契約の判定前に過去の事例を参考にする)。既定の --learn-mode env は
        ナレッジもAPIキーも不要(⑤がまとめた 判定事例.txt をアプリの環境変数 learned_cases に貼る)
      → --learn-mode kb にするとDifyの事例ナレッジ方式(検索ノード+ナレッジ登録APIで自動保存。
        ナレッジの作成と環境変数 dify_base_url / dataset_api_key / case_dataset_id が必要で、
        「類似事例の検索」ノードでナレッジを選ぶまで公開できません)
      → kb でさらに --learn-dataset-id / --learn-base-url / --learn-dataset-key を付けると、
        ナレッジの選択と環境変数が設定済みの「設定込みDSL」になります(インポート後の再設定が不要。
        キーはDSLに平文で入るため、ファイルの共有先に注意)

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
   - LLMノードの数(コード一発選択=4、コード2段選択=5、
     ツリー判定=判定の段の数+3、フォーム=判定の段の数+3 になるはずです)
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
取り込むと、契約書をチャットで読み取って、仕訳の流れを整理し、キャッシュ(現金・預金)の
相手勘定となる勘定科目とそのコードを返すアプリになります
(--form で作った場合だけ、入力欄で実行する従来のワークフローです)。

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

USER_BODY = ('\n\n<契約書本文>\n{{#aggregator_text.output#}}\n</契約書本文>\n\n'
             '<補足情報>\n{{#start.additional_info#}}\n</補足情報>\n'
             '(補足情報は、過去の質問への回答です。空の場合もあります。)')

SUPPLEMENT_SECTION = [
    '【補足情報の扱い】',
    '- ユーザー入力の<補足情報>には、過去にあなたが出力した質問への回答が入っていることがある。契約書本文と合わせて判定に使うこと。',
]

# チャット版(advanced-chat)は本文を会話変数から読み、回答・訂正は会話履歴(memory)で受け取る。
# 3形式共通の前段(llm_journal)が特定した相手勘定を判定対象として各段に渡す
USER_BODY_CHAT = ('\n\n<仕訳の分析>\n{{#llm_journal.text#}}\n</仕訳の分析>\n\n'
                  '<契約書本文>\n{{#conversation.contract_text#}}\n</契約書本文>\n\n'
                  '<読み取り内容(確認済み)>\n{{#conversation.contract_summary#}}\n</読み取り内容>\n'
                  '(仕訳の分析の「相手勘定」「性質」を判定の中心に置き、これまでの会話でのユーザーの回答・訂正も判断材料に使うこと。)')

SUPPLEMENT_SECTION_CHAT = [
    '【会話の扱い】',
    '- ユーザー入力の<仕訳の分析>は、前段で整理した仕訳の流れとキャッシュ(現金・預金)の相手勘定の特定結果。判定はこの相手勘定を対象に行うこと。',
    '- これまでの会話には、読み取り内容へのユーザーの確認・訂正や、過去にあなたが出力した質問への回答が入っていることがある。契約書本文と合わせて判定に使うこと。',
]

# 会計方針・判定ルールの既定値(1,008通のE2Eテストの誤答分析で判明した迷いどころを初期値として収載。
# 環境変数 accounting_policy としてアプリ側で自由に書き足せる)
ACCOUNTING_POLICY_DEFAULT = (
    '- リース・長期の賃借契約: 契約期間が1年超で中途解約できない(または解約に高額な違約金が伴う)場合は、'
    '費用処理ではなく使用権資産とリース債務を計上する。少額または1年以内の短期リースのみ費用処理とする\n'
    '- 貸付金・借入金の長期/短期: 返済期限が1年超なら長期(長期貸付金・長期借入金 など)、1年以内なら短期として区分する\n'
    '- 人材紹介(採用の成功報酬)の紹介手数料は、人材派遣料ではなく「その他経費」とする\n'
    '- 自社が売主・貸主・受託者など「対価を受け取る側」の契約では、収益側の仕訳'
    '(売掛金・営業収入・前受収益・受入敷金 など)を書く')

# 会話履歴の渡し方。参考にした社内チャットフロー(契約仕訳アシスタント)の設定をそのまま使う
MEMORY_BLOCK = {
    'query_prompt_template': '{{#sys.query#}}',
    'role_prefix': {'assistant': '', 'user': ''},
    'window': {'enabled': False, 'size': 50},
}

QUESTION_SECTION_HEAD = [
    '【更問い(判定に必要な情報が無い場合)】',
    '- 契約書本文と補足情報を読んでも判定に必要な情報が不足している場合は、ラベルを出力する代わりに、次の2行の形式で質問を出力する。',
    '  質問: (このノードの判定に必要な点を1つだけ、選択式で答えられるように聞く)',
    '  回答例: (ユーザーがそのまま使える回答の文例を「 / 」区切りで2〜3個示す)',
    '- 質問は1回の出力につき1つだけとし、判定を最も左右する点を聞くこと。',
    '- このノードでの質問の例:',
]

QUESTION_SECTION_HEAD_CHAT = [
    '【更問い(判定に必要な情報が無い場合)】',
    '- 仕訳の分析・契約書本文とこれまでの会話を読んでも判定に必要な情報が不足している場合は、ラベルを出力する代わりに、次の2行の形式で質問を出力する。',
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
    elif definition:
        # 「ラベル: 定義 [1234]」のように定義文側にコードが紛れ込んでも拾う
        m = re.search(r'\s*\[(\d+)\]\s*$', definition) or re.match(r'^\[(\d+)\]\s*', definition)
        if m:
            node.code = m.group(1)
            node.definition = (definition[:m.start()] + definition[m.end():]).strip() or None
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
    # 同じ名前の分岐が別の場所にあっても、経路で区別するので問題ない(参考として知らせるだけ)
    labels, dups = [ROOT_LABEL], []

    def collect(n):
        for c in n.children:
            if c.is_branch:
                if c.label in labels and c.label not in dups:
                    dups.append(c.label)
                labels.append(c.label)
            collect(c)
    collect(root)
    if dups:
        sys.stderr.write('同じ名前の分岐が複数あります(別のものとして扱います): %s\n'
                         % '、'.join(dups[:10]))

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

def node_key(node):
    """ステージを引くためのキー。同じ名前の分岐が複数あってもぶつからないよう、経路で持つ"""
    parts = []
    n = node
    while n.parent is not None:
        parts.append(n.label)
        n = n.parent
    return '/'.join(reversed(parts)) or ROOT_LABEL


class Stage(object):
    """細分判定を1回行う単位(=LLMノード1つ。分岐する子があれば if-else も持つ)"""

    def __init__(self, node, extras, used_ids, taken):
        self.node = node
        self.label = node.label
        self.env = node.env
        self.is_root = node.parent is None
        self.is_sub = node.parent is not None and node.parent.parent is None
        ex = extras.get('stages', {}).get(self.label, {})
        self.ex = ex
        self.title_prefix = ''
        # 同じラベルの分岐が複数あると extras の固定IDを取り合うので、先に来た方だけが使う
        cand = ex.get('id')
        self.id = cand if (cand and cand not in taken) else self._new_id(used_ids)
        taken.add(self.id)
        used_ids.add(self.id)
        self.ifelse_id = None
        if self.branch_children():
            cand = (ex.get('ifelse') or {}).get('id')
            self.ifelse_id = cand if (cand and cand not in taken) else self._new_ifelse_id(used_ids)
            taken.add(self.ifelse_id)
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
    used_ids, taken = set(), set()
    for st in extras.get('stages', {}).values():
        used_ids.add(st.get('id'))
        if st.get('ifelse'):
            used_ids.add(st['ifelse'].get('id'))
    stages = {}

    def walk(node):
        stage = Stage(node, extras, used_ids, taken)
        stages[node_key(node)] = stage
        for c in stage.branch_children():
            walk(c)
    walk(root)
    # 同じ名前の分岐が複数ある場合、Difyの画面で見分けが付くようタイトルに親を添える
    seen = {}
    for st in stages.values():
        seen[st.label] = seen.get(st.label, 0) + 1
    for st in stages.values():
        if seen[st.label] > 1 and st.node.parent is not None:
            st.title_prefix = st.node.parent.label + '/'
    return stages


def postorder(root, stages):
    """集約は「子孫のステージが先」の順(最深の実行結果が勝つ)"""
    out = []

    def walk(node):
        for c in node.children:
            if c.is_branch:
                walk(c)
        out.append(stages[node_key(node)])
    walk(root)
    return out


# ---------------------------------------------------------------- プロンプト生成

def numbered_defs(children, defs):
    lines = []
    for i, c in enumerate(children, 1):
        d = c.definition or defs.get(c.label, '')
        lines.append('%d. %s(例: %s)' % (i, c.label, d) if d else '%d. %s' % (i, c.label))
    return lines


def system_prompt(stage, chat=False):
    node, ex = stage.node, stage.ex
    children = [c for c in node.children if not (stage.is_root and c.note)]
    n = len(children)
    lines = ['あなたは日本の企業会計に精通した経理・会計の専門家です。']
    read_src = '仕訳の分析と契約書の本文' if chat else '契約書の本文'
    if stage.is_root:
        if chat:
            lines.append('前段の仕訳分析で、この契約のキャッシュ(現金・預金)の相手勘定となる勘定科目が特定されています。'
                         'その相手勘定が主として属する勘定科目区分を1つだけ判定し、区分名のラベルのみを出力してください。')
        else:
            lines.append('与えられた契約書の本文を読み、その契約が主として関係する勘定科目区分を1つだけ判定し、区分名のラベルのみを出力してください。')
    else:
        subject = 'この契約の相手勘定(勘定科目)' if chat else 'この契約書'
        if stage.is_sub:
            lines.append('%sは、前段の判定で勘定科目区分「%s」に該当すると判定されています。' % (subject, stage.label))
        else:
            lines.append('%sは、前段の判定で%sのうち「%s」に該当すると判定されています。'
                         % (subject, stage.parent_phrase(), stage.label))
        if stage.env:
            lines.append('下記の【分類基準】に従い、最も適切な細分を1つだけ判定し、ラベルのみを出力してください。')
        elif stage.is_sub:
            lines.append('%sを読み、次の%dの小区分のうち最も適切なものを1つだけ判定し、小区分名のラベルのみを出力してください。' % (read_src, n))
        else:
            lines.append('%sを読み、次の%dつの細分のうち最も適切なものを1つだけ判定し、ラベルのみを出力してください。' % (read_src, n))
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
    lines += [''] + (SUPPLEMENT_SECTION_CHAT if chat else SUPPLEMENT_SECTION)
    lines += [''] + (QUESTION_SECTION_HEAD_CHAT if chat else QUESTION_SECTION_HEAD)
    question = stage.ex.get('question')
    if not question:
        opts = [c.label for c in node.children[:3]]
        question = ['質問: この契約は次のどれに最も近いですか?(%s)' % ' / '.join(opts),
                    '回答例: %s' % ' / '.join('%sです' % o for o in opts[:2])]
    lines += ['  ' + q for q in question]
    return '\n'.join(lines)


def user_prompt(stage, chat=False):
    if chat:
        # extras の user_intro はフォーム版の文面なので、チャット版は相手勘定の判定文に組み替える
        if stage.is_root:
            intro = '以下は前段の仕訳分析と契約書の本文です。相手勘定の勘定科目区分を判定し、ラベル名のみを出力してください。'
        elif stage.is_sub:
            intro = '以下は前段の仕訳分析と契約書の本文です。%sの小区分を判定し、ラベル名のみを出力してください。' % stage.label
        else:
            intro = '以下は前段の仕訳分析と契約書の本文です。この%sの細分を判定し、ラベル名のみを出力してください。' % stage.label
        return intro + USER_BODY_CHAT
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
LEARN_Y = -140     # 自己学習レーン(最上部。どの形式のノードとも重ならない)
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
    ga_col = max(11, 9 + 2 * max_depth)

    # スキャフォールド(メインの横ライン+上部レーン)
    pos['start'] = (colx(0), SCAF_Y)
    pos['doc-extractor'] = (colx(1), SCAF_Y)
    pos['template-join'] = (colx(2), SCAF_Y)
    pos['if-else-read'] = (colx(3), SCAF_Y)
    pos['llm_read'] = (colx(4), TOP_Y)
    pos['aggregator_text'] = (colx(4), SCAF_Y)
    pos['if-else-text'] = (colx(5), SCAF_Y)
    pos['template-scan'] = (colx(5), TOP_Y)
    pos['llm_summary'] = (colx(6), SCAF_Y)
    pos['if-else-confirm'] = (colx(7), SCAF_Y)
    pos[stages[node_key(root)].id] = (colx(8), SCAF_Y)
    if stages[node_key(root)].ifelse_id:
        pos[stages[node_key(root)].ifelse_id] = (colx(9), SCAF_Y)
    pos['template-confirm'] = (colx(8), TOP_Y)
    pos['aggregator'] = (colx(ga_col + 1), AGG_Y + 150)
    pos['template_path'] = (colx(ga_col + 2), AGG_Y + 150)
    pos['template_code'] = (colx(ga_col + 3), AGG_Y + 150)
    pos['if-else-q'] = (colx(ga_col + 4), AGG_Y + 370)
    pos['llm_journal'] = (colx(ga_col + 5), AGG_Y + 590)
    pos['aggregator-out'] = (colx(ga_col + 6), AGG_Y)
    pos['end'] = (colx(ga_col + 7), AGG_Y)

    # 区分ごとのバンド。行0 = 小区分判定+深い段(4段目)の行、行1〜 = 細分判定、
    # 最下行の下 = グループ集約(合流レーン)。合流の線がバンドの下側を通り、交差しない。
    band_y = BANDS_Y0
    for cat in root.children:
        if not cat.is_branch:
            continue
        head = stages[node_key(cat)]
        sub_stages = [stages[node_key(c)] for c in cat.children if c.is_branch]
        rows = 1 + len(sub_stages)
        pos[head.id] = (colx(10), band_y)
        if head.ifelse_id:
            pos[head.ifelse_id] = (colx(11), band_y)
        for i, st in enumerate(sub_stages):
            y = band_y + ROW * (1 + i)
            pos[st.id] = (colx(8 + 2 * stage_depth(st)), y)
            if st.ifelse_id:
                pos[st.ifelse_id] = (colx(9 + 2 * stage_depth(st)), y)

            def deeper(node):
                for c in node.children:
                    if not c.is_branch:
                        continue
                    dst = stages[node_key(c)]
                    pos[dst.id] = (colx(8 + 2 * stage_depth(dst)), y)
                    if dst.ifelse_id:
                        pos[dst.ifelse_id] = (colx(9 + 2 * stage_depth(dst)), y)
                    deeper(c)
            deeper(st.node)
        gy = band_y + rows * ROW + 70
        pos[gagg_ids[node_key(cat)]] = (colx(ga_col), gy)
        band_y = gy + 116 + BAND_GAP
    return pos


def place(pos, nid):
    x, y = pos[nid]
    return {'x': x, 'y': y}


def node_shell(nid, data, pos, height=116):
    return {'data': data, 'height': height, 'id': nid,
            'position': pos, 'positionAbsolute': dict(pos), 'selected': False,
            'sourcePosition': 'right', 'targetPosition': 'left', 'type': 'custom', 'width': 244}


def llm_node(stage, pos, chat=False):
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
            {'id': 'system-prompt-%s' % suffix, 'role': 'system', 'text': system_prompt(stage, chat)},
            {'id': 'user-prompt-%s' % suffix, 'role': 'user', 'text': user_prompt(stage, chat)},
        ],
        'selected': False,
        'title': stage.ex.get('title') or ('%s%s 細分判定' % (stage.title_prefix, stage.label)),
        'type': 'llm',
        'variables': [],
        'vision': {'enabled': False},
    }
    if chat:
        data['memory'] = copy.deepcopy(MEMORY_BLOCK)
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
        case, value = make_case(stage, stages[node_key(c)])
        cases.append(case)
        values.append(value)
    # ケースは値の長い順に並べる(Difyは上から順に評価するため、
    # 「その他」と「その他の◯◆」のような前方一致の包含関係があっても正しく振り分けられる)
    pairs = sorted(zip(cases, values, branch), key=lambda t: -len(t[1]))
    cases = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    # 前方一致の衝突: 分岐同士の包含は上記の並びで解決する。
    # ケースを持たない葉ラベル(例: 「その他の金融負債」)がケース値(例: 「その他」)に
    # 飲み込まれる場合は、そのケースだけ完全一致に切り替える
    # (葉ラベルはどのケースにも一致せず ELSE に落ち、その段の出力として正しく集約される)
    for case, v, bc in pairs:
        for c in stage.node.children:
            if c.label == bc.label or c.is_branch:
                continue
            if c.label.startswith(v):
                case['conditions'][0]['comparison_operator'] = 'is'
                break
    for c in stage.node.children:
        if c.label.startswith('質問'):
            raise SystemExit('「質問」で始まるラベルは使えません: %s' % c.label)
    if len(set(values)) != len(values):
        raise SystemExit('条件分岐のケース値が重複しています: %s' % values)
    ex_if = stage.ex.get('ifelse') or {}
    if stage.is_root:
        default_title, default_desc = '条件分岐', '細分を持つ区分の場合のみ小区分判定へ分岐します。'
    else:
        default_title = '条件分岐(%s%s細分)' % (stage.title_prefix, stage.label)
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


def codes7_lines(root):
    """7桁コードの候補一覧(横並び)。[7桁]の宣言行と、フルコード行の上7桁から作る。
    1行=「- 経路 [7桁]: 定義」。コード選択形式(flat)の1段目の選択肢になる"""
    lines, seen = [], set()

    def walk(n, seven, path):
        if n.parent is not None:
            path = path + [n.label]
            if n.code is not None:
                cand = None
                if len(n.code) == 7 and not seven:
                    seven = cand = n.code
                elif len(n.code) not in (3, 7):
                    cand = n.code[:7]   # フルコード行
                if cand and cand not in seen:
                    seen.add(cand)
                    d = ': ' + n.definition if n.definition else ''
                    lines.append('- %s [%s]%s' % ('/'.join(path), cand, d))
        for c in n.children:
            walk(c, seven, path)
    walk(root, None, [])
    return lines


def codes10_lines(root):
    """7桁→10桁の対応表(書き分け)。「[7桁] 経路」の見出しの下に、
    配下の「  - 名称 [3桁]: 定義」を並べる。コード選択形式(flat)の2段目の選択肢になる"""
    groups, order = {}, []

    def group(seven, path):
        if seven not in groups:
            groups[seven] = ('/'.join(path), [])
            order.append(seven)
        return groups[seven][1]

    def walk(n, seven, path):
        if n.parent is not None:
            path = path + [n.label]
            if n.code is not None:
                if len(n.code) == 7 and not seven:
                    seven = n.code
                    group(seven, path)
                elif len(n.code) == 3 and seven:
                    group(seven, path[:-1]).append((n.label, n.code, n.definition or ''))
                elif len(n.code) not in (3, 7):
                    group(n.code[:7], path[:-1]).append((n.label, n.code[7:], n.definition or ''))
        for c in n.children:
            walk(c, seven, path)
    walk(root, None, [])
    lines = []
    for seven in order:
        head, items = groups[seven]
        lines.append('[%s] %s' % (seven, head))
        for label, three, d in items:
            lines.append('  - %s [%s]%s' % (label, three, ': ' + d if d else ''))
    return lines


def codes_pick_lines(root):
    """全コード候補の横並び一覧(一発選択用)。10桁がある科目は「- 経路/名称 [10桁]: 定義」、
    10桁が無い7桁は「- 経路 [7桁]: 定義」。コード一発選択形式(pick)の選択肢になる"""
    groups, order = {}, []

    def g(seven, path, d=None):
        if seven not in groups:
            groups[seven] = ['/'.join(path), d or '', []]
            order.append(seven)
        return groups[seven]

    def walk(n, seven, path):
        if n.parent is not None:
            path = path + [n.label]
            if n.code is not None:
                if len(n.code) == 7 and not seven:
                    seven = n.code
                    g(seven, path, n.definition or '')
                elif len(n.code) == 3 and seven:
                    g(seven, path[:-1])[2].append((n.label, n.code, n.definition or ''))
                elif len(n.code) not in (3, 7):
                    g(n.code[:7], path[:-1])[2].append((n.label, n.code[7:], n.definition or ''))
        for c in n.children:
            walk(c, seven, path)
    walk(root, None, [])
    lines = []
    for seven in order:
        head, d7, items = groups[seven]
        if items:
            for label, three, d in items:
                lines.append('- %s/%s [%s%s]%s' % (head, label, seven, three, ': ' + d if d else ''))
        else:
            lines.append('- %s [%s]%s' % (head, seven, ': ' + d7 if d7 else ''))
    return lines


# ---------------------------------------------------------------- チャット入り口の共通部品
# 入力・読み取り・認識確認・仕訳の流れ分析(相手勘定の特定)・更問いチェックまでは
# 3つの判定形式(ツリー判定・コード2段選択・コード一発選択)で同一構成にする

CHAT_FRONT_IDS = ['start', 'doc-extractor', 'template-plain', 'if-else-read', 'llm_read',
                  'template-join-read', 'save-text-read', 'template-join', 'save-text',
                  'if-else-att', 'llm_summary', 'save-summary', 'answer-confirm',
                  'llm_journal', 'if-else-q', 'answer-q']


def env_check_simple(pos):
    """company_name の設定漏れだけを点検する軽量版の設定チェック(判定形式ごとの変種用)"""
    return node_shell('env_check', {
        'desc': '環境変数の設定漏れを点検し、未設定なら注意書きを作ります(設定済みなら何も出しません)。',
        'selected': False,
        'template': "{% if (company | trim) == '' %}\n\n---\n"
                    '⚠️ 環境変数 company_name(自社名)が未設定です。アプリ設定の「環境変数」で自社の正式社名を'
                    '設定すると、判定の向き(自社がどちらの当事者か)の取り違えを防げます。'
                    'それまでは、チャットで「当社は◯◯です」と伝えてください。{% endif %}',
        'title': '設定チェック',
        'type': 'template-transform',
        'variables': [{'value_selector': ['env', 'company_name'], 'variable': 'company'}],
    }, place(pos, 'env_check'), height=82)


def chat_front(extras, pos, learn=False, learn_cfg=None):
    """3形式共通の入り口(開始〜読み取り〜認識確認〜仕訳の流れ分析〜更問いチェック)を組み立てる。
    learn=True なら自己学習(事例ナレッジの検索・「正解:」返信での自動保存)も組み込む。
    learn_cfg にナレッジIDがあれば「類似事例の検索」ノードに選択済みで入れる"""
    by_id = {n['id']: n for n in extras['chat']['scaffold_nodes']}
    nodes = [copy.deepcopy(by_id[i]) for i in CHAT_FRONT_IDS]
    nodes.append(env_check_simple(pos))
    if learn:
        cfg = learn_cfg_norm(learn_cfg)
        if cfg['mode'] == 'env':   # ナレッジ無しの短いレーン
            pos['code_cases'] = (colx(8), LEARN_Y)
            pos['llm_case'] = (colx(9), LEARN_Y)
            pos['answer-case'] = (colx(10), LEARN_Y)
        nodes += learn_nodes(pos, cfg)
        for n in nodes:
            if n['id'] == 'llm_journal':
                learn_journal_patch(n, cfg['mode'])
    for n in nodes:
        if n['id'] in pos:
            n['position'] = place(pos, n['id'])
            n['positionAbsolute'] = place(pos, n['id'])
    return nodes


def chat_front_edges(E, learn=False, mode='env'):
    E('start', 'source', 'doc-extractor')
    E('doc-extractor', 'source', 'template-plain')
    E('template-plain', 'source', 'if-else-read')
    E('if-else-read', 'case-need-read', 'llm_read')
    E('llm_read', 'source', 'template-join-read')
    E('template-join-read', 'source', 'save-text-read')
    E('save-text-read', 'source', 'if-else-att')
    E('if-else-read', 'false', 'template-join')
    E('template-join', 'source', 'save-text')
    E('save-text', 'source', 'if-else-att')
    E('if-else-att', 'true', 'llm_summary')
    E('llm_summary', 'source', 'save-summary')
    E('save-summary', 'source', 'env_check')
    E('env_check', 'source', 'answer-confirm')
    if learn and mode == 'env':
        E('if-else-att', 'false', 'if-else-learn')
        E('if-else-learn', 'case-teach', 'llm_case')
        E('llm_case', 'source', 'answer-case')
        E('if-else-learn', 'false', 'code_cases')
        E('code_cases', 'source', 'llm_journal')
    elif learn:
        E('if-else-att', 'false', 'if-else-learn')
        E('if-else-learn', 'case-teach', 'learn_gate')
        E('learn_gate', 'source', 'llm_case')
        E('llm_case', 'source', 'if-else-learn-set')
        E('if-else-learn-set', 'case-set', 'code_case_body')
        E('code_case_body', 'source', 'http_save_case')
        E('http_save_case', 'source', 'answer-learned')
        E('if-else-learn-set', 'false', 'answer-nolearn')
        E('if-else-learn', 'false', 'code_pagecases')
        E('code_pagecases', 'source', 'kr_cases')
        E('kr_cases', 'source', 'llm_journal')
    else:
        E('if-else-att', 'false', 'llm_journal')
    E('llm_journal', 'source', 'if-else-q')
    E('if-else-q', 'case-question', 'answer-q')


def judge_answer_final(extras, pos, answer, desc):
    by_id = {n['id']: n for n in extras['chat']['scaffold_nodes']}
    af = copy.deepcopy(by_id['answer-final'])
    af['data']['answer'] = answer
    af['data']['desc'] = desc
    af['position'] = place(pos, 'answer-final')
    af['positionAbsolute'] = place(pos, 'answer-final')
    return af


ANSWER_TAIL = '\n\n---\n(誤りや補足があれば、そのまま返信してください。判定し直します。)'

ANSWER_FINAL_DESC = '確定した相手勘定(勘定科目)とコードの表、または更問い(質問)を返信します。'

# 3形式共通のアプリ名・説明文の部品(コードの決め方だけが形式ごとに違う)
CHAT_APP_NAME = '契約書 相手勘定判定'

CHAT_DESC_HEAD = ('契約書(PDF・画像・テキスト)をチャットに添付すると、読み取った内容を確認したうえで、'
                  '契約で発生する一般的な仕訳の流れ(3〜5行)を整理し、キャッシュ(現金・預金)の'
                  '相手勘定となる勘定科目を1つ判定するチャットフロー。'
                  '文字を取り出せないスキャンPDFや画像はAIが直接読み取る。')

CHAT_DESC_TAIL = ('回答は相手勘定・確定コード・判定経路・理由・根拠の仕訳の表を1つ返す。'
                  '情報が足りない場合はAIが質問し、回答すると確定するまで対話を継続する。'
                  'このDSLはREADMEの分類ツリーから tools/generate_workflow.py で自動生成したもの。')


def chat_opening(method, learn=False, mode='env'):
    out = ('契約書(PDF・画像・テキスト)をアップロードし、テキスト欄に「.」など任意の1文字を入れて送信してください(入力した文字は使われません)。\n'
           'まず契約書から読み取った内容(契約名・当事者・主目的など)をお見せします。「OK」または訂正内容を返信いただくと、'
           '契約の一般的な仕訳の流れを整理し、キャッシュ(現金・預金)の相手勘定となる勘定科目を1つ判定して、'
           '勘定科目コードを確定します(コードの確定方法: %s)。\n'
           '情報が足りない場合は質問しますので、回答を送っていただければ確定するまで対話を続けます。' % method)
    if learn and mode == 'env':
        out += ('\n判定が違っていたら「正解: ◯◯」と返信してください。判定事例カードを返します。⑤の自動学習が集めた 判定事例.txt を'
                'アプリの環境変数 learned_cases に貼ると、次回から似た契約の判定で自動的に参考にします。')
    elif learn:
        out += ('\n判定が違っていたら「正解: ◯◯」と返信してください。判定事例カードを作って事例ナレッジに保存し'
                '(保存先が未設定ならカードを返信します)、次回から似た契約の判定で自動的に参照します。')
    return out


def learn_desc_note(learn_cfg):
    """アプリ説明文の自己学習の注記(設定込みで生成した場合は「設定済み」と書く)"""
    cfg = learn_cfg_norm(learn_cfg)
    if cfg['mode'] == 'env':
        return ('自己学習つき(ナレッジ・APIキー不要): チャットで「正解: ◯◯」と返信すると判定事例カードを返す。'
                '環境変数 learned_cases に貼った事例(⑤の自動学習が出す 判定事例.txt)から、判定前に似た契約の事例を選んで参考にする。')
    done = cfg['base_url'] and cfg['dataset_key'] and cfg['dataset_id']
    return ('自己学習(事例ナレッジ)つき: チャットで「正解: ◯◯」と返信すると判定事例カードを作って'
            'Difyのナレッジに自動保存し、次回から似た契約の判定前に検索して参考にする'
            + ('(保存先のナレッジと環境変数は生成時に設定済み)。' if done else
               '(ナレッジの作成と環境変数 dify_base_url / dataset_api_key / case_dataset_id の設定が必要。'
               '未設定でも判定は動き、「正解:」の返信には判定事例カードの文面が返る)。'))


COMPANY_ENV = {
    'description': '自社の会社名。判定を必ず自社の視点で行わせるために使う(契約書のどちらの当事者が自社かの特定に効く)。',
    'id': 'env-company-name',
    'name': 'company_name',
    'value': '',
    'value_type': 'string',
}

POLICY_ENV = {
    'description': '会社の会計方針・判定ルール(自由記述)。判定で迷いやすい点をここに書き足すと次回から反映される。',
    'id': 'env-accounting-policy',
    'name': 'accounting_policy',
    'value': ACCOUNTING_POLICY_DEFAULT,
    'value_type': 'string',
}


# ---------------------------------------------------------------- 自己学習(B案: 事例ナレッジ)
# チャットで「正解: ◯◯」と返信すると事例カードを作ってDifyのナレッジに自動保存し、
# 次回から判定前に似た事例を検索して仕訳の流れ分析(相手勘定の特定)に渡す。
# 保存先が未設定でも判定は通常どおり動く(検索は空・「正解:」にはカードの文面だけを返す)。
# ⑤の自動学習ページはナレッジAPIキーが無いとき、返ってきたカードをブラウザ側の仮ナレッジに溜め、
# 次の判定の「OK」に「参考事例:」として添える(code_pagecases が取り出して判定プロンプトへ渡す)。

LEARN_ENVS = [{
    'description': 'DifyのAPIエンドポイント(例: https://dify.example.com/v1)。自己学習の事例保存に使う。'
                   '各アプリの「APIアクセス」画面に表示されるAPIサーバーのURLと同じ。',
    'id': 'env-dify-base-url',
    'name': 'dify_base_url',
    'value': '',
    'value_type': 'string',
}, {
    'description': 'ナレッジ(データセット)APIキー(dataset-…)。Difyの「サービスAPI」→「APIキー」で発行(1.12以降はナレッジ一覧の右上、1.9〜1.11はナレッジを開いた左メニューの一番下、1.8以前は一覧左上の「API ACCESS」タブ)。'
                   'アプリのAPIキー(app-…)とは別物。',
    'id': 'env-dataset-api-key',
    'name': 'dataset_api_key',
    'value': '',
    'value_type': 'string',
}, {
    'description': '事例ナレッジのID。Difyで空のナレッジを1つ作り、そのURLの /datasets/<この部分>/documents を貼る。'
                   '判定前の類似事例検索は「類似事例の検索」ノードにも同じナレッジを選ぶ(1回だけ)。',
    'id': 'env-case-dataset-id',
    'name': 'case_dataset_id',
    'value': '',
    'value_type': 'string',
}]

LEARN_JOURNAL_SECTION = '# 過去の正解事例(あれば最優先で参考にする)\n- 下の【過去の正解事例】には、この会社で過去に人が確認した似た契約の判定事例が入っていることがある(空のこともある)\n- 事例の「正解」「決め手」は、相手勘定の選定で一般則より優先して参考にする(ただし今回の契約内容が事例と明らかに違う場合は引きずられない)\n- ユーザーの返信に「参考事例:」以下の文章が付いている場合、それは自動学習ページが添えた過去の判定事例(参考資料)であり、読み取り内容への訂正ではない\n\n【過去の正解事例】\n{{#context#}}\n{{#code_pagecases.cases#}}\n\n'

LEARN_CASE_SYSTEM = '''あなたは日本の会計実務に精通した経理・会計の専門家です。ユーザーがチャットで教えてくれた「正解」をもとに、次回から似た契約の判定に使う【判定事例】カードを1枚作ってください。出力はすべて日本語で行ってください。

# 材料
- これまでの会話に、判定した契約の読み取り内容・仕訳の流れ分析・アプリの判定結果が入っている
- ユーザーの最後の入力が正解(例: 「正解: 支払手数料」「正解: 費用/経費/支払手数料 [5030002001]」)
- アプリの判定が正解と同じだった場合も、事例として保存する価値はある(正しい判定の再現に効く)

# ルール
- 事実はこれまでの会話(読み取り内容・ユーザーの訂正)から取る。推測で補完しない
- 金額は書かない。社名などの固有名詞は書かず、立場(貸主/借主 など)で書く
- 「決め手」は、似た契約が来たときにこの科目を選べる見分け方として書く

# 出力形式(前置き・後書き・コードブロック記号は書かない。この形式だけを出力する)
【判定事例】
契約の種類: (契約・決裁の種類を具体的に)
当社の立場: (支払う側/受け取る側 など)
主な条件: (期間・支払条件・解約条件など判定を左右した条件。金額は書かない)
間違えやすい判定: (アプリが誤答した場合はその科目と誤答理由を短く。正解していた場合は「-」)
正解: (ユーザーが教えた勘定科目。コードが分かれば [コード] も)
決め手: (この契約をその科目と判定する見分け方を1〜2行)'''

LEARN_CASE_USER = '''以下は確認済みの読み取り内容と、ユーザーが教えてくれた正解です。これまでの会話の判定結果・訂正も材料にして、【判定事例】カードを1枚作ってください。

<読み取り内容(確認済み)>
{{#conversation.contract_summary#}}
</読み取り内容>

<ユーザーが教えた正解>
{{#sys.query#}}
</ユーザーが教えた正解>'''

LEARN_SAVE_BODY_CODE = '''def main(card: str, query: str) -> dict:
    # 事例カードを、ナレッジ登録API(create-by-text)のリクエストボディ(JSON)にする。
    import json
    import unicodedata

    def nk(s):
        return unicodedata.normalize('NFKC', (s or '')).strip()

    name = ''
    for line in (card or '').split('\\n'):
        line = nk(line)
        if line.startswith('契約の種類:'):
            name = line.split(':', 1)[1].strip()
            break
    if not name:
        name = nk(query)[:40] or '判定事例'
    return {'body': json.dumps({
        'name': ('判定事例: ' + name)[:100],
        'text': card,
        'indexing_technique': 'high_quality',
        'process_rule': {'mode': 'automatic'},
    }, ensure_ascii=False)}
'''

LEARN_ANSWER_SAVED = ('✅ 正解を事例ナレッジに保存しました(HTTP {{#http_save_case.status_code#}})。'
                      '次回から、似た契約の判定前に自動で検索して参考にします。\n\n{{#llm_case.text#}}\n\n---\n'
                      '(HTTPが200番台以外の場合は保存できていません。環境変数 dify_base_url / dataset_api_key / '
                      'case_dataset_id を確認してください。)')

LEARN_ANSWER_NOSAVE = '📋 正解を受け取り、判定事例カードを作りました。保存先(環境変数 dify_base_url / dataset_api_key / case_dataset_id)が未設定のため、事例ナレッジには保存していません。\n\n{{#llm_case.text#}}\n\n---\nこのカードは、事例ナレッジに「テキストを追加」で貼るか、⑤の自動学習(ナレッジAPIキーなし)が仮ナレッジとして記録します。環境変数を設定すると、次回から自動で保存されます。'

# ⑤が「OK」の返信に添える参考事例(ブラウザ側の仮ナレッジ)を取り出すコードノード
LEARN_PAGECASES_CODE = "def main(query: str) -> dict:\n    # ⑤の自動学習ページが「OK」の返信に添える参考事例(ブラウザ側の仮ナレッジ)を取り出す。無ければ空。\n    q = query or ''\n    mark = '参考事例:'\n    i = q.find(mark)\n    return {'cases': q[i + len(mark):].strip() if i >= 0 else ''}\n"


# ---- 事例の置き場「環境変数」方式(既定): ナレッジもAPIキーも使わない。
# 「正解:」の返信にはカードを返すだけ。⑤の自動学習がカードを集めて 判定事例.txt にまとめる。
# 社内展開では 判定事例.txt の中身をアプリの環境変数 learned_cases に貼る。判定前に code_cases が
# 読み取り内容に似た事例を4件まで選び(⑤と同じ2文字組の重なり)、判定プロンプトの【過去の正解事例】に渡す。
LEARN_CASES_ENV = {
    'description': '⑤の自動学習が出力した「判定事例.txt」の中身をそのまま貼る(空でも可)。判定前に、ここから読み取り内容に'
                   '似た事例を4件まで選んで参考にする。貼れる量の目安は日本語で5万〜10万字(Difyの MAX_VARIABLE_SIZE=既定200KB。'
                   '超えるなら古い決裁のブロックから削る)。',
    'id': 'env-learned-cases',
    'name': 'learned_cases',
    'value': '',
    'value_type': 'string',
}

LEARN_JOURNAL_SECTION_ENV = ('# 過去の正解事例(あれば最優先で参考にする)\n'
                             '- 下の【過去の正解事例】には、この会社で過去に人が確認した似た契約の判定事例が入っていることがある(空のこともある)\n'
                             '- 事例の「正解」「決め手」は、相手勘定の選定で一般則より優先して参考にする(ただし今回の契約内容が事例と明らかに違う場合は引きずられない)\n'
                             '- ユーザーの返信に「参考事例:」以下の文章が付いている場合、それは自動学習ページが添えた過去の判定事例(参考資料)であり、読み取り内容への訂正ではない\n'
                             '\n【過去の正解事例】\n{{#code_cases.cases#}}\n\n')

LEARN_CASES_CODE = """def main(query: str, summary: str, learned: str) -> dict:
    # 判定前に参考にする過去の判定事例を集める(ナレッジやAPIキーは使わない)。
    #  - ⑤の自動学習ページが「OK」の返信に添えた「参考事例:」以下(あれば)
    #  - 環境変数 learned_cases(⑤が出す 判定事例.txt の中身。「### 決裁名」見出しつきのブロック、または【判定事例】カードの列)
    # 読み取り内容(summary)と文字の重なり(2文字組)が大きい順に4件まで返す。
    import unicodedata

    def cards_of(text):
        t = (text or '').replace('\\r', '')
        out = []
        if '\\n### ' in ('\\n' + t):
            for seg in ('\\n' + t).split('\\n### ')[1:]:
                out.append((seg.split('\\n', 1)[1] if '\\n' in seg else '').strip())
        else:
            for seg in t.split('【判定事例】'):
                seg = seg.strip()
                if seg:
                    out.append('【判定事例】\\n' + seg)
        return [c for c in out if c]

    def grams(s):
        t = unicodedata.normalize('NFKC', s or '')
        t = ''.join(ch for ch in t if ch not in ' \\t\\n|[]【】()「」:、。・,./-*#')
        return set(t[i:i + 2] for i in range(len(t) - 1))

    def sim(a, b):
        return len(a & b) / ((len(a) * len(b)) ** 0.5) if a and b else 0.0

    q = query or ''
    i = q.find('参考事例:')
    page = cards_of(q[i + len('参考事例:'):]) if i >= 0 else []
    cands, seen = [], set()
    for c in page + cards_of(learned):
        key = ''.join(c.split())
        if key not in seen:
            seen.add(key)
            cands.append(c)
    g = grams(summary)
    scored = sorted(((sim(g, grams(c)), c) for c in cands), key=lambda x: -x[0])
    return {'cases': '\\n\\n'.join(c for s, c in scored[:4] if s > 0)}
"""

LEARN_ANSWER_CARD = ('📋 正解を受け取り、判定事例カードを作りました。\n\n{{#llm_case.text#}}\n\n---\n'
                     'このカードは⑤の自動学習が集めて 判定事例.txt にまとめます。社内で使うアプリには、その中身をアプリの環境変数 '
                     'learned_cases に貼ると、次回から似た契約の判定前に参考にします(ナレッジ・APIキー不要)。')


def learn_cfg_norm(cfg):
    """自己学習の設定を正規化する。mode: 'env'(既定。環境変数 learned_cases に事例を貼る。ナレッジ不要)
    または 'kb'(Difyの事例ナレッジ。検索ノード+自動保存。ナレッジIDやキーは生成時に書き込める)"""
    cfg = cfg or {}
    mode = (cfg.get('mode') or '').strip().lower()
    return {'mode': 'kb' if mode == 'kb' else 'env',
            'base_url': (cfg.get('base_url') or '').strip(),
            'dataset_key': (cfg.get('dataset_key') or '').strip(),
            'dataset_id': (cfg.get('dataset_id') or '').strip()}


def learn_envs(cfg):
    """環境変数方式なら learned_cases の1つ。ナレッジ方式なら LEARN_ENVS のコピーに生成時の値(あれば)を書き込んで返す"""
    if cfg['mode'] == 'env':
        return [dict(LEARN_CASES_ENV)]
    vals = {'dify_base_url': cfg['base_url'],
            'dataset_api_key': cfg['dataset_key'],
            'case_dataset_id': cfg['dataset_id']}
    out = []
    for e in LEARN_ENVS:
        e = dict(e)
        if vals.get(e['name']):
            e['value'] = vals[e['name']]
        out.append(e)
    return out


def learn_journal_patch(node, mode='env'):
    """llm_journal に過去の正解事例の参照を組み込む(環境変数方式は code_cases の出力、ナレッジ方式は検索結果 context)"""
    sys_p = node['data']['prompt_template'][0]
    anchor = '# 仕訳の流れの作り方'
    if mode == 'env':
        sys_p['text'] = sys_p['text'].replace(anchor, LEARN_JOURNAL_SECTION_ENV + anchor)
        return
    node['data']['context'] = {'enabled': True, 'variable_selector': ['kr_cases', 'result']}
    sys_p['text'] = sys_p['text'].replace(anchor, LEARN_JOURNAL_SECTION + anchor)


def learn_nodes(pos, cfg):
    """自己学習のノード一式。cfg['mode'] が 'env' なら環境変数方式(ナレッジ不要)、'kb' なら事例ナレッジ方式"""
    if cfg['mode'] == 'env':
        return learn_nodes_env(pos)
    return learn_nodes_kb(pos, cfg['dataset_id'])


def learn_ifelse_node(pos):
    return node_shell('if-else-learn', {
        'cases': [{
            'case_id': 'case-teach',
            'conditions': [{
                'comparison_operator': 'start with',
                'id': 'cond-teach',
                'value': '正解',
                'varType': 'string',
                'variable_selector': ['sys', 'query'],
            }],
            'id': 'case-teach',
            'logical_operator': 'and',
        }],
        'desc': '「正解: ◯◯」の返信なら事例の保存へ、それ以外は判定へ進みます。',
        'selected': False,
        'title': '条件分岐(正解の受け取り)',
        'type': 'if-else',
    }, place(pos, 'if-else-learn'), height=126)


def learn_llm_case_node(pos):
    return node_shell('llm_case', {
        'context': {'enabled': False, 'variable_selector': []},
        'desc': '教えてもらった正解と会話の内容から、次回の判定に使う【判定事例】カードを1枚作ります。',
        'memory': copy.deepcopy(MEMORY_BLOCK),
        'model': copy.deepcopy(MODEL),
        'prompt_template': [
            {'id': 'system-prompt-case', 'role': 'system', 'text': LEARN_CASE_SYSTEM},
            {'id': 'user-prompt-case', 'role': 'user', 'text': LEARN_CASE_USER},
        ],
        'selected': False,
        'title': '判定事例カード作成',
        'type': 'llm',
        'variables': [],
        'vision': {'enabled': False},
    }, place(pos, 'llm_case'), height=98)


def learn_nodes_env(pos):
    """環境変数方式: 参考事例の選択 → 判定 / 「正解:」→ カード作成 → カードを返信(保存しない)"""
    out = []
    out.append(node_shell('code_cases', {
        'code': LEARN_CASES_CODE,
        'code_language': 'python3',
        'desc': '判定前に参考にする過去の判定事例を選びます: 環境変数 learned_cases(⑤が出す 判定事例.txt を貼る)と、'
                '⑤が「OK」に添えた参考事例から、読み取り内容に似た順に4件まで。ナレッジやAPIキーは使いません。',
        'outputs': {'cases': {'children': None, 'type': 'string'}},
        'selected': False,
        'title': '参考事例の選択',
        'type': 'code',
        'variables': [{'value_selector': ['sys', 'query'], 'variable': 'query'},
                      {'value_selector': ['conversation', 'contract_summary'], 'variable': 'summary'},
                      {'value_selector': ['env', 'learned_cases'], 'variable': 'learned'}],
    }, place(pos, 'code_cases'), height=92))
    out.append(learn_ifelse_node(pos))
    out.append(learn_llm_case_node(pos))
    out.append(node_shell('answer-case', {
        'answer': LEARN_ANSWER_CARD,
        'desc': '作った判定事例カードを返信します(⑤が集めます。社内展開では 判定事例.txt を環境変数 learned_cases に貼ります)。',
        'selected': False,
        'title': '回答(判定事例カード)',
        'type': 'answer',
        'variables': [],
    }, place(pos, 'answer-case'), height=120))
    return out


def learn_nodes_kb(pos, dataset_id=''):
    """事例ナレッジ方式のノード一式。dataset_id を渡すと「類似事例の検索」に選択済みで入る"""
    out = []
    out.append(node_shell('kr_cases', {
        'dataset_ids': [dataset_id] if dataset_id else [],
        'desc': '事例ナレッジから、いま読んでいる契約に似た過去の判定事例を検索します。'
                + ('生成時に入力された事例ナレッジを設定済みです(変えるときはここで選び直してください)。'
                   if dataset_id else
                   'インポート後、このノードで事例ナレッジを1回選んでください(未選択でも判定は動きます)。'),
        'multiple_retrieval_config': {'reranking_enable': False, 'score_threshold': None, 'top_k': 4},
        'query_variable_selector': ['conversation', 'contract_summary'],
        'retrieval_mode': 'multiple',
        'selected': False,
        'title': '類似事例の検索',
        'type': 'knowledge-retrieval',
    }, place(pos, 'kr_cases'), height=92))
    out.append(node_shell('code_pagecases', {
        'code': LEARN_PAGECASES_CODE,
        'code_language': 'python3',
        'desc': '⑤の自動学習ページが「OK」の返信に添えた参考事例(ブラウザ側の仮ナレッジ)を取り出します。無ければ空です。',
        'outputs': {'cases': {'children': None, 'type': 'string'}},
        'selected': False,
        'title': '参考事例の取り出し',
        'type': 'code',
        'variables': [{'value_selector': ['sys', 'query'], 'variable': 'query'}],
    }, place(pos, 'code_pagecases'), height=92))
    out.append(learn_ifelse_node(pos))
    out.append(node_shell('learn_gate', {
        'desc': '事例ナレッジの保存先(環境変数3つ)が設定済みかを点検します。',
        'selected': False,
        'template': "{% if (u | trim) == '' or (k | trim) == '' or (d | trim) == '' %}off{% else %}on{% endif %}",
        'title': '保存先チェック',
        'type': 'template-transform',
        'variables': [{'value_selector': ['env', 'dify_base_url'], 'variable': 'u'},
                      {'value_selector': ['env', 'dataset_api_key'], 'variable': 'k'},
                      {'value_selector': ['env', 'case_dataset_id'], 'variable': 'd'}],
    }, place(pos, 'learn_gate'), height=82))
    out.append(node_shell('if-else-learn-set', {
        'cases': [{
            'case_id': 'case-set',
            'conditions': [{
                'comparison_operator': 'start with',
                'id': 'cond-set',
                'value': 'on',
                'varType': 'string',
                'variable_selector': ['learn_gate', 'output'],
            }],
            'id': 'case-set',
            'logical_operator': 'and',
        }],
        'desc': '保存先が設定済みならナレッジへ保存、未設定ならカードだけを返信します。',
        'selected': False,
        'title': '条件分岐(保存先の有無)',
        'type': 'if-else',
    }, place(pos, 'if-else-learn-set'), height=126))
    out.append(learn_llm_case_node(pos))
    out.append(node_shell('code_case_body', {
        'code': LEARN_SAVE_BODY_CODE,
        'code_language': 'python3',
        'desc': '事例カードを、ナレッジ登録API(create-by-text)のリクエストにします。',
        'outputs': {'body': {'children': None, 'type': 'string'}},
        'selected': False,
        'title': '保存リクエスト作成',
        'type': 'code',
        'variables': [{'value_selector': ['llm_case', 'text'], 'variable': 'card'},
                      {'value_selector': ['sys', 'query'], 'variable': 'query'}],
    }, place(pos, 'code_case_body'), height=92))
    out.append(node_shell('http_save_case', {
        'authorization': {'config': None, 'type': 'no-auth'},
        'body': {'data': [{'id': 'key-value-body-case', 'key': '', 'type': 'text',
                           'value': '{{#code_case_body.body#}}'}], 'type': 'json'},
        'desc': '事例カードをDifyの事例ナレッジに登録します(document/create-by-text)。',
        'headers': 'Content-Type: application/json\nAuthorization: Bearer {{#env.dataset_api_key#}}',
        'method': 'post',
        'params': '',
        'retry_config': {'max_retries': 1, 'retry_enabled': True, 'retry_interval': 2000},
        'selected': False,
        'timeout': {'max_connect_timeout': 30, 'max_read_timeout': 120, 'max_write_timeout': 30},
        'title': 'ナレッジへ保存',
        'type': 'http-request',
        'url': '{{#env.dify_base_url#}}/datasets/{{#env.case_dataset_id#}}/document/create-by-text',
        'variables': [],
    }, place(pos, 'http_save_case'), height=92))
    out.append(node_shell('answer-learned', {
        'answer': LEARN_ANSWER_SAVED,
        'desc': '保存した事例カードと保存結果を返信します。',
        'selected': False,
        'title': '回答(事例を保存)',
        'type': 'answer',
        'variables': [],
    }, place(pos, 'answer-learned'), height=120))
    out.append(node_shell('answer-nolearn', {
        'answer': LEARN_ANSWER_NOSAVE,
        'desc': '保存先(環境変数)が未設定のときは、作ったカードの文面をそのまま返信します。',
        'selected': False,
        'title': '回答(保存先未設定・カードのみ)',
        'type': 'answer',
        'variables': [],
    }, place(pos, 'answer-nolearn'), height=120))
    return out


def compute_layout_flat():
    pos = compute_layout_front()
    pos['llm_code7'] = (colx(9), SCAF_Y)
    pos['llm_code10'] = (colx(10), SCAF_Y)
    pos['code_final'] = (colx(11), SCAF_Y)
    pos['answer-final'] = (colx(12), SCAF_Y)
    return pos


def compute_layout_pick():
    pos = compute_layout_front()
    pos['llm_pick'] = (colx(9), SCAF_Y)
    pos['code_pick'] = (colx(10), SCAF_Y)
    pos['answer-final'] = (colx(11), SCAF_Y)
    return pos


def compute_layout_tree(root, stages, gagg_ids):
    """ツリー判定形式のレイアウト。共通の入り口+段階判定のバンド"""
    pos = compute_layout_front()
    max_depth = max(stage_depth(st) for st in stages.values())
    ga_col = max(12, 10 + 2 * max_depth)

    pos[stages[node_key(root)].id] = (colx(9), SCAF_Y)
    if stages[node_key(root)].ifelse_id:
        pos[stages[node_key(root)].ifelse_id] = (colx(10), SCAF_Y)
    pos['aggregator'] = (colx(ga_col + 1), AGG_Y + 150)
    pos['template_path'] = (colx(ga_col + 2), AGG_Y + 150)
    pos['template_code'] = (colx(ga_col + 3), AGG_Y + 150)
    pos['if-else-q-tree'] = (colx(ga_col + 4), AGG_Y + 150)
    pos['answer-q-tree'] = (colx(ga_col + 5), AGG_Y + 40)
    pos['code_result'] = (colx(ga_col + 5), AGG_Y + 260)
    pos['answer-final'] = (colx(ga_col + 6), AGG_Y + 260)

    band_y = BANDS_Y0
    for cat in root.children:
        if not cat.is_branch:
            continue
        head = stages[node_key(cat)]
        sub_stages = [stages[node_key(c)] for c in cat.children if c.is_branch]
        rows = 1 + len(sub_stages)
        pos[head.id] = (colx(11), band_y)
        if head.ifelse_id:
            pos[head.ifelse_id] = (colx(12), band_y)
        for i, st in enumerate(sub_stages):
            y = band_y + ROW * (1 + i)
            pos[st.id] = (colx(9 + 2 * stage_depth(st)), y)
            if st.ifelse_id:
                pos[st.ifelse_id] = (colx(10 + 2 * stage_depth(st)), y)

            def deeper(node):
                for c in node.children:
                    if not c.is_branch:
                        continue
                    dst = stages[node_key(c)]
                    pos[dst.id] = (colx(9 + 2 * stage_depth(dst)), y)
                    if dst.ifelse_id:
                        pos[dst.ifelse_id] = (colx(10 + 2 * stage_depth(dst)), y)
                    deeper(c)
            deeper(st.node)
        gy = band_y + rows * ROW + 70
        pos[gagg_ids[node_key(cat)]] = (colx(ga_col), gy)
        band_y = gy + 116 + BAND_GAP
    return pos


NO_CODES_MSG = ('ツリーに [7桁] のコードが1つもありません。%sは、'
                'ツリーの [7桁][3桁] を選択肢にする形式なので、コード付きのツリーで生成してください。')


def generate_flat(tree_text, extras, learn=False, learn_cfg=None):
    """コード2段選択形式(advanced-chat)。入力・読み取り・仕訳の流れ分析(相手勘定の特定)は
    3形式共通。コードの確定は、7桁コードの候補を横並びで1つ選び、その7桁に紐付く10桁を
    名称と書き分けの定義(環境変数)で絞り込む2段選択。コードの確定は機械(コードノード)"""
    root = parse_tree(tree_text)
    c7 = codes7_lines(root)
    c10 = codes10_lines(root)
    if not c7:
        raise SystemExit(NO_CODES_MSG % 'コード2段選択形式')

    pos = compute_layout_flat()
    nodes = chat_front(extras, pos, learn, learn_cfg)
    nodes += [copy.deepcopy(n) for n in extras['flat']['scaffold_nodes']]
    nodes.append(judge_answer_final(
        extras, pos, '{{#code_final.text#}}' + ANSWER_TAIL, ANSWER_FINAL_DESC))
    for n in nodes:
        if n['id'] in pos:
            n['position'] = place(pos, n['id'])
            n['positionAbsolute'] = place(pos, n['id'])
    nodes_by_id = {n['id']: n for n in nodes}
    if len(nodes_by_id) != len(nodes):
        raise SystemExit('ノードIDが重複しています')

    edges = []

    def E(src, handle, tgt):
        edges.append(make_edge_chat(nodes_by_id, src, handle, tgt))
    chat_front_edges(E, learn, learn_cfg_norm(learn_cfg)['mode'])
    E('if-else-q', 'false', 'llm_code7')
    E('llm_code7', 'source', 'llm_code10')
    E('llm_code10', 'source', 'code_final')
    E('code_final', 'source', 'answer-final')

    app = copy.deepcopy(extras['app'])
    app['mode'] = 'advanced-chat'
    app['name'] = CHAT_APP_NAME + '(コード2段選択)'
    app['description'] = (
        CHAT_DESC_HEAD +
        'コードの確定は、7桁コードの候補(%d件)を横並びで1つ選び、その7桁に紐付く10桁(%d件)を'
        '名称と書き分けの定義(環境変数で編集可)で絞り込む2段選択方式。'
        'コードはLLMに書かせず、選ばれた経路・名称から対応表で機械的に確定する。'
        % (len(c7), sum(1 for l in c10 if l.startswith('  - '))) +
        (learn_desc_note(learn_cfg) if learn else '') + CHAT_DESC_TAIL)

    envs = [{
        'description': '7桁コードの候補一覧(横並び)。分類ツリーの[7桁]とフルコードの上7桁から自動生成。'
                       '1行=「- 経路 [7桁]: 定義」。修正はツリー側が正で、ここでの編集は再生成までの応急対応。',
        'id': 'env-codes7-list',
        'name': 'codes7_list',
        'value': '\n'.join(c7),
        'value_type': 'string',
    }, {
        'description': '7桁→10桁の対応表(書き分け)。「[7桁] 経路」の見出しの下に、配下の「- 名称 [3桁]: 定義」。'
                       'ツリーの[3桁]と定義(十桁定義)から自動生成。定義を書き足すと10桁絞り込みの判定に反映される。'
                       '修正はツリー側が正で、ここでの編集は再生成までの応急対応。',
        'id': 'env-codes10-list',
        'name': 'codes10_list',
        'value': '\n'.join(c10),
        'value_type': 'string',
    }, dict(COMPANY_ENV), dict(POLICY_ENV)]
    if learn:
        envs += learn_envs(learn_cfg_norm(learn_cfg))

    features = copy.deepcopy(extras['features'])
    features['opening_statement'] = chat_opening('7桁を選んでから10桁を絞り込む2段選択', learn, learn_cfg_norm(learn_cfg)['mode'])

    return {
        'app': app,
        'kind': 'app',
        'version': '0.3.0',
        'workflow': {
            'conversation_variables': copy.deepcopy(extras['chat']['conversation_variables']),
            'environment_variables': envs,
            'features': features,
            'graph': {'edges': edges, 'nodes': nodes, 'viewport': {'x': 0, 'y': 0, 'zoom': 0.7}},
        },
    }


def generate_pick(tree_text, extras, learn=False, learn_cfg=None):
    """コード一発選択形式(advanced-chat)。入力・読み取り・仕訳の流れ分析(相手勘定の特定)は
    3形式共通。コードの確定は、10桁(無い科目は7桁)のコード候補すべてを横並びで提示して
    1回で選ぶ。コードの確定は機械(コードノード)"""
    root = parse_tree(tree_text)
    cl = codes_pick_lines(root)
    if not cl:
        raise SystemExit(NO_CODES_MSG % 'コード一発選択形式')

    pos = compute_layout_pick()
    nodes = chat_front(extras, pos, learn, learn_cfg)
    nodes += [copy.deepcopy(n) for n in extras['pick']['scaffold_nodes']]
    nodes.append(judge_answer_final(
        extras, pos, '{{#code_pick.text#}}' + ANSWER_TAIL, ANSWER_FINAL_DESC))
    for n in nodes:
        if n['id'] in pos:
            n['position'] = place(pos, n['id'])
            n['positionAbsolute'] = place(pos, n['id'])
    nodes_by_id = {n['id']: n for n in nodes}
    if len(nodes_by_id) != len(nodes):
        raise SystemExit('ノードIDが重複しています')

    edges = []

    def E(src, handle, tgt):
        edges.append(make_edge_chat(nodes_by_id, src, handle, tgt))
    chat_front_edges(E, learn, learn_cfg_norm(learn_cfg)['mode'])
    E('if-else-q', 'false', 'llm_pick')
    E('llm_pick', 'source', 'code_pick')
    E('code_pick', 'source', 'answer-final')

    app = copy.deepcopy(extras['app'])
    app['mode'] = 'advanced-chat'
    app['name'] = CHAT_APP_NAME + '(コード一発選択)'
    app['description'] = (
        CHAT_DESC_HEAD +
        'コードの確定は、10桁(無い科目は7桁)のコード候補(%d件)をすべて横並びで提示して1つ選ぶ一発選択方式。'
        'コードはLLMに書かせず、選ばれた経路から対応表で機械的に確定する。'
        % len(cl) +
        (learn_desc_note(learn_cfg) if learn else '') + CHAT_DESC_TAIL)

    envs = [{
        'description': '全コード候補の横並び一覧(一発選択用)。10桁がある科目は「- 経路/名称 [10桁]: 定義」、'
                       '10桁が無い7桁は「- 経路 [7桁]: 定義」。ツリーの[7桁][3桁]と定義から自動生成。'
                       '修正はツリー側が正で、ここでの編集は再生成までの応急対応。',
        'id': 'env-codes-list',
        'name': 'codes_list',
        'value': '\n'.join(cl),
        'value_type': 'string',
    }, dict(COMPANY_ENV), dict(POLICY_ENV)]
    if learn:
        envs += learn_envs(learn_cfg_norm(learn_cfg))

    features = copy.deepcopy(extras['features'])
    features['opening_statement'] = chat_opening('全コード候補からの一発選択', learn, learn_cfg_norm(learn_cfg)['mode'])

    return {
        'app': app,
        'kind': 'app',
        'version': '0.3.0',
        'workflow': {
            'conversation_variables': copy.deepcopy(extras['chat']['conversation_variables']),
            'environment_variables': envs,
            'features': features,
            'graph': {'edges': edges, 'nodes': nodes, 'viewport': {'x': 0, 'y': 0, 'zoom': 0.7}},
        },
    }


# ツリー判定形式の結果整形コードノード(コード2段選択・一発選択の code_final / code_pick に対応)
CODE_RESULT_CODE = '''def main(path: str, code: str, journal: str) -> dict:
    # ツリー判定の経路とコードを、前段の仕訳分析(相手勘定・根拠の仕訳)と合わせて結果表にまとめる。
    import unicodedata

    def nk(s):
        return unicodedata.normalize('NFKC', (s or '')).strip()

    def field(text, key):
        for line in (text or '').split('\\n'):
            line = nk(line)
            if line.startswith(key + ':'):
                return nk(line[len(key) + 1:])
        return ''

    path = nk(path)
    code = nk(code)
    final = '' if code in ('', 'コード未登録') else code

    # 結果表(相手勘定=判定経路の末端科目。仕訳分析の科目名と違う場合は併記)
    leaf = path.split('/')[-1] if path else ''
    subject = leaf or '-'
    j_account = field(journal, '相手勘定')
    if j_account and leaf and nk(j_account) != nk(leaf):
        subject = '%s(仕訳上の名称: %s)' % (leaf, j_account)

    out = ['## 🔢 判定結果(キャッシュの相手勘定)',
           '| 項目 | 内容 |',
           '|---|---|',
           '| 相手勘定(科目) | %s |' % subject,
           '| 確定コード | %s |' % (code or '未確定'),
           '| 判定経路 | %s |' % (path or '-'),
           '| 判定の理由 | %s |' % (field(journal, '理由') or '-'),
           '| 根拠の仕訳 | %s |' % (field(journal, '根拠の仕訳') or '-')]
    return {'text': '\\n'.join(out), 'code': final}
'''


def generate_tree(tree_text, extras, learn=False, learn_cfg=None):
    """ツリー判定形式(advanced-chat)。入力・読み取り・仕訳の流れ分析(相手勘定の特定)は
    3形式共通。コードの確定は、相手勘定を分類ツリーで1段ずつ下りて位置づける段階判定
    (従来フォーム版と同じ判定部)。判定経路から勘定科目コード(code_map の最長一致)を確定する"""
    root = parse_tree(tree_text)
    stages = build_stages(root, extras)

    used = {st.id for st in stages.values()} | {st.ifelse_id for st in stages.values() if st.ifelse_id}
    gagg_ids = {}
    for cat in root.children:
        if not cat.is_branch:
            continue
        suffix = stages[node_key(cat)].id.replace('llm-sub-', '').replace('llm-', '')
        gid = 'aggregator-' + suffix
        k = 2
        while gid in used:
            gid, k = 'aggregator-%s%d' % (suffix, k), k + 1
        used.add(gid)
        gagg_ids[node_key(cat)] = gid

    pos = compute_layout_tree(root, stages, gagg_ids)
    by_chat = {n['id']: n for n in extras['chat']['scaffold_nodes']}
    nodes = chat_front(extras, pos, learn, learn_cfg)

    stage_nodes = []

    def emit(node):
        stage = stages[node_key(node)]
        stage_nodes.append(llm_node(stage, pos, chat=True))
        if stage.ifelse_id:
            stage_nodes.append(ifelse_node(stage, stages, pos))
        for c in stage.branch_children():
            emit(c)
    emit(root)
    nodes += stage_nodes

    for cat in root.children:
        if not cat.is_branch:
            continue
        gid = gagg_ids[node_key(cat)]
        data = {
            'desc': '%s系の判定結果を1つに集約します(最も深い判定が優先)。' % cat.label,
            'output_type': 'string',
            'selected': False,
            'title': '変数集約(%s)' % cat.label,
            'type': 'variable-aggregator',
            'variables': [[st.id, 'text'] for st in postorder_sub(cat, stages)],
        }
        nodes.append(node_shell(gid, data, place(pos, gid)))

    agg = copy.deepcopy({n['id']: n for n in extras['scaffold_nodes']}['aggregator'])
    agg['data']['variables'] = ([[gagg_ids[node_key(c)], 'output'] for c in root.children if c.is_branch]
                                + [[stages[node_key(root)].id, 'text']])
    agg['position'] = place(pos, 'aggregator')
    agg['positionAbsolute'] = place(pos, 'aggregator')
    nodes.append(agg)

    path_order = sorted(stages.values(), key=lambda st: stage_depth(st))
    tp_parts = []
    for st in path_order:
        v = st.id.replace('-', '_')
        tp_parts.append("{%% if %s and %s[:2] != '質問' %%}%s{{ %s }}{%% endif %%}"
                        % (v, v, '' if st.is_root else '/', v))
    nodes.append(node_shell('template_path', {
        'desc': '判定で通ってきた経路を「流動資産/現金・預金/預金」のように「/」で連結します。',
        'selected': False,
        'template': ''.join(tp_parts),
        'title': '経路組み立て',
        'type': 'template-transform',
        'variables': [{'value_selector': [st.id, 'text'], 'variable': st.id.replace('-', '_')}
                      for st in path_order],
    }, place(pos, 'template_path')))

    code_tmpl = (
        "{% set ns = namespace(code='', p=path) %}"
        "{% for _ in range(12) %}{% if ns.code == '' and ns.p %}"
        "{% for line in map.split('\\n') %}"
        "{% if line and line.split(',')[0] == ns.p %}{% set ns.code = line.split(',')[1] %}{% endif %}"
        "{% endfor %}"
        "{% if ns.code == '' %}{% set ns.p = ns.p.rsplit('/', 1)[0] if '/' in ns.p else '' %}{% endif %}"
        "{% endif %}{% endfor %}"
        "{{ ns.code if ns.code else 'コード未登録' }}")
    nodes.append(node_shell('template_code', {
        'desc': '経路から勘定科目コード(共通7桁、下3桁まで確定していれば10桁)を対応表 code_map で決定的に確定します。未登録は「コード未登録」。',
        'selected': False,
        'template': code_tmpl,
        'title': 'コード確定',
        'type': 'template-transform',
        'variables': [{'value_selector': ['template_path', 'output'], 'variable': 'path'},
                      {'value_selector': ['env', 'code_map'], 'variable': 'map'}],
    }, place(pos, 'template_code')))

    # 段階判定そのものからの更問い(共通前段の更問いチェックとは別に、集約後にもう1回チェック)
    q = copy.deepcopy(by_chat['if-else-q'])
    q['id'] = 'if-else-q-tree'
    q['data']['cases'][0]['conditions'][0]['variable_selector'] = ['aggregator', 'output']
    q['data']['desc'] = '段階判定が更問い(質問)を返した場合はコード確定に進まず、質問をそのまま返信します。'
    q['data']['title'] = '条件分岐(更問いチェック:段階判定)'
    q['position'] = place(pos, 'if-else-q-tree')
    q['positionAbsolute'] = place(pos, 'if-else-q-tree')
    nodes.append(q)

    aq = copy.deepcopy(by_chat['answer-q'])
    aq['id'] = 'answer-q-tree'
    aq['data']['answer'] = '{{#aggregator.output#}}\n\n(回答をそのまま返信してください。判定を続けます。)'
    aq['data']['desc'] = '段階判定に必要な情報が足りないときの質問を返信します。'
    aq['position'] = place(pos, 'answer-q-tree')
    aq['positionAbsolute'] = place(pos, 'answer-q-tree')
    nodes.append(aq)

    nodes.append(node_shell('code_result', {
        'code': CODE_RESULT_CODE,
        'code_language': 'python3',
        'desc': 'ツリー判定の経路とコードを、仕訳分析(相手勘定・根拠の仕訳)と合わせて結果表にまとめます(LLMはコードに触れません)。',
        'outputs': {'code': {'children': None, 'type': 'string'},
                    'text': {'children': None, 'type': 'string'}},
        'selected': False,
        'title': '判定結果整形',
        'type': 'code',
        'variables': [
            {'value_selector': ['template_path', 'output'], 'variable': 'path'},
            {'value_selector': ['template_code', 'output'], 'variable': 'code'},
            {'value_selector': ['llm_journal', 'text'], 'variable': 'journal'},
        ],
    }, place(pos, 'code_result'), height=92))

    nodes.append(judge_answer_final(
        extras, pos, '{{#code_result.text#}}' + ANSWER_TAIL, ANSWER_FINAL_DESC))

    nodes_by_id = {n['id']: n for n in nodes}
    if len(nodes_by_id) != len(nodes):
        raise SystemExit('ノードIDが重複しています')

    edges = []

    def E(src, handle, tgt):
        edges.append(make_edge_chat(nodes_by_id, src, handle, tgt))
    chat_front_edges(E, learn, learn_cfg_norm(learn_cfg)['mode'])
    E('if-else-q', 'false', stages[node_key(root)].id)

    def wire(node, sink):
        stage = stages[node_key(node)]
        if stage.ifelse_id:
            E(stage.id, 'source', stage.ifelse_id)
            for c in stage.branch_children():
                E(stage.ifelse_id, case_id_for(stages[node_key(c)]), stages[node_key(c)].id)
                wire(c, gagg_ids[node_key(c)] if node is root else sink)
            E(stage.ifelse_id, 'false', sink)
        else:
            E(stage.id, 'source', sink)
    wire(root, 'aggregator')
    for cat in root.children:
        if cat.is_branch:
            E(gagg_ids[node_key(cat)], 'source', 'aggregator')
    E('aggregator', 'source', 'template_path')
    E('template_path', 'source', 'template_code')
    E('template_code', 'source', 'if-else-q-tree')
    E('if-else-q-tree', 'case-question', 'answer-q-tree')
    E('if-else-q-tree', 'false', 'code_result')
    E('code_result', 'source', 'answer-final')

    order = postorder(root, stages)
    leaves = []

    def count_leaves(n):
        for c in n.children:
            (leaves.append(c.label) if c.leaf else count_leaves(c))
    count_leaves(root)
    app = copy.deepcopy(extras['app'])
    app['mode'] = 'advanced-chat'
    app['name'] = CHAT_APP_NAME + '(ツリー判定)'
    app['description'] = (
        CHAT_DESC_HEAD +
        'コードの確定は、相手勘定を分類ツリーで1段ずつ下りて位置づける段階判定方式'
        '(%dステージ・最終ラベル%d種類。細分の分類基準は環境変数 rules_*(%d個)で編集できる)。'
        'コードはLLMに書かせず、判定経路から対応表 code_map で機械的に確定する。'
        % (len(order), len(leaves), sum(1 for st in stages.values() if st.env)) +
        (learn_desc_note(learn_cfg) if learn else '') + CHAT_DESC_TAIL)

    envs = env_vars(root, stages, extras)
    envs.append({
        'description': '経路→勘定科目コードの対応表(ツリーの[7桁][3桁]から自動生成。1行=「経路,コード」。'
                       '修正はツリー側が正で、ここでの編集は再生成までの応急対応)。',
        'id': 'env-code-map',
        'name': 'code_map',
        'value': '\n'.join(code_map_lines(root)),
        'value_type': 'string',
    })
    envs.append(dict(COMPANY_ENV))
    envs.append(dict(POLICY_ENV))
    if learn:
        envs += learn_envs(learn_cfg_norm(learn_cfg))

    features = copy.deepcopy(extras['features'])
    features['opening_statement'] = chat_opening('分類ツリーを1段ずつ下りる段階判定', learn, learn_cfg_norm(learn_cfg)['mode'])

    return {
        'app': app,
        'kind': 'app',
        'version': '0.3.0',
        'workflow': {
            'conversation_variables': copy.deepcopy(extras['chat']['conversation_variables']),
            'environment_variables': envs,
            'features': features,
            'graph': {'edges': edges, 'nodes': nodes, 'viewport': {'x': 0, 'y': 0, 'zoom': 0.7}},
        },
    }


def env_vars(root, stages, extras):
    out = []

    def walk(node):
        stage = stages[node_key(node)]
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
        out.append(stages[node_key(n)])
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
        suffix = stages[node_key(cat)].id.replace('llm-sub-', '').replace('llm-', '')
        gid = 'aggregator-' + suffix
        k = 2
        while gid in used:
            gid, k = 'aggregator-%s%d' % (suffix, k), k + 1
        used.add(gid)
        gagg_ids[node_key(cat)] = gid

    pos = compute_layout(root, stages, gagg_ids)

    nodes = [copy.deepcopy(n) for n in extras['scaffold_nodes']]
    for n in nodes:
        if n['id'] in pos:
            n['position'] = place(pos, n['id'])
            n['positionAbsolute'] = place(pos, n['id'])
    order = postorder(root, stages)

    stage_nodes = []
    def emit(node):
        stage = stages[node_key(node)]
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
        gid = gagg_ids[node_key(cat)]
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
    nodes.append(node_shell('template_path', {
        'desc': '判定で通ってきた経路を「流動資産/現金・預金/預金」のように「/」で連結します。',
        'selected': False,
        'template': ''.join(tp_parts),
        'title': '経路組み立て',
        'type': 'template-transform',
        'variables': [{'value_selector': [st.id, 'text'], 'variable': st.id.replace('-', '_')}
                      for st in path_order],
    }, place(pos, 'template_path')))

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
    nodes.append(node_shell('template_code', {
        'desc': '経路から勘定科目コード(共通7桁、下3桁まで確定していれば10桁)を対応表 code_map で決定的に確定します。未登録は「コード未登録」。',
        'selected': False,
        'template': code_tmpl,
        'title': 'コード確定',
        'type': 'template-transform',
        'variables': [{'value_selector': ['template_path', 'output'], 'variable': 'path'},
                      {'value_selector': ['env', 'code_map'], 'variable': 'map'}],
    }, place(pos, 'template_code')))

    nodes_by_id = {n['id']: n for n in nodes}
    if len(nodes_by_id) != len(nodes):
        raise SystemExit('ノードIDが重複しています')

    # 全体集約: グループ別集約の結果(実行された1つだけが値を持つ)+ 区分判定
    agg = nodes_by_id['aggregator']
    agg['data']['variables'] = ([[gagg_ids[node_key(c)], 'output'] for c in root.children if c.is_branch]
                                + [[stages[node_key(root)].id, 'text']])

    # 終了ノード: main_account は経路(スラッシュ連結)、account_code は勘定科目コード
    end_node = nodes_by_id['end']
    for o in end_node['data']['outputs']:
        if o['variable'] == 'main_account':
            o['value_selector'] = ['template_path', 'output']
    if not any(o['variable'] == 'account_code' for o in end_node['data']['outputs']):
        end_node['data']['outputs'].append({'value_selector': ['template_code', 'output'],
                                            'variable': 'account_code'})
    end_node['data']['desc'] = '契約内容サマリー(認識確認用)、仕訳または更問い、判定経路(/区切り)、勘定科目コードを出力します。'

    # エッジ
    edges = []
    def E(src, handle, tgt):
        edges.append(make_edge(nodes_by_id, src, handle, tgt))
    E('start', 'source', 'doc-extractor')
    E('doc-extractor', 'source', 'template-join')
    E('template-join', 'source', 'if-else-read')
    E('if-else-read', 'case-no-extract', 'llm_read')
    E('llm_read', 'source', 'aggregator_text')
    E('if-else-read', 'false', 'aggregator_text')
    E('aggregator_text', 'source', 'if-else-text')
    E('if-else-text', 'case-no-text', 'template-scan')
    E('template-scan', 'source', 'aggregator-out')
    E('if-else-text', 'false', 'llm_summary')
    E('llm_summary', 'source', 'if-else-confirm')
    E('if-else-confirm', 'case-unconfirmed', 'template-confirm')
    E('if-else-confirm', 'false', stages[node_key(root)].id)
    E('template-confirm', 'source', 'aggregator-out')
    def wire(node, sink):
        stage = stages[node_key(node)]
        if stage.ifelse_id:
            E(stage.id, 'source', stage.ifelse_id)
            for c in stage.branch_children():
                E(stage.ifelse_id, case_id_for(stages[node_key(c)]), stages[node_key(c)].id)
                # 区分の直下に入るときはグループ別集約に切り替える
                wire(c, gagg_ids[node_key(c)] if node is root else sink)
            E(stage.ifelse_id, 'false', sink)
        else:
            E(stage.id, 'source', sink)
    wire(root, 'aggregator')
    for cat in root.children:
        if cat.is_branch:
            E(gagg_ids[node_key(cat)], 'source', 'aggregator')
    E('aggregator', 'source', 'template_path')
    E('template_path', 'source', 'template_code')
    E('template_code', 'source', 'if-else-q')
    E('if-else-q', 'case-question', 'aggregator-out')
    E('if-else-q', 'false', 'llm_journal')
    E('llm_journal', 'source', 'aggregator-out')
    E('aggregator-out', 'source', 'end')

    # app 説明文
    leaves = []
    def count_leaves(n):
        for c in n.children:
            (leaves.append(c.label) if c.leaf else count_leaves(c))
    count_leaves(root)
    app = copy.deepcopy(extras['app'])
    app['description'] = (
        '契約書ファイル(PDF・画像・テキスト)を読み込み、契約の主たる勘定科目を段階的に判定して、'
        '金額なしの仕訳(借方/貸方)と確信度・誤分類時の影響度を出力するワークフロー。'
        '文字を取り出せないスキャンPDFや画像はAIが直接読み取る。初回実行は契約内容の認識確認で停止し、'
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


def compute_layout_front():
    """3形式共通の入り口(読み取り〜認識確認〜仕訳の流れ分析〜更問いチェック)のレイアウト"""
    pos = {}
    pos['start'] = (colx(0), SCAF_Y)
    pos['doc-extractor'] = (colx(1), SCAF_Y)
    pos['template-plain'] = (colx(2), SCAF_Y)
    pos['if-else-read'] = (colx(3), SCAF_Y)
    pos['llm_read'] = (colx(4), TOP_Y)
    pos['template-join-read'] = (colx(5), TOP_Y)
    pos['save-text-read'] = (colx(6), TOP_Y)
    pos['template-join'] = (colx(4), SCAF_Y)
    pos['save-text'] = (colx(5), SCAF_Y)
    pos['if-else-att'] = (colx(6), SCAF_Y)
    pos['llm_summary'] = (colx(7), TOP_Y)
    pos['save-summary'] = (colx(8), TOP_Y)
    pos['env_check'] = (colx(9), TOP_Y)
    pos['answer-confirm'] = (colx(10), TOP_Y)
    pos['llm_journal'] = (colx(7), SCAF_Y)
    pos['if-else-q'] = (colx(8), SCAF_Y)
    pos['answer-q'] = (colx(11), TOP_Y)
    # 自己学習(learn=True のときだけ使われる。上部の専用レーンでどの形式とも重ならない)
    pos['if-else-learn'] = (colx(7), LEARN_Y)
    pos['code_pagecases'] = (colx(8), LEARN_Y)
    pos['kr_cases'] = (colx(9), LEARN_Y)
    pos['learn_gate'] = (colx(10), LEARN_Y)
    pos['llm_case'] = (colx(11), LEARN_Y)
    pos['if-else-learn-set'] = (colx(12), LEARN_Y)
    pos['code_case_body'] = (colx(13), LEARN_Y)
    pos['http_save_case'] = (colx(14), LEARN_Y)
    pos['answer-learned'] = (colx(15), LEARN_Y)
    pos['answer-nolearn'] = (colx(13), LEARN_Y - 150)
    return pos


def make_edge_chat(nodes_by_id, src, handle, tgt):
    """チャット版のエッジ(参考チャットフローと同じ isInLoop 形式)"""
    return {
        'data': {'isInLoop': False,
                 'sourceType': nodes_by_id[src]['data']['type'],
                 'targetType': nodes_by_id[tgt]['data']['type']},
        'id': '%s-%s-%s-target' % (src, handle, tgt),
        'source': src, 'sourceHandle': handle,
        'target': tgt, 'targetHandle': 'target',
        'type': 'custom', 'zIndex': 0,
    }


def set_llm_model(dsl, provider=None, name=None):
    """生成済みDSLの全LLMノードのモデルを差し替える。

    Difyはモデルをノード単位で保存するため、インポート先に無いプロバイダー/モデル名の
    DSLを取り込むと、キャンバス上でノードを1つずつ選び直すことになる。
    生成時に実際に使うモデルを書き込んでおけば、インポートしてそのまま動く。
    provider はDifyの内部名(例: openai / azure_openai / langgenius/openai/openai)。
    確実なのは、そのモデルで動いている既存アプリをDSLエクスポートして
    model: の provider / name を写すこと。"""
    n = 0
    for node in dsl['workflow']['graph']['nodes']:
        model = node.get('data', {}).get('model')
        if node.get('data', {}).get('type') == 'llm' and isinstance(model, dict):
            if provider:
                model['provider'] = provider
            if name:
                model['name'] = name
            n += 1
    return n



# --- ひな形(開始・サマリー・仕訳生成などの共通ノード)---
EXTRAS_JSON = "{\"app\":{\"description\":\"\",\"icon\":\"📑\",\"icon_background\":\"#FFEAD5\",\"mode\":\"workflow\",\"name\":\"契約書 勘定科目区分分類\",\"use_icon_as_answer_icon\":false},\"features\":{\"file_upload\":{\"allowed_file_extensions\":[\".PDF\",\".TXT\",\".MD\",\".MARKDOWN\",\".DOCX\",\".XLSX\",\".XLS\",\".PPTX\",\".PPT\",\".CSV\",\".PNG\",\".JPG\",\".JPEG\",\".WEBP\",\".GIF\"],\"allowed_file_types\":[\"document\",\"image\"],\"allowed_file_upload_methods\":[\"local_file\",\"remote_url\"],\"enabled\":true,\"image\":{\"detail\":\"high\",\"enabled\":true,\"number_limits\":10,\"transfer_methods\":[\"local_file\",\"remote_url\"]},\"number_limits\":10},\"opening_statement\":\"\",\"retriever_resource\":{\"enabled\":true},\"sensitive_word_avoidance\":{\"enabled\":false},\"speech_to_text\":{\"enabled\":false},\"suggested_questions\":[],\"suggested_questions_after_answer\":{\"enabled\":false},\"text_to_speech\":{\"enabled\":false,\"language\":\"\",\"voice\":\"\"}},\"conversation_variables\":[],\"scaffold_nodes\":[{\"data\":{\"desc\":\"契約書ファイルをアップロードします(PDF・Word・テキスト・スキャン画像。複数可)。\",\"selected\":false,\"title\":\"開始\",\"type\":\"start\",\"variables\":[{\"allowed_file_extensions\":[],\"allowed_file_types\":[\"document\",\"image\"],\"allowed_file_upload_methods\":[\"local_file\",\"remote_url\"],\"label\":\"契約書ファイル(PDF・画像・テキスト)\",\"max_length\":10,\"options\":[],\"required\":true,\"type\":\"file-list\",\"variable\":\"contract_file\"},{\"label\":\"補足情報(更問いへの回答)\",\"max_length\":2000,\"options\":[],\"required\":false,\"type\":\"paragraph\",\"variable\":\"additional_info\"}]},\"height\":116,\"id\":\"start\",\"position\":{\"x\":80,\"y\":690},\"positionAbsolute\":{\"x\":80,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約書ファイル(文書)からテキストを抽出します。画像はここでは対象外で、後段の「契約書ファイルの読み取り」がAIで直接読みます。\",\"is_array_file\":true,\"selected\":false,\"title\":\"契約書テキスト抽出\",\"type\":\"document-extractor\",\"variable_selector\":[\"start\",\"contract_file\"]},\"height\":116,\"id\":\"doc-extractor\",\"position\":{\"x\":384,\"y\":690},\"positionAbsolute\":{\"x\":384,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"複数ファイルから抽出したテキストを、1つの本文にまとめます。\",\"selected\":false,\"template\":\"{{ texts | join('\\\\n\\\\n') | trim }}\",\"title\":\"抽出テキスト結合\",\"type\":\"template-transform\",\"variables\":[{\"value_selector\":[\"doc-extractor\",\"text\"],\"variable\":\"texts\"}]},\"height\":116,\"id\":\"template-join\",\"position\":{\"x\":384,\"y\":990},\"positionAbsolute\":{\"x\":384,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-no-extract\",\"conditions\":[{\"comparison_operator\":\"empty\",\"id\":\"cond-no-extract\",\"value\":\"\",\"varType\":\"string\",\"variable_selector\":[\"template-join\",\"output\"]}],\"id\":\"case-no-extract\",\"logical_operator\":\"and\"}],\"desc\":\"テキスト抽出で文字が取れなかった場合(スキャンPDF・画像など)は、AIがファイルを直接読む経路へ回します。\",\"selected\":false,\"title\":\"条件分岐(抽出チェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-read\",\"position\":{\"x\":500,\"y\":990},\"positionAbsolute\":{\"x\":500,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"契約書ファイル(スキャンPDF・画像)をAIが直接読んで、本文を忠実に文字起こしします。テキスト抽出で文字が取れなかったときだけ実行されます。\",\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-read\",\"role\":\"system\",\"text\":\"あなたは書類の文字起こしの専門家です。添付された契約書ファイル(PDF・画像)を、書かれているとおり忠実に全文文字起こししてください。\\n\\n【ルール】\\n- 要約・省略・言い換え・追記はしない。書かれている文字をそのまま書き起こす\\n- ファイルやページが複数ある場合は、順番どおりに続けて出力する\\n- 表は「|」区切りのテキスト表として書き起こす\\n- 判読できない文字は 〓 と書く(推測で補わない)\\n- 印影・手書きの署名は「(押印)」「(署名)」と書く\\n- 前置き・後書き・説明は一切書かない(本文だけを出力する)\\n- 添付ファイルが1つも見えない・1文字も読み取れない場合は「〓読取不能〓」とだけ出力する\"},{\"id\":\"user-prompt-read\",\"role\":\"user\",\"text\":\"添付の契約書ファイルを全文文字起こししてください。\"}],\"selected\":false,\"title\":\"契約書ファイルの読み取り\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"start\",\"contract_file\"]},\"enabled\":true}},\"height\":116,\"id\":\"llm_read\",\"position\":{\"x\":688,\"y\":990},\"positionAbsolute\":{\"x\":688,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"AI直接読み取りの結果(実行された場合)と、テキスト抽出の結果を1つの本文にまとめます。\",\"output_type\":\"string\",\"selected\":false,\"title\":\"本文集約\",\"type\":\"variable-aggregator\",\"variables\":[[\"llm_read\",\"text\"],[\"template-join\",\"output\"]]},\"height\":116,\"id\":\"aggregator_text\",\"position\":{\"x\":992,\"y\":990},\"positionAbsolute\":{\"x\":992,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-no-text\",\"conditions\":[{\"comparison_operator\":\"empty\",\"id\":\"cond-no-text\",\"value\":\"\",\"varType\":\"string\",\"variable_selector\":[\"aggregator_text\",\"output\"]},{\"comparison_operator\":\"contains\",\"id\":\"cond-unreadable\",\"value\":\"〓読取不能〓\",\"varType\":\"string\",\"variable_selector\":[\"aggregator_text\",\"output\"]}],\"id\":\"case-no-text\",\"logical_operator\":\"or\"}],\"desc\":\"本文の文字が1文字も取れなかった場合(AIでも読み取れなかった場合)は、判定に進まず案内を返します。\",\"selected\":false,\"title\":\"条件分岐(本文チェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-text\",\"position\":{\"x\":1100,\"y\":990},\"positionAbsolute\":{\"x\":1100,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"文字が取れず、AIでも読み取れなかった場合の案内メッセージを出力します。\",\"selected\":false,\"template\":\"質問: 契約書ファイルから文字を読み取れませんでした。スキャン(画像)のPDFで、選択中のAIモデルがPDFの直接読み取りに対応していない可能性があります。①各ページを画像(スクリーンショットや写真)にして「契約書ファイル」欄に追加して再実行する、②PDFを直接読めるAIモデル(Claude系など)に切り替える、のどちらかをお試しください。\\n回答例: (画像を追加して再実行)\",\"title\":\"スキャン案内\",\"type\":\"template-transform\",\"variables\":[]},\"height\":116,\"id\":\"template-scan\",\"position\":{\"x\":1100,\"y\":1200},\"positionAbsolute\":{\"x\":1100,\"y\":1200},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"契約書の読み取り内容(契約名・当事者・主目的・主要条件)を認識確認用に出力します。添付ファイルも直接参照し、補足情報の訂正を反映します。\",\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-summary\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n与えられた契約書の本文から、勘定科目分類の前提となる要点を読み取り、次の形式で出力してください。\\nこの出力は「契約書の読み取りに認識間違いがないか」をユーザーが確認するために提示されます。\\n\\n【出力形式】(この形式のみを出力する。前置き・後書きは付けない)\\n契約名: <契約書の題名>\\n当事者: <当事者名と、読み取れる場合は自社の立場(貸主/借主、受託者/委託者、買主/売主 など)。読み取れない場合は「不明」と書く>\\n契約の主目的: <1行で>\\n主要条件: <期間・金額・支払条件など分類に影響する重要な条件を2〜3点、「 / 」区切りで>\\n特記事項: <分類に影響しそうな点があれば1行、なければ「なし」>\\n※ この認識に誤りがある場合は、「補足情報」欄で訂正して再実行してください。\\n\\n【ルール】\\n- 契約書に書かれていることだけを書き、推測で断定しない。読み取れない項目は「不明」とする。\\n- <補足情報>に訂正や回答が入っている場合は、その内容を事実として反映し、該当箇所に「(補足情報より)」と付記する。\\n- 最終行の「※ …」の注意書きは毎回そのまま出力する。\"},{\"id\":\"user-prompt-summary\",\"role\":\"user\",\"text\":\"以下はアップロードされた契約書から抽出した本文です。契約書が画像やスキャンPDFで添付されている場合は本文が空・不完全なことがあるため、その場合は添付ファイルを直接読み取ってください。読み取り内容の要点を出力してください。\\n\\n<契約書本文>\\n{{#aggregator_text.output#}}\\n</契約書本文>\\n\\n<補足情報>\\n{{#start.additional_info#}}\\n</補足情報>\\n(補足情報は、過去の質問への回答や認識の訂正です。空の場合もあります。)\"}],\"selected\":false,\"title\":\"契約内容サマリー\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"start\",\"contract_file\"]},\"enabled\":true}},\"height\":116,\"id\":\"llm_summary\",\"position\":{\"x\":688,\"y\":690},\"positionAbsolute\":{\"x\":688,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-unconfirmed\",\"conditions\":[{\"comparison_operator\":\"empty\",\"id\":\"cond-unconfirmed\",\"value\":\"\",\"varType\":\"string\",\"variable_selector\":[\"start\",\"additional_info\"]}],\"id\":\"case-unconfirmed\",\"logical_operator\":\"and\"}],\"desc\":\"補足情報が空(=認識結果が未確認)の場合は分類に進まず、確認要求を出力します。\",\"selected\":false,\"title\":\"条件分岐(認識確認)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-confirm\",\"position\":{\"x\":1296,\"y\":690},\"positionAbsolute\":{\"x\":1296,\"y\":690},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"認識結果の確認を求めるメッセージを出力します(初回実行時)。\",\"selected\":false,\"template\":\"質問: 契約内容の認識結果(contract_summary)は合っていますか?内容を確認して、補足情報欄に回答を入力し、再実行してください。\\n回答例: 正しいです / 当社は借主です(誤りがある場合は、このように訂正内容を記入)\",\"title\":\"確認要求\",\"type\":\"template-transform\",\"variables\":[]},\"height\":116,\"id\":\"template-confirm\",\"position\":{\"x\":1296,\"y\":990},\"positionAbsolute\":{\"x\":1296,\"y\":990},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"実行された分岐の判定結果を1つに集約します。\",\"output_type\":\"string\",\"selected\":false,\"title\":\"変数集約\",\"type\":\"variable-aggregator\",\"variables\":[]},\"height\":150,\"id\":\"aggregator\",\"position\":{\"x\":3424,\"y\":860},\"positionAbsolute\":{\"x\":3424,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-question\",\"conditions\":[{\"comparison_operator\":\"start with\",\"id\":\"cond-question\",\"value\":\"質問\",\"varType\":\"string\",\"variable_selector\":[\"aggregator\",\"output\"]}],\"id\":\"case-question\",\"logical_operator\":\"and\"}],\"desc\":\"更問い(質問)の場合は仕訳を作らず、質問をそのまま出力へ流します。\",\"selected\":false,\"title\":\"条件分岐(更問いチェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-q\",\"position\":{\"x\":3728,\"y\":860},\"positionAbsolute\":{\"x\":3728,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"判定済みの主科目から、金額なしの仕訳(借方/貸方)と確信度・誤分類時の影響度を生成します。\",\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-journal\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n前段までの判定で、この契約書の主たる勘定科目(主科目)は「{{#aggregator.output#}}」と判定されています。\\n契約書の本文を読み、この契約の典型的な取引について仕訳を1本、金額なしで出力してください。\\n\\n【仕訳の作り方】\\n- 主科目を、会計原則に従って借方・貸方の正しい側に置く(資産の増加・費用の発生=借方、負債・純資産・収益の発生=貸方)。\\n- 相手科目は契約内容から最も典型的なものを1つ選ぶ。可能な限り本ワークフローの分類ラベル(預金、売掛金、未払金、営業収入 など)を使い、該当がなければ一般的な勘定科目名でよい。\\n- 継続的な契約(毎月の賃料・給与など)は、発生時点の典型仕訳を1本とする。\\n- この段階では質問(更問い)はしない。不明点は典型形を仮定したうえで、確信度を下げて表現する。\\n\\n【確信度の基準】\\n- 高: 契約書(と補足情報)に明確な根拠がある\\n- 中: 一部を推定で補っている\\n- 低: 情報が乏しく、典型形を仮定した\\n\\n【誤分類時の影響(リスク)の基準】\\n- 高: 貸借対照表と損益計算書をまたぐ誤り(資産計上か費用計上か等)や、税務(交際費の損金算入・少額判定、資産計上の要否等)に影響しうる\\n- 中: 流動・固定の区分や表示区分に影響する\\n- 低: 同一区分内の細分の違いにとどまり、損益や税額への影響がない\\n\\n【出力形式】(この5行のみを出力する。金額・前置き・後書きは付けない)\\n借方: <科目名>\\n貸方: <科目名>\\n確信度: 借方=高|中|低 / 貸方=高|中|低\\n確信度の補足: <根拠と推定箇所を1行で>\\n誤分類時の影響: 高|中|低 — <理由を1行で>\\n\\n【出力例】\\n借方: 賃借料\\n貸方: 預金\\n確信度: 借方=高 / 貸方=中\\n確信度の補足: 賃料の定めは契約条項に明確。支払方法は振込と推定。\\n誤分類時の影響: 低 — 経費内の細分違いにとどまり、損益や税額への影響はない。\"},{\"id\":\"user-prompt-journal\",\"role\":\"user\",\"text\":\"以下はアップロードされた契約書から抽出した本文です。契約書が画像やスキャンPDFで添付されている場合は本文が空・不完全なことがあるため、その場合は添付ファイルを直接読み取ってください。判定済みの主科目「{{#aggregator.output#}}」を用いて、金額なしの仕訳と確信度・影響度を出力してください。\\n\\n<契約書本文>\\n{{#aggregator_text.output#}}\\n</契約書本文>\\n\\n<補足情報>\\n{{#start.additional_info#}}\\n</補足情報>\\n(補足情報は、過去の質問への回答です。空の場合もあります。)\"}],\"selected\":false,\"title\":\"仕訳生成\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"start\",\"contract_file\"]},\"enabled\":true}},\"height\":116,\"id\":\"llm_journal\",\"position\":{\"x\":4032,\"y\":760},\"positionAbsolute\":{\"x\":4032,\"y\":760},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"仕訳または更問い(質問)を1つに集約します。\",\"output_type\":\"string\",\"selected\":false,\"title\":\"出力集約\",\"type\":\"variable-aggregator\",\"variables\":[[\"llm_journal\",\"text\"],[\"template-confirm\",\"output\"],[\"template-scan\",\"output\"],[\"aggregator\",\"output\"]]},\"height\":116,\"id\":\"aggregator-out\",\"position\":{\"x\":4336,\"y\":860},\"positionAbsolute\":{\"x\":4336,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約内容サマリー(認識確認用)、仕訳または更問い、主科目ラベルを出力します。\",\"outputs\":[{\"value_selector\":[\"llm_summary\",\"text\"],\"variable\":\"contract_summary\"},{\"value_selector\":[\"aggregator-out\",\"output\"],\"variable\":\"classification_result\"},{\"value_selector\":[\"aggregator\",\"output\"],\"variable\":\"main_account\"}],\"selected\":false,\"title\":\"終了\",\"type\":\"end\"},\"height\":116,\"id\":\"end\",\"position\":{\"x\":4640,\"y\":860},\"positionAbsolute\":{\"x\":4640,\"y\":860},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244}],\"chat\":{\"conversation_variables\":[{\"description\":\"アップロードされた契約書から抽出した本文(会話をまたいで保持する)\",\"id\":\"c1d2e3f4-0001-4a00-9000-000000000001\",\"name\":\"contract_text\",\"selector\":[\"conversation\",\"contract_text\"],\"value\":\"\",\"value_type\":\"string\"},{\"description\":\"契約書から読み取りユーザーに提示した認識内容(確認・訂正の対象)\",\"id\":\"c1d2e3f4-0002-4a00-9000-000000000002\",\"name\":\"contract_summary\",\"selector\":[\"conversation\",\"contract_summary\"],\"value\":\"\",\"value_type\":\"string\"}],\"scaffold_nodes\":[{\"data\":{\"desc\":\"\",\"selected\":false,\"title\":\"開始\",\"type\":\"start\",\"variables\":[]},\"height\":54,\"id\":\"start\",\"position\":{\"x\":80,\"y\":190},\"positionAbsolute\":{\"x\":80,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"アップロードされた契約書ファイル(PDF/テキスト/Word)から本文テキストを抽出する。画像は抽出対象外(LLMが直接読む)。\",\"is_array_file\":true,\"selected\":false,\"title\":\"契約書テキスト抽出\",\"type\":\"document-extractor\",\"variable_selector\":[\"sys\",\"files\"]},\"height\":92,\"id\":\"doc-extractor\",\"position\":{\"x\":384,\"y\":190},\"positionAbsolute\":{\"x\":384,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"今回の添付から抽出できた文字だけを取り出します(読み取り要否の判定用)。\",\"selected\":false,\"template\":\"{{ texts | join('') | trim }}\",\"title\":\"抽出文字の確認\",\"type\":\"template-transform\",\"variables\":[{\"value_selector\":[\"doc-extractor\",\"text\"],\"variable\":\"texts\"}]},\"height\":92,\"id\":\"template-plain\",\"position\":{\"x\":688,\"y\":190},\"positionAbsolute\":{\"x\":688,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-need-read\",\"conditions\":[{\"comparison_operator\":\"not empty\",\"id\":\"cond-read-files\",\"value\":\"\",\"varType\":\"array[file]\",\"variable_selector\":[\"sys\",\"files\"]},{\"comparison_operator\":\"empty\",\"id\":\"cond-read-empty\",\"value\":\"\",\"varType\":\"string\",\"variable_selector\":[\"template-plain\",\"output\"]}],\"id\":\"case-need-read\",\"logical_operator\":\"and\"}],\"desc\":\"添付があるのに文字を取り出せなかった場合(スキャンPDF・画像)は、AIがファイルを直接読む経路へ回します。\",\"selected\":false,\"title\":\"条件分岐(抽出チェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-read\",\"position\":{\"x\":992,\"y\":190},\"positionAbsolute\":{\"x\":992,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"契約書ファイル(スキャンPDF・画像)をAIが直接読んで、本文を忠実に文字起こしします。文字を取り出せなかったときだけ実行されます。\",\"model\":{\"completion_params\":{\"max_tokens\":8192,\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-read\",\"role\":\"system\",\"text\":\"あなたは書類の文字起こしの専門家です。添付された契約書ファイル(PDF・画像)を、書かれているとおり忠実に全文文字起こししてください。\\n\\n【ルール】\\n- 要約・省略・言い換え・追記はしない。書かれている文字をそのまま書き起こす\\n- ファイルやページが複数ある場合は、順番どおりに続けて出力する\\n- 表は「|」区切りのテキスト表として書き起こす\\n- 判読できない文字は 〓 と書く(推測で補わない)\\n- 印影・手書きの署名は「(押印)」「(署名)」と書く\\n- 前置き・後書き・説明は一切書かない(本文だけを出力する)\\n- 添付ファイルが1つも見えない・1文字も読み取れない場合は「〓読取不能〓」とだけ出力する\"},{\"id\":\"user-prompt-read\",\"role\":\"user\",\"text\":\"添付の契約書ファイルを全文文字起こししてください。\"}],\"selected\":false,\"title\":\"契約書ファイルの読み取り\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_read\",\"position\":{\"x\":1296,\"y\":40},\"positionAbsolute\":{\"x\":1296,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"これまでの契約書本文に、AIが読み取った本文を追記する。\",\"selected\":false,\"template\":\"{{ contract }}\\n\\n【アップロード書類(AI読み取り)】\\n{{ read }}\",\"title\":\"契約書テキスト結合(AI読み取り)\",\"type\":\"template-transform\",\"variables\":[{\"value_selector\":[\"conversation\",\"contract_text\"],\"variable\":\"contract\"},{\"value_selector\":[\"llm_read\",\"text\"],\"variable\":\"read\"}]},\"height\":92,\"id\":\"template-join-read\",\"position\":{\"x\":1600,\"y\":40},\"positionAbsolute\":{\"x\":1600,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約書本文を会話変数に保存し、次のターン(質問への回答時)でも参照できるようにする。\",\"items\":[{\"input_type\":\"variable\",\"operation\":\"over-write\",\"value\":[\"template-join-read\",\"output\"],\"variable_selector\":[\"conversation\",\"contract_text\"]}],\"selected\":false,\"title\":\"契約書テキストを保存(AI読み取り)\",\"type\":\"assigner\",\"version\":\"2\"},\"height\":88,\"id\":\"save-text-read\",\"position\":{\"x\":1904,\"y\":40},\"positionAbsolute\":{\"x\":1904,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"これまでの契約書本文に、今回アップロードされた書類の本文を追記する。\",\"selected\":false,\"template\":\"{{ contract }}\\n{% for t in new_texts %}\\n\\n【アップロード書類{{ loop.index }}】\\n{{ t }}\\n{% endfor %}\",\"title\":\"契約書テキスト結合\",\"type\":\"template-transform\",\"variables\":[{\"value_selector\":[\"conversation\",\"contract_text\"],\"variable\":\"contract\"},{\"value_selector\":[\"doc-extractor\",\"text\"],\"variable\":\"new_texts\"}]},\"height\":92,\"id\":\"template-join\",\"position\":{\"x\":1296,\"y\":190},\"positionAbsolute\":{\"x\":1296,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"契約書本文を会話変数に保存し、次のターン(質問への回答時)でも参照できるようにする。\",\"items\":[{\"input_type\":\"variable\",\"operation\":\"over-write\",\"value\":[\"template-join\",\"output\"],\"variable_selector\":[\"conversation\",\"contract_text\"]}],\"selected\":false,\"title\":\"契約書テキストを保存\",\"type\":\"assigner\",\"version\":\"2\"},\"height\":88,\"id\":\"save-text\",\"position\":{\"x\":1600,\"y\":190},\"positionAbsolute\":{\"x\":1600,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"true\",\"conditions\":[{\"comparison_operator\":\"not empty\",\"id\":\"cond-files-exist\",\"value\":\"\",\"varType\":\"array[file]\",\"variable_selector\":[\"sys\",\"files\"]}],\"id\":\"true\",\"logical_operator\":\"and\"}],\"desc\":\"新しい書類が添付されたターンなら読み取り内容の確認へ、添付なし(確認への返事・質問への回答)なら分類へ。\",\"selected\":false,\"title\":\"添付ありで分岐\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-att\",\"position\":{\"x\":2208,\"y\":190},\"positionAbsolute\":{\"x\":2208,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"アップロードされた契約書から、勘定科目分類の前提となる要点を読み取る(この段階では分類しない)。画像・スキャンPDFは添付を直接読む。\",\"model\":{\"completion_params\":{\"max_tokens\":4096,\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-summary\",\"role\":\"system\",\"text\":\"あなたは日本の会計実務に精通した経理・会計の専門家です。アップロードされた決裁用の書類一式(契約書・申込書・注文書・覚書のドラフトのほか、見積書・仕様書・料金表などの添付資料を含むことがある)から、勘定科目の判定に必要な事実を漏れなく抽出してください。押印・署名前のドラフトや、社名・金額・日付が空欄のひな形のことも多い前提で読んでください。この段階では判定はまだ行いません。出力はすべて日本語で行ってください。\\n\\n# 抽出する項目\\n- 書類の種類と構成(何の書類が何通あるか。ドラフト・未押印・記入前のひな形かどうか)\\n- 契約の種類・タイトル\\n- 契約当事者(自社側・相手方の名称と、読み取れる場合は自社の立場(貸主/借主、受託者/委託者、買主/売主、保証人/被保証人 など))\\n- 契約締結日\\n- 契約期間(開始日・終了日・更新条件・中途解約条件)\\n- 金額に関する事実(金額の内訳、税込/税抜の別)\\n- 支払条件(支払時期・支払方法・締め日)\\n- 納品・検収・役務提供の時期に関する定め\\n- その他、勘定科目の判定に影響する記載(担保・保証、所有権の移転、資産の取得か利用か、継続か一時か など)\\n\\n# ルール\\n- 金額・日付・名称は書類の記載どおり正確に書き写す。推測で補完しない\\n- 記載が無い項目は「記載なし」、記入欄はあるが空欄の項目(社名・金額・日付など)は「空欄」とする。推測で埋めない\\n- 添付資料(見積書・料金表・仕様書など)に本文の空欄を補う情報(金額・数量など)があれば、出どころを付けて採用する(例: 「金額: 1,200,000円(見積書より)」)\\n- 記載が曖昧で解釈が分かれる箇所は、内容の末尾に「(要確認)」を付ける\\n- 本文が空・不完全で、添付ファイルからも何も読み取れない場合は、表の代わりにその旨と対処(ページを画像にして添付し直す、またはPDFを直接読めるAIモデルに切り替える)を1行で伝える\\n\\n# 出力形式\\n前置きや解説は書かず、次のMarkdownだけを出力してください。\\n\\n## 📋 契約書から読み取った事実\\n| 項目 | 内容 |\\n|---|---|\\n| (項目名) | (内容) |\\n\\n## 🎯 一言でいうと(状況の要約)\\n(簿記の試験の問題文のように、この契約で自社に何が起きる状況かを金額を書かずに1〜2文で。例: 「当社は事務所を借りる契約を結び、契約時に敷金を差し入れ、毎月の賃料を預金から支払う。」上の事実表と矛盾しないこと。ドラフトで確定していない場合は「〜する予定」と書く。)\"},{\"id\":\"user-prompt-summary\",\"role\":\"user\",\"text\":\"以下はアップロードされた書類(複数ある場合は連結)から抽出した本文です。書類が画像として添付されている場合は本文が空のことがあるため、その場合は添付画像を直接読み取ってください。この書類一式から事実を抽出してください。\\n\\n<契約書本文>\\n{{#conversation.contract_text#}}\\n</契約書本文>\\n\\n<ユーザーの入力>\\n{{#sys.query#}}\\n</ユーザーの入力>\\n(ユーザーの入力が「.」などの記号だけの場合は無視してください。訂正や補足が書かれていれば事実として反映し、該当箇所に「(ユーザー入力より)」と付記してください。)\"}],\"selected\":false,\"title\":\"契約内容サマリー\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_summary\",\"position\":{\"x\":2512,\"y\":40},\"positionAbsolute\":{\"x\":2512,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"desc\":\"読み取り内容を会話変数に保存し、次のターン(分類時)で参照できるようにする。\",\"items\":[{\"input_type\":\"variable\",\"operation\":\"over-write\",\"value\":[\"llm_summary\",\"text\"],\"variable_selector\":[\"conversation\",\"contract_summary\"]}],\"selected\":false,\"title\":\"読み取り内容を保存\",\"type\":\"assigner\",\"version\":\"2\"},\"height\":88,\"id\":\"save-summary\",\"position\":{\"x\":2816,\"y\":40},\"positionAbsolute\":{\"x\":2816,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"answer\":\"{{#llm_summary.text#}}\\n\\n---\\n上記の読み取り内容をもとに、キャッシュ(現金・預金)の相手勘定となる勘定科目を判定します。\\n✅ 内容が正しければ「**OK**」と返信してください。\\n✏️ 誤りや補足があれば、訂正内容をそのまま返信してください(例:「当社は借主です」)。{{#env_check.output#}}\",\"desc\":\"読み取った内容をユーザーに提示し、確認・訂正を求める。\",\"selected\":false,\"title\":\"読み取り内容の確認依頼\",\"type\":\"answer\",\"variables\":[]},\"height\":120,\"id\":\"answer-confirm\",\"position\":{\"x\":3120,\"y\":40},\"positionAbsolute\":{\"x\":3120,\"y\":40},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"cases\":[{\"case_id\":\"case-question\",\"conditions\":[{\"comparison_operator\":\"start with\",\"id\":\"cond-question\",\"value\":\"質問\",\"varType\":\"string\",\"variable_selector\":[\"llm_journal\",\"text\"]}],\"id\":\"case-question\",\"logical_operator\":\"and\"}],\"desc\":\"更問い(質問)の場合は判定に進まず、質問をそのまま返信します。\",\"selected\":false,\"title\":\"条件分岐(更問いチェック)\",\"type\":\"if-else\"},\"height\":126,\"id\":\"if-else-q\",\"position\":{\"x\":3728,\"y\":190},\"positionAbsolute\":{\"x\":3728,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"answer\":\"{{#llm_journal.text#}}\\n\\n(回答をそのまま返信してください。判定を続けます。)\",\"desc\":\"判定に必要な情報が足りないときの質問を返信します。\",\"selected\":false,\"title\":\"回答(質問)\",\"type\":\"answer\",\"variables\":[]},\"height\":100,\"id\":\"answer-q\",\"position\":{\"x\":4032,\"y\":410},\"positionAbsolute\":{\"x\":4032,\"y\":410},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"確認済みの契約内容から一般的な仕訳の流れ(3〜5行)を整理し、主目的の行をもとにキャッシュ(現金・預金)の相手勘定を1つ特定します(3形式共通の前段)。\",\"memory\":{\"query_prompt_template\":\"{{#sys.query#}}\",\"role_prefix\":{\"assistant\":\"\",\"user\":\"\"},\"window\":{\"enabled\":false,\"size\":50}},\"model\":{\"completion_params\":{\"max_tokens\":8192,\"temperature\":0.2},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-journal\",\"role\":\"system\",\"text\":\"あなたは日本の会計実務に精通した経理・会計の専門家です。確認済みの契約内容をもとに、この契約で発生する一般的な会計仕訳の流れを短く整理し、キャッシュ(現金・預金)の相手勘定となる勘定科目を1つ特定してください。出力はすべて日本語で行ってください。\\n\\n# この分析の目的\\n- 後段が、ここで特定した「相手勘定」1科目に勘定科目コードを付与する。ここでは仕訳の流れの整理と相手勘定の特定だけを行う(コードは扱わない)\\n- 科目名は一般的な名称でよい(後段が会社の科目一覧と照合する)。金額は書かない\\n\\n# 自社の視点(最重要)\\n- 仕訳は必ず「自社」の視点で考える。自社={{#env.company_name#}}(環境変数 company_name。未設定の場合は、ユーザーの発言と確認済みの読み取り内容から自社側の当事者を特定する)\\n- まず契約当事者のどちらが自社かを特定する。自社が「提供・販売・貸す側」なら収益側(売掛金・営業収入・前受収益 など)、「受ける・購入・借りる側」なら費用・資産側になる。向きを取り違えない\\n- どちらが自社か特定できない場合は、# 質問 の形式で質問する\\n\\n# 会社の会計方針・判定ルール(判定で必ず従う)\\n{{#env.accounting_policy#}}\\n\\n# 仕訳の流れの作り方\\n- 契約のライフサイクル(契約時・前払時・役務提供時/検収時・請求時・支払時・決算時・契約終了時 など)に沿って、発生する仕訳を3〜5行で書く(この契約に該当する場面だけでよい)\\n- 1行=「(場面) 借方科目 / 貸方科目」。金額・コードは書かない\\n- 継続的な契約(毎月の支払など)は、代表的な1回分を書き、場面に「毎月」等と記す\\n- 書類がドラフト(押印・署名前、社名・金額・日付が空欄)でも、記載済みの条件から流れを作る。空欄が相手勘定の判定を左右する場合は # 質問 の形式で質問する\\n\\n# 相手勘定の選び方(最重要)\\n- 仕訳の流れの中から「契約の主目的を最もよく表す行」を1本選ぶ(敷金・保証金・手数料・消費税・源泉税などの付随的な行は選ばない)\\n- その行の、現金・預金の反対側にある科目が「相手勘定」。自社が支払う契約なら費用や資産、受け取る契約なら収益になることが多いが、負債や純資産のこともある\\n- 現金・預金が動く行が無い契約(相殺・現物取引など)では、主目的の行の中心となる科目を相手勘定とする\\n- 主目的の行が複数あり得てどれか決められない場合は、# 質問 の形式で質問する\\n\\n# 質問(情報不足・判断できない場合)\\n- 契約書とこれまでの会話を読んでも相手勘定を決められない場合は、下記の出力の代わりに次の2行だけを出力する\\n  質問: (判断を最も左右する点を1つだけ、選択式で答えられるように聞く)\\n  回答例: (ユーザーがそのまま使える文例を「 / 」区切りで2〜3個)\\n- 迷いはあるが決められる場合は質問せず、理由に「(要確認: 理由)」を付ける\\n\\n# 出力形式(前置き・後書きは書かない。次の形式だけを出力する。ラベル名は一字一句そのまま使う)\\n仕訳の流れ:\\n1. (場面) 借方科目 / 貸方科目\\n2. (場面) 借方科目 / 貸方科目\\n主目的の行: (行番号を1つだけ)\\n根拠の仕訳: (その行を「(場面) 借方科目 / 貸方科目」の形でそのまま再掲)\\n相手勘定: (科目名を1つだけ)\\n性質: (資産・負債・純資産・収益・費用 のどれか1つ)\\n理由: (この科目を相手勘定と判断した理由を1〜2行)\"},{\"id\":\"user-prompt-journal\",\"role\":\"user\",\"text\":\"以下はアップロードされた契約書から抽出した本文と、確認済みの読み取り内容です。契約書が画像として添付されている場合は本文が空のことがあるため、その場合は添付ファイルとこれまでの会話を判断材料にしてください。この契約の一般的な仕訳の流れを整理し、キャッシュ(現金・預金)の相手勘定を特定してください。\\n\\n<契約書本文>\\n{{#conversation.contract_text#}}\\n</契約書本文>\\n\\n<読み取り内容(確認済み)>\\n{{#conversation.contract_summary#}}\\n</読み取り内容>\\n(これまでの会話でのユーザーの回答・訂正も判断材料に使うこと。)\"}],\"selected\":false,\"title\":\"仕訳の流れ分析\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_journal\",\"position\":{\"x\":2208,\"y\":190},\"positionAbsolute\":{\"x\":2208,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"answer\":\"(この文言は生成時に、各判定形式の確定結果の表への参照に置き換わります)\",\"desc\":\"確定した相手勘定(勘定科目)とコードの表、または更問い(質問)を返信します。\",\"selected\":false,\"title\":\"回答(仕訳)\",\"type\":\"answer\",\"variables\":[]},\"height\":120,\"id\":\"answer-final\",\"position\":{\"x\":4336,\"y\":190},\"positionAbsolute\":{\"x\":4336,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244}]},\"flat\":{\"scaffold_nodes\":[{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"前段で特定した相手勘定に対応する7桁候補を、7桁コードの候補一覧(横並び)から1つ選びます。\",\"memory\":{\"query_prompt_template\":\"{{#sys.query#}}\",\"role_prefix\":{\"assistant\":\"\",\"user\":\"\"},\"window\":{\"enabled\":false,\"size\":50}},\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-code7\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n前段の仕訳分析で、この契約のキャッシュ(現金・預金)の相手勘定となる勘定科目が特定されています。\\n下の【7桁コードの候補一覧】から、その相手勘定として最も適切な候補を1つ選びます。\\n候補は分類の階層をたどらず、すべて横並びで示されます。経路(スラッシュ区切り)と定義を読み、相手勘定の科目名・性質に最も合うものを選んでください。\\n\\n# ルール\\n- 仕訳分析の「相手勘定」「性質」「根拠の仕訳」を判定の中心に置く(相手勘定は一般的な名称のことがあるため、一覧の中で最も意味が近い候補に対応させる)\\n- 契約書・これまでの会話は補助的な確認に使う(仕訳分析と明らかに矛盾する場合は契約書を優先し、理由にその旨を書く)\\n- 判定は必ず自社の視点で行う。自社(会社名): {{#env.company_name#}}\\n- 会社の会計方針・判定ルール: {{#env.accounting_policy#}}\\n\\n# 出力形式(この2行だけを出力する。前置き・後書き・コードは書かない)\\n経路: (選んだ候補の経路を、一覧から一字一句そのまま)\\n理由: (選定理由を1〜2行。相手勘定・定義のどこが決め手か)\\n\\n# 質問(判定できない場合)\\n- 仕訳分析と契約書を読んでも1つに決められない場合は、上の2行の代わりに次の2行だけを出力する\\n質問: (判断を最も左右する点を1つだけ、選択式で答えられるように聞く)\\n回答例: (ユーザーがそのまま使える文例を「 / 」区切りで2〜3個)\\n\\n【7桁コードの候補一覧】(1行=「- 経路 [7桁コード]: 定義」)\\n{{#env.codes7_list#}}\"},{\"id\":\"user-prompt-code7\",\"role\":\"user\",\"text\":\"以下は前段の仕訳分析と、契約書の本文・確認済みの読み取り内容です。キャッシュの相手勘定に対応する7桁候補を一覧から1つ選んでください。\\n\\n<仕訳の分析>\\n{{#llm_journal.text#}}\\n</仕訳の分析>\\n\\n<契約書本文>\\n{{#conversation.contract_text#}}\\n</契約書本文>\\n\\n<読み取り内容(確認済み)>\\n{{#conversation.contract_summary#}}\\n</読み取り内容>\\n(これまでの会話でのユーザーの回答・訂正も判断材料に使うこと。)\"}],\"selected\":false,\"title\":\"7桁選択(横並び)\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_code7\",\"position\":{\"x\":2208,\"y\":190},\"positionAbsolute\":{\"x\":2208,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"選択した7桁に紐付く10桁候補を、名称と書き分けの定義(環境変数)を照らして1つに絞り込みます。\",\"memory\":{\"query_prompt_template\":\"{{#sys.query#}}\",\"role_prefix\":{\"assistant\":\"\",\"user\":\"\"},\"window\":{\"enabled\":false,\"size\":50}},\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-code10\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n7桁の選択結果を受けて、その7桁に紐付く10桁コード(下3桁)を確定します。\\n【7桁→10桁の対応表】のうち、選ばれた経路の7桁の配下にある候補だけを対象に、名称と書き分けの定義(環境変数で管理)を照らして最も適切な1つを選んでください。\\n\\n# ルール\\n- 対象は選ばれた7桁の配下の候補のみ。他の7桁の配下からは選ばない\\n- 候補が1つしか無ければそれを選ぶ\\n- 選ばれた7桁の配下に10桁候補が無い場合は、名称に「7桁止まり」と書く(コードは7桁のまま確定される)\\n- 前段の仕訳分析の「相手勘定」「性質」「根拠の仕訳」を書き分けの判断に使う\\n- 会社の会計方針・判定ルール: {{#env.accounting_policy#}}\\n- <7桁の選択>が「質問:」で始まる場合は、その質問と回答例の2行をそのまま出力する\\n\\n# 出力形式(この3行だけを出力する。前置き・後書き・コードは書かない)\\n経路: (7桁の選択の経路をそのまま)\\n名称: (選んだ10桁候補の名称を、対応表から一字一句そのまま。無ければ「7桁止まり」)\\n理由: (書き分けの定義のどこに該当したかを1〜2行)\\n\\n# 質問(絞り込めない場合)\\n- どうしても1つに決められない場合のみ、上の3行の代わりに次の2行だけを出力する\\n質問: (判断を最も左右する点を1つだけ、選択式で答えられるように聞く)\\n回答例: (ユーザーがそのまま使える文例を「 / 」区切りで2〜3個)\\n\\n【7桁→10桁の対応表】(「[7桁] 経路」の行の下に、配下の「- 名称 [3桁]: 書き分けの定義」)\\n{{#env.codes10_list#}}\"},{\"id\":\"user-prompt-code10\",\"role\":\"user\",\"text\":\"以下は前段の仕訳分析・契約書の本文・確認済みの読み取り内容と、7桁の選択結果です。選ばれた7桁に紐付く10桁を確定してください。\\n\\n<仕訳の分析>\\n{{#llm_journal.text#}}\\n</仕訳の分析>\\n\\n<契約書本文>\\n{{#conversation.contract_text#}}\\n</契約書本文>\\n\\n<読み取り内容(確認済み)>\\n{{#conversation.contract_summary#}}\\n</読み取り内容>\\n\\n<7桁の選択>\\n{{#llm_code7.text#}}\\n</7桁の選択>\\n(これまでの会話でのユーザーの回答・訂正も判断材料に使うこと。)\"}],\"selected\":false,\"title\":\"10桁絞り込み\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_code10\",\"position\":{\"x\":2512,\"y\":190},\"positionAbsolute\":{\"x\":2512,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"code\":\"def main(sel7: str, sel10: str, codes7: str, codes10: str, journal: str) -> dict:\\n    # 7桁の選択(横並び)と10桁の絞り込みの結果から、相手勘定の勘定科目コードを\\n    # 機械的に確定し、仕訳分析(根拠の仕訳)と合わせて1つの結果表にまとめる。\\n    # LLMは経路・名称しか書かない。コードはこの対応表からだけ引く(創作は構造的に起きない)。\\n    import re\\n    import unicodedata\\n\\n    def nk(s):\\n        return unicodedata.normalize('NFKC', (s or '')).strip()\\n\\n    def field(text, key):\\n        for line in (text or '').split('\\\\n'):\\n            line = nk(line)\\n            if line.startswith(key + ':'):\\n                return nk(line[len(key) + 1:])\\n        return ''\\n\\n    # 質問の引き継ぎ(どちらかのLLMが質問を返したら、そのまま出力して終わる)\\n    for t in (sel10, sel7):\\n        lines = [nk(l) for l in (t or '').split('\\\\n') if nk(l)]\\n        if lines and lines[0].startswith('質問'):\\n            return {'text': '\\\\n'.join(lines) + '\\\\n\\\\n(そのまま返信してください。回答をもとに判定を続けます。)', 'code': ''}\\n\\n    # 対応表の読み込み\\n    path7 = {}\\n    for line in (codes7 or '').split('\\\\n'):\\n        line = nk(line)\\n        if line.startswith('- '):\\n            body = line[2:].split(': ', 1)[0]\\n            m = re.search(r'\\\\[([0-9]{7})\\\\]', body)\\n            if m:\\n                path7[nk(body.split('[', 1)[0])] = m.group(1)\\n\\n    groups = {}\\n    cur = None\\n    for line in (codes10 or '').split('\\\\n'):\\n        s = nk(line)\\n        if not s:\\n            continue\\n        m = re.match(r'\\\\[([0-9]{7})\\\\]', s)\\n        if m:\\n            cur = m.group(1)\\n            groups.setdefault(cur, [])\\n            continue\\n        if s.startswith('- ') and cur:\\n            body = s[2:].split(': ', 1)[0]\\n            m = re.search(r'\\\\[([0-9]{3})\\\\]', body)\\n            if m:\\n                groups[cur].append((nk(body.split('[', 1)[0]), m.group(1)))\\n\\n    notes = []\\n    path = field(sel7, '経路')\\n    code7 = path7.get(path, '')\\n    if not code7 and path:\\n        hits = [p for p in path7 if p.endswith('/' + path)]\\n        if len(hits) == 1:\\n            path, code7 = hits[0], path7[hits[0]]\\n        elif len(hits) > 1:\\n            notes.append('経路「%s」が複数の候補に一致します(%s)。要確認。' % (path, '、'.join(sorted(hits)[:3])))\\n    if not code7:\\n        notes.append('経路「%s」が7桁候補一覧(codes7_list)に見つかりません。要確認。' % path)\\n\\n    name10 = field(sel10, '名称')\\n    final = ''\\n    if code7:\\n        if name10 in ('', '7桁止まり'):\\n            final = code7\\n            if groups.get(code7):\\n                notes.append('この7桁には10桁候補が%d件あります。名称が選ばれていないため7桁止まりにしました。要確認。' % len(groups[code7]))\\n        else:\\n            three = dict(groups.get(code7, []))\\n            if name10 in three:\\n                final = code7 + three[name10]\\n            else:\\n                cands = [n for n, _ in groups.get(code7, [])]\\n                final = code7\\n                notes.append('名称「%s」が [%s] の10桁候補に見つからないため7桁止まりにしました(候補: %s)。要確認。'\\n                             % (name10, code7, '、'.join(cands[:5]) if cands else 'なし'))\\n\\n    # 結果表(相手勘定=判定経路の末端科目。仕訳分析の科目名と違う場合は併記)\\n    leaf = name10 if name10 not in ('', '7桁止まり') else (path.split('/')[-1] if path else '')\\n    subject = leaf or '-'\\n    j_account = field(journal, '相手勘定')\\n    if j_account and leaf and nk(j_account) != nk(leaf):\\n        subject = '%s(仕訳上の名称: %s)' % (leaf, j_account)\\n\\n    route = path or '-'\\n    if path and name10 not in ('', '7桁止まり'):\\n        route = '%s/%s' % (path, name10)\\n\\n    reasons = []\\n    if field(sel7, '理由'):\\n        reasons.append('7桁: ' + field(sel7, '理由'))\\n    if field(sel10, '理由'):\\n        reasons.append('10桁: ' + field(sel10, '理由'))\\n\\n    out = ['## 🔢 判定結果(キャッシュの相手勘定)',\\n           '| 項目 | 内容 |',\\n           '|---|---|',\\n           '| 相手勘定(科目) | %s |' % subject,\\n           '| 確定コード | %s |' % (final or '未確定'),\\n           '| 判定経路 | %s |' % route,\\n           '| 判定の理由 | %s |' % (' / '.join(reasons) or '-'),\\n           '| 根拠の仕訳 | %s |' % (field(journal, '根拠の仕訳') or '-')]\\n    if notes:\\n        out.append('')\\n        out.append('⚠️ 確認事項:')\\n        for x in notes:\\n            out.append('- ' + x)\\n    return {'text': '\\\\n'.join(out), 'code': final}\\n\",\"code_language\":\"python3\",\"desc\":\"選択された経路・名称から相手勘定のコードを対応表で機械的に確定し、根拠の仕訳と合わせて結果表にまとめます(LLMはコードに触れません)。\",\"outputs\":{\"code\":{\"children\":null,\"type\":\"string\"},\"text\":{\"children\":null,\"type\":\"string\"}},\"selected\":false,\"title\":\"コード確定\",\"type\":\"code\",\"variables\":[{\"value_selector\":[\"llm_code7\",\"text\"],\"variable\":\"sel7\"},{\"value_selector\":[\"llm_code10\",\"text\"],\"variable\":\"sel10\"},{\"value_selector\":[\"env\",\"codes7_list\"],\"variable\":\"codes7\"},{\"value_selector\":[\"env\",\"codes10_list\"],\"variable\":\"codes10\"},{\"value_selector\":[\"llm_journal\",\"text\"],\"variable\":\"journal\"}]},\"height\":92,\"id\":\"code_final\",\"position\":{\"x\":2816,\"y\":190},\"positionAbsolute\":{\"x\":2816,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244}]},\"pick\":{\"scaffold_nodes\":[{\"data\":{\"context\":{\"enabled\":false,\"variable_selector\":[]},\"desc\":\"前段で特定した相手勘定に対応する候補を、全コード候補の一覧(横並び)から1回で選びます。\",\"memory\":{\"query_prompt_template\":\"{{#sys.query#}}\",\"role_prefix\":{\"assistant\":\"\",\"user\":\"\"},\"window\":{\"enabled\":false,\"size\":50}},\"model\":{\"completion_params\":{\"temperature\":0.1},\"mode\":\"chat\",\"name\":\"gpt-4o\",\"provider\":\"openai\"},\"prompt_template\":[{\"id\":\"system-prompt-pick\",\"role\":\"system\",\"text\":\"あなたは日本の企業会計に精通した経理・会計の専門家です。\\n前段の仕訳分析で、この契約のキャッシュ(現金・預金)の相手勘定となる勘定科目が特定されています。\\n下の【コード候補の一覧】から、その相手勘定として最も適切な候補を1つ選びます。\\n候補は分類の階層をたどらず、10桁コード(10桁の無い科目は7桁コード)まで含めてすべて横並びで示されます。\\n経路(スラッシュ区切り)と定義を読み、相手勘定の科目名・性質に最も合うものを選んでください。\\n\\n# ルール\\n- 仕訳分析の「相手勘定」「性質」「根拠の仕訳」を判定の中心に置く(相手勘定は一般的な名称のことがあるため、一覧の中で最も意味が近い候補に対応させる)\\n- 契約書・これまでの会話は補助的な確認に使う(仕訳分析と明らかに矛盾する場合は契約書を優先し、理由にその旨を書く)\\n- 判定は必ず自社の視点で行う。自社(会社名): {{#env.company_name#}}\\n- 会社の会計方針・判定ルール: {{#env.accounting_policy#}}\\n\\n# 出力形式(この2行だけを出力する。前置き・後書き・コードは書かない)\\n経路: (選んだ候補の経路を、一覧から一字一句そのまま)\\n理由: (選定理由を1〜2行。相手勘定・定義のどこが決め手か)\\n\\n# 質問(判定できない場合)\\n- 仕訳分析と契約書を読んでも1つに決められない場合は、上の2行の代わりに次の2行だけを出力する\\n質問: (判断を最も左右する点を1つだけ、選択式で答えられるように聞く)\\n回答例: (ユーザーがそのまま使える文例を「 / 」区切りで2〜3個)\\n\\n【コード候補の一覧】(1行=「- 経路 [コード]: 定義」)\\n{{#env.codes_list#}}\"},{\"id\":\"user-prompt-pick\",\"role\":\"user\",\"text\":\"以下は前段の仕訳分析と、契約書の本文・確認済みの読み取り内容です。キャッシュの相手勘定に対応する候補を一覧から1つ選んでください。\\n\\n<仕訳の分析>\\n{{#llm_journal.text#}}\\n</仕訳の分析>\\n\\n<契約書本文>\\n{{#conversation.contract_text#}}\\n</契約書本文>\\n\\n<読み取り内容(確認済み)>\\n{{#conversation.contract_summary#}}\\n</読み取り内容>\\n(これまでの会話でのユーザーの回答・訂正も判断材料に使うこと。)\"}],\"selected\":false,\"title\":\"コード一発選択(横並び)\",\"type\":\"llm\",\"variables\":[],\"vision\":{\"configs\":{\"detail\":\"high\",\"variable_selector\":[\"sys\",\"files\"]},\"enabled\":true}},\"height\":98,\"id\":\"llm_pick\",\"position\":{\"x\":2208,\"y\":190},\"positionAbsolute\":{\"x\":2208,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244},{\"data\":{\"code\":\"def main(sel: str, codes: str, journal: str) -> dict:\\n    # 一発選択の結果(経路)から相手勘定の勘定科目コードを機械的に確定し、\\n    # 仕訳分析(根拠の仕訳)と合わせて1つの結果表にまとめる。\\n    # LLMは経路しか書かない。コードはこの対応表からだけ引く(創作は構造的に起きない)。\\n    import re\\n    import unicodedata\\n\\n    def nk(s):\\n        return unicodedata.normalize('NFKC', (s or '')).strip()\\n\\n    def field(text, key):\\n        for line in (text or '').split('\\\\n'):\\n            line = nk(line)\\n            if line.startswith(key + ':'):\\n                return nk(line[len(key) + 1:])\\n        return ''\\n\\n    lines = [nk(l) for l in (sel or '').split('\\\\n') if nk(l)]\\n    if lines and lines[0].startswith('質問'):\\n        return {'text': '\\\\n'.join(lines) + '\\\\n\\\\n(そのまま返信してください。回答をもとに判定を続けます。)', 'code': ''}\\n\\n    table = {}\\n    for line in (codes or '').split('\\\\n'):\\n        line = nk(line)\\n        if line.startswith('- '):\\n            body = line[2:].split(': ', 1)[0]\\n            m = re.search(r'\\\\[([0-9]+)\\\\]', body)\\n            if m:\\n                table[nk(body.split('[', 1)[0])] = m.group(1)\\n\\n    notes = []\\n    path = field(sel, '経路')\\n    code = table.get(path, '')\\n    if not code and path:\\n        hits = [p for p in table if p.endswith('/' + path)]\\n        if len(hits) == 1:\\n            path, code = hits[0], table[hits[0]]\\n        elif len(hits) > 1:\\n            notes.append('経路「%s」が複数の候補に一致します(%s)。要確認。' % (path, '、'.join(sorted(hits)[:3])))\\n    if not code:\\n        notes.append('経路「%s」がコード候補一覧(codes_list)に見つかりません。要確認。' % path)\\n\\n    # 結果表(相手勘定=判定経路の末端科目。仕訳分析の科目名と違う場合は併記)\\n    leaf = path.split('/')[-1] if path else ''\\n    subject = leaf or '-'\\n    j_account = field(journal, '相手勘定')\\n    if j_account and leaf and nk(j_account) != nk(leaf):\\n        subject = '%s(仕訳上の名称: %s)' % (leaf, j_account)\\n\\n    out = ['## 🔢 判定結果(キャッシュの相手勘定)',\\n           '| 項目 | 内容 |',\\n           '|---|---|',\\n           '| 相手勘定(科目) | %s |' % subject,\\n           '| 確定コード | %s |' % (code or '未確定'),\\n           '| 判定経路 | %s |' % (path or '-'),\\n           '| 判定の理由 | %s |' % (field(sel, '理由') or '-'),\\n           '| 根拠の仕訳 | %s |' % (field(journal, '根拠の仕訳') or '-')]\\n    if notes:\\n        out.append('')\\n        out.append('⚠️ 確認事項:')\\n        for x in notes:\\n            out.append('- ' + x)\\n    return {'text': '\\\\n'.join(out), 'code': code}\\n\",\"code_language\":\"python3\",\"desc\":\"選択された経路から相手勘定のコードを対応表で機械的に確定し、根拠の仕訳と合わせて結果表にまとめます(LLMはコードに触れません)。\",\"outputs\":{\"code\":{\"children\":null,\"type\":\"string\"},\"text\":{\"children\":null,\"type\":\"string\"}},\"selected\":false,\"title\":\"コード確定\",\"type\":\"code\",\"variables\":[{\"value_selector\":[\"llm_pick\",\"text\"],\"variable\":\"sel\"},{\"value_selector\":[\"env\",\"codes_list\"],\"variable\":\"codes\"},{\"value_selector\":[\"llm_journal\",\"text\"],\"variable\":\"journal\"}]},\"height\":92,\"id\":\"code_pick\",\"position\":{\"x\":2512,\"y\":190},\"positionAbsolute\":{\"x\":2512,\"y\":190},\"selected\":false,\"sourcePosition\":\"right\",\"targetPosition\":\"left\",\"type\":\"custom\",\"width\":244}]}}"


# ---------------------------------------------------------------- 実行

def main():
    ap = argparse.ArgumentParser(description='分類ツリーから Dify ワークフローYAMLを作る')
    ap.add_argument('tree', help='分類ツリーのファイル(.md)')
    ap.add_argument('-o', '--output', default='contract-account-classification-pick.yml')
    ap.add_argument('--form', action='store_true',
                    help='フォーム形式(workflow。分類ツリーを1段ずつ下りる従来の形)で作る。'
                         '既定はコード一発選択形式(advanced-chat。契約書をチャットに添付して会話で進め、'
                         '仕訳の流れを整理してキャッシュの相手勘定を1つ判定し、コードを機械確定)')
    ap.add_argument('--tree', dest='style_tree', action='store_true',
                    help='ツリー判定形式(advanced-chat。コードの決め方だけが違い、相手勘定を分類ツリーで'
                         '1段ずつ下りて位置づける段階判定)で作る')
    ap.add_argument('--flat', action='store_true',
                    help='コード2段選択形式(advanced-chat。7桁コードの候補を横並びで1つ選び、'
                         'その7桁に紐付く10桁を名称と書き分けの定義で絞り込む)で作る。'
                         'ツリーに[7桁]のコードが必要')
    ap.add_argument('--pick', action='store_true',
                    help='コード一発選択形式(advanced-chat。10桁(無い科目は7桁)の候補すべてを'
                         '横並びで提示して1回で選ぶ)で作る。ツリーに[7桁]のコードが必要')
    ap.add_argument('--both', action='store_true',
                    help='コード一発選択形式と従来のフォーム形式の両方を作る(フォーム形式は別ファイルに)')
    ap.add_argument('--all', action='store_true',
                    help='チャット入力の3形式(コード一発選択・ツリー判定・コード2段選択)すべてを作る')
    ap.add_argument('--learn', action='store_true',
                    help='チャット3形式に自己学習(「正解:」返信で判定事例カード+判定前に過去の事例を参考)を組み込む。'
                         '既定(--learn-mode env)はナレッジもAPIキーも不要')
    ap.add_argument('--learn-mode', choices=['env', 'kb'], default='env',
                    help='自己学習の事例の置き場。env=環境変数 learned_cases に貼る(既定。ナレッジ不要)/ '
                         'kb=Difyの事例ナレッジ(検索ノード+自動保存。ナレッジの作成と環境変数 dify_base_url / '
                         'dataset_api_key / case_dataset_id が必要)')
    ap.add_argument('--learn-dataset-id', default='',
                    help='自己学習(kb): 事例ナレッジのID(ナレッジURLの /datasets/ のあとの英数字)。'
                         '「類似事例の検索」ノードに選択済みで入り、環境変数 case_dataset_id にも書き込む')
    ap.add_argument('--learn-base-url', default='',
                    help='自己学習(kb): 環境変数 dify_base_url に書き込む値(…/v1)')
    ap.add_argument('--learn-dataset-key', default='',
                    help='自己学習(kb): 環境変数 dataset_api_key に書き込む値(dataset-…)。'
                         'DSLファイルに平文で入るため、ファイルの共有先に注意')
    args = ap.parse_args()

    if not os.path.exists(args.tree):
        print('■ ファイルが見つかりません: %s' % args.tree)
        sys.exit(1)
    text = io.open(args.tree, encoding='utf-8').read()
    extras = json.loads(EXTRAS_JSON)
    learn_cfg = {'mode': args.learn_mode, 'base_url': args.learn_base_url, 'dataset_key': args.learn_dataset_key,
                 'dataset_id': args.learn_dataset_id}

    if args.all:
        styles = ['pick', 'tree', 'flat']
    elif args.both:
        styles = ['pick', 'form']
    else:
        styles = [s for s, on in (('form', args.form), ('tree', args.style_tree),
                                  ('flat', args.flat), ('pick', args.pick)) if on]
        if not styles:
            styles = ['pick']

    def derived(suffix):
        if args.output.endswith('-pick.yml'):
            base = args.output[:-len('-pick.yml')]
        elif args.output.endswith('.yml'):
            base = args.output[:-len('.yml')]
        else:
            base = args.output
        return base + suffix + '.yml'

    MAKERS = {'tree': ('ツリー判定形式', generate_tree, '-tree'),
              'flat': ('コード2段選択形式', generate_flat, '-flat'),
              'pick': ('コード一発選択形式', generate_pick, '-pick'),
              'form': ('フォーム形式(従来)', generate, '')}
    jobs = []
    for s in styles:
        label, make, suffix = MAKERS[s]
        if len(styles) == 1:
            out = args.output
        elif s == 'pick' and args.output.endswith('-pick.yml'):
            out = args.output
        else:
            out = derived(suffix)
        jobs.append((label, make, out))

    for label, make, out in jobs:
        try:
            d = make(text, extras) if make is generate else make(text, extras, args.learn, learn_cfg)
        except SystemExit as e:
            if make in (generate_flat, generate_pick) and len(jobs) > 1 and '[7桁]' in str(e):
                print('■ %sはスキップ: %s' % (label, e))
                continue
            print('')
            print('■ 変換できませんでした')
            print(str(e))
            print('')
            print('※ このメッセージをそのまま伝えず、内容をかみくだいて利用者に質問してください。')
            sys.exit(1)

        with io.open(out, 'w', encoding='utf-8') as f:
            f.write(dump(d))

        g = d['workflow']['graph']
        kinds = {}
        for n in g['nodes']:
            t = n['data']['type']
            kinds[t] = kinds.get(t, 0) + 1
        print('■ 変換しました: %s(%s)' % (out, label))
        print('  ノード %d個 / エッジ %d個 / 環境変数 %d個'
              % (len(g['nodes']), len(g['edges']), len(d['workflow']['environment_variables'])))
        print('  内訳: ' + ' / '.join('%s %d' % (k, v) for k, v in sorted(kinds.items(), key=lambda x: -x[1])))
    print('')
    print('次: Dify の「アプリを作成 → DSLファイルをインポート」で取り込んでください。')


if __name__ == '__main__':
    main()
