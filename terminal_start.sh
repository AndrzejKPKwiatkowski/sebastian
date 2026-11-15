#!/bin/bash
# Sebastian 2.15 — terminal w przeglądarce (ttyd). Hasło czytane z Pęku kluczy macOS, nie z pliku.
set -euo pipefail
cd "$(dirname "$0")"
PASS="$(security find-generic-password -s pl.sebastian.terminal -a sebastian -w)"
TTYD="$(command -v ttyd || echo /opt/homebrew/bin/ttyd)"
exec "$TTYD" -i 127.0.0.1 -p 7681 -c "sebastian:${PASS}" -W -t fontSize=15 /bin/zsh -l
