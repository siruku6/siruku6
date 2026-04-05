"""
Markdown パーサーモジュール。

仕様書 .md ファイルを解析して構造化データ（dict）に変換する。

主な公開関数:
    parse_spec_file(filepath)    カラム定義形式の仕様書をパース
    parse_generic_file(filepath) 汎用 Markdown ファイルをパース
"""

import html as html_module
import re
from dataclasses import dataclass, field
from pathlib import Path


# ── データ構造 ─────────────────────────────────────────────

@dataclass
class Node:
    text: str
    indent: int
    children: list = field(default_factory=list)


# ── 低レベル変換ユーティリティ ──────────────────────────────

def parse_list_structure(lines: list[str]) -> list[Node]:
    """インデントベースの箇条書き行列をツリー構造に変換する。"""
    root_nodes: list[Node] = []
    stack: list[Node] = []

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        m = re.match(r'^( *)- (.*)$', stripped)
        if not m:
            continue
        indent = len(m.group(1))
        text = m.group(2)
        node = Node(text=text, indent=indent)

        while stack and stack[-1].indent >= indent:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            root_nodes.append(node)
        stack.append(node)

    return root_nodes


def _inline_fragment_to_html(text: str) -> str:
    """コードスパン以外のインライン Markdown（リンク・太字）を HTML に変換する。"""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '[':
            m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', text[i:])
            if m:
                label = html_module.escape(m.group(1))
                url = html_module.escape(m.group(2))
                result.append(f'<a href="{url}">{label}</a>')
                i += len(m.group(0))
                continue
        if text[i:i+2] == '**':
            m = re.match(r'\*\*([^*]+)\*\*', text[i:])
            if m:
                result.append(f'<strong>{html_module.escape(m.group(1))}</strong>')
                i += len(m.group(0))
                continue
        # 次の特殊文字までをまとめてエスケープ
        j = i + 1
        while j < len(text) and text[j] not in ('[', '*', '&', '<', '>'):
            j += 1
        result.append(html_module.escape(text[i:j]))
        i = j
    return ''.join(result)


def inline_md_to_html(text: str) -> str:
    """インライン Markdown（コードスパン・リンク・太字）を HTML に変換する。"""
    parts = re.split(r'(`[^`]+`)', text)
    result = []
    for part in parts:
        if part.startswith('`') and part.endswith('`') and len(part) > 1:
            result.append(f'<code>{html_module.escape(part[1:-1])}</code>')
        else:
            result.append(_inline_fragment_to_html(part))
    return ''.join(result)


def nodes_to_html(nodes: list[Node]) -> str:
    """Node リストを HTML に変換する。単一ノードはそのまま、複数は <ul><li> でリスト化。"""
    if not nodes:
        return ''
    if len(nodes) == 1 and not nodes[0].children:
        return inline_md_to_html(nodes[0].text)
    items = []
    for node in nodes:
        content = inline_md_to_html(node.text)
        if node.children:
            content += nodes_to_html(node.children)
        items.append(f'<li>{content}</li>')
    return '<ul>' + ''.join(items) + '</ul>'


def col_name_to_html(name: str) -> str:
    """
    カラム名を HTML に変換する。
    ' / ' 区切りで複数カラムがある場合は改行して並べる。
    """
    parts = [p.strip() for p in name.split(' / ')]
    return '<br>'.join(f'<code>{html_module.escape(p)}</code>' for p in parts)


# ── 仕様書パーサー内部ヘルパー ─────────────────────────────

def _split_by_h2(lines: list[str]) -> list[tuple[str, list[str]]]:
    """H2（## ）で lines を分割する。H2 が存在しない場合は空リストを返す。"""
    result: list[tuple[str, list[str]]] = []
    current_h2: str | None = None
    current_lines: list[str] = []
    for line in lines:
        m = re.match(r'^## (.+)$', line.rstrip())
        if m:
            if current_h2 is not None:
                result.append((current_h2, current_lines[:]))
            current_h2 = m.group(1)
            current_lines = []
        else:
            if current_h2 is not None:
                current_lines.append(line)
    if current_h2 is not None:
        result.append((current_h2, current_lines[:]))
    return result


def _is_column_section(nodes: list[Node]) -> bool:
    """ノードリストがカラム定義セクションか否かを判定する（子ノードに「算出方法」または「補足」があるか確認）。"""
    for node in nodes:
        for child in node.children:
            if child.text in ('算出方法', '補足'):
                return True
    return False


def _build_col_def(col_node: Node) -> dict:
    """カラム定義ノードから column_def dict を生成する。"""
    method_nodes: list[Node] = []
    note_nodes: list[Node] = []
    for child in col_node.children:
        if child.text == '算出方法':
            method_nodes = child.children
        elif child.text == '補足':
            note_nodes = child.children
    return {
        'name': col_node.text,
        'method_html': nodes_to_html(method_nodes),
        'note_html': nodes_to_html(note_nodes),
    }


