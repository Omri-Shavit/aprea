#!/usr/bin/env bash
# Install and register a GitHub Actions self-hosted runner on a GCP VM (Ubuntu).
#
# Usage (on the VM, after SSH):
#   curl -fsSL https://raw.githubusercontent.com/Omri-Shavit/aprea/main/scripts/setup-gcp-actions-runner.sh -o setup.sh
#   chmod +x setup.sh
#   sudo ./setup.sh YOUR_REGISTRATION_TOKEN
#
# Get YOUR_REGISTRATION_TOKEN from:
#   GitHub repo → Settings → Actions → Runners → New self-hosted runner → Linux
#   (Token expires in ~1 hour — run this script promptly after generating it.)

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Omri-Shavit/aprea}"
RUNNER_USER="${RUNNER_USER:-runner}"
RUNNER_HOME="/home/${RUNNER_USER}/actions-runner"
TOKEN="${1:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "Usage: sudo $0 REGISTRATION_TOKEN"
  echo "Get a token from GitHub → Settings → Actions → Runners → New self-hosted runner"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0 REGISTRATION_TOKEN"
  exit 1
fi

echo "==> Installing packages (git, curl, jq)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl jq ca-certificates

if ! id "${RUNNER_USER}" &>/dev/null; then
  echo "==> Creating user ${RUNNER_USER}..."
  useradd -m -s /bin/bash "${RUNNER_USER}"
fi

echo "==> Downloading latest GitHub Actions runner..."
RUNNER_VERSION="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')"
RUNNER_TAR="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_TAR}"

mkdir -p "${RUNNER_HOME}"
cd "${RUNNER_HOME}"
curl -fsSL -o "${RUNNER_TAR}" "${RUNNER_URL}"
tar xzf "${RUNNER_TAR}"
rm -f "${RUNNER_TAR}"
chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_HOME}"

echo "==> Configuring runner for ${REPO_URL}..."
sudo -u "${RUNNER_USER}" bash -c "
  cd '${RUNNER_HOME}'
  ./config.sh \
    --url '${REPO_URL}' \
    --token '${TOKEN}' \
    --name 'gcp-$(hostname)' \
    --labels 'self-hosted,Linux,X64' \
    --unattended \
    --replace
"

echo "==> Installing runner as a systemd service..."
cd "${RUNNER_HOME}"
./svc.sh install "${RUNNER_USER}"
./svc.sh start

echo ""
echo "Done. Runner should appear as Idle in:"
echo "  ${REPO_URL}/settings/actions/runners"
echo ""
echo "Check status: sudo ${RUNNER_HOME}/svc.sh status"
