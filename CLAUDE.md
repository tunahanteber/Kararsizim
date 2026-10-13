# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/KARARSIZIM.md` (Turkish) is the full spec: data model, business rules, design system, Vercel/Supabase setup, and the phase roadmap (Faz 0–5). Read it before changing anything. **Implement only the phase the user asks for; don't start the next one.** Current state: Faz 0 (skeleton) is done; Faz 1+ not started.

## Commands

Use the project venv (Python 3.14 here, spec says 3.12 — user chose to stay on 3.14; `.python-version` says `3.14`).

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
.venv/bin/python manage.py test                      # all tests
.venv/bin/python manage.py test polls.tests.TestX.test_y   # single test
.venv/bin/python manage.py check --deploy
```

Settings require `DJANGO_SECRET_KEY` (loaded from a git-ignored `.env`; see `.env.example`). With `DJANGO_DEBUG=1` and no `DATABASE_URL`, SQLite is used.

## Architecture notes

- Django 5.2, server-rendered templates, plain HTML/CSS/vanilla JS — no npm, no build step, no JS/CSS frameworks. Don't add dependencies beyond `requirements.txt` without asking.
- `accounts.User` is a custom `AbstractUser` (`AUTH_USER_MODEL`): login by **email**, public identity is lowercase `username` (validated by `validate_username`, reserved names, case-insensitive unique constraint). Email must never be rendered anywhere.
- `polls` app holds polls/options/votes. Business logic (voting, results, verdict, code generation) belongs in `polls/services.py`; keep views thin.
- Deliberate deviation from the spec: in `config/settings.py`, when `DATABASE_URL` is unset and `DEBUG` is off, `DATABASES` uses the `dummy` backend (no silent SQLite fallback on Vercel; `collectstatic` still works at build).
- The `DATABASE_URL` branch in settings is tuned for Supabase's transaction pooler on serverless (`conn_max_age=0`, `prepare_threshold=None`, `DISABLE_SERVER_SIDE_CURSORS`). Do not change these (spec rule, Bölüm 9.4/13).
- Migrations are never run during the Vercel build; they're applied locally against the Supabase session pooler (port 5432).
- Code and identifiers in English; all user-facing text in Turkish.
