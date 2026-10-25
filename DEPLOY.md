# Deploying the all-in-one container

One Docker image holds everything: Next.js frontend, FastAPI backend and Postgres + pgvector with the
documents already loaded. One public port (`$PORT`, default 7860). The only secret it needs is
`OPENROUTER_API_KEY`. Memory: about 0.7 GB in use, so pick a host with at least 1 GB (2 GB for headroom).

```
Browser ──► :7860 Next.js ──/api/*──► 127.0.0.1:8000 FastAPI ──► 127.0.0.1:5432 Postgres (inside the container)
                                              └──► OpenRouter
```

Try it locally first (needs Docker):
```bash
docker build -t plantbot .
docker run --rm -p 7860:7860 -e OPENROUTER_API_KEY=<your key> plantbot   # then open http://localhost:7860
```

## Option A: Hugging Face Space (free if your account allows Docker Spaces)
1. Create an account at huggingface.co (you do this yourself) and check that you can create a **Docker** Space.
2. `hf auth login` (prints a URL and code; open it and sign in).
3. Create the Space and push it:
   ```bash
   hf repo create <you>/plant-docs-assistant --repo-type space --space-sdk docker
   scripts/prepare_space.sh /tmp/plant-space          # copies the files the Space needs, plus its README
   cd /tmp/plant-space && git init -q && git add -A && git commit -qm "Plant Docs Assistant"
   git remote add space https://huggingface.co/spaces/<you>/plant-docs-assistant && git push space HEAD:main
   ```
4. In the Space → **Settings → Variables and secrets**, add the secret `OPENROUTER_API_KEY`.
5. The Space builds (about 10 minutes) and then serves at `https://<you>-plant-docs-assistant.hf.space`.
Free Spaces sleep when idle, and chat history and alerts reset on restart.

## Option B: Railway (about $5/month after the trial; needs a card)
```bash
railway login && railway init
railway variables --set "OPENROUTER_API_KEY=<your key>"
railway up            # uses ./Dockerfile and railway.json (health check: /api/health)
railway domain        # public URL
```
To keep chat history and alerts across restarts, attach a volume and set `APP_PGDATA` to a folder inside it.

## Settings (all optional)
`ROUTER_MODEL`, `GUARD_MODEL`, `ANSWER_MODEL` (defaults are in the Dockerfile), `APP_PGDATA`.

## Before you share the link
- In OpenRouter, set a **credit limit** on the key. There is no login, so anyone with the link can spend credits
  (each visitor is limited to 20 requests a minute).
- `/operator` is public: anyone can see and acknowledge emergency alerts. Alerts are stored only; nothing is sent
  by SMS or Slack.
- The 3-service setup (Vercel + Railway + Supabase) is described in `DEPLOY-3-SERVICE.md`.
