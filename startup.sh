#!/usr/bin/env bash
set -euo pipefail

# Ensure vendored deps (root of the zip) are importable
export PYTHONPATH="/home/site/wwwroot:${PYTHONPATH:-}"

# (Optional) show what's there during troubleshooting
python -V || true
python -c "import sys, pkgutil; print('PYTHONPATH=', sys.path)" || true
python -c "import uvicorn, gunicorn; print('uvicorn', uvicorn.__version__)" || true
python -c "import sys, cryptography; print('cryptography=', cryptography.__version__, cryptography.__file__); print('sys.maxunicode=', sys.maxunicode)" || true

# Start the API
exec gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:${PORT}
