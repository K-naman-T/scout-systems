#!/usr/bin/env bash
# Install/update outreach-tracker on a VPS (uses docker for root ops).
set -euo pipefail

SRC="${HOME}/scout-systems"
DEST="/root/scout-systems"
OLD_TRACKER="/root/outreach-tracker"
SERVICE="outreach-tracker"

if [[ ! -d "${SRC}/outreach-tracker" ]]; then
  echo "Missing ${SRC}/outreach-tracker — rsync scout-systems first." >&2
  exit 1
fi

echo "==> Syncing code to ${DEST} (preserving production DB)..."
docker run --rm -v /:/host alpine sh -ceu "
  mkdir -p /host${DEST}
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude __pycache__ --exclude '*.pyc' --exclude .venv --exclude _screenshots \
      /host${SRC}/ /host${DEST}/
  else
    rm -rf /host${DEST}/*
    cp -a /host${SRC}/. /host${DEST}/
  fi
  if [ -f /host${OLD_TRACKER}/outreach.db ]; then
    cp -a /host${OLD_TRACKER}/outreach.db /host${DEST}/outreach-tracker/outreach.db
    echo 'Preserved production outreach.db'
  fi
  chmod -R a+rX /host${DEST}
"

echo "==> Creating venv + installing requirements..."
if docker run --rm -v /:/host alpine test -d "/host${OLD_TRACKER}/.venv"; then
  echo "Reusing existing venv from ${OLD_TRACKER}..."
  docker run --rm -v /:/host alpine sh -ceu "
    rm -rf /host${DEST}/outreach-tracker/.venv
    cp -a /host${OLD_TRACKER}/.venv /host${DEST}/outreach-tracker/.venv
  "
else
  docker run --rm --pid=host -v /:/host alpine chroot /host bash -ceu "
    cd ${DEST}/outreach-tracker
    python3 -m venv .venv
  "
fi
# Run pip inside host chroot (venv binaries are host ELF, not alpine)
docker run --rm --network host --pid=host -v /:/host alpine chroot /host bash -ceu "
  cd ${DEST}/outreach-tracker
  ./.venv/bin/python3 -m pip install -q --upgrade pip
  ./.venv/bin/python3 -m pip install -q -r requirements.txt
"

echo "==> Updating systemd unit..."
docker run --rm -v /:/host alpine sh -ceu "cat > /host/etc/systemd/system/${SERVICE}.service <<'UNIT'
[Unit]
Description=Scout Outreach Tracker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${DEST}/outreach-tracker
ExecStart=${DEST}/outreach-tracker/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
Environment=OUTREACH_DB=${DEST}/outreach-tracker/outreach.db

[Install]
WantedBy=multi-user.target
UNIT"

echo "==> Restarting ${SERVICE}..."
docker run --rm --pid=host -v /:/host alpine chroot /host bash -ceu "
  systemctl daemon-reload
  systemctl enable ${SERVICE}
  systemctl restart ${SERVICE}
  sleep 2
  systemctl is-active ${SERVICE}
"

echo "==> Health check..."
code="$(curl -s -o /tmp/swipe-check.html -w '%{http_code}' http://127.0.0.1:8080/swipe || true)"
if [[ "${code}" != "200" ]]; then
  echo "WARN: /swipe returned HTTP ${code}" >&2
  exit 1
fi
if grep -q 'app.css' /tmp/swipe-check.html && grep -q 'Review — Scout' /tmp/swipe-check.html; then
  echo "OK: new Scout UI is live on :8080"
else
  echo "WARN: response 200 but new UI markers not found" >&2
  head -5 /tmp/swipe-check.html
  exit 1
fi

rm -f /tmp/swipe-check.html
echo "Deploy complete: ${DEST}/outreach-tracker"