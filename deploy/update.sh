#!/bin/sh
# Обновляет код на сервере и пересобирает контейнеры. .env не трогает.
set -eu

cd "$(dirname "$0")/.."

git fetch origin master
git checkout master
git reset --hard origin/master

if [ ! -f .env ]; then
  echo "На сервере нет .env. Создайте его из .env.example и заполните токены." >&2
  exit 1
fi

docker compose up -d --build --remove-orphans
docker image prune -f
