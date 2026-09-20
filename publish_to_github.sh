#!/usr/bin/env bash
# Push local changes to the existing Resource-planning-capacity-forecasting
# repo (macOS/Linux). The repo and its "origin" remote already exist --
# this just commits and pushes, then reminds you to enable Pages once.
#
# Usage (from the project root):
#   chmod +x publish_to_github.sh
#   ./publish_to_github.sh "optional commit message"
#
set -euo pipefail

COMMIT_MSG="${1:-Add resource-planning dashboard, advanced analyses, and forecasting updates}"

echo "==> Staging and committing"
git add -A
git commit -q -m "$COMMIT_MSG" || echo "(nothing new to commit)"

echo "==> Pushing to origin/main"
git push origin main

echo ""
echo "Done. If this is the first time enabling Pages on this repo:"
echo "  Settings -> Pages -> Source -> GitHub Actions"
echo "The included workflow (.github/workflows/deploy-pages.yml) will build and publish"
echo "the dashboard automatically on every push to main from then on."
