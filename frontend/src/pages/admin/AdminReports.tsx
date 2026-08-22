import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../../api";
import type { SalesReport, SustainabilityReport } from "../../types";
import { ErrorNote, money, Spinner } from "../../components";

const MOSS = "#4b5d2a";
const TERRA = "#c2703d";
const PIE_COLORS = ["#4b5d2a", "#c2703d", "#6b8e3d", "#a95d2f", "#2f7d4f", "#b7791f"];

export default function AdminReports() {
  const [sales, setSales] = useState<SalesReport | null>(null);
  const [sust, setSust] = useState<SustainabilityReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.salesReport(), api.sustainabilityReport()])
      .then(([s, u]) => { setSales(s); setSust(u); })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (!sales || !sust) return <Spinner />;

  return (
    <div className="stack">
      <div className="spread">
        <h1 style={{ margin: 0 }}>Reports</h1>
        <Link to="/admin" className="btn btn-ghost btn-sm">← Dashboard</Link>
      </div>

      {/* Sales */}
      <section className="card card-pad stack">
        <h2 style={{ marginTop: 0 }}>Sales</h2>
        <div className="metric-grid">
          <Tile label="Total sales" value={money(sales.total_sales)} />
          <Tile label="Total orders" value={sales.total_orders} />
        </div>
        <div style={{ display: "grid", gap: 20, gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)" }}>
          <div>
            <h3>Best sellers (units)</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sales.best_sellers} margin={{ left: -18 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="units_sold" fill={MOSS} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>Revenue by category</h3>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={sales.sales_by_category} dataKey="value" nameKey="name" outerRadius={90} label>
                  {sales.sales_by_category.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Sustainability */}
      <section className="card card-pad stack">
        <h2 style={{ marginTop: 0 }}>Sustainability <span className="reason">(estimates, kg CO₂e)</span></h2>
        <div className="metric-grid">
          <Tile label="Total est. CO₂" value={`${sust.total_estimated_co2.toFixed(1)} kg`} eco />
          <Tile label="Avg CO₂ / order" value={`${sust.average_co2_per_order.toFixed(2)} kg`} eco />
          <Tile label="Eco deliveries" value={`${sust.eco_delivery_percentage}%`} eco />
          <Tile label="Eco products sold" value={`${sust.eco_products_sold_units} units`} eco />
          <Tile label="Est. CO₂ saved vs Express" value={`${sust.estimated_co2_saved_vs_express.toFixed(2)} kg`} accent />
        </div>
        <div>
          <h3>Estimated CO₂: actual vs all-Express baseline</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart layout="vertical" margin={{ left: 30 }} data={[
              { name: "Actual", co2: sust.total_estimated_co2 },
              { name: "All-Express baseline", co2: sust.total_estimated_co2 + sust.estimated_co2_saved_vs_express },
            ]}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="co2" radius={[0, 4, 4, 0]}>
                <Cell fill={MOSS} /><Cell fill={TERRA} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

function Tile({ label, value, eco, accent }: { label: string; value: string | number; eco?: boolean; accent?: boolean }) {
  return (
    <div className="card metric">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${eco ? "metric-eco" : accent ? "metric-accent" : ""}`}>{value}</div>
    </div>
  );
}
