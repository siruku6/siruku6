#!/usr/bin/env python3
"""
出力ファイル仕様書 PDF 生成スクリプト

Usage:
    python build.py
"""

import sys

from build_modules.config import (
    DOC_DIR,
    DOCS_ORDER,
    GENERIC_FILES,
    OUTPUT_HTML,
    OUTPUT_PDF,
)
from build_modules.html_renderer import build_full_html
from build_modules.md_parser import parse_generic_file, parse_spec_file


# ── エントリポイント ─────────────────────────────────────

def main() -> None:
    try:
        from weasyprint import HTML as WeasyprintHTML
    except ImportError:
        print("エラー: weasyprint がインストールされていません。", file=sys.stderr)
        print("  uv pip install weasyprint", file=sys.stderr)
        sys.exit(1)

    print("=== 職務経歴書 PDF 生成 ===\n")

    # 1. markdown ファイルの解析
    # ------------------------------------------------------------
    specs = []
    for filename in DOCS_ORDER:
        path = DOC_DIR / filename
        if not path.exists():
            print(f"  警告: {filename} が見つかりません。スキップします。")
            continue
        if filename in GENERIC_FILES:
            spec = parse_generic_file(path)
            print(f"  解析完了: {spec['title']} （汎用ドキュメント）")
        else:
            spec = parse_spec_file(path)
            col_count = len(spec['column_defs'])
            print(f"  解析完了: {spec['title']} — {col_count} カラム定義")
        specs.append(spec)

    if not specs:
        print("エラー: 処理対象のファイルがありません。", file=sys.stderr)
        sys.exit(1)

    # 2. HTML ドキュメントの組み立て
    # ------------------------------------------------------------
    full_html = build_full_html(specs)

    OUTPUT_HTML.write_text(full_html, encoding='utf-8')
    print(f"\nHTML 保存: {OUTPUT_HTML}")

    # 3. PDF の生成
    # ------------------------------------------------------------
    print("PDF 生成中 ...")
    WeasyprintHTML(string=full_html, base_url=str(DOC_DIR)).write_pdf(str(OUTPUT_PDF))
    print(f"PDF 生成完了: {OUTPUT_PDF}")


if __name__ == '__main__':
    main()
