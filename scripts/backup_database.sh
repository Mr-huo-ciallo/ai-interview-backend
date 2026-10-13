#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${AI_INTERVIEW_BACKUP_DIR:-$HOME/backups/ai-interview}"
retention_days="${AI_INTERVIEW_BACKUP_RETENTION_DAYS:-30}"

if [[ ! "$retention_days" =~ ^[1-9][0-9]*$ ]]; then
  echo "AI_INTERVIEW_BACKUP_RETENTION_DAYS must be a positive integer" >&2
  exit 2
fi

mkdir -p -- "$backup_dir"
chmod 700 -- "$backup_dir"

exec 9>"$backup_dir/.backup.lock"
if ! flock -n 9; then
  echo "Another database backup is already running"
  exit 0
fi

cd -- "$project_dir"
if ! docker compose config --services | grep -Fxq database; then
  echo "Compose service 'database' was not found in $project_dir" >&2
  exit 1
fi

timestamp="$(date +%Y%m%dT%H%M%S%z)"
backup_file="$backup_dir/ai_interview_${timestamp}.sql.gz"
temporary_file="$(mktemp "$backup_dir/.ai_interview_${timestamp}.XXXXXXXX.sql.gz")"
trap 'rm -f -- "$temporary_file"' EXIT

docker compose exec -T database sh -ec '
  export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
  exec mysqldump --user=root --single-transaction --quick \
    --routines --events --triggers --no-tablespaces \
    --set-gtid-purged=OFF --default-character-set=utf8mb4 \
    "$MYSQL_DATABASE"
' | gzip -c > "$temporary_file"

test -s "$temporary_file"
gzip -t -- "$temporary_file"
mv -- "$temporary_file" "$backup_file"
trap - EXIT

(
  cd -- "$backup_dir"
  sha256sum -- "${backup_file##*/}" > "${backup_file##*/}.sha256"
)

echo "Backup complete: $backup_file ($(stat -c %s -- "$backup_file") bytes)"

# Only rotate files produced by this script, and only after a successful backup.
find "$backup_dir" -maxdepth 1 -type f -name 'ai_interview_*.sql.gz' \
  -mtime "+$((retention_days - 1))" -print0 |
while IFS= read -r -d '' old_file; do
  rm -f -- "$old_file" "$old_file.sha256"
  echo "Removed expired backup: $old_file"
done
