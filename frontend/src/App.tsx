import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import { apiRequest, signInWithPassword, signUpWithPassword, wsUrl } from "./api";
import type { ArtisanDetail, ArtisanSummary, Auction, AuctionListResponse, Cart, Order, Product, Profile } from "./types";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { CartPage } from "./CartPage";
import { BrowseSkeleton } from "./BrowseSkeleton";
import "./styles.css";

const CURRENCY_LABEL = "BHD";

const TOKEN_KEY = "artisan_access_token";

type AuctionView = "active" | "upcoming" | "ended" | "all";
type OrdersTab = "orders" | "sales";
type ProductSort = "newest" | "popular" | "price_asc" | "price_desc";

type AuctionDetail = {
  auction_id: string;
  status: string;
  product_id: string;
  seller_id: string;
  highest_bidder_id: string | null;
  current_highest_bid: string;
  min_increment: string;
  start_time: string;
  end_time: string;
  minimum_next_bid: string;
  recent_bids: Array<{
    id: string;
    bidder_id: string;
    bid_amount: string;
    created_at: string;
  }>;
};

function shortId(value: string): string {
  return value.length > 10 ? `${value.slice(0, 8)}...` : value;
}

function formatMoney(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) {
    return "0.00";
  }
  return n.toFixed(2);
}

function getArtisanName(artisan: Pick<ArtisanSummary, "full_name" | "shop_name">): string {
  return artisan.shop_name || artisan.full_name || "Independent Artisan";
}

function getProductArtistName(product: Product): string {
  return product.artist_shop_name || product.artist_name || "Independent Artisan";
}

function getInitial(value: string | null | undefined): string {
  return value?.trim().charAt(0).toUpperCase() || "A";
}

function parseError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function getFriendlyAuthMessage(error: unknown): string {
  const rawMessage = parseError(error);

  if (rawMessage.includes("Account is suspended")) {
    return "Your account has been suspended. Contact support or an administrator for access.";
  }

  try {
    const parsed = JSON.parse(rawMessage) as { detail?: unknown };
    if (Array.isArray(parsed.detail)) {
      const suspendedDetail = parsed.detail.find((item) => {
        if (!item || typeof item !== "object") {
          return false;
        }
        const detailItem = item as { msg?: unknown };
        return typeof detailItem.msg === "string" && detailItem.msg.includes("Account is suspended");
      });

      if (suspendedDetail) {
        return "Your account has been suspended. Contact support or an administrator for access.";
      }
    }
  } catch {
    // Fall back to the original message.
  }

  return rawMessage;
}

function toCountdown(endTime: string): string {
  const diffMs = new Date(endTime).getTime() - Date.now();
  if (diffMs <= 0) {
    return "Ended";
  }
  const total = Math.floor(diffMs / 1000);
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (d > 0) {
    return `${d}d ${h}h ${m}m left`;
  }
  return `${h}h ${m}m left`;
}

function statusClass(status: string): string {
  switch (status) {
    case "delivered":
      return "status-pill delivered";
    case "shipped":
      return "status-pill shipped";
    case "processing":
      return "status-pill processing";
    case "canceled":
      return "status-pill canceled";
    default:
      return "status-pill";
  }
}

function progressStage(status: string): number {
  if (status === "pending" || status === "paid") {
    return 1;
  }
  if (status === "processing") {
    return 2;
  }
  if (status === "shipped") {
    return 3;
  }
  if (status === "delivered") {
    return 4;
  }
  return 0;
}

