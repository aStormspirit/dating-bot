#!/bin/sh
# Подтягивает коммит, скачивает образы из Docker Hub и перезапускает контейнеры.
# .env не трогает и ничего на сервере не собирает.
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

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
  printf '%s' "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
fi

docker compose pull
docker logout >/dev/null 2>&1 || true
docker compose up -d --no-build --remove-orphans
docker image prune -af
