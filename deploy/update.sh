#!/bin/sh
# Подтягивает коммит, скачивает образы из Docker Hub и перезапускает контейнеры.
# В .env обновляет токены из секрета ENV_FILE и адрес Studio.
set -eu

cd "$(dirname "$0")/.."

if [ -z "${GIT_SHA:-}" ]; then
  echo "Не задан GIT_SHA." >&2
  exit 1
fi
if [ -z "${BOT_IMAGE:-}" ] || [ -z "${CHAT_API_IMAGE:-}" ] || [ -z "${TG_BOT_IMAGE:-}" ] || [ -z "${ENGINE_BRIDGE_IMAGE:-}" ]; then
  echo "Не заданы BOT_IMAGE, CHAT_API_IMAGE, TG_BOT_IMAGE и ENGINE_BRIDGE_IMAGE." >&2
  exit 1
fi

git fetch origin "$GIT_SHA"
git checkout --detach --force "$GIT_SHA"

if [ ! -f .env ] && [ -z "${ENV_FILE:-}" ] && [ -z "${ENV_FILE_B64:-}" ]; then
  echo "На сервере нет .env. Создайте его из .env.example и заполните токены." >&2
  exit 1
fi

set_env() {
  key=$1
  value=$2
  tmp=$(mktemp)
  grep -v "^${key}=" .env > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" .env
  chmod 600 .env
}

