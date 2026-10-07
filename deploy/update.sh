#!/bin/sh
# Подтягивает коммит, скачивает образы из Docker Hub и перезапускает контейнеры.
# В .env обновляет только адреса оплаты и Studio.
set -eu

cd "$(dirname "$0")/.."

if [ -z "${GIT_SHA:-}" ]; then
  echo "Не задан GIT_SHA." >&2
  exit 1
fi
if [ -z "${BOT_IMAGE:-}" ] || [ -z "${PREMIUM_IMAGE:-}" ]; then
  echo "Не заданы BOT_IMAGE и PREMIUM_IMAGE." >&2
  exit 1
fi

git fetch origin "$GIT_SHA"
git checkout --detach --force "$GIT_SHA"

if [ ! -f .env ]; then
  echo "На сервере нет .env. Создайте его из .env.example и заполните токены." >&2
  exit 1
fi

PAY_HOST="${PAY_HOST:-pay.chatwithyou.site}"
STUDIO_HOST="${STUDIO_HOST:-studio.chatwithyou.site}"

set_env() {
  key=$1
  value=$2
  tmp=$(mktemp)
  grep -v "^${key}=" .env > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" .env
  chmod 600 .env
}

set_env PAY_HOST "$PAY_HOST"
set_env STUDIO_HOST "$STUDIO_HOST"
set_env PREMIUM_URL "https://${PAY_HOST}"
set_env STUDIO_PUBLIC_URL "https://${STUDIO_HOST}"
set_env PREMIUM_PUBLISH "127.0.0.1:8080"

public_ip=$(curl -4 -fsS --max-time 15 https://api.ipify.org || true)
echo "PUBLIC_IP=${public_ip}"

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  printf '%s' "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
fi

docker compose --profile proxy pull
docker logout >/dev/null 2>&1 || true
docker compose --profile proxy up -d --no-build --remove-orphans
docker image prune -af
