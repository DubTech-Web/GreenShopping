import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../api";
import type { Order } from "../types";
import { ErrorNote, money, Spinner } from "../components";
import { useApp } from "../store";

export default function OrderConfirmation() {
  const { id } = useParams();
  const location = useLocation();
  const { refreshCart } = useApp();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const reference = params.get("reference") || params.get("trxref");
    const load = reference ? api.verifyPayment(reference) : api.order(Number(id));
    load
      .then((ord) => {
        setOrder(ord);
        refreshCart();
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, location.search, refreshCart]);

  if (loading) return <Spinner />;
  if (error) return <ErrorNote message={error} />;
  if (!order) return null;

  return (
    <div className="stack" style={{ maxWidth: 640, margin: "0 auto" }}>
      <div className="card card-pad center-text stack">
        <h1 style={{ margin: 0 }}>Order #{order.id} details</h1>
        <p className="muted">Placed {new Date(order.created_at).toLocaleString()} · <span style={{ textTransform: "capitalize" }}>{order.status}</span></p>
      </div>

      <div className="card card-pad stack">
        <h2 style={{ marginTop: 0 }}>Items</h2>
        {order.items.map((it) => (
          <div key={it.product_id} className="impact-row">
            <Link to={`/products/${it.product_id}`}>{it.name} × {it.quantity}</Link>
            <span className="mono">{money(it.line_total)}</span>
          </div>
        ))}
        <div className="impact-row impact-total"><span>Total</span>
          <span className="mono">{money(order.total_amount)}</span></div>
      </div>

      <div className="card card-pad eco-alt">
        <div className="impact-row"><span>Delivery method</span>
          <strong style={{ textTransform: "capitalize" }}>{order.delivery_method}</strong></div>
        <div className="impact-row"><span>Distance</span>
          <span className="mono">{order.delivery_distance} km</span></div>
        <div className="impact-row impact-total"><span>Estimated carbon impact</span>
          <span className="mono">{order.carbon_impact.toFixed(2)} kg CO₂e</span></div>
      </div>

      <div className="row" style={{ justifyContent: "center" }}>
        <Link to="/products" className="btn btn-ghost">Continue shopping</Link>
        <Link to="/orders" className="btn btn-primary">View my orders</Link>
      </div>
    </div>
  );
}