# Токены сообществ ВК из секрета ENV_FILE. Токены Telegram (123456:ABC...) пропускаются.
apply_secret_tokens() {
  secret_file=$(mktemp)
  vk_file=$(mktemp)
  if [ -n "${ENV_FILE_B64:-}" ]; then
    printf '%s' "$ENV_FILE_B64" | base64 -d | tr -d '\r' > "$secret_file"
  elif [ -n "${ENV_FILE:-}" ]; then
    printf '%s\n' "$ENV_FILE" | tr -d '\r' > "$secret_file"
  else
    rm -f "$secret_file" "$vk_file"
    return
  fi
  if [ ! -f .env ]; then
    : > .env
    chmod 600 .env
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    line=$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$line" ] && continue
    case "$line" in
      \#*) continue ;;
    esac
    value=$line
    known=yes
    case "$line" in
      VK_TOKEN=*|VK_TOKENS=*)
        value=${line#*=}
        ;;
      *=*)
        value=${line#*=}
        known=no
        ;;
    esac
    old_ifs=$IFS
    IFS=',;'
    for part in $value; do
      token=$(printf '%s' "$part" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^"//;s/"$//')
      [ -z "$token" ] && continue
      if printf '%s' "$token" | grep -Eq '^[0-9]{6,}:[A-Za-z0-9_-]{20,}$'; then
        continue
      fi
      if [ "$known" = yes ] || printf '%s' "$token" | grep -Eq '^vk[12]\.'; then
        printf '%s\n' "$token" >> "$vk_file"
      fi
    done
    IFS=$old_ifs
  done < "$secret_file"
  vk_sorted=$(mktemp)
  awk '!seen[$0]++' "$vk_file" > "$vk_sorted"
  vk_count=$(grep -c . "$vk_sorted" || true)
  echo "Из секрета: сообществ ВК ${vk_count}."
  if [ "$vk_count" -gt 0 ]; then
    first=$(sed -n '1p' "$vk_sorted")
    rest=$(sed -n '2,$p' "$vk_sorted" | paste -sd, -)
    set_env VK_TOKEN "$first"
    set_env VK_TOKENS "$rest"
  elif ! grep -qE '^VK_TOKEN=.+' .env; then
    echo "В секрете нет токена сообщества ВК, и в .env на сервере его тоже нет." >&2
    rm -f "$secret_file" "$vk_file" "$vk_sorted"
    exit 1
  else
    echo "В секрете нет токена ВК. Оставляю VK_TOKEN из .env на сервере."
  fi
  rm -f "$secret_file" "$vk_file" "$vk_sorted"
}

apply_secret_tokens

secret_value() {
  key=$1
  if [ -n "${ENV_FILE_B64:-}" ]; then
    printf '%s' "$ENV_FILE_B64" | base64 -d | tr -d '\r'
  elif [ -n "${ENV_FILE:-}" ]; then
    printf '%s\n' "$ENV_FILE" | tr -d '\r'
  fi | sed -n "s/^[[:space:]]*${key}=//p" | tail -n 1 | sed 's/^"//;s/"$//'
}

# Ключ из секрета ENV_FILE, иначе тот, что уже лежит в .env, иначе новый случайный.
ensure_secret() {
  key=$1
  value=$(secret_value "$key")
  if [ -z "$value" ]; then
    value=$(sed -n "s/^${key}=//p" .env | tail -n 1)
  fi
  if [ -z "$value" ]; then
    value=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
    echo "Сгенерирован ${key}."
  fi
  set_env "$key" "$value"
}

# Ключ, который знает не только сервер: из отдельного секрета GitHub, из ENV_FILE или из .env.
# Код возврата 1, если его нет нигде.
optional_secret() {
  key=$1
  eval "value=\${$key:-}"
  if [ -z "$value" ]; then
    value=$(secret_value "$key")
  fi
  if [ -z "$value" ]; then
    value=$(sed -n "s/^${key}=//p" .env | tail -n 1)
  fi
  if [ -z "$value" ]; then
    return 1
  fi
  set_env "$key" "$value"
}

# То же, но без ключа деплой останавливается.
require_secret() {
  if ! optional_secret "$1"; then
    echo "Добавьте $1 в секреты GitHub или в секрет ENV_FILE." >&2
    exit 1
  fi
}

drop_env() {
  tmp=$(mktemp)
  grep -v "^$1=" .env > "$tmp" || true
  mv "$tmp" .env
  chmod 600 .env
}

ensure_secret CHAT_API_SERVICE_TOKEN
require_secret CHAT_API_APP_TOKEN
require_secret CLOUDFLARE_TUNNEL_TOKEN

# Бот Telegram и мост к chat-engine запускаются, только если для них есть токены.
profiles=proxy
optional_services=""
if optional_secret TELEGRAM_BOT_TOKEN; then
  profiles="${profiles},telegram"
  optional_services="${optional_services} tg-bot"
else
  echo "Нет TELEGRAM_BOT_TOKEN: бот Telegram не запускается."
  docker rm -f vk-tg-bot >/dev/null 2>&1 || true
fi
if optional_secret CHAT_ENGINE_TOKEN; then
  ensure_secret CHAT_API_ENGINE_TOKEN
  profiles="${profiles},engine"
  optional_services="${optional_services} engine-bridge"
else
  echo "Нет CHAT_ENGINE_TOKEN: собеседники из chat-engine не подключаются."
  drop_env CHAT_API_ENGINE_TOKEN
  docker rm -f vk-engine-bridge >/dev/null 2>&1 || true
fi
export COMPOSE_PROFILES="$profiles"
for stale in STUDIO_HOST PAY_HOST API_HOST CORS_ORIGINS PREMIUM_URL PREMIUM_PUBLISH WEB_GATEWAY_PUBLISH WEB_GATEWAY_IMAGE; do
  drop_env "$stale"
done

STUDIO_HOST="${STUDIO_HOST:-studio.chatwithyou.site}"

set_env STUDIO_PUBLIC_URL "https://${STUDIO_HOST}"
set_env CHAT_API_PUBLISH "127.0.0.1:8000"

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  printf '%s' "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
fi

docker compose pull
docker logout >/dev/null 2>&1 || true
docker compose up -d --no-build --remove-orphans db redis
docker compose up -d --no-build --remove-orphans --force-recreate chat-api
# shellcheck disable=SC2086 # список сервисов разделён пробелами
docker compose up -d --no-build --remove-orphans --force-recreate bot $optional_services
docker compose up -d --no-build --remove-orphans studio meta cloudflared
sleep 12
docker logs vk-bot-cloudflared --tail 20 2>&1 | grep -E "Registered tunnel connection|ERR|error" || true
docker logs vk-chat-api --tail 40 2>&1 | grep -E "Схема базы|Application startup|ERROR|Traceback" || true
docker logs vk-bot --tail 80 2>&1 | grep -E "Токенов ВК|VK:|Chat API|События|пропущен|Нет доступа|Токен невалиден|Бот запущен|Ошибка запуска|VK Error|Traceback" || true
for name in vk-tg-bot vk-engine-bridge; do
  if docker inspect "$name" >/dev/null 2>&1; then
    docker logs "$name" --tail 30 2>&1 | grep -E "Бот @|Chat API|Аккаунт|Читаю|Не задан|WARNING|ERROR|Traceback" || true
  fi
done
docker image prune -af
