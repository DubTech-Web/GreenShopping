import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Cart as CartT } from "../types";
import { ErrorNote, money, Spinner } from "../components";
import { useApp } from "../store";

export default function Cart() {
  const { customer, refreshCart } = useApp();
  const navigate = useNavigate();
  const [cart, setCart] = useState<CartT | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!customer) { setLoading(false); return; }
    api.cart().then(setCart).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [customer]);

  const apply = async (fn: () => Promise<CartT>) => {
    try { const c = await fn(); setCart(c); await refreshCart(); setError(""); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  if (!customer) return (
    <div className="panel center-text stack">
      <h1>Your cart</h1>
      <p className="muted">Please log in to view your cart.</p>
      <div><Link to="/login" className="btn btn-primary">Log in</Link></div>
    </div>
  );
  if (loading) return <Spinner />;

  return (
    <div className="stack">
      <h1>Your cart</h1>
      {error && <ErrorNote message={error} />}
      {!cart || cart.items.length === 0 ? (
        <div className="panel center-text stack">
          <p className="muted">Your cart is empty.</p>
          <div><Link to="/products" className="btn btn-primary">Browse products</Link></div>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Product</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead>
              <tbody>
                {cart.items.map((it) => (
                  <tr key={it.id}>
                    <td><Link to={`/products/${it.product_id}`}>{it.name}</Link></td>
                    <td className="mono">{money(it.price)}</td>
                    <td>
                      <input type="number" min={1} max={it.stock_quantity} value={it.quantity}
                        className="input" style={{ width: 70 }}
                        onChange={(e) => apply(() => api.updateCartItem(it.id, Math.max(1, Number(e.target.value))))} />
                    </td>
                    <td className="mono">{money(it.line_total)}</td>
                    <td><button className="btn btn-ghost btn-sm"
                      onClick={() => apply(() => api.removeCartItem(it.id))}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="spread card card-pad">
            <span className="muted">{cart.item_count} item(s)</span>
            <div className="row" style={{ gap: 16 }}>
              <span className="price">Subtotal: {money(cart.subtotal)}</span>
              <button className="btn btn-primary" onClick={() => navigate("/checkout")}>
                Proceed to checkout →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
