#!/usr/bin/env bash
# Cache-bust passport frontend assets: stamp ?v=<mtime> onto app.js/auth.js/auth.css in index.html.
# Run this after editing any of those files, then no hard-refresh / Cloudflare purge is needed.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDX="$DIR/index.html"
ORD="$DIR/order.html"
[ -f "$IDX" ] || { echo "index.html not found in $DIR" >&2; exit 1; }

stamp() {
  local f="$DIR/$1"
  [ -f "$f" ] && stat -c %Y "$f" || echo ""
}

APPJS=$(stamp app.js)
AUTHJS=$(stamp auth.js)
AUTHCSS=$(stamp auth.css)

# Replace existing ?v=<digits> (or seed the first time) for each asset.
perl -0pi -e "s#app\.js\?v=\d*#app.js?v=${APPJS}#g"  "$IDX"
perl -0pi -e "s#auth\.js\?v=\d*#auth.js?v=${AUTHJS}#g" "$IDX"
perl -0pi -e "s#auth\.css\?v=\d*#auth.css?v=${AUTHCSS}#g" "$IDX"

# order.html also loads auth.js — stamp it so edits propagate without hard refresh.
if [ -f "$ORD" ]; then
  perl -0pi -e "s#auth\.js(\?v=\d*)?#auth.js?v=${AUTHJS}#g" "$ORD"
fi

echo "Bumped cache-bust versions: app.js?v=${APPJS} auth.js?v=${AUTHJS} auth.css?v=${AUTHCSS}"
grep -E "\.(js|css)\?v=" "$IDX"
[ -f "$ORD" ] && grep -E "\.(js|css)\?v=" "$ORD"
