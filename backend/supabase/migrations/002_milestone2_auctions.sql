-- Milestone 2 schema for auctions and live bidding

create table if not exists public.auctions (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  seller_id uuid not null references public.profiles(id) on delete cascade,
  highest_bidder_id uuid references public.profiles(id) on delete set null,

  status text not null default 'scheduled',

  starting_price numeric(10,2) not null,
  min_increment numeric(10,2) not null default 1.00,
  current_highest_bid numeric(10,2) not null,

  start_time timestamptz not null default now(),
  end_time timestamptz not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_auctions_status on public.auctions(status);
create index if not exists idx_auctions_end_time on public.auctions(end_time);
create index if not exists idx_auctions_start_time on public.auctions(start_time);
create index if not exists idx_auctions_seller on public.auctions(seller_id);

create table if not exists public.bids (
  id uuid primary key default gen_random_uuid(),
  auction_id uuid not null references public.auctions(id) on delete cascade,
  bidder_id uuid not null references public.profiles(id) on delete cascade,

  bid_amount numeric(10,2) not null,
  status text not null default 'active',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_bids_auction_id on public.bids(auction_id);
create index if not exists idx_bids_bidder_id on public.bids(bidder_id);
create index if not exists idx_bids_status on public.bids(status);
create index if not exists idx_bids_auction_created on public.bids(auction_id, created_at desc);

alter table public.auctions enable row level security;
alter table public.bids enable row level security;

drop policy if exists "auctions_authenticated_all" on public.auctions;
create policy "auctions_authenticated_all" on public.auctions for all to authenticated using (true) with check (true);

drop policy if exists "bids_authenticated_all" on public.bids;
create policy "bids_authenticated_all" on public.bids for all to authenticated using (true) with check (true);
