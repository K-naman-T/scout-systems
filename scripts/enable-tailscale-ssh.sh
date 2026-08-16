#!/usr/bin/env bash
# One-time setup for Tailscale SSH on a Linux node.
# Run ON the target machine with sudo:
#   sudo bash enable-tailscale-ssh.sh [username]
set -euo pipefail

USER_NAME="${1:-${SUDO_USER:-$(whoami)}}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0 ${USER_NAME}"
  exit 1
fi

echo "Granting tailscale operator to ${USER_NAME}..."
tailscale set --operator="${USER_NAME}"

echo "Enabling Tailscale SSH..."
sudo -u "${USER_NAME}" tailscale set --ssh --accept-risk=lose-ssh

echo "Done. Verify:"
sudo -u "${USER_NAME}" tailscale debug prefs | grep RunSSH
echo "From another tailnet machine: ssh ${USER_NAME}@$(tailscale status --self --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Self",{}).get("HostName","").rstrip("."))' 2>/dev/null || hostname)"