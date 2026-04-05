export type UserRole = "customer" | "artisan" | "admin";

export interface Profile {
  id: string;
  email: string;
  role: UserRole;
  full_name: string | null;
  shop_name: string | null;
  bio: string | null;
  profile_image_url: string | null;
  is_suspended: boolean;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  artist_id: string;
  name: string;
  description: string;
  category: string;
  price: string;
  stock_quantity: number;
  image_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CartItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface Cart {
  id: string;
  customer_id: string;
  currency: string;
  items: CartItem[];
  subtotal: string;
}

export interface OrderItem {
  id: string;
  product_id: string | null;
  artist_id: string | null;
  product_name: string;
  quantity: number;
  unit_price: string;
}

export interface Order {
  id: string;
  customer_id: string;
  status: string;
  total_amount: string;
  currency: string;
  shipping_address: string;
  payment_transaction_id: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
}

export interface Auction {
  id: string;
  product_id: string;
  seller_id: string;
  highest_bidder_id: string | null;
  status: string;
  starting_price: string;
  min_increment: string;
  current_highest_bid: string;
  start_time: string;
  end_time: string;
  created_at: string;
  updated_at: string;
}

export interface AuctionListResponse {
  items: Auction[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminDashboardSummary {
  users_total: number;
  users_suspended: number;
  products_total: number;
  orders_total: number;
  auctions_total: number;
  revenue_total: string;
}

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_suspended: boolean;
  full_name: string | null;
  shop_name: string | null;
  created_at: string;
}

export interface AdminAuditLog {
  id: string;
  admin_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}
