import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { OrderSummary } from "../types";
import { ErrorNote, money, Spinner } from "../components";

export default function Orders() {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.orders().then(setOrders).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (!orders) return <Spinner />;

  return (
    <div className="stack">
      <h1>My orders</h1>
      {orders.length === 0 ? (
        <div className="panel center-text">No orders yet. <Link to="/products">Start shopping</Link>.</div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Order</th><th>Date</th><th>Delivery</th><th>Carbon</th><th>Total</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td><Link to={`/orders/${o.id}`}>#{o.id}</Link></td>
                  <td className="muted">{new Date(o.created_at).toLocaleDateString()}</td>
                  <td style={{ textTransform: "capitalize" }}>{o.delivery_method}</td>
                  <td className="mono">{o.carbon_impact.toFixed(2)} kg</td>
                  <td className="mono">{money(o.total_amount)}</td>
                  <td><span className="badge badge-neutral">{o.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
