#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python"
if ! command -v uv >/dev/null || ! command -v npm >/dev/null; then
  print "Install uv and Node.js 22.12+ first. See README.md."
  read "?Press Return to close."
  exit 1
fi
uv sync --locked --python 3.13
if [[ ! -d web/node_modules ]]; then
  npm --prefix web ci
fi
npm --prefix web run build
print "Your default browser will open when Aperture is ready at http://127.0.0.1:8000."
print "Keep this window open; Control-C stops Aperture."
exec .venv/bin/python -m aperture --open-browser
