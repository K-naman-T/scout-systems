#!/usr/bin/env bash
# Deploy scout-systems to a remote host (code sync + outreach-tracker install).
set -euo pipefail

HOST="${DEPLOY_HOST:-your-vps-host}"
REMOTE_USER="${DEPLOY_USER:-your-user}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Rsync ${SRC} -> ${REMOTE_USER}@${HOST}:~/scout-systems/"
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.venv' \
  --exclude '_screenshots' \
  --exclude 'outreach-tracker/outreach.db' \
  --exclude 'outreach-tracker/outreach.db-*' \
  "${SRC}/" "${REMOTE_USER}@${HOST}:~/scout-systems/"

echo "==> Remote install..."
ssh "${REMOTE_USER}@${HOST}" 'bash ~/scout-systems/scripts/install-outreach-vps.sh'

echo "==> Done. Outreach tracker: http://${HOST}:8080/swipe"
