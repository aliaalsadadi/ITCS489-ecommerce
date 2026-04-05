import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiRequest, signInWithPassword, wsUrl } from "./api";
import type {
  AdminAuditLog,
  AdminDashboardSummary,
  AdminUser,
  Auction,
  AuctionListResponse,
  Cart,
  Order,
  Product,
  Profile,
  UserRole,
} from "./types";
import "./styles.css";

type TabKey = "store" | "auctions" | "admin";

const TOKEN_KEY = "artisan_access_token";

function parseErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatMoney(value: string | number): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numeric)) {
    return "0.00";
  }
  return numeric.toFixed(2);
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}

function roleLabel(role: UserRole): string {
  if (role === "admin") {
    return "Admin";
  }
  if (role === "artisan") {
    return "Artisan";
  }
  return "Customer";
}

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem(TOKEN_KEY) || "");
  const [statusText, setStatusText] = useState<string>("");

  const [loginEmail, setLoginEmail] = useState("customer@artisan-demo.local");
  const [loginPassword, setLoginPassword] = useState("DemoPass123!");

  const [tab, setTab] = useState<TabKey>("store");

  const [profile, setProfile] = useState<Profile | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<Cart | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);

  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [auctionFilter, setAuctionFilter] = useState<"active" | "upcoming" | "ended" | "all">("active");
  const [selectedAuctionId, setSelectedAuctionId] = useState<string>("");
  const [auctionBidAmount, setAuctionBidAmount] = useState<string>("30");
  const [auctionLiveEvents, setAuctionLiveEvents] = useState<string[]>([]);

  const [checkoutAddress, setCheckoutAddress] = useState<string>("Demo shipping address");
  const [checkoutCardToken, setCheckoutCardToken] = useState<string>("success_demo");

  const [newAuctionProductId, setNewAuctionProductId] = useState<string>("");
  const [newAuctionStartingPrice, setNewAuctionStartingPrice] = useState<string>("25");
  const [newAuctionMinIncrement, setNewAuctionMinIncrement] = useState<string>("1");
  const [newAuctionEndTime, setNewAuctionEndTime] = useState<string>("2030-01-01T12:00:00Z");

  const [adminDashboard, setAdminDashboard] = useState<AdminDashboardSummary | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminAuditLogs, setAdminAuditLogs] = useState<AdminAuditLog[]>([]);

  const isAdmin = profile?.role === "admin";
  const isArtisan = profile?.role === "artisan";
  const canCreateAuction = isAdmin || isArtisan;

  const selectedAuction = useMemo(
    () => auctions.find((item) => item.id === selectedAuctionId) ?? null,
    [auctions, selectedAuctionId]
  );

  async function handleLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setStatusText("Signing in...");
    try {
      const accessToken = await signInWithPassword(loginEmail, loginPassword);
      localStorage.setItem(TOKEN_KEY, accessToken);
      setToken(accessToken);
      setStatusText("Signed in");
    } catch (error) {
      setStatusText(`Login failed: ${parseErrorMessage(error)}`);
    }
  }

  function handleLogout(): void {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setProfile(null);
    setProducts([]);
    setCart(null);
    setOrders([]);
    setAuctions([]);
    setSelectedAuctionId("");
    setAuctionLiveEvents([]);
    setAdminDashboard(null);
    setAdminUsers([]);
    setAdminAuditLogs([]);
    setTab("store");
    setStatusText("Signed out");
  }

  async function loadProfile(): Promise<void> {
    if (!token) {
      return;
    }
    const data = await apiRequest<Profile>("/auth/me", {}, token);
    setProfile(data);
  }

  async function loadProducts(): Promise<void> {
    if (!token) {
      return;
    }
    const data = await apiRequest<Product[]>("/products?limit=50", {}, token);
    setProducts(data);
  }

  async function loadCart(): Promise<void> {
    if (!token) {
      return;
    }
    const data = await apiRequest<Cart>("/cart", {}, token);
    setCart(data);
  }

  async function loadOrders(): Promise<void> {
    if (!token) {
      return;
    }
    const data = await apiRequest<Order[]>("/orders", {}, token);
    setOrders(data);
  }

  async function loadAuctions(): Promise<void> {
    if (!token) {
      return;
    }
    const data = await apiRequest<AuctionListResponse>(`/auctions?view=${auctionFilter}&limit=50`, {}, token);
    setAuctions(data.items);
    if (!selectedAuctionId && data.items.length > 0) {
      setSelectedAuctionId(data.items[0].id);
    }
    if (selectedAuctionId && data.items.every((item) => item.id !== selectedAuctionId)) {
      setSelectedAuctionId(data.items[0]?.id ?? "");
    }
  }

  async function loadAdminData(): Promise<void> {
    if (!token || !isAdmin) {
      return;
    }
    const [dashboard, users, logs] = await Promise.all([
      apiRequest<AdminDashboardSummary>("/admin/dashboard", {}, token),
      apiRequest<AdminUser[]>("/admin/users?limit=100", {}, token),
      apiRequest<AdminAuditLog[]>("/admin/audit-logs?limit=100", {}, token),
    ]);

    setAdminDashboard(dashboard);
    setAdminUsers(users);
    setAdminAuditLogs(logs);
  }

  async function addToCart(productId: string): Promise<void> {
    if (!token) {
      return;
    }
    try {
      await apiRequest<Cart>(
        "/cart/items",
        {
          method: "POST",
          body: JSON.stringify({ product_id: productId, quantity: 1 }),
        },
        token
      );
      await loadCart();
      setStatusText("Added to cart");
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function removeCartItem(itemId: string): Promise<void> {
    if (!token) {
      return;
    }
    try {
      await apiRequest<Cart>(`/cart/items/${itemId}`, { method: "DELETE" }, token);
      await loadCart();
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function checkout(): Promise<void> {
    if (!token) {
      return;
    }
    try {
      await apiRequest<Order>(
        "/orders/checkout",
        {
          method: "POST",
          body: JSON.stringify({
            card_token: checkoutCardToken,
            shipping_address: checkoutAddress,
          }),
        },
        token
      );
      await Promise.all([loadCart(), loadOrders()]);
      setStatusText("Checkout completed");
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function placeBid(): Promise<void> {
    if (!token || !selectedAuctionId) {
      return;
    }

    const amount = Number(auctionBidAmount);
    if (Number.isNaN(amount) || amount <= 0) {
      setStatusText("Bid amount must be greater than zero");
      return;
    }

    try {
      await apiRequest(
        `/auctions/${selectedAuctionId}/bids`,
        {
          method: "POST",
          body: JSON.stringify({ bid_amount: amount }),
        },
        token
      );
      setStatusText("Bid submitted");
      await loadAuctions();
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function closeAuction(): Promise<void> {
    if (!token || !selectedAuctionId) {
      return;
    }
    try {
      await apiRequest(`/auctions/${selectedAuctionId}/close`, { method: "POST" }, token);
      setStatusText("Auction closed");
      await loadAuctions();
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function createAuction(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!token) {
      return;
    }

    try {
      await apiRequest<Auction>(
        "/auctions",
        {
          method: "POST",
          body: JSON.stringify({
            product_id: newAuctionProductId,
            starting_price: Number(newAuctionStartingPrice),
            min_increment: Number(newAuctionMinIncrement),
            end_time: newAuctionEndTime,
          }),
        },
        token
      );
      setStatusText("Auction created");
      await loadAuctions();
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  async function toggleUserSuspension(user: AdminUser): Promise<void> {
    if (!token || !isAdmin) {
      return;
    }

    try {
      await apiRequest<AdminUser>(
        `/admin/users/${user.id}/suspension`,
        {
          method: "PATCH",
          body: JSON.stringify({ is_suspended: !user.is_suspended }),
        },
        token
      );
      await loadAdminData();
      setStatusText(`Updated suspension for ${user.email}`);
    } catch (error) {
      setStatusText(parseErrorMessage(error));
    }
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        await loadProfile();
      } catch {
        if (!cancelled) {
          handleLogout();
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }

    (async () => {
      try {
        await Promise.all([loadProducts(), loadCart(), loadOrders(), loadAuctions()]);
      } catch (error) {
        setStatusText(parseErrorMessage(error));
      }
    })();
  }, [token, auctionFilter]);

  useEffect(() => {
    if (!token || !isAdmin) {
      return;
    }

    (async () => {
      try {
        await loadAdminData();
      } catch (error) {
        setStatusText(parseErrorMessage(error));
      }
    })();
  }, [token, isAdmin]);

  useEffect(() => {
    if (!token || !selectedAuctionId) {
      return;
    }

    const socket = new WebSocket(wsUrl(`/auctions/ws/live/${selectedAuctionId}`, token));

    socket.onmessage = (event) => {
      setAuctionLiveEvents((existing) => {
        const item = `${new Date().toLocaleTimeString()} ${event.data}`;
        return [item, ...existing].slice(0, 50);
      });
      void loadAuctions();
    };

    socket.onerror = () => {
      setStatusText("Live socket error. Check token and backend WebSocket endpoint.");
    };

    return () => {
      socket.close();
    };
  }, [token, selectedAuctionId]);

  if (!token) {
    return (
      <div className="app-shell auth-layout">
        <section className="panel auth-panel">
          <p className="eyebrow">ITCS489 Project Frontend</p>
          <h1>Artisan Marketplace Console</h1>
          <p className="muted">
            Sign in with your seeded Supabase users to test products, checkout, auctions, and admin moderation.
          </p>

          <form className="stack" onSubmit={handleLogin}>
            <label>
              Email
              <input value={loginEmail} onChange={(event) => setLoginEmail(event.target.value)} required />
            </label>

            <label>
              Password
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                required
              />
            </label>

            <button type="submit">Sign In</button>
          </form>

          <p className="status-text">{statusText}</p>
          <div className="quick-logins">
            <button
              type="button"
              onClick={() => {
                setLoginEmail("customer@artisan-demo.local");
                setLoginPassword("DemoPass123!");
              }}
            >
              Use Customer Demo
            </button>
            <button
              type="button"
              onClick={() => {
                setLoginEmail("artisan@artisan-demo.local");
                setLoginPassword("DemoPass123!");
              }}
            >
              Use Artisan Demo
            </button>
            <button
              type="button"
              onClick={() => {
                setLoginEmail("admin@artisan-demo.local");
                setLoginPassword("DemoPass123!");
              }}
            >
              Use Admin Demo
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar panel">
        <div>
          <p className="eyebrow">Connected to FastAPI</p>
          <h1>Artisan Marketplace Frontend</h1>
          {profile && (
            <p className="muted">
              {profile.email} · {roleLabel(profile.role)} · {profile.is_suspended ? "Suspended" : "Active"}
            </p>
          )}
        </div>
        <button type="button" onClick={handleLogout}>
          Log Out
        </button>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={tab === "store" ? "tab-active" : ""}
          onClick={() => setTab("store")}
        >
          Store
        </button>
        <button
          type="button"
          className={tab === "auctions" ? "tab-active" : ""}
          onClick={() => setTab("auctions")}
        >
          Auctions
        </button>
        {isAdmin && (
          <button
            type="button"
            className={tab === "admin" ? "tab-active" : ""}
            onClick={() => setTab("admin")}
          >
            Admin
          </button>
        )}
      </nav>

      <p className="status-text">{statusText}</p>

      {tab === "store" && (
        <section className="grid two-col">
          <article className="panel">
            <div className="panel-head">
              <h2>Products</h2>
              <button type="button" onClick={() => void loadProducts()}>
                Refresh
              </button>
            </div>
            <ul className="list-grid">
              {products.map((product) => (
                <li key={product.id} className="list-item">
                  <div>
                    <p className="title">{product.name}</p>
                    <p className="muted">{product.category}</p>
                    <p className="muted">{product.description}</p>
                    <p>
                      ${formatMoney(product.price)} · Stock {product.stock_quantity}
                    </p>
                    <p className="muted">ID: {product.id}</p>
                  </div>
                  <button type="button" onClick={() => void addToCart(product.id)}>
                    Add To Cart
                  </button>
                </li>
              ))}
            </ul>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h2>Cart</h2>
              <button type="button" onClick={() => void loadCart()}>
                Refresh
              </button>
            </div>
            <ul className="list-grid compact">
              {(cart?.items ?? []).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <p className="title">{item.product_name}</p>
                    <p>
                      Qty {item.quantity} · ${formatMoney(item.line_total)}
                    </p>
                  </div>
                  <button type="button" onClick={() => void removeCartItem(item.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>

            <p className="subtotal">Subtotal: ${formatMoney(cart?.subtotal ?? "0")}</p>

            <div className="stack">
              <label>
                Shipping Address
                <input
                  value={checkoutAddress}
                  onChange={(event) => setCheckoutAddress(event.target.value)}
                  minLength={5}
                />
              </label>
              <label>
                Card Token
                <input value={checkoutCardToken} onChange={(event) => setCheckoutCardToken(event.target.value)} />
              </label>
              <button type="button" onClick={() => void checkout()}>
                Checkout
              </button>
            </div>
          </article>

          <article className="panel span-all">
            <div className="panel-head">
              <h2>My Orders</h2>
              <button type="button" onClick={() => void loadOrders()}>
                Refresh
              </button>
            </div>
            <ul className="list-grid compact">
              {orders.map((order) => (
                <li key={order.id} className="list-item order-item">
                  <div>
                    <p className="title">Order {shortId(order.id)}</p>
                    <p>
                      {order.status} · ${formatMoney(order.total_amount)}
                    </p>
                    <p className="muted">{order.shipping_address}</p>
                  </div>
                </li>
              ))}
            </ul>
          </article>
        </section>
      )}

      {tab === "auctions" && (
        <section className="grid two-col">
          <article className="panel">
            <div className="panel-head">
              <h2>Auction Feed</h2>
              <div className="inline-tools">
                <select
                  value={auctionFilter}
                  onChange={(event) =>
                    setAuctionFilter(event.target.value as "active" | "upcoming" | "ended" | "all")
                  }
                >
                  <option value="active">active</option>
                  <option value="upcoming">upcoming</option>
                  <option value="ended">ended</option>
                  <option value="all">all</option>
                </select>
                <button type="button" onClick={() => void loadAuctions()}>
                  Refresh
                </button>
              </div>
            </div>

            <ul className="list-grid compact selectable-list">
              {auctions.map((auction) => (
                <li
                  key={auction.id}
                  className={`list-item ${selectedAuctionId === auction.id ? "selected" : ""}`}
                  onClick={() => setSelectedAuctionId(auction.id)}
                >
                  <div>
                    <p className="title">Auction {shortId(auction.id)}</p>
                    <p>
                      {auction.status} · ${formatMoney(auction.current_highest_bid)}
                    </p>
                    <p className="muted">Product {shortId(auction.product_id)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </article>

          <article className="panel">
            <h2>Live Bidding</h2>
            {selectedAuction ? (
              <>
                <div className="stack dense">
                  <p>
                    <strong>Auction:</strong> {selectedAuction.id}
                  </p>
                  <p>
                    <strong>Highest:</strong> ${formatMoney(selectedAuction.current_highest_bid)}
                  </p>
                  <p>
                    <strong>Min Increment:</strong> ${formatMoney(selectedAuction.min_increment)}
                  </p>
                  <p>
                    <strong>Ends:</strong> {new Date(selectedAuction.end_time).toLocaleString()}
                  </p>
                </div>

                <div className="inline-tools">
                  <input
                    value={auctionBidAmount}
                    onChange={(event) => setAuctionBidAmount(event.target.value)}
                    aria-label="Bid amount"
                  />
                  <button type="button" onClick={() => void placeBid()}>
                    Place Bid
                  </button>
                  {canCreateAuction && (
                    <button type="button" onClick={() => void closeAuction()}>
                      Close Auction
                    </button>
                  )}
                </div>
              </>
            ) : (
              <p className="muted">Select an auction from the feed.</p>
            )}

            {canCreateAuction && (
              <form className="stack top-gap" onSubmit={(event) => void createAuction(event)}>
                <h3>Create Auction</h3>
                <label>
                  Product ID
                  <input
                    value={newAuctionProductId}
                    onChange={(event) => setNewAuctionProductId(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Starting Price
                  <input
                    value={newAuctionStartingPrice}
                    onChange={(event) => setNewAuctionStartingPrice(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Min Increment
                  <input
                    value={newAuctionMinIncrement}
                    onChange={(event) => setNewAuctionMinIncrement(event.target.value)}
                    required
                  />
                </label>
                <label>
                  End Time (ISO)
                  <input value={newAuctionEndTime} onChange={(event) => setNewAuctionEndTime(event.target.value)} required />
                </label>
                <button type="submit">Create</button>
              </form>
            )}
          </article>

          <article className="panel span-all">
            <h2>Live Socket Events</h2>
            <ul className="terminal-log">
              {auctionLiveEvents.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>
      )}

      {tab === "admin" && isAdmin && (
        <section className="grid two-col">
          <article className="panel">
            <div className="panel-head">
              <h2>Dashboard</h2>
              <button type="button" onClick={() => void loadAdminData()}>
                Refresh
              </button>
            </div>

            {adminDashboard && (
              <ul className="metric-list">
                <li>Users: {adminDashboard.users_total}</li>
                <li>Suspended: {adminDashboard.users_suspended}</li>
                <li>Products: {adminDashboard.products_total}</li>
                <li>Orders: {adminDashboard.orders_total}</li>
                <li>Auctions: {adminDashboard.auctions_total}</li>
                <li>Revenue: ${formatMoney(adminDashboard.revenue_total)}</li>
              </ul>
            )}
          </article>

          <article className="panel">
            <h2>Users</h2>
            <ul className="list-grid compact">
              {adminUsers.map((user) => (
                <li key={user.id} className="list-item">
                  <div>
                    <p className="title">{user.email}</p>
                    <p className="muted">
                      {user.role} · {user.is_suspended ? "suspended" : "active"}
                    </p>
                  </div>
                  <button type="button" onClick={() => void toggleUserSuspension(user)}>
                    {user.is_suspended ? "Unsuspend" : "Suspend"}
                  </button>
                </li>
              ))}
            </ul>
          </article>

          <article className="panel span-all">
            <h2>Audit Logs</h2>
            <ul className="list-grid compact">
              {adminAuditLogs.map((log) => (
                <li key={log.id} className="list-item order-item">
                  <div>
                    <p className="title">{log.action}</p>
                    <p>
                      {log.target_type} · {shortId(log.target_id)}
                    </p>
                    <p className="muted">{new Date(log.created_at).toLocaleString()}</p>
                  </div>
                </li>
              ))}
            </ul>
          </article>
        </section>
      )}
    </div>
  );
}
