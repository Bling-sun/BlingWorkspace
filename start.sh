#!/usr/bin/env bash
# Bling-Workspace（论文精读 + 代码分析）· macOS / Linux 启动：建 .venv、缺依赖就装、启动并打开浏览器
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "没找到 Python 3，请先安装（https://www.python.org/downloads/）"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
if ! .venv/bin/python -c "import flask, markdown, fitz" 2>/dev/null; then
  .venv/bin/python -m pip install -r web/requirements.txt || .venv/bin/python -m pip install -r web/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi
exec .venv/bin/python web/server.py --open
