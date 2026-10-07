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

if [ ! -f .env ] && [ -z "${ENV_FILE:-}" ]; then
  echo "На сервере нет .env. Создайте его из .env.example и заполните токены." >&2
  exit 1
fi

if [ -n "${ENV_FILE:-}" ]; then
  secret_file=$(mktemp)
  printf '%s\n' "$ENV_FILE" | tr -d '\r' > "$secret_file"
  token_line=$(grep -E '^VK_TOKEN=' "$secret_file" | tail -n 1 || true)
  rm -f "$secret_file"
  if [ -z "$token_line" ]; then
    echo "В секрете ENV_FILE нет строки VK_TOKEN." >&2
    exit 1
  fi
  if [ ! -f .env ]; then
    : > .env
  fi
  tmp=$(mktemp)
  grep -v '^VK_TOKEN=' .env > "$tmp" || true
  printf '%s\n' "$token_line" >> "$tmp"
  mv "$tmp" .env
  chmod 600 .env
  echo "VK_TOKEN на сервере обновлён из ENV_FILE."
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
set_env PREMIUM_URL "https://vk.cc/d2HjY8"
set_env STUDIO_PUBLIC_URL "https://${STUDIO_HOST}"
set_env PREMIUM_PUBLISH "127.0.0.1:8080"

lookup_ip() {
  if command -v curl >/dev/null 2>&1; then
    curl -4 -fsS --max-time 15 https://api.ipify.org && return
    curl -4 -fsS --max-time 15 https://ifconfig.me/ip && return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -4 -qO- --timeout=15 https://api.ipify.org && return
  fi
  return 1
}

public_ip=$(lookup_ip || true)
public_ip=$(printf '%s' "$public_ip" | tr -d '[:space:]')
echo "IP_PARTS=$(printf '%s' "$public_ip" | tr '.' ' ')"

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  printf '%s' "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
fi

docker compose --profile proxy pull
docker logout >/dev/null 2>&1 || true
docker compose --profile proxy up -d --no-build --remove-orphans --force-recreate bot
docker restart vk-bot-caddy
sleep 12
docker logs vk-bot --tail 80 2>&1 | grep -E "Колонки bot_users|OK:|Нет права|Нет доступа|Токен невалиден|Бот запущен|Ошибка запуска|VK Error|Traceback" || true
sleep 8
docker logs vk-bot-caddy --tail 20 || true
docker image prune -af
