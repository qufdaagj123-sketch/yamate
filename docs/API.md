# Kittylol API

## Loader

`GET /files/v4/loader/<token>.lua`

- Browser-style requests receive the Kittylol loader page.
- Non-browser requests receive the script source.
- Invalid/disabled/expired tokens are rejected.
- Loader requests are rate limited.

## Key validation

`GET /api/v1/key/<token>`

Example response:

```json
{
  "valid": true,
  "token": "example",
  "script": "Demo",
  "expires_at": null
}
```

## Health

`GET /health`

No authentication required.

## Dashboard stats

`GET /api/v1/stats`

Requires an authenticated admin session.
