import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import type { Dashboard, RestockRow } from "../../types";
import { ErrorNote, money, Spinner } from "../../components";

export default function AdminDashboard() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [restock, setRestock] = useState<RestockRow[]>([]);
  const [error, setError] = useState("");

  // Two independent aggregate calls; no polling, no auto-refresh (Spec §18).
  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setError(e.message));
    api.restock().then(setRestock).catch(() => {});
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (!d) return <Spinner />;

  const tiles = [
    { label: "Total sales", value: money(d.total_sales) },
    { label: "Total orders", value: d.total_orders },
    { label: "Products", value: d.total_products },
    { label: "Low-stock products", value: d.low_stock_products, cls: "metric-accent" },
    { label: "Eco delivery", value: `${d.eco_delivery_percentage}%`, cls: "metric-eco" },
    { label: "Total est. CO₂", value: `${d.total_estimated_co2.toFixed(1)} kg`, cls: "metric-eco" },
  ];

  return (
    <div className="stack">
      <div className="spread">
        <h1 style={{ margin: 0 }}>Admin dashboard</h1>
        <div className="row">
          <Link to="/admin/products" className="btn btn-ghost btn-sm">Products</Link>
          <Link to="/admin/orders" className="btn btn-ghost btn-sm">Orders</Link>
          <Link to="/admin/reports" className="btn btn-primary btn-sm">Reports</Link>
        </div>
      </div>

      <div className="metric-grid">
        {tiles.map((t) => (
          <div key={t.label} className="card metric">
            <div className="metric-label">{t.label}</div>
            <div className={`metric-value ${t.cls ?? ""}`}>{t.value}</div>
          </div>
        ))}
      </div>

      <div className="card card-pad stack">
        <h2 style={{ margin: 0 }}>Restock recommendations</h2>
        {restock.length === 0 ? (
          <p className="muted">All products are sufficiently stocked.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Product</th><th>Status</th><th>Stock</th><th>Sold (30d)</th><th>Reorder</th><th>Reason</th></tr></thead>
              <tbody>
                {restock.map((r) => (
                  <tr key={r.product_id}>
                    <td>{r.name}</td>
                    <td><span className={`badge ${r.status === "out_of_stock" ? "badge-danger" : "badge-warn"}`}>
                      {r.status.replace("_", " ")}</span></td>
                    <td className="mono">{r.stock_quantity}</td>
                    <td className="mono">{r.recent_units_sold}</td>
                    <td className="mono"><strong>+{r.suggested_reorder_qty}</strong></td>
                    <td className="muted">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
