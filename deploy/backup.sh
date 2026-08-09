#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${BACKUP_DIR:-/srv/talento/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
database_tmp="${backup_dir}/.talento-db-${timestamp}.dump.tmp"
database_backup="${backup_dir}/talento-db-${timestamp}.dump"

umask 077
install -d -m 700 "$backup_dir"

cleanup() {
    rm -f "$database_tmp"
}
trap cleanup EXIT

docker compose \
    --project-directory "$repo_root" \
    --env-file "$repo_root/.env" \
    -f "$repo_root/compose.vps.yaml" \
    exec -T db pg_dump -U talento -d talento --format=custom > "$database_tmp"

mv "$database_tmp" "$database_backup"

docker run --rm --network none \
    -v talento-product_uploads:/source:ro \
    -v "$backup_dir:/backup" \
    alpine:3.22 \
    tar -czf "/backup/talento-uploads-${timestamp}.tar.gz" -C /source .

find "$backup_dir" -maxdepth 1 -type f \
    \( -name 'talento-db-*.dump' -o -name 'talento-uploads-*.tar.gz' \) \
    -mtime +7 -delete
