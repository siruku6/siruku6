"""
HTML レンダラーモジュール。

パース済みの仕様データ（dict）を受け取り、HTML フラグメントおよび
完成した HTML ドキュメントを生成する。

主な公開関数:
    spec_to_html_fragment(spec, section_num)    カラム定義仕様を HTML 化
    generic_to_html_fragment(spec, section_num) 汎用仕様を HTML 化
    build_full_html(specs)                      全セクションを1つの HTML に組み立て
"""

import html as html_module

from .config import DATE, DOC_DIR, SUBTITLE, TITLE
from .md_parser import col_name_to_html, parse_generic_file


# ── CSS ───────────────────────────────────────────────────

CSS = """\
/* ── ページ設定 ── */
@page {
    size: A4;
    margin: 20mm 20mm 22mm 22mm;
    @bottom-center {
        content: counter(page);
        font-family: "Hiragino Mincho ProN", "YuMincho", serif;
        font-size: 9pt;
        color: #aaa;
    }
}

/* ── 基本 ── */
* { box-sizing: border-box; }

body {
    font-family: "Hiragino Mincho ProN", "Hiragino Mincho Pro",
                 "YuMincho", "Yu Mincho", "MS Mincho", serif;
    font-size: 10.5pt;
    line-height: 1.8;
    color: #222;
}

a {
    color: #2a6fa8;
    text-decoration: underline;
}

strong {
    font-weight: bold;
}

code {
    font-family: "Menlo", "Monaco", "Courier New", monospace;
    font-size: 8.5pt;
    background: #eef0f6;
    padding: 1px 4px;
    border-radius: 2px;
    word-break: break-all;
}

/* ── 表紙（目次と同一ページ） ── */
.cover-page {
    text-align: center;
    padding: 16mm 0 12mm;
    border-bottom: 1px solid #c8d4e8;
    margin-bottom: 20px;
}

.cover-title {
    font-size: 28pt;
    font-weight: bold;
    color: #1c3260;
    letter-spacing: 0.2em;
    border-bottom: 2px solid #1c3260;
    padding-bottom: 14px;
    margin-bottom: 14px;
}

.cover-subtitle {
    font-size: 14pt;
    color: #444;
    letter-spacing: 0.1em;
    margin: 0 0 12px;
}

.cover-meta {
    font-size: 10.5pt;
    color: #555;
    line-height: 2.0;
}

/* ── 目次（表紙と同一ページ、ページ末でブレーク） ── */
.toc {
    page-break-after: always;
}

.toc-title {
    font-size: 15pt;
    color: #1c3260;
    border-bottom: 2px solid #1c3260;
    padding-bottom: 6px;
    margin-bottom: 18px;
}

.toc ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.toc ul li {
    padding: 7px 0;
    border-bottom: 1px dotted #ccc;
    font-size: 11pt;
}

.toc-num {
    color: #888;
    margin-right: 10px;
}

/* ── セクション ── */
.spec-section {
    page-break-before: always;
}

.spec-title {
    font-size: 18pt;
    color: #1c3260;
    border-left: 5px solid #3674a6;
    padding: 5px 12px;
    margin-bottom: 22px;
    background: #f5f7fb;
}

.no-content {
    color: #999;
    font-style: italic;
}

/* ── 仕様テーブル ── */
.spec-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 20px;
    font-size: 9pt;
    table-layout: fixed;
}

.col-w-name   { width: 27%; }
.col-w-method { width: 48%; }
.col-w-note   { width: 25%; }

.spec-table th {
    background-color: #1c3260;
    color: #fff;
    padding: 7px 10px;
    text-align: left;
    font-size: 10pt;
    font-weight: bold;
}

.spec-table td {
    padding: 6px 10px;
    vertical-align: top;
    border: 1px solid #ccd;
    word-break: break-word;
}

.spec-table tr:nth-child(even) td {
    background-color: #f5f7fb;
}

.col-name { font-weight: bold; }
.col-note { color: #555; font-size: 8.5pt; }

.spec-table ul {
    margin: 2px 0;
    padding-left: 16px;
}

.spec-table ul li {
    margin: 2px 0;
}

/* ── 注意事項 ── */
.extra-heading {
    font-size: 12pt;
    color: #333;
    border-bottom: 1px solid #bbb;
    padding-bottom: 4px;
    margin-top: 24px;
}

/* ── 汎用セクション ── */
.section-heading {
    font-size: 13pt;
    color: #1c3260;
    border-left: 4px solid #3674a6;
    border-bottom: 1px solid #c8d4e8;
    padding: 3px 10px 5px;
    margin-top: 28px;
    margin-bottom: 10px;
}

.subsection-heading {
    font-size: 11pt;
    color: #1c3260;
    border-left: 3px solid #3674a6;
    padding: 3px 10px;
    margin-top: 18px;
    margin-bottom: 6px;
    background: #f5f7fb;
}

.generic-para {
    margin: 6px 0 10px;
}

.generic-list {
    margin: 4px 0 10px;
    padding-left: 22px;
    line-height: 1.9;
}

.generic-list li {
    margin: 3px 0;
}

/* ── コードブロック ── */
.code-block {
    background: #f4f5fa;
    border: 1px solid #d0d4e8;
    border-left: 4px solid #3674a6;
    border-radius: 3px;
    padding: 10px 14px;
    margin: 10px 0;
    white-space: pre;
}

.code-block code {
    font-family: "Menlo", "Monaco", "Courier New", monospace;
    font-size: 8pt;
    line-height: 1.6;
    background: none;
    padding: 0;
    border-radius: 0;
}

/* ── 汎用テーブル ── */
.arg-table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 16px;
    font-size: 10pt;
}

.arg-table th {
    background-color: #edf0f8;
    color: #1c3260;
    padding: 6px 12px;
    text-align: left;
    font-weight: bold;
    border: 1px solid #c8d4e8;
}

.arg-table td {
    padding: 6px 12px;
    vertical-align: top;
    border: 1px solid #d0d8ee;
    word-break: break-word;
}

.arg-table tbody tr:nth-child(even) td {
    background-color: #f5f7fb;
}

/* 2カラムテーブルの1列目はラベルとして強調 */
.arg-table td:first-child {
    font-weight: bold;
    color: #1c3260;
    white-space: nowrap;
}

/* ── ページブレーク ── */
.page-break {
    page-break-before: always;
}

/* ── 担当工程バッジ ── */
.phase-yes, .phase-no {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 3px;
    font-size: 8.5pt;
    margin: 1px 3px 1px 0;
    white-space: nowrap;
}

.phase-yes {
    background: #e4f0e4;
    color: #276027;
    border: 1px solid #b8d8b8;
}

.phase-no {
    background: #f4f4f4;
    color: #bbb;
    border: 1px solid #e2e2e2;
}

/* ── 項番号 ── */
.section-num {
    color: #3674a6;
    font-weight: bold;
}

.toc-label {
    color: #666;
    margin-right: 4px;
}

/* ── 概要ページ ── */
.overview-body { margin-top: 8px; }

.overview-heading {
    font-size: 12pt;
    color: #1c3260;
    border-bottom: 2px solid #c8d4e8;
    padding-bottom: 4px;
    margin-top: 22px;
    margin-bottom: 8px;
}

.overview-list {
    margin: 4px 0 14px;
    padding-left: 20px;
    line-height: 2.0;
}
"""


