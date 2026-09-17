# Kittylol — Full Render Project

A custom script-management platform with a Kittylol-branded dashboard, script manager,
key/token manager, users, HWID records, logs, API documentation, settings, browser
loader page, and Render deployment configuration.

This project is intentionally an original UI and branding rather than a pixel-for-pixel
copy of another service.

## Features

- Responsive dark dashboard
- Overview analytics
- Script upload/paste/version/status management
- Per-script loader tokens
- Token expiry, revoke, enable/disable and delete
- Users and HWID management
- Request logs
- API documentation
- Browser-friendly loader page
- Raw Lua/Luau response for non-browser clients
- Admin session authentication
- Security headers
- Basic request rate limiting
- PostgreSQL support
- SQLite development mode
- Render configuration
- Health endpoint

## Loader

After deployment:

`https://YOUR-SERVICE.onrender.com/files/v4/loader/<token>.lua`

For a custom domain:

`https://api.kittylol.com/files/v4/loader/<token>.lua`

A browser request renders the Kittylol loader page. A non-browser client receives
the script source.

## Render

Recommended production setup:

1. Create a Render Web Service from this repository.
2. Build command:
   `pip install -r requirements.txt`
3. Start command:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Configure `DATABASE_URL` with PostgreSQL.
5. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SESSION_SECRET`, and `HOMEPAGE_URL`.
6. Set `COOKIE_SECURE=true` when serving over HTTPS.

The free Render filesystem is ephemeral, so PostgreSQL should be used for persistent
production data.

## Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me
export SESSION_SECRET=replace-me
uvicorn app.main:app --reload
```

Open `/login`.
