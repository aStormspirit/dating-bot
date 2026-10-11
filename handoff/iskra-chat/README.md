# Iskra chat handoff (apply on a machine with write access to aStormspirit/iskra)

Cloud agent could not push to iskra (403). Apply on local machine:

```bash
git clone https://github.com/aStormspirit/iskra.git
cd iskra
git checkout -b cursor/chat-page-9fe7
git am path/to/0001-*.patch path/to/0002-*.patch
# or: git pull path/to/chat-page.bundle HEAD
npm ci && NEXT_PUBLIC_CHAT_API_URL=https://pay.chatwithyou.site NEXT_PUBLIC_SITE_URL=https://chatwithyou.site npm run build
git push -u origin cursor/chat-page-9fe7
gh pr create --base main --head cursor/chat-page-9fe7 --title "feat: add /chat page wired to dating-bot web gateway" --body "Browser chat at /chat/ using NEXT_PUBLIC_CHAT_API_URL=https://pay.chatwithyou.site (Caddy → web-gateway)."
```

Prod API base: `https://pay.chatwithyou.site` (not api.* — that host is behind Cloudflare Access).
