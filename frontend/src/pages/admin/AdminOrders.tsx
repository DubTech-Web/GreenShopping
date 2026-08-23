import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api";
import type { AdminOrderRow } from "../../types";
import { ErrorNote, money, Spinner } from "../../components";

const STATUSES = ["Pending Payment", "Paid", "Processing", "Shipped", "Delivered", "Cancelled"];

export default function AdminOrders() {
  const [rows, setRows] = useState<AdminOrderRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.adminOrders().then((d) => setRows(d.items)).catch((e) => setError(e.message));
  }, []);

  const setStatus = async (id: number, status: string) => {
    try {
      const updated = await api.updateOrderStatus(id, status);
      setRows((rs) => rs!.map((r) => (r.id === id ? updated : r)));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed");
    }
  };

  if (error && !rows) return <ErrorNote message={error} />;
  if (!rows) return <Spinner />;

  return (
    <div className="stack">
      <div className="spread">
        <h1 style={{ margin: 0 }}>Orders</h1>
        <Link to="/admin" className="btn btn-ghost btn-sm">← Dashboard</Link>
      </div>
      {error && <ErrorNote message={error} />}
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Order</th><th>Customer</th><th>Date</th><th>Delivery</th><th>Carbon</th><th>Total</th><th>Status</th></tr></thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id}>
                <td>#{o.id}</td>
                <td className="muted">#{o.customer_id}</td>
                <td className="muted">{new Date(o.created_at).toLocaleDateString()}</td>
                <td style={{ textTransform: "capitalize" }}>{o.delivery_method}</td>
                <td className="mono">{o.carbon_impact.toFixed(2)} kg</td>
                <td className="mono">{money(o.total_amount)}</td>
                <td>
                  <select className="select" value={o.status} onChange={(e) => setStatus(o.id, e.target.value)}>
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