# ── HTML フラグメント生成 ──────────────────────────────────

def spec_to_html_fragment(spec: dict, section_num: int | None = None) -> str:
    """パース済み仕様データ（type='spec'）を HTML フラグメントに変換する。"""
    title_esc = html_module.escape(spec['title'])
    num_html = f'<span class="section-num">{section_num}.</span>\u3000' if section_num is not None else ''
    html = f'<section class="spec-section">\n<h1 class="spec-title">{num_html}{title_esc}</h1>\n'

    if spec['column_defs']:
        html += '<table class="spec-table">\n'
        html += (
            '<colgroup>'
            '<col class="col-w-name">'
            '<col class="col-w-method">'
            '<col class="col-w-note">'
            '</colgroup>\n'
        )
        html += '<thead><tr><th>カラム名</th><th>算出方法</th><th>補足</th></tr></thead>\n'
        html += '<tbody>\n'
        for col in spec['column_defs']:
            name_html = col_name_to_html(col['name'])
            html += (
                f'<tr>'
                f'<td class="col-name">{name_html}</td>'
                f'<td class="col-method">{col["method_html"]}</td>'
                f'<td class="col-note">{col["note_html"]}</td>'
                f'</tr>\n'
            )
        html += '</tbody>\n</table>\n'
    else:
        html += '<p class="no-content">（未記載）</p>\n'

    for section in spec['extra_sections']:
        heading_esc = html_module.escape(section['heading'])
        html += f'<h2 class="extra-heading">{heading_esc}</h2>\n'
        html += section['content_html'] + '\n'

    html += '</section>\n'
    return html


def generic_to_html_fragment(spec: dict, section_num: int | None = None) -> str:
    """パース済み汎用ドキュメント（type='generic'）を HTML フラグメントに変換する。"""
    title_esc = html_module.escape(spec['title'])
    num_html = f'<span class="section-num">{section_num}.</span>\u3000' if section_num is not None else ''
    return (
        f'<section class="spec-section">\n'
        f'<h1 class="spec-title">{num_html}{title_esc}</h1>\n'
        f'{spec["content_html"]}\n'
        f'</section>\n'
    )


# ── ドキュメント全体の組み立て ─────────────────────────────

def build_full_html(specs: list[dict]) -> str:
    """全仕様を1つの HTML ドキュメントにまとめる。"""
    cover = f"""\
<div class="cover-page">
  <div>
    <p class="cover-title">{html_module.escape(TITLE)}</p>
    <p class="cover-subtitle">{html_module.escape(SUBTITLE)}</p>
  </div>
  <div class="cover-meta">
    <div>{html_module.escape(DATE)}</div>
  </div>
</div>"""

    overview_path = DOC_DIR / "overview.md"
    has_overview = overview_path.exists()

    # セクション番号: overview があれば 1 を使い、spec は続きから
    spec_start = 2 if has_overview else 1
    toc_lines = []
    if has_overview:
        toc_lines.append('    <li><span class="toc-num">1.</span>概要</li>')
    for i, s in enumerate(specs):
        num = spec_start + i
        toc_lines.append(
            f'    <li><span class="toc-num">{num}.</span>'
            f'{html_module.escape(s["title"])}</li>'
        )
    toc = f"""\
<div class="toc">
  <h2 class="toc-title">目次</h2>
  <ul>
{chr(10).join(toc_lines)}
  </ul>
</div>"""

    if has_overview:
        overview_spec = parse_generic_file(overview_path)
        overview_section = generic_to_html_fragment(overview_spec, 1)
    else:
        overview_section = ''

    spec_sections = '\n'.join(
        generic_to_html_fragment(s, spec_start + i) if s['type'] == 'generic'
        else spec_to_html_fragment(s, spec_start + i)
        for i, s in enumerate(specs)
    )

    return f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>{html_module.escape(TITLE)}</title>
  <style>
{CSS}
  </style>
</head>
<body>
{cover}
{toc}
{overview_section}
{spec_sections}
</body>
</html>"""
