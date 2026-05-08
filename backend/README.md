# Souq Al Artisan Backend

Async FastAPI backend using Supabase Postgres, Supabase Auth, and Supabase Storage.

## Quick start

1. Copy environment values:
   - Create `backend/.env` from `backend/.env.example`
   - Fill in your real Supabase values
2. Install dependencies:
   - `uv sync`
3. Run API:
   - `uv run uvicorn app.main:app --reload`

If you run the frontend on Vite (`http://127.0.0.1:5173`), make sure your `CORS_ORIGINS` includes that origin.

## Auth flow

- The backend accepts Supabase access tokens from `Authorization: Bearer <token>`.
- On first authenticated request, a local profile row is auto-created.

## Fake payment simulation

Use card tokens to force outcomes:

- `success_xxx` => success
- `decline_xxx` => decline
- `timeout_xxx` => timeout
- any other token => deterministic 90/8/2 distribution

## Implemented Milestone 1 modules

- Profile bootstrap and role update
- Product create/list/detail/update/archive
- Cart add/update/remove/view
- Checkout and order history

## Implemented Milestone 2 modules

- Auction creation/listing/detail
- Live bidding endpoint with transactional validation
- Auction live updates over WebSocket
- Manual and automatic auction closing
- Winner pending-order generation on auction close

## Implemented Milestone 3 administration layer

- Admin dashboard summary endpoint
- Admin user management (role updates, suspension)
- Admin moderation endpoints for products, orders, and auctions
- Admin audit log table and read endpoint

## API docs

- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Testing

This backend now includes all three testing layers:

- Unit tests: small isolated checks for business logic and auth guards
- Integration tests: API-level tests that exercise route wiring, dependency overrides, and response serialization
- Performance tests: lightweight latency checks for a public endpoint

Install test dependencies:

```powershell
uv sync --group dev
```

Run the full backend test suite:

```powershell
uv run pytest
```

Run specific layers:

```powershell
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m performance
```

### Locust stress tests

For real load testing against a running backend, this project also includes two Locust scenarios in
`tests/performance/locustfile.py`:

- `BrowseAndSearchUser`: heavy public browsing and product searching
- `SimultaneousBidUser`: many authenticated users bidding on the same auction

Install the dev tools first:

```powershell
uv sync --group dev
```

Start the backend in a separate terminal:

```powershell
uv run uvicorn app.main:app --reload
```

Test 1: 100 users browsing and searching products

```powershell
uv run locust -f tests/performance/locustfile.py BrowseAndSearchUser --host http://127.0.0.1:8000 --users 100 --spawn-rate 20 --run-time 2m --headless
```

Test 2: 50 users bidding on the same auction

Set the target auction id and a comma-separated list of bidder access tokens first:

```powershell
$env:LOCUST_AUCTION_ID="<auction-id>"
$env:LOCUST_BIDDER_TOKENS="<token-1>,<token-2>,<token-3>"
```

Then run:

```powershell
uv run locust -f tests/performance/locustfile.py SimultaneousBidUser --host http://127.0.0.1:8000 --users 50 --spawn-rate 10 --run-time 2m --headless
```

Notes:

- The pytest performance test is an in-memory latency check.
- The Locust scenarios are real HTTP load tests against your running API.
- For the bid load test, include enough customer tokens to spread requests across distinct users.

## Seed demo users and data

Run once from `backend`:

```powershell
python -m app.scripts.seed_demo
```

This creates (or reuses) three Supabase Auth users and matching profile rows:

- admin: `admin@artisan-demo.local`
- artisan: `artisan@artisan-demo.local`
- customer: `customer@artisan-demo.local`
- password for all: `DemoPass123!`

It also inserts 3 sample products for the artisan if none exist.

## Mass seed catalog and popularity data

Run from `backend` when you want a larger demo dataset:

```powershell
python -m app.scripts.seed_mass
```

This creates or reuses demo auth users under `@souq-demo.local`, then resets only seed-owned carts,
orders, and products before recreating:

