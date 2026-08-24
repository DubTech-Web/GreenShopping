import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Cart, Estimate } from "../types";
import { ConfirmModal, ErrorNote, money, Spinner } from "../components";
import { useApp } from "../store";

export default function Checkout() {
  const { refreshCart } = useApp();
  const navigate = useNavigate();
  const [cart, setCart] = useState<Cart | null>(null);
  const [distance, setDistance] = useState(50);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [method, setMethod] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [placing, setPlacing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Fetch the carbon estimate for a distance. Called on load and on explicit "update" —
  // NOT on every keystroke, and never when only the delivery method changes (Spec §21).
  const fetchEstimate = useCallback(async (dist: number) => {
    try {
      const est = await api.estimate(dist);
      setEstimate(est);
      setMethod((m) => m || est.recommended); // default to the greener recommendation
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not estimate impact");
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const c = await api.cart();
        setCart(c);
        if (c.item_count > 0) await fetchEstimate(50);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not load cart");
      } finally { setLoading(false); }
    })();
  }, [fetchEstimate]);

  const placeOrder = async () => {
    setConfirming(false);
    setPlacing(true); setError("");
    try {
      const order = await api.checkout(method, distance);
      const callbackUrl = `${window.location.origin}/orders/${order.id}`;
      const payment = await api.initPayment(order.id, callbackUrl);
      if (!payment.simulated && payment.authorization_url) {
        window.location.assign(payment.authorization_url);
        return;
      }
      await api.verifyPayment(payment.reference);
      await refreshCart();
      navigate(`/orders/${order.id}`, { state: { justPlaced: true } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Checkout failed");
      setPlacing(false);
    }
  };

  if (loading) return <Spinner />;
  if (!cart || cart.item_count === 0)
    return <div className="panel center-text">Your cart is empty. <a href="/products">Browse products</a>.</div>;

  const selected = estimate?.options.find((o) => o.key === method);

  return (
    <div className="stack">
      <h1>Checkout</h1>
      {error && <ErrorNote message={error} />}

      <div className="checkout-layout">
        {/* Delivery selection */}
        <div className="stack">
          <div className="card card-pad stack">
            <h2 style={{ margin: 0 }}>Delivery distance</h2>
            <div className="row">
              <input type="number" min={1} className="input" style={{ width: 120 }} value={distance}
                onChange={(e) => setDistance(Math.max(1, Number(e.target.value)))} />
              <span className="muted">km</span>
              <button className="btn btn-ghost btn-sm" onClick={() => fetchEstimate(distance)}>
                Update estimate
              </button>
            </div>
          </div>

          <div className="card card-pad stack">
            <h2 style={{ margin: 0 }}>Choose delivery</h2>
            {estimate?.options.map((o) => {
              const isRec = o.key === estimate.recommended;
              return (
                <label key={o.key} className={`panel row-wrap ${o.key === method ? "eco-alt" : ""}`}
                  style={{ justifyContent: "space-between", cursor: "pointer" }}>
                  <div className="row" style={{ gap: 10 }}>
                    <input type="radio" name="delivery" checked={o.key === method}
                      onChange={() => setMethod(o.key)} />
                    <div>
                      <strong>{o.label}</strong>{isRec && <span className="badge badge-eco" style={{ marginLeft: 8 }}>Recommended</span>}
                      <div className="muted" style={{ fontSize: "0.85rem" }}>{o.speed} · {money(o.cost)}</div>
                    </div>
                  </div>
                  <span className="mono badge badge-neutral">{o.delivery_carbon.toFixed(2)} kg CO₂e</span>
                </label>
              );
            })}
            {estimate && <div className="reason">{estimate.reason}</div>}
          </div>
        </div>

        {/* Impact + summary — updates client-side when switching method (no refetch) */}
        <aside className="stack">
          <div className="card card-pad">
            <h2 style={{ marginTop: 0 }}>Estimated environmental impact</h2>
            <div className="impact-row"><span>Products</span>
              <span className="mono">{estimate?.product_carbon.toFixed(2)} kg CO₂e</span></div>
            <div className="impact-row"><span>Delivery ({selected?.label ?? "—"})</span>
              <span className="mono">{selected ? selected.delivery_carbon.toFixed(2) : "—"} kg CO₂e</span></div>
            <div className="impact-row impact-total"><span>Total</span>
              <span className="mono">{selected ? selected.total_carbon.toFixed(2) : "—"} kg CO₂e</span></div>
            <div className="reason" style={{ marginTop: 8 }}>Figures are estimates (kg CO₂e).</div>
          </div>

          <div className="card card-pad">
            <div className="impact-row"><span>Subtotal</span><span className="mono">{money(cart.subtotal)}</span></div>
            <div className="impact-row"><span>Delivery</span>
              <span className="mono">{selected ? money(selected.cost) : "—"}</span></div>
            <div className="impact-row impact-total"><span>Order total</span>
              <span className="mono">{selected ? money(cart.subtotal + selected.cost) : money(cart.subtotal)}</span></div>
            <button className="btn btn-primary btn-block" style={{ marginTop: 12 }}
              disabled={!method || placing} onClick={() => setConfirming(true)}>
              {placing ? "Starting payment…" : "Continue to payment"}
            </button>
            <div className="reason center-text" style={{ marginTop: 6 }}>You will be redirected to secure Paystack checkout.</div>
          </div>
        </aside>
      </div>
      {confirming && <ConfirmModal title="Confirm checkout" message="You are about to proceed to payment." confirmLabel="Continue" onConfirm={placeOrder} onCancel={() => setConfirming(false)} />}
    </div>
  );
}
