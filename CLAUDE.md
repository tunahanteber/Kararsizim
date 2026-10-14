# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/KARARSIZIM.md` (Turkish) is the full spec: data model, business rules, design system, Vercel/Supabase setup, and the phase roadmap (Faz 0–5). Read it before changing anything. **Implement only the phase the user asks for; don't start the next one.** Current state: Faz 0, 2, 3, 4 done; Faz 5 done except password reset and Turnstile (need external services). Faz 1 is partly done (Supabase project, RLS migrations, `vercel.json`, `/saglik/` exist); the Vercel project/env setup and Data API toggle are still pending (user deferred them).

## Commands

Use the project venv (Python 3.14 here, spec says 3.12 — user chose to stay on 3.14; `.python-version` says `3.14`).

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
.venv/bin/python manage.py test                      # all tests
.venv/bin/python manage.py test polls.tests.TestX.test_y   # single test
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py seed_demo [--reset]       # demo users (no usable password), polls and votes
```

Settings require `DJANGO_SECRET_KEY` (loaded from a git-ignored `.env`; see `.env.example`). With `DJANGO_DEBUG=1` and no `DATABASE_URL`, SQLite is used.

## Architecture notes

- Django 5.2, server-rendered templates, plain HTML/CSS/vanilla JS — no npm, no build step, no JS/CSS frameworks. Don't add dependencies beyond `requirements.txt` without asking.
- `accounts.User` is a custom `AbstractUser` (`AUTH_USER_MODEL`): login by **email or username** (`LoginForm` maps a username to its email; the error message never reveals which exists), public identity is lowercase `username` (validated by `validate_username`, reserved names, case-insensitive unique constraint). Email must never be rendered anywhere.
- `polls` app holds polls/options/votes. Business logic (voting, results, verdict, code generation) belongs in `polls/services.py`; keep views thin.
- Deliberate deviation from the spec: in `config/settings.py`, when `DATABASE_URL` is unset and `DEBUG` is off, `DATABASES` uses the `dummy` backend (no silent SQLite fallback on Vercel; `collectstatic` still works at build).
- The `DATABASE_URL` branch in settings is tuned for Supabase's transaction pooler on serverless (`conn_max_age=0`, `prepare_threshold=None`, `DISABLE_SERVER_SIDE_CURSORS`). Do not change these (spec rule, Bölüm 9.4/13).
- Migrations are never run during the Vercel build; they're applied locally against the Supabase session pooler (port 5432).
- Code and identifiers in English; all user-facing text in Turkish.
- `.env` points at the real Supabase DB (session pooler); `manage.py test` is forced onto SQLite in `settings.py`. To try things against a throwaway DB, run `DATABASE_URL= manage.py runserver` (with `DJANGO_DEBUG=1`) and delete `db.sqlite3` afterwards.
- Every migration that adds tables must be followed by a migration calling `config.rls.enable_rls` (see `polls/migrations/0002_enable_rls.py`).
- Vote results are only computed/rendered for users allowed to see them (`services.can_see_results`); the vote form posts the option `position` (0-4), never internal IDs. Voting works without JS; `static/js/app.js` upgrades it to fetch+JSON and falls back to a normal form post.
- CSS/JS URLs carry `?v=<mtime>` (`config/context_processors.py`) so browsers don't serve stale assets.
- Rate limiting (`polls/ratelimit.py`, limits in `settings.RATE_LIMITS`) uses Django's `DatabaseCache` (`django_cache` table, created by `polls` migration 0004 + RLS) — in-memory caches don't work on serverless. Tests run against SQLite, so the cache table exists there too.
- Closed polls (`Poll.closed_at`) reject votes (409/redirect) and show results to everyone; reports (`polls.Report`) are visible only in Django admin. Dark mode is CSS-only via `prefers-color-scheme` (tokens in `static/css/app.css`; contrast ratios were computed for AA).
