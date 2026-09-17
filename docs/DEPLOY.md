# Render deployment

Use PostgreSQL for production persistence.

Required environment variables:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SESSION_SECRET`
- `DATABASE_URL`
- `HOMEPAGE_URL`
- `COOKIE_SECURE=true`

Do not commit credentials.

After the service is deployed, Render normally gives a host such as:

`https://api-kittylol.onrender.com`

The loader URL is:

`https://api-kittylol.onrender.com/files/v4/loader/<token>.lua`

If you own a domain, attach `api.kittylol.com` as a custom domain in Render.
