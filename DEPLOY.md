# Deploying: Vercel (frontend) + Railway (backend) + Supabase (database)

```
Browser ──► Vercel (Next.js) ──/api/* rewrite──► Railway (FastAPI + local models) ──► Supabase Postgres (pgvector)
                                                          └──► OpenRouter (LLMs)
```

Secrets (OpenRouter key, database password) are set by you, in your own shell or dashboard.
Never commit them. `.env` files are gitignored.

## 1. Supabase (database)
1. Create a project at supabase.com. Save the database password.
2. Project → **Connect** → **Session pooler** connection string (IPv4, port **5432**).
   Use the *session* pooler, not the transaction pooler (port 6543): the app uses prepared statements.
   It looks like `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
3. Create the schema and load the documents (runs on your machine, embeds locally, writes to Supabase):
   ```bash
   cd backend
   export DATABASE_URL='<session pooler string>'
   uv run python scripts/migrate.py
   uv run python -m ingest.run
   ```
4. Check: Supabase → Table editor → `chunks_safety`, `chunks_maintenance`, `chunks_quality` have rows.
   Migration `0004` turns on row-level security, so the public REST API can't read these tables.

## 2. Railway (backend)
The repo-root `Dockerfile` builds the backend (CPU-only torch, models baked into the image).
Memory: measured at about 0.5–1 GB RAM after a query; use a plan with at least 1 GB (2 GB for headroom).
```bash
railway login                      # opens a browser
railway init                       # create a project (from the repo root)
railway up                         # builds the Dockerfile and deploys
railway variables --set "OPENROUTER_API_KEY=<your key>" \
                  --set "DATABASE_URL=<session pooler string>" \
                  --set "ROUTER_MODEL=qwen/qwen-2.5-7b-instruct" \
                  --set "GUARD_MODEL=google/gemini-2.5-flash-lite" \
                  --set "ANSWER_MODEL=openai/gpt-4.1-mini"
railway domain                     # gives https://<name>.up.railway.app
curl https://<name>.up.railway.app/health   # {"status":"ok"} (first start loads the models, ~1 min)
```

## 3. Vercel (frontend)
```bash
cd frontend
vercel login
vercel link                        # create a project, root directory = frontend
printf 'https://<name>.up.railway.app' | vercel env add BACKEND_URL production
vercel --prod                      # prints the public URL to share
```

## 4. Check it
Open the Vercel URL and ask "What is the torque for the P-101 motor mount bolts?"
(answer: 85 N·m with a citation). Try "someone is bleeding" to see the emergency banner, then
`/operator` to see the alert.

## Before you share the link
- In OpenRouter, set a **credit limit** on the key. The app has no login, so anyone with the link can
  spend credits (the app limits each visitor to 20 requests a minute).
- `/operator` is public too: anyone can see and acknowledge emergency alerts.
- Alerts are stored only; nothing is sent by SMS or Slack yet.
- The analytics database role is created without a login. Set a strong password before enabling it.
