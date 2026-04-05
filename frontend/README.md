# Artisan Marketplace Frontend

React + TypeScript client integrated with the existing FastAPI backend.

## Implemented UI modules

- Supabase password login and token storage
- Profile-aware role display (customer, artisan, admin)
- Product list and cart operations
- Checkout flow and order history
- Auctions listing, bidding, manual close, and live WebSocket event feed
- Admin dashboard, user suspension toggle, and audit log viewing

## Setup

1. Copy env values:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` with your Supabase values:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`

3. Ensure backend CORS allows Vite origin (`http://127.0.0.1:5173`).

## Install and run

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Demo accounts

All seeded users use password `DemoPass123!`:

- `customer@artisan-demo.local`
- `artisan@artisan-demo.local`
- `admin@artisan-demo.local`
