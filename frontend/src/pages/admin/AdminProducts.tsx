import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api";
import type { AdminProductRow } from "../../types";
import { ErrorNote, money, Spinner } from "../../components";

export default function AdminProducts() {
  const [rows, setRows] = useState<AdminProductRow[] | null>(null);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    api.adminProducts().then((d) => setRows(d.items)).catch((e) => setError(e.message));
  }, []);

  const saveStock = async (id: number, stock_quantity: number) => {
    setSavingId(id);
    try {
      const updated = await api.updateProduct(id, { stock_quantity });
      setRows((rs) => rs!.map((r) => (r.id === id ? updated : r)));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed");
    } finally { setSavingId(null); }
  };

  if (error && !rows) return <ErrorNote message={error} />;
  if (!rows) return <Spinner />;

  const statusBadge = (s: string) =>
    s === "out_of_stock" ? "badge-danger" : s === "low_stock" ? "badge-warn" : "badge-neutral";

  return (
    <div className="stack">
      <div className="spread">
        <h1 style={{ margin: 0 }}>Products & inventory</h1>
        <Link to="/admin" className="btn btn-ghost btn-sm">← Dashboard</Link>
      </div>
      {error && <ErrorNote message={error} />}
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Eco</th><th>Stock</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="muted">{r.category}</td>
                <td className="mono">{money(r.price)}</td>
                <td className="mono">{r.eco_score}{r.is_eco_friendly ? " 🌱" : ""}</td>
                <td>
                  <input type="number" min={0} defaultValue={r.stock_quantity} className="input"
                    style={{ width: 80 }}
                    onBlur={(e) => {
                      const v = Math.max(0, Number(e.target.value));
                      if (v !== r.stock_quantity) saveStock(r.id, v);
                    }} />
                </td>
                <td><span className={`badge ${statusBadge(r.stock_status)}`}>
                  {r.stock_status.replace("_", " ")}</span></td>
                <td className="muted">{savingId === r.id ? "Saving…" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="reason">Edit a stock value and click away to save (one PATCH per change — Spec §16).</p>
    </div>
  );
}
