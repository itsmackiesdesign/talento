#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Refusing to deploy a dirty worktree." >&2
  exit 1
fi

git pull --ff-only origin master
docker compose -f compose.vps.yaml pull db redis
docker compose -f compose.vps.yaml build --pull migrate api worker frontend
docker compose -f compose.vps.yaml up -d --remove-orphans
docker compose -f compose.vps.yaml ps --all
