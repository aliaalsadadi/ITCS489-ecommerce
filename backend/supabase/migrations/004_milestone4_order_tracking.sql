-- Milestone 4 order tracking + shipping metadata

alter table public.orders
  add column if not exists tracking_number text,
  add column if not exists shipping_carrier text,
  add column if not exists shipping_method text,
  add column if not exists estimated_delivery_at timestamptz;

create index if not exists idx_orders_tracking_number on public.orders(tracking_number);
