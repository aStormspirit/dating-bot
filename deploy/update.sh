#!/bin/sh
# Подтягивает коммит, скачивает образы из Docker Hub и перезапускает контейнеры.
# В .env обновляет только адреса оплаты и Studio.
set -eu

cd "$(dirname "$0")/.."

if [ -z "${GIT_SHA:-}" ]; then
  echo "Не задан GIT_SHA." >&2
  exit 1
fi
if [ -z "${BOT_IMAGE:-}" ] || [ -z "${PREMIUM_IMAGE:-}" ] || [ -z "${CHAT_API_IMAGE:-}" ]; then
  echo "Не заданы BOT_IMAGE, CHAT_API_IMAGE и PREMIUM_IMAGE." >&2
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

apply_secret_tokens() {
  secret_file=$(mktemp)
  vk_file=$(mktemp)
  tg_file=$(mktemp)
  if [ -n "${ENV_FILE_B64:-}" ]; then
    printf '%s' "$ENV_FILE_B64" | base64 -d | tr -d '\r' > "$secret_file"
  elif [ -n "${ENV_FILE:-}" ]; then
    printf '%s\n' "$ENV_FILE" | tr -d '\r' > "$secret_file"
  else
    rm -f "$secret_file" "$vk_file" "$tg_file"
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
      VK_TOKEN=*|VK_TOKENS=*|TG_TOKEN=*|TG_TOKENS=*)
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
        printf '%s\n' "$token" >> "$tg_file"
      elif [ "$known" = yes ] || printf '%s' "$token" | grep -Eq '^vk[12]\.'; then
        printf '%s\n' "$token" >> "$vk_file"
      fi
    done
    IFS=$old_ifs
  done < "$secret_file"
  vk_sorted=$(mktemp)
  tg_sorted=$(mktemp)
  awk '!seen[$0]++' "$vk_file" > "$vk_sorted"
  awk '!seen[$0]++' "$tg_file" > "$tg_sorted"
  vk_count=$(grep -c . "$vk_sorted" || true)
  tg_count=$(grep -c . "$tg_sorted" || true)
  echo "Из секрета: сообществ ВК ${vk_count}, ботов Telegram ${tg_count}."
  if [ "$vk_count" -gt 0 ]; then
    first=$(sed -n '1p' "$vk_sorted")
    rest=$(sed -n '2,$p' "$vk_sorted" | paste -sd, -)
    set_env VK_TOKEN "$first"
    set_env VK_TOKENS "$rest"
  elif ! grep -qE '^VK_TOKEN=.+' .env; then
    echo "В секрете нет токена сообщества ВК, и в .env на сервере его тоже нет." >&2
    rm -f "$secret_file" "$vk_file" "$tg_file" "$vk_sorted" "$tg_sorted"
    exit 1
  else
    echo "В секрете нет токена ВК. Оставляю VK_TOKEN из .env на сервере."
  fi
  if [ "$tg_count" -gt 0 ]; then
    first=$(sed -n '1p' "$tg_sorted")
    rest=$(sed -n '2,$p' "$tg_sorted" | paste -sd, -)
    set_env TG_TOKEN "$first"
    set_env TG_TOKENS "$rest"
  fi
  rm -f "$secret_file" "$vk_file" "$tg_file" "$vk_sorted" "$tg_sorted"
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

# Ключ, который знает не только сервер: из секрета ENV_FILE или из .env. Без него деплой останавливается.
require_secret() {
  key=$1
  value=$(secret_value "$key")
  if [ -z "$value" ]; then
    value=$(sed -n "s/^${key}=//p" .env | tail -n 1)
  fi
  if [ -z "$value" ]; then
    echo "Добавьте ${key} в секрет ENV_FILE." >&2
    exit 1
  fi
  set_env "$key" "$value"
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
for stale in GUEST_JWT_SECRET CORS_ORIGINS STUDIO_HOST API_HOST; do
  drop_env "$stale"
done

PAY_HOST="${PAY_HOST:-pay.chatwithyou.site}"
STUDIO_HOST="${STUDIO_HOST:-studio.chatwithyou.site}"

set_env PAY_HOST "$PAY_HOST"
set_env PREMIUM_URL "https://vk.cc/d2HjY8"
set_env STUDIO_PUBLIC_URL "https://${STUDIO_HOST}"
set_env PREMIUM_PUBLISH "127.0.0.1:8080"
set_env CHAT_API_PUBLISH "127.0.0.1:8000"

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
docker compose --profile proxy up -d --no-build --remove-orphans db redis
docker compose --profile proxy up -d --no-build --remove-orphans --force-recreate chat-api premium
docker compose --profile proxy up -d --no-build --remove-orphans --force-recreate bot
docker compose --profile proxy up -d --no-build caddy cloudflared
docker restart vk-bot-caddy
sleep 12
docker logs vk-bot-cloudflared --tail 20 2>&1 | grep -E "Registered tunnel connection|ERR|error" || true
docker logs vk-chat-api --tail 40 2>&1 | grep -E "Схема базы|Application startup|ERROR|Traceback" || true
docker logs vk-bot --tail 80 2>&1 | grep -E "Токенов ВК|VK:|Telegram:|Chat API|События|пропущен|OK:|Нет права|Нет доступа|Токен невалиден|Бот запущен|Ошибка запуска|VK Error|Traceback" || true
sleep 8
docker logs vk-bot-caddy --tail 20 || true
docker image prune -af
