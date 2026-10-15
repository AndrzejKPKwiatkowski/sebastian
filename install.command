#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
python3 -c 'import sys; assert sys.version_info >= (3,11), "Zainstaluj Python 3.11 lub nowszy z python.org"'
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r requirements-learner.txt
.venv/bin/python sebastian.py init
if ! command -v tesseract >/dev/null 2>&1; then
  printf '\nOCR (tekst ze zdjęć i skanów) wymaga Tesseracta: brew install tesseract tesseract-lang\n'
fi
printf '\nGotowe. Nastepnie: source .venv/bin/activate\n'
