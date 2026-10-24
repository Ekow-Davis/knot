# Knot

Project Wonder Woman. A private question game for two, built as an installable PWA.
See `docs/ARCHITECTURE.md` for how it all fits together.

```
knot/
├── api/            FastAPI + SQLAlchemy + Alembic
├── web/            Vue 3 + TypeScript + Vite PWA
├── docs/           Architecture
├── Dockerfile      One image: builds web, serves it + the API
└── railway.json
```

## Run it locally

You need Python 3.12+, Node 20+ and Postgres 16.

**1. Database**

```bash
createuser knot -P          # password: knot
createdb knot -O knot
```

**2. API** (terminal 1)

```bash
cd api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # fill SECRET_KEY, BANK_KEY, OWNER_EMAIL
alembic upgrade head
pytest                                               # needs the knot_test database, see below
uvicorn app.main:app --reload --port 8000
```

**Tests** run against their own database, so your dev data is never touched. Create it once in psql:

```sql
CREATE DATABASE knot_test OWNER knot;
```

**Questions:** the game needs a question bank. For testing, import the throwaway test pack (42 placeholder
questions, not part of the real bank). `BANK_KEY` must be set in `api/.env` first:

```bash
python -m app.tools.import_pack sample/test-000.json
# later, before the real bank goes in:
python -m app.tools.import_pack --remove test-000
```

The real bank arrives as encrypted `.pack` files and imports the same way. The tool only ever prints counts.

**Sign-in codes in development:** if `RESEND_API_KEY` is empty, codes are printed in the uvicorn
terminal (`DEV sign-in code for …`) instead of emailed. With the key set, real emails go out, which
needs `MAIL_FROM` on a domain you've verified in Resend.

**3. Web** (terminal 2)

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173 to see the landing page. To see the installed-app flow (the door), use
http://localhost:5173/?app=1. Add `?app=0` to switch back. The door shows **Connected** when the
API and database are reachable.

**To test on your iPhone:** run `npm run dev -- --host` and open the shown network address in Safari.
The phone and laptop must be on the same Wi-Fi. A real install (Add to Home Screen, push) needs HTTPS,
so that part waits for the Railway deploy.

## Deploy to Railway

1. Create a new project from the repo. Railway picks up `railway.json` and builds the `Dockerfile`.
2. Add the **Postgres** plugin. Railway sets `DATABASE_URL` for you.
3. In Variables, set `ENV=production`, `SECRET_KEY`, `BANK_KEY`, `OWNER_EMAIL`, `RESEND_API_KEY`,
   `MAIL_FROM` and `APP_ORIGIN=https://ww.forgottenguardian.com`.
4. Under Settings → Networking, add the custom domain `ww.forgottenguardian.com`. Then add the
   CNAME it shows you in Namecheap.

Migrations run automatically on each deploy.

## Your assets to drop in later

| File | Size | Notes |
|---|---|---|
| `web/public/icons/apple-touch-icon.png` | 180×180 | iPhone home screen. No transparency (iOS fills it black). |
| `web/public/icons/icon-192.png` | 192×192 | |
| `web/public/icons/icon-512.png` | 512×512 | |
| `web/public/icons/icon-512-maskable.png` | 512×512 | Keep the emblem inside the middle 80%. |
| `web/public/og.png` | 1200×630 | Link preview card: blue background, emblem, caption. |

The current files are plain blue placeholders.

## Changing the schema

`api/migrations/versions/0001_initial.sql` is the schema, and `api/app/models.py` mirrors it.
For later changes, edit `models.py` and run `alembic revision --autogenerate -m "what changed"`.
Then `pytest` confirms the two still agree.
