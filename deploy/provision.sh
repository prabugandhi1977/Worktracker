#!/usr/bin/env bash
# One-time server setup for WorkTrack backend deployment.
# Run this once on a fresh Ubuntu/Debian VPS, logged in as the deploy user.
#
# Usage: ./provision.sh <git-repo-url> [deploy-path]

set -euo pipefail

REPO_URL="${1:?Usage: ./provision.sh <git-repo-url> [deploy-path]}"
DEPLOY_PATH="${2:-$HOME/worktrack-backend}"

if ! command -v docker &> /dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "Added $USER to the docker group. Log out and back in for this to take effect."
fi

if [ -d "$DEPLOY_PATH/.git" ]; then
  echo "Repo already exists at $DEPLOY_PATH, pulling latest..."
  git -C "$DEPLOY_PATH" pull
else
  echo "Cloning $REPO_URL into $DEPLOY_PATH..."
  git clone "$REPO_URL" "$DEPLOY_PATH"
fi

cd "$DEPLOY_PATH"

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "Created .env from .env.example — edit it now and set a real SECRET_KEY"
  echo "before starting the stack:"
  echo "  \$EDITOR $DEPLOY_PATH/.env"
  echo
else
  echo ".env already exists, leaving it as-is."
fi

echo "Starting the stack..."
docker compose up -d --build

echo
echo "Done. The API should be reachable on port 8000 once the containers are healthy:"
echo "  docker compose ps"
echo "  docker compose logs -f api"
echo
echo "For CI/CD, add these secrets to the GitHub repo (Settings > Secrets and variables > Actions):"
echo "  SSH_HOST=<this server's IP or hostname>"
echo "  SSH_USER=$USER"
echo "  SSH_PORT=22"
echo "  SSH_PRIVATE_KEY=<a private key whose public half is in ~/.ssh/authorized_keys on this server>"
echo "  DEPLOY_PATH=$DEPLOY_PATH"
