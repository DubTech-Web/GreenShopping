import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Order } from "../types";
import { ErrorNote, money, Spinner } from "../components";

export default function OrderConfirmation() {
  const { id } = useParams();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.order(Number(id)).then(setOrder).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spinner />;
  if (error) return <ErrorNote message={error} />;
  if (!order) return null;

  return (
    <div className="stack" style={{ maxWidth: 640, margin: "0 auto" }}>
      <div className="card card-pad center-text stack">
        <div style={{ fontSize: "2.6rem" }}>✅</div>
        <h1 style={{ margin: 0 }}>Order confirmed</h1>
        <p className="muted">Order #{order.id} · {order.status}</p>
      </div>

      <div className="card card-pad stack">
        <h2 style={{ marginTop: 0 }}>Items</h2>
        {order.items.map((it) => (
          <div key={it.product_id} className="impact-row">
            <span>{it.name} × {it.quantity}</span>
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