# ── 汎用 Markdown → HTML 変換 ─────────────────────────────

def _try_parse_kv(text: str) -> tuple[str, str] | None:
    """'**key**: value' パターンを (key, value) に分解する。非マッチは None。"""
    m = re.match(r'^\*\*([^*]+)\*\*\s*:\s*(.+)$', text)
    return (m.group(1), m.group(2)) if m else None


# 担当工程の標準リスト（全職歴で比較できるよう固定順で定義）
_PROCESS_PHASES = ['要件定義', '基本設計', '詳細設計', '実装・開発', 'テスト・コードレビュー', '保守・運用']


def _render_phases(value: str) -> str:
    """担当工程の値（読点区切り）を ○/× バッジ HTML に変換する。"""
    listed = {p.strip() for p in re.split(r'[、,]', value) if p.strip()}
    return ' '.join(
        f'<span class="phase-yes">{html_module.escape(phase)}</span>'
        if phase in listed else
        f'<span class="phase-no">{html_module.escape(phase)}</span>'
        for phase in _PROCESS_PHASES
    )


def _render_kv_list(nodes: list[Node]) -> str:
    """
    ▼ 見出し直後のリストをテーブル + リストに変換する。

    先頭から続く「**key**: value かつ子なし」のノードをキー/バリューテーブルに変換し、
    それ以降のノード（子あり・パターン非マッチ）を通常リストとして出力する。
    """
    table_rows: list[tuple[str, str]] = []
    remaining: list[Node] = []
    switched = False

    for node in nodes:
        if not switched:
            kv = _try_parse_kv(node.text)
            if kv is not None and not node.children:
                table_rows.append(kv)
                continue
            switched = True
        remaining.append(node)

    parts = []
    if table_rows:
        rows_html = '\n'.join(
            f'<tr><td>{html_module.escape(k)}</td>'
            f'<td>{_render_phases(v) if k == "担当工程" else inline_md_to_html(v)}</td></tr>'
            for k, v in table_rows
        )
        parts.append(f'<table class="arg-table"><tbody>\n{rows_html}\n</tbody></table>')
    if remaining:
        items_html = ''.join(
            f'<li>{inline_md_to_html(n.text)}'
            + (nodes_to_html(n.children) if n.children else '')
            + '</li>'
            for n in remaining
        )
        parts.append(f'<ul class="generic-list">{items_html}</ul>')
    return '\n'.join(parts)


def md_table_to_html(table_lines: list[str]) -> str:
    """Markdown テーブル行列（先頭 | 形式）を HTML テーブルに変換する。"""
    rows = []
    for line in table_lines:
        stripped = line.strip()
        if not stripped:
            continue
        cells = [c.strip() for c in stripped.strip('|').split('|')]
        # セパレーター行（--- など）はスキップ
        if all(re.match(r'^[-: ]+$', c) for c in cells if c):
            continue
        rows.append(cells)

    if not rows:
        return ''

    html = '<table class="arg-table">\n'
    for row_idx, row in enumerate(rows):
        if row_idx == 0:
            html += '<thead><tr>' + ''.join(
                f'<th>{inline_md_to_html(cell)}</th>' for cell in row
            ) + '</tr></thead>\n<tbody>\n'
        else:
            html += '<tr>' + ''.join(
                f'<td>{inline_md_to_html(cell)}</td>' for cell in row
            ) + '</tr>\n'
    html += '</tbody>\n</table>\n'
    return html


