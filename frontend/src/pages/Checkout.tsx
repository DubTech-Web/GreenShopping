import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Cart, DeliveryDestination, Estimate } from "../types";
import { ConfirmModal, ErrorNote, money, Spinner } from "../components";
import { useApp } from "../store";

export default function Checkout() {
  const { refreshCart } = useApp();
  const navigate = useNavigate();
  const [cart, setCart] = useState<Cart | null>(null);
  const [destination, setDestination] = useState<DeliveryDestination | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [method, setMethod] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [placing, setPlacing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [locating, setLocating] = useState(false);

  const fetchEstimate = useCallback(async (location: DeliveryDestination) => {
    try {
      const est = await api.estimate(location);
      setEstimate(est);
      setMethod((m) => m || est.recommended); // default to the greener recommendation
      setError("");
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not estimate impact");
      return false;
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const c = await api.cart();
        setCart(c);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not load cart");
      } finally { setLoading(false); }
    })();
  }, []);

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError("Location is unavailable. Use a browser with location access over HTTPS and try again.");
      return;
    }
    setLocating(true);
    setError("");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const current = { latitude: coords.latitude, longitude: coords.longitude };
        if (await fetchEstimate(current)) setDestination(current);
        setLocating(false);
      },
      (positionError) => {
        const message = positionError.code === positionError.PERMISSION_DENIED
          ? "Location permission was denied. Allow location access in your browser settings and try again."
          : positionError.code === positionError.TIMEOUT
            ? "Could not get your location in time. Please try again."
            : "Could not determine your location. Check your device location settings and try again.";
        setError(message);
        setLocating(false);
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    );
  };

  const placeOrder = async () => {
    setConfirming(false);
    setPlacing(true); setError("");
    try {
      if (!destination) {
        setError("Share your delivery location to calculate the route estimate before checkout.");
        setPlacing(false);
        return;
      }
      const order = await api.checkout(method, destination);
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
            <h2 style={{ margin: 0 }}>Delivery location</h2>
            <p className="muted" style={{ margin: 0 }}>
              Share your location to estimate a delivery route from Abuja, Nigeria. Your coordinates
              are used only to calculate this estimate and are not saved with your order. Use this
              if you are at the delivery destination.
            </p>
            <button className="btn btn-ghost" onClick={useCurrentLocation} disabled={locating}>
              {locating ? "Getting location…" : destination ? "Refresh my location" : "Use my current location"}
            </button>
            {estimate && <p className="muted" style={{ margin: 0 }}>
              Estimated route distance from Abuja: {estimate.delivery_distance.toFixed(1)} km
            </p>}
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
              disabled={!method || !destination || !estimate || placing} onClick={() => setConfirming(true)}>
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
