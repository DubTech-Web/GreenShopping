import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import type { OrderSummary } from "../types";
import { ConfirmModal, ErrorNote, money, Spinner } from "../components";

export default function Orders() {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState("");
  const [cancelId, setCancelId] = useState<number | null>(null);

  const cancel = async (id: number) => {
    setCancelId(null);
    try {
      const updated = await api.cancelOrder(id);
      setOrders((current) => current?.map((order) => order.id === id ? { ...order, status: updated.status } : order) ?? null);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Could not cancel order"); }
  };

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
            <thead><tr><th>Order</th><th>Date</th><th>Delivery</th><th>Carbon</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td><Link to={`/orders/${o.id}`}>#{o.id}</Link></td>
                  <td className="muted">{new Date(o.created_at).toLocaleDateString()}</td>
                  <td style={{ textTransform: "capitalize" }}>{o.delivery_method}</td>
                  <td className="mono">{o.carbon_impact.toFixed(2)} kg</td>
                  <td className="mono">{money(o.total_amount)}</td>
                  <td><span className="badge badge-neutral">{o.status}</span></td>
                  <td><div className="row order-actions">
                    <Link to={`/orders/${o.id}`} className="btn btn-ghost btn-sm">View details</Link>
                    {["Pending Payment", "Paid", "Processing"].includes(o.status) &&
                      <button className="btn btn-ghost btn-sm" onClick={() => setCancelId(o.id)}>Cancel</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {cancelId !== null && <ConfirmModal title="Cancel order?" message="This may restore product inventory." confirmLabel="Cancel order" onConfirm={() => cancel(cancelId)} onCancel={() => setCancelId(null)} />}
    </div>
  );
}