def generic_lines_to_html(lines: list[str]) -> str:
    """
    汎用 Markdown 行列を HTML に変換する（H2・H3・テーブル・コードブロック・箇条書き対応）。

    見出し末尾に ▼ を付けると、直後のリストを自動キー/バリューテーブルに変換する。
    テーブル部分は **key**: value 形式かつ子なしのアイテムが対象で、
    子ありのアイテム以降は通常リストとして出力される。
    """
    html_parts = []
    i = 0
    kv_mode = False  # ▼ 付き見出し直後のリストを KV テーブル化するフラグ

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # H2 見出し
        m = re.match(r'^## (.+)$', stripped)
        if m:
            heading_text = m.group(1)
            kv_mode = heading_text.rstrip().endswith('▼')
            if kv_mode:
                heading_text = re.sub(r'\s*▼\s*$', '', heading_text)
            html_parts.append(f'<h2 class="section-heading">{inline_md_to_html(heading_text)}</h2>')
            i += 1
            continue

        # H3 見出し
        m = re.match(r'^### (.+)$', stripped)
        if m:
            heading_text = m.group(1)
            kv_mode = heading_text.rstrip().endswith('▼')
            if kv_mode:
                heading_text = re.sub(r'\s*▼\s*$', '', heading_text)
            html_parts.append(f'<h3 class="subsection-heading">{inline_md_to_html(heading_text)}</h3>')
            i += 1
            continue

        # ページブレーク（--- で改ページ）
        if re.match(r'^-{3,}$', stripped):
            html_parts.append('<div class="page-break"></div>')
            i += 1
            continue

        # コードブロック開始
        if re.match(r'^```', stripped):
            lang_m = re.match(r'^```(\w*)$', stripped)
            lang = lang_m.group(1) if lang_m else ''
            i += 1
            code_lines = []
            while i < len(lines) and not re.match(r'^```', lines[i].rstrip()):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 閉じ ``` をスキップ
            code_text = html_module.escape('\n'.join(code_lines))
            lang_cls = f' class="lang-{html_module.escape(lang)}"' if lang else ''
            html_parts.append(
                f'<pre class="code-block"><code{lang_cls}>{code_text}</code></pre>'
            )
            continue

        # Markdown テーブル（| で始まる行）
        if stripped.startswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].rstrip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            html_parts.append(md_table_to_html(table_lines))
            continue

        # 箇条書き
        if re.match(r'^( *)- ', stripped):
            list_lines = []
            while i < len(lines) and re.match(r'^( *)- ', lines[i]):
                list_lines.append(lines[i])
                i += 1
            nodes = parse_list_structure(list_lines)
            if kv_mode:
                html_parts.append(_render_kv_list(nodes))
                kv_mode = False
            else:
                items = ''.join(
                    f'<li>{inline_md_to_html(n.text)}'
                    + (nodes_to_html(n.children) if n.children else '')
                    + '</li>'
                    for n in nodes
                )
                html_parts.append(f'<ul class="generic-list">{items}</ul>')
            continue

        # 空行スキップ
        if not stripped:
            i += 1
            continue

        # 通常テキスト → <p>
        html_parts.append(f'<p class="generic-para">{inline_md_to_html(stripped)}</p>')
        i += 1

    return '\n'.join(html_parts)


# ── 公開パーサー ───────────────────────────────────────────

def parse_spec_file(filepath: Path) -> dict:
    """
    カラム定義形式の仕様書 .md ファイルをパースして構造化データを返す。

    返り値:
        type            : 'spec'
        title           : str
        column_defs     : list[{name, method_html, note_html}]
        extra_sections  : list[{heading, content_html}]
    """
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')

    # H1 見出しでセクション分割
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r'^# (.+)$', line)
        if m:
            if current_heading is not None:
                sections.append((current_heading, current_lines[:]))
            current_heading = m.group(1)
            current_lines = []
        else:
            if current_heading is not None:
                current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_lines[:]))

    title = sections[0][0] if sections else filepath.stem
    column_defs: list[dict] = []
    extra_sections = []

    for idx, (heading, sec_lines) in enumerate(sections):
        if idx == 0:
            # H2 サブセクションがあれば分割して処理（新スタイル）
            h2_subs = _split_by_h2(sec_lines)
            if h2_subs:
                for h2_heading, h2_lines in h2_subs:
                    col_nodes = parse_list_structure(h2_lines)
                    if _is_column_section(col_nodes):
                        # カラム定義セクション → テーブルに変換
                        column_defs.extend(_build_col_def(n) for n in col_nodes)
                    else:
                        # その他の ## セクション → 表の外に出力
                        extra_sections.append({
                            'heading': h2_heading,
                            'content_html': generic_lines_to_html(h2_lines),
                        })
            else:
                # H2 なし（旧スタイル）→ 全体をカラム定義として処理
                column_defs.extend(_build_col_def(n) for n in parse_list_structure(sec_lines))
        else:
            # 追加 H1 セクション（旧スタイルの「注意事項」など）
            extra_sections.append({
                'heading': heading,
                'content_html': generic_lines_to_html(sec_lines),
            })

    return {
        'type': 'spec',
        'title': title,
        'column_defs': column_defs,
        'extra_sections': extra_sections,
    }


def parse_generic_file(filepath: Path) -> dict:
    """
    汎用 Markdown ファイルをパースして構造化データを返す。
    execConfig.md など、カラム定義テーブル形式でない文書向け。

    返り値:
        type         : 'generic'
        title        : str
        content_html : str
    """
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    title = filepath.stem
    body_lines = []
    title_found = False
    for line in lines:
        m = re.match(r'^# (.+)$', line)
        if m and not title_found:
            # コードブロック外の最初の H1 のみをタイトルとして採用
            title = m.group(1)
            title_found = True
        else:
            body_lines.append(line)

    return {
        'type': 'generic',
        'title': title,
        'content_html': generic_lines_to_html(body_lines),
    }