- 20 artisans
- 40 customers
- 120 products with curated external image URLs
- 220 paid/processing/shipped/delivered orders to drive popularity rankings
- matching admin activity logs for product creation, payment success, and order creation

All mass-seeded users use password `DemoPass123!`.

## Quick manual test flow

1. Start backend:

```powershell
python -m uvicorn app.main:app --reload
```

2. Get a Supabase access token for one demo user:

```powershell
$body = @{ email = "artisan@artisan-demo.local"; password = "DemoPass123!" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
   -Uri "https://<your-project-ref>.supabase.co/auth/v1/token?grant_type=password" `
   -Headers @{ apikey = "<SUPABASE_ANON_KEY>"; "Content-Type" = "application/json" } `
   -Body $body
```

3. Copy `access_token` from response.
4. Open `/docs`, click Authorize, paste `Bearer <access_token>`.
5. Test endpoints in order:
    - `GET /api/v1/auth/me`
    - `POST /api/v1/products` (artisan/admin)
    - `GET /api/v1/products`
    - `POST /api/v1/cart/items` (customer token)
    - `POST /api/v1/orders/checkout` with `card_token: success_demo`

## Milestone 2 manual test flow (auctions + live bidding)

1. Get an artisan token and create an auction:

```json
POST /api/v1/auctions
{
   "product_id": "<artisan-owned-product-id>",
   "starting_price": 25,
   "min_increment": 1,
   "end_time": "2030-01-01T12:00:00Z"
}
```

2. Open live updates in a WebSocket client (two tabs recommended):

```text
ws://127.0.0.1:8000/api/v1/auctions/ws/live/<auction_id>?token=<supabase_access_token>
```

3. Place bids as customer users:

```json
POST /api/v1/auctions/<auction_id>/bids
{
   "bid_amount": 30
}
```

4. Verify live events in WebSocket clients:
    - `bid_placed`
    - `bid_outbid`
    - `auction_closed`

5. Close auction manually as artisan/admin:

```text
POST /api/v1/auctions/<auction_id>/close
```

6. Verify winner order exists:
    - `GET /api/v1/orders` with winner token

## Milestone 3 admin test flow

1. Apply latest migration in Supabase SQL editor:

```sql
-- run file: supabase/migrations/003_milestone3_admin_layer.sql
```

2. Login as seeded admin (`admin@artisan-demo.local`) and authorize in `/docs`.

3. Test admin endpoints:
   - `GET /api/v1/admin/dashboard`
   - `GET /api/v1/admin/users`
   - `PATCH /api/v1/admin/users/{user_id}/role`
   - `PATCH /api/v1/admin/users/{user_id}/suspension`
   - `GET /api/v1/admin/products`
   - `PATCH /api/v1/admin/products/{product_id}`
   - `GET /api/v1/admin/orders`
   - `PATCH /api/v1/admin/orders/{order_id}/status`
   - `GET /api/v1/admin/auctions`
   - `PATCH /api/v1/admin/auctions/{auction_id}/status`
   - `GET /api/v1/admin/audit-logs`

## Troubleshooting

### Startup fails with `socket.gaierror: [Errno 11001] getaddrinfo failed`

If you are using `db.<project-ref>.supabase.co`, your network may only get an IPv6 record for that host.
On some Windows/DNS setups, asyncpg cannot resolve or connect in that case.

Use the Supabase **Connection Pooler** URL from the Supabase dashboard instead:

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?ssl=require
```

Get the exact value from Supabase:
- Dashboard -> Project Settings -> Database -> Connection string -> Transaction pooler

Then restart uvicorn.

### Startup shows `DuplicatePreparedStatementError` with Supabase pooler

If you use the Supabase Transaction Pooler host (`*.pooler.supabase.com:6543`),
PgBouncer is in front of Postgres and asyncpg prepared statements can conflict.

This backend is configured to handle that by:
- disabling asyncpg statement cache
- using `NullPool` on pooler URLs

If you still see the error, fully stop all running uvicorn processes and start again.