function LoadingState({
  title,
  message,
  compact = false,
}: {
  title: string;
  message: string;
  compact?: boolean;
}) {
  return (
    <div className={`loading-screen${compact ? " loading-screen--compact" : ""}`} role="status" aria-live="polite" aria-busy="true">
      <div className="loading-screen__ambient loading-screen__ambient--one" aria-hidden="true" />
      <div className="loading-screen__ambient loading-screen__ambient--two" aria-hidden="true" />
      <div className="loading-card">
        <p className="eyebrow loading-eyebrow">Souq Al Artisan</p>
        <div className="loading-glyph" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <h1>{title}</h1>
        <p className="loading-copy">{message}</p>
        <div className="loading-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  );
}

function AuthGate({ token }: { token: string }) {
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

function AdminGate({ profile }: { profile: Profile | null }) {
  if (profile?.role !== "admin") {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

function Header({ profile, cart, onLogout }: { profile: Profile | null; cart: Cart | null; onLogout: () => void }) {
  const canManageStudio = profile?.role === "artisan" || profile?.role === "admin";
  const cartItemCount = cart?.items.length ?? 0;

  return (
    <header className="site-header">
      <div className="site-wrap header-inner">
        <Link className="brand" to="/">
          <span className="brand-star">*</span> Souq Al Artisan
        </Link>

        <nav className="main-nav">
          <Link to="/">Home</Link>
          <Link to="/browse">Browse</Link>
          <Link to="/auctions">Auctions</Link>
          <Link to="/orders">Orders</Link>
          {canManageStudio && <Link to="/studio">Studio</Link>}
          {profile?.role === "admin" && <Link to="/admin">Admin</Link>}
        </nav>

        <div className="header-actions">
          <Link to="/cart" className="cart-link">
            <span className="cart-icon">🛒</span>
            {cartItemCount > 0 && <span className="cart-badge">{cartItemCount}</span>}
          </Link>
          <Link className="profile-link" to="/account">
            <span
              className="avatar-chip"
              style={profile?.profile_image_url ? { backgroundImage: `url(${profile.profile_image_url})` } : undefined}
            >
              {!profile?.profile_image_url && (profile?.full_name?.charAt(0) || profile?.email?.charAt(0)?.toUpperCase() || "U")}
            </span>
            <span className="muted-inline">{profile?.full_name || profile?.email}</span>
          </Link>
          <button type="button" className="ghost-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}

function GuestHeader() {
  return (
    <header className="site-header">
      <div className="site-wrap header-inner">
        <Link className="brand" to="/">
          <span className="brand-star">*</span> Souq Al Artisan
        </Link>
        <nav className="main-nav">
          <Link to="/">Home</Link>
          <Link to="/browse">Browse</Link>
          <Link to="/auctions">Auctions</Link>
        </nav>
        <div className="header-actions">
          <Link className="ghost-btn" to="/login">
            Log in
          </Link>
          <Link className="solid-btn" to="/join">
            Join
          </Link>
        </div>
      </div>
    </header>
  );
}

function HomePage({ token, profile }: { token: string; profile: Profile | null }) {
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [popularArtisans, setPopularArtisans] = useState<ArtisanSummary[]>([]);
  const [popularProducts, setPopularProducts] = useState<Product[]>([]);
  const [homeStatus, setHomeStatus] = useState("");

  const artisanCta =
    !token
      ? {
          to: "/join",
          label: "Join Souq Al Artisan",
          copy: "Open your account, introduce your craft, and begin preparing your shop profile.",
        }
      : profile?.role === "artisan" || profile?.role === "admin"
        ? {
            to: "/studio",
            label: "Open Studio",
            copy: "Manage your catalog, refresh your listings, and keep your artisan presence ready for buyers.",
          }
        : {
            to: "/account",
            label: "Prepare Your Artisan Profile",
            copy: "Add your shop name, story, and profile image so your craft has a home when you are ready.",
          };

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const [artisansData, productsData] = await Promise.all([
          apiRequest<ArtisanSummary[]>("/artisans?sort=popular&limit=4"),
          apiRequest<Product[]>("/products?sort=popular&limit=4"),
        ]);
        if (cancelled) {
          return;
        }
        setPopularArtisans(artisansData);
        setPopularProducts(productsData);
      } catch (error) {
        if (!cancelled) {
          setHomeStatus(parseError(error));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    void (async () => {
      const data = await apiRequest<AuctionListResponse>("/auctions?view=active&limit=3", {}, token);
      setAuctions(data.items);
    })();
  }, [token]);

  return (
    <>
      <section className="site-wrap hero-grid home-hero">
        <div>
          <p className="eyebrow">Souq Al Artisan</p>
          <h1 className="hero-title">
            Handmade finds from the makers who shape them.
          </h1>
          <p className="hero-copy">
            Discover popular artisans, shop their most loved pieces, and support a marketplace built around craft, care, and local stories.
          </p>
          <div className="hero-actions">
            <Link className="solid-btn" to={token ? "/browse" : "/login"}>
              Browse Products
            </Link>
            <Link className="ghost-btn" to="/auctions">
              View Auctions
            </Link>
          </div>
        </div>
        <div className="hero-art" />
      </section>

      <section className="site-wrap support-panel">
        <article>
          <h3>Support Local</h3>
          <p>Directly support the livelihoods of talented artisans in your community.</p>
        </article>
        <article>
          <h3>Fair Trade</h3>
          <p>We ensure fair compensation and ethical practices for all our creators.</p>
        </article>
        <article>
          <h3>Handcrafted</h3>
          <p>Each item is unique, made with passion, skill, and attention to detail.</p>
        </article>
      </section>

      {homeStatus && (
        <section className="site-wrap">
          <p className="error-text">{homeStatus}</p>
        </section>
      )}

      <section className="site-wrap section-block">
        <div className="section-head">
          <h2>Popular Artisans</h2>
          <Link to="/browse">Shop their work</Link>
        </div>
        <div className="card-grid four-col top-gap">
          {popularArtisans.length === 0 ? (
            <article className="empty-state-card">
              <h3>Artisans are getting ready</h3>
              <p className="muted">Featured makers will appear here once their profiles and products are live.</p>
            </article>
          ) : (
            popularArtisans.map((artisan) => (
              <Link to={`/artisans/${artisan.id}`} key={artisan.id} className="artisan-card-link">
                <article className="artisan-card">
                  <div className="artisan-card-top">
                    <div
                      className="artisan-avatar artisan-avatar-large"
                      style={artisan.profile_image_url ? { backgroundImage: `url(${artisan.profile_image_url})` } : undefined}
                    >
                      {!artisan.profile_image_url && getInitial(getArtisanName(artisan))}
                    </div>
                    <span className="status-pill delivered">{artisan.units_sold} sold</span>
                  </div>
                  <h3>{getArtisanName(artisan)}</h3>
                  {artisan.bio && <p className="muted artisan-card-bio">{artisan.bio}</p>}
                  <p className="muted">{artisan.active_product_count} active products</p>
                </article>
              </Link>
            ))
          )}
        </div>
      </section>

      <section className="site-wrap section-block">
        <div className="section-head">
          <h2>Popular Products</h2>
          <Link to={token ? "/browse" : "/login"}>View all products</Link>
        </div>
        <div className="card-grid four-col top-gap">
          {popularProducts.length === 0 ? (
            <article className="empty-state-card">
              <h3>Products are coming soon</h3>
              <p className="muted">Popular handmade pieces will appear here as artisans publish their catalogs.</p>
            </article>
          ) : (
            popularProducts.map((product) => (
              <Link to={`/products/${product.id}`} key={product.id} className="product-card-link">
                <article className="product-card clickable-card">
                  <div className="product-photo" style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} />
                  <div className="product-content">
                    <h3>{product.name}</h3>
                    <p className="muted">{getProductArtistName(product)}</p>
                    <p className="price-row">{CURRENCY_LABEL} {formatMoney(product.price)}</p>
                    <p className="muted">{product.units_sold} sold</p>
                  </div>
                </article>
              </Link>
            ))
          )}
        </div>
      </section>

      {token && auctions.length > 0 && (
        <section className="site-wrap section-block">
          <div className="section-head">
            <h2>Live Auctions Now</h2>
            <Link to="/auctions">View all auctions</Link>
          </div>
          <div className="card-grid three-col">
            {auctions.map((auction) => (
              <Link to={`/auctions/${auction.id}`} key={auction.id} className="auction-card-link">
                <article className="auction-card">
                  <div className="card-photo" />
                  <div className="card-body">
                    <h3>Auction {shortId(auction.id)}</h3>
                    <p className="muted">{auction.status}</p>
                    <p className="bid-value">{CURRENCY_LABEL} {formatMoney(auction.current_highest_bid)}</p>
                    <p className="muted">Ends in {toCountdown(auction.end_time)}</p>
                  </div>
                </article>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="site-wrap section-block">
        <div className="artisan-cta-panel">
          <div>
            <p className="eyebrow">Welcome artisans</p>
            <h2>Bring your craft to Souq Al Artisan.</h2>
            <p>{artisanCta.copy}</p>
          </div>
          <Link className="solid-btn" to={artisanCta.to}>
            {artisanCta.label}
          </Link>
        </div>
      </section>
    </>
  );
}

function LoginPage({
  onLogin,
  noticeText,
}: {
  onLogin: (email: string, password: string) => Promise<void>;
  noticeText: string;
}) {
  const [email, setEmail] = useState("customer@artisan-demo.local");
  const [password, setPassword] = useState("DemoPass123!");
  const [errorText, setErrorText] = useState("");
  const navigate = useNavigate();

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorText("");
    try {
      await onLogin(email, password);
      navigate("/");
    } catch (error) {
      setErrorText(parseError(error));
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">Souq Al Artisan</p>
        <h1>Welcome Back</h1>
        <p className="muted">Sign in to access your account and orders</p>
        <form className="form-stack" onSubmit={submit}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <button type="submit" className="solid-btn full-width">
            Log In
          </button>
        </form>
        {noticeText && <p className="status-text">{noticeText}</p>}
        {errorText && <p className="error-text">{errorText}</p>}
        <p className="auth-switch">
          Don&apos;t have an account? <Link to="/join">Sign up</Link>
        </p>
      </section>
    </main>
  );
}

function RegisterPage({
  onRegister,
  noticeText,
}: {
  onRegister: (email: string, password: string, displayName: string) => Promise<void>;
  noticeText: string;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [errorText, setErrorText] = useState("");
  const navigate = useNavigate();

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorText("");
    try {
      await onRegister(email, password, displayName);
      navigate("/");
    } catch (error) {
      setErrorText(parseError(error));
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">Souq Al Artisan</p>
        <h1>Create Account</h1>
        <p className="muted">Join our community of artisans and collectors</p>
        <form className="form-stack" onSubmit={submit}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            Display Name
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required />
          </label>
          <button type="submit" className="solid-btn full-width">
            Create Account
          </button>
        </form>
        {noticeText && <p className="status-text">{noticeText}</p>}
        {errorText && <p className="error-text">{errorText}</p>}
        <p className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </section>
    </main>
  );
}

function AccountPage({
  token,
  profile,
  onProfileUpdate,
}: {
  token: string;
  profile: Profile | null;
  onProfileUpdate: (profile: Profile) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [shopName, setShopName] = useState("");
  const [bio, setBio] = useState("");
  const [profileImageUrl, setProfileImageUrl] = useState("");
  const [selectedProfileImage, setSelectedProfileImage] = useState<File | null>(null);
  const [profilePreviewUrl, setProfilePreviewUrl] = useState("");
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    setFullName(profile?.full_name || "");
    setShopName(profile?.shop_name || "");
    setBio(profile?.bio || "");
    setProfileImageUrl(profile?.profile_image_url || "");
  }, [profile]);

  useEffect(() => {
    if (!selectedProfileImage) {
      setProfilePreviewUrl("");
      return;
    }

    const objectUrl = URL.createObjectURL(selectedProfileImage);
    setProfilePreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedProfileImage]);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setStatusText("");
    try {
      let updated = await apiRequest<Profile>(
        "/auth/me",
        {
          method: "PUT",
          body: JSON.stringify({
            full_name: fullName || null,
            shop_name: shopName || null,
            bio: bio || null,
          }),
        },
        token
      );
      if (selectedProfileImage) {
        const body = new FormData();
        body.append("image_file", selectedProfileImage);
        updated = await apiRequest<Profile>("/auth/me/profile-image", { method: "POST", body }, token);
        setSelectedProfileImage(null);
        setProfileImageUrl(updated.profile_image_url || "");
      }
      onProfileUpdate(updated);
      setStatusText("Profile updated");
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  return (
    <main className="site-wrap section-block">
      <div className="section-head">
        <div>
          <h1>Account Profile</h1>
          <p className="muted">Shape the public details buyers and admins use to understand your craft.</p>
        </div>
      </div>

      <section className="account-grid top-gap">
        <form className="card section-card form-stack" onSubmit={submit}>
          <label>
            Full Name
            <input value={fullName} onChange={(event) => setFullName(event.target.value)} />
          </label>
          <label>
            Shop Name
            <input value={shopName} onChange={(event) => setShopName(event.target.value)} />
          </label>
          <label>
            Bio
            <textarea value={bio} onChange={(event) => setBio(event.target.value)} rows={5} maxLength={1000} />
          </label>
          <label className="studio-upload">
            Profile Photo
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setSelectedProfileImage(event.target.files?.[0] ?? null)}
            />
          </label>
          {selectedProfileImage && <p className="muted">Selected: {selectedProfileImage.name}</p>}
          <button type="submit" className="solid-btn">
            Save Profile
          </button>
          {statusText && <p className="status-text">{statusText}</p>}
        </form>

        <aside className="card section-card account-preview">
          <div
            className="artisan-avatar artisan-avatar-large"
            style={profilePreviewUrl || profileImageUrl ? { backgroundImage: `url(${profilePreviewUrl || profileImageUrl})` } : undefined}
          >
            {!profilePreviewUrl && !profileImageUrl && getInitial(shopName || fullName)}
          </div>
          <p className="eyebrow">{profile?.role || "customer"}</p>
          <h2>{shopName || fullName || "Your artisan profile"}</h2>
          <p className="muted">{bio || "Add a short story about your work, materials, and studio."}</p>
          <p className="muted">Role changes are handled by the marketplace team.</p>
        </aside>
      </section>
    </main>
  );
}

function BrowsePage({ token, onCartUpdate }: { token: string; onCartUpdate: () => Promise<void> }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [artisans, setArtisans] = useState<ArtisanSummary[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All Categories");
  const [artistId, setArtistId] = useState("");
  const [sortBy, setSortBy] = useState<ProductSort>("newest");
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    void Promise.all([loadProducts(), loadArtisans()]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadArtisans(): Promise<void> {
    try {
      const data = await apiRequest<ArtisanSummary[]>("/artisans?sort=popular&limit=100");
      setArtisans(data);
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function loadProducts(): Promise<void> {
    setIsLoadingProducts(true);
    try {
      const query = new URLSearchParams({ limit: "100", sort: sortBy });
      if (search.trim()) {
        query.set("search", search.trim());
      }
      if (category !== "All Categories") {
        query.set("category", category);
      }
      if (artistId) {
        query.set("artist_id", artistId);
      }
      const data = await apiRequest<Product[]>(`/products?${query.toString()}`, {}, token);
      setProducts(data);
    } catch (error) {
      setStatusText(parseError(error));
    } finally {
      setIsLoadingProducts(false);
    }
  }

  async function addToCart(productId: string): Promise<void> {
    try {
      await apiRequest<Cart>(
        "/cart/items",
        {
          method: "POST",
          body: JSON.stringify({ product_id: productId, quantity: 1 }),
        },
        token
      );
      setStatusText("Added to cart");
      await onCartUpdate();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  const categories = useMemo(() => {
    const set = new Set(products.map((item) => item.category));
    return ["All Categories", ...Array.from(set).sort()];
  }, [products]);

  const navigate = useNavigate();

  return (
    <main className="site-wrap section-block">
      <h1>Browse Products</h1>
      <p className="muted">Explore our curated collection of handcrafted goods.</p>

      <section className="filter-row">
        <input
          placeholder="Search products..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void loadProducts();
            }
          }}
        />
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          {categories.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select value={artistId} onChange={(event) => setArtistId(event.target.value)}>
          <option value="">All Artisans</option>
          {artisans.map((artisan) => (
            <option key={artisan.id} value={artisan.id}>
              {getArtisanName(artisan)}
            </option>
          ))}
        </select>
        <select value={sortBy} onChange={(event) => setSortBy(event.target.value as ProductSort)}>
          <option value="newest">Newest Arrivals</option>
          <option value="popular">Most Popular</option>
          <option value="price_asc">Price Low to High</option>
          <option value="price_desc">Price High to Low</option>
        </select>
        <button type="button" className="ghost-btn" onClick={() => void loadProducts()}>
          Apply
        </button>
      </section>

      {statusText && <p className="status-text">{statusText}</p>}

      {isLoadingProducts ? (
        <BrowseSkeleton />
      ) : (
        <>
          <p className="muted top-gap">{products.length} products found</p>
          <section className="card-grid four-col top-gap">
            {products.map((product) => (
              <article className="product-card clickable-card" key={product.id} onClick={() => navigate(`/products/${product.id}`)}>
                <div className="product-photo" style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} />
                <div className="product-content">
                  <div className="product-info">
                    <h3>{product.name}</h3>
                    <p className="muted product-category">{product.category}</p>
                    <Link
                      className="artisan-inline-link product-artisan"
                      to={`/artisans/${product.artist_id}`}
                      onClick={(event) => event.stopPropagation()}
                    >
                      {getProductArtistName(product)}
                    </Link>
                  </div>
                  <p className="price-row product-price">{CURRENCY_LABEL} {formatMoney(product.price)}</p>
                  <div className="product-card-footer">
                    <p className="muted product-stock">{product.stock_quantity} in stock | {product.units_sold} sold</p>
                    <button type="button" className="ghost-btn" onClick={(e) => { e.stopPropagation(); void addToCart(product.id); }}>
                      Add to Cart
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </section>
        </>
      )}
    </main>
  );
}

function ArtisanDetailPage() {
  const params = useParams();
  const [artisan, setArtisan] = useState<ArtisanDetail | null>(null);
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    if (!params.artisanId) {
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const data = await apiRequest<ArtisanDetail>(`/artisans/${params.artisanId}`);
        if (!cancelled) {
          setArtisan(data);
        }
      } catch (error) {
        if (!cancelled) {
          setStatusText(parseError(error));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.artisanId]);

  if (statusText) {
    return (
      <main className="site-wrap section-block">
        <Link to="/" className="back-link">
          Back to Home
        </Link>
        <p className="error-text top-gap">{statusText}</p>
      </main>
    );
  }

  if (!artisan) {
    return (
      <main className="site-wrap section-block">
        <LoadingState compact title="Loading artisan profile" message="Gathering the maker story and active products." />
      </main>
    );
  }

  return (
    <main className="site-wrap section-block">
      <Link to="/" className="back-link">
        Back to Home
      </Link>
      <section className="artisan-profile-hero top-gap">
        <div
          className="artisan-avatar artisan-profile-avatar"
          style={artisan.profile_image_url ? { backgroundImage: `url(${artisan.profile_image_url})` } : undefined}
        >
          {!artisan.profile_image_url && getInitial(getArtisanName(artisan))}
        </div>
        <div>
          <p className="eyebrow">Artisan Profile</p>
          <h1>{getArtisanName(artisan)}</h1>
          {artisan.full_name && artisan.shop_name && <p className="muted">By {artisan.full_name}</p>}
          <p className="top-gap">{artisan.bio || "This artisan is preparing their studio story."}</p>
          <div className="artisan-stat-row top-gap">
            <span className="status-pill delivered">{artisan.units_sold} sold</span>
            <span className="status-pill">{artisan.active_product_count} active products</span>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-head">
          <h2>Products by {getArtisanName(artisan)}</h2>
          <Link to={`/browse`}>Browse all</Link>
        </div>
        <div className="card-grid four-col top-gap">
          {artisan.products.length === 0 ? (
            <article className="empty-state-card">
              <h3>No active products yet</h3>
              <p className="muted">Check back soon for this artisan's latest work.</p>
            </article>
          ) : (
            artisan.products.map((product) => (
              <Link to={`/products/${product.id}`} key={product.id} className="product-card-link">
                <article className="product-card clickable-card">
                  <div className="product-photo" style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} />
                  <div className="product-content">
                    <h3>{product.name}</h3>
                    <p className="muted">{product.category}</p>
                    <p className="price-row">{CURRENCY_LABEL} {formatMoney(product.price)}</p>
                    <p className="muted">{product.units_sold} sold</p>
                  </div>
                </article>
              </Link>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function StudioPage({ token, profile }: { token: string; profile: Profile | null }) {
  const canManageStudio = profile?.role === "artisan" || profile?.role === "admin";
  const [statusText, setStatusText] = useState("");
  const [myProducts, setMyProducts] = useState<Product[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);
  const [showArchived, setShowArchived] = useState(true);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("1");
  const [selectedImages, setSelectedImages] = useState<Array<{ id: string; file: File; url: string }>>([]);
  const [isActive, setIsActive] = useState(true);

  function imageKey(file: File): string {
    return `${file.name}:${file.size}:${file.lastModified}`;
  }

  function appendSelectedImages(files: FileList | null): void {
    if (!files) {
      return;
    }

    setSelectedImages((prev) => {
      const existing = new Set(prev.map((item) => imageKey(item.file)));
      const additions = Array.from(files)
        .filter((file) => file.type.startsWith("image/"))
        .filter((file) => !existing.has(imageKey(file)))
        .map((file) => ({
          id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
          file,
          url: URL.createObjectURL(file),
        }));

      return [...prev, ...additions];
    });
  }

  function removeSelectedImage(id: string): void {
    setSelectedImages((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target) {
        URL.revokeObjectURL(target.url);
      }
      return prev.filter((item) => item.id !== id);
    });
  }

  function clearSelectedImages(): void {
    setSelectedImages((prev) => {
      prev.forEach((item) => URL.revokeObjectURL(item.url));
      return [];
    });
  }

  useEffect(() => {
    if (!canManageStudio) {
      return;
    }
    void loadMyProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, canManageStudio, showArchived]);

  function StudioProductsSkeleton() {
    return (
      <div className="skeleton-grid three-col top-gap" aria-label="Loading studio products">
        {Array.from({ length: 6 }).map((_, i) => (
          <article key={i} className="skeleton-card">
            <div className="skeleton-photo" />
            <div className="skeleton-content">
              <div className="skeleton-line skeleton-title" style={{ width: "70%" }} />
              <div className="skeleton-line skeleton-category" style={{ width: "45%" }} />
              <div className="skeleton-line skeleton-price" style={{ width: "55%" }} />
              <div className="skeleton-line skeleton-button" />
            </div>
          </article>
        ))}
      </div>
    );
  }

  async function loadMyProducts(): Promise<void> {
    setIsLoadingProducts(true);
    try {
      const query = new URLSearchParams({ include_inactive: String(showArchived), limit: "100" });
      const data = await apiRequest<Product[]>(`/products/mine?${query.toString()}`, {}, token);
      setMyProducts(data);
    } catch (error) {
      setStatusText(parseError(error));
    } finally {
      setIsLoadingProducts(false);
    }
  }

  function resetForm(): void {
    setName("");
    setDescription("");
    setCategory("");
    setPrice("");
    setStock("1");
    clearSelectedImages();
    setIsActive(true);
  }

  async function createProduct(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      const body = new FormData();
      body.append("name", name);
      body.append("description", description);
      body.append("category", category);
      body.append("price", price);
      body.append("stock_quantity", stock);
      const primaryImage = selectedImages[0]?.file;
      if (primaryImage) {
        body.append("image_file", primaryImage, primaryImage.name);
      }

      await apiRequest<Product>("/products/upload", { method: "POST", body }, token);
      setStatusText("Product added");
      resetForm();
      await loadMyProducts();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  function openEditor(product: Product): void {
    setEditingProduct(product);
    setName(product.name);
    setDescription(product.description);
    setCategory(product.category);
    setPrice(String(product.price));
    setStock(String(product.stock_quantity));
    setIsActive(product.is_active);
    clearSelectedImages();
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!editingProduct) {
      return;
    }

    try {
      const body = new FormData();
      body.append("name", name);
      body.append("description", description);
      body.append("category", category);
      body.append("price", price);
      body.append("stock_quantity", stock);
      body.append("is_active", String(isActive));
      const primaryImage = selectedImages[0]?.file;
      if (primaryImage) {
        body.append("image_file", primaryImage, primaryImage.name);
      }

      await apiRequest<Product>(`/products/${editingProduct.id}/upload`, { method: "PATCH", body }, token);
      setStatusText("Product updated");
      setEditingProduct(null);
      resetForm();
      await loadMyProducts();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function archiveProduct(productId: string): Promise<void> {
    try {
      await apiRequest<Product>(`/products/${productId}`, { method: "DELETE" }, token);
      setStatusText("Product archived");
      await loadMyProducts();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function restoreProduct(productId: string): Promise<void> {
    try {
      await apiRequest<Product>(`/products/${productId}/restore`, { method: "POST" }, token);
      setStatusText("Product restored");
      await loadMyProducts();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  if (!canManageStudio) {
    return (
      <main className="site-wrap section-block">
        <h1>Studio</h1>
        <p className="muted">Only artisans and admins can manage products.</p>
      </main>
    );
  }

  return (
    <main className="site-wrap section-block">
      <div className="section-head">
        <h1>Studio</h1>
        <label className="studio-toggle muted-inline">
          <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />
          Show archived
        </label>
      </div>
      <p className="muted">Create new products and edit your current catalog.</p>

      {statusText && <p className="status-text">{statusText}</p>}

      <section className="card section-card top-gap">
        <h2>Add Product</h2>
        <form className="form-grid" onSubmit={createProduct}>
          <input placeholder="Name" value={name} onChange={(event) => setName(event.target.value)} required />
          <input placeholder="Category" value={category} onChange={(event) => setCategory(event.target.value)} required />
          <textarea
            placeholder="Description"
            value={description}
            rows={4}
            onChange={(event) => setDescription(event.target.value)}
            required
          />
          <input placeholder="Price" value={price} onChange={(event) => setPrice(event.target.value)} required />
          <input type="number" min="0" placeholder="Stock" value={stock} onChange={(event) => setStock(event.target.value)} required />
          <label className="studio-upload">
            Upload images
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => {
                appendSelectedImages(event.currentTarget.files);
                event.currentTarget.value = "";
              }}
            />
          </label>
          {selectedImages.length > 0 && (
            <div className="image-preview-row" aria-label="Selected images">
              {selectedImages.map((item) => (
                <div key={item.id} className="image-preview-card">
                  <img src={item.url} alt={item.file.name} className="image-preview-img" />
                  <button
                    type="button"
                    className="image-remove-btn"
                    aria-label={`Remove ${item.file.name}`}
                    onClick={() => removeSelectedImage(item.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <button type="submit" className="solid-btn">
            Add Product
          </button>
        </form>
      </section>

      {isLoadingProducts ? (
        <StudioProductsSkeleton />
      ) : (
        <section className="card-grid three-col top-gap">
          {myProducts.map((product) => (
            <article className="product-card" key={product.id}>
              <div className="product-photo" style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} />
              <div className="product-content">
                <h3>{product.name}</h3>
                <p className="muted">{product.category}</p>
                <p className="price-row">{CURRENCY_LABEL} {formatMoney(product.price)}</p>
                <p className="muted">{product.stock_quantity} in stock</p>
                <p className={product.is_active ? "status-pill delivered" : "status-pill canceled"}>
                  {product.is_active ? "active" : "archived"}
                </p>
                <div className="studio-actions">
                  <button type="button" className="ghost-btn" onClick={() => openEditor(product)}>
                    Edit
                  </button>
                  {product.is_active ? (
                    <button type="button" className="ghost-btn" onClick={() => void archiveProduct(product.id)}>
                      Archive
                    </button>
                  ) : (
                    <button type="button" className="ghost-btn" onClick={() => void restoreProduct(product.id)}>
                      Restore
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </section>
      )}

      {editingProduct && (
        <div className="modal-overlay" onClick={() => setEditingProduct(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setEditingProduct(null)} type="button">
              ×
            </button>
            <h2>Edit Product</h2>
            <form className="form-grid top-gap" onSubmit={saveProduct}>
              <input placeholder="Name" value={name} onChange={(event) => setName(event.target.value)} required />
              <input placeholder="Category" value={category} onChange={(event) => setCategory(event.target.value)} required />
              <textarea
                placeholder="Description"
                value={description}
                rows={4}
                onChange={(event) => setDescription(event.target.value)}
                required
              />
              <input placeholder="Price" value={price} onChange={(event) => setPrice(event.target.value)} required />
              <input type="number" min="0" placeholder="Stock" value={stock} onChange={(event) => setStock(event.target.value)} required />
              <label className="checkbox-row">
                <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
                Product is active
              </label>
              <label>
                Replace images (optional)
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(event) => {
                    appendSelectedImages(event.currentTarget.files);
                    event.currentTarget.value = "";
                  }}
                />
                {selectedImages.length > 0 && (
                  <div className="image-preview-row" aria-label="Selected images">
                    {selectedImages.map((item) => (
                      <div key={item.id} className="image-preview-card">
                        <img src={item.url} alt={item.file.name} className="image-preview-img" />
                        <button
                          type="button"
                          className="image-remove-btn"
                          aria-label={`Remove ${item.file.name}`}
                          onClick={() => removeSelectedImage(item.id)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </label>
              <button type="submit" className="solid-btn">
                Save Changes
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function ProductDetailPage({ token, onCartUpdate }: { token: string; onCartUpdate: () => Promise<void> }) {
  const params = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    if (!params.productId) {
      return;
    }
    void (async () => {
      const data = await apiRequest<Product>(`/products/${params.productId}`, {}, token);
      setProduct(data);
    })();
  }, [params.productId, token]);

  async function addToCart(): Promise<void> {
    if (!product) {
      return;
    }
    try {
      await apiRequest<Cart>(
        "/cart/items",
        {
          method: "POST",
          body: JSON.stringify({ product_id: product.id, quantity: 1 }),
        },
        token
      );
      setStatusText("Added to cart");
      await onCartUpdate();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  if (!product) {
    return (
      <main className="site-wrap section-block">
        <LoadingState
          compact
          title="Loading product details"
          message="Fetching the handmade piece, images, and purchase options."
        />
      </main>
    );
  }

  return (
    <main className="site-wrap section-block">
      <Link to="/browse" className="back-link">
        ← Back to Products
      </Link>
      <section className="detail-grid top-gap">
        <div className="detail-photo" style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} />
        <article>
          <p className="eyebrow">{product.category}</p>
          <h1>{product.name}</h1>
          <Link className="artisan-inline-link" to={`/artisans/${product.artist_id}`}>
            By {getProductArtistName(product)}
          </Link>
          <p className="price-row">{CURRENCY_LABEL} {formatMoney(product.price)}</p>
          <p className="muted top-gap">{product.description}</p>
          <p className="muted top-gap">{product.units_sold} sold | {product.stock_quantity} in stock</p>
          <button type="button" className="solid-btn top-gap" onClick={() => void addToCart()}>
            Add to Cart
          </button>
          {statusText && <p className="status-text">{statusText}</p>}
          <p className="muted top-gap">Product ID: {shortId(product.id)}</p>
        </article>
      </section>
    </main>
  );
}

function AuctionsPage({ token }: { token: string }) {
  const [view, setView] = useState<AuctionView>("active");
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("");

  function AuctionsSkeleton() {
    return (
      <div className="skeleton-grid three-col top-gap" aria-label="Loading auctions">
        {Array.from({ length: 6 }).map((_, i) => (
          <article key={i} className="skeleton-card">
            <div className="skeleton-photo" />
            <div className="skeleton-content">
              <div className="skeleton-line skeleton-title" style={{ width: "70%" }} />
              <div className="skeleton-line skeleton-category" style={{ width: "45%" }} />
              <div className="skeleton-line skeleton-price" style={{ width: "55%" }} />
              <div className="skeleton-line" style={{ width: "40%" }} />
            </div>
          </article>
        ))}
      </div>
    );
  }

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setIsLoading(true);
      setStatusText("");
      setAuctions([]);
      try {
        const data = await apiRequest<AuctionListResponse>(`/auctions?view=${view}&limit=50`, {}, token);
        if (cancelled) return;
        setAuctions(data.items);
      } catch (error) {
        if (cancelled) return;
        setStatusText(parseError(error));
      } finally {
        if (cancelled) return;
        setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, view]);

  return (
    <main className="site-wrap section-block">
      <div className="section-head">
        <h1>Artisan Auctions</h1>
      </div>
      <div className="tab-row top-gap">
        {(["active", "upcoming", "ended", "all"] as AuctionView[]).map((value) => (
          <button
            key={value}
            type="button"
            className={view === value ? "chip active" : "chip"}
            onClick={() => setView(value)}
          >
            {value}
          </button>
        ))}
      </div>

      {statusText && <p className="status-text">{statusText}</p>}

      {isLoading ? (
        <AuctionsSkeleton />
      ) : (
        <section className="card-grid three-col top-gap">
          {auctions.length === 0 ? (
          <article className="empty-state-card">
            <h3>No auctions right now</h3>
            <p className="muted">No auctions are being held at the moment. Please check back soon.</p>
          </article>
          ) : (
            auctions.map((auction) => (
              <Link key={auction.id} to={`/auctions/${auction.id}`} className="auction-card-link">
                <article className="auction-card">
                  <div className="card-photo" />
                  <div className="card-body">
                    <h3>{shortId(auction.product_id)}</h3>
                    <p className="muted">{auction.status}</p>
                    <p className="bid-value">{CURRENCY_LABEL} {formatMoney(auction.current_highest_bid)}</p>
                    <p className="muted">{toCountdown(auction.end_time)}</p>
                  </div>
                </article>
              </Link>
            ))
          )}
        </section>
      )}
    </main>
  );
}

function AuctionDetailPage({ token }: { token: string }) {
  const params = useParams();
  const [detail, setDetail] = useState<AuctionDetail | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [currentProfile, setCurrentProfile] = useState<Profile | null>(null);
  const [bidderName, setBidderName] = useState("");
  const [bidAmount, setBidAmount] = useState("");
  const [statusText, setStatusText] = useState("");
  const [bidError, setBidError] = useState("");
  const [showBidConfirmation, setShowBidConfirmation] = useState(false);
  const [liveEvents, setLiveEvents] = useState<string[]>([]);

  async function loadAuctionAndProduct(): Promise<void> {
    if (!params.auctionId) {
      return;
    }
    try {
      const data = await apiRequest<AuctionDetail>(`/auctions/${params.auctionId}`, {}, token);
      setDetail(data);
      setBidAmount(data.minimum_next_bid);
      
      // Fetch product details
      try {
        const prod = await apiRequest<Product>(`/products/${data.product_id}`, {}, token);
        setProduct(prod);
      } catch {
        // Product fetch failed, but auction detail succeeded
      }
    } catch {
      setStatusText("Failed to load auction details");
    }

    // Fetch current user profile
    try {
      const profile = await apiRequest<Profile>("/profile", {}, token);
      setCurrentProfile(profile);
    } catch {
      // Profile fetch failed, but that's okay
    }
  }

  useEffect(() => {
    void loadAuctionAndProduct();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.auctionId, token]);

  useEffect(() => {
    if (!params.auctionId) {
      return;
    }

    const socket = new WebSocket(wsUrl(`/auctions/ws/live/${params.auctionId}`, token));
    socket.onmessage = (event) => {
      setLiveEvents((items) => {
        const line = `${new Date().toLocaleTimeString()} · ${event.data}`;
        return [line, ...items].slice(0, 10);
      });
      void loadAuctionAndProduct();
    };
    socket.onerror = () => {
      setStatusText("Live updates disconnected");
    };

    return () => {
      socket.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.auctionId, token]);

  function validateBidAmount(): boolean {
    setBidError("");
    
    const bidNum = Number(bidAmount);
    if (Number.isNaN(bidNum)) {
      setBidError("Bid amount must be a number");
      return false;
    }

    if (!detail) {
      setBidError("Auction details not loaded");
      return false;
    }

    const minimumBid = Number(detail.minimum_next_bid);
    if (bidNum < minimumBid) {
      setBidError(`Bid must be at least ${CURRENCY_LABEL} ${formatMoney(minimumBid)}`);
      return false;
    }

    return true;
  }

  async function placeBid(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!params.auctionId) {
      return;
    }

    if (!validateBidAmount()) {
      return;
    }

    setShowBidConfirmation(true);
  }

  async function confirmBid(): Promise<void> {
    if (!params.auctionId) {
      return;
    }

    setShowBidConfirmation(false);
    setStatusText("Placing bid...");

    try {
      await apiRequest(
        `/auctions/${params.auctionId}/bids`,
        {
          method: "POST",
          body: JSON.stringify({ bid_amount: Number(bidAmount) }),
        },
        token
      );
      setStatusText("✅ Bid placed successfully!");
      setBidAmount("");
      setBidError("");
      await loadAuctionAndProduct();
    } catch (error) {
      setStatusText("");
      setBidError(parseError(error));
    }
  }

  if (!detail) {
    return (
      <main className="site-wrap section-block">
        <LoadingState
          compact
          title="Loading auction details"
          message="Pulling in the current bid, countdown, and recent activity."
        />
      </main>
    );
  }

  const isYouWinning = detail.highest_bidder_id === currentProfile?.id;
  const minimumBid = Number(detail.minimum_next_bid);
  const bidNum = Number(bidAmount);
  const isValidBid = !Number.isNaN(bidNum) && bidNum >= minimumBid;

  return (
    <main className="site-wrap section-block">
      <Link to="/auctions" className="back-link">
        ← Back to Auctions
      </Link>
      <section className="detail-grid top-gap">
        <div className="detail-photo">
          {product?.image_url ? (
            <img src={product.image_url} alt={product.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <div style={{ background: "#e0e0e0", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span className="muted">No image</span>
            </div>
          )}
        </div>
        <article>
          <h1>{product?.name || `Auction ${shortId(detail.auction_id)}`}</h1>
          {product?.artist_id && (
            <Link className="artisan-inline-link" to={`/artisans/${product.artist_id}`}>
              By {getProductArtistName(product)}
            </Link>
          )}
          <p className="muted">{detail.status}</p>
          
          <div className="bid-panel top-gap">
            <h3>Current Highest Bid</h3>
            <p className="bid-value">{CURRENCY_LABEL} {formatMoney(detail.current_highest_bid)}</p>
            <p className="muted">{toCountdown(detail.end_time)}</p>
            
            {detail.highest_bidder_id && (
              <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid #e0e0e0" }}>
                {isYouWinning ? (
                  <p style={{ color: "#2ecc71", fontWeight: "bold" }}>🏆 Your bid is winning!</p>
                ) : (
                  <p className="muted">Leading: {shortId(detail.highest_bidder_id)}</p>
                )}
              </div>
            )}
          </div>

          <form className="form-stack top-gap" onSubmit={placeBid}>
            <label>
              Your Name
              <input value={bidderName} onChange={(event) => setBidderName(event.target.value)} placeholder="Enter your name" />
            </label>
            <label>
              Bid Amount (minimum: {CURRENCY_LABEL} {formatMoney(detail.minimum_next_bid)})
              <input
                type="number"
                step="0.01"
                value={bidAmount}
                onChange={(event) => {
                  setBidAmount(event.target.value);
                  setBidError("");
                }}
                required
              />
            </label>
            {bidError && <p style={{ color: "#e74c3c", fontSize: "0.9rem" }}>⚠️ {bidError}</p>}
            <button type="submit" className="solid-btn" disabled={!isValidBid || showBidConfirmation}>
              {showBidConfirmation ? "Confirming..." : "Place Bid"}
            </button>
          </form>

          {showBidConfirmation && (
            <div className="confirmation-overlay">
              <div className="confirmation-dialog">
                <h3>Confirm Your Bid</h3>
                <div className="confirmation-details">
                  <div>
                    <p className="muted">Product</p>
                    <p><strong>{product?.name || "Auction Item"}</strong></p>
                  </div>
                  <div>
                    <p className="muted">Current Highest Bid</p>
                    <p><strong>{CURRENCY_LABEL} {formatMoney(detail.current_highest_bid)}</strong></p>
                  </div>
                  <div>
                    <p className="muted">Your Bid</p>
                    <p><strong style={{ color: "#2ecc71", fontSize: "1.2rem" }}>{CURRENCY_LABEL} {formatMoney(bidAmount)}</strong></p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
                  <button
                    className="outline-btn"
                    onClick={() => setShowBidConfirmation(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="solid-btn"
                    onClick={() => void confirmBid()}
                  >
                    Confirm Bid
                  </button>
                </div>
              </div>
            </div>
          )}

          {statusText && <p className="status-text">{statusText}</p>}
        </article>
      </section>

      <section className="top-gap">
        <div className="section-head">
          <h2>Bid History</h2>
          <span className="muted">{detail.recent_bids.length} bids</span>
        </div>
        <ul className="history-list">
          {detail.recent_bids.map((bid) => {
            const isYourBid = bid.bidder_id === currentProfile?.id;
            return (
              <li key={bid.id} style={{ opacity: bid.bidder_id === detail.highest_bidder_id ? 1 : 0.7 }}>
                <div>
                  <strong>{isYourBid ? "You" : shortId(bid.bidder_id)}</strong>
                  {bid.bidder_id === detail.highest_bidder_id && (
                    <span style={{ marginLeft: "0.5rem", color: "#2ecc71" }}>🏆 Winning</span>
                  )}
                  <p className="muted">{new Date(bid.created_at).toLocaleString()}</p>
                </div>
                <strong>{CURRENCY_LABEL} {formatMoney(bid.bid_amount)}</strong>
              </li>
            );
          })}
        </ul>
      </section>

      {liveEvents.length > 0 && (
        <section className="top-gap">
          <div className="section-head">
            <h2>Live Feed</h2>
          </div>
          <ul className="history-list live-feed">
            {liveEvents.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function OrdersPage({ token, profile }: { token: string; profile: Profile | null }) {
  const [tab, setTab] = useState<OrdersTab>("orders");
  const [orders, setOrders] = useState<Order[]>([]);
  const [sales, setSales] = useState<Order[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState<boolean>(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [statusText, setStatusText] = useState("");
  const [nextStatus, setNextStatus] = useState("processing");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [shippingCarrier, setShippingCarrier] = useState("");
  const [shippingMethod, setShippingMethod] = useState("");
  const [estimatedDeliveryAt, setEstimatedDeliveryAt] = useState("");

  const canManageSales = profile?.role === "artisan" || profile?.role === "admin";

  async function loadOrders(): Promise<void> {
    setIsLoadingOrders(true);
    try {
      const [myOrders, mySales] = await Promise.all([
        apiRequest<Order[]>("/orders", {}, token),
        canManageSales ? apiRequest<Order[]>("/orders/artisan/sales", {}, token) : Promise.resolve([]),
      ]);
      setOrders(myOrders);
      setSales(mySales);
    } finally {
      setIsLoadingOrders(false);
    }
  }

  useEffect(() => {
    void loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, canManageSales]);

  async function updateStatus(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedOrder) {
      return;
    }

    try {
      await apiRequest<Order>(
        `/orders/${selectedOrder.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: nextStatus,
            tracking_number: trackingNumber || null,
            shipping_carrier: shippingCarrier || null,
            shipping_method: shippingMethod || null,
            estimated_delivery_at: estimatedDeliveryAt ? new Date(estimatedDeliveryAt).toISOString() : null,
          }),
        },
        token
      );
      setStatusText("Order status updated");
      await loadOrders();
      setSelectedOrder(null);
      setTrackingNumber("");
      setShippingCarrier("");
      setShippingMethod("");
      setEstimatedDeliveryAt("");
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  const data = tab === "orders" ? orders : sales;

  function OrdersSkeleton() {
    return (
      <section className="card-grid three-col top-gap">
        {Array.from({ length: 3 }).map((_, i) => (
          <article className="skeleton-card" key={i} style={{ minHeight: 140 }}>
            <div className="skeleton-photo" />
            <div className="skeleton-content">
              <div className="skeleton-line skeleton-title" style={{ width: '60%' }} />
              <div className="skeleton-line" style={{ width: '40%' }} />
              <div className="skeleton-line" style={{ width: '30%' }} />
            </div>
          </article>
        ))}
      </section>
    );
  }

  return (
    <main className="site-wrap section-block">
      <h1>Orders & Sales</h1>
      <p className="muted">Manage your purchases and track artisan sales.</p>

      <div className="tab-row top-gap">
        <button type="button" className={tab === "orders" ? "chip active" : "chip"} onClick={() => setTab("orders")}>
          My Orders
        </button>
        {canManageSales && (
          <button type="button" className={tab === "sales" ? "chip active" : "chip"} onClick={() => setTab("sales")}>
            My Sales
          </button>
        )}
      </div>

      {statusText && <p className="status-text">{statusText}</p>}

      {isLoadingOrders ? (
        <OrdersSkeleton />
      ) : (
        <section className="card-grid three-col top-gap">
          {data.map((order) => (
            <article className="order-card" key={order.id}>
              <div className="card-photo" />
              <div className="card-body">
                <h3>Order #{shortId(order.id)}</h3>
                <p className="muted"><strong>Placed:</strong> {new Date(order.created_at).toLocaleString()}</p>
                <p className="price-row">{CURRENCY_LABEL} {formatMoney(order.total_amount)}</p>
                <p className={statusClass(order.status)}>{order.status}</p>
                <button type="button" className="ghost-btn" onClick={() => setSelectedOrder(order)}>
                  View Details
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {selectedOrder && (
        <div className="modal-overlay" onClick={() => setSelectedOrder(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedOrder(null)} type="button">
              ×
            </button>
            <h2>Order Details</h2>
            <p>
              <strong>Order ID:</strong> {selectedOrder.id}
            </p>
            <p>
              <strong>Status:</strong> <span className={statusClass(selectedOrder.status)}>{selectedOrder.status}</span>
            </p>
            <p>
              <strong>Date:</strong> {new Date(selectedOrder.created_at).toLocaleString()}
            </p>
            <p>
              <strong>Shipping:</strong> {selectedOrder.shipping_address}
            </p>
            {selectedOrder.tracking_number && (
              <p>
                <strong>Tracking:</strong> {selectedOrder.tracking_number}
              </p>
            )}
            {selectedOrder.shipping_carrier && (
              <p>
                <strong>Carrier:</strong> {selectedOrder.shipping_carrier}
              </p>
            )}
            {selectedOrder.shipping_method && (
              <p>
                <strong>Method:</strong> {selectedOrder.shipping_method}
              </p>
            )}
            {selectedOrder.estimated_delivery_at && (
              <p>
                <strong>Estimated Delivery:</strong> {new Date(selectedOrder.estimated_delivery_at).toLocaleString()}
              </p>
            )}

            <section className="progress-strip top-gap">
              <div className={progressStage(selectedOrder.status) >= 1 ? "step done" : "step"}>Placed</div>
              <div className={progressStage(selectedOrder.status) >= 2 ? "step done" : "step"}>Processing</div>
              <div className={progressStage(selectedOrder.status) >= 3 ? "step done" : "step"}>Shipped</div>
              <div className={progressStage(selectedOrder.status) >= 4 ? "step done" : "step"}>Delivered</div>
            </section>

            <ul className="history-list top-gap">
              {selectedOrder.items.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.product_name}</strong>
                    <p className="muted">Qty {item.quantity}</p>
                  </div>
                  <strong>{CURRENCY_LABEL} {formatMoney(item.unit_price)}</strong>
                </li>
              ))}
            </ul>

            {tab === "sales" && canManageSales && (
              <form className="form-stack top-gap" onSubmit={updateStatus}>
                <h3>Update Order Status</h3>
                <label>
                  New Status
                  <select value={nextStatus} onChange={(event) => setNextStatus(event.target.value)}>
                    <option value="processing">Processing</option>
                    <option value="shipped">Shipped</option>
                    <option value="delivered">Delivered</option>
                    <option value="canceled">Canceled</option>
                  </select>
                </label>
                <label>
                  Tracking Number
                  <input value={trackingNumber} onChange={(event) => setTrackingNumber(event.target.value)} />
                </label>
                <label>
                  Carrier
                  <input value={shippingCarrier} onChange={(event) => setShippingCarrier(event.target.value)} />
                </label>
                <label>
                  Shipping Method
                  <input value={shippingMethod} onChange={(event) => setShippingMethod(event.target.value)} />
                </label>
                <label>
                  Estimated Delivery
                  <input
                    type="datetime-local"
                    value={estimatedDeliveryAt}
                    onChange={(event) => setEstimatedDeliveryAt(event.target.value)}
                  />
                </label>
                <button type="submit" className="solid-btn">
                  Update Status
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

function SiteLayout({ profile, cart, onLogout }: { profile: Profile | null; cart: Cart | null; onLogout: () => void }) {
  return (
    <>
      <Header profile={profile} cart={cart} onLogout={onLogout} />
      <Outlet />
    </>
  );
}

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem(TOKEN_KEY) || "");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [cart, setCart] = useState<Cart | null>(null);
  const [authNotice, setAuthNotice] = useState("");

  const navigate = useNavigate();

  useEffect(() => {
    if (!token) {
      setProfile(null);
      setCart(null);
      return;
    }

    setProfileLoading(true);
    void (async () => {
      try {
        const me = await apiRequest<Profile>("/auth/me", {}, token);
        setProfile(me);
        setAuthNotice("");
        await loadCart();
      } catch (error) {
        setAuthNotice(getFriendlyAuthMessage(error));
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
        setProfile(null);
        setCart(null);
        navigate("/login");
      } finally {
        setProfileLoading(false);
      }
    })();
  }, [navigate, token]);

  async function loadCart(): Promise<void> {
    try {
      const data = await apiRequest<Cart>("/cart", {}, token);
      setCart(data);
    } catch {
      setCart(null);
    }
  }

  async function login(email: string, password: string): Promise<void> {
    const accessToken = await signInWithPassword(email, password);
    try {
      await apiRequest<Profile>("/auth/me", {}, accessToken);
      localStorage.setItem(TOKEN_KEY, accessToken);
      setAuthNotice("");
      setToken(accessToken);
    } catch (error) {
      const message = getFriendlyAuthMessage(error);
      setAuthNotice(message);
      throw new Error(message);
    }
  }

  async function register(email: string, password: string, displayName: string): Promise<void> {
    await signUpWithPassword(email, password, displayName);
    await login(email, password);
  }

  function logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setProfile(null);
    navigate("/login");
  }

  const isBootstrappingSession = Boolean(token) && profileLoading && !profile;

  if (isBootstrappingSession) {
    return (
      <LoadingState
        title="Preparing Souq Al Artisan"
        message="Loading your profile, products, and live auction data."
      />
    );
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <>
            {token ? <Header profile={profile} cart={cart} onLogout={logout} /> : <GuestHeader />}
            <HomePage token={token} profile={profile} />
          </>
        }
      />
      <Route
        path="/artisans/:artisanId"
        element={
          <>
            {token ? <Header profile={profile} cart={cart} onLogout={logout} /> : <GuestHeader />}
            <ArtisanDetailPage />
          </>
        }
      />
      <Route path="/login" element={token ? <Navigate to="/" replace /> : <><GuestHeader /><LoginPage onLogin={login} noticeText={authNotice} /></>} />
      <Route path="/join" element={token ? <Navigate to="/" replace /> : <><GuestHeader /><RegisterPage onRegister={register} noticeText={authNotice} /></>} />

      <Route element={<AuthGate token={token} />}>
        <Route element={<SiteLayout profile={profile} cart={cart} onLogout={logout} />}>
          <Route path="/browse" element={<BrowsePage token={token} onCartUpdate={loadCart} />} />
          <Route path="/cart" element={<CartPage token={token} cart={cart} onCartUpdate={loadCart} />} />
          <Route path="/account" element={<AccountPage token={token} profile={profile} onProfileUpdate={setProfile} />} />
          <Route path="/studio" element={<StudioPage token={token} profile={profile} />} />
          <Route path="/products/:productId" element={<ProductDetailPage token={token} onCartUpdate={loadCart} />} />
          <Route path="/auctions" element={<AuctionsPage token={token} />} />
          <Route path="/auctions/:auctionId" element={<AuctionDetailPage token={token} />} />
          <Route path="/orders" element={<OrdersPage token={token} profile={profile} />} />
        </Route>

        <Route element={<AdminGate profile={profile} />}>
          <Route element={<SiteLayout profile={profile} cart={cart} onLogout={logout} />}>
            <Route path="/admin" element={<AdminDashboardPage token={token} />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
