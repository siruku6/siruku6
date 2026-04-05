"""
設定定数モジュール。

出力ファイル名・メタ情報・処理対象ファイル一覧を定義する。
ここを変更することで PDF の表紙・出力先・対象ファイルを調整できる。
"""

from pathlib import Path

DOC_DIR = Path(__file__).parent.parent.parent / "docs"

OUTPUT_PDF = DOC_DIR / "formatted_doc.pdf"
OUTPUT_HTML = DOC_DIR / "formatted_doc.html"

# COMPANY_NAME = ""  # ← 必要に応じて変更
DATE = "2026年04月06日"
TITLE = "職務経歴書"
SUBTITLE = "hoge"

DOCS_ORDER = [
    "basic.md",
    "resume.md",
    "additional_skills.md",
]

# 汎用ドキュメント（別パーサーで処理）
GENERIC_FILES = {"basic.md", "resume.md", "additional_skills.md"}
