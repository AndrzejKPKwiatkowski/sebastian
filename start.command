#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
open 'http://127.0.0.1:8765'
exec .venv/bin/python sebastian.py serve
