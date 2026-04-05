#!/usr/bin/env bash
# 出力ファイル仕様書 PDF 生成スクリプト
# Usage: bash build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Homebrew ライブラリパスを設定（weasyprint の Pango/GLib 依存に必要）
export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:-}:/opt/homebrew/lib"

"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/build.py"
