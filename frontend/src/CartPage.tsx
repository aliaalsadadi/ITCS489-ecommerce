import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "./api";
import type { Cart, Order } from "./types";

const DEMO_CARD = "1111222233334444";

function formatMoney(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) {
    return "0.00";
  }
  return n.toFixed(2);
}

function parseError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function CartPage({ token, cart, onCartUpdate }: { token: string; cart: Cart | null; onCartUpdate: () => Promise<void> }) {
  const [checkoutAddress, setCheckoutAddress] = useState("123 Main Street, Apt 4B, San Francisco, CA 94102");
  const [checkoutCardToken, setCheckoutCardToken] = useState("");
  const [cardHolder, setCardHolder] = useState("");
  const [expiry, setExpiry] = useState(""); // MM/YY
  const [cvv, setCvv] = useState("");
  const [statusText, setStatusText] = useState("");
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    void onCartUpdate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function removeCartItem(itemId: string): Promise<void> {
    try {
      await apiRequest(`/cart/items/${itemId}`, { method: "DELETE" }, token);
      setStatusText("Item removed");
      await onCartUpdate();
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function checkout(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsCheckingOut(true);
    setStatusText("");
    try {
      // Client-side validation: required fields
      if (!cardHolder.trim()) throw new Error("Card holder name is required.");

      const cardDigits = checkoutCardToken.replace(/\D/g, "");
      if (cardDigits.length !== 16 && cardDigits !== DEMO_CARD) throw new Error("Invalid card number. Use 1111222233334444 for demo.");

      // expiry format MM/YY
      if (!/^\d{2}\/\d{2}$/.test(expiry)) throw new Error("Expiry must be in MM/YY format.");
      const [mStr, yStr] = expiry.split("/");
      const month = Number(mStr);
      const year = Number(yStr) + 2000;
      if (!(month >= 1 && month <= 12)) throw new Error("Expiry month is invalid.");
      const expDate = new Date(year, month - 1 + 1, 1); // first day of month after expiry
      if (expDate <= new Date()) throw new Error("Card has expired.");

      if (!/^\d{3,4}$/.test(cvv)) throw new Error("CVV must be 3 or 4 digits.");

      await apiRequest<Order>(
        "/orders/checkout",
        {
          method: "POST",
          body: JSON.stringify({
            card_token: cardDigits,
            shipping_address: checkoutAddress,
          }),
        },
        token
      );
      setStatusText("Checkout complete!");
      await onCartUpdate();
      setTimeout(() => navigate("/orders"), 1500);
    } catch (error) {
      setStatusText(parseError(error));
    } finally {
      setIsCheckingOut(false);
    }
  }

  if (!cart || cart.items.length === 0) {
    return (
      <main className="site-wrap section-block">
        <h1>Shopping Cart</h1>
        <p className="muted">Your cart is empty</p>
        <button
          type="button"
          className="solid-btn top-gap"
          onClick={() => navigate("/browse")}
        >
          Continue Shopping
        </button>
      </main>
    );
  }

  return (
    <main className="site-wrap section-block">
      <h1>Shopping Cart</h1>
      <p className="muted">{cart.items.length} items in your cart</p>

      <section className="card section-card top-gap">
        <h2>Order Summary</h2>

        <ul className="history-list top-gap">
          {cart.items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.product_name}</strong>
                <p className="muted">Qty {item.quantity}</p>
              </div>
              <div className="cart-actions">
                <strong>{"BHD"} {formatMoney(item.line_total)}</strong>
                <button type="button" className="ghost-btn" onClick={() => void removeCartItem(item.id)}>
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>

        <p className="price-row top-gap">Subtotal: {"BHD"} {formatMoney(cart.subtotal)}</p>
      </section>

      <section className="card section-card top-gap">
        <h2>Checkout</h2>
        {statusText && (
          <p className={statusText.includes("complete") ? "status-text" : "error-text"}>
            {statusText}
          </p>
        )}

        <form className="form-stack top-gap" onSubmit={checkout}>
          <label>
            Shipping Address
            <input
              value={checkoutAddress}
              onChange={(event) => setCheckoutAddress(event.target.value)}
              minLength={5}
              required
            />
          </label>

          <label>
            Card Holder Name
            <input
              placeholder="Full name as on card"
              value={cardHolder}
              onChange={(e) => setCardHolder(e.target.value)}
              required
            />
          </label>

          <label>
            Card Number
            <input
              inputMode="numeric"
              placeholder="1111 2222 3333 4444"
              value={checkoutCardToken.replace(/(.{4})/g, "$1 ").trim()}
              onChange={(event) => {
                // keep only digits, limit to 16
                const digits = (event.target.value || "").replace(/\D/g, "").slice(0, 16);
                setCheckoutCardToken(digits);
              }}
              required
            />
            <p className="muted-inline">Demo: use 1111222233334444</p>
          </label>

          <div className="form-grid" style={{ gridTemplateColumns: "1fr 120px" }}>
            <label>
              Expiry (MM/YY)
              <input
                placeholder="MM/YY"
                value={expiry}
                onChange={(e) => {
                  // allow digits and slash, auto-insert slash
                  const raw = (e.target.value || "").replace(/[^\d]/g, "");
                  if (raw.length <= 2) setExpiry(raw);
                  else setExpiry(raw.slice(0, 2) + "/" + raw.slice(2, 4));
                }}
                inputMode="numeric"
                required
              />
            </label>

            <label>
              CVV
              <input
                placeholder="123"
                inputMode="numeric"
                value={cvv}
                onChange={(e) => setCvv((e.target.value || "").replace(/\D/g, "").slice(0, 4))}
                required
              />
            </label>
          </div>

          <button type="submit" className="solid-btn" disabled={isCheckingOut}>
            {isCheckingOut ? "Processing..." : "Complete Purchase"}
          </button>
        </form>
      </section>
    </main>
  );
}
