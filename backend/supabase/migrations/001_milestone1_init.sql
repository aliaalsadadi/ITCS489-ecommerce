-- Milestone 1 schema for Supabase Postgres (public schema)

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key,
  email text not null unique,
  role text not null default 'customer',
  full_name text,
  shop_name text,
  bio text,
  profile_image_url text,
  wallet_balance numeric(12,2) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  artist_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  description text not null,
  category text not null,
  price numeric(10,2) not null,
  stock_quantity integer not null default 0,
  image_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_products_category on public.products(category);
create index if not exists idx_products_active on public.products(is_active);

create table if not exists public.carts (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null unique references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cart_items (
  id uuid primary key default gen_random_uuid(),
  cart_id uuid not null references public.carts(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  quantity integer not null,
  unit_price numeric(10,2) not null,
  currency text not null default 'USD',
  constraint uq_cart_product unique (cart_id, product_id)
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.profiles(id) on delete cascade,
  status text not null default 'paid',
  total_amount numeric(12,2) not null default 0,
  currency text not null default 'USD',
  shipping_address text not null,
  payment_transaction_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_orders_customer_id on public.orders(customer_id);
create index if not exists idx_orders_status on public.orders(status);

create table if not exists public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  artist_id uuid references public.profiles(id) on delete set null,
  product_name text not null,
  quantity integer not null,
  unit_price numeric(10,2) not null
);

-- Optional relaxed RLS setup for MVP speed. Keep disabled if you query with service role.
alter table public.profiles enable row level security;
alter table public.products enable row level security;
alter table public.carts enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;

-- Relaxed policies (authenticated read/write) for university MVP.
drop policy if exists "profiles_authenticated_all" on public.profiles;
create policy "profiles_authenticated_all" on public.profiles for all to authenticated using (true) with check (true);

drop policy if exists "products_authenticated_all" on public.products;
create policy "products_authenticated_all" on public.products for all to authenticated using (true) with check (true);

drop policy if exists "carts_authenticated_all" on public.carts;
create policy "carts_authenticated_all" on public.carts for all to authenticated using (true) with check (true);

drop policy if exists "cart_items_authenticated_all" on public.cart_items;
create policy "cart_items_authenticated_all" on public.cart_items for all to authenticated using (true) with check (true);

drop policy if exists "orders_authenticated_all" on public.orders;
create policy "orders_authenticated_all" on public.orders for all to authenticated using (true) with check (true);

drop policy if exists "order_items_authenticated_all" on public.order_items;
create policy "order_items_authenticated_all" on public.order_items for all to authenticated using (true) with check (true);
